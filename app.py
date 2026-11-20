import re
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
    div[data-testid="stMetricValue"] {
        font-size: 1.45rem !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("NFL Syndicate Execution Terminal")
st.caption("Closed-Loop Quantitative Market Intelligence — 2026 Regular Season Feed")

# ==========================================
# --- STADIUM COORDINATES & ROOF METADATA ---
# ==========================================
NFL_STADIUMS = {
    "ARI": (33.5276, -112.2626, "DOME"),
    "ATL": (33.7554, -84.4008, "DOME"),
    "BAL": (39.2780, -76.6227, "OUTDOORS"),
    "BUF": (42.7738, -78.7870, "OUTDOORS"),
    "CAR": (35.2258, -80.8528, "OUTDOORS"),
    "CHI": (41.8623, -87.6167, "OUTDOORS"),
    "CIN": (39.0955, -84.5161, "OUTDOORS"),
    "CLE": (41.5061, -81.6995, "OUTDOORS"),
    "DAL": (32.7473, -97.0945, "DOME"),
    "DEN": (39.7439, -105.0201, "OUTDOORS"),
    "DET": (42.3400, -83.0456, "DOME"),
    "GB":  (44.5013, -88.0622, "OUTDOORS"),
    "HOU": (29.6847, -95.4107, "DOME"),
    "IND": (39.7601, -86.1639, "DOME"),
    "JAX": (30.3239, -81.6373, "OUTDOORS"),
    "KC":  (39.0489, -94.4839, "OUTDOORS"),
    "LA":  (33.9535, -118.3392, "DOME"),
    "LAR": (33.9535, -118.3392, "DOME"),
    "LAC": (33.9535, -118.3392, "DOME"),
    "LV":  (36.0909, -115.1833, "DOME"),
    "MIA": (25.9580, -80.2389, "OUTDOORS"),
    "MIN": (44.9736, -93.2575, "DOME"),
    "NE":  (42.0909, -71.2643, "OUTDOORS"),
    "NO":  (29.9511, -90.0812, "DOME"),
    "NYG": (40.8128, -74.0742, "OUTDOORS"),
    "NYJ": (40.8128, -74.0742, "OUTDOORS"),
    "PHI": (39.9008, -75.1675, "OUTDOORS"),
    "PIT": (40.4468, -80.0158, "OUTDOORS"),
    "SEA": (47.5952, -122.3316, "OUTDOORS"),
    "SF":  (37.4033, -121.9694, "OUTDOORS"),
    "TB":  (27.9759, -82.5033, "OUTDOORS"),
    "TEN": (36.1665, -86.7713, "OUTDOORS"),
    "WAS": (38.9076, -76.8645, "OUTDOORS"),
}

TEAM_NAME_TO_ABBR = {
    "ARIZONA CARDINALS": "ARI", "ATLANTA FALCONS": "ATL", "BALTIMORE RAVENS": "BAL",
    "BUFFALO BILLS": "BUF", "CAROLINA PANTHERS": "CAR", "CHICAGO BEARS": "CHI",
    "CINCINNATI BENGALS": "CIN", "CLEVELAND BROWNS": "CLE", "DALLAS COWBOYS": "DAL",
    "DENVER BRONCOS": "DEN", "DETROIT LIONS": "DET", "GREEN BAY PACKERS": "GB",
    "HOUSTON TEXANS": "HOU", "INDIANAPOLIS COLTS": "IND", "JACKSONVILLE JAGUARS": "JAX",
    "KANSAS CITY CHIEFS": "KC", "LAS VEGAS RAIDERS": "LV", "LOS ANGELES CHARGERS": "LAC",
    "LOS ANGELES RAMS": "LA", "MIAMI DOLPHINS": "MIA", "MINNESOTA VIKINGS": "MIN",
    "NEW ENGLAND PATRIOTS": "NE", "NEW ORLEANS SAINTS": "NO", "NEW YORK GIANTS": "NYG",
    "NEW YORK JETS": "NYJ", "PHILADELPHIA EAGLES": "PHI", "PITTSBURGH STEELERS": "PIT",
    "SAN FRANCISCO 49ERS": "SF", "SEATTLE SEAHAWKS": "SEA", "TAMPA BAY BUCCANEERS": "TB",
    "TENNESSEE TITANS": "TEN", "WASHINGTON COMMANDERS": "WAS"
}

MARKET_LABELS = {
    "player_pass_yds": "PASS YDS",
    "player_rush_yds": "RUSH YDS",
    "player_reception_yds": "REC YDS"
}

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
st.sidebar.subheader("Live Odds Feed (The Odds API)")
default_odds_key = st.secrets.get("ODDS_API_KEY", "") if hasattr(st, "secrets") else ""
odds_api_key = st.sidebar.text_input("API Key", value=default_odds_key, type="password")

# ==========================================
# --- 2026 DATA LOADERS (SCHEMA-HARDENED) ---
# ==========================================
def normalize_name(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(name).upper())

@st.cache_data(ttl=300)
def load_all_2026_feeds():
    data = {
        "stats": pd.DataFrame(),
        "schedules": pd.DataFrame(),
        "snaps": pd.DataFrame(),
        "team_eff": pd.DataFrame(),
        "def_eff": pd.DataFrame()
    }

    try:
        p_stats = nfl.load_player_stats(seasons=[2026])
        if p_stats is not None and not p_stats.is_empty():
            df = p_stats.to_pandas()
            if "season" in df.columns:
                df = df[df["season"] == 2026]
            if "season_type" in df.columns:
                df = df[df["season_type"].astype(str).str.upper() == "REG"]

            if "recent_team" not in df.columns:
                df["recent_team"] = df["team"] if "team" in df.columns else (df["posteam"] if "posteam" in df.columns else "UNK")
            if "player_display_name" not in df.columns:
                df["player_display_name"] = df["player_name"] if "player_name" in df.columns else (df["player"] if "player" in df.columns else "UNKNOWN")

            df["norm_name"] = df["player_display_name"].apply(normalize_name)
            data["stats"] = df
    except Exception as e:
        st.error(f"Player stats feed error: {e}")

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

    try:
        pbp = nfl.load_pbp(seasons=[2026])
        if pbp is not None and not pbp.is_empty():
            pbp_reg = pbp.filter(
                (pl.col("season_type") == "REG") &
                (pl.col("play_type").is_in(["pass", "run"])) &
                (pl.col("epa").is_not_null())
            )
            pbp_neutral = pbp_reg.filter((pl.col("wp") >= 0.05) & (pl.col("wp") <= 0.95)) if "wp" in pbp_reg.columns else pbp_reg

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

@st.cache_data(ttl=1800)
def fetch_stadium_forecast(home_team: str):
    info = NFL_STADIUMS.get(str(home_team).upper())
    if not info:
        return "OUTDOORS", np.nan, np.nan
    lat, lon, roof = info
    if roof == "DOME":
        return "DOME", 0.0, 70.0
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,wind_speed_10m&temperature_unit=fahrenheit&wind_speed_unit=mph"
        )
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            cur = r.json().get("current", {})
            return "OUTDOORS", float(cur.get("wind_speed_10m", np.nan)), float(cur.get("temperature_2m", np.nan))
    except Exception:
        pass
    return "OUTDOORS", np.nan, np.nan

