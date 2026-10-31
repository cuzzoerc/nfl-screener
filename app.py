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

# Create a clean 2-column dashboard grid (matching your sector cluster layout)
col1, col2 = st.columns(2, gap="medium")

# ==========================================
# COLUMN 1: QUARTERBACKS, RUNNING BACKS, KICKERS
# ==========================================
with col1:
    # 1. QUARTERBACK BOX
    st.subheader("QUARTERBACK")
    qb_data = raw_data[raw_data['position'] == 'QB'].copy()
    qb_macro = qb_data.groupby(['player_display_name']).agg(
        COMPLETIONS=('completions', 'sum'),
        ATTEMPTS=('attempts', 'sum'),
        YARDS=('passing_yards', 'sum'),
        TDS=('passing_tds', 'sum'),
        INT=('interceptions', 'sum')
    ).reset_index().sort_values(by='YARDS', ascending=False)
    
    qb_macro.columns = ['QB NAME', 'COMPLETIONS', 'ATTEMPTS', 'YARDS', 'TDs', 'INT']
    st.dataframe(qb_macro, hide_index=True, height=380, use_container_width=True)

    st.markdown("---")

    # 2. RUNNING BACK BOX
    st.subheader("RUNNING BACK")
    rb_data = raw_data[raw_data['position'] == 'RB'].copy()
    td_col = 'touchdowns' if 'touchdowns' in rb_data.columns else 'rushing_tds'
    
    rb_macro = rb_data.groupby(['player_display_name']).agg(
        CARRYS=('carries', 'sum'),
        CARRY_YARDS=('rushing_yards', 'sum'),
        RECEPTIONS=('receptions', 'sum'),
        RECEPTION_YARDS=('receiving_yards', 'sum'),
        TDS=(td_col, 'sum')
    ).reset_index().sort_values(by='CARRY YARDS', ascending=False) if 'rushing_yards' in rb_data.columns else rb_data.groupby(['player_display_name']).agg(
        CARRYS=('carries', 'sum'),
        CARRY_YARDS=('rushing_yards', 'sum'),
        RECEPTIONS=('receptions', 'sum'),
        RECEPTION_YARDS=('receiving_yards', 'sum'),
        TDS=(td_col, 'sum')
    ).reset_index().sort_values(by='rushing_yards', ascending=False)
    
    rb_macro.columns = ['RB NAME', 'CARRYS', 'CARRY YARDS', 'RECEPTIONS', 'RECEPTION YARDS', 'TDs']
    st.dataframe(rb_macro, hide_index=True, height=380, use_container_width=True)

    st.markdown("---")

    # 3. PLACE KICKER BOX
    st.subheader("PLACE KICKER")
    pk_data = raw_data[raw_data['position'] == 'K'].copy()
    pk_grouped = pk_data.groupby(['player_display_name']).agg(
        FG_MADE=('fg_made', 'sum'),
        FG_ATT=('fg_att', 'sum'),
        PAT_MADE=('pat_made', 'sum')
    ).reset_index()
    
    pk_grouped['FG_COMP_RATE'] = (pk_grouped['FG_MADE'] / pk_grouped['FG_ATT'].replace(0, 1) * 100).round(1).astype(str) + '%'
    pk_grouped['TOTAL_POINTS'] = (pk_grouped['FG_MADE'] * 3) + pk_grouped['PAT_MADE']
    pk_macro = pk_grouped.sort_values(by='TOTAL_POINTS', ascending=False)[['player_display_name', 'FG_COMP_RATE', 'PAT_MADE', 'TOTAL_POINTS']]
    
    pk_macro.columns = ['PK NAME', 'FIELD GOAL COMPLETION RATE', 'EXTRA POINTS MADE', 'TOTAL POINTS']
    st.dataframe(pk_macro, hide_index=True, height=380, use_container_width=True)


# ==========================================
# COLUMN 2: WIDE RECEIVERS, TIGHT ENDS
# ==========================================
with col2:
    # 4. WIDE RECEIVER BOX
    st.subheader("WIDE RECEIVER")
    wr_data = raw_data[raw_data['position'] == 'WR'].copy()
    wr_macro = wr_data.groupby(['player_display_name']).agg(
        RECEPTIONS=('receptions', 'sum'),
        TARGETS=('targets', 'sum'),
        YARDS=('receiving_yards', 'sum'),
        TDS=('receiving_tds', 'sum')
    ).reset_index().sort_values(by='TARGETS', ascending=False)
    
    wr_macro.columns = ['WR NAME', 'RECEPTIONS', 'TARGETS', 'YARDS', 'TDs']
    st.dataframe(wr_macro, hide_index=True, height=520, use_container_width=True)

    st.markdown("---")

    # 5. TIGHT END BOX
    st.subheader("TIGHT END")
    te_data = raw_data[raw_data['position'] == 'TE'].copy()
    te_macro = te_data.groupby(['player_display_name']).agg(
        RECEPTIONS=('receptions', 'sum'),
        TARGETS=('targets', 'sum'),
        YARDS=('receiving_yards', 'sum'),
        TDS=('receiving_tds', 'sum')
    ).reset_index().sort_values(by='TARGETS', ascending=False)
    
    te_macro.columns = ['TE NAME', 'RECEPTIONS', 'TARGETS', 'YARDS', 'TDs']
    st.dataframe(te_macro, hide_index=True, height=520, use_container_width=True)
