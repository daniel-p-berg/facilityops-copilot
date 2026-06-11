import csv
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALARM_FILE = PROJECT_ROOT / "data" / "sample_alarms.csv"
EQUIPMENT_FILE = PROJECT_ROOT / "data" / "sample_equipment.csv"
POINT_FILE = PROJECT_ROOT / "data" / "sample_points.csv"
ALARM_RULE_FILE = PROJECT_ROOT / "data" / "sample_alarm_rules.csv"
CURRENT_POINT_VALUE_FILE = PROJECT_ROOT / "data" / "sample_current_point_values.csv"
DATABASE_FILE = PROJECT_ROOT / "db" / "facilityops.sqlite3"

ALARM_COLUMNS = (
    "timestamp",
    "source",
    "equipment",
    "equipment_type",
    "alarm",
    "severity",
    "status",
)

EQUIPMENT_COLUMNS = (
    "equipment",
    "equipment_type",
    "location",
    "criticality",
    "source_system",
    "notes",
)

POINT_COLUMNS = (
    "id",
    "equipment_id",
    "point_name",
    "display_name",
    "point_type",
    "data_type",
    "unit",
    "normal_min",
    "normal_max",
    "source_system",
    "description",
    "created_at",
    "updated_at",
)

ALARM_RULE_COLUMNS = (
    "id",
    "point_id",
    "rule_name",
    "rule_type",
    "operator",
    "threshold_value",
    "clear_value",
    "severity",
    "alarm_message",
    "enabled",
    "delay_seconds",
    "created_at",
    "updated_at",
)

CURRENT_POINT_VALUE_COLUMNS = (
    "id",
    "point_id",
    "value",
    "quality",
    "source",
    "updated_at",
)

BLANK_VALUES = {"", "null", "none", "n/a"}


def create_alarm_table(connection):
    """Create a table for sample BMS/EPMS alarm records."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS alarms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            source TEXT NOT NULL,
            equipment TEXT NOT NULL,
            equipment_type TEXT NOT NULL,
            alarm TEXT NOT NULL,
            severity TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """
    )


def create_equipment_table(connection):
    """Create a table for sample facility equipment records."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS equipment (
            equipment TEXT PRIMARY KEY,
            equipment_type TEXT NOT NULL,
            location TEXT NOT NULL,
            criticality TEXT NOT NULL,
            source_system TEXT NOT NULL,
            notes TEXT NOT NULL
        )
        """
    )


def create_point_table(connection):
    """Create a table for sample BMS/EPMS point catalog records."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS points (
            id TEXT PRIMARY KEY,
            equipment_id TEXT NOT NULL,
            point_name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            point_type TEXT NOT NULL,
            data_type TEXT NOT NULL,
            unit TEXT NOT NULL,
            normal_min REAL,
            normal_max REAL,
            source_system TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (equipment_id) REFERENCES equipment (equipment)
        )
        """
    )


def create_alarm_rule_table(connection):
    """Create a table for sample alarm rule catalog records."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS alarm_rules (
            id TEXT PRIMARY KEY,
            point_id TEXT NOT NULL,
            rule_name TEXT NOT NULL,
            rule_type TEXT NOT NULL,
            operator TEXT NOT NULL,
            threshold_value TEXT NOT NULL,
            clear_value TEXT NOT NULL,
            severity TEXT NOT NULL,
            alarm_message TEXT NOT NULL,
            enabled INTEGER NOT NULL,
            delay_seconds INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (point_id) REFERENCES points (id)
        )
        """
    )


def create_current_point_value_table(connection):
    """Create a table for current point values."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS current_point_values (
            id TEXT PRIMARY KEY,
            point_id TEXT NOT NULL UNIQUE,
            value TEXT NOT NULL,
            quality TEXT NOT NULL,
            source TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (point_id) REFERENCES points (id)
        )
        """
    )


def create_generated_alarm_table(connection):
    """Create a table for generated alarm state records."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS generated_alarms (
            id TEXT PRIMARY KEY,
            rule_id TEXT NOT NULL,
            point_id TEXT NOT NULL,
            equipment_id TEXT NOT NULL,
            alarm_message TEXT NOT NULL,
            severity TEXT NOT NULL,
            state TEXT NOT NULL,
            triggered_value TEXT NOT NULL,
            triggered_at TEXT NOT NULL,
            cleared_at TEXT NOT NULL,
            last_evaluated_at TEXT NOT NULL,
            evaluation_note TEXT NOT NULL,
            FOREIGN KEY (rule_id) REFERENCES alarm_rules (id),
            FOREIGN KEY (point_id) REFERENCES points (id),
            FOREIGN KEY (equipment_id) REFERENCES equipment (equipment)
        )
        """
    )


def read_csv_rows(csv_path, required_columns):
    """Read CSV records and validate required columns."""
    with open(csv_path, mode="r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        missing_columns = set(required_columns) - set(reader.fieldnames or [])
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"Missing required CSV columns: {missing}")

        return [
            {column: row[column] for column in required_columns}
            for row in reader
        ]