@st.cache_data(ttl=1800)
def fetch_upcoming_nfl_events(api_key: str):
    """Zero-credit endpoint: discovers active NFL event IDs and matchups."""
    if not api_key:
        return []
    base_url = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/events"
    try:
        resp = requests.get(base_url, params={"apiKey": api_key}, timeout=10)
        if resp.status_code == 200:
            out = []
            for ev in resp.json():
                home_full = str(ev.get("home_team", "")).upper()
                away_full = str(ev.get("away_team", "")).upper()
                home_abbr = TEAM_NAME_TO_ABBR.get(home_full, home_full[:3])
                away_abbr = TEAM_NAME_TO_ABBR.get(away_full, away_full[:3])
                out.append({
                    "id": ev.get("id"),
                    "matchup": f"{away_abbr} @ {home_abbr}",
                    "home": home_abbr,
                    "away": away_abbr,
                    "commence": ev.get("commence_time", "")
                })
            return out
    except Exception:
        pass
    return []

@st.cache_data(ttl=900)
def scan_selected_events_props(api_key: str, selected_events: tuple, selected_markets: tuple):
    """Fetches props strictly for user-selected games & markets to conserve API credits."""
    if not api_key or not selected_events or not selected_markets:
        return pd.DataFrame(), "No events or markets selected."

    base_url = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl"
    markets_param = ",".join(selected_markets)
    prop_rows = []
    remaining_quota = "N/A"
    credits_spent = 0

    try:
        for ev_id, matchup_str, home_abbr, away_abbr in selected_events:
            p_resp = requests.get(
                f"{base_url}/events/{ev_id}/odds",
                params={
                    "apiKey": api_key,
                    "regions": "us",
                    "markets": markets_param,
                    "oddsFormat": "american"
                },
                timeout=10
            )
            if p_resp.status_code != 200:
                continue

            remaining_quota = p_resp.headers.get("x-requests-remaining", remaining_quota)
            last_cost = p_resp.headers.get("x-requests-last")
            if last_cost and str(last_cost).isdigit():
                credits_spent += int(last_cost)

            ev_data = p_resp.json()
            bookmakers = ev_data.get("bookmakers", [])
            if not bookmakers:
                continue

            book = next((b for b in bookmakers if b["key"] in ["draftkings", "fanduel"]), bookmakers[0])
            book_title = book.get("title", "US Book")

            for mkt in book.get("markets", []):
                m_key = mkt.get("key")
                paired = {}
                for out in mkt.get("outcomes", []):
                    player_name = out.get("description", "")
                    side = str(out.get("name", "")).upper()
                    pt = out.get("point")
                    price = out.get("price")
                    if not player_name or pt is None or price is None:
                        continue
                    key = (player_name, float(pt))
                    paired.setdefault(key, {})[side] = int(price)

                for (p_name, line_pt), sides in paired.items():
                    if "OVER" in sides and "UNDER" in sides:
                        prop_rows.append({
                            "MATCHUP": matchup_str,
                            "HOME": home_abbr,
                            "AWAY": away_abbr,
                            "BOOK": book_title,
                            "MARKET": m_key,
                            "PLAYER_RAW": p_name,
                            "NORM_NAME": normalize_name(p_name),
                            "LINE": line_pt,
                            "OVER_ODDS": sides["OVER"],
                            "UNDER_ODDS": sides["UNDER"]
                        })

        return pd.DataFrame(prop_rows), f"OK | Scan Cost: {credits_spent} credits | Remaining: {remaining_quota}"
    except Exception as e:
        return pd.DataFrame(), f"Request exception: {e}"

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
    snaps_clean["join_name"] = snaps_clean["player"].apply(normalize_name)
    snaps_clean["join_team"] = snaps_clean["team"].astype(str).str.upper().str.strip()

    stats_df["join_name"] = stats_df["player_display_name"].apply(normalize_name)
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
    vals = p_sorted[target_col].fillna(0.0).values
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

