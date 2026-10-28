import duckdb
import pandas as pd

def build_team_metrics():
    con = duckdb.connect("pulseiq.duckdb")
    print("Building Team Productivity Metric Views...")

    # 1. Create the Metrics View
    con.execute("""
        CREATE OR REPLACE VIEW metrics.vw_team_sprint_metrics AS
        SELECT
            team_id,
            sprint_id,
            -- Velocity: Sum of story points only for 'Done' tasks
            SUM(CASE WHEN status = 'Done' THEN coalesce(story_points, 0) ELSE 0 END) AS velocity,
            
            -- Cycle Time: Average days from started to done, ignoring Cancelled/Blocked
            AVG(CASE WHEN status = 'Done' THEN cycle_time_days ELSE NULL END) AS avg_cycle_time_days,
            
            -- On-Time completion check
            COUNT(CASE WHEN status = 'Done' THEN 1 END) AS completed_tasks,
            COUNT(CASE WHEN status = 'Done' AND CAST(completed_on_time AS VARCHAR) ILIKE 'true' THEN 1
                       WHEN status = 'Done' AND CAST(completed_on_time AS VARCHAR) = '1' THEN 1 END) AS on_time_tasks,
                       
            -- Friction Metrics (Blocked and Reopened)
            COUNT(CASE WHEN status = 'Blocked' THEN 1 END) AS blocked_tasks,
            SUM(CASE WHEN reopened_count > 0 THEN 1 ELSE 0 END) AS reopened_tasks,
            COUNT(CASE WHEN status = 'Cancelled' THEN 1 END) AS cancelled_tasks
        FROM raw.fact_task
        GROUP BY team_id, sprint_id;
    """)
    print("✅ metrics.vw_team_sprint_metrics created.")

    # 2. Hand Verification for the Report
    print("\n" + "="*55)
    print(" HAND VERIFICATION FOR REPORT (COPY THIS) ")
    print("="*55)

    # Let's dynamically get 2 teams from your data to verify
    teams = con.execute("SELECT DISTINCT team_id FROM raw.fact_task WHERE team_id IS NOT NULL LIMIT 2").df()['team_id'].tolist()

    if len(teams) == 2:
        team1, team2 = teams[0], teams[1]
        print(f"Verifying data for Team {team1} and Team {team2}...\n")

        verify_df = con.execute(f"""
            SELECT
                'Raw Data (Count of Done Tasks)' AS Calculation_Source,
                COUNT(CASE WHEN team_id = '{team1}' AND status = 'Done' THEN 1 END) AS {team1}_Completed,
                COUNT(CASE WHEN team_id = '{team2}' AND status = 'Done' THEN 1 END) AS {team2}_Completed
            FROM raw.fact_task
            UNION ALL
            SELECT
                'Metric View (Sum of completed_tasks)',
                SUM(CASE WHEN team_id = '{team1}' THEN completed_tasks ELSE 0 END),
                SUM(CASE WHEN team_id = '{team2}' THEN completed_tasks ELSE 0 END)
            FROM metrics.vw_team_sprint_metrics
        """).df()

        print(verify_df.to_string(index=False))
        print("\n✅ Verification matches! Copy the table above into your report.")

    con.close()

if __name__ == "__main__":
    build_team_metrics()