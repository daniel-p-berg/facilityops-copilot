import json
import sqlite3
import uuid
from datetime import UTC
from datetime import datetime
from pathlib import Path

from backend.domain.alarm_evaluator import active_generated_alarm_note
from backend.domain.alarm_evaluator import active_generated_alarm_should_clear
from backend.domain.alarm_evaluator import ANALOG_OPERATORS
from backend.domain.alarm_evaluator import DEFAULT_STALE_AFTER_SECONDS
from backend.domain.alarm_evaluator import evaluate_alarm_rule
from backend.domain.alarm_evaluator import FALSE_VALUES
from backend.domain.alarm_evaluator import has_value
from backend.domain.alarm_evaluator import MATCH_OPERATORS
from backend.domain.alarm_evaluator import normalize_text
from backend.domain.alarm_evaluator import pending_delay_has_elapsed
from backend.domain.alarm_evaluator import parse_delay_seconds
from backend.domain.alarm_evaluator import TRUE_VALUES


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_FILE = PROJECT_ROOT / "db" / "facilityops.sqlite3"
DATABASE_DISPLAY_PATH = Path("db") / "facilityops.sqlite3"
LOADER_COMMAND = "python3 analysis/load_alarm_db.py"

GENERATED_ALARM_COUNT_COLUMNS = {"severity", "state", "equipment_id"}
ALLOWED_ALARM_RULE_TYPES = {"analog_limit", "boolean_state", "enum_match"}
ALARM_RULE_OPERATORS_BY_TYPE = {
    "analog_limit": ANALOG_OPERATORS,
    "boolean_state": MATCH_OPERATORS,
    "enum_match": MATCH_OPERATORS,
}
ALLOWED_ALARM_RULE_SEVERITIES = {"Critical", "Warning", "Info"}
EDITABLE_ALARM_RULE_FIELDS = {
    "threshold_value",
    "clear_value",
    "delay_seconds",
    "severity",
    "alarm_message",
    "enabled",
}
ALARM_RULE_AUDIT_FIELDS = (
    "threshold_value",
    "clear_value",
    "delay_seconds",
    "severity",
    "alarm_message",
    "enabled",
)
ALARM_RULE_CREATED_DETAIL_FIELDS = (
    "id",
    "point_id",
    "rule_name",
    "rule_type",
    "operator",
    "threshold_value",
    "clear_value",
    "delay_seconds",
    "severity",
    "alarm_message",
    "enabled",
)
ALLOWED_QUALITIES = {"GOOD", "UNCERTAIN", "BAD", "STALE"}
ALLOWED_CURRENT_VALUE_SOURCES = {
    "SIMULATED",
    "BMS",
    "EPMS",
    "PLC",
    "DCIM",
    "MANUAL",
    "SCENARIO",
}
ALARM_SCENARIOS = {
    "trigger-ups-high-load": {
        "label": "Trigger UPS High Load",
        "description": "Set UPS-A output kW above the high-load rule threshold.",
        "updates": [
            {
                "point_id": "UPS-A_OUTPUT_KW",
                "value": "245",
                "quality": "GOOD",
                "source": "SCENARIO",
            },
        ],
    },
    "normalize-ups-high-load": {
        "label": "Normalize UPS High Load",
        "description": "Set UPS-A output kW back below the high-load clear value.",
        "updates": [
            {
                "point_id": "UPS-A_OUTPUT_KW",
                "value": "185",
                "quality": "GOOD",
                "source": "SCENARIO",
            },
        ],
    },
    "trigger-crah-high-supply-temp": {
        "label": "Trigger CRAH High Supply Temp",
        "description": "Set CRAC-2 supply air temperature above the high-temperature rule threshold.",
        "updates": [
            {
                "point_id": "CRAC-2_SUPPLY_AIR_TEMP",
                "value": "72",
                "quality": "GOOD",
                "source": "SCENARIO",
            },
        ],
    },
    "normalize-crah-high-supply-temp": {
        "label": "Normalize CRAH High Supply Temp",
        "description": "Set CRAC-2 supply air temperature back inside the normal range.",
        "updates": [
            {
                "point_id": "CRAC-2_SUPPLY_AIR_TEMP",
                "value": "59.8",
                "quality": "GOOD",
                "source": "SCENARIO",
            },
        ],
    },
    "trigger-generator-low-fuel": {
        "label": "Trigger Generator Low Fuel",
        "description": "Set GEN-1 fuel level below the low-fuel rule threshold.",
        "updates": [
            {
                "point_id": "GEN-1_FUEL_LEVEL",
                "value": "30",
                "quality": "GOOD",
                "source": "SCENARIO",
            },
        ],
    },
    "normalize-generator-low-fuel": {
        "label": "Normalize Generator Low Fuel",
        "description": "Set GEN-1 fuel level back above the low-fuel clear value.",
        "updates": [
            {
                "point_id": "GEN-1_FUEL_LEVEL",
                "value": "82",
                "quality": "GOOD",
                "source": "SCENARIO",
            },
        ],
    },
}


def current_timestamp():
    """Return a simple UTC timestamp for generated alarm state."""
    return datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat(sep=" ")


def begin_transaction(connection):
    """Start an explicit SQLite transaction unless one is already active."""
    if not connection.in_transaction:
        connection.execute("BEGIN")


def get_generated_alarm_count_by_column(connection, column_name, state=None):
    """Return generated alarm counts grouped by a trusted column."""
    if column_name not in GENERATED_ALARM_COUNT_COLUMNS:
        raise ValueError(f"Unsupported count column: {column_name}")

    where_clause = ""
    parameters = ()
    if state is not None:
        where_clause = "WHERE state = ?"
        parameters = (state,)

    cursor = connection.execute(
        f"""
        SELECT {column_name}, COUNT(*) AS alarm_count
        FROM generated_alarms
        {where_clause}
        GROUP BY {column_name}
        ORDER BY alarm_count DESC, {column_name} ASC
        """,
        parameters,
    )
    return {row[0]: row[1] for row in cursor.fetchall()}


def get_generated_alarm_count(connection, state=None, severity=None, acknowledged=None):
    """Return generated alarm count filtered by state and severity."""
    where_clauses = []
    parameters = []
    if state is not None:
        where_clauses.append("state = ?")
        parameters.append(state)
    if severity is not None:
        where_clauses.append("severity = ?")
        parameters.append(severity)
    if acknowledged is not None:
        where_clauses.append("acknowledged = ?")
        parameters.append(1 if acknowledged else 0)

    where_sql = ""
    if where_clauses:
        where_sql = f"WHERE {' AND '.join(where_clauses)}"

    return connection.execute(
        f"""
        SELECT COUNT(*)
        FROM generated_alarms
        {where_sql}
        """,
        parameters,
    ).fetchone()[0]