def evaluate_prop_signal(pos_code: str, p_history: pd.DataFrame, opp_team: str, bet_side: str, book_line: float, side_odds: int, opp_odds: int, weather_gate: str = "SURF / GO", market_key: str = ""):
    # CRITICAL: Map target stat by prop market first so QB rush yards & RB rec yards score against true distributions
    market_to_stat = {
        "player_pass_yds": "passing_yards",
        "player_rush_yds": "rushing_yards",
        "player_reception_yds": "receiving_yards"
    }
    pos_to_stat = {
        "QB": "passing_yards",
        "RB": "rushing_yards",
        "WR": "receiving_yards",
        "TE": "receiving_yards"
    }
    target_stat = market_to_stat.get(market_key, pos_to_stat.get(pos_code, "receiving_yards"))

    s_mean, l5_mean, l5_med, p_atr, vol_regime = compute_player_volatility_profile(p_history, target_stat)
    avg_snap = float(p_history["SNAP_PCT"].head(3).mean()) if "SNAP_PCT" in p_history.columns and p_history["SNAP_PCT"].notna().any() else 75.0

    # Matchup funnel adjustment aligned to the specific stat type (passing vs rushing)
    funnel_adj = 0.0
    if not def_eff_df.empty and opp_team in def_eff_df["defteam"].values:
        opp_row = def_eff_df[def_eff_df["defteam"] == opp_team].iloc[0]
        if target_stat in ["passing_yards", "receiving_yards"]:
            opp_def_epa = float(opp_row["DEF_PASS_EPA"])
            lg_avg_epa = float(def_eff_df["DEF_PASS_EPA"].mean())
        else:
            opp_def_epa = float(opp_row["DEF_RUSH_EPA"])
            lg_avg_epa = float(def_eff_df["DEF_RUSH_EPA"].mean())
        epa_delta = opp_def_epa - lg_avg_epa
        funnel_adj = np.clip(epa_delta * 2.5, -0.35, 0.35) * p_atr

    fair_proj = round((0.60 * l5_mean) + (0.40 * s_mean) + funnel_adj, 1)

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

    if weather_gate == "WIND LOCKOUT" and target_stat in ["passing_yards", "receiving_yards"] and bet_side == "OVER":
        gate_label, r_tier = "LOCKOUT: WIND", 0.0
    elif not liquidity_ok:
        gate_label, r_tier = f"LOCKOUT: SNAP {avg_snap:.0f}%", 0.0
    elif edge_pct < min_edge_pct:
        gate_label, r_tier = f"PASS: EDGE {edge_pct:.1f}%", 0.0
    elif cqs_score < 60.0:
        gate_label, r_tier = f"PASS: CQS {cqs_score}", 0.0
    else:
        if cqs_score >= 80.0 and edge_pct >= 7.5:
            gate_label, r_tier = "EXECUTE: APEX", apex_r_pct
        elif cqs_score >= 65.0 and edge_pct >= 5.0:
            gate_label, r_tier = "EXECUTE: STD", std_r_pct
        else:
            gate_label, r_tier = "EXECUTE: CAUT", caut_r_pct

    return {
        "fair_proj": fair_proj,
        "l5_med": l5_med,
        "p_atr": p_atr,
        "vol_regime": vol_regime,
        "avg_snap": avg_snap,
        "model_prob": model_prob * 100.0,
        "book_novig_prob": book_novig_prob * 100.0,
        "edge_pct": edge_pct,
        "cqs_score": cqs_score,
        "gate_label": gate_label,
        "r_tier": r_tier,
        "dollar_stake": round(bankroll * (r_tier / 100.0), 2)
    }

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
    "2. CQS & AUTOMATED PROP SCANNER",
    "3. PLAYER CLUSTER & ATR MATRIX",
    "4. TEAM DEFENSE & FUNNEL MATRIX"
])

