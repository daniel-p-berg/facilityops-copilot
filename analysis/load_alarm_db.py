import csv
import sqlite3
import sys
import uuid
from datetime import UTC
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""}:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.facility_package_registry import NORTHSTAR_FACILITY_ID
from backend.services.facility_package_registry import NORTHSTAR_FIXTURE_VERSION
from backend.services.facility_package_registry import resolve_registered_fixture
from backend.services.facility_topology_service import clear_topology_rows
from backend.services.facility_topology_service import create_facility_topology_tables
from backend.services.facility_topology_service import record_facility_environment

ALARM_FILE = PROJECT_ROOT / "data" / "sample_alarms.csv"
EQUIPMENT_FILE = PROJECT_ROOT / "data" / "sample_equipment.csv"
POINT_FILE = PROJECT_ROOT / "data" / "sample_points.csv"
ALARM_RULE_FILE = PROJECT_ROOT / "data" / "sample_alarm_rules.csv"
CURRENT_POINT_VALUE_FILE = PROJECT_ROOT / "data" / "sample_current_point_values.csv"
FACILITY_SCENARIO_FILE = PROJECT_ROOT / "data" / "sample_facility_scenarios.csv"
ALARM_CORRELATION_FILE = PROJECT_ROOT / "data" / "sample_alarm_correlations.csv"
ALARM_CORRELATION_MEMBER_FILE = (
    PROJECT_ROOT / "data" / "sample_alarm_correlation_members.csv"
)
INCIDENT_TIMELINE_FILE = PROJECT_ROOT / "data" / "sample_incident_timeline.csv"
SHIFT_TURNOVER_FILE = PROJECT_ROOT / "data" / "sample_shift_turnover.csv"
EQUIPMENT_OUT_OF_SERVICE_FILE = (
    PROJECT_ROOT / "data" / "sample_equipment_out_of_service.csv"
)
CORRECTIVE_ACTION_FILE = PROJECT_ROOT / "data" / "sample_corrective_actions.csv"
PROCEDURE_REFERENCE_FILE = PROJECT_ROOT / "data" / "sample_procedure_references.csv"
RELIABILITY_REPORT_FILE = PROJECT_ROOT / "data" / "sample_reliability_reports.csv"
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

POINT_METADATA_MIGRATIONS = {
    "protocol": "TEXT NOT NULL DEFAULT ''",
    "address": "TEXT NOT NULL DEFAULT ''",
}

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

FACILITY_SCENARIO_COLUMNS = (
    "id",
    "name",
    "status",
    "risk_level",
    "start_time",
    "end_time",
    "operating_mode",
    "incident_commander",
    "summary",
    "operator_goal",
)

ALARM_CORRELATION_COLUMNS = (
    "id",
    "scenario_id",
    "title",
    "status",
    "confidence",
    "window_start",
    "window_end",
    "primary_equipment",
    "impacted_equipment",
    "root_cause_hypothesis",
    "explanation",
    "recommended_focus",
)

ALARM_CORRELATION_MEMBER_COLUMNS = (
    "id",
    "correlation_id",
    "alarm_rule_id",
    "point_id",
    "equipment_id",
    "contribution",
    "evidence",
)

INCIDENT_TIMELINE_COLUMNS = (
    "id",
    "scenario_id",
    "event_timestamp",
    "event_type",
    "equipment_id",
    "title",
    "description",
    "source",
    "actor",
    "severity",
)

SHIFT_TURNOVER_COLUMNS = (
    "id",
    "shift_date",
    "shift_name",
    "outgoing_operator",
    "incoming_operator",
    "facility_state",
    "watch_items",
    "open_actions",
    "turnover_risk",
)

EQUIPMENT_OUT_OF_SERVICE_COLUMNS = (
    "id",
    "equipment_id",
    "status",
    "oos_type",
    "started_at",
    "expected_return_at",
    "returned_at",
    "reason",
    "operational_impact",
    "mitigation",
    "approved_by",
)

CORRECTIVE_ACTION_COLUMNS = (
    "id",
    "scenario_id",
    "equipment_id",
    "action_type",
    "priority",
    "status",
    "owner",
    "due_at",
    "completed_at",
    "description",
    "verification",
)

PROCEDURE_REFERENCE_COLUMNS = (
    "id",
    "scenario_id",
    "procedure_type",
    "procedure_code",
    "title",
    "applicability",
    "reference_step",
    "owner",
    "location",
)

RELIABILITY_REPORT_COLUMNS = (
    "id",
    "period_start",
    "period_end",
    "generated_at",
    "availability_percent",
    "critical_alarm_count",
    "warning_alarm_count",
    "mttr_minutes",
    "oos_hours",
    "corrective_actions_open",
    "corrective_actions_closed",
    "nuisance_alarm_count",
    "executive_summary",
)