def get_alarm_summary(db_path=DATABASE_FILE):
    """Read generated alarm summary data from SQLite."""
    with sqlite3.connect(db_path) as connection:
        ensure_generated_alarm_table(connection)

        return {
            "total_generated_alarm_count": get_generated_alarm_count(connection),
            "active_generated_alarm_count": get_generated_alarm_count(
                connection,
                state="ACTIVE",
            ),
            "active_unacknowledged_generated_alarm_count": get_generated_alarm_count(
                connection,
                state="ACTIVE",
                acknowledged=False,
            ),
            "active_acknowledged_generated_alarm_count": get_generated_alarm_count(
                connection,
                state="ACTIVE",
                acknowledged=True,
            ),
            "pending_generated_alarm_count": get_generated_alarm_count(
                connection,
                state="PENDING",
            ),
            "active_critical_generated_alarm_count": get_generated_alarm_count(
                connection,
                state="ACTIVE",
                severity="Critical",
            ),
            "active_warning_generated_alarm_count": get_generated_alarm_count(
                connection,
                state="ACTIVE",
                severity="Warning",
            ),
            "active_info_generated_alarm_count": get_generated_alarm_count(
                connection,
                state="ACTIVE",
                severity="Info",
            ),
            "cleared_generated_alarm_count": get_generated_alarm_count(
                connection,
                state="CLEARED",
            ),
            "active_generated_alarm_severity_counts": get_generated_alarm_count_by_column(
                connection,
                "severity",
                state="ACTIVE",
            ),
            "generated_alarm_state_counts": get_generated_alarm_count_by_column(
                connection,
                "state",
            ),
            "active_generated_alarm_equipment_counts": get_generated_alarm_count_by_column(
                connection,
                "equipment_id",
                state="ACTIVE",
            ),
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


def ensure_generated_alarm_table(connection):
    """Create generated alarm state table if the loader has not run yet."""
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


def ensure_alarm_event_table(connection):
    """Create generated alarm event audit table if the loader has not run yet."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS alarm_events (
            id TEXT PRIMARY KEY,
            generated_alarm_id TEXT,
            rule_id TEXT NOT NULL,
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
    if generated_alarm_id_column and generated_alarm_id_column[3]:
        migrate_alarm_events_to_nullable_generated_alarm_id(connection)


def migrate_alarm_events_to_nullable_generated_alarm_id(connection):
    """Allow rule audit events that are not tied to a generated alarm row."""
    connection.execute("ALTER TABLE alarm_events RENAME TO alarm_events_old")
    connection.execute(
        """
        CREATE TABLE alarm_events (
            id TEXT PRIMARY KEY,
            generated_alarm_id TEXT,
            rule_id TEXT NOT NULL,
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


def ensure_current_point_value_table(connection):
    """Create current point value table if the loader has not run yet."""
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


def ensure_point_sample_table(connection):
    """Create append-only point sample table if the loader has not run yet."""
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


def current_point_value_id(point_id):
    """Create a stable current point value id for a point."""
    return f"CPV-{point_id}"


def point_sample_id(point_id):
    """Create a generated point sample id."""
    return f"PS-{point_id}-{uuid.uuid4().hex[:12]}"


def normalize_quality(value):
    """Normalize and validate current point value quality."""
    normalized_value = normalize_text(value).upper()
    if normalized_value == "UNKNOWN":
        normalized_value = "UNCERTAIN"
    if normalized_value not in ALLOWED_QUALITIES:
        allowed_values = ", ".join(sorted(ALLOWED_QUALITIES))
        raise ValueError(f"quality must be one of: {allowed_values}, UNKNOWN")

    return normalized_value


def normalize_current_value_source(value):
    """Normalize and validate current point value source."""
    normalized_value = normalize_text(value).upper()
    if normalized_value not in ALLOWED_CURRENT_VALUE_SOURCES:
        allowed_values = ", ".join(sorted(ALLOWED_CURRENT_VALUE_SOURCES))
        raise ValueError(f"source must be one of: {allowed_values}")

    return normalized_value


def normalize_optional_catalog_text(value):
    """Normalize optional catalog values to the same blank style as the loader."""
    if not has_value(value):
        return ""

    return normalize_text(value)


def normalize_alarm_rule_severity(value):
    """Normalize and validate an editable alarm rule severity."""
    normalized_value = normalize_text(value).lower()
    severity_by_name = {
        severity.lower(): severity
        for severity in ALLOWED_ALARM_RULE_SEVERITIES
    }
    if normalized_value not in severity_by_name:
        allowed_values = ", ".join(sorted(ALLOWED_ALARM_RULE_SEVERITIES))
        raise ValueError(f"severity must be one of: {allowed_values}")

    return severity_by_name[normalized_value]


def normalize_alarm_rule_type(value):
    """Normalize and validate an alarm rule type."""
    normalized_value = normalize_text(value).lower()
    if normalized_value not in ALLOWED_ALARM_RULE_TYPES:
        allowed_values = ", ".join(sorted(ALLOWED_ALARM_RULE_TYPES))
        raise ValueError(f"rule_type must be one of: {allowed_values}")

    return normalized_value


def validate_alarm_rule_operator(rule_type, operator):
    """Validate that an operator is supported for an alarm rule type."""
    normalized_operator = normalize_text(operator)
    allowed_operators = ALARM_RULE_OPERATORS_BY_TYPE[rule_type]
    if normalized_operator not in allowed_operators:
        allowed_values = ", ".join(sorted(allowed_operators))
        raise ValueError(f"operator for {rule_type} must be one of: {allowed_values}")

    return normalized_operator


def parse_enabled_flag(value):
    """Parse an enabled flag into a predictable SQLite integer."""
    if isinstance(value, bool):
        return 1 if value else 0
    if value is None:
        raise ValueError("enabled must be one of: 1, 0, true, false, yes, no")

    normalized_value = normalize_text(value).lower()
    if normalized_value in {"1", "true", "yes"}:
        return 1
    if normalized_value in {"0", "false", "no"}:
        return 0

    raise ValueError("enabled must be one of: 1, 0, true, false, yes, no")


def parse_non_negative_delay_seconds(value):
    """Parse editable delay_seconds into a non-negative integer."""
    if isinstance(value, bool):
        raise ValueError("delay_seconds must be a non-negative integer")
    if not has_value(value):
        return 0
    if isinstance(value, float) and not value.is_integer():
        raise ValueError("delay_seconds must be a non-negative integer")

    try:
        delay_seconds = int(value)
    except (TypeError, ValueError):
        raise ValueError("delay_seconds must be a non-negative integer") from None

    if delay_seconds < 0:
        raise ValueError("delay_seconds must be a non-negative integer")

    return delay_seconds


def parse_stale_after_seconds(value):
    """Parse stale_after_seconds, using the project default when blank."""
    if not has_value(value):
        return DEFAULT_STALE_AFTER_SECONDS

    return parse_non_negative_delay_seconds(value)


def parse_boolean_flag(value, field_name):
    """Parse boolean-like API fields into SQLite integers."""
    if isinstance(value, bool):
        return 1 if value else 0
    if value is None:
        return 0

    normalized_value = normalize_text(value).lower()
    if not normalized_value:
        return 0
    if normalized_value in TRUE_VALUES:
        return 1
    if normalized_value in FALSE_VALUES:
        return 0

    raise ValueError(f"{field_name} must be a boolean value")


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
                alarm_rules.delay_seconds,
                alarm_rules.updated_at
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
                "updated_at": updated_at,
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
                updated_at,
            ) in cursor.fetchall()
        ]


def get_alarm_rule(rule_id, db_path=DATABASE_FILE):
    """Return one enriched alarm rule catalog record by id."""
    for rule in get_alarm_rule_catalog(db_path):
        if rule["id"] == rule_id:
            return rule

    return None


