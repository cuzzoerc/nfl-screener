import streamlit as st
import nfl_data_py as nfl
import pandas as pd

st.set_page_config(page_title="NFL Performance Screener", layout="wide")

st.title("NFL Multi-Position Analytics Screener")
st.caption("Macro season leaderboards with instant last-5-game micro drill-downs. Updated daily at 00:00 EST.")

# Cached data loader for the active/recent season
@st.cache_data
def load_nfl_data():
    # Loads weekly player data
    df = nfl.import_weekly_data([2024])
    return df

try:
    raw_data = load_nfl_data()
except Exception as e:
    st.error(f"Error loading NFL data: {e}")
    st.stop()

# Selection navigation for position matrices
position_tab = st.selectbox(
    "Select Position Matrix", 
    ["QUARTERBACK", "RUNNING BACK", "WIDE RECEIVER", "TIGHT END", "PLACE KICKER"]
)

# ==========================================
# 1. QUARTERBACK MATRIX
# ==========================================
if position_tab == "QUARTERBACK":
    st.subheader("All Starting Quarterbacks")
    qb_data = raw_data[raw_data['position'] == 'QB'].copy()
    
    # Calculate Macro Season Stats
    qb_macro = qb_data.groupby(['player_id', 'player_display_name']).agg(
        COMPLETIONS=('completions', 'sum'),
        ATTEMPTS=('attempts', 'sum'),
        YARDS=('passing_yards', 'sum'),
        TDS=('passing_tds', 'sum'),
        INT=('interceptions', 'sum')
    ).reset_index().sort_values(by='YARDS', ascending=False)
    
    # Render Master-Detail View (Macro summary + expandable last 5 games)
    for _, player in qb_macro.iterrows():
        label = (
            f"**{player['player_display_name']}** | "
            f"COMP: {int(player['COMPLETIONS'])} | "
            f"ATT: {int(player['ATTEMPTS'])} | "
            f"YDS: {int(player['YARDS'])} | "
            f"TDS: {int(player['TDS'])} | "
            f"INT: {int(player['INT'])}"
        )
        with st.expander(label):
            recent_games = qb_data[qb_data['player_id'] == player['player_id']].tail(5)
            game_log = recent_games[['week', 'opponent_team', 'completions', 'attempts', 'passing_yards', 'passing_tds', 'interceptions']].copy()
            game_log.columns = ['WEEK', 'OPP', 'COMP', 'ATT', 'YDS', 'TDS', 'INT']
            st.dataframe(game_log, hide_index=True, use_container_width=True)

# ==========================================
# 2. RUNNING BACK MATRIX
# ==========================================
elif position_tab == "RUNNING BACK":
    st.subheader("All Running Backs")
    rb_data = raw_data[raw_data['position'] == 'RB'].copy()
    
    # Calculate Total TDs if present, else sum rushing tds
    td_col = 'touchdowns' if 'touchdowns' in rb_data.columns else 'rushing_tds'
    
    rb_macro = rb_data.groupby(['player_id', 'player_display_name']).agg(
        CARRYS=('carries', 'sum'),
        CARRY_YARDS=('rushing_yards', 'sum'),
        RECEPTIONS=('receptions', 'sum'),
        RECEPTION_YARDS=('receiving_yards', 'sum'),
        TDS=(td_col, 'sum')
    ).reset_index().sort_values(by='CARRY_YARDS', ascending=False)
    
    for _, player in rb_macro.iterrows():
        label = (
            f"**{player['player_display_name']}** | "
            f"CARRYS: {int(player['CARRYS'])} | "
            f"CARRY YDS: {int(player['CARRY_YARDS'])} | "
            f"REC: {int(player['RECEPTIONS'])} | "
            f"REC YDS: {int(player['RECEPTION_YARDS'])} | "
            f"TDS: {int(player['TDS'])}"
        )
        with st.expander(label):
            recent_games = rb_data[rb_data['player_id'] == player['player_id']].tail(5)
            game_log = recent_games[['week', 'opponent_team', 'carries', 'rushing_yards', 'receptions', 'receiving_yards']].copy()
            game_log.columns = ['WEEK', 'OPP', 'CARRYS', 'CARRY YDS', 'REC', 'REC YDS']
            st.dataframe(game_log, hide_index=True, use_container_width=True)

