import streamlit as st
import pandas as pd

# Set wide layout to support the multi-box dashboard matrix
st.set_page_config(page_title="NFL Cluster Matrix Screener", layout="wide")

st.title("🚀 NFL Performance Cluster Matrix")
st.caption("Multi-position market intelligence dashboard — Real-time analytics terminal.")

# ==========================================
# SIDEBAR FILTERS (YEAR & SEASON TYPES)
# ==========================================
st.sidebar.header("📊 Screener Parameters")

# 1. YEAR FILTER (Now fully supporting 2026 live data)
selected_year = st.sidebar.selectbox(
    "Select Season Year", 
    [2026, 2025, 2024, 2023, 2022], 
    index=0
)

st.sidebar.markdown("---")
st.sidebar.subheader("Game Type Filters")

# 2, 3, 4. TOGGLES FOR PRE-SEASON, REGULAR SEASON, PLAYOFFS
use_pre = st.sidebar.checkbox("Pre-Season", value=False)
use_reg = st.sidebar.checkbox("Regular Season", value=True)
use_post = st.sidebar.checkbox("Playoffs", value=False)

# Direct data loader from unified nflverse stats_player release endpoint
@st.cache_data
def load_nfl_data(year):
    url = "https://github.com/nflverse/nflverse-data/releases/download/stats_player/player_stats.csv.gz"
    try:
        df = pd.read_csv(url, compression='gzip')
        if 'season' in df.columns:
            df = df[df['season'] == year]
        return df
    except Exception as e:
        return pd.DataFrame()

raw_data = load_nfl_data(selected_year)

if raw_data.empty:
    st.warning(f"No weekly data found for the {selected_year} season. Please check your connection or select a different year.")
    st.stop()

# Filter dataset by selected season types ('REG', 'POST', 'PRE')
allowed_types = []
if use_pre:
    allowed_types.append('PRE')
if use_reg:
    allowed_types.append('REG')
if use_post:
    allowed_types.append('POST')

if 'season_type' in raw_data.columns and allowed_types:
    filtered_data = raw_data[raw_data['season_type'].isin(allowed_types)].copy()
else:
    filtered_data = raw_data.copy()

if filtered_data.empty:
    st.warning("No records match your selected season type filters. Please enable at least one game type in the sidebar.")
    st.stop()

# Create a clean 2-column dashboard grid
col1, col2 = st.columns(2, gap="medium")

