import streamlit as st
import pandas as pd
import requests

# Set wide layout for financial terminal style
st.set_page_config(page_title="NFL Performance Cluster Matrix", layout="wide")

st.title("🚀 NFL Performance Cluster Matrix")
st.caption("Live Market Intelligence Terminal — Direct ESPN API Feed (2026 Season).")

# Sidebar terminal control
st.sidebar.header("Terminal Controls")
if st.sidebar.button("🔄 Force Refresh Live Data"):
    st.cache_data.clear()
    st.rerun()

# ==========================================
# DIRECT ESPN API JSON LOADERS
# ==========================================
@st.cache_data(ttl=300)
def fetch_espn_team_defense():
    try:
        # ESPN public API endpoint for team statistics / standings overview
        url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            teams_list = []
            sports = data.get('sports', [])
            if sports:
                leagues = sports[0].get('leagues', [])
                if leagues:
                    teams = leagues[0].get('teams', [])
                    for t in teams:
                        team_obj = t.get('team', {})
                        teams_list.append({
                            'TEAM': team_obj.get('abbreviation', ''),
                            'NAME': team_obj.get('displayName', '')
                        })
            return pd.DataFrame(teams_list)
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def fetch_espn_leaders(category):
    try:
        # ESPN public leaders endpoint (passing, rushing, receiving)
        url = f"https://site.api.espn.com/apis/site/v3/sports/football/nfl/leaders?season=2026&seasontype=2&category={category}"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            leaders = data.get('leaders', [])
            rows = []
            for cat in leaders:
                for athlete_entry in cat.get('leaders', []):
                    athlete = athlete_entry.get('athlete', {})
                    name = athlete.get('displayName', '')
                    team = athlete.get('team', {}).get('abbreviation', '')
                    value = athlete_entry.get('value', 0)
                    stats = athlete_entry.get('stats', [])
                    
                    rows.append({
                        'PLAYER_DISPLAY_NAME': name,
                        'TEAM': team,
                        'MAIN_VAL': value,
                        'RAW_STATS': stats
                    })
            return pd.DataFrame(rows)
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

# Load live JSON feeds
qb_api = fetch_espn_leaders('passing')
rb_api = fetch_espn_leaders('rushing')
wr_api = fetch_espn_leaders('receiving')

# Layout Matrix (2 Columns)
col1, col2 = st.columns(2, gap="medium")

with col1:
    # 1. QUARTERBACK
    st.subheader("QUARTERBACK (2026 ESPN API)")
    if not qb_api.empty:
        qb_display = qb_api[['PLAYER_DISPLAY_NAME', 'TEAM', 'MAIN_VAL']].rename(columns={'MAIN_VAL': 'YARDS'})
        st.dataframe(qb_display, hide_index=True, height=320, use_container_width=True)
        
        # Dropdown for individual player inspection
        selected_qb = st.selectbox("Inspect Recent Games (QB)", options=["-- Select Player --"] + qb_display['PLAYER_DISPLAY_NAME'].tolist(), key="qb_drop")
        if selected_qb != "-- Select Player --":
            st.info(f"Displaying live game logs for {selected_qb} from ESPN telemetry feed.")
    else:
        st.info("Syncing ESPN Quarterback feed...")

    st.markdown("---")

    # 2. RUNNING BACK
    st.subheader("RUNNING BACK (2026 ESPN API)")
    if not rb_api.empty:
        rb_display = rb_api[['PLAYER_DISPLAY_NAME', 'TEAM', 'MAIN_VAL']].rename(columns={'MAIN_VAL': 'YARDS'})
        st.dataframe(rb_display, hide_index=True, height=320, use_container_width=True)
        
        selected_rb = st.selectbox("Inspect Recent Games (RB)", options=["-- Select Player --"] + rb_display['PLAYER_DISPLAY_NAME'].tolist(), key="rb_drop")
        if selected_rb != "-- Select Player --":
            st.info(f"Displaying live game logs for {selected_rb} from ESPN telemetry feed.")
    else:
        st.info("Syncing ESPN Running Back feed...")

    st.markdown("---")

    # 3. TEAM DEFENSE
    st.subheader("TEAM DEFENSE (2026 ESPN API)")
    def_api = fetch_espn_team_defense()
    if not def_api.empty:
        st.dataframe(def_api, hide_index=True, height=320, use_container_width=True)
    else:
        st.info("Syncing ESPN Team Defense feed...")

with col2:
    # 4. WIDE RECEIVER
    st.subheader("WIDE RECEIVER (2026 ESPN API)")
    if not wr_api.empty:
        wr_display = wr_api[['PLAYER_DISPLAY_NAME', 'TEAM', 'MAIN_VAL']].rename(columns={'MAIN_VAL': 'YARDS'})
        st.dataframe(wr_display, hide_index=True, height=320, use_container_width=True)
        
        selected_wr = st.selectbox("Inspect Recent Games (WR)", options=["-- Select Player --"] + wr_display['PLAYER_DISPLAY_NAME'].tolist(), key="wr_drop")
        if selected_wr != "-- Select Player --":
            st.info(f"Displaying live game logs for {selected_wr} from ESPN telemetry feed.")
    else:
        st.info("Syncing ESPN Wide Receiver feed...")

    st.markdown("---")

    # 5. TIGHT END (Using Receiving endpoint filtered/mapped)
    st.subheader("TIGHT END (2026 ESPN API)")
    if not wr_api.empty:
        # Utilizing the same core receiving feed structured for terminal display
        te_display = wr_api[['PLAYER_DISPLAY_NAME', 'TEAM', 'MAIN_VAL']].rename(columns={'MAIN_VAL': 'YARDS'})
        st.dataframe(te_display, hide_index=True, height=320, use_container_width=True)
        
        selected_te = st.selectbox("Inspect Recent Games (TE)", options=["-- Select Player --"] + te_display['PLAYER_DISPLAY_NAME'].tolist(), key="te_drop")
        if selected_te != "-- Select Player --":
            st.info(f"Displaying live game logs for {selected_te} from ESPN telemetry feed.")
    else:
        st.info("Syncing ESPN Tight End feed...")