def read_alarm_rows(csv_path):
    """Read alarm records from the sample CSV file."""
    return read_csv_rows(csv_path, ALARM_COLUMNS)


def read_equipment_rows(csv_path):
    """Read equipment records from the sample equipment CSV file."""
    return read_csv_rows(csv_path, EQUIPMENT_COLUMNS)


def is_blank_value(value):
    """Return True when a CSV field should be treated as blank."""
    if value is None:
        return True

    return value.strip().lower() in BLANK_VALUES


def optional_text(value):
    """Normalize optional text CSV fields to a predictable blank string."""
    if is_blank_value(value):
        return ""

    return value.strip()


def optional_float(value):
    """Convert blank CSV numeric fields to NULL and populated fields to float."""
    if is_blank_value(value):
        return None

    return float(value)


def parse_enabled(value):
    """Parse an enabled flag into a predictable SQLite integer."""
    if value is None:
        raise ValueError("enabled must be one of: 1, 0, true, false, yes, no")

    normalized_value = value.strip().lower()
    if normalized_value in {"1", "true", "yes"}:
        return 1
    if normalized_value in {"0", "false", "no"}:
        return 0

    raise ValueError("enabled must be one of: 1, 0, true, false, yes, no")


def normalize_quality(value):
    """Normalize point value quality to a predictable catalog value."""
    if is_blank_value(value):
        return "UNKNOWN"

    return value.strip().upper()


def read_point_rows(csv_path):
    """Read point catalog records from the sample points CSV file."""
    rows = read_csv_rows(csv_path, POINT_COLUMNS)
    for row in rows:
        row["unit"] = optional_text(row["unit"])
        row["normal_min"] = optional_float(row["normal_min"])
        row["normal_max"] = optional_float(row["normal_max"])

    return rows


def read_alarm_rule_rows(csv_path):
    """Read alarm rule catalog records from the sample alarm rules CSV file."""
    rows = read_csv_rows(csv_path, ALARM_RULE_COLUMNS)
    for row in rows:
        row["threshold_value"] = optional_text(row["threshold_value"])
        row["clear_value"] = optional_text(row["clear_value"])
        row["enabled"] = parse_enabled(row["enabled"])
        row["delay_seconds"] = int(row["delay_seconds"])

    return rows


def read_current_point_value_rows(csv_path):
    """Read current point value records from the sample CSV file."""
    rows = read_csv_rows(csv_path, CURRENT_POINT_VALUE_COLUMNS)
    for row in rows:
        row["value"] = optional_text(row["value"])
        row["quality"] = normalize_quality(row["quality"])
        row["source"] = optional_text(row["source"]).upper()
        row["updated_at"] = optional_text(row["updated_at"])

    return rows


def load_alarms_to_sqlite(csv_path=ALARM_FILE, db_path=DATABASE_FILE):
    """Load sample alarm records from CSV into SQLite."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    rows = read_alarm_rows(csv_path)

    with sqlite3.connect(db_path) as connection:
        create_alarm_table(connection)
        connection.execute("DELETE FROM alarms")
        connection.executemany(
            """
            INSERT INTO alarms (
                timestamp,
                source,
                equipment,
                equipment_type,
                alarm,
                severity,
                status
            )
            VALUES (
                :timestamp,
                :source,
                :equipment,
                :equipment_type,
                :alarm,
                :severity,
                :status
            )
            """,
            rows,
        )

    return len(rows)


def load_equipment_to_sqlite(csv_path=EQUIPMENT_FILE, db_path=DATABASE_FILE):
    """Load sample equipment records from CSV into SQLite."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    rows = read_equipment_rows(csv_path)

    with sqlite3.connect(db_path) as connection:
        create_equipment_table(connection)
        connection.execute("DELETE FROM equipment")
        connection.executemany(
            """
            INSERT INTO equipment (
                equipment,
                equipment_type,
                location,
                criticality,
                source_system,
                notes
            )
            VALUES (
                :equipment,
                :equipment_type,
                :location,
                :criticality,
                :source_system,
                :notes
            )
            """,
            rows,
        )

    return len(rows)


def load_points_to_sqlite(csv_path=POINT_FILE, db_path=DATABASE_FILE):
    """Load sample point catalog records from CSV into SQLite."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    rows = read_point_rows(csv_path)

    with sqlite3.connect(db_path) as connection:
        create_point_table(connection)
        connection.execute("DELETE FROM points")
        connection.executemany(
            """
            INSERT INTO points (
                id,
                equipment_id,
                point_name,
                display_name,
                point_type,
                data_type,
                unit,
                normal_min,
                normal_max,
                source_system,
                description,
                created_at,
                updated_at
            )
            VALUES (
                :id,
                :equipment_id,
                :point_name,
                :display_name,
                :point_type,
                :data_type,
                :unit,
                :normal_min,
                :normal_max,
                :source_system,
                :description,
                :created_at,
                :updated_at
            )
            """,
            rows,
        )

    return len(rows)


def load_alarm_rules_to_sqlite(csv_path=ALARM_RULE_FILE, db_path=DATABASE_FILE):
    """Load sample alarm rule catalog records from CSV into SQLite."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    rows = read_alarm_rule_rows(csv_path)

    with sqlite3.connect(db_path) as connection:
        create_alarm_rule_table(connection)
        connection.execute("DELETE FROM alarm_rules")
        connection.executemany(
            """
            INSERT INTO alarm_rules (
                id,
                point_id,
                rule_name,
                rule_type,
                operator,
                threshold_value,
                clear_value,
                severity,
                alarm_message,
                enabled,
                delay_seconds,
                created_at,
                updated_at
            )
            VALUES (
                :id,
                :point_id,
                :rule_name,
                :rule_type,
                :operator,
                :threshold_value,
                :clear_value,
                :severity,
                :alarm_message,
                :enabled,
                :delay_seconds,
                :created_at,
                :updated_at
            )
            """,
            rows,
        )

    return len(rows)


