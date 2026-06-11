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


def get_point_dictionary(db_path=DATABASE_FILE):
    """Return point catalog records with equipment context."""
    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(
            """
            SELECT
                points.id,
                points.equipment_id,
                COALESCE(equipment.equipment_type, 'Unknown') AS equipment_type,
                COALESCE(equipment.location, 'Unknown') AS location,
                COALESCE(equipment.criticality, 'Unknown') AS criticality,
                points.point_name,
                points.display_name,
                points.point_type,
                points.data_type,
                points.unit,
                points.normal_min,
                points.normal_max,
                points.source_system,
                points.description
            FROM points
            LEFT JOIN equipment
                ON points.equipment_id = equipment.equipment
            ORDER BY points.equipment_id ASC, points.point_name ASC
            """
        )
        return [
            {
                "id": point_id,
                "equipment_id": equipment_id,
                "equipment_type": equipment_type,
                "location": location,
                "criticality": criticality,
                "point_name": point_name,
                "display_name": display_name,
                "point_type": point_type,
                "data_type": data_type,
                "unit": unit,
                "normal_min": normal_min,
                "normal_max": normal_max,
                "source_system": source_system,
                "description": description,
            }
            for (
                point_id,
                equipment_id,
                equipment_type,
                location,
                criticality,
                point_name,
                display_name,
                point_type,
                data_type,
                unit,
                normal_min,
                normal_max,
                source_system,
                description,
            ) in cursor.fetchall()
        ]


def get_alarm_rule_catalog(db_path=DATABASE_FILE):
    """Return alarm rule catalog records with point and equipment context."""
    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(
            """
            SELECT
                alarm_rules.id,
                alarm_rules.point_id,
                points.point_name,
                points.display_name,
                points.equipment_id,
                COALESCE(equipment.equipment_type, 'Unknown') AS equipment_type,
                COALESCE(equipment.location, 'Unknown') AS location,
                alarm_rules.rule_name,
                alarm_rules.rule_type,
                alarm_rules.operator,
                alarm_rules.threshold_value,
                alarm_rules.clear_value,
                alarm_rules.severity,
                alarm_rules.alarm_message,
                alarm_rules.enabled,
                alarm_rules.delay_seconds
            FROM alarm_rules
            LEFT JOIN points
                ON alarm_rules.point_id = points.id
            LEFT JOIN equipment
                ON points.equipment_id = equipment.equipment
            ORDER BY points.equipment_id ASC, points.point_name ASC, alarm_rules.rule_name ASC
            """
        )
        return [
            {
                "id": rule_id,
                "point_id": point_id,
                "point_name": point_name,
                "display_name": display_name,
                "equipment_id": equipment_id,
                "equipment_type": equipment_type,
                "location": location,
                "rule_name": rule_name,
                "rule_type": rule_type,
                "operator": operator,
                "threshold_value": threshold_value,
                "clear_value": clear_value,
                "severity": severity,
                "alarm_message": alarm_message,
                "enabled": bool(enabled),
                "delay_seconds": delay_seconds,
            }
            for (
                rule_id,
                point_id,
                point_name,
                display_name,
                equipment_id,
                equipment_type,
                location,
                rule_name,
                rule_type,
                operator,
                threshold_value,
                clear_value,
                severity,
                alarm_message,
                enabled,
                delay_seconds,
            ) in cursor.fetchall()
        ]


def get_current_point_values(db_path=DATABASE_FILE):
    """Return current point values with point and equipment context."""
    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(
            """
            SELECT
                current_point_values.id,
                current_point_values.point_id,
                points.point_name,
                points.display_name,
                points.equipment_id,
                COALESCE(equipment.equipment_type, 'Unknown') AS equipment_type,
                COALESCE(equipment.location, 'Unknown') AS location,
                points.point_type,
                points.data_type,
                points.unit,
                current_point_values.value,
                current_point_values.quality,
                current_point_values.source,
                current_point_values.updated_at
            FROM current_point_values
            LEFT JOIN points
                ON current_point_values.point_id = points.id
            LEFT JOIN equipment
                ON points.equipment_id = equipment.equipment
            ORDER BY points.equipment_id ASC, points.point_name ASC
            """
        )
        return [
            {
                "id": value_id,
                "point_id": point_id,
                "point_name": point_name,
                "display_name": display_name,
                "equipment_id": equipment_id,
                "equipment_type": equipment_type,
                "location": location,
                "point_type": point_type,
                "data_type": data_type,
                "unit": unit,
                "value": value,
                "quality": quality,
                "source": source,
                "updated_at": updated_at,
            }
            for (
                value_id,
                point_id,
                point_name,
                display_name,
                equipment_id,
                equipment_type,
                location,
                point_type,
                data_type,
                unit,
                value,
                quality,
                source,
                updated_at,
            ) in cursor.fetchall()
        ]