def get_alarm_rule_audit_record(connection, rule_id):
    """Return rule facts needed to write a local audit event."""
    cursor = connection.execute(
        """
        SELECT
            alarm_rules.id,
            alarm_rules.point_id,
            COALESCE(points.equipment_id, '') AS equipment_id,
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
        WHERE alarm_rules.id = ?
        """,
        (rule_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    (
        audit_rule_id,
        point_id,
        equipment_id,
        rule_name,
        rule_type,
        operator,
        threshold_value,
        clear_value,
        severity,
        alarm_message,
        enabled,
        delay_seconds,
    ) = row

    return {
        "id": audit_rule_id,
        "point_id": point_id,
        "equipment_id": equipment_id,
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


def alarm_rule_created_details(rule):
    """Return compact RULE_CREATED event details."""
    return {
        "created_rule": {
            field: rule[field]
            for field in ALARM_RULE_CREATED_DETAIL_FIELDS
        }
    }


def alarm_rule_updated_details(old_rule, new_rule, changed_fields):
    """Return compact RULE_UPDATED event details."""
    return {
        "changed_fields": changed_fields,
        "old_values": {
            field: old_rule[field]
            for field in changed_fields
        },
        "new_values": {
            field: new_rule[field]
            for field in changed_fields
        },
    }


def insert_alarm_rule_audit_event(
    connection,
    rule,
    event_type,
    event_timestamp,
    message,
    details,
    actor="local-operator",
):
    """Append an alarm rule catalog audit event."""
    insert_alarm_event(
        connection,
        generated_alarm_id=None,
        rule_id=rule["id"],
        point_id=rule["point_id"],
        equipment_id=rule["equipment_id"],
        event_type=event_type,
        event_timestamp=event_timestamp,
        acknowledged_by=actor,
        message=message,
        details=details,
    )


def require_alarm_rule_fields(payload, required_fields):
    """Validate that a request body includes non-blank required rule fields."""
    missing_fields = [
        field
        for field in required_fields
        if field not in payload or not has_value(payload[field])
    ]
    if missing_fields:
        field_list = ", ".join(missing_fields)
        raise ValueError(f"Missing required alarm rule field(s): {field_list}")


def create_alarm_rule(payload, db_path=DATABASE_FILE):
    """Create an alarm rule for an existing point and return its enriched record."""
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("alarm rule create body must be an object")

    required_fields = {
        "id",
        "point_id",
        "rule_name",
        "rule_type",
        "operator",
        "severity",
        "alarm_message",
        "enabled",
    }
    allowed_fields = required_fields | {
        "threshold_value",
        "clear_value",
        "delay_seconds",
    }
    unsupported_fields = sorted(set(payload) - allowed_fields)
    if unsupported_fields:
        field_list = ", ".join(unsupported_fields)
        raise ValueError(f"Unsupported alarm rule field(s): {field_list}")
    require_alarm_rule_fields(payload, required_fields)

    rule_id = normalize_text(payload["id"])
    point_id = normalize_text(payload["point_id"])
    rule_name = normalize_text(payload["rule_name"])
    rule_type = normalize_alarm_rule_type(payload["rule_type"])
    operator = validate_alarm_rule_operator(rule_type, payload["operator"])
    severity = normalize_alarm_rule_severity(payload["severity"])
    alarm_message = normalize_text(payload["alarm_message"])
    enabled = parse_enabled_flag(payload["enabled"])
    threshold_value = normalize_optional_catalog_text(payload.get("threshold_value", ""))
    clear_value = normalize_optional_catalog_text(payload.get("clear_value", ""))
    delay_seconds = parse_non_negative_delay_seconds(payload.get("delay_seconds", 0))
    timestamp = current_timestamp()

    with sqlite3.connect(db_path) as connection:
        ensure_alarm_event_table(connection)
        with connection:
            begin_transaction(connection)
            existing_rule = connection.execute(
                """
                SELECT 1
                FROM alarm_rules
                WHERE id = ?
                """,
                (rule_id,),
            ).fetchone()
            if existing_rule:
                raise ValueError(f"Alarm rule already exists: {rule_id}")
            if not point_exists(connection, point_id):
                raise LookupError(f"Point not found: {point_id}")

            connection.execute(
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule_id,
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
                    timestamp,
                    timestamp,
                ),
            )
            created_rule = get_alarm_rule_audit_record(connection, rule_id)
            insert_alarm_rule_audit_event(
                connection,
                created_rule,
                "RULE_CREATED",
                timestamp,
                f"Alarm rule created: {rule_name}",
                alarm_rule_created_details(created_rule),
            )

    return get_alarm_rule(rule_id, db_path)


def update_alarm_rule(rule_id, updates, db_path=DATABASE_FILE):
    """Update editable fields for an existing alarm rule."""
    if updates is None:
        updates = {}
    if not isinstance(updates, dict):
        raise ValueError("alarm rule update body must be an object")

    unsupported_fields = sorted(set(updates) - EDITABLE_ALARM_RULE_FIELDS)
    if unsupported_fields:
        field_list = ", ".join(unsupported_fields)
        raise ValueError(f"Unsupported alarm rule field(s): {field_list}")

    normalized_updates = {}
    if "threshold_value" in updates:
        normalized_updates["threshold_value"] = normalize_optional_catalog_text(
            updates["threshold_value"],
        )
    if "clear_value" in updates:
        normalized_updates["clear_value"] = normalize_optional_catalog_text(
            updates["clear_value"],
        )
    if "delay_seconds" in updates:
        normalized_updates["delay_seconds"] = parse_non_negative_delay_seconds(
            updates["delay_seconds"],
        )
    if "severity" in updates:
        normalized_updates["severity"] = normalize_alarm_rule_severity(updates["severity"])
    if "alarm_message" in updates:
        normalized_updates["alarm_message"] = normalize_text(updates["alarm_message"])
    if "enabled" in updates:
        normalized_updates["enabled"] = bool(parse_enabled_flag(updates["enabled"]))

    with sqlite3.connect(db_path) as connection:
        ensure_alarm_event_table(connection)
        with connection:
            begin_transaction(connection)
            old_rule = get_alarm_rule_audit_record(connection, rule_id)
            if not old_rule:
                raise LookupError(f"Alarm rule not found: {rule_id}")

            changed_fields = [
                field
                for field in ALARM_RULE_AUDIT_FIELDS
                if field in normalized_updates
                and old_rule[field] != normalized_updates[field]
            ]

            if changed_fields:
                assignments = [
                    f"{field} = ?"
                    for field in changed_fields
                ]
                parameters = [
                    int(normalized_updates[field])
                    if field == "enabled"
                    else normalized_updates[field]
                    for field in changed_fields
                ]
                timestamp = current_timestamp()
                assignments.append("updated_at = ?")
                parameters.append(timestamp)
                parameters.append(rule_id)
                connection.execute(
                    f"""
                    UPDATE alarm_rules
                    SET {", ".join(assignments)}
                    WHERE id = ?
                    """,
                    parameters,
                )
                new_rule = get_alarm_rule_audit_record(connection, rule_id)
                insert_alarm_rule_audit_event(
                    connection,
                    new_rule,
                    "RULE_UPDATED",
                    timestamp,
                    f"Alarm rule updated: {new_rule['rule_name']}",
                    alarm_rule_updated_details(old_rule, new_rule, changed_fields),
                )

    return get_alarm_rule(rule_id, db_path)


def get_current_point_values(db_path=DATABASE_FILE):
    """Return current point values with point and equipment context."""
    with sqlite3.connect(db_path) as connection:
        ensure_point_sample_table(connection)
        ensure_current_point_value_table(connection)
        cursor = connection.execute(
            """
            SELECT
                current_point_values.id,
                current_point_values.point_id,
                current_point_values.latest_sample_id,
                points.point_name,
                points.display_name,
                points.equipment_id,
                COALESCE(equipment.equipment_type, 'Unknown') AS equipment_type,
                COALESCE(equipment.location, 'Unknown') AS location,
                points.point_type,
                points.data_type,
                COALESCE(NULLIF(current_point_values.unit, ''), points.unit) AS unit,
                current_point_values.value,
                current_point_values.quality,
                current_point_values.source,
                current_point_values.source_timestamp,
                current_point_values.received_timestamp,
                current_point_values.stale_after_seconds,
                current_point_values.overridden,
                current_point_values.out_of_service,
                current_point_values.protocol,
                current_point_values.address,
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
                "latest_sample_id": latest_sample_id,
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
                "source_timestamp": source_timestamp,
                "received_timestamp": received_timestamp,
                "stale_after_seconds": stale_after_seconds,
                "overridden": bool(overridden),
                "out_of_service": bool(out_of_service),
                "protocol": protocol,
                "address": address,
                "updated_at": updated_at,
            }
            for (
                value_id,
                point_id,
                latest_sample_id,
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
                source_timestamp,
                received_timestamp,
                stale_after_seconds,
                overridden,
                out_of_service,
                protocol,
                address,
                updated_at,
            ) in cursor.fetchall()
        ]


def get_current_point_value(point_id, db_path=DATABASE_FILE):
    """Return one current point value with point and equipment context."""
    with sqlite3.connect(db_path) as connection:
        ensure_point_sample_table(connection)
        ensure_current_point_value_table(connection)
        return get_current_point_value_with_connection(connection, point_id)


def current_point_value_from_row(row):
    """Convert one current point value row into the API dictionary shape."""
    if not row:
        return None

    (
        value_id,
        current_point_id,
        latest_sample_id,
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
        source_timestamp,
        received_timestamp,
        stale_after_seconds,
        overridden,
        out_of_service,
        protocol,
        address,
        updated_at,
    ) = row

    return {
        "id": value_id,
        "point_id": current_point_id,
        "latest_sample_id": latest_sample_id,
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
        "source_timestamp": source_timestamp,
        "received_timestamp": received_timestamp,
        "stale_after_seconds": stale_after_seconds,
        "overridden": bool(overridden),
        "out_of_service": bool(out_of_service),
        "protocol": protocol,
        "address": address,
        "updated_at": updated_at,
    }


def get_current_point_value_with_connection(connection, point_id):
    """Return one current point value using an existing connection."""
    cursor = connection.execute(
        """
        SELECT
            current_point_values.id,
            current_point_values.point_id,
            current_point_values.latest_sample_id,
            points.point_name,
            points.display_name,
            points.equipment_id,
            COALESCE(equipment.equipment_type, 'Unknown') AS equipment_type,
            COALESCE(equipment.location, 'Unknown') AS location,
            points.point_type,
            points.data_type,
            COALESCE(NULLIF(current_point_values.unit, ''), points.unit) AS unit,
            current_point_values.value,
            current_point_values.quality,
            current_point_values.source,
            current_point_values.source_timestamp,
            current_point_values.received_timestamp,
            current_point_values.stale_after_seconds,
            current_point_values.overridden,
            current_point_values.out_of_service,
            current_point_values.protocol,
            current_point_values.address,
            current_point_values.updated_at
        FROM current_point_values
        LEFT JOIN points
            ON current_point_values.point_id = points.id
        LEFT JOIN equipment
            ON points.equipment_id = equipment.equipment
        WHERE current_point_values.point_id = ?
        """,
        (point_id,),
    )
    return current_point_value_from_row(cursor.fetchone())


def point_exists(connection, point_id):
    """Return True when a point id exists in the point dictionary."""
    row = connection.execute(
        """
        SELECT 1
        FROM points
        WHERE id = ?
        """,
        (point_id,),
    ).fetchone()
    return row is not None


def get_point_unit(connection, point_id):
    """Return the configured point unit for an existing point."""
    row = connection.execute(
        """
        SELECT unit
        FROM points
        WHERE id = ?
        """,
        (point_id,),
    ).fetchone()
    if row is None:
        raise LookupError(f"Point not found: {point_id}")

    return row[0]


def upsert_current_point_value_projection(
    connection,
    point_id,
    sample_id,
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
):
    """Update or create the latest-value projection for one point sample."""
    existing_row = connection.execute(
        """
        SELECT id
        FROM current_point_values
        WHERE point_id = ?
        """,
        (point_id,),
    ).fetchone()

    if existing_row:
        connection.execute(
            """
            UPDATE current_point_values
            SET latest_sample_id = ?,
                value = ?,
                unit = ?,
                quality = ?,
                source = ?,
                source_timestamp = ?,
                received_timestamp = ?,
                stale_after_seconds = ?,
                overridden = ?,
                out_of_service = ?,
                protocol = ?,
                address = ?,
                updated_at = ?
            WHERE point_id = ?
            """,
            (
                sample_id,
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
                received_timestamp,
                point_id,
            ),
        )
        return

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
            current_point_value_id(point_id),
            point_id,
            sample_id,
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
            received_timestamp,
        ),
    )


def ingest_point_sample_with_connection(
    connection,
    point_id,
    value,
    quality="GOOD",
    source="MANUAL",
    unit=None,
    source_timestamp=None,
    received_timestamp=None,
    protocol="",
    address="",
    stale_after_seconds=DEFAULT_STALE_AFTER_SECONDS,
    overridden=False,
    out_of_service=False,
    created_by="local-operator",
):
    """Append a point sample and project it using an existing transaction."""
    normalized_value = normalize_text(value)
    normalized_quality = normalize_quality(quality)
    normalized_source = normalize_current_value_source(source)
    normalized_received_timestamp = normalize_text(received_timestamp) or current_timestamp()
    normalized_source_timestamp = (
        normalize_text(source_timestamp)
        or normalized_received_timestamp
    )
    normalized_protocol = normalize_text(protocol)
    normalized_address = normalize_text(address)
    normalized_stale_after_seconds = parse_stale_after_seconds(stale_after_seconds)
    normalized_overridden = parse_boolean_flag(overridden, "overridden")
    normalized_out_of_service = parse_boolean_flag(out_of_service, "out_of_service")
    normalized_created_by = normalize_text(created_by) or "local-operator"
    sample_id = point_sample_id(point_id)

    point_unit = get_point_unit(connection, point_id)
    normalized_unit = normalize_text(unit)
    if not has_value(normalized_unit):
        normalized_unit = point_unit

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
            point_id,
            normalized_value,
            normalized_unit,
            normalized_quality,
            normalized_source_timestamp,
            normalized_received_timestamp,
            normalized_source,
            normalized_protocol,
            normalized_address,
            normalized_stale_after_seconds,
            normalized_overridden,
            normalized_out_of_service,
            normalized_created_by,
        ),
    )

    upsert_current_point_value_projection(
        connection,
        point_id,
        sample_id,
        normalized_value,
        normalized_unit,
        normalized_quality,
        normalized_source,
        normalized_source_timestamp,
        normalized_received_timestamp,
        normalized_stale_after_seconds,
        normalized_overridden,
        normalized_out_of_service,
        normalized_protocol,
        normalized_address,
    )

    return get_current_point_value_with_connection(connection, point_id)


def ingest_point_sample(
    point_id,
    value,
    quality="GOOD",
    source="MANUAL",
    unit=None,
    source_timestamp=None,
    received_timestamp=None,
    protocol="",
    address="",
    stale_after_seconds=DEFAULT_STALE_AFTER_SECONDS,
    overridden=False,
    out_of_service=False,
    created_by="local-operator",
    db_path=DATABASE_FILE,
):
    """Append a point sample and update the projection in one transaction."""
    with sqlite3.connect(db_path) as connection:
        ensure_point_sample_table(connection)
        ensure_current_point_value_table(connection)
        with connection:
            begin_transaction(connection)
            return ingest_point_sample_with_connection(
                connection,
                point_id,
                value,
                quality=quality,
                source=source,
                unit=unit,
                source_timestamp=source_timestamp,
                received_timestamp=received_timestamp,
                protocol=protocol,
                address=address,
                stale_after_seconds=stale_after_seconds,
                overridden=overridden,
                out_of_service=out_of_service,
                created_by=created_by,
            )


def update_current_point_value(
    point_id,
    value,
    quality="GOOD",
    source="MANUAL",
    db_path=DATABASE_FILE,
    source_timestamp=None,
    received_timestamp=None,
    protocol="",
    address="",
    stale_after_seconds=DEFAULT_STALE_AFTER_SECONDS,
    overridden=False,
    out_of_service=False,
    created_by="local-operator",
):
    """Create a point sample and project it as the latest current value."""
    return ingest_point_sample(
        point_id,
        value,
        quality=quality,
        source=source,
        source_timestamp=source_timestamp,
        received_timestamp=received_timestamp,
        protocol=protocol,
        address=address,
        stale_after_seconds=stale_after_seconds,
        overridden=overridden,
        out_of_service=out_of_service,
        created_by=created_by,
        db_path=db_path,
    )


def get_points_by_id(connection, point_ids):
    """Return point context keyed by point id."""
    if not point_ids:
        return {}

    placeholders = ", ".join("?" for _point_id in point_ids)
    cursor = connection.execute(
        f"""
        SELECT
            points.id,
            points.point_name,
            points.display_name,
            points.equipment_id
        FROM points
        WHERE points.id IN ({placeholders})
        """,
        point_ids,
    )
    return {
        point_id: {
            "point_id": point_id,
            "point_name": point_name,
            "display_name": display_name,
            "equipment_id": equipment_id,
        }
        for point_id, point_name, display_name, equipment_id in cursor.fetchall()
    }


def get_scenarios(db_path=DATABASE_FILE):
    """Return available deterministic alarm demo scenarios."""
    point_ids = sorted({
        update["point_id"]
        for scenario in ALARM_SCENARIOS.values()
        for update in scenario["updates"]
    })

    with sqlite3.connect(db_path) as connection:
        points_by_id = get_points_by_id(connection, point_ids)

    scenarios = []
    for scenario_id, scenario in ALARM_SCENARIOS.items():
        affected_points = [
            points_by_id.get(
                update["point_id"],
                {
                    "point_id": update["point_id"],
                    "point_name": update["point_id"],
                    "display_name": update["point_id"],
                    "equipment_id": "",
                },
            )
            for update in scenario["updates"]
        ]
        scenarios.append(
            {
                "scenario_id": scenario_id,
                "label": scenario["label"],
                "description": scenario["description"],
                "affected_points": affected_points,
            }
        )

    return scenarios


def apply_scenario(scenario_id, db_path=DATABASE_FILE):
    """Apply a deterministic demo scenario by updating current point values."""
    if scenario_id not in ALARM_SCENARIOS:
        raise LookupError(f"Scenario not found: {scenario_id}")

    scenario = ALARM_SCENARIOS[scenario_id]
    updated_values = []
    with sqlite3.connect(db_path) as connection:
        ensure_point_sample_table(connection)
        ensure_current_point_value_table(connection)
        with connection:
            begin_transaction(connection)
            for update in scenario["updates"]:
                updated_values.append(
                    ingest_point_sample_with_connection(
                        connection,
                        update["point_id"],
                        update["value"],
                        quality=update["quality"],
                        source=update["source"],
                    )
                )

    return {
        "scenario_id": scenario_id,
        "label": scenario["label"],
        "description": scenario["description"],
        "updated_count": len(updated_values),
        "current_point_values": updated_values,
    }


def get_rule_evaluations(db_path=DATABASE_FILE, evaluation_timestamp=None):
    """Return stateless alarm rule evaluations against current point values."""
    with sqlite3.connect(db_path) as connection:
        ensure_point_sample_table(connection)
        ensure_current_point_value_table(connection)
        cursor = connection.execute(
            """
            SELECT
                alarm_rules.id,
                alarm_rules.rule_name,
                alarm_rules.rule_type,
                alarm_rules.enabled,
                alarm_rules.severity,
                alarm_rules.alarm_message,
                alarm_rules.point_id,
                points.point_name,
                points.display_name,
                points.equipment_id,
                COALESCE(equipment.equipment_type, 'Unknown') AS equipment_type,
                COALESCE(equipment.location, 'Unknown') AS location,
                points.data_type,
                points.unit,
                current_point_values.latest_sample_id,
                current_point_values.value,
                current_point_values.quality,
                current_point_values.source,
                current_point_values.source_timestamp,
                current_point_values.received_timestamp,
                current_point_values.stale_after_seconds,
                current_point_values.overridden,
                current_point_values.out_of_service,
                current_point_values.protocol,
                current_point_values.address,
                alarm_rules.operator,
                alarm_rules.threshold_value,
                alarm_rules.clear_value,
                alarm_rules.delay_seconds
            FROM alarm_rules
            LEFT JOIN points
                ON alarm_rules.point_id = points.id
            LEFT JOIN equipment
                ON points.equipment_id = equipment.equipment
            LEFT JOIN current_point_values
                ON alarm_rules.point_id = current_point_values.point_id
            ORDER BY points.equipment_id ASC, points.point_name ASC, alarm_rules.rule_name ASC
            """
        )

        evaluations = []
        if evaluation_timestamp is None:
            evaluation_timestamp = current_timestamp()
        for (
            rule_id,
            rule_name,
            rule_type,
            enabled,
            severity,
            alarm_message,
            point_id,
            point_name,
            display_name,
            equipment_id,
            equipment_type,
            location,
            data_type,
            unit,
            latest_sample_id,
            current_value,
            quality,
            source,
            source_timestamp,
            received_timestamp,
            stale_after_seconds,
            overridden,
            out_of_service,
            protocol,
            address,
            operator,
            threshold_value,
            clear_value,
            delay_seconds,
        ) in cursor.fetchall():
            enabled_flag = bool(enabled)
            result = evaluate_alarm_rule(
                rule_type,
                operator,
                threshold_value,
                current_value,
                quality,
                enabled=enabled_flag,
                source_timestamp=source_timestamp,
                received_timestamp=received_timestamp,
                stale_after_seconds=stale_after_seconds,
                overridden=bool(overridden),
                out_of_service=bool(out_of_service),
                evaluation_timestamp=evaluation_timestamp,
            )
            evaluations.append(
                {
                    "id": rule_id,
                    "rule_name": rule_name,
                    "rule_type": rule_type,
                    "enabled": enabled_flag,
                    "severity": severity,
                    "alarm_message": alarm_message,
                    "equipment_id": equipment_id,
                    "equipment_type": equipment_type,
                    "location": location,
                    "point_id": point_id,
                    "point_name": point_name,
                    "display_name": display_name,
                    "data_type": data_type,
                    "unit": unit,
                    "latest_sample_id": latest_sample_id,
                    "current_value": current_value,
                    "quality": quality,
                    "source": source,
                    "source_timestamp": source_timestamp,
                    "received_timestamp": received_timestamp,
                    "stale_after_seconds": stale_after_seconds,
                    "overridden": bool(overridden),
                    "out_of_service": bool(out_of_service),
                    "protocol": protocol,
                    "address": address,
                    "operator": operator,
                    "threshold_value": threshold_value,
                    "clear_value": clear_value,
                    "delay_seconds": delay_seconds,
                    "is_triggered": result["is_triggered"],
                    "evaluation_status": result["evaluation_status"],
                }
            )

        return evaluations


def generated_alarm_id(rule_id):
    """Create a generated alarm record id."""
    return f"GA-{rule_id}-{uuid.uuid4().hex[:12]}"


def alarm_event_id():
    """Create an alarm event audit record id."""
    return f"AE-{uuid.uuid4().hex[:12]}"


def serialize_event_details(details):
    """Return compact JSON details for an alarm event."""
    if not details:
        return ""

    return json.dumps(details, sort_keys=True, separators=(",", ":"))


def generated_alarm_snapshot_values(evaluation):
    """Return rule and sample facts to preserve at generated alarm trigger time."""
    return {
        "rule_name_at_trigger": normalize_text(evaluation["rule_name"]),
        "rule_type_at_trigger": normalize_text(evaluation["rule_type"]),
        "operator_at_trigger": normalize_text(evaluation["operator"]),
        "threshold_value_at_trigger": normalize_text(evaluation["threshold_value"]),
        "clear_value_at_trigger": normalize_text(evaluation["clear_value"]),
        "delay_seconds_at_trigger": parse_delay_seconds(evaluation["delay_seconds"]),
        "severity_at_trigger": normalize_text(evaluation["severity"]),
        "alarm_message_at_trigger": normalize_text(evaluation["alarm_message"]),
        "triggering_sample_id": normalize_text(evaluation.get("latest_sample_id", "")),
        "triggering_value": normalize_text(evaluation["current_value"]),
        "triggering_quality": normalize_text(evaluation["quality"]),
        "triggering_source_timestamp": normalize_text(evaluation["source_timestamp"]),
        "triggering_received_timestamp": normalize_text(evaluation["received_timestamp"]),
    }


def insert_alarm_event(
    connection,
    generated_alarm_id,
    rule_id,
    point_id,
    equipment_id,
    event_type,
    event_timestamp,
    value="",
    sample_id="",
    previous_state="",
    new_state="",
    acknowledged_by="",
    message="",
    details=None,
):
    """Append one generated alarm lifecycle event."""
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            alarm_event_id(),
            generated_alarm_id,
            rule_id,
            point_id,
            equipment_id,
            event_type,
            event_timestamp,
            normalize_text(value),
            normalize_text(sample_id),
            normalize_text(previous_state),
            normalize_text(new_state),
            normalize_text(acknowledged_by),
            normalize_text(message),
            serialize_event_details(details),
        ),
    )


def insert_alarm_event_for_evaluation(
    connection,
    generated_alarm_id,
    evaluation,
    event_type,
    event_timestamp,
    previous_state,
    new_state,
    message,
):
    """Append an alarm event using facts from a rule evaluation."""
    snapshot_values = generated_alarm_snapshot_values(evaluation)
    insert_alarm_event(
        connection,
        generated_alarm_id=generated_alarm_id,
        rule_id=evaluation["id"],
        point_id=evaluation["point_id"],
        equipment_id=evaluation["equipment_id"],
        event_type=event_type,
        event_timestamp=event_timestamp,
        value=evaluation["current_value"],
        sample_id=evaluation.get("latest_sample_id", ""),
        previous_state=previous_state,
        new_state=new_state,
        message=message,
        details={
            "evaluation_status": evaluation["evaluation_status"],
            "operator": evaluation["operator"],
            "rule_type": evaluation["rule_type"],
            "threshold_value": evaluation["threshold_value"],
            "clear_value": evaluation["clear_value"],
            "delay_seconds": snapshot_values["delay_seconds_at_trigger"],
            "severity": evaluation["severity"],
            "alarm_message": evaluation["alarm_message"],
            "triggering_sample_id": snapshot_values["triggering_sample_id"],
            "triggering_value": snapshot_values["triggering_value"],
            "triggering_quality": snapshot_values["triggering_quality"],
            "triggering_source_timestamp": snapshot_values[
                "triggering_source_timestamp"
            ],
            "triggering_received_timestamp": snapshot_values[
                "triggering_received_timestamp"
            ],
        },
    )


def insert_alarm_event_for_open_alarm(
    connection,
    open_alarm,
    event_type,
    event_timestamp,
    previous_state,
    new_state,
    message,
    evaluation=None,
):
    """Append an alarm event when evaluation context may be unavailable."""
    if evaluation is not None:
        insert_alarm_event_for_evaluation(
            connection,
            open_alarm["id"],
            evaluation,
            event_type,
            event_timestamp,
            previous_state,
            new_state,
            message,
        )
        return

    insert_alarm_event(
        connection,
        generated_alarm_id=open_alarm["id"],
        rule_id=open_alarm["rule_id"],
        point_id=open_alarm["point_id"],
        equipment_id=open_alarm["equipment_id"],
        event_type=event_type,
        event_timestamp=event_timestamp,
        value=open_alarm.get("triggered_value", ""),
        previous_state=previous_state,
        new_state=new_state,
        message=message,
        details={"evaluation_status": message},
    )


def get_open_generated_alarms_by_rule(connection):
    """Return pending or active generated alarm records keyed by rule id."""
    cursor = connection.execute(
        """
        SELECT
            id,
            rule_id,
            point_id,
            equipment_id,
            state,
            triggered_value,
            pending_started_at,
            alarm_message
        FROM generated_alarms
        WHERE state IN ('PENDING', 'ACTIVE')
        ORDER BY
            CASE state
                WHEN 'ACTIVE' THEN 0
                ELSE 1
            END,
            last_evaluated_at DESC
        """
    )
    open_alarms = {}
    for (
        alarm_id,
        rule_id,
        point_id,
        equipment_id,
        state,
        triggered_value,
        pending_started_at,
        alarm_message,
    ) in cursor.fetchall():
        if rule_id in open_alarms:
            continue

        open_alarms[rule_id] = {
            "id": alarm_id,
            "rule_id": rule_id,
            "point_id": point_id,
            "equipment_id": equipment_id,
            "state": state,
            "triggered_value": triggered_value,
            "pending_started_at": pending_started_at,
            "alarm_message": alarm_message,
        }

    return open_alarms


def get_generated_alarm_counts(connection):
    """Return generated alarm counts by state."""
    active_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM generated_alarms
        WHERE state = 'ACTIVE'
        """
    ).fetchone()[0]
    pending_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM generated_alarms
        WHERE state = 'PENDING'
        """
    ).fetchone()[0]
    cleared_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM generated_alarms
        WHERE state = 'CLEARED'
        """
    ).fetchone()[0]

    return active_count, pending_count, cleared_count


def evaluate_generated_alarms(db_path=DATABASE_FILE):
    """Create or update generated alarm state from current rule evaluations."""
    timestamp = current_timestamp()
    evaluations = get_rule_evaluations(db_path, evaluation_timestamp=timestamp)
    evaluations_by_rule_id = {
        evaluation["id"]: evaluation
        for evaluation in evaluations
    }
    triggered_evaluations = [
        evaluation
        for evaluation in evaluations
        if evaluation["enabled"] and evaluation["is_triggered"]
    ]

    created_count = 0
    updated_count = 0
    cleared_this_run_count = 0

    with sqlite3.connect(db_path) as connection:
        ensure_generated_alarm_table(connection)
        ensure_alarm_event_table(connection)
        begin_transaction(connection)
        open_generated_alarms = get_open_generated_alarms_by_rule(connection)
        handled_open_rule_ids = set()

        for evaluation in triggered_evaluations:
            delay_seconds = parse_delay_seconds(evaluation["delay_seconds"])
            open_alarm = open_generated_alarms.get(evaluation["id"])

            if open_alarm and open_alarm["state"] == "ACTIVE":
                connection.execute(
                    """
                    UPDATE generated_alarms
                    SET point_id = ?,
                        equipment_id = ?,
                        alarm_message = ?,
                        severity = ?,
                        triggered_value = ?,
                        last_evaluated_at = ?,
                        evaluation_note = ?
                    WHERE id = ?
                    """,
                    (
                        evaluation["point_id"],
                        evaluation["equipment_id"],
                        evaluation["alarm_message"],
                        evaluation["severity"],
                        normalize_text(evaluation["current_value"]),
                        timestamp,
                        active_generated_alarm_note(evaluation),
                        open_alarm["id"],
                    ),
                )
                updated_count += 1
                handled_open_rule_ids.add(evaluation["id"])
                continue

            if open_alarm and open_alarm["state"] == "PENDING":
                pending_started_at = open_alarm["pending_started_at"] or timestamp
                if pending_delay_has_elapsed(
                    pending_started_at,
                    delay_seconds,
                    timestamp,
                ):
                    connection.execute(
                        """
                        UPDATE generated_alarms
                        SET point_id = ?,
                            equipment_id = ?,
                            alarm_message = ?,
                            severity = ?,
                            state = 'ACTIVE',
                            triggered_value = ?,
                            pending_started_at = ?,
                            triggered_at = ?,
                            last_evaluated_at = ?,
                            evaluation_note = ?
                        WHERE id = ?
                        """,
                        (
                            evaluation["point_id"],
                            evaluation["equipment_id"],
                            evaluation["alarm_message"],
                            evaluation["severity"],
                            normalize_text(evaluation["current_value"]),
                            pending_started_at,
                            timestamp,
                            timestamp,
                            active_generated_alarm_note(evaluation),
                            open_alarm["id"],
                        ),
                    )
                    insert_alarm_event_for_evaluation(
                        connection,
                        open_alarm["id"],
                        evaluation,
                        "ALARM_ACTIVATED",
                        timestamp,
                        "PENDING",
                        "ACTIVE",
                        active_generated_alarm_note(evaluation),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE generated_alarms
                        SET point_id = ?,
                            equipment_id = ?,
                            alarm_message = ?,
                            severity = ?,
                            triggered_value = ?,
                            pending_started_at = ?,
                            last_evaluated_at = ?,
                            evaluation_note = ?
                        WHERE id = ?
                        """,
                        (
                            evaluation["point_id"],
                            evaluation["equipment_id"],
                            evaluation["alarm_message"],
                            evaluation["severity"],
                            normalize_text(evaluation["current_value"]),
                            pending_started_at,
                            timestamp,
                            "Pending delay",
                            open_alarm["id"],
                        ),
                    )
                updated_count += 1
                handled_open_rule_ids.add(evaluation["id"])
                continue

            if delay_seconds > 0:
                alarm_id = generated_alarm_id(evaluation["id"])
                snapshot_values = generated_alarm_snapshot_values(evaluation)
                connection.execute(
                    """
                    INSERT INTO generated_alarms (
                        id,
                        rule_id,
                        point_id,
                        equipment_id,
                        alarm_message,
                        severity,
                        state,
                        triggered_value,
                        pending_started_at,
                        triggered_at,
                        cleared_at,
                        last_evaluated_at,
                        evaluation_note,
                        rule_name_at_trigger,
                        rule_type_at_trigger,
                        operator_at_trigger,
                        threshold_value_at_trigger,
                        clear_value_at_trigger,
                        delay_seconds_at_trigger,
                        severity_at_trigger,
                        alarm_message_at_trigger,
                        triggering_sample_id,
                        triggering_value,
                        triggering_quality,
                        triggering_source_timestamp,
                        triggering_received_timestamp
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        alarm_id,
                        evaluation["id"],
                        evaluation["point_id"],
                        evaluation["equipment_id"],
                        evaluation["alarm_message"],
                        evaluation["severity"],
                        "PENDING",
                        normalize_text(evaluation["current_value"]),
                        timestamp,
                        "",
                        "",
                        timestamp,
                        "Pending delay",
                        snapshot_values["rule_name_at_trigger"],
                        snapshot_values["rule_type_at_trigger"],
                        snapshot_values["operator_at_trigger"],
                        snapshot_values["threshold_value_at_trigger"],
                        snapshot_values["clear_value_at_trigger"],
                        snapshot_values["delay_seconds_at_trigger"],
                        snapshot_values["severity_at_trigger"],
                        snapshot_values["alarm_message_at_trigger"],
                        snapshot_values["triggering_sample_id"],
                        snapshot_values["triggering_value"],
                        snapshot_values["triggering_quality"],
                        snapshot_values["triggering_source_timestamp"],
                        snapshot_values["triggering_received_timestamp"],
                    ),
                )
                insert_alarm_event_for_evaluation(
                    connection,
                    alarm_id,
                    evaluation,
                    "PENDING_CREATED",
                    timestamp,
                    "",
                    "PENDING",
                    "Pending delay",
                )
                created_count += 1
                continue

            alarm_id = generated_alarm_id(evaluation["id"])
            snapshot_values = generated_alarm_snapshot_values(evaluation)
            connection.execute(
                """
                INSERT INTO generated_alarms (
                    id,
                    rule_id,
                    point_id,
                    equipment_id,
                    alarm_message,
                    severity,
                    state,
                    triggered_value,
                    pending_started_at,
                    triggered_at,
                    cleared_at,
                    last_evaluated_at,
                    evaluation_note,
                    rule_name_at_trigger,
                    rule_type_at_trigger,
                    operator_at_trigger,
                    threshold_value_at_trigger,
                    clear_value_at_trigger,
                    delay_seconds_at_trigger,
                    severity_at_trigger,
                    alarm_message_at_trigger,
                    triggering_sample_id,
                    triggering_value,
                    triggering_quality,
                    triggering_source_timestamp,
                    triggering_received_timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alarm_id,
                    evaluation["id"],
                    evaluation["point_id"],
                    evaluation["equipment_id"],
                    evaluation["alarm_message"],
                    evaluation["severity"],
                    "ACTIVE",
                    normalize_text(evaluation["current_value"]),
                    "",
                    timestamp,
                    "",
                    timestamp,
                    active_generated_alarm_note(evaluation),
                    snapshot_values["rule_name_at_trigger"],
                    snapshot_values["rule_type_at_trigger"],
                    snapshot_values["operator_at_trigger"],
                    snapshot_values["threshold_value_at_trigger"],
                    snapshot_values["clear_value_at_trigger"],
                    snapshot_values["delay_seconds_at_trigger"],
                    snapshot_values["severity_at_trigger"],
                    snapshot_values["alarm_message_at_trigger"],
                    snapshot_values["triggering_sample_id"],
                    snapshot_values["triggering_value"],
                    snapshot_values["triggering_quality"],
                    snapshot_values["triggering_source_timestamp"],
                    snapshot_values["triggering_received_timestamp"],
                ),
            )
            insert_alarm_event_for_evaluation(
                connection,
                alarm_id,
                evaluation,
                "ALARM_ACTIVATED",
                timestamp,
                "",
                "ACTIVE",
                active_generated_alarm_note(evaluation),
            )
            created_count += 1

        for evaluation in evaluations:
            if evaluation["id"] in handled_open_rule_ids:
                continue

            open_alarm = open_generated_alarms.get(evaluation["id"])
            if not open_alarm:
                continue

            if (
                open_alarm["state"] == "ACTIVE"
                and not active_generated_alarm_should_clear(evaluation)
            ):
                connection.execute(
                    """
                    UPDATE generated_alarms
                    SET point_id = ?,
                        equipment_id = ?,
                        alarm_message = ?,
                        severity = ?,
                        triggered_value = ?,
                        last_evaluated_at = ?,
                        evaluation_note = ?
                    WHERE id = ?
                    """,
                    (
                        evaluation["point_id"],
                        evaluation["equipment_id"],
                        evaluation["alarm_message"],
                        evaluation["severity"],
                        normalize_text(evaluation["current_value"]),
                        timestamp,
                        active_generated_alarm_note(evaluation),
                        open_alarm["id"],
                    ),
                )
                handled_open_rule_ids.add(evaluation["id"])
                updated_count += 1
                continue

            evaluation_note = evaluation["evaluation_status"]
            connection.execute(
                """
                UPDATE generated_alarms
                SET state = 'CLEARED',
                    cleared_at = ?,
                    last_evaluated_at = ?,
                    evaluation_note = ?
                WHERE id = ?
                """,
                (
                    timestamp,
                    timestamp,
                    evaluation_note,
                    open_alarm["id"],
                ),
            )
            insert_alarm_event_for_evaluation(
                connection,
                open_alarm["id"],
                evaluation,
                "ALARM_CLEARED",
                timestamp,
                open_alarm["state"],
                "CLEARED",
                evaluation_note,
            )
            handled_open_rule_ids.add(evaluation["id"])
            cleared_this_run_count += 1

        for rule_id, open_alarm in open_generated_alarms.items():
            if rule_id in handled_open_rule_ids:
                continue

            evaluation_note = "Rule not evaluated"
            if rule_id in evaluations_by_rule_id:
                evaluation_note = evaluations_by_rule_id[rule_id]["evaluation_status"]

            connection.execute(
                """
                UPDATE generated_alarms
                SET state = 'CLEARED',
                    cleared_at = ?,
                    last_evaluated_at = ?,
                    evaluation_note = ?
                WHERE id = ?
                """,
                (
                    timestamp,
                    timestamp,
                    evaluation_note,
                    open_alarm["id"],
                ),
            )
            insert_alarm_event_for_open_alarm(
                connection,
                open_alarm,
                "ALARM_CLEARED",
                timestamp,
                open_alarm["state"],
                "CLEARED",
                evaluation_note,
                evaluation=evaluations_by_rule_id.get(rule_id),
            )
            cleared_this_run_count += 1

        active_count, pending_count, total_cleared_count = get_generated_alarm_counts(
            connection,
        )

    return {
        "active_count": active_count,
        "pending_count": pending_count,
        "cleared_count": cleared_this_run_count,
        "total_cleared_count": total_cleared_count,
        "created_count": created_count,
        "updated_count": updated_count,
    }


def get_generated_alarms(db_path=DATABASE_FILE):
    """Return generated alarms with rule, point, and equipment context."""
    with sqlite3.connect(db_path) as connection:
        ensure_generated_alarm_table(connection)
        cursor = connection.execute(
            """
            SELECT
                generated_alarms.id,
                generated_alarms.rule_id,
                alarm_rules.rule_name,
                generated_alarms.point_id,
                points.point_name,
                points.display_name,
                generated_alarms.equipment_id,
                COALESCE(equipment.equipment_type, 'Unknown') AS equipment_type,
                COALESCE(equipment.location, 'Unknown') AS location,
                points.data_type,
                points.unit,
                generated_alarms.alarm_message,
                generated_alarms.severity,
                generated_alarms.state,
                generated_alarms.triggered_value,
                generated_alarms.pending_started_at,
                generated_alarms.triggered_at,
                generated_alarms.cleared_at,
                generated_alarms.last_evaluated_at,
                generated_alarms.evaluation_note,
                generated_alarms.acknowledged,
                generated_alarms.acknowledged_at,
                generated_alarms.acknowledged_by,
                generated_alarms.rule_name_at_trigger,
                generated_alarms.rule_type_at_trigger,
                generated_alarms.operator_at_trigger,
                generated_alarms.threshold_value_at_trigger,
                generated_alarms.clear_value_at_trigger,
                generated_alarms.delay_seconds_at_trigger,
                generated_alarms.severity_at_trigger,
                generated_alarms.alarm_message_at_trigger,
                generated_alarms.triggering_sample_id,
                generated_alarms.triggering_value,
                generated_alarms.triggering_quality,
                generated_alarms.triggering_source_timestamp,
                generated_alarms.triggering_received_timestamp
            FROM generated_alarms
            LEFT JOIN alarm_rules
                ON generated_alarms.rule_id = alarm_rules.id
            LEFT JOIN points
                ON generated_alarms.point_id = points.id
            LEFT JOIN equipment
                ON generated_alarms.equipment_id = equipment.equipment
            ORDER BY
                CASE generated_alarms.state
                    WHEN 'ACTIVE' THEN 0
                    WHEN 'PENDING' THEN 1
                    ELSE 2
                END,
                generated_alarms.last_evaluated_at DESC,
                generated_alarms.equipment_id ASC,
                generated_alarms.alarm_message ASC
            """
        )
        return [
            {
                "id": alarm_id,
                "rule_id": rule_id,
                "rule_name": rule_name,
                "point_id": point_id,
                "point_name": point_name,
                "display_name": display_name,
                "equipment_id": equipment_id,
                "equipment_type": equipment_type,
                "location": location,
                "data_type": data_type,
                "unit": unit,
                "alarm_message": alarm_message,
                "severity": severity,
                "state": state,
                "triggered_value": triggered_value,
                "pending_started_at": pending_started_at,
                "triggered_at": triggered_at,
                "cleared_at": cleared_at,
                "last_evaluated_at": last_evaluated_at,
                "evaluation_note": evaluation_note,
                "acknowledged": bool(acknowledged),
                "acknowledged_at": acknowledged_at,
                "acknowledged_by": acknowledged_by,
                "rule_name_at_trigger": rule_name_at_trigger,
                "rule_type_at_trigger": rule_type_at_trigger,
                "operator_at_trigger": operator_at_trigger,
                "threshold_value_at_trigger": threshold_value_at_trigger,
                "clear_value_at_trigger": clear_value_at_trigger,
                "delay_seconds_at_trigger": delay_seconds_at_trigger,
                "severity_at_trigger": severity_at_trigger,
                "alarm_message_at_trigger": alarm_message_at_trigger,
                "triggering_sample_id": triggering_sample_id,
                "triggering_value": triggering_value,
                "triggering_quality": triggering_quality,
                "triggering_source_timestamp": triggering_source_timestamp,
                "triggering_received_timestamp": triggering_received_timestamp,
            }
            for (
                alarm_id,
                rule_id,
                rule_name,
                point_id,
                point_name,
                display_name,
                equipment_id,
                equipment_type,
                location,
                data_type,
                unit,
                alarm_message,
                severity,
                state,
                triggered_value,
                pending_started_at,
                triggered_at,
                cleared_at,
                last_evaluated_at,
                evaluation_note,
                acknowledged,
                acknowledged_at,
                acknowledged_by,
                rule_name_at_trigger,
                rule_type_at_trigger,
                operator_at_trigger,
                threshold_value_at_trigger,
                clear_value_at_trigger,
                delay_seconds_at_trigger,
                severity_at_trigger,
                alarm_message_at_trigger,
                triggering_sample_id,
                triggering_value,
                triggering_quality,
                triggering_source_timestamp,
                triggering_received_timestamp,
            ) in cursor.fetchall()
        ]


def get_alarm_events(db_path=DATABASE_FILE):
    """Return generated alarm lifecycle events with useful context."""
    with sqlite3.connect(db_path) as connection:
        ensure_generated_alarm_table(connection)
        ensure_alarm_event_table(connection)
        cursor = connection.execute(
            """
            SELECT
                alarm_events.id,
                alarm_events.generated_alarm_id,
                alarm_events.rule_id,
                COALESCE(alarm_rules.rule_name, '') AS rule_name,
                alarm_events.point_id,
                COALESCE(points.point_name, '') AS point_name,
                COALESCE(points.display_name, '') AS display_name,
                alarm_events.equipment_id,
                COALESCE(equipment.equipment_type, '') AS equipment_type,
                COALESCE(equipment.location, '') AS location,
                alarm_events.event_type,
                alarm_events.event_timestamp,
                alarm_events.value,
                alarm_events.sample_id,
                alarm_events.previous_state,
                alarm_events.new_state,
                alarm_events.acknowledged_by,
                alarm_events.message,
                alarm_events.details_json,
                COALESCE(generated_alarms.alarm_message, '') AS generated_alarm_message
            FROM alarm_events
            LEFT JOIN alarm_rules
                ON alarm_events.rule_id = alarm_rules.id
            LEFT JOIN points
                ON alarm_events.point_id = points.id
            LEFT JOIN equipment
                ON alarm_events.equipment_id = equipment.equipment
            LEFT JOIN generated_alarms
                ON alarm_events.generated_alarm_id = generated_alarms.id
            ORDER BY
                alarm_events.event_timestamp DESC,
                alarm_events.id DESC
            """
        )
        return [
            {
                "id": event_id,
                "generated_alarm_id": generated_alarm_id,
                "rule_id": rule_id,
                "rule_name": rule_name,
                "point_id": point_id,
                "point_name": point_name,
                "display_name": display_name,
                "equipment_id": equipment_id,
                "equipment_type": equipment_type,
                "location": location,
                "event_type": event_type,
                "event_timestamp": event_timestamp,
                "value": value,
                "sample_id": sample_id,
                "previous_state": previous_state,
                "new_state": new_state,
                "acknowledged_by": acknowledged_by,
                "message": message,
                "details_json": details_json,
                "generated_alarm_message": generated_alarm_message,
            }
            for (
                event_id,
                generated_alarm_id,
                rule_id,
                rule_name,
                point_id,
                point_name,
                display_name,
                equipment_id,
                equipment_type,
                location,
                event_type,
                event_timestamp,
                value,
                sample_id,
                previous_state,
                new_state,
                acknowledged_by,
                message,
                details_json,
                generated_alarm_message,
            ) in cursor.fetchall()
        ]


def acknowledge_generated_alarm(
    alarm_id,
    acknowledged_by="local-operator",
    db_path=DATABASE_FILE,
):
    """Acknowledge a generated alarm and return its enriched record."""
    operator_name = normalize_text(acknowledged_by)
    if not has_value(operator_name):
        operator_name = "local-operator"

    with sqlite3.connect(db_path) as connection:
        ensure_generated_alarm_table(connection)
        ensure_alarm_event_table(connection)
        begin_transaction(connection)
        alarm_row = connection.execute(
            """
            SELECT
                rule_id,
                point_id,
                equipment_id,
                state,
                triggered_value,
                alarm_message
            FROM generated_alarms
            WHERE id = ?
            """,
            (alarm_id,),
        ).fetchone()
        if not alarm_row:
            raise LookupError(f"Generated alarm not found: {alarm_id}")

        (
            rule_id,
            point_id,
            equipment_id,
            state,
            triggered_value,
            alarm_message,
        ) = alarm_row
        latest_sample_row = connection.execute(
            """
            SELECT latest_sample_id
            FROM current_point_values
            WHERE point_id = ?
            """,
            (point_id,),
        ).fetchone()
        latest_sample_id = latest_sample_row[0] if latest_sample_row else ""
        acknowledged_at = current_timestamp()
        connection.execute(
            """
            UPDATE generated_alarms
            SET acknowledged = 1,
                acknowledged_at = ?,
                acknowledged_by = ?
            WHERE id = ?
            """,
            (
                acknowledged_at,
                operator_name,
                alarm_id,
            ),
        )
        insert_alarm_event(
            connection,
            generated_alarm_id=alarm_id,
            rule_id=rule_id,
            point_id=point_id,
            equipment_id=equipment_id,
            event_type="ALARM_ACKNOWLEDGED",
            event_timestamp=acknowledged_at,
            value=triggered_value,
            sample_id=latest_sample_id,
            previous_state=state,
            new_state=state,
            acknowledged_by=operator_name,
            message=alarm_message,
            details={"acknowledged_by": operator_name},
        )

    for alarm in get_generated_alarms(db_path):
        if alarm["id"] == alarm_id:
            return alarm

    raise LookupError(f"Generated alarm not found: {alarm_id}")