# ==========================================
# 3. WIDE RECEIVER MATRIX
# ==========================================
elif position_tab == "WIDE RECEIVER":
    st.subheader("All Wide Receivers")
    wr_data = raw_data[raw_data['position'] == 'WR'].copy()
    
    wr_macro = wr_data.groupby(['player_id', 'player_display_name']).agg(
        RECEPTIONS=('receptions', 'sum'),
        TARGETS=('targets', 'sum'),
        YARDS=('receiving_yards', 'sum'),
        TDS=('receiving_tds', 'sum')
    ).reset_index().sort_values(by='TARGETS', ascending=False)
    
    for _, player in wr_macro.iterrows():
        label = (
            f"**{player['player_display_name']}** | "
            f"REC: {int(player['RECEPTIONS'])} | "
            f"TGTS: {int(player['TARGETS'])} | "
            f"YDS: {int(player['YARDS'])} | "
            f"TDS: {int(player['TDS'])}"
        )
        with st.expander(label):
            recent_games = wr_data[wr_data['player_id'] == player['player_id']].tail(5)
            game_log = recent_games[['week', 'opponent_team', 'receptions', 'targets', 'receiving_yards', 'receiving_tds']].copy()
            game_log.columns = ['WEEK', 'OPP', 'REC', 'TGTS', 'YDS', 'TDS']
            st.dataframe(game_log, hide_index=True, use_container_width=True)

# ==========================================
# 4. TIGHT END MATRIX
# ==========================================
elif position_tab == "TIGHT END":
    st.subheader("All Tight Ends")
    te_data = raw_data[raw_data['position'] == 'TE'].copy()
    
    te_macro = te_data.groupby(['player_id', 'player_display_name']).agg(
        RECEPTIONS=('receptions', 'sum'),
        TARGETS=('targets', 'sum'),
        YARDS=('receiving_yards', 'sum'),
        TDS=('receiving_tds', 'sum')
    ).reset_index().sort_values(by='TARGETS', ascending=False)
    
    for _, player in te_macro.iterrows():
        label = (
            f"**{player['player_display_name']}** | "
            f"REC: {int(player['RECEPTIONS'])} | "
            f"TGTS: {int(player['TARGETS'])} | "
            f"YDS: {int(player['YARDS'])} | "
            f"TDS: {int(player['TDS'])}"
        )
        with st.expander(label):
            recent_games = te_data[te_data['player_id'] == player['player_id']].tail(5)
            game_log = recent_games[['week', 'opponent_team', 'receptions', 'targets', 'receiving_yards', 'receiving_tds']].copy()
            game_log.columns = ['WEEK', 'OPP', 'REC', 'TGTS', 'YDS', 'TDS']
            st.dataframe(game_log, hide_index=True, use_container_width=True)

# ==========================================
# 5. PLACE KICKER MATRIX
# ==========================================
elif position_tab == "PLACE KICKER":
    st.subheader("All Place Kickers")
    pk_data = raw_data[raw_data['position'] == 'K'].copy()
    
    pk_grouped = pk_data.groupby(['player_id', 'player_display_name']).agg(
        FG_MADE=('fg_made', 'sum'),
        FG_ATT=('fg_att', 'sum'),
        PAT_MADE=('pat_made', 'sum')
    ).reset_index()
    
    # Compute FG Completion Rate and Total Points
    pk_grouped['FG_COMP_RATE'] = (pk_grouped['FG_MADE'] / pk_grouped['FG_ATT'].replace(0, 1) * 100).round(1).astype(str) + '%'
    pk_grouped['TOTAL_POINTS'] = (pk_grouped['FG_MADE'] * 3) + pk_grouped['PAT_MADE']
    pk_macro = pk_grouped.sort_values(by='TOTAL_POINTS', ascending=False)
    
    for _, player in pk_macro.iterrows():
        label = (
            f"**{player['player_display_name']}** | "
            f"FG%: {player['FG_COMP_RATE']} | "
            f"PAT MADE: {int(player['PAT_MADE'])} | "
            f"TOTAL PTS: {int(player['TOTAL_POINTS'])}"
        )
        with st.expander(label):
            recent_games = pk_data[pk_data['player_id'] == player['player_id']].tail(5)
            game_log = recent_games[['week', 'opponent_team', 'fg_made', 'fg_att', 'pat_made']].copy()
            game_log.columns = ['WEEK', 'OPP', 'FG MADE', 'FG ATT', 'PAT MADE']
            st.dataframe(game_log, hide_index=True, use_container_width=True)