# ==========================================
# COLUMN 1: QUARTERBACKS, RUNNING BACKS, DEFENSE
# ==========================================
with col1:
    # 1. QUARTERBACK BOX
    st.subheader("QUARTERBACK")
    qb_data = filtered_data[filtered_data['position'] == 'QB'].copy()
    if not qb_data.empty:
        qb_macro = qb_data.groupby(['player_display_name']).agg(
            completions=('completions', 'sum'),
            attempts=('attempts', 'sum'),
            passing_yards=('passing_yards', 'sum'),
            passing_tds=('passing_tds', 'sum'),
            interceptions=('interceptions', 'sum')
        ).reset_index().sort_values(by='passing_yards', ascending=False)
        
        qb_macro.columns = ['QB NAME', 'COMPLETIONS', 'ATTEMPTS', 'YARDS', 'TDs', 'INT']
        st.dataframe(qb_macro, hide_index=True, height=380, use_container_width=True)
    else:
        st.info("No quarterback data available for current filters.")

    st.markdown("---")

    # 2. RUNNING BACK BOX
    st.subheader("RUNNING BACK")
    rb_data = filtered_data[filtered_data['position'] == 'RB'].copy()
    if not rb_data.empty:
        td_col = 'touchdowns' if 'touchdowns' in rb_data.columns else ('rushing_tds' if 'rushing_tds' in rb_data.columns else 'receiving_tds')
        
        rb_macro = rb_data.groupby(['player_display_name']).agg(
            carries=('carries', 'sum'),
            rushing_yards=('rushing_yards', 'sum'),
            receptions=('receptions', 'sum'),
            receiving_yards=('receiving_yards', 'sum'),
            tds=(td_col, 'sum')
        ).reset_index().sort_values(by='rushing_yards', ascending=False)
        
        rb_macro.columns = ['RB NAME', 'CARRYS', 'CARRY YARDS', 'RECEPTIONS', 'RECEPTION YARDS', 'TDs']
        st.dataframe(rb_macro, hide_index=True, height=380, use_container_width=True)
    else:
        st.info("No running back data available for current filters.")

    st.markdown("---")

    # 3. TEAM DEFENSE BOX
    st.subheader("TEAM DEFENSE")
    if 'opponent_team' in filtered_data.columns:
        def_df = filtered_data.groupby('opponent_team').agg(
            pass_yds=('passing_yards', 'sum'),
            pass_tds=('passing_tds', 'sum'),
            rush_yds=('rushing_yards', 'sum'),
            rush_tds=('rushing_tds', 'sum'),
            games=('week', 'nunique')
        ).reset_index()
        
        def_df['AVG_PASS_YDS'] = (def_df['pass_yds'] / def_df['games']).round(1)
        def_df['AVG_RUSH_YDS'] = (def_df['rush_yds'] / def_df['games']).round(1)
        def_df['TOTAL_YDS'] = def_df['pass_yds'] + def_df['rush_yds']
        def_df['DEFENSE_RANK'] = def_df['TOTAL_YDS'].rank(ascending=True, method='min').astype(int)
        
        def_macro = def_df.sort_values(by='DEFENSE_RANK', ascending=True)[[
            'opponent_team', 'AVG_PASS_YDS', 'pass_tds', 'AVG_RUSH_YDS', 'rush_tds', 'DEFENSE_RANK'
        ]]
        def_macro.columns = ['TEAM', 'PASS YDS/G', 'PASS TDS', 'RUSH YDS/G', 'RUSH TDS', 'RANK']
        st.dataframe(def_macro, hide_index=True, height=380, use_container_width=True)
    else:
        st.info("Team defense metrics unavailable.")


# ==========================================
# COLUMN 2: WIDE RECEIVERS, TIGHT ENDS
# ==========================================
with col2:
    # 4. WIDE RECEIVER BOX
    st.subheader("WIDE RECEIVER")
    wr_data = filtered_data[filtered_data['position'] == 'WR'].copy()
    if not wr_data.empty:
        wr_macro = wr_data.groupby(['player_display_name']).agg(
            receptions=('receptions', 'sum'),
            targets=('targets', 'sum'),
            receiving_yards=('receiving_yards', 'sum'),
            receiving_tds=('receiving_tds', 'sum')
        ).reset_index().sort_values(by='targets', ascending=False)
        
        wr_macro.columns = ['WR NAME', 'RECEPTIONS', 'TARGETS', 'YARDS', 'TDs']
        st.dataframe(wr_macro, hide_index=True, height=380, use_container_width=True)
    else:
        st.info("No wide receiver data available for current filters.")

    st.markdown("---")

    # 5. TIGHT END BOX
    st.subheader("TIGHT END")
    te_data = filtered_data[filtered_data['position'] == 'TE'].copy()
    if not te_data.empty:
        te_macro = te_data.groupby(['player_display_name']).agg(
            receptions=('receptions', 'sum'),
            targets=('targets', 'sum'),
            receiving_yards=('receiving_yards', 'sum'),
            receiving_tds=('receiving_tds', 'sum')
        ).reset_index().sort_values(by='targets', ascending=False)
        
        te_macro.columns = ['TE NAME', 'RECEPTIONS', 'TARGETS', 'YARDS', 'TDs']
        st.dataframe(te_macro, hide_index=True, height=380, use_container_width=True)
    else:
        st.info("No tight end data available for current filters.")
