import csv
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALARM_FILE = PROJECT_ROOT / "data" / "sample_alarms.csv"
REPORT_FILE = PROJECT_ROOT / "reports" / "daily_briefing.md"


def load_alarms(file_path):
    """Load alarm records from a CSV file."""
    with open(file_path, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return list(reader)


def summarize_alarms(alarms):
    """Create basic alarm summary statistics."""
    severity_counts = Counter(alarm["severity"] for alarm in alarms)
    source_counts = Counter(alarm["source"] for alarm in alarms)
    equipment_counts = Counter(alarm["equipment"] for alarm in alarms)

    active_critical_alarms = [
        alarm for alarm in alarms
        if alarm["severity"] == "Critical" and alarm["status"] == "Active"
    ]

    return {
        "total_alarms": len(alarms),
        "severity_counts": severity_counts,
        "source_counts": source_counts,
        "equipment_counts": equipment_counts,
        "active_critical_alarms": active_critical_alarms,
    }


def write_report(summary):
    """Write a simple daily operations briefing."""
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Daily Facility Operations Briefing",
        "",
        "## Executive Summary",
        "",
        f"The sample facility alarm log contains {summary['total_alarms']} total alarm records.",
        "",
        "## Alarm Count by Severity",
        "",
    ]

    for severity, count in summary["severity_counts"].most_common():
        lines.append(f"- {severity}: {count}")

    lines.extend([
        "",
        "## Alarm Count by Source",
        "",
    ])

    for source, count in summary["source_counts"].most_common():
        lines.append(f"- {source}: {count}")

    lines.extend([
        "",
        "## Most Frequent Equipment in Alarm",
        "",
    ])

    for equipment, count in summary["equipment_counts"].most_common():
        lines.append(f"- {equipment}: {count}")

    lines.extend([
        "",
        "## Active Critical Alarms",
        "",
    ])

    if summary["active_critical_alarms"]:
        for alarm in summary["active_critical_alarms"]:
            lines.append(
                f"- {alarm['timestamp']} | {alarm['source']} | "
                f"{alarm['equipment']} | {alarm['alarm']}"
            )
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

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")


def main():
    alarms = load_alarms(ALARM_FILE)
    summary = summarize_alarms(alarms)
    write_report(summary)
    print(f"Report generated: {REPORT_FILE}")


if __name__ == "__main__":
    main()
