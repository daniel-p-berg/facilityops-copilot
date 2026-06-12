import csv
import re
import sqlite3
from pathlib import Path

from analysis.load_alarm_db import create_equipment_table
from analysis.load_alarm_db import create_point_table
from backend.summary import current_timestamp
from backend.summary import ensure_alarm_event_table
from backend.summary import ensure_generated_alarm_table
from backend.summary import insert_alarm_event


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODBUS_IMPORT_CSV = (
    PROJECT_ROOT / "data" / "imports" / "modbus_register_map_sample.csv"
)

MODBUS_PROTOCOL = "MODBUS"
REQUIRED_COLUMNS = (
    "device_name",
    "slave_id",
    "function_code",
    "register_address",
    "point_name",
    "data_type",
    "scale",
    "unit",
    "description",
)
REQUIRED_VALUE_FIELDS = tuple(
    column
    for column in REQUIRED_COLUMNS
    if column != "unit"
)
ALLOWED_FUNCTION_CODES = {1, 2, 3, 4}
SUPPORTED_DATA_TYPES = {
    "analog": "analog",
    "bool": "boolean",
    "boolean": "boolean",
    "bit": "boolean",
    "enum": "enum",
    "float": "analog",
    "float32": "analog",
    "float64": "analog",
    "int16": "analog",
    "int32": "analog",
    "integer": "analog",
    "uint16": "analog",
    "uint32": "analog",
}
BLANK_VALUES = {"", "null", "none", "n/a"}


def resolve_csv_path(csv_path=None):
    """Resolve an import CSV path from the project root when relative."""
    if csv_path is None:
        return DEFAULT_MODBUS_IMPORT_CSV

    path = Path(str(csv_path)).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    return path


def has_value(value):
    """Return True when a CSV field has meaningful content."""
    if value is None:
        return False

    return str(value).strip().lower() not in BLANK_VALUES


def normalize_text(value):
    """Normalize CSV text fields to stripped strings."""
    if value is None:
        return ""

    return str(value).strip()


def validation_issue(row_number, field, message):
    """Return one structured validation issue."""
    return {
        "row_number": row_number,
        "field": field,
        "message": message,
    }


def normalize_device_name(value):
    """Normalize a device name into the local equipment id style."""
    normalized = normalize_text(value).upper().replace(" ", "-")
    normalized = re.sub(r"[^A-Z0-9_-]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-_")
    return normalized