# ==============================================================================
# TAB 1: STAGE 0 SLATE & MACRO TIDE
# ==============================================================================
slate_weather_map = {}

with tab1:
    st.subheader("Stage 0 Macro Environment, Odds & Live Weather Gates")

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
            home = str(g.get("home_team", "")).upper()
            away = str(g.get("away_team", "")).upper()
            spread = g.get("spread_line", np.nan)
            total = g.get("total_line", np.nan)
            raw_roof = g.get("roof")
            wind = g.get("wind", np.nan)
            temp = g.get("temp", np.nan)
            h_rest = g.get("home_rest", 7)
            a_rest = g.get("away_rest", 7)
            is_unplayed = pd.isna(g.get("result")) if "result" in g else True

            if pd.notna(total) and pd.notna(spread):
                home_imp = round((total + spread) / 2.0, 1)
                away_imp = round((total - spread) / 2.0, 1)
            else:
                home_imp, away_imp = np.nan, np.nan

            if pd.isna(raw_roof) or str(raw_roof).upper() in ["NAN", "NONE", ""]:
                roof = NFL_STADIUMS.get(home, (0, 0, "OUTDOORS"))[2]
            else:
                roof = str(raw_roof).upper()

            is_dome = roof in ["DOME", "CLOSED"]
            if is_dome:
                wind_val, temp_val = 0.0, 70.0
            elif is_unplayed and (pd.isna(wind) or pd.isna(temp)):
                _, wind_val, temp_val = fetch_stadium_forecast(home)
            else:
                wind_val = float(wind) if pd.notna(wind) else np.nan
                temp_val = float(temp) if pd.notna(temp) else np.nan

            gate_status = "SURF / GO"
            if not is_dome and pd.notna(wind_val) and wind_val >= max_wind_mph:
                gate_status = "WIND LOCKOUT"
            elif not is_dome and pd.notna(temp_val) and temp_val <= min_temp_f:
                gate_status = "COLD CAUTION"
            elif pd.notna(h_rest) and pd.notna(a_rest) and abs(h_rest - a_rest) >= 4:
                gate_status = "REST ASYMMETRY"

            slate_weather_map[f"{away} @ {home}"] = gate_status

            slate_rows.append({
                "WEEK": selected_week,
                "MATCHUP": f"{away} @ {home}",
                "SPREAD (HOME)": f"{-spread:+.1f}" if pd.notna(spread) else "N/A",
                "TOTAL": total,
                "AWAY IMP": away_imp,
                "HOME IMP": home_imp,
                "ROOF": roof,
                "WIND (MPH)": round(wind_val, 1) if pd.notna(wind_val) else "N/A",
                "TEMP (°F)": round(temp_val, 1) if pd.notna(temp_val) else "N/A",
                "REST (A/H)": f"{int(a_rest)}d / {int(h_rest)}d" if pd.notna(a_rest) and pd.notna(h_rest) else "N/A",
                "STAGE 0 GATE": gate_status
            })

        slate_display = pd.DataFrame(slate_rows)
        st.dataframe(slate_display, hide_index=True, use_container_width=True)

    st.markdown("---")
    st.subheader("Neutral-Script Team Offensive Efficiency & Pace (5%–95% WP)")
    if not team_eff_df.empty:
        eff_disp = team_eff_df.copy()
        eff_disp["OFF_PASS_EPA"] = eff_disp["OFF_PASS_EPA"].round(3)
        eff_disp["OFF_RUSH_EPA"] = eff_disp["OFF_RUSH_EPA"].round(3)
        eff_disp["OFF_SUCCESS_RATE"] = (eff_disp["OFF_SUCCESS_RATE"] * 100.0).round(1)
        eff_disp["PASS_RATE"] = (eff_disp["PASS_RATE"] * 100.0).round(1)
        eff_disp["PROE"] = eff_disp["PROE"].round(1)
        eff_disp = eff_disp.sort_values(by="OFF_PASS_EPA", ascending=False)
        eff_disp.columns = ["TEAM", "NEUTRAL PASS EPA", "NEUTRAL RUSH EPA", "SUCCESS %", "PASS RATE %", "PROE %"]
        st.dataframe(eff_disp, hide_index=True, height=340, use_container_width=True)
    else:
        st.info("Play-by-play neutral efficiency data loading or unavailable.")

