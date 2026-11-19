import streamlit as st
import pandas as pd
import polars as pl
import numpy as np
from scipy.stats import norm
import requests
import nflreadpy as nfl

# ==========================================
# --- PAGE CONFIG & TERMINAL STYLING ---
# ==========================================
st.set_page_config(page_title="NFL Syndicate Execution Terminal", layout="wide")

st.markdown("""
<style>
    .metric-card {
        background-color: #0e1117;
        border: 1px solid #262730;
        padding: 12px 16px;
        border-radius: 6px;
    }
    .gate-pass { background-color: #1b4332; color: #74c69d; padding: 4px 10px; border-radius: 4px; font-weight: 700; }
    .gate-caution { background-color: #663c00; color: #ffb703; padding: 4px 10px; border-radius: 4px; font-weight: 700; }
    .gate-lockout { background-color: #590d22; color: #ff758f; padding: 4px 10px; border-radius: 4px; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

st.title("NFL Syndicate Execution Terminal")
st.caption("Closed-Loop Quantitative Market Intelligence — 2026 Regular Season Feed")

# ==========================================
# --- SIDEBAR: RISK & STAGE 0 CONTROLS ---
# ==========================================
st.sidebar.header("Terminal Controls")
if st.sidebar.button("🔄 Force Refresh Live Data"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Portfolio & Heat Cap (R-Units)")
bankroll = st.sidebar.number_input("Trading Bankroll ($)", min_value=1000.0, value=25000.0, step=1000.0)
max_heat_pct = st.sidebar.number_input("Max Open Heat Cap (%)", min_value=0.50, max_value=10.0, value=2.00, step=0.25)
apex_r_pct = st.sidebar.number_input("Apex Tier Risk (% R)", min_value=0.05, max_value=2.0, value=0.35, step=0.05)
std_r_pct = st.sidebar.number_input("Standard Tier Risk (% R)", min_value=0.05, max_value=2.0, value=0.25, step=0.05)
caut_r_pct = st.sidebar.number_input("Caution Tier Risk (% R)", min_value=0.05, max_value=2.0, value=0.125, step=0.025)

st.sidebar.markdown("---")
st.sidebar.subheader("Stage 0 Gate Thresholds")
min_snap_skill = st.sidebar.slider("Min Snap % Liquidity (WR/TE)", 20, 90, 60, 5)
min_snap_rb = st.sidebar.slider("Min Snap % Liquidity (RB)", 20, 90, 45, 5)
max_wind_mph = st.sidebar.slider("Weather Wind Lockout (MPH)", 10, 30, 15, 1)
min_temp_f = st.sidebar.slider("Weather Cold Caution (°F)", 10, 45, 32, 1)
min_edge_pct = st.sidebar.number_input("Min No-Vig Edge (%)", min_value=1.0, max_value=15.0, value=3.5, step=0.5)

st.sidebar.markdown("---")
st.sidebar.subheader("Live Odds Feed (Optional)")
default_odds_key = st.secrets.get("ODDS_API_KEY", "") if hasattr(st, "secrets") else ""
odds_api_key = st.sidebar.text_input("The Odds API Key", value=default_odds_key, type="password")

# ==========================================
# --- 2026 DATA LOADERS (SCHEMA-HARDENED) ---
# ==========================================
@st.cache_data(ttl=300)
def load_all_2026_feeds():
    data = {
        "stats": pd.DataFrame(),
        "schedules": pd.DataFrame(),
        "snaps": pd.DataFrame(),
        "team_eff": pd.DataFrame(),
        "def_eff": pd.DataFrame()
    }

    # 1. Player Stats (2026)
    try:
        p_stats = nfl.load_player_stats(seasons=[2026])
        if p_stats is not None and not p_stats.is_empty():
            df = p_stats.to_pandas()
            if "season" in df.columns:
                df = df[df["season"] == 2026]
            if "season_type" in df.columns:
                df = df[df["season_type"].astype(str).str.upper() == "REG"]

            # Normalize nflreadpy vs nfl_data_py schema column names
            if "recent_team" not in df.columns:
                if "team" in df.columns:
                    df["recent_team"] = df["team"]
                elif "posteam" in df.columns:
                    df["recent_team"] = df["posteam"]
                else:
                    df["recent_team"] = "UNK"

            if "player_display_name" not in df.columns:
                if "player_name" in df.columns:
                    df["player_display_name"] = df["player_name"]
                elif "player" in df.columns:
                    df["player_display_name"] = df["player"]
                else:
                    df["player_display_name"] = "UNKNOWN"

            data["stats"] = df
    except Exception as e:
        st.error(f"Player stats feed error: {e}")

    # 2. Schedules, Lines, Weather & Rest (2026)
    try:
        sched = nfl.load_schedules(seasons=[2026])
        if sched is not None and not sched.is_empty():
            sdf = sched.to_pandas()
            if "season" in sdf.columns:
                sdf = sdf[sdf["season"] == 2026]
            if "game_type" in sdf.columns:
                sdf = sdf[sdf["game_type"].astype(str).str.upper() == "REG"]
            data["schedules"] = sdf
    except Exception as e:
        st.warning(f"Schedules feed notice: {e}")

    # 3. Snap Counts (2026)
    try:
        snaps = nfl.load_snap_counts(seasons=[2026])
        if snaps is not None and not snaps.is_empty():
            sndf = snaps.to_pandas()
            if "season" in sndf.columns:
                sndf = sndf[sndf["season"] == 2026]
            if "game_type" in sndf.columns:
                sndf = sndf[sndf["game_type"].astype(str).str.upper() == "REG"]
            if "player" not in sndf.columns and "player_display_name" in sndf.columns:
                sndf["player"] = sndf["player_display_name"]
            data["snaps"] = sndf
    except Exception:
        pass

    # 4. Play-by-Play Neutral-Script Efficiency (Polars fast aggregation)
    try:
        pbp = nfl.load_pbp(seasons=[2026])
        if pbp is not None and not pbp.is_empty():
            pbp_reg = pbp.filter(
                (pl.col("season_type") == "REG") &
                (pl.col("play_type").is_in(["pass", "run"])) &
                (pl.col("epa").is_not_null())
            )
            if "wp" in pbp_reg.columns:
                pbp_neutral = pbp_reg.filter((pl.col("wp") >= 0.05) & (pl.col("wp") <= 0.95))
            else:
                pbp_neutral = pbp_reg

            off_agg = (
                pbp_neutral.group_by("posteam")
                .agg([
                    pl.col("epa").filter(pl.col("play_type") == "pass").mean().alias("OFF_PASS_EPA"),
                    pl.col("epa").filter(pl.col("play_type") == "run").mean().alias("OFF_RUSH_EPA"),
                    pl.col("success").mean().alias("OFF_SUCCESS_RATE"),
                    (pl.col("play_type") == "pass").mean().alias("PASS_RATE"),
                    pl.col("pass_oe").mean().alias("PROE") if "pass_oe" in pbp_neutral.columns else pl.lit(0.0).alias("PROE")
                ])
                .drop_nulls("posteam")
                .to_pandas()
            )
            data["team_eff"] = off_agg

            def_agg = (
                pbp_neutral.group_by("defteam")
                .agg([
                    pl.col("epa").filter(pl.col("play_type") == "pass").mean().alias("DEF_PASS_EPA"),
                    pl.col("epa").filter(pl.col("play_type") == "run").mean().alias("DEF_RUSH_EPA"),
                    pl.col("success").filter(pl.col("play_type") == "pass").mean().alias("DEF_PASS_SUCC"),
                    pl.col("success").filter(pl.col("play_type") == "run").mean().alias("DEF_RUSH_SUCC"),
                    pl.col("epa").mean().alias("DEF_TOTAL_EPA")
                ])
                .drop_nulls("defteam")
                .to_pandas()
            )
            data["def_eff"] = def_agg
    except Exception:
        pass

    return data

@st.cache_data(ttl=120)
def fetch_live_odds(api_key: str):
    if not api_key:
        return pd.DataFrame()
    url = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american"
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            games = resp.json()
            rows = []
            for g in games:
                home = g.get("home_team", "")
                away = g.get("away_team", "")
                book = g["bookmakers"][0] if g.get("bookmakers") else None
                spread_h, total_pts = np.nan, np.nan
                if book:
                    for m in book.get("markets", []):
                        if m["key"] == "spreads":
                            for o in m["outcomes"]:
                                if o["name"] == home:
                                    spread_h = o.get("point", np.nan)
                        elif m["key"] == "totals":
                            if m["outcomes"]:
                                total_pts = m["outcomes"][0].get("point", np.nan)
                rows.append({
                    "MATCHUP": f"{away} @ {home}",
                    "BOOKMAKER": book["title"] if book else "N/A",
                    "LIVE_SPREAD_HOME": spread_h,
                    "LIVE_TOTAL": total_pts
                })
            return pd.DataFrame(rows)
    except Exception:
        pass
    return pd.DataFrame()

feeds = load_all_2026_feeds()
stats_df = feeds["stats"]
sched_df = feeds["schedules"]
snaps_df = feeds["snaps"]
team_eff_df = feeds["team_eff"]
def_eff_df = feeds["def_eff"]

if stats_df.empty:
    st.warning("No regular season records found for 2026 yet. Stream syncing...")
    st.stop()

# ==========================================
# --- MERGE SNAP COUNTS & COMPUTE VOLATILITY ---
# ==========================================
if not snaps_df.empty and {"player", "team", "week", "offense_pct"}.issubset(snaps_df.columns) and "week" in stats_df.columns:
    snaps_clean = snaps_df[["player", "team", "week", "offense_pct"]].copy()
    snaps_clean["join_name"] = snaps_clean["player"].astype(str).str.upper().str.strip()
    snaps_clean["join_team"] = snaps_clean["team"].astype(str).str.upper().str.strip()

    stats_df["join_name"] = stats_df["player_display_name"].astype(str).str.upper().str.strip()
    stats_df["join_team"] = stats_df["recent_team"].astype(str).str.upper().str.strip()

    stats_df = pd.merge(
        stats_df,
        snaps_clean[["join_name", "join_team", "week", "offense_pct"]],
        on=["join_name", "join_team", "week"],
        how="left"
    )
    stats_df["SNAP_PCT"] = (stats_df["offense_pct"] * 100.0).round(1)
else:
    stats_df["SNAP_PCT"] = np.nan

# ==========================================
# --- QUANTITATIVE HELPER FUNCTIONS ---
# ==========================================
def american_to_implied_prob(odds: float) -> float:
    if odds < 0:
        return abs(odds) / (abs(odds) + 100.0)
    elif odds > 0:
        return 100.0 / (odds + 100.0)
    return 0.50

def remove_vig(over_odds: float, under_odds: float):
    p_o = american_to_implied_prob(over_odds)
    p_u = american_to_implied_prob(under_odds)
    total = p_o + p_u
    return (p_o / total), (p_u / total)

def compute_player_volatility_profile(p_logs: pd.DataFrame, target_col: str):
    if target_col not in p_logs.columns:
        return 0.0, 0.0, 0.0, 0.0, "NO DATA"
    p_sorted = p_logs.sort_values(by="week", ascending=False) if "week" in p_logs.columns else p_logs
    vals = p_sorted[target_col].dropna().values
    if len(vals) == 0:
        return 0.0, 0.0, 0.0, 0.0, "NO DATA"

    season_mean = float(np.mean(vals))
    l5_vals = vals[:5]
    l5_mean = float(np.mean(l5_vals))
    l5_median = float(np.median(l5_vals))
    raw_std = float(np.std(l5_vals, ddof=1)) if len(l5_vals) > 1 else season_mean * 0.25
    player_atr = max(raw_std, season_mean * 0.15, 1.0)

    cv = player_atr / max(l5_mean, 1.0)
    regime = "COILED (LOW ATR)" if cv <= 0.22 else ("NORMAL ATR" if cv <= 0.38 else "HIGH-BETA (WIDE ATR)")
    return season_mean, l5_mean, l5_median, player_atr, regime

def build_position_cluster_table(pos_df: pd.DataFrame, base_agg: dict, target_metric: str, sort_col: str):
    if pos_df.empty:
        return pd.DataFrame()

    valid_agg = {k: v for k, v in base_agg.items() if k in pos_df.columns}
    if "week" in pos_df.columns:
        valid_agg["week"] = "nunique"
    if "SNAP_PCT" in pos_df.columns:
        valid_agg["SNAP_PCT"] = "mean"

    if not valid_agg:
        return pd.DataFrame()

    grouped = pos_df.groupby(["player_display_name", "recent_team"], as_index=False).agg(valid_agg)
    grouped = grouped.rename(columns={"week": "G", "recent_team": "TEAM", "player_display_name": "PLAYER"})

    l5_means, player_atrs, regimes = [], [], []
    for _, row in grouped.iterrows():
        p_sub = pos_df[pos_df["player_display_name"] == row["PLAYER"]]
        _, l5_m, _, p_atr, reg = compute_player_volatility_profile(p_sub, target_metric)
        l5_means.append(round(l5_m, 1))
        player_atrs.append(round(p_atr, 1))
        regimes.append(reg)

    grouped["L5_AVG"] = l5_means
    grouped["ATR_STD"] = player_atrs
    grouped["VOL_REGIME"] = regimes

    for col in ["passing_epa", "rushing_epa", "receiving_epa", "dakota", "wopr", "target_share", "air_yards_share", "SNAP_PCT"]:
        if col in grouped.columns:
            if col in ["target_share", "air_yards_share"]:
                grouped[col] = (grouped[col] * 100.0).round(1)
            elif col == "SNAP_PCT":
                grouped[col] = grouped[col].round(1)
            else:
                grouped[col] = grouped[col].round(2)

    if sort_col in grouped.columns:
        grouped = grouped.sort_values(by=sort_col, ascending=False)

    return grouped

# ==========================================
# --- MAIN TERMINAL NAVIGATION TABS ---
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs([
    "1. STAGE 0: SLATE & MACRO TIDE",
    "2. CQS & FAIR-LINE EXECUTION",
    "3. PLAYER CLUSTER & ATR MATRIX",
    "4. TEAM DEFENSE & FUNNEL MATRIX"
])

# ==============================================================================
# TAB 1: STAGE 0 SLATE & MACRO TIDE
# ==============================================================================
with tab1:
    st.subheader("Stage 0 Macro Environment, Odds & Weather Gates")

    if sched_df.empty or "week" not in sched_df.columns:
        st.info("2026 schedule feed unavailable.")
    else:
        available_weeks = sorted(sched_df["week"].dropna().unique().astype(int).tolist())
        unplayed = sched_df[sched_df["result"].isna()] if "result" in sched_df.columns else pd.DataFrame()
        valid_unplayed_weeks = unplayed["week"].dropna() if not unplayed.empty else pd.Series(dtype=int)
        default_week = int(valid_unplayed_weeks.min()) if not valid_unplayed_weeks.empty else max(available_weeks)

        selected_week = st.selectbox("Select NFL Week", options=available_weeks, index=available_weeks.index(default_week))
        week_games = sched_df[sched_df["week"] == selected_week].copy()

        slate_rows = []
        for _, g in week_games.iterrows():
            home = g.get("home_team", "")
            away = g.get("away_team", "")
            spread = g.get("spread_line", np.nan)
            total = g.get("total_line", np.nan)
            roof = str(g.get("roof", "outdoors")).upper()
            wind = g.get("wind", np.nan)
            temp = g.get("temp", np.nan)
            h_rest = g.get("home_rest", 7)
            a_rest = g.get("away_rest", 7)

            if pd.notna(total) and pd.notna(spread):
                home_imp = round((total + spread) / 2.0, 1)
                away_imp = round((total - spread) / 2.0, 1)
            else:
                home_imp, away_imp = np.nan, np.nan

            is_dome = roof in ["DOME", "CLOSED"]
            wind_val = 0.0 if is_dome else (float(wind) if pd.notna(wind) else 0.0)
            temp_val = 70.0 if is_dome else (float(temp) if pd.notna(temp) else 65.0)

            gate_status = "SURF / GO"
            if not is_dome and wind_val >= max_wind_mph:
                gate_status = "WIND LOCKOUT"
            elif not is_dome and temp_val <= min_temp_f:
                gate_status = "COLD CAUTION"
            elif pd.notna(h_rest) and pd.notna(a_rest) and abs(h_rest - a_rest) >= 4:
                gate_status = "REST ASYMMETRY"

            slate_rows.append({
                "WEEK": selected_week,
                "MATCHUP": f"{away} @ {home}",
                "SPREAD (HOME)": f"{-spread:+.1f}" if pd.notna(spread) else "N/A",
                "TOTAL": total,
                "AWAY IMP": away_imp,
                "HOME IMP": home_imp,
                "ROOF": roof,
                "WIND (MPH)": 0 if is_dome else wind,
                "TEMP (°F)": 70 if is_dome else temp,
                "REST (A/H)": f"{int(a_rest)}d / {int(h_rest)}d" if pd.notna(a_rest) and pd.notna(h_rest) else "N/A",
                "STAGE 0 GATE": gate_status
            })

        slate_display = pd.DataFrame(slate_rows)
        st.dataframe(slate_display, hide_index=True, use_container_width=True)

        if odds_api_key:
            st.markdown("#### Live Sportsbook Order Book (The Odds API)")
            live_odds_df = fetch_live_odds(odds_api_key)
            if not live_odds_df.empty:
                st.dataframe(live_odds_df, hide_index=True, use_container_width=True)
            else:
                st.info("No live NFL lines returned or API quota reached.")

    st.markdown("---")
    st.subheader("Neutral-Script Team Offensive Efficiency & Pace (5%–95% WP)")
    if not team_eff_df.empty:
        eff_disp = team_eff_df.copy()
        eff_disp["OFF_PASS_EPA"] = eff_disp["OFF_PASS_EPA"].round(3)
        eff_disp["OFF_RUSH_EPA"] = eff_disp["OFF_RUSH_EPA"].round(3)
        eff_disp["OFF_SUCCESS_RATE"] = (eff_disp["OFF_SUCCESS_RATE"] * 100.0).round(1)
        eff_disp["PASS_RATE"] = (eff_disp["PASS_RATE"] * 100.0).round(1)
        eff_disp["PROE"] = (eff_disp["PROE"] * 100.0).round(1)
        eff_disp = eff_disp.sort_values(by="OFF_PASS_EPA", ascending=False)
        eff_disp.columns = ["TEAM", "NEUTRAL PASS EPA", "NEUTRAL RUSH EPA", "SUCCESS %", "PASS RATE %", "PROE %"]
        st.dataframe(eff_disp, hide_index=True, height=340, use_container_width=True)
    else:
        st.info("Play-by-play neutral efficiency data loading or unavailable.")

# ==============================================================================
# TAB 2: CQS & FAIR-LINE EXECUTION ENGINE
# ==============================================================================
with tab2:
    st.subheader("Composite Quality Score (CQS) & Fair-Line Execution Calculator")
    st.caption("Evaluates Player ATR, Matchup Funnel Clearance, Stage 0 Weather/Snap Liquidity, and R-Unit Position Sizing.")

    c1, c2, c3 = st.columns(3)
    with c1:
        calc_pos = st.selectbox("1. Position / Market", ["QB (Passing Yards)", "RB (Rushing Yards)", "WR (Receiving Yards)", "TE (Receiving Yards)"])
    pos_code = calc_pos.split(" ")[0]
    metric_map = {
        "QB": "passing_yards",
        "RB": "rushing_yards",
        "WR": "receiving_yards",
        "TE": "receiving_yards"
    }
    target_stat = metric_map[pos_code]

    pos_pool = stats_df[stats_df["position"].astype(str).str.upper() == pos_code].copy() if "position" in stats_df.columns else pd.DataFrame()
    player_names = sorted(pos_pool["player_display_name"].dropna().unique().tolist()) if not pos_pool.empty else []

    with c2:
        calc_player = st.selectbox("2. Select Player", options=player_names if player_names else ["No Players Available"])
    with c3:
        all_teams = sorted(stats_df["recent_team"].dropna().unique().tolist())
        calc_opp = st.selectbox("3. Upcoming Opponent", options=all_teams if all_teams else ["N/A"])

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        bet_side = st.selectbox("4. Trade Direction", ["OVER", "UNDER"])
    with m2:
        book_line = st.number_input("5. Sportsbook Line", min_value=0.5, max_value=500.0, value=65.5, step=0.5)
    with m3:
        side_odds = st.number_input("6. Target Side Odds", min_value=-500, max_value=500, value=-110, step=5)
    with m4:
        opp_odds = st.number_input("7. Opposing Side Odds", min_value=-500, max_value=500, value=-110, step=5)

    if calc_player and calc_player != "No Players Available":
        p_history = pos_pool[pos_pool["player_display_name"] == calc_player]
        if "week" in p_history.columns:
            p_history = p_history.sort_values(by="week", ascending=False)
        s_mean, l5_mean, l5_med, p_atr, vol_regime = compute_player_volatility_profile(p_history, target_stat)
        avg_snap = float(p_history["SNAP_PCT"].head(3).mean()) if "SNAP_PCT" in p_history.columns and p_history["SNAP_PCT"].notna().any() else 75.0

        funnel_adj = 0.0
        if not def_eff_df.empty and calc_opp in def_eff_df["defteam"].values:
            opp_row = def_eff_df[def_eff_df["defteam"] == calc_opp].iloc[0]
            if pos_code in ["QB", "WR", "TE"]:
                opp_def_epa = float(opp_row["DEF_PASS_EPA"])
                lg_avg_epa = float(def_eff_df["DEF_PASS_EPA"].mean())
            else:
                opp_def_epa = float(opp_row["DEF_RUSH_EPA"])
                lg_avg_epa = float(def_eff_df["DEF_RUSH_EPA"].mean())
            epa_delta = opp_def_epa - lg_avg_epa
            funnel_adj = np.clip(epa_delta * 2.5, -0.35, 0.35) * p_atr

        raw_proj = (0.60 * l5_mean) + (0.40 * s_mean) + funnel_adj
        fair_proj = round(raw_proj, 1)

        z_score = (book_line - fair_proj) / p_atr
        prob_over = float(1.0 - norm.cdf(z_score))
        prob_under = float(norm.cdf(z_score))

        novig_over, novig_under = remove_vig(side_odds, opp_odds) if bet_side == "OVER" else remove_vig(opp_odds, side_odds)
        model_prob = prob_over if bet_side == "OVER" else prob_under
        book_novig_prob = novig_over if bet_side == "OVER" else novig_under
        edge_pct = (model_prob - book_novig_prob) * 100.0

        s_eff = np.clip((edge_pct / 10.0) * 100.0, 0.0, 100.0)
        cv_ratio = p_atr / max(l5_mean, 1.0)
        s_coil = np.clip(((0.45 - cv_ratio) / 0.25) * 100.0, 0.0, 100.0)
        s_runway = np.clip(50.0 + (funnel_adj / max(p_atr, 1.0)) * 140.0, 0.0, 100.0)
        snap_req = min_snap_rb if pos_code == "RB" else min_snap_skill
        s_liq = 100.0 if avg_snap >= snap_req else 0.0

        cqs_score = round((0.35 * s_eff) + (0.30 * s_coil) + (0.25 * s_runway) + (0.10 * s_liq), 1)

        liquidity_ok = avg_snap >= snap_req
        gate_label = "LOCKOUT: NO EDGE"
        r_tier = 0.0

        if not liquidity_ok:
            gate_label = f"LOCKOUT: LOW SNAP ({avg_snap:.0f}% < {snap_req}%)"
            r_tier = 0.0
        elif edge_pct < min_edge_pct:
            gate_label = f"PASS: EDGE {edge_pct:.1f}% < {min_edge_pct:.1f}%"
            r_tier = 0.0
        elif cqs_score < 60.0:
            gate_label = f"PASS: CQS {cqs_score} < 60.0"
            r_tier = 0.0
        else:
            if cqs_score >= 80.0 and edge_pct >= 7.5:
                gate_label = "EXECUTE (APEX GEAR)"
                r_tier = apex_r_pct
            elif cqs_score >= 65.0 and edge_pct >= 5.0:
                gate_label = "EXECUTE (STANDARD GEAR)"
                r_tier = std_r_pct
            else:
                gate_label = "EXECUTE (CAUTION GEAR)"
                r_tier = caut_r_pct

        dollar_stake = round(bankroll * (r_tier / 100.0), 2)
        max_slots = int(max_heat_pct // r_tier) if r_tier > 0 else 0

        st.markdown("---")
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Model Fair Line", f"{fair_proj}", f"L5 Med: {l5_med:.1f} | ATR: ±{p_atr:.1f}")
        k2.metric("Model vs No-Vig Prob", f"{model_prob*100:.1f}% vs {book_novig_prob*100:.1f}%", f"Edge: {edge_pct:+.2f}%")
        k3.metric("CQS Score", f"{cqs_score} / 100", vol_regime)
        k4.metric("Gate Status", gate_label, f"L3 Snap: {avg_snap:.1f}%")
        k5.metric("R-Unit Stake", f"${dollar_stake:,.2f} ({r_tier}%)", f"Max Heat Slots: {max_slots} @ {max_heat_pct}% Cap")

# ==============================================================================
# TAB 3: PLAYER CLUSTER & ATR MATRIX
# ==============================================================================
with tab3:
    def render_upgraded_section(title, pos_code_str, stat_dict, target_col, sort_col, log_cols):
        st.subheader(title)
        if "position" not in stats_df.columns:
            st.info("Position column unavailable.")
            return
        sub_df = stats_df[stats_df["position"].astype(str).str.upper() == pos_code_str].copy()
        if sub_df.empty:
            st.info("No data available.")
            return

        cluster_df = build_position_cluster_table(sub_df, stat_dict, target_col, sort_col)
        if cluster_df.empty:
            st.info("Insufficient columns to build cluster matrix.")
            return

        disp = cluster_df.copy()
        disp.columns = [c.replace("_", " ").upper() for c in disp.columns]
        st.dataframe(disp, hide_index=True, height=340, use_container_width=True)

        p_list = cluster_df["PLAYER"].tolist()
        sel_p = st.selectbox(f"Inspect Last 5 Game Logs ({title})", ["-- Select Player --"] + p_list, key=f"log_{pos_code_str}")
        if sel_p != "-- Select Player --":
            logs = sub_df[sub_df["player_display_name"] == sel_p]
            if "week" in logs.columns:
                logs = logs.sort_values(by="week", ascending=False)
            logs = logs.head(5)
            valid_cols = [c for c in log_cols if c in logs.columns]
            l_disp = logs[valid_cols].copy()
            for sc in ["target_share", "air_yards_share"]:
                if sc in l_disp.columns:
                    l_disp[sc] = (l_disp[sc] * 100.0).round(1)
            for ec in ["passing_epa", "rushing_epa", "receiving_epa", "wopr", "dakota"]:
                if ec in l_disp.columns:
                    l_disp[ec] = l_disp[ec].round(2)
            l_disp.columns = [c.replace("_", " ").upper() for c in l_disp.columns]
            st.markdown(f"**Last 5 Games: {sel_p}**")
            st.dataframe(l_disp, hide_index=True, use_container_width=True)

    col_left, col_right = st.columns(2, gap="medium")

    with col_left:
        qb_agg = {
            "completions": "sum", "attempts": "sum", "passing_yards": "sum",
            "passing_tds": "sum", "interceptions": "sum", "passing_epa": "sum", "dakota": "mean"
        }
        qb_log_cols = ["week", "recent_team", "opponent_team", "SNAP_PCT", "completions", "attempts", "passing_yards", "passing_tds", "interceptions", "passing_epa", "dakota"]
        render_upgraded_section("QUARTERBACK (2026)", "QB", qb_agg, "passing_yards", "passing_yards", qb_log_cols)

        st.markdown("---")

        rb_agg = {
            "carries": "sum", "rushing_yards": "sum", "rushing_tds": "sum",
            "rushing_epa": "sum", "targets": "sum", "receptions": "sum", "receiving_yards": "sum"
        }
        rb_log_cols = ["week", "recent_team", "opponent_team", "SNAP_PCT", "carries", "rushing_yards", "rushing_tds", "rushing_epa", "targets", "receiving_yards"]
        render_upgraded_section("RUNNING BACK (2026)", "RB", rb_agg, "rushing_yards", "rushing_yards", rb_log_cols)

    with col_right:
        wr_agg = {
            "targets": "sum", "receptions": "sum", "receiving_yards": "sum",
            "receiving_tds": "sum", "target_share": "mean", "air_yards_share": "mean", "wopr": "mean", "receiving_epa": "sum"
        }
        wr_log_cols = ["week", "recent_team", "opponent_team", "SNAP_PCT", "targets", "receptions", "receiving_yards", "receiving_tds", "target_share", "wopr", "receiving_epa"]
        render_upgraded_section("WIDE RECEIVER (2026)", "WR", wr_agg, "receiving_yards", "receiving_yards", wr_log_cols)

        st.markdown("---")

        te_agg = {
            "targets": "sum", "receptions": "sum", "receiving_yards": "sum",
            "receiving_tds": "sum", "target_share": "mean", "wopr": "mean", "receiving_epa": "sum"
        }
        te_log_cols = ["week", "recent_team", "opponent_team", "SNAP_PCT", "targets", "receptions", "receiving_yards", "receiving_tds", "target_share", "wopr", "receiving_epa"]
        render_upgraded_section("TIGHT END (2026)", "TE", te_agg, "receiving_yards", "receiving_yards", te_log_cols)

# ==============================================================================
# TAB 4: TEAM DEFENSE & FUNNEL MATRIX (BYE-WEEK CORRECTED)
# ==============================================================================
with tab4:
    st.subheader("Team Defense Per-Game & Neutral-Script Funnel Matrix (2026)")
    st.caption("Ranked by Per-Game Yardage & Neutral-Script EPA/Play Allowed (Bye-Week Distortion Removed).")

    if "opponent_team" in stats_df.columns:
        def_candidates = {
            "passing_yards": "sum",
            "passing_tds": "sum",
            "rushing_yards": "sum",
            "rushing_tds": "sum",
            "week": "nunique"
        }
        valid_def_agg = {k: v for k, v in def_candidates.items() if k in stats_df.columns}
        def_base = stats_df.groupby("opponent_team", as_index=False).agg(valid_def_agg).rename(columns={"opponent_team": "TEAM", "week": "GAMES"})

        if {"passing_yards", "rushing_yards", "GAMES"}.issubset(def_base.columns):
            def_base["PASS_YDS_G"] = (def_base["passing_yards"] / def_base["GAMES"]).round(1)
            def_base["RUSH_YDS_G"] = (def_base["rushing_yards"] / def_base["GAMES"]).round(1)
            def_base["TOTAL_YDS_G"] = (def_base["PASS_YDS_G"] + def_base["RUSH_YDS_G"]).round(1)
            def_base["YDS_RANK"] = def_base["TOTAL_YDS_G"].rank(ascending=True, method="min").astype(int)

            if not def_eff_df.empty:
                def_merged = pd.merge(def_base, def_eff_df, left_on="TEAM", right_on="defteam", how="left")
                def_merged["DEF_PASS_EPA"] = def_merged["DEF_PASS_EPA"].round(3)
                def_merged["DEF_RUSH_EPA"] = def_merged["DEF_RUSH_EPA"].round(3)
                def_merged["DEF_PASS_SUCC"] = (def_merged["DEF_PASS_SUCC"] * 100.0).round(1)
                def_merged["DEF_RUSH_SUCC"] = (def_merged["DEF_RUSH_SUCC"] * 100.0).round(1)

                def classify_funnel(r):
                    p_epa = r.get("DEF_PASS_EPA", 0.0)
                    r_epa = r.get("DEF_RUSH_EPA", 0.0)
                    if pd.isna(p_epa) or pd.isna(r_epa):
                        return "BALANCED"
                    if p_epa > 0.06 and p_epa > (r_epa + 0.08):
                        return "PASS FUNNEL (TARGET WR/QB)"
                    elif r_epa > 0.02 and r_epa > (p_epa + 0.08):
                        return "RUN FUNNEL (TARGET RB)"
                    elif p_epa < -0.05 and r_epa < -0.08:
                        return "ELITE LOCKDOWN (AVOID)"
                    return "BALANCED"

                def_merged["FUNNEL_PROFILE"] = def_merged.apply(classify_funnel, axis=1)
                def_merged = def_merged.sort_values(by="DEF_TOTAL_EPA", ascending=True)

                final_cols = [
                    "TEAM", "GAMES", "TOTAL_YDS_G", "YDS_RANK",
                    "PASS_YDS_G", "DEF_PASS_EPA", "DEF_PASS_SUCC",
                    "RUSH_YDS_G", "DEF_RUSH_EPA", "DEF_RUSH_SUCC", "FUNNEL_PROFILE"
                ]
                def_disp = def_merged[final_cols].copy()
                def_disp.columns = [
                    "TEAM", "G", "TOT YDS/G", "YDS RK",
                    "PASS YDS/G", "PASS EPA/P", "PASS SUCC %",
                    "RUSH YDS/G", "RUSH EPA/P", "RUSH SUCC %", "MATCHUP FUNNEL"
                ]
                st.dataframe(def_disp, hide_index=True, height=520, use_container_width=True)
            else:
                def_base = def_base.sort_values(by="YDS_RANK", ascending=True)
                st.dataframe(def_base, hide_index=True, height=520, use_container_width=True)
        else:
            st.dataframe(def_base, hide_index=True, height=520, use_container_width=True)
    else:
        st.info("Defense opponent column missing.")
