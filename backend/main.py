import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_FILE = PROJECT_ROOT / "db" / "facilityops.sqlite3"
DATABASE_DISPLAY_PATH = Path("db") / "facilityops.sqlite3"
LOADER_COMMAND = "python3 analysis/load_alarm_db.py"

COUNT_COLUMNS = {"severity", "source", "equipment"}

app = FastAPI(title="FacilityOps Copilot API")


def get_count_by_column(connection, column_name):
    """Return alarm counts grouped by a trusted alarms table column."""
    if column_name not in COUNT_COLUMNS:
        raise ValueError(f"Unsupported count column: {column_name}")

    cursor = connection.execute(
        f"""
        SELECT {column_name}, COUNT(*) AS alarm_count
        FROM alarms
        GROUP BY {column_name}
        ORDER BY alarm_count DESC, {column_name} ASC
        """
    )
    return {row[0]: row[1] for row in cursor.fetchall()}


def get_active_critical_alarms(connection):
    """Return active Critical alarms as JSON-ready dictionaries."""
    cursor = connection.execute(
        """
        SELECT timestamp, source, equipment, alarm
        FROM alarms
        WHERE severity = 'Critical'
          AND status = 'Active'
        ORDER BY timestamp ASC, source ASC, equipment ASC
        """
    )
    return [
        {
            "timestamp": timestamp,
            "source": source,
            "equipment": equipment,
            "alarm": alarm,
        }
        for timestamp, source, equipment, alarm in cursor.fetchall()
    ]


def get_alarm_summary(db_path=DATABASE_FILE):
    """Read alarm summary data from SQLite."""
    with sqlite3.connect(db_path) as connection:
        total_alarm_records = connection.execute(
            "SELECT COUNT(*) FROM alarms"
        ).fetchone()[0]

        return {
            "total_alarm_records": total_alarm_records,
            "severity_counts": get_count_by_column(connection, "severity"),
            "source_counts": get_count_by_column(connection, "source"),
            "equipment_counts": get_count_by_column(connection, "equipment"),
            "active_critical_alarms": get_active_critical_alarms(connection),
        }


@app.get("/summary")
def read_summary():
    if not DATABASE_FILE.exists():
        return JSONResponse(
            status_code=404,
            content={
                "error": f"Database not found: {DATABASE_DISPLAY_PATH}",
                "run_first": LOADER_COMMAND,
            },
        )

    return get_alarm_summary()