# ==============================================================================
# TAB 2: PHASE 2 AUTOMATED PROP SCANNER & MANUAL CALCULATOR
# ==============================================================================
with tab2:
    st.subheader("Phase 2: Credit-Guarded Prop Scanner & Open Heat Tracker")
    st.caption("Select specific matchups & markets to minimize API credit burn (1 credit = 1 game × 1 market).")

    if not odds_api_key:
        st.info("Enter your ODDS_API_KEY in the sidebar (or Streamlit Secrets) to enable surgical live prop scanning.")
    else:
        # 0-Credit Event Discovery
        upcoming_events = fetch_upcoming_nfl_events(odds_api_key)
        event_label_map = {f"{e['matchup']} ({e['commence'][:10]})": e for e in upcoming_events}
        all_labels = list(event_label_map.keys())

        sc1, sc2 = st.columns([2, 1])
        with sc1:
            chosen_game_labels = st.multiselect(
                "1. Select Target Matchups (0-Credit Discovery)",
                options=all_labels,
                default=all_labels[:1] if all_labels else [],
                help="Select 1–3 high-total or Stage 0 SURF/GO games to keep credit cost under 10 credits per scan."
            )
        with sc2:
            chosen_markets = st.multiselect(
                "2. Select Prop Markets",
                options=["player_pass_yds", "player_rush_yds", "player_reception_yds"],
                default=["player_pass_yds", "player_rush_yds", "player_reception_yds"],
                format_func=lambda m: MARKET_LABELS.get(m, m)
            )

        est_cost = len(chosen_game_labels) * len(chosen_markets)
        btn_col, cost_col = st.columns([1, 3])
        with btn_col:
            run_scan = st.button(f"⚡ Scan Selected ({est_cost} Credits)", type="primary", use_container_width=True, disabled=(est_cost == 0))
        with cost_col:
            st.caption(f"Pre-Scan Cost Guard: **{est_cost} credits** ({len(chosen_game_labels)} game(s) × {len(chosen_markets)} market(s) × 1 US region). Parameter tweaks below re-run at 0 credits.")

        if run_scan:
            ev_tuples = tuple(
                (event_label_map[lbl]["id"], event_label_map[lbl]["matchup"], event_label_map[lbl]["home"], event_label_map[lbl]["away"])
                for lbl in chosen_game_labels
            )
            raw_props, status_msg = scan_selected_events_props(odds_api_key, ev_tuples, tuple(chosen_markets))
            st.session_state["live_props_df"] = raw_props
            st.session_state["scan_status"] = status_msg

    if "live_props_df" in st.session_state and not st.session_state["live_props_df"].empty:
        raw_props = st.session_state["live_props_df"]
        st.caption(f"Feed Telemetry: {st.session_state.get('scan_status', '')}")

        mkt_to_pos = {
            "player_pass_yds": ["QB"],
            "player_rush_yds": ["RB", "QB"],
            "player_reception_yds": ["WR", "TE", "RB"]
        }
        evaluated_rows = []
        for _, pr in raw_props.iterrows():
            valid_positions = mkt_to_pos.get(pr["MARKET"], [])
            p_matches = stats_df[
                (stats_df["norm_name"] == pr["NORM_NAME"]) &
                (stats_df["position"].astype(str).str.upper().isin(valid_positions))
            ]
            if p_matches.empty:
                continue

            p_team = str(p_matches["recent_team"].iloc[-1]).upper()
            p_pos = str(p_matches["position"].iloc[-1]).upper()
            opp_team = pr["AWAY"] if p_team == pr["HOME"] else pr["HOME"]
            w_gate = slate_weather_map.get(pr["MATCHUP"], "SURF / GO")

            for side, s_odds, o_odds in [
                ("OVER", pr["OVER_ODDS"], pr["UNDER_ODDS"]),
                ("UNDER", pr["UNDER_ODDS"], pr["OVER_ODDS"])
            ]:
                res = evaluate_prop_signal(
                    p_pos, p_matches, opp_team, side, pr["LINE"], s_odds, o_odds,
                    weather_gate=w_gate, market_key=pr["MARKET"]
                )
                if res["gate_label"].startswith("EXECUTE"):
                    evaluated_rows.append({
                        "MATCHUP": pr["MATCHUP"],
                        "PLAYER": pr["PLAYER_RAW"],
                        "POS": p_pos,
                        "MARKET": MARKET_LABELS.get(pr["MARKET"], pr["MARKET"]),
                        "OPP": opp_team,
                        "SIDE": side,
                        "LINE": pr["LINE"],
                        "ODDS": f"{s_odds:+d}",
                        "FAIR": res["fair_proj"],
                        "ATR": round(res["p_atr"], 1),
                        "EDGE %": round(res["edge_pct"], 2),
                        "CQS": res["cqs_score"],
                        "GATE": res["gate_label"],
                        "R %": res["r_tier"],
                        "STAKE ($)": res["dollar_stake"]
                    })

        if evaluated_rows:
            exec_df = pd.DataFrame(evaluated_rows).sort_values(by=["CQS", "EDGE %"], ascending=False).reset_index(drop=True)

            cum_heat = 0.0
            alloc_status = []
            for _, er in exec_df.iterrows():
                if cum_heat + er["R %"] <= max_heat_pct + 1e-6:
                    cum_heat += er["R %"]
                    alloc_status.append("ACTIVE SLOT")
                else:
                    alloc_status.append("HEAT CAP HOLD")
            exec_df["PORTFOLIO SLOT"] = alloc_status

            game_counts = exec_df[exec_df["PORTFOLIO SLOT"] == "ACTIVE SLOT"]["MATCHUP"].value_counts().to_dict()
            exec_df["CORRELATION"] = exec_df["MATCHUP"].apply(lambda m: f"MULTI-LEG ({game_counts.get(m, 0)}x)" if game_counts.get(m, 0) > 1 else "SINGLE LEG")

            h1, h2, h3 = st.columns(3)
            h1.metric("EXECUTE Signals Found", f"{len(exec_df)}")
            h2.metric("Allocated Open Heat", f"{cum_heat:.2f}% / {max_heat_pct:.2f}%")
            h3.metric("Active Capital Deployed", f"${bankroll * (cum_heat / 100.0):,.2f}")

            st.dataframe(exec_df, hide_index=True, use_container_width=True)
        else:
            st.warning("Props ingested successfully, but 0 setups currently pass all Stage 0, CQS (≥60), and No-Vig Edge gates.")

    st.markdown("---")
    st.subheader("Single-Prop Manual Execution Calculator (0 Credits)")

    c1, c2, c3 = st.columns(3)
    with c1:
        calc_pos = st.selectbox("1. Position / Market", ["QB (Passing Yards)", "RB (Rushing Yards)", "WR (Receiving Yards)", "TE (Receiving Yards)"])
    pos_code = calc_pos.split(" ")[0]

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
        book_line = st.number_input("5. Sportsbook Line", min_value=0.5, max_value=500.0, value=235.5, step=0.5)
    with m3:
        side_odds = st.number_input("6. Target Side Odds", min_value=-500, max_value=500, value=-110, step=5)
    with m4:
        opp_odds = st.number_input("7. Opposing Side Odds", min_value=-500, max_value=500, value=-110, step=5)

    if calc_player and calc_player != "No Players Available":
        p_history = pos_pool[pos_pool["player_display_name"] == calc_player]
        res = evaluate_prop_signal(pos_code, p_history, calc_opp, bet_side, book_line, side_odds, opp_odds)
        max_slots = int(max_heat_pct // res["r_tier"]) if res["r_tier"] > 0 else 0

        st.markdown("---")
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Fair Line", f"{res['fair_proj']}", f"Med: {res['l5_med']:.1f} | ATR: ±{res['p_atr']:.1f}")
        k2.metric("Edge (Model vs Book)", f"{res['edge_pct']:+.2f}%", f"{res['model_prob']:.1f}% vs {res['book_novig_prob']:.1f}%")
        k3.metric("CQS Score", f"{res['cqs_score']} / 100", res["vol_regime"])
        k4.metric("Gate Status", res["gate_label"], f"L3 Snap: {res['avg_snap']:.1f}%")
        k5.metric("R-Unit Stake", f"${res['dollar_stake']:,.2f}", f"{res['r_tier']}% R ({max_slots} slots max)")

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
                    if p_epa > 0.03 and (p_epa - r_epa) > 0.05:
                        return "PASS FUNNEL (TARGET WR/QB)"
                    elif r_epa > 0.01 and (r_epa - p_epa) > 0.05:
                        return "RUN FUNNEL (TARGET RB)"
                    elif p_epa < -0.05 and r_epa < -0.07:
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