BLANK_VALUES = {"", "null", "none", "n/a"}
DEFAULT_STALE_AFTER_SECONDS = 300


def current_timestamp():
    """Return a simple UTC timestamp for local sample ingestion."""
    return datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat(sep=" ")


def begin_transaction(connection):
    """Start an explicit SQLite transaction unless one is already active."""
    if not connection.in_transaction:
        connection.execute("BEGIN")


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
            protocol TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (equipment_id) REFERENCES equipment (equipment)
        )
        """
    )
    migrate_point_metadata_columns(connection)


def migrate_point_metadata_columns(connection):
    """Add optional static protocol/address metadata to older point tables."""
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(points)")
    }
    for column_name, column_definition in POINT_METADATA_MIGRATIONS.items():
        if column_name not in columns:
            connection.execute(
                f"""
                ALTER TABLE points
                ADD COLUMN {column_name} {column_definition}
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
            latest_sample_id TEXT NOT NULL DEFAULT '',
            value TEXT NOT NULL,
            unit TEXT NOT NULL DEFAULT '',
            quality TEXT NOT NULL,
            source TEXT NOT NULL,
            source_timestamp TEXT NOT NULL DEFAULT '',
            received_timestamp TEXT NOT NULL DEFAULT '',
            stale_after_seconds INTEGER NOT NULL DEFAULT 300,
            overridden INTEGER NOT NULL DEFAULT 0,
            out_of_service INTEGER NOT NULL DEFAULT 0,
            protocol TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            FOREIGN KEY (point_id) REFERENCES points (id),
            FOREIGN KEY (latest_sample_id) REFERENCES point_samples (id)
        )
        """
    )
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(current_point_values)")
    }
    migrations = {
        "latest_sample_id": "TEXT NOT NULL DEFAULT ''",
        "unit": "TEXT NOT NULL DEFAULT ''",
        "source_timestamp": "TEXT NOT NULL DEFAULT ''",
        "received_timestamp": "TEXT NOT NULL DEFAULT ''",
        "stale_after_seconds": "INTEGER NOT NULL DEFAULT 300",
        "overridden": "INTEGER NOT NULL DEFAULT 0",
        "out_of_service": "INTEGER NOT NULL DEFAULT 0",
        "protocol": "TEXT NOT NULL DEFAULT ''",
        "address": "TEXT NOT NULL DEFAULT ''",
    }
    for column_name, column_definition in migrations.items():
        if column_name not in columns:
            connection.execute(
                f"""
                ALTER TABLE current_point_values
                ADD COLUMN {column_name} {column_definition}
                """
            )


def create_point_sample_table(connection):
    """Create an append-only table for point samples."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS point_samples (
            id TEXT PRIMARY KEY,
            point_id TEXT NOT NULL,
            value TEXT NOT NULL,
            unit TEXT NOT NULL,
            quality TEXT NOT NULL,
            source_timestamp TEXT NOT NULL,
            received_timestamp TEXT NOT NULL,
            source TEXT NOT NULL,
            protocol TEXT NOT NULL,
            address TEXT NOT NULL,
            stale_after_seconds INTEGER NOT NULL,
            overridden INTEGER NOT NULL DEFAULT 0,
            out_of_service INTEGER NOT NULL DEFAULT 0,
            created_by TEXT NOT NULL,
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
            pending_started_at TEXT NOT NULL DEFAULT '',
            triggered_at TEXT NOT NULL,
            cleared_at TEXT NOT NULL,
            last_evaluated_at TEXT NOT NULL,
            evaluation_note TEXT NOT NULL,
            acknowledged INTEGER NOT NULL DEFAULT 0,
            acknowledged_at TEXT NOT NULL DEFAULT '',
            acknowledged_by TEXT NOT NULL DEFAULT '',
            rule_name_at_trigger TEXT NOT NULL DEFAULT '',
            rule_type_at_trigger TEXT NOT NULL DEFAULT '',
            operator_at_trigger TEXT NOT NULL DEFAULT '',
            threshold_value_at_trigger TEXT NOT NULL DEFAULT '',
            clear_value_at_trigger TEXT NOT NULL DEFAULT '',
            delay_seconds_at_trigger INTEGER NOT NULL DEFAULT 0,
            severity_at_trigger TEXT NOT NULL DEFAULT '',
            alarm_message_at_trigger TEXT NOT NULL DEFAULT '',
            triggering_sample_id TEXT NOT NULL DEFAULT '',
            triggering_value TEXT NOT NULL DEFAULT '',
            triggering_quality TEXT NOT NULL DEFAULT '',
            triggering_source_timestamp TEXT NOT NULL DEFAULT '',
            triggering_received_timestamp TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (rule_id) REFERENCES alarm_rules (id),
            FOREIGN KEY (point_id) REFERENCES points (id),
            FOREIGN KEY (equipment_id) REFERENCES equipment (equipment)
        )
        """
    )
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(generated_alarms)")
    }
    if "pending_started_at" not in columns:
        connection.execute(
            """
            ALTER TABLE generated_alarms
            ADD COLUMN pending_started_at TEXT NOT NULL DEFAULT ''
            """
        )
    if "acknowledged" not in columns:
        connection.execute(
            """
            ALTER TABLE generated_alarms
            ADD COLUMN acknowledged INTEGER NOT NULL DEFAULT 0
            """
        )
    if "acknowledged_at" not in columns:
        connection.execute(
            """
            ALTER TABLE generated_alarms
            ADD COLUMN acknowledged_at TEXT NOT NULL DEFAULT ''
            """
        )
    if "acknowledged_by" not in columns:
        connection.execute(
            """
            ALTER TABLE generated_alarms
            ADD COLUMN acknowledged_by TEXT NOT NULL DEFAULT ''
            """
        )
    snapshot_migrations = {
        "rule_name_at_trigger": "TEXT NOT NULL DEFAULT ''",
        "rule_type_at_trigger": "TEXT NOT NULL DEFAULT ''",
        "operator_at_trigger": "TEXT NOT NULL DEFAULT ''",
        "threshold_value_at_trigger": "TEXT NOT NULL DEFAULT ''",
        "clear_value_at_trigger": "TEXT NOT NULL DEFAULT ''",
        "delay_seconds_at_trigger": "INTEGER NOT NULL DEFAULT 0",
        "severity_at_trigger": "TEXT NOT NULL DEFAULT ''",
        "alarm_message_at_trigger": "TEXT NOT NULL DEFAULT ''",
        "triggering_sample_id": "TEXT NOT NULL DEFAULT ''",
        "triggering_value": "TEXT NOT NULL DEFAULT ''",
        "triggering_quality": "TEXT NOT NULL DEFAULT ''",
        "triggering_source_timestamp": "TEXT NOT NULL DEFAULT ''",
        "triggering_received_timestamp": "TEXT NOT NULL DEFAULT ''",
    }
    for column_name, column_definition in snapshot_migrations.items():
        if column_name not in columns:
            connection.execute(
                f"""
                ALTER TABLE generated_alarms
                ADD COLUMN {column_name} {column_definition}
                """
            )


def create_alarm_event_table(connection):
    """Create an append-only table for generated alarm lifecycle events."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS alarm_events (
            id TEXT PRIMARY KEY,
            generated_alarm_id TEXT,
            rule_id TEXT,
            point_id TEXT NOT NULL,
            equipment_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_timestamp TEXT NOT NULL,
            value TEXT NOT NULL,
            sample_id TEXT NOT NULL,
            previous_state TEXT NOT NULL,
            new_state TEXT NOT NULL,
            acknowledged_by TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL,
            details_json TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (generated_alarm_id) REFERENCES generated_alarms (id),
            FOREIGN KEY (rule_id) REFERENCES alarm_rules (id),
            FOREIGN KEY (point_id) REFERENCES points (id),
            FOREIGN KEY (equipment_id) REFERENCES equipment (equipment)
        )
        """
    )
    columns = {
        row[1]: row
        for row in connection.execute("PRAGMA table_info(alarm_events)")
    }
    generated_alarm_id_column = columns.get("generated_alarm_id")
    rule_id_column = columns.get("rule_id")
    if (
        (generated_alarm_id_column and generated_alarm_id_column[3])
        or (rule_id_column and rule_id_column[3])
    ):
        migrate_alarm_events_to_nullable_audit_links(connection)


def create_facility_scenario_table(connection):
    """Create table for seeded end-to-end facility scenarios."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS facility_scenarios (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            operating_mode TEXT NOT NULL,
            incident_commander TEXT NOT NULL,
            summary TEXT NOT NULL,
            operator_goal TEXT NOT NULL
        )
        """
    )


def create_alarm_correlation_table(connection):
    """Create table for explainable alarm correlation records."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS alarm_correlations (
            id TEXT PRIMARY KEY,
            scenario_id TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL,
            confidence TEXT NOT NULL,
            window_start TEXT NOT NULL,
            window_end TEXT NOT NULL,
            primary_equipment TEXT NOT NULL,
            impacted_equipment TEXT NOT NULL,
            root_cause_hypothesis TEXT NOT NULL,
            explanation TEXT NOT NULL,
            recommended_focus TEXT NOT NULL,
            FOREIGN KEY (scenario_id) REFERENCES facility_scenarios (id)
        )
        """
    )


def create_alarm_correlation_member_table(connection):
    """Create table for correlation evidence rows."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS alarm_correlation_members (
            id TEXT PRIMARY KEY,
            correlation_id TEXT NOT NULL,
            alarm_rule_id TEXT NOT NULL,
            point_id TEXT NOT NULL,
            equipment_id TEXT NOT NULL,
            contribution TEXT NOT NULL,
            evidence TEXT NOT NULL,
            FOREIGN KEY (correlation_id) REFERENCES alarm_correlations (id),
            FOREIGN KEY (alarm_rule_id) REFERENCES alarm_rules (id),
            FOREIGN KEY (point_id) REFERENCES points (id),
            FOREIGN KEY (equipment_id) REFERENCES equipment (equipment)
        )
        """
    )


def create_incident_timeline_table(connection):
    """Create table for seeded incident timeline events."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS incident_timeline (
            id TEXT PRIMARY KEY,
            scenario_id TEXT NOT NULL,
            event_timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            equipment_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            source TEXT NOT NULL,
            actor TEXT NOT NULL,
            severity TEXT NOT NULL,
            FOREIGN KEY (scenario_id) REFERENCES facility_scenarios (id)
        )
        """
    )


def create_shift_turnover_table(connection):
    """Create table for shift turnover records."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS shift_turnover (
            id TEXT PRIMARY KEY,
            shift_date TEXT NOT NULL,
            shift_name TEXT NOT NULL,
            outgoing_operator TEXT NOT NULL,
            incoming_operator TEXT NOT NULL,
            facility_state TEXT NOT NULL,
            watch_items TEXT NOT NULL,
            open_actions TEXT NOT NULL,
            turnover_risk TEXT NOT NULL
        )
        """
    )


def create_equipment_out_of_service_table(connection):
    """Create table for equipment out-of-service tracking."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS equipment_out_of_service (
            id TEXT PRIMARY KEY,
            equipment_id TEXT NOT NULL,
            status TEXT NOT NULL,
            oos_type TEXT NOT NULL,
            started_at TEXT NOT NULL,
            expected_return_at TEXT NOT NULL,
            returned_at TEXT NOT NULL,
            reason TEXT NOT NULL,
            operational_impact TEXT NOT NULL,
            mitigation TEXT NOT NULL,
            approved_by TEXT NOT NULL,
            FOREIGN KEY (equipment_id) REFERENCES equipment (equipment)
        )
        """
    )


def create_corrective_action_table(connection):
    """Create table for corrective action records."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS corrective_actions (
            id TEXT PRIMARY KEY,
            scenario_id TEXT NOT NULL,
            equipment_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL,
            owner TEXT NOT NULL,
            due_at TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            description TEXT NOT NULL,
            verification TEXT NOT NULL,
            FOREIGN KEY (scenario_id) REFERENCES facility_scenarios (id)
        )
        """
    )


def create_procedure_reference_table(connection):
    """Create table for MOP, SOP, and EOP references."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS procedure_references (
            id TEXT PRIMARY KEY,
            scenario_id TEXT NOT NULL,
            procedure_type TEXT NOT NULL,
            procedure_code TEXT NOT NULL,
            title TEXT NOT NULL,
            applicability TEXT NOT NULL,
            reference_step TEXT NOT NULL,
            owner TEXT NOT NULL,
            location TEXT NOT NULL,
            FOREIGN KEY (scenario_id) REFERENCES facility_scenarios (id)
        )
        """
    )


def create_reliability_report_table(connection):
    """Create table for management-level reliability report rows."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS reliability_reports (
            id TEXT PRIMARY KEY,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            availability_percent REAL NOT NULL,
            critical_alarm_count INTEGER NOT NULL,
            warning_alarm_count INTEGER NOT NULL,
            mttr_minutes INTEGER NOT NULL,
            oos_hours REAL NOT NULL,
            corrective_actions_open INTEGER NOT NULL,
            corrective_actions_closed INTEGER NOT NULL,
            nuisance_alarm_count INTEGER NOT NULL,
            executive_summary TEXT NOT NULL
        )
        """
    )


def create_operational_context_tables(connection):
    """Create all seeded operations context tables."""
    create_facility_scenario_table(connection)
    create_alarm_correlation_table(connection)
    create_alarm_correlation_member_table(connection)
    create_incident_timeline_table(connection)
    create_shift_turnover_table(connection)
    create_equipment_out_of_service_table(connection)
    create_corrective_action_table(connection)
    create_procedure_reference_table(connection)
    create_reliability_report_table(connection)


def migrate_alarm_events_to_nullable_audit_links(connection):
    """Allow audit events that are not tied to generated alarms or rules."""
    connection.execute("ALTER TABLE alarm_events RENAME TO alarm_events_old")
    connection.execute(
        """
        CREATE TABLE alarm_events (
            id TEXT PRIMARY KEY,
            generated_alarm_id TEXT,
            rule_id TEXT,
            point_id TEXT NOT NULL,
            equipment_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_timestamp TEXT NOT NULL,
            value TEXT NOT NULL,
            sample_id TEXT NOT NULL,
            previous_state TEXT NOT NULL,
            new_state TEXT NOT NULL,
            acknowledged_by TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL,
            details_json TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (generated_alarm_id) REFERENCES generated_alarms (id),
            FOREIGN KEY (rule_id) REFERENCES alarm_rules (id),
            FOREIGN KEY (point_id) REFERENCES points (id),
            FOREIGN KEY (equipment_id) REFERENCES equipment (equipment)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO alarm_events (
            id,
            generated_alarm_id,
            rule_id,
            point_id,
            equipment_id,
            event_type,
            event_timestamp,
            value,
            sample_id,
            previous_state,
            new_state,
            acknowledged_by,
            message,
            details_json
        )
        SELECT
            id,
            generated_alarm_id,
            rule_id,
            point_id,
            equipment_id,
            event_type,
            event_timestamp,
            value,
            sample_id,
            previous_state,
            new_state,
            acknowledged_by,
            message,
            details_json
        FROM alarm_events_old
        """
    )
    connection.execute("DROP TABLE alarm_events_old")


def read_csv_rows(csv_path, required_columns):
    """Read CSV records and validate required columns."""
    with open(csv_path, mode="r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        missing_columns = set(required_columns) - set(reader.fieldnames or [])
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"Missing required CSV columns: {missing}")

        rows = []
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(
                    "Unexpected extra CSV columns "
                    f"in {csv_path} row {row_number}: {row[None]}"
                )
            rows.append({column: row[column] for column in required_columns})

        return rows


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
        return "UNCERTAIN"

    normalized_value = value.strip().upper()
    if normalized_value == "UNKNOWN":
        return "UNCERTAIN"

    return normalized_value


def point_sample_id(current_point_value_id):
    """Create a stable seed sample id from the current value row id."""
    if is_blank_value(current_point_value_id):
        return f"PS-{uuid.uuid4().hex[:12]}"

    return f"PS-{current_point_value_id}"


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


def read_reliability_report_rows(csv_path):
    """Read reliability report records with numeric management metrics."""
    rows = read_csv_rows(csv_path, RELIABILITY_REPORT_COLUMNS)
    for row in rows:
        row["availability_percent"] = float(row["availability_percent"])
        row["critical_alarm_count"] = int(row["critical_alarm_count"])
        row["warning_alarm_count"] = int(row["warning_alarm_count"])
        row["mttr_minutes"] = int(row["mttr_minutes"])
        row["oos_hours"] = float(row["oos_hours"])
        row["corrective_actions_open"] = int(row["corrective_actions_open"])
        row["corrective_actions_closed"] = int(row["corrective_actions_closed"])
        row["nuisance_alarm_count"] = int(row["nuisance_alarm_count"])

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


def reset_legacy_alarms(db_path=DATABASE_FILE):
    """Create and clear the legacy sample alarm table."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        create_alarm_table(connection)
        connection.execute("DELETE FROM alarms")


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
    """Load seed current values by appending point samples, then projecting latest values."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    rows = read_current_point_value_rows(csv_path)

    with sqlite3.connect(db_path) as connection:
        create_point_sample_table(connection)
        create_current_point_value_table(connection)
        begin_transaction(connection)
        connection.execute("DELETE FROM current_point_values")
        connection.execute("DELETE FROM point_samples")

        units_by_point_id = {
            point_id: unit
            for point_id, unit in connection.execute("SELECT id, unit FROM points")
        }
        received_timestamp = current_timestamp()
        for row in rows:
            sample_id = point_sample_id(row["id"])
            source_timestamp = row["updated_at"] or received_timestamp
            unit = units_by_point_id.get(row["point_id"], "")
            connection.execute(
                """
                INSERT INTO point_samples (
                    id,
                    point_id,
                    value,
                    unit,
                    quality,
                    source_timestamp,
                    received_timestamp,
                    source,
                    protocol,
                    address,
                    stale_after_seconds,
                    overridden,
                    out_of_service,
                    created_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sample_id,
                    row["point_id"],
                    row["value"],
                    unit,
                    row["quality"],
                    source_timestamp,
                    received_timestamp,
                    row["source"],
                    "",
                    "",
                    DEFAULT_STALE_AFTER_SECONDS,
                    0,
                    0,
                    "loader",
                ),
            )
            connection.execute(
                """
                INSERT INTO current_point_values (
                    id,
                    point_id,
                    latest_sample_id,
                    value,
                    unit,
                    quality,
                    source,
                    source_timestamp,
                    received_timestamp,
                    stale_after_seconds,
                    overridden,
                    out_of_service,
                    protocol,
                    address,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["point_id"],
                    sample_id,
                    row["value"],
                    unit,
                    row["quality"],
                    row["source"],
                    source_timestamp,
                    received_timestamp,
                    DEFAULT_STALE_AFTER_SECONDS,
                    0,
                    0,
                    "",
                    "",
                    received_timestamp,
                ),
            )

    return len(rows)


def reset_generated_alarms(db_path=DATABASE_FILE):
    """Create and clear generated alarm state output records."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        create_generated_alarm_table(connection)
        create_alarm_event_table(connection)
        begin_transaction(connection)
        connection.execute("DELETE FROM alarm_events")
        connection.execute("DELETE FROM generated_alarms")


def replace_table_rows(connection, table_name, columns, rows):
    """Replace rows in a trusted table using trusted CSV column names."""
    column_sql = ", ".join(columns)
    placeholder_sql = ", ".join(f":{column}" for column in columns)
    connection.execute(f"DELETE FROM {table_name}")
    connection.executemany(
        f"""
        INSERT INTO {table_name} (
            {column_sql}
        )
        VALUES (
            {placeholder_sql}
        )
        """,
        rows,
    )


def load_operational_context_to_sqlite(
    facility_scenario_csv_path=FACILITY_SCENARIO_FILE,
    alarm_correlation_csv_path=ALARM_CORRELATION_FILE,
    alarm_correlation_member_csv_path=ALARM_CORRELATION_MEMBER_FILE,
    incident_timeline_csv_path=INCIDENT_TIMELINE_FILE,
    shift_turnover_csv_path=SHIFT_TURNOVER_FILE,
    equipment_out_of_service_csv_path=EQUIPMENT_OUT_OF_SERVICE_FILE,
    corrective_action_csv_path=CORRECTIVE_ACTION_FILE,
    procedure_reference_csv_path=PROCEDURE_REFERENCE_FILE,
    reliability_report_csv_path=RELIABILITY_REPORT_FILE,
    db_path=DATABASE_FILE,
):
    """Load deterministic operations context for the portfolio scenario."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    facility_scenario_rows = read_csv_rows(
        facility_scenario_csv_path,
        FACILITY_SCENARIO_COLUMNS,
    )
    alarm_correlation_rows = read_csv_rows(
        alarm_correlation_csv_path,
        ALARM_CORRELATION_COLUMNS,
    )
    alarm_correlation_member_rows = read_csv_rows(
        alarm_correlation_member_csv_path,
        ALARM_CORRELATION_MEMBER_COLUMNS,
    )
    incident_timeline_rows = read_csv_rows(
        incident_timeline_csv_path,
        INCIDENT_TIMELINE_COLUMNS,
    )
    shift_turnover_rows = read_csv_rows(
        shift_turnover_csv_path,
        SHIFT_TURNOVER_COLUMNS,
    )
    equipment_out_of_service_rows = read_csv_rows(
        equipment_out_of_service_csv_path,
        EQUIPMENT_OUT_OF_SERVICE_COLUMNS,
    )
    corrective_action_rows = read_csv_rows(
        corrective_action_csv_path,
        CORRECTIVE_ACTION_COLUMNS,
    )
    procedure_reference_rows = read_csv_rows(
        procedure_reference_csv_path,
        PROCEDURE_REFERENCE_COLUMNS,
    )
    reliability_report_rows = read_reliability_report_rows(
        reliability_report_csv_path,
    )

    with sqlite3.connect(db_path) as connection:
        create_operational_context_tables(connection)
        begin_transaction(connection)
        replace_table_rows(
            connection,
            "alarm_correlation_members",
            ALARM_CORRELATION_MEMBER_COLUMNS,
            alarm_correlation_member_rows,
        )
        replace_table_rows(
            connection,
            "alarm_correlations",
            ALARM_CORRELATION_COLUMNS,
            alarm_correlation_rows,
        )
        replace_table_rows(
            connection,
            "incident_timeline",
            INCIDENT_TIMELINE_COLUMNS,
            incident_timeline_rows,
        )
        replace_table_rows(
            connection,
            "shift_turnover",
            SHIFT_TURNOVER_COLUMNS,
            shift_turnover_rows,
        )
        replace_table_rows(
            connection,
            "equipment_out_of_service",
            EQUIPMENT_OUT_OF_SERVICE_COLUMNS,
            equipment_out_of_service_rows,
        )
        replace_table_rows(
            connection,
            "corrective_actions",
            CORRECTIVE_ACTION_COLUMNS,
            corrective_action_rows,
        )
        replace_table_rows(
            connection,
            "procedure_references",
            PROCEDURE_REFERENCE_COLUMNS,
            procedure_reference_rows,
        )
        replace_table_rows(
            connection,
            "reliability_reports",
            RELIABILITY_REPORT_COLUMNS,
            reliability_report_rows,
        )
        replace_table_rows(
            connection,
            "facility_scenarios",
            FACILITY_SCENARIO_COLUMNS,
            facility_scenario_rows,
        )

    return {
        "facility_scenario_records": len(facility_scenario_rows),
        "alarm_correlation_records": len(alarm_correlation_rows),
        "alarm_correlation_member_records": len(alarm_correlation_member_rows),
        "incident_timeline_records": len(incident_timeline_rows),
        "shift_turnover_records": len(shift_turnover_rows),
        "equipment_out_of_service_records": len(equipment_out_of_service_rows),
        "corrective_action_records": len(corrective_action_rows),
        "procedure_reference_records": len(procedure_reference_rows),
        "reliability_report_records": len(reliability_report_rows),
    }


def load_sample_data_to_sqlite(
    alarm_csv_path=ALARM_FILE,
    equipment_csv_path=EQUIPMENT_FILE,
    point_csv_path=POINT_FILE,
    alarm_rule_csv_path=ALARM_RULE_FILE,
    current_point_value_csv_path=CURRENT_POINT_VALUE_FILE,
    facility_scenario_csv_path=FACILITY_SCENARIO_FILE,
    alarm_correlation_csv_path=ALARM_CORRELATION_FILE,
    alarm_correlation_member_csv_path=ALARM_CORRELATION_MEMBER_FILE,
    incident_timeline_csv_path=INCIDENT_TIMELINE_FILE,
    shift_turnover_csv_path=SHIFT_TURNOVER_FILE,
    equipment_out_of_service_csv_path=EQUIPMENT_OUT_OF_SERVICE_FILE,
    corrective_action_csv_path=CORRECTIVE_ACTION_FILE,
    procedure_reference_csv_path=PROCEDURE_REFERENCE_FILE,
    reliability_report_csv_path=RELIABILITY_REPORT_FILE,
    db_path=DATABASE_FILE,
):
    """Load the legacy default Northstar fixture into SQLite."""
    northstar_context = resolve_registered_fixture(
        NORTHSTAR_FACILITY_ID,
        NORTHSTAR_FIXTURE_VERSION,
    )
    reset_legacy_alarms(db_path)
    equipment_count = load_equipment_to_sqlite(equipment_csv_path, db_path)
    point_count = load_points_to_sqlite(point_csv_path, db_path)
    alarm_rule_count = load_alarm_rules_to_sqlite(alarm_rule_csv_path, db_path)
    current_point_value_count = load_current_point_values_to_sqlite(
        current_point_value_csv_path,
        db_path,
    )
    operational_context_counts = load_operational_context_to_sqlite(
        facility_scenario_csv_path=facility_scenario_csv_path,
        alarm_correlation_csv_path=alarm_correlation_csv_path,
        alarm_correlation_member_csv_path=alarm_correlation_member_csv_path,
        incident_timeline_csv_path=incident_timeline_csv_path,
        shift_turnover_csv_path=shift_turnover_csv_path,
        equipment_out_of_service_csv_path=equipment_out_of_service_csv_path,
        corrective_action_csv_path=corrective_action_csv_path,
        procedure_reference_csv_path=procedure_reference_csv_path,
        reliability_report_csv_path=reliability_report_csv_path,
        db_path=db_path,
    )
    reset_generated_alarms(db_path)

    with sqlite3.connect(db_path) as connection:
        create_facility_topology_tables(connection)
        begin_transaction(connection)
        clear_topology_rows(connection)
        record_facility_environment(
            connection,
            facility_id=northstar_context["facility_id"],
            facility_name=northstar_context["facility_name"],
            fixture_version=northstar_context["fixture_version"],
            manifest_path=northstar_context["manifest_path"],
            loaded_at=current_timestamp(),
        )

    load_counts = {
        "alarm_records": 0,
        "equipment_records": equipment_count,
        "point_records": point_count,
        "alarm_rule_records": alarm_rule_count,
        "current_point_value_records": current_point_value_count,
        "point_sample_records": current_point_value_count,
        "facility_environment_records": 1,
    }
    load_counts.update(operational_context_counts)
    return load_counts


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
        create_alarm_table(connection)
        total_records = connection.execute(
            "SELECT COUNT(*) FROM alarms"
        ).fetchone()[0]

        return {
            "total_alarm_records": total_records,
            "severity_counts": get_group_counts(connection, "severity"),
            "source_counts": get_group_counts(connection, "source"),
            "equipment_counts": get_group_counts(connection, "equipment"),
        }


def get_generated_alarm_summary(db_path=DATABASE_FILE):
    """Return generated alarm counts from SQLite."""
    with sqlite3.connect(db_path) as connection:
        create_generated_alarm_table(connection)
        create_alarm_event_table(connection)
        total_records = connection.execute(
            "SELECT COUNT(*) FROM generated_alarms"
        ).fetchone()[0]
        event_records = connection.execute(
            "SELECT COUNT(*) FROM alarm_events"
        ).fetchone()[0]
        active_records = connection.execute(
            """
            SELECT COUNT(*)
            FROM generated_alarms
            WHERE state = 'ACTIVE'
            """
        ).fetchone()[0]
        pending_records = connection.execute(
            """
            SELECT COUNT(*)
            FROM generated_alarms
            WHERE state = 'PENDING'
            """
        ).fetchone()[0]
        cleared_records = connection.execute(
            """
            SELECT COUNT(*)
            FROM generated_alarms
            WHERE state = 'CLEARED'
            """
        ).fetchone()[0]

    return {
        "total_generated_alarm_records": total_records,
        "alarm_event_records": event_records,
        "active_generated_alarm_records": active_records,
        "pending_generated_alarm_records": pending_records,
        "cleared_generated_alarm_records": cleared_records,
    }


def print_count_section(title, counts):
    print(title)
    for name, count in counts.items():
        print(f"- {name}: {count}")


def print_verification_summary(
    generated_alarm_summary,
    equipment_record_count=None,
    point_record_count=None,
    alarm_rule_record_count=None,
    current_point_value_record_count=None,
    point_sample_record_count=None,
    operational_context_counts=None,
):
    print("Legacy alarm records loaded: 0")
    if equipment_record_count is not None:
        print(f"Equipment records loaded: {equipment_record_count}")
    if point_record_count is not None:
        print(f"Point records loaded: {point_record_count}")
    if alarm_rule_record_count is not None:
        print(f"Alarm rule records loaded: {alarm_rule_record_count}")
    if current_point_value_record_count is not None:
        print(f"Current point value records loaded: {current_point_value_record_count}")
    if point_sample_record_count is not None:
        print(f"Point sample records loaded: {point_sample_record_count}")
    if operational_context_counts:
        print("Operational context records loaded:")
        for label, count in operational_context_counts.items():
            print(f"- {label}: {count}")
    print(
        "Generated alarm records present: "
        f"{generated_alarm_summary['total_generated_alarm_records']}"
    )
    print(
        "Alarm event records present: "
        f"{generated_alarm_summary['alarm_event_records']}"
    )
    print(
        "Active generated alarm records: "
        f"{generated_alarm_summary['active_generated_alarm_records']}"
    )
    print(
        "Pending generated alarm records: "
        f"{generated_alarm_summary['pending_generated_alarm_records']}"
    )
    print(
        "Cleared generated alarm records: "
        f"{generated_alarm_summary['cleared_generated_alarm_records']}"
    )


def main():
    load_counts = load_sample_data_to_sqlite()
    generated_alarm_summary = get_generated_alarm_summary()
    print(f"SQLite database generated: {DATABASE_FILE}")
    print_verification_summary(
        generated_alarm_summary,
        equipment_record_count=load_counts["equipment_records"],
        point_record_count=load_counts["point_records"],
        alarm_rule_record_count=load_counts["alarm_rule_records"],
        current_point_value_record_count=load_counts["current_point_value_records"],
        point_sample_record_count=load_counts["point_sample_records"],
        operational_context_counts={
            "facility scenarios": load_counts["facility_scenario_records"],
            "alarm correlations": load_counts["alarm_correlation_records"],
            "correlation evidence rows": load_counts[
                "alarm_correlation_member_records"
            ],
            "incident timeline events": load_counts["incident_timeline_records"],
            "shift turnover notes": load_counts["shift_turnover_records"],
            "equipment OOS records": load_counts[
                "equipment_out_of_service_records"
            ],
            "corrective actions": load_counts["corrective_action_records"],
            "procedure references": load_counts["procedure_reference_records"],
            "reliability reports": load_counts["reliability_report_records"],
        },
    )


if __name__ == "__main__":
    main()
