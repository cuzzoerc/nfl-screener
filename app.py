import streamlit as st
import pandas as pd
import nflreadpy as nfl

# Set wide layout for financial terminal style
st.set_page_config(page_title="NFL Performance Cluster Matrix", layout="wide")

st.title("🚀 NFL Performance Cluster Matrix")
st.caption("Live Market Intelligence Terminal — Active 2026 Regular Season Feed.")

# Sidebar terminal control
st.sidebar.header("Terminal Controls")
if st.sidebar.button("🔄 Force Refresh Live Data"):
    st.cache_data.clear()
    st.rerun()

# ==========================================
# STRICT 2026 SEASON LIVE DATA LOADER
# ==========================================
@st.cache_data(ttl=300)
def load_live_2026_data():
    try:
        df_polars = nfl.load_player_stats(seasons=[2026])
        if df_polars is not None and not df_polars.is_empty():
            df = df_polars.to_pandas()
            if 'season' in df.columns:
                df = df[df['season'] == 2026]
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Failed to fetch live 2026 feed: {e}")
        return pd.DataFrame()

raw_data = load_live_2026_data()

if raw_data.empty:
    st.warning("No records found for the 2026 season yet. Stream syncing...")
    st.stop()

# Filter regular season only
if 'season_type' in raw_data.columns:
    filtered_data = raw_data[raw_data['season_type'].astype(str).str.upper() == 'REG'].copy()
else:
    filtered_data = raw_data.copy()

if filtered_data.empty:
    st.warning("No regular season records match the current data feed.")
    st.stop()

# Helper function to render compact terminal table + individual player log dropdown
def render_terminal_section(title, pos_df, group_col, stat_dict, sort_col, log_cols):
    st.subheader(title)
    if pos_df.empty:
        st.info("No data available.")
        return

    existing_agg = {k: v for k, v in stat_dict.items() if k in pos_df.columns}
    if not existing_agg or group_col not in pos_df.columns:
        st.info("Required metric columns unavailable.")
        return

    totals = pos_df.groupby(group_col).agg(existing_agg).reset_index()
    if sort_col in totals.columns:
        totals = totals.sort_values(by=sort_col, ascending=False)

    # 1. Render Clean Financial Terminal Table
    display_df = totals.copy()
    display_df.columns = [c.replace('_', ' ').upper() for c in display_df.columns]
    st.dataframe(display_df, hide_index=True, height=320, use_container_width=True)

    # 2. Compact Dropdown to inspect recent game logs for any player in this position
    player_list = totals[group_col].tolist()
    selected_player = st.selectbox(f"Inspect Recent Games ({title})", options=["-- Select Player --"] + player_list, key=f"select_{title}")

    if selected_player != "-- Select Player --":
        p_logs = pos_df[pos_df[group_col] == selected_player].copy()
        if 'week' in p_logs.columns:
            p_logs = p_logs.sort_values(by='week', ascending=False)
        
        recent_5 = p_logs.head(5)
        valid_log_cols = [c for c in log_cols if c in recent_5.columns]
        log_df = recent_5[valid_log_cols].copy()
        log_df.columns = [c.replace('_', ' ').upper() for c in log_df.columns]
        
        st.markdown(f"**Last 5 Games: {selected_player}**")
        st.dataframe(log_df, hide_index=True, use_container_width=True)


# Layout Matrix (2 Columns)
col1, col2 = st.columns(2, gap="medium")