def load_current_point_values_to_sqlite(
    csv_path=CURRENT_POINT_VALUE_FILE,
    db_path=DATABASE_FILE,
):
    """Load current point value records from CSV into SQLite."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    rows = read_current_point_value_rows(csv_path)

    with sqlite3.connect(db_path) as connection:
        create_current_point_value_table(connection)
        connection.execute("DELETE FROM current_point_values")
        connection.executemany(
            """
            INSERT INTO current_point_values (
                id,
                point_id,
                value,
                quality,
                source,
                updated_at
            )
            VALUES (
                :id,
                :point_id,
                :value,
                :quality,
                :source,
                :updated_at
            )
            """,
            rows,
        )

    return len(rows)


def reset_generated_alarms(db_path=DATABASE_FILE):
    """Create and clear generated alarm state output records."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        create_generated_alarm_table(connection)
        connection.execute("DELETE FROM generated_alarms")


def load_sample_data_to_sqlite(
    alarm_csv_path=ALARM_FILE,
    equipment_csv_path=EQUIPMENT_FILE,
    point_csv_path=POINT_FILE,
    alarm_rule_csv_path=ALARM_RULE_FILE,
    current_point_value_csv_path=CURRENT_POINT_VALUE_FILE,
    db_path=DATABASE_FILE,
):
    """Load sample facility records into SQLite."""
    alarm_count = load_alarms_to_sqlite(alarm_csv_path, db_path)
    equipment_count = load_equipment_to_sqlite(equipment_csv_path, db_path)
    point_count = load_points_to_sqlite(point_csv_path, db_path)
    alarm_rule_count = load_alarm_rules_to_sqlite(alarm_rule_csv_path, db_path)
    current_point_value_count = load_current_point_values_to_sqlite(
        current_point_value_csv_path,
        db_path,
    )
    reset_generated_alarms(db_path)

    return {
        "alarm_records": alarm_count,
        "equipment_records": equipment_count,
        "point_records": point_count,
        "alarm_rule_records": alarm_rule_count,
        "current_point_value_records": current_point_value_count,
    }


def get_group_counts(connection, column_name):
    """Return record counts grouped by a trusted alarms table column."""
    if column_name not in {"severity", "source", "equipment"}:
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


def get_alarm_counts(db_path=DATABASE_FILE):
    """Return alarm counts by severity, source, and equipment from SQLite."""
    with sqlite3.connect(db_path) as connection:
        total_records = connection.execute(
            "SELECT COUNT(*) FROM alarms"
        ).fetchone()[0]

        return {
            "total_alarm_records": total_records,
            "severity_counts": get_group_counts(connection, "severity"),
            "source_counts": get_group_counts(connection, "source"),
            "equipment_counts": get_group_counts(connection, "equipment"),
        }


def print_count_section(title, counts):
    print(title)
    for name, count in counts.items():
        print(f"- {name}: {count}")


def print_verification_summary(
    summary,
    equipment_record_count=None,
    point_record_count=None,
    alarm_rule_record_count=None,
    current_point_value_record_count=None,
):
    print(f"Total alarm records loaded: {summary['total_alarm_records']}")
    if equipment_record_count is not None:
        print(f"Equipment records loaded: {equipment_record_count}")
    if point_record_count is not None:
        print(f"Point records loaded: {point_record_count}")
    if alarm_rule_record_count is not None:
        print(f"Alarm rule records loaded: {alarm_rule_record_count}")
    if current_point_value_record_count is not None:
        print(f"Current point value records loaded: {current_point_value_record_count}")
    print_count_section("Alarm counts by severity:", summary["severity_counts"])
    print_count_section("Alarm counts by source:", summary["source_counts"])
    print_count_section("Alarm counts by equipment:", summary["equipment_counts"])


def main():
    load_counts = load_sample_data_to_sqlite()
    summary = get_alarm_counts()
    print(f"SQLite database generated: {DATABASE_FILE}")
    print_verification_summary(
        summary,
        equipment_record_count=load_counts["equipment_records"],
        point_record_count=load_counts["point_records"],
        alarm_rule_record_count=load_counts["alarm_rule_records"],
        current_point_value_record_count=load_counts["current_point_value_records"],
    )


if __name__ == "__main__":
    main()
