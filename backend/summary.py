import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_FILE = PROJECT_ROOT / "db" / "facilityops.sqlite3"
DATABASE_DISPLAY_PATH = Path("db") / "facilityops.sqlite3"
LOADER_COMMAND = "python3 analysis/load_alarm_db.py"

COUNT_COLUMNS = {"severity", "source", "equipment"}


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
    """Return active Critical alarms with equipment context."""
    cursor = connection.execute(
        """
        SELECT
            alarms.timestamp,
            alarms.source,
            alarms.equipment,
            COALESCE(equipment.equipment_type, alarms.equipment_type) AS equipment_type,
            COALESCE(equipment.location, 'Unknown') AS location,
            COALESCE(equipment.criticality, 'Unknown') AS criticality,
            COALESCE(equipment.source_system, alarms.source) AS source_system,
            alarms.alarm
        FROM alarms
        LEFT JOIN equipment
            ON alarms.equipment = equipment.equipment
        WHERE alarms.severity = 'Critical'
          AND alarms.status = 'Active'
        ORDER BY alarms.timestamp ASC, alarms.source ASC, alarms.equipment ASC
        """
    )
    return [
        {
            "timestamp": timestamp,
            "source": source,
            "equipment": equipment_name,
            "equipment_type": equipment_type,
            "location": location,
            "criticality": criticality,
            "source_system": source_system,
            "alarm": alarm,
        }
        for (
            timestamp,
            source,
            equipment_name,
            equipment_type,
            location,
            criticality,
            source_system,
            alarm,
        ) in cursor.fetchall()
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


def get_equipment_inventory(db_path=DATABASE_FILE):
    """Return the equipment inventory from SQLite."""
    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(
            """
            SELECT
                equipment,
                equipment_type,
                location,
                criticality,
                source_system,
                notes
            FROM equipment
            ORDER BY equipment ASC
            """
        )
        return [
            {
                "equipment": equipment,
                "equipment_type": equipment_type,
                "location": location,
                "criticality": criticality,
                "source_system": source_system,
                "notes": notes,
            }
            for (
                equipment,
                equipment_type,
                location,
                criticality,
                source_system,
                notes,
            ) in cursor.fetchall()
        ]
