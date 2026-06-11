import sqlite3
import uuid
from datetime import UTC
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_FILE = PROJECT_ROOT / "db" / "facilityops.sqlite3"
DATABASE_DISPLAY_PATH = Path("db") / "facilityops.sqlite3"
LOADER_COMMAND = "python3 analysis/load_alarm_db.py"

GENERATED_ALARM_COUNT_COLUMNS = {"severity", "state", "equipment_id"}
BLANK_VALUES = {"", "null", "none", "n/a"}
ANALOG_OPERATORS = {">", ">=", "<", "<="}
MATCH_OPERATORS = {"==", "!="}
TRUE_VALUES = {"true", "1", "yes", "on"}
FALSE_VALUES = {"false", "0", "no", "off"}
ALLOWED_QUALITIES = {"GOOD", "BAD", "STALE", "UNKNOWN"}
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


def get_generated_alarm_count(connection, state=None, severity=None):
    """Return generated alarm count filtered by state and severity."""
    where_clauses = []
    parameters = []
    if state is not None:
        where_clauses.append("state = ?")
        parameters.append(state)
    if severity is not None:
        where_clauses.append("severity = ?")
        parameters.append(severity)

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


def ensure_current_point_value_table(connection):
    """Create current point value table if the loader has not run yet."""
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


def has_value(value):
    """Return True when an API/database field contains a meaningful value."""
    if value is None:
        return False

    return str(value).strip().lower() not in BLANK_VALUES


def normalize_text(value):
    """Normalize optional values to stripped strings for comparison."""
    if value is None:
        return ""

    return str(value).strip()


def current_point_value_id(point_id):
    """Create a stable current point value id for a point."""
    return f"CPV-{point_id}"


def normalize_quality(value):
    """Normalize and validate current point value quality."""
    normalized_value = normalize_text(value).upper()
    if normalized_value not in ALLOWED_QUALITIES:
        allowed_values = ", ".join(sorted(ALLOWED_QUALITIES))
        raise ValueError(f"quality must be one of: {allowed_values}")

    return normalized_value


def normalize_current_value_source(value):
    """Normalize and validate current point value source."""
    normalized_value = normalize_text(value).upper()
    if normalized_value not in ALLOWED_CURRENT_VALUE_SOURCES:
        allowed_values = ", ".join(sorted(ALLOWED_CURRENT_VALUE_SOURCES))
        raise ValueError(f"source must be one of: {allowed_values}")

    return normalized_value