def normalize_point_name(value):
    """Normalize point names into the existing uppercase point catalog style."""
    normalized = normalize_text(value).upper()
    normalized = re.sub(r"[^A-Z0-9]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


def display_name_for_point(equipment_id, point_name):
    """Create a simple display name for imported points."""
    words = point_name.replace("_", " ").title()
    words = words.replace("Kw", "kW")
    return f"{equipment_id} {words}"


def infer_equipment_type(equipment_id):
    """Infer a readable equipment type from common local sample ids."""
    prefix_map = (
        ("UPS", "UPS"),
        ("GEN", "Generator"),
        ("ATS", "ATS"),
        ("PDU", "PDU"),
        ("CRAC", "CRAC"),
        ("CRAH", "CRAH"),
        ("CRAC", "CRAC"),
        ("AHU", "Air Handler"),
        ("CHW", "Chilled Water Pump"),
        ("TEMP", "Temperature Sensor"),
        ("HUM", "Humidity Sensor"),
        ("MTR", "Electrical Meter"),
    )
    for prefix, equipment_type in prefix_map:
        if equipment_id.startswith(prefix):
            return equipment_type

    return "Modbus Device"


def infer_source_system(equipment_type):
    """Infer whether the imported point belongs to BMS or EPMS context."""
    if equipment_type in {"UPS", "Generator", "ATS", "PDU", "Electrical Meter"}:
        return "EPMS"

    return "BMS"


def infer_criticality(equipment_type):
    """Infer a conservative default criticality for imported equipment."""
    if equipment_type in {"UPS", "Generator", "ATS", "PDU", "Electrical Meter"}:
        return "Critical"
    if equipment_type in {"CRAH", "CRAC", "Air Handler", "Chilled Water Pump"}:
        return "High"

    return "Medium"


def infer_location(equipment_type):
    """Infer a local demonstration location for imported equipment."""
    if equipment_type in {"UPS", "ATS", "PDU", "Electrical Meter"}:
        return "Electrical Room A"
    if equipment_type == "Generator":
        return "Generator Yard"
    if equipment_type in {"CRAH", "CRAC"}:
        return "Data Hall A"
    if equipment_type in {"Temperature Sensor", "Humidity Sensor"}:
        return "Data Hall A"
    if equipment_type in {"Air Handler", "Chilled Water Pump"}:
        return "Central Plant"

    return "Local Simulation"


def infer_point_type(point_name, data_type):
    """Infer point type using the existing sensor/status/command vocabulary."""
    if data_type == "boolean":
        return "status"
    if "STATUS" in point_name or "STATE" in point_name or "AVAILABLE" in point_name:
        return "status"
    if "COMMAND" in point_name:
        return "command"

    return "sensor"


def parse_integer_field(value, field_name, row_number, minimum, maximum, errors):
    """Parse an integer field and append a validation error when invalid."""
    try:
        parsed_value = int(normalize_text(value))
    except ValueError:
        errors.append(
            validation_issue(
                row_number,
                field_name,
                f"{field_name} must be an integer from {minimum} to {maximum}",
            )
        )
        return None

    if parsed_value < minimum or parsed_value > maximum:
        errors.append(
            validation_issue(
                row_number,
                field_name,
                f"{field_name} must be an integer from {minimum} to {maximum}",
            )
        )
        return None

    return parsed_value


def parse_scale(value, row_number, errors):
    """Parse a required numeric Modbus scale."""
    try:
        return float(normalize_text(value))
    except ValueError:
        errors.append(
            validation_issue(
                row_number,
                "scale",
                "scale must be a number",
            )
        )
        return None


def normalize_data_type(value, row_number, errors):
    """Normalize supported Modbus data types to point catalog data types."""
    register_data_type = normalize_text(value).lower()
    point_data_type = SUPPORTED_DATA_TYPES.get(register_data_type)
    if point_data_type is None:
        allowed_values = ", ".join(sorted(SUPPORTED_DATA_TYPES))
        errors.append(
            validation_issue(
                row_number,
                "data_type",
                f"data_type must be one of: {allowed_values}",
            )
        )
        return None, None

    return register_data_type, point_data_type


def modbus_address(slave_id, function_code, register_address):
    """Return the stable address metadata stored on imported points."""
    return (
        f"slave_id={slave_id};"
        f"function_code={function_code};"
        f"register_address={register_address}"
    )


def read_csv_records(csv_path):
    """Read raw import rows and return structured header/file errors."""
    errors = []
    path = resolve_csv_path(csv_path)
    if not path.exists():
        return path, [], [
            validation_issue(None, "csv_path", f"CSV file not found: {path}")
        ]

    with open(path, mode="r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames or []
        missing_columns = [
            column
            for column in REQUIRED_COLUMNS
            if column not in fieldnames
        ]
        if missing_columns:
            missing = ", ".join(missing_columns)
            errors.append(
                validation_issue(
                    None,
                    "header",
                    f"Missing required CSV columns: {missing}",
                )
            )
            return path, [], errors

        return path, list(reader), errors


def normalized_import_row(raw_row, row_number, errors):
    """Normalize one CSV row into point/equipment catalog fields."""
    missing_fields = [
        field
        for field in REQUIRED_VALUE_FIELDS
        if not has_value(raw_row.get(field))
    ]
    for field in missing_fields:
        errors.append(
            validation_issue(row_number, field, f"Missing required field: {field}")
        )

    equipment_id = normalize_device_name(raw_row.get("device_name"))
    point_name = normalize_point_name(raw_row.get("point_name"))
    slave_id = None
    function_code = None
    register_address = None
    scale = None
    register_data_type = None
    point_data_type = None

    if has_value(raw_row.get("slave_id")):
        slave_id = parse_integer_field(
            raw_row.get("slave_id"),
            "slave_id",
            row_number,
            1,
            247,
            errors,
        )
    if has_value(raw_row.get("function_code")):
        function_code = parse_integer_field(
            raw_row.get("function_code"),
            "function_code",
            row_number,
            min(ALLOWED_FUNCTION_CODES),
            max(ALLOWED_FUNCTION_CODES),
            errors,
        )
        if function_code is not None and function_code not in ALLOWED_FUNCTION_CODES:
            errors.append(
                validation_issue(
                    row_number,
                    "function_code",
                    "function_code must be one of: 1, 2, 3, 4",
                )
            )
            function_code = None
    if has_value(raw_row.get("register_address")):
        register_address = parse_integer_field(
            raw_row.get("register_address"),
            "register_address",
            row_number,
            0,
            65535,
            errors,
        )
    if has_value(raw_row.get("scale")):
        scale = parse_scale(raw_row.get("scale"), row_number, errors)
    if has_value(raw_row.get("data_type")):
        register_data_type, point_data_type = normalize_data_type(
            raw_row.get("data_type"),
            row_number,
            errors,
        )

    if not equipment_id or not point_name:
        return None
    if (
        slave_id is None
        or function_code is None
        or register_address is None
        or scale is None
        or register_data_type is None
    ):
        return None

    equipment_type = infer_equipment_type(equipment_id)
    source_system = infer_source_system(equipment_type)
    point_id = f"{equipment_id}_{point_name}"
    address = modbus_address(slave_id, function_code, register_address)

    return {
        "row_number": row_number,
        "device_name": equipment_id,
        "equipment_id": equipment_id,
        "equipment_type": equipment_type,
        "location": infer_location(equipment_type),
        "criticality": infer_criticality(equipment_type),
        "source_system": source_system,
        "slave_id": slave_id,
        "function_code": function_code,
        "register_address": register_address,
        "point_id": point_id,
        "point_name": point_name,
        "display_name": display_name_for_point(equipment_id, point_name),
        "point_type": infer_point_type(point_name, point_data_type),
        "data_type": point_data_type,
        "register_data_type": register_data_type,
        "scale": scale,
        "unit": normalize_text(raw_row.get("unit")),
        "description": normalize_text(raw_row.get("description")),
        "protocol": MODBUS_PROTOCOL,
        "address": address,
        "equipment_action": "create_equipment",
        "action": "create_point",
    }


def point_metadata_columns(connection):
    """Return available point table columns for clean compatibility checks."""
    table_exists = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'points'
        """
    ).fetchone()
    if not table_exists:
        return set()

    return {
        row[1]
        for row in connection.execute("PRAGMA table_info(points)")
    }


def existing_points_by_id(connection):
    """Return existing point protocol/address metadata keyed by point id."""
    columns = point_metadata_columns(connection)
    if not columns:
        return {}

    protocol_sql = "protocol" if "protocol" in columns else "''"
    address_sql = "address" if "address" in columns else "''"
    cursor = connection.execute(
        f"""
        SELECT id, equipment_id, point_name, {protocol_sql}, {address_sql}
        FROM points
        """
    )
    return {
        point_id: {
            "id": point_id,
            "equipment_id": equipment_id,
            "point_name": point_name,
            "protocol": protocol or "",
            "address": address or "",
        }
        for point_id, equipment_id, point_name, protocol, address in cursor.fetchall()
    }


def existing_equipment_names(connection):
    """Return existing equipment ids when the equipment table is present."""
    table_exists = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'equipment'
        """
    ).fetchone()
    if not table_exists:
        return set()

    return {
        row[0]
        for row in connection.execute("SELECT equipment FROM equipment")
    }


def add_duplicate_import_issues(rows, errors):
    """Add duplicate point and Modbus tuple errors within the import file."""
    point_rows = {}
    address_rows = {}
    for row in rows:
        previous_point_row = point_rows.get(row["point_id"])
        if previous_point_row is not None:
            errors.append(
                validation_issue(
                    row["row_number"],
                    "point_name",
                    (
                        "Duplicate point_name in import: "
                        f"{row['point_name']} also appears on row {previous_point_row}"
                    ),
                )
            )
        else:
            point_rows[row["point_id"]] = row["row_number"]

        address_key = (
            row["protocol"],
            row["slave_id"],
            row["function_code"],
            row["register_address"],
        )
        previous_address_row = address_rows.get(address_key)
        if previous_address_row is not None:
            errors.append(
                validation_issue(
                    row["row_number"],
                    "register_address",
                    (
                        "Duplicate Modbus address tuple in import: "
                        f"slave_id={row['slave_id']}, "
                        f"function_code={row['function_code']}, "
                        f"register_address={row['register_address']} "
                        f"also appears on row {previous_address_row}"
                    ),
                )
            )
        else:
            address_rows[address_key] = row["row_number"]


def add_existing_metadata_issues(rows, db_path, errors, warnings):
    """Add warnings/errors for existing point catalog metadata conflicts."""
    if db_path is None or not Path(db_path).exists():
        return

    with sqlite3.connect(db_path) as connection:
        existing_by_id = existing_points_by_id(connection)
        existing_equipment = existing_equipment_names(connection)
        existing_by_address = {}
        for existing in existing_by_id.values():
            if existing["protocol"] and existing["address"]:
                existing_by_address[(existing["protocol"], existing["address"])] = existing

        for row in rows:
            if row["equipment_id"] in existing_equipment:
                row["equipment_action"] = "existing_equipment"

            existing_point = existing_by_id.get(row["point_id"])
            existing_address_point = existing_by_address.get(
                (row["protocol"], row["address"])
            )
            if (
                existing_address_point is not None
                and existing_address_point["id"] != row["point_id"]
            ):
                errors.append(
                    validation_issue(
                        row["row_number"],
                        "register_address",
                        (
                            "Modbus address conflicts with existing point "
                            f"{existing_address_point['id']}"
                        ),
                    )
                )

            if existing_point is None:
                continue

            if existing_point["protocol"] and existing_point["address"]:
                if (
                    existing_point["protocol"] == row["protocol"]
                    and existing_point["address"] == row["address"]
                ):
                    row["action"] = "skip_existing_point"
                    warnings.append(
                        validation_issue(
                            row["row_number"],
                            "point_name",
                            f"Point already has matching Modbus metadata: {row['point_id']}",
                        )
                    )
                else:
                    errors.append(
                        validation_issue(
                            row["row_number"],
                            "point_name",
                            (
                                "Point already exists with different protocol/address "
                                f"metadata: {row['point_id']}"
                            ),
                        )
                    )
                continue

            row["action"] = "update_point_metadata"
            warnings.append(
                validation_issue(
                    row["row_number"],
                    "point_name",
                    f"Existing point will be updated with Modbus metadata: {row['point_id']}",
                )
            )


def preview_summary(rows, raw_row_count, errors, warnings):
    """Return deterministic summary counts for a preview result."""
    invalid_row_numbers = {
        error["row_number"]
        for error in errors
        if error["row_number"] is not None
    }
    equipment_to_create = {
        row["equipment_id"]
        for row in rows
        if row["equipment_action"] == "create_equipment"
    }

    return {
        "total_rows": raw_row_count,
        "parsed_rows": len(rows),
        "valid_rows": max(raw_row_count - len(invalid_row_numbers), 0),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "would_create_equipment_count": len(equipment_to_create),
        "would_create_point_count": len(
            [
                row
                for row in rows
                if row["action"] == "create_point"
            ]
        ),
        "would_update_point_count": len(
            [
                row
                for row in rows
                if row["action"] == "update_point_metadata"
            ]
        ),
        "would_skip_point_count": len(
            [
                row
                for row in rows
                if row["action"] == "skip_existing_point"
            ]
        ),
    }


def preview_modbus_import(csv_path=None, db_path=None):
    """Parse and validate a static Modbus register map without database writes."""
    resolved_path, raw_rows, errors = read_csv_records(csv_path)
    warnings = []
    normalized_rows = []

    for index, raw_row in enumerate(raw_rows, start=2):
        row_errors_before = len(errors)
        normalized_row = normalized_import_row(raw_row, index, errors)
        if normalized_row is not None and len(errors) == row_errors_before:
            normalized_rows.append(normalized_row)

    add_duplicate_import_issues(normalized_rows, errors)
    add_existing_metadata_issues(normalized_rows, db_path, errors, warnings)

    return {
        "csv_path": str(resolved_path),
        "rows": normalized_rows,
        "errors": errors,
        "warnings": warnings,
        "summary": preview_summary(normalized_rows, len(raw_rows), errors, warnings),
    }


def point_exists_with_connection(connection, point_id):
    """Return existing point protocol/address metadata inside a transaction."""
    cursor = connection.execute(
        """
        SELECT protocol, address
        FROM points
        WHERE id = ?
        """,
        (point_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    return {
        "protocol": row[0] or "",
        "address": row[1] or "",
    }


def insert_equipment_if_needed(connection, row):
    """Create imported equipment when not already present."""
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO equipment (
            equipment,
            equipment_type,
            location,
            criticality,
            source_system,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            row["equipment_id"],
            row["equipment_type"],
            row["location"],
            row["criticality"],
            row["source_system"],
            "Imported from static Modbus register map",
        ),
    )
    return cursor.rowcount == 1


def insert_point(connection, row, timestamp):
    """Create one imported point catalog record."""
    connection.execute(
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
            protocol,
            address,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["point_id"],
            row["equipment_id"],
            row["point_name"],
            row["display_name"],
            row["point_type"],
            row["data_type"],
            row["unit"],
            None,
            None,
            row["source_system"],
            row["description"],
            row["protocol"],
            row["address"],
            timestamp,
            timestamp,
        ),
    )


def update_existing_point_metadata(connection, row, timestamp):
    """Fill blank protocol/address metadata on an existing point."""
    connection.execute(
        """
        UPDATE points
        SET protocol = ?,
            address = ?,
            unit = CASE WHEN unit = '' THEN ? ELSE unit END,
            description = CASE WHEN description = '' THEN ? ELSE description END,
            source_system = CASE WHEN source_system = '' THEN ? ELSE source_system END,
            updated_at = ?
        WHERE id = ?
        """,
        (
            row["protocol"],
            row["address"],
            row["unit"],
            row["description"],
            row["source_system"],
            timestamp,
            row["point_id"],
        ),
    )


def insert_commit_audit_event(connection, rows, result, timestamp, csv_path):
    """Append one catalog audit event for a committed static Modbus import."""
    if not rows:
        return

    anchor_row = rows[0]
    insert_alarm_event(
        connection,
        generated_alarm_id=None,
        rule_id=None,
        point_id=anchor_row["point_id"],
        equipment_id=anchor_row["equipment_id"],
        event_type="MODBUS_IMPORT_COMMITTED",
        event_timestamp=timestamp,
        acknowledged_by="local-operator",
        message=(
            "Static Modbus register map imported into equipment and point records"
        ),
        details={
            "csv_path": str(csv_path),
            "created_equipment_count": result["created_equipment_count"],
            "created_point_count": result["created_point_count"],
            "updated_point_count": result["updated_point_count"],
            "skipped_row_count": len(result["skipped_rows"]),
            "row_count": len(rows),
        },
    )


def commit_modbus_import(csv_path=None, db_path=None):
    """Validate again and commit imported equipment/point metadata transactionally."""
    preview = preview_modbus_import(csv_path, db_path=db_path)
    if preview["errors"]:
        return {
            **preview,
            "committed": False,
            "created_equipment_count": 0,
            "created_point_count": 0,
            "updated_point_count": 0,
            "skipped_rows": [],
        }

    if db_path is None:
        raise ValueError("db_path is required for commit")

    created_equipment = set()
    created_point_count = 0
    updated_point_count = 0
    skipped_rows = []
    timestamp = current_timestamp()
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        create_equipment_table(connection)
        create_point_table(connection)
        ensure_generated_alarm_table(connection)
        ensure_alarm_event_table(connection)
        with connection:
            if not connection.in_transaction:
                connection.execute("BEGIN")

            for row in preview["rows"]:
                if insert_equipment_if_needed(connection, row):
                    created_equipment.add(row["equipment_id"])

                existing_point = point_exists_with_connection(
                    connection,
                    row["point_id"],
                )
                if existing_point is None:
                    insert_point(connection, row, timestamp)
                    created_point_count += 1
                    continue

                if (
                    existing_point["protocol"] == row["protocol"]
                    and existing_point["address"] == row["address"]
                ):
                    skipped_rows.append(
                        {
                            "row_number": row["row_number"],
                            "point_id": row["point_id"],
                            "reason": "Point already has matching Modbus metadata",
                        }
                    )
                    continue

                update_existing_point_metadata(connection, row, timestamp)
                updated_point_count += 1

            result = {
                "created_equipment_count": len(created_equipment),
                "created_point_count": created_point_count,
                "updated_point_count": updated_point_count,
                "skipped_rows": skipped_rows,
            }
            insert_commit_audit_event(
                connection,
                preview["rows"],
                result,
                timestamp,
                preview["csv_path"],
            )

    return {
        **preview,
        "committed": True,
        "created_equipment_count": len(created_equipment),
        "created_point_count": created_point_count,
        "updated_point_count": updated_point_count,
        "skipped_rows": skipped_rows,
    }
