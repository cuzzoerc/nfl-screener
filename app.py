import streamlit as st
import pandas as pd
import nflreadpy as nfl

# Set wide layout for the financial-terminal cluster matrix
st.set_page_config(page_title="NFL Performance Cluster Matrix", layout="wide")

st.title("🚀 NFL Performance Cluster Matrix")
st.caption("Live Market Intelligence Terminal — Active 2026 Regular Season Feed.")

# Sidebar control for cache busting on demand
st.sidebar.header("Terminal Controls")
if st.sidebar.button("🔄 Force Refresh Live Data"):
    st.cache_data.clear()
    st.rerun()

# ==========================================
# STRICT 2026 SEASON LIVE DATA LOADER
# ==========================================
@st.cache_data(ttl=300)  # Short 5-minute TTL to ensure fresh data pulls
def load_live_2026_data():
    try:
        # Programmatically request ONLY the active 2026 season
        df_polars = nfl.load_player_stats(seasons=[2026])
        if df_polars is not None and not df_polars.is_empty():
            df = df_polars.to_pandas()
            # Absolute guardrail: Drop any historical/retired players if present
            if 'season' in df.columns:
                df = df[df['season'] == 2026]
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Failed to fetch live 2026 feed: {e}")
        return pd.DataFrame()

raw_data = load_live_2026_data()

if raw_data.empty:
    st.warning("No records found for the 2026 season yet. The live data stream may still be syncing from upstream source files.")
    st.stop()

# Force strict Regular Season filter for the live terminal
if 'season_type' in raw_data.columns:
    filtered_data = raw_data[raw_data['season_type'].astype(str).str.upper() == 'REG'].copy()
else:
    filtered_data = raw_data.copy()

if filtered_data.empty:
    st.warning("No regular season records match the current 2026 data feed.")
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
    st.subheader("QUARTERBACK (2026)")
    qb_data = filtered_data[filtered_data['position'].astype(str).str.upper() == 'QB'].copy() if 'position' in filtered_data.columns else pd.DataFrame()
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
        st.info("No active 2026 quarterback data available.")

    st.markdown("---")

    # 2. RUNNING BACK BOX
    st.subheader("RUNNING BACK (2026)")
    rb_data = filtered_data[filtered_data['position'].astype(str).str.upper() == 'RB'].copy() if 'position' in filtered_data.columns else pd.DataFrame()
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
        st.info("No active 2026 running back data available.")

    st.markdown("---")

    # 3. TEAM DEFENSE BOX
    st.subheader("TEAM DEFENSE (2026)")
    opp_col = 'opponent_team' if 'opponent_team' in filtered_data.columns else ('opp' if 'opp' in filtered_data.columns else None)
    if opp_col:
        def_agg = {
            'passing_yards': 'sum',
            'passing_tds': 'sum',
            'rushing_yards': 'sum',
            'rushing_tds': 'sum',
            'week': 'nunique'
        }
        def_df = safe_agg(filtered_data, opp_col, def_agg, 'passing_yards')
        if not def_df.empty:
            def_df = def_df.rename(columns={
                opp_col: 'team',
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
                    'team', 'AVG_PASS_YDS', 'pass_tds', 'AVG_RUSH_YDS', 'rush_tds', 'RANK'
                ]]
                def_macro.columns = ['TEAM', 'PASS YDS/G', 'PASS TDS', 'RUSH YDS/G', 'RUSH TDS', 'RANK']
                st.dataframe(def_macro, hide_index=True, height=380, use_container_width=True)
            else:
                st.info("Defense calculation columns missing.")
        else:
            st.info("Defense metrics unavailable.")
    else:
        st.info("Team defense opponent column unavailable.")


# ==========================================
# COLUMN 2: WIDE RECEIVERS, TIGHT ENDS
# ==========================================
with col2:
    # 4. WIDE RECEIVER BOX
    st.subheader("WIDE RECEIVER (2026)")
    wr_data = filtered_data[filtered_data['position'].astype(str).str.upper() == 'WR'].copy() if 'position' in filtered_data.columns else pd.DataFrame()
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
        st.info("No active 2026 wide receiver data available.")

    st.markdown("---")

    # 5. TIGHT END BOX
    st.subheader("TIGHT END (2026)")
    te_data = filtered_data[filtered_data['position'].astype(str).str.upper() == 'TE'].copy() if 'position' in filtered_data.columns else pd.DataFrame()
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
        st.info("No active 2026 tight end data available.")
