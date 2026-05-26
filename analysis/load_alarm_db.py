import csv
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALARM_FILE = PROJECT_ROOT / "data" / "sample_alarms.csv"
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


def read_alarm_rows(csv_path):
    """Read alarm records from the sample CSV file."""
    with open(csv_path, mode="r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        missing_columns = set(ALARM_COLUMNS) - set(reader.fieldnames or [])
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"Missing required CSV columns: {missing}")

        return [
            {column: row[column] for column in ALARM_COLUMNS}
            for row in reader
        ]


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


def print_verification_summary(summary):
    print(f"Total alarm records loaded: {summary['total_alarm_records']}")
    print_count_section("Alarm counts by severity:", summary["severity_counts"])
    print_count_section("Alarm counts by source:", summary["source_counts"])
    print_count_section("Alarm counts by equipment:", summary["equipment_counts"])


def main():
    load_alarms_to_sqlite()
    summary = get_alarm_counts()
    print(f"SQLite database generated: {DATABASE_FILE}")
    print_verification_summary(summary)


if __name__ == "__main__":
    main()
