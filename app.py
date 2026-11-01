import streamlit as st
import nfl_data_py as nfl
import pandas as pd

# Set wide layout to support the multi-box dashboard matrix
st.set_page_config(page_title="NFL Cluster Matrix Screener", layout="wide")

st.title("🚀 NFL Performance Cluster Matrix")
st.caption("Multi-position market intelligence dashboard — Updated daily at 00:00 EST.")

# Cached data loader for active/recent season
@st.cache_data
def load_nfl_data():
    df = nfl.import_weekly_data([2024])
    return df

try:
    raw_data = load_nfl_data()
except Exception as e:
    st.error(f"Error loading NFL data: {e}")
    st.stop()

# Create a clean 2-column dashboard grid
col1, col2 = st.columns(2, gap="medium")

# ==========================================
# COLUMN 1: QUARTERBACKS, RUNNING BACKS, KICKERS
# ==========================================
with col1:
    # 1. QUARTERBACK BOX
    st.subheader("QUARTERBACK")
    qb_data = raw_data[raw_data['position'] == 'QB'].copy()
    qb_macro = qb_data.groupby(['player_display_name']).agg(
        completions=('completions', 'sum'),
        attempts=('attempts', 'sum'),
        passing_yards=('passing_yards', 'sum'),
        passing_tds=('passing_tds', 'sum'),
        interceptions=('interceptions', 'sum')
    ).reset_index().sort_values(by='passing_yards', ascending=False)
    
    qb_macro.columns = ['QB NAME', 'COMPLETIONS', 'ATTEMPTS', 'YARDS', 'TDs', 'INT']
    st.dataframe(qb_macro, hide_index=True, height=380, use_container_width=True)

    st.markdown("---")

    # 2. RUNNING BACK BOX
    st.subheader("RUNNING BACK")
    rb_data = raw_data[raw_data['position'] == 'RB'].copy()
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

    st.markdown("---")

    # 3. PLACE KICKER BOX (Using corrected nfl_data_py schema keys: fgm, fga, pat_made)
    st.subheader("PLACE KICKER")
    pk_data = raw_data[raw_data['position'] == 'K'].copy()
    
    fg_made_col = 'fgm' if 'fgm' in pk_data.columns else ('fg_made' if 'fg_made' in pk_data.columns else None)
    fg_att_col = 'fga' if 'fga' in pk_data.columns else ('fg_att' if 'fg_att' in pk_data.columns else None)
    pat_made_col = 'pat_made' if 'pat_made' in pk_data.columns else ('patm' if 'patm' in pk_data.columns else None)

    if fg_made_col and fg_att_col and pat_made_col:
        pk_grouped = pk_data.groupby(['player_display_name']).agg(
            fgm=(fg_made_col, 'sum'),
            fga=(fg_att_col, 'sum'),
            pat_made=(pat_made_col, 'sum')
        ).reset_index()
        
        pk_grouped['FG_COMP_RATE'] = (pk_grouped['fgm'] / pk_grouped['fga'].replace(0, 1) * 100).round(1).astype(str) + '%'
        pk_grouped['TOTAL_POINTS'] = (pk_grouped['fgm'] * 3) + pk_grouped['pat_made']
        
        pk_macro = pk_grouped.sort_values(by='TOTAL_POINTS', ascending=False)[['player_display_name', 'FG_COMP_RATE', 'pat_made', 'TOTAL_POINTS']]
        pk_macro.columns = ['PK NAME', 'FIELD GOAL COMPLETION RATE', 'EXTRA POINTS MADE', 'TOTAL POINTS']
        st.dataframe(pk_macro, hide_index=True, height=380, use_container_width=True)
    else:
        st.info("Kicker stats mapping initializing...")


# ==========================================
# COLUMN 2: WIDE RECEIVERS, TIGHT ENDS
# ==========================================
with col2:
    # 4. WIDE RECEIVER BOX
    st.subheader("WIDE RECEIVER")
    wr_data = raw_data[raw_data['position'] == 'WR'].copy()
    wr_macro = wr_data.groupby(['player_display_name']).agg(
        receptions=('receptions', 'sum'),
        targets=('targets', 'sum'),
        receiving_yards=('receiving_yards', 'sum'),
        receiving_tds=('receiving_tds', 'sum')
    ).reset_index().sort_values(by='targets', ascending=False)
    
    wr_macro.columns = ['WR NAME', 'RECEPTIONS', 'TARGETS', 'YARDS', 'TDs']
    st.dataframe(wr_macro, hide_index=True, height=520, use_container_width=True)

    st.markdown("---")

    # 5. TIGHT END BOX
    st.subheader("TIGHT END")
    te_data = raw_data[raw_data['position'] == 'TE'].copy()
    te_macro = te_data.groupby(['player_display_name']).agg(
        receptions=('receptions', 'sum'),
        targets=('targets', 'sum'),
        receiving_yards=('receiving_yards', 'sum'),
        receiving_tds=('receiving_tds', 'sum')
    ).reset_index().sort_values(by='targets', ascending=False)
    
    te_macro.columns = ['TE NAME', 'RECEPTIONS', 'TARGETS', 'YARDS', 'TDs']
    st.dataframe(te_macro, hide_index=True, height=520, use_container_width=True)
