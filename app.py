import streamlit as st
import pandas as pd
import nflreadpy as nfl

# Set wide layout to support the multi-box dashboard matrix
st.set_page_config(page_title="NFL Cluster Matrix Screener", layout="wide")

st.title("🚀 NFL Performance Cluster Matrix")
st.caption("Multi-position market intelligence dashboard — Live Terminal.")

# ==========================================
# SIDEBAR FILTERS (YEAR & SEASON TYPES)
# ==========================================
st.sidebar.header("📊 Screener Parameters")

selected_year = st.sidebar.selectbox(
    "Select Season Year", 
    [2026, 2025, 2024, 2023, 2022], 
    index=0
)

st.sidebar.markdown("---")
st.sidebar.subheader("Game Type Filters")

use_pre = st.sidebar.checkbox("Pre-Season", value=False)
use_reg = st.sidebar.checkbox("Regular Season", value=True)
use_post = st.sidebar.checkbox("Playoffs", value=False)

# Safe data loader using nflreadpy
@st.cache_data
def load_nfl_data(year):
    try:
        df_polars = nfl.load_player_stats(seasons=[year])
        if df_polars is not None and not df_polars.is_empty():
            return df_polars.to_pandas()
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Failed to fetch live feed: {e}")
        return pd.DataFrame()

raw_data = load_nfl_data(selected_year)

if raw_data.empty:
    st.warning(f"No records found for the {selected_year} season yet.")
    st.stop()

# Robust case-insensitive game type filtering
allowed_types = []
if use_pre: allowed_types.append('PRE')
if use_reg: allowed_types.append('REG')
if use_post: allowed_types.append('POST')

if 'season_type' in raw_data.columns and allowed_types:
    filtered_data = raw_data[raw_data['season_type'].astype(str).str.upper().isin(allowed_types)].copy()
else:
    filtered_data = raw_data.copy()

if filtered_data.empty:
    st.warning("No records match your selected game type filters.")
    st.stop()

# Helper function to safely aggregate only columns that exist
def safe_agg(df, group_col, agg_dict, sort_col):
    existing_dict = {k: v for k, v in agg_dict.items() if k in df.columns}
    if not existing_dict or group_col not in df.columns:
        return pd.DataFrame()
    
    result = df.groupby(group_col).agg(existing_dict).reset_index()
    if sort_col in result.columns:
        result = result.sort_values(by=sort_col, ascending=False)
    return result

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
        qb_agg = {
            'completions': 'sum',
            'attempts': 'sum',
            'passing_yards': 'sum',
            'passing_tds': 'sum',
            'interceptions': 'sum'
        }
        qb_macro = safe_agg(qb_data, 'player_display_name', qb_agg, 'passing_yards')
        if not qb_macro.empty:
            qb_macro.columns = [c.upper() for c in qb_macro.columns]
            st.dataframe(qb_macro, hide_index=True, height=380, use_container_width=True)
        else:
            st.info("Required QB metric columns unavailable.")
    else:
        st.info("No quarterback data available.")

    st.markdown("---")

    # 2. RUNNING BACK BOX
    st.subheader("RUNNING BACK")
    rb_data = filtered_data[filtered_data['position'] == 'RB'].copy()
    if not rb_data.empty:
        td_key = 'touchdowns' if 'touchdowns' in rb_data.columns else ('rushing_tds' if 'rushing_tds' in rb_data.columns else 'receiving_tds')
        rb_agg = {
            'carries': 'sum',
            'rushing_yards': 'sum',
            'receptions': 'sum',
            'receiving_yards': 'sum',
            td_key: 'sum'
        }
        rb_macro = safe_agg(rb_data, 'player_display_name', rb_agg, 'rushing_yards')
        if not rb_macro.empty:
            rb_macro.columns = [c.upper() for c in rb_macro.columns]
            st.dataframe(rb_macro, hide_index=True, height=380, use_container_width=True)
        else:
            st.info("Required RB metric columns unavailable.")
    else:
        st.info("No running back data available.")

    st.markdown("---")

    # 3. TEAM DEFENSE BOX
    st.subheader("TEAM DEFENSE")
    if 'opponent_team' in filtered_data.columns:
        def_agg = {
            'passing_yards': 'sum',
            'passing_tds': 'sum',
            'rushing_yards': 'sum',
            'rushing_tds': 'sum',
            'week': 'nunique'
        }
        def_df = safe_agg(filtered_data, 'opponent_team', def_agg, 'passing_yards')
        if not def_df.empty:
            def_df = def_df.rename(columns={
                'passing_yards': 'pass_yds',
                'passing_tds': 'pass_tds',
                'rushing_yards': 'rush_yds',
                'rushing_tds': 'rush_tds',
                'week': 'games'
            })
            if {'pass_yds', 'games'}.issubset(def_df.columns):
                def_df['AVG_PASS_YDS'] = (def_df['pass_yds'] / def_df['games']).round(1)
                def_df['AVG_RUSH_YDS'] = (def_df['rush_yds'] / def_df['games']).round(1)
                def_df['TOTAL_YDS'] = def_df['pass_yds'] + def_df['rush_yds']
                def_df['RANK'] = def_df['TOTAL_YDS'].rank(ascending=True, method='min').astype(int)
                
                def_macro = def_df.sort_values(by='RANK', ascending=True)[[
                    'opponent_team', 'AVG_PASS_YDS', 'pass_tds', 'AVG_RUSH_YDS', 'rush_tds', 'RANK'
                ]]
                def_macro.columns = ['TEAM', 'PASS YDS/G', 'PASS TDS', 'RUSH YDS/G', 'RUSH TDS', 'RANK']
                st.dataframe(def_macro, hide_index=True, height=380, use_container_width=True)
            else:
                st.info("Defense calculation columns missing.")
        else:
            st.info("Defense metrics unavailable.")
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
        wr_agg = {
            'receptions': 'sum',
            'targets': 'sum',
            'receiving_yards': 'sum',
            'receiving_tds': 'sum'
        }
        wr_macro = safe_agg(wr_data, 'player_display_name', wr_agg, 'targets')
        if not wr_macro.empty:
            wr_macro.columns = [c.upper() for c in wr_macro.columns]
            st.dataframe(wr_macro, hide_index=True, height=380, use_container_width=True)
        else:
            st.info("Required WR metric columns unavailable.")
    else:
        st.info("No wide receiver data available.")

    st.markdown("---")

    # 5. TIGHT END BOX
    st.subheader("TIGHT END")
    te_data = filtered_data[filtered_data['position'] == 'TE'].copy()
    if not te_data.empty:
        te_agg = {
            'receptions': 'sum',
            'targets': 'sum',
            'receiving_yards': 'sum',
            'receiving_tds': 'sum'
        }
        te_macro = safe_agg(te_data, 'player_display_name', te_agg, 'targets')
        if not te_macro.empty:
            te_macro.columns = [c.upper() for c in te_macro.columns]
            st.dataframe(te_macro, hide_index=True, height=380, use_container_width=True)
        else:
            st.info("Required TE metric columns unavailable.")
    else:
        st.info("No tight end data available.")
