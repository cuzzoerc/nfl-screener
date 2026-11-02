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

# Helper function to render a position card list with collapsable game logs
def render_position_cards(pos_df, group_col, stat_cols, sort_col, game_log_cols):
    if pos_df.empty:
        st.info("No position data available.")
        return

    # Aggregate season totals
    existing_agg = {k: 'sum' for k in stat_cols if k in pos_df.columns}
    if not existing_agg or group_col not in pos_df.columns:
        st.info("Required metric columns unavailable.")
        return

    totals = pos_df.groupby(group_col).agg(existing_agg).reset_index()
    
    # Sort strictly by target metric descending
    if sort_col in totals.columns:
        totals = totals.sort_values(by=sort_col, ascending=False)

    # Render top players as terminal cards with drop-down expanders
    for _, row in totals.head(15).iterrows():
        player_name = row[group_col]
        
        # Display main metric summary line
        metrics_summary = " | ".join([f"{col.replace('_', ' ').upper()}: {row[col]}" for col in stat_cols if col in row])
        
        with st.expander(f"👤 {player_name} — ({metrics_summary})"):
            # Filter player's game-by-game logs
            p_logs = pos_df[pos_df[group_col] == player_name].copy()
            if 'week' in p_logs.columns:
                p_logs = p_logs.sort_values(by='week', ascending=False)
            
            # Extract most recent 5 games
            recent_5 = p_logs.head(5)
            
            # Select relevant columns for display
            log_cols_to_show = [c for c in game_log_cols if c in recent_5.columns]
            if not log_cols_to_show:
                log_cols_to_show = [c for c in ['week', 'recent_team', 'opponent_team'] + stat_cols if c in recent_5.columns]
                
            recent_df = recent_5[log_cols_to_show].copy()
            recent_df.columns = [c.replace('_', ' ').upper() for c in recent_df.columns]
            
            st.dataframe(recent_df, hide_index=True, use_container_width=True)


# Layout Matrix (2 Columns)
col1, col2 = st.columns(2, gap="medium")

with col1:
    st.subheader("QUARTERBACK")
    qb_data = filtered_data[filtered_data['position'].astype(str).str.upper() == 'QB'].copy() if 'position' in filtered_data.columns else pd.DataFrame()
    qb_stats = ['passing_yards', 'passing_tds', 'completions', 'attempts', 'interceptions']
    qb_log_cols = ['week', 'recent_team', 'opponent_team', 'completions', 'attempts', 'passing_yards', 'passing_tds', 'interceptions']
    render_position_cards(qb_data, 'player_display_name', qb_stats, 'passing_yards', qb_log_cols)

    st.markdown("---")

    st.subheader("RUNNING BACK")
    rb_data = filtered_data[filtered_data['position'].astype(str).str.upper() == 'RB'].copy() if 'position' in filtered_data.columns else pd.DataFrame()
    rb_stats = ['rushing_yards', 'carries', 'rushing_tds', 'receptions', 'receiving_yards']
    rb_log_cols = ['week', 'recent_team', 'opponent_team', 'carries', 'rushing_yards', 'rushing_tds', 'receptions', 'receiving_yards']
    render_position_cards(rb_data, 'player_display_name', rb_stats, 'rushing_yards', rb_log_cols)

    st.markdown("---")

    st.subheader("TEAM DEFENSE")
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
            st.dataframe(def_macro, hide_index=True, height=380, use_container_width=True)

with col2:
    st.subheader("WIDE RECEIVER")
    wr_data = filtered_data[filtered_data['position'].astype(str).str.upper() == 'WR'].copy() if 'position' in filtered_data.columns else pd.DataFrame()
    wr_stats = ['receiving_yards', 'receptions', 'targets', 'receiving_tds']
    wr_log_cols = ['week', 'recent_team', 'opponent_team', 'receptions', 'targets', 'receiving_yards', 'receiving_tds']
    render_position_cards(wr_data, 'player_display_name', wr_stats, 'receiving_yards', wr_log_cols)

    st.markdown("---")

    st.subheader("TIGHT END")
    te_data = filtered_data[filtered_data['position'].astype(str).str.upper() == 'TE'].copy() if 'position' in filtered_data.columns else pd.DataFrame()
    te_stats = ['receiving_yards', 'receptions', 'targets', 'receiving_tds']
    te_log_cols = ['week', 'recent_team', 'opponent_team', 'receptions', 'targets', 'receiving_yards', 'receiving_tds']
    render_position_cards(te_data, 'player_display_name', te_stats, 'receiving_yards', te_log_cols)
