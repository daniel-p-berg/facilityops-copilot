import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_FILE = PROJECT_ROOT / "db" / "facilityops.sqlite3"
REPORT_FILE = PROJECT_ROOT / "reports" / "daily_briefing_from_db.md"

DATABASE_DISPLAY_PATH = Path("db") / "facilityops.sqlite3"
LOADER_COMMAND = "python3 analysis/load_alarm_db.py"


def get_group_counts(connection, column_name):
    """Return alarm counts grouped by a trusted alarms table column."""
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
    return cursor.fetchall()


def get_active_critical_alarms(connection):
    """Return active Critical alarms from the SQLite alarm table."""
    cursor = connection.execute(
        """
        SELECT timestamp, source, equipment, alarm
        FROM alarms
        WHERE severity = 'Critical'
          AND status = 'Active'
        ORDER BY timestamp ASC, source ASC, equipment ASC
        """
    )
    return cursor.fetchall()


def build_summary(db_path=DATABASE_FILE):
    """Build the daily briefing summary from SQLite alarm records."""
    with sqlite3.connect(db_path) as connection:
        total_alarms = connection.execute(
            "SELECT COUNT(*) FROM alarms"
        ).fetchone()[0]

        return {
            "total_alarms": total_alarms,
            "severity_counts": get_group_counts(connection, "severity"),
            "source_counts": get_group_counts(connection, "source"),
            "equipment_counts": get_group_counts(connection, "equipment"),
            "active_critical_alarms": get_active_critical_alarms(connection),
        }


def add_count_section(lines, title, counts):
    lines.extend([
        "",
        title,
        "",
    ])

    for name, count in counts:
        lines.append(f"- {name}: {count}")


def write_report(summary, report_path=REPORT_FILE):
    """Write the database-backed daily operations briefing."""
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Daily Facility Operations Briefing from SQLite",
        "",
        "## Executive Summary",
        "",
        f"The SQLite alarm database contains {summary['total_alarms']} total alarm records.",
    ]

    add_count_section(
        lines,
        "## Alarm Count by Severity",
        summary["severity_counts"],
    )
    add_count_section(
        lines,
        "## Alarm Count by Source",
        summary["source_counts"],
    )
    add_count_section(
        lines,
        "## Most Frequent Equipment in Alarm",
        summary["equipment_counts"],
    )

    lines.extend([
        "",
        "## Active Critical Alarms",
        "",
    ])

    if summary["active_critical_alarms"]:
        for timestamp, source, equipment, alarm in summary["active_critical_alarms"]:
            lines.append(f"- {timestamp} | {source} | {equipment} | {alarm}")
    else:
        lines.append("- No active critical alarms found.")

    lines.extend([
        "",
        "## Operator Follow-Up",
        "",
        "- Review active Critical alarms first.",
        "- Check for repeated alarms on the same equipment.",
        "- Compare BMS alarms against EPMS events when power and cooling issues occur near the same time.",
        "- Confirm whether repeated alarms represent actual equipment issues, nuisance alarms, or communication problems.",
        "",
    ])

    report_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    if not DATABASE_FILE.exists():
        print(f"Database not found: {DATABASE_DISPLAY_PATH}")
        print(f"Run this first: {LOADER_COMMAND}")
        return

    summary = build_summary()
    write_report(summary)
    print(f"Report generated: {REPORT_FILE.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