def parse_number(value):
    """Safely parse a numeric point or threshold value."""
    if not has_value(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_boolean(value):
    """Safely parse a boolean-style point or threshold value."""
    if not has_value(value):
        return None

    normalized_value = normalize_text(value).lower()
    if normalized_value in TRUE_VALUES:
        return True
    if normalized_value in FALSE_VALUES:
        return False

    return None


def compare_values(current_value, threshold_value, operator):
    """Compare parsed values with a supported operator."""
    if operator == "==":
        return current_value == threshold_value
    if operator == "!=":
        return current_value != threshold_value
    if operator == ">":
        return current_value > threshold_value
    if operator == ">=":
        return current_value >= threshold_value
    if operator == "<":
        return current_value < threshold_value
    if operator == "<=":
        return current_value <= threshold_value

    return False


def quality_status(quality):
    """Return an evaluation status for non-GOOD point quality."""
    normalized_quality = normalize_text(quality).upper()
    if normalized_quality == "BAD":
        return "Bad quality"
    if normalized_quality == "STALE":
        return "Stale quality"

    return "Unknown quality"


def evaluation_result(is_triggered, evaluation_status):
    """Create a consistent rule evaluation result."""
    return {
        "is_triggered": is_triggered,
        "evaluation_status": evaluation_status,
    }


def evaluate_alarm_rule(
    rule_type,
    operator,
    threshold_value,
    current_value,
    quality,
    enabled=True,
):
    """Evaluate one alarm rule against one current point value."""
    if not enabled:
        return evaluation_result(False, "Disabled")

    if not has_value(current_value):
        return evaluation_result(False, "No current value")

    if normalize_text(quality).upper() != "GOOD":
        return evaluation_result(False, quality_status(quality))

    if rule_type == "analog_limit":
        if operator not in ANALOG_OPERATORS:
            return evaluation_result(False, "Unsupported operator")

        parsed_current_value = parse_number(current_value)
        parsed_threshold_value = parse_number(threshold_value)
        if parsed_current_value is None or parsed_threshold_value is None:
            return evaluation_result(False, "Invalid analog value")

        is_triggered = compare_values(
            parsed_current_value,
            parsed_threshold_value,
            operator,
        )
        return evaluation_result(is_triggered, "Triggered" if is_triggered else "Normal")

    if rule_type == "boolean_state":
        if operator not in MATCH_OPERATORS:
            return evaluation_result(False, "Unsupported operator")

        parsed_current_value = parse_boolean(current_value)
        parsed_threshold_value = parse_boolean(threshold_value)
        if parsed_current_value is None or parsed_threshold_value is None:
            return evaluation_result(False, "Invalid boolean value")

        is_triggered = compare_values(
            parsed_current_value,
            parsed_threshold_value,
            operator,
        )
        return evaluation_result(is_triggered, "Triggered" if is_triggered else "Normal")

    if rule_type == "enum_match":
        if operator not in MATCH_OPERATORS:
            return evaluation_result(False, "Unsupported operator")

        is_triggered = compare_values(
            normalize_text(current_value).lower(),
            normalize_text(threshold_value).lower(),
            operator,
        )
        return evaluation_result(is_triggered, "Triggered" if is_triggered else "Normal")

    return evaluation_result(False, "Unsupported rule type")


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
        ensure_current_point_value_table(connection)
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


def get_current_point_value(point_id, db_path=DATABASE_FILE):
    """Return one current point value with point and equipment context."""
    with sqlite3.connect(db_path) as connection:
        ensure_current_point_value_table(connection)
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
            WHERE current_point_values.point_id = ?
            """,
            (point_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        (
            value_id,
            current_point_id,
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
        ) = row

        return {
            "id": value_id,
            "point_id": current_point_id,
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


def update_current_point_value(
    point_id,
    value,
    quality="GOOD",
    source="MANUAL",
    db_path=DATABASE_FILE,
):
    """Update or create the current value for an existing point."""
    normalized_value = normalize_text(value)
    normalized_quality = normalize_quality(quality)
    normalized_source = normalize_current_value_source(source)
    updated_at = current_timestamp()

    with sqlite3.connect(db_path) as connection:
        ensure_current_point_value_table(connection)
        if not point_exists(connection, point_id):
            raise LookupError(f"Point not found: {point_id}")

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
                SET value = ?,
                    quality = ?,
                    source = ?,
                    updated_at = ?
                WHERE point_id = ?
                """,
                (
                    normalized_value,
                    normalized_quality,
                    normalized_source,
                    updated_at,
                    point_id,
                ),
            )
        else:
            connection.execute(
                """
                INSERT INTO current_point_values (
                    id,
                    point_id,
                    value,
                    quality,
                    source,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    current_point_value_id(point_id),
                    point_id,
                    normalized_value,
                    normalized_quality,
                    normalized_source,
                    updated_at,
                ),
            )

    return get_current_point_value(point_id, db_path)


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
    updated_values = [
        update_current_point_value(
            update["point_id"],
            update["value"],
            quality=update["quality"],
            source=update["source"],
            db_path=db_path,
        )
        for update in scenario["updates"]
    ]

    return {
        "scenario_id": scenario_id,
        "label": scenario["label"],
        "description": scenario["description"],
        "updated_count": len(updated_values),
        "current_point_values": updated_values,
    }


def get_rule_evaluations(db_path=DATABASE_FILE):
    """Return stateless alarm rule evaluations against current point values."""
    with sqlite3.connect(db_path) as connection:
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
                current_point_values.value,
                current_point_values.quality,
                current_point_values.source,
                alarm_rules.operator,
                alarm_rules.threshold_value,
                alarm_rules.clear_value
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
            current_value,
            quality,
            source,
            operator,
            threshold_value,
            clear_value,
        ) in cursor.fetchall():
            enabled_flag = bool(enabled)
            result = evaluate_alarm_rule(
                rule_type,
                operator,
                threshold_value,
                current_value,
                quality,
                enabled=enabled_flag,
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
                    "current_value": current_value,
                    "quality": quality,
                    "source": source,
                    "operator": operator,
                    "threshold_value": threshold_value,
                    "clear_value": clear_value,
                    "is_triggered": result["is_triggered"],
                    "evaluation_status": result["evaluation_status"],
                }
            )

        return evaluations


def generated_alarm_id(rule_id):
    """Create a generated alarm record id."""
    return f"GA-{rule_id}-{uuid.uuid4().hex[:12]}"


def get_active_generated_alarms_by_rule(connection):
    """Return active generated alarm ids keyed by rule id."""
    cursor = connection.execute(
        """
        SELECT id, rule_id
        FROM generated_alarms
        WHERE state = 'ACTIVE'
        """
    )
    return {
        rule_id: alarm_id
        for alarm_id, rule_id in cursor.fetchall()
    }


def get_generated_alarm_counts(connection):
    """Return generated alarm counts by state."""
    active_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM generated_alarms
        WHERE state = 'ACTIVE'
        """
    ).fetchone()[0]
    cleared_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM generated_alarms
        WHERE state = 'CLEARED'
        """
    ).fetchone()[0]

    return active_count, cleared_count


def evaluate_generated_alarms(db_path=DATABASE_FILE):
    """Create or update generated alarm state from current rule evaluations."""
    evaluations = get_rule_evaluations(db_path)
    evaluations_by_rule_id = {
        evaluation["id"]: evaluation
        for evaluation in evaluations
    }
    triggered_evaluations = [
        evaluation
        for evaluation in evaluations
        if evaluation["enabled"] and evaluation["is_triggered"]
    ]
    triggered_rule_ids = {
        evaluation["id"]
        for evaluation in triggered_evaluations
    }

    timestamp = current_timestamp()
    created_count = 0
    updated_count = 0
    cleared_this_run_count = 0

    with sqlite3.connect(db_path) as connection:
        ensure_generated_alarm_table(connection)
        active_generated_alarms = get_active_generated_alarms_by_rule(connection)

        for evaluation in triggered_evaluations:
            active_alarm_id = active_generated_alarms.get(evaluation["id"])
            if active_alarm_id:
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
                        evaluation["evaluation_status"],
                        active_alarm_id,
                    ),
                )
                updated_count += 1
            else:
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
                        triggered_at,
                        cleared_at,
                        last_evaluated_at,
                        evaluation_note
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        generated_alarm_id(evaluation["id"]),
                        evaluation["id"],
                        evaluation["point_id"],
                        evaluation["equipment_id"],
                        evaluation["alarm_message"],
                        evaluation["severity"],
                        "ACTIVE",
                        normalize_text(evaluation["current_value"]),
                        timestamp,
                        "",
                        timestamp,
                        evaluation["evaluation_status"],
                    ),
                )
                created_count += 1

        for rule_id, alarm_id in active_generated_alarms.items():
            if rule_id in triggered_rule_ids:
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
                    alarm_id,
                ),
            )
            cleared_this_run_count += 1

        active_count, total_cleared_count = get_generated_alarm_counts(connection)

    return {
        "active_count": active_count,
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
                generated_alarms.triggered_at,
                generated_alarms.cleared_at,
                generated_alarms.last_evaluated_at,
                generated_alarms.evaluation_note
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
                    ELSE 1
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
                "triggered_at": triggered_at,
                "cleared_at": cleared_at,
                "last_evaluated_at": last_evaluated_at,
                "evaluation_note": evaluation_note,
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
                triggered_at,
                cleared_at,
                last_evaluated_at,
                evaluation_note,
            ) in cursor.fetchall()
        ]