with col1:
    # 1. QUARTERBACK
    qb_data = filtered_data[filtered_data['position'].astype(str).str.upper() == 'QB'].copy() if 'position' in filtered_data.columns else pd.DataFrame()
    qb_stats = {'completions': 'sum', 'attempts': 'sum', 'passing_yards': 'sum', 'passing_tds': 'sum', 'interceptions': 'sum'}
    qb_logs = ['week', 'recent_team', 'opponent_team', 'completions', 'attempts', 'passing_yards', 'passing_tds', 'interceptions']
    render_terminal_section("QUARTERBACK (2026)", qb_data, 'player_display_name', qb_stats, 'passing_yards', qb_logs)

    st.markdown("---")

    # 2. RUNNING BACK
    rb_data = filtered_data[filtered_data['position'].astype(str).str.upper() == 'RB'].copy() if 'position' in filtered_data.columns else pd.DataFrame()
    rb_stats = {'carries': 'sum', 'rushing_yards': 'sum', 'receptions': 'sum', 'receiving_yards': 'sum', 'rushing_tds': 'sum'}
    rb_logs = ['week', 'recent_team', 'opponent_team', 'carries', 'rushing_yards', 'rushing_tds', 'receptions', 'receiving_yards']
    render_terminal_section("RUNNING BACK (2026)", rb_data, 'player_display_name', rb_stats, 'rushing_yards', rb_logs)

    st.markdown("---")

    # 3. TEAM DEFENSE
    st.subheader("TEAM DEFENSE (2026)")
    opp_col = 'opponent_team' if 'opponent_team' in filtered_data.columns else None
    if opp_col:
        def_agg = {'passing_yards': 'sum', 'passing_tds': 'sum', 'rushing_yards': 'sum', 'rushing_tds': 'sum', 'week': 'nunique'}
        existing_agg = {k: v for k, v in def_agg.items() if k in filtered_data.columns}
        def_df = filtered_data.groupby(opp_col).agg(existing_agg).reset_index()
        if not def_df.empty:
            def_df = def_df.rename(columns={'passing_yards': 'PASS_YDS', 'passing_tds': 'PASS_TDS', 'rushing_yards': 'RUSH_YDS', 'rushing_tds': 'RUSH_TDS', 'week': 'GAMES'})
            def_df['AVG_PASS_YDS'] = (def_df['PASS_YDS'] / def_df['GAMES']).round(1)
            def_df['AVG_RUSH_YDS'] = (def_df['RUSH_YDS'] / def_df['GAMES']).round(1)
            def_df['TOTAL_YDS'] = def_df['PASS_YDS'] + def_df['RUSH_YDS']
            def_df['RANK'] = def_df['TOTAL_YDS'].rank(ascending=True, method='min').astype(int)
            def_macro = def_df.sort_values(by='RANK', ascending=True)[[opp_col, 'AVG_PASS_YDS', 'PASS_TDS', 'AVG_RUSH_YDS', 'RUSH_TDS', 'RANK']]
            def_macro.columns = ['TEAM', 'PASS YDS/G', 'PASS TDS', 'RUSH YDS/G', 'RUSH TDS', 'RANK']
            st.dataframe(def_macro, hide_index=True, height=320, use_container_width=True)
        else:
            st.info("Defense metrics unavailable.")
    else:
        st.info("Defense opponent column missing.")

with col2:
    # 4. WIDE RECEIVER
    wr_data = filtered_data[filtered_data['position'].astype(str).str.upper() == 'WR'].copy() if 'position' in filtered_data.columns else pd.DataFrame()
    wr_stats = {'receptions': 'sum', 'targets': 'sum', 'receiving_yards': 'sum', 'receiving_tds': 'sum'}
    wr_logs = ['week', 'recent_team', 'opponent_team', 'receptions', 'targets', 'receiving_yards', 'receiving_tds']
    render_terminal_section("WIDE RECEIVER (2026)", wr_data, 'player_display_name', wr_stats, 'receiving_yards', wr_logs)

    st.markdown("---")

    # 5. TIGHT END
    te_data = filtered_data[filtered_data['position'].astype(str).str.upper() == 'TE'].copy() if 'position' in filtered_data.columns else pd.DataFrame()
    te_stats = {'receptions': 'sum', 'targets': 'sum', 'receiving_yards': 'sum', 'receiving_tds': 'sum'}
    te_logs = ['week', 'recent_team', 'opponent_team', 'receptions', 'targets', 'receiving_yards', 'receiving_tds']
    render_terminal_section("TIGHT END (2026)", te_data, 'player_display_name', te_stats, 'receiving_yards', te_logs)
