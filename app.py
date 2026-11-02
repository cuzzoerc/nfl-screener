# 3. TEAM DEFENSE (Correct Defensive Allowed Aggregation)
    st.subheader("TEAM DEFENSE (2026)")
    if 'opponent_team' in filtered_data.columns:
        # Sum passing and rushing allowed across all opposing offensive players
        def_agg = {
            'passing_yards': 'sum',
            'passing_tds': 'sum',
            'rushing_yards': 'sum',
            'rushing_tds': 'sum'
        }
        existing_agg = {k: v for k, v in def_agg.items() if k in filtered_data.columns}
        
        def_df = filtered_data.groupby('opponent_team').agg(existing_agg).reset_index()
        
        # Calculate true Games Played (GP) per defense from weekly schedules
        if 'week' in filtered_data.columns:
            gp_df = filtered_data.groupby('opponent_team')['week'].nunique().reset_index().rename(columns={'week': 'GP'})
            def_df = def_df.merge(gp_df, on='opponent_team', how='left')
        else:
            def_df['GP'] = 1

        if not def_df.empty:
            def_df = def_df.rename(columns={
                'opponent_team': 'TEAM',
                'passing_yards': 'PASS_YDS',
                'passing_tds': 'PASS_TDS',
                'rushing_yards': 'RUSH_YDS',
                'rushing_tds': 'RUSH_TDS'
            })
            
            # Compute official per-game defensive metrics
            def_df['PASS YDS/G'] = (def_df['PASS_YDS'] / def_df['GP']).round(1)
            def_df['RUSH YDS/G'] = (def_df['RUSH_YDS'] / def_df['GP']).round(1)
            def_df['TOTAL YDS/G'] = ((def_df['PASS_YDS'] + def_df['RUSH_YDS']) / def_df['GP']).round(1)
            
            # Rank strictly by lowest Total Yards Allowed Per Game (matching ESPN)
            def_df['RANK'] = def_df['TOTAL YDS/G'].rank(ascending=True, method='min').astype(int)
            
            def_macro = def_df.sort_values(by='RANK', ascending=True)[[
                'TEAM', 'PASS YDS/G', 'PASS_TDS', 'RUSH YDS/G', 'RUSH_TDS', 'RANK'
            ]]
            def_macro.columns = ['TEAM', 'PASS YDS/G', 'PASS TDS', 'RUSH YDS/G', 'RUSH TDS', 'RANK']
            
            st.dataframe(def_macro, hide_index=True, height=320, use_container_width=True)
        else:
            st.info("Defense metrics unavailable.")
    else:
        st.info("Defense opponent column missing.")
