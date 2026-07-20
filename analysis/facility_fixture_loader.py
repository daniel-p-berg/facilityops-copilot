import argparse
import csv
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

from analysis import load_alarm_db
from backend.services.facility_package_registry import FLAGSHIP_FACILITY_ID
from backend.services.facility_package_registry import FLAGSHIP_FACILITY_NAME
from backend.services.facility_package_registry import FLAGSHIP_FIXTURE_VERSION
from backend.services.facility_package_registry import manifest_identity
from backend.services.facility_package_registry import read_manifest
from backend.services.facility_package_registry import resolve_manifest_file
from backend.services.facility_topology_service import clear_topology_rows
from backend.services.facility_topology_service import create_facility_topology_tables
from backend.services.facility_topology_service import get_facility_topology
from backend.services.facility_topology_service import record_facility_environment


MANIFEST_SCHEMA_VERSION = 1
FLAGSHIP_PACKAGE_TYPE = "minimum_flagship_topology"
STABLE_ID_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]*$")
FIXTURE_VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
IDENTITY_COLUMNS = ("facility_id", "fixture_version")

FILE_DEFINITIONS = {
    "equipment": {
        "table": "equipment",
        "columns": load_alarm_db.EQUIPMENT_COLUMNS,
    },
    "points": {
        "table": "points",
        "columns": load_alarm_db.POINT_COLUMNS,
    },
    "zones": {
        "table": "zones",
        "columns": ("id", "name", "description"),
    },
    "systems": {
        "table": "facility_systems",
        "columns": ("id", "name", "system_type", "description"),
    },
    "pressure_boundaries": {
        "table": "pressure_boundaries",
        "columns": (
            "id",
            "name",
            "upstream_zone_id",
            "downstream_zone_id",
            "description",
        ),
    },
    "shared_system_paths": {
        "table": "shared_system_paths",
        "columns": ("id", "name", "path_type", "description"),
    },
    "monitored_dependencies": {
        "table": "monitored_dependencies",
        "columns": (
            "id",
            "name",
            "dependency_type",
            "monitoring_only",
            "description",
        ),
    },
    "equipment_system_memberships": {
        "table": "equipment_system_memberships",
        "columns": ("equipment_id", "system_id", "equipment_role"),
    },
    "system_zone_services": {
        "table": "system_zone_services",
        "columns": ("system_id", "zone_id"),
    },
    "equipment_shared_path_memberships": {
        "table": "equipment_shared_path_memberships",
        "columns": ("equipment_id", "shared_path_id"),
    },
    "shared_path_monitored_dependencies": {
        "table": "shared_path_monitored_dependencies",
        "columns": ("shared_path_id", "dependency_id"),
    },
    "pressure_boundary_system_dependencies": {
        "table": "pressure_boundary_system_dependencies",
        "columns": ("pressure_boundary_id", "system_id"),
    },
    "pressure_boundary_monitored_dependencies": {
        "table": "pressure_boundary_monitored_dependencies",
        "columns": ("pressure_boundary_id", "dependency_id"),
    },
    "pressure_boundary_cascade_order": {
        "table": "pressure_boundary_cascade_order",
        "columns": ("upstream_boundary_id", "downstream_boundary_id"),
    },
    "point_zone_bindings": {
        "table": "point_zone_bindings",
        "columns": ("point_id", "zone_id"),
    },
    "point_system_bindings": {
        "table": "point_system_bindings",
        "columns": ("point_id", "system_id"),
    },
    "point_pressure_boundary_bindings": {
        "table": "point_pressure_boundary_bindings",
        "columns": ("point_id", "pressure_boundary_id"),
    },
    "point_shared_path_bindings": {
        "table": "point_shared_path_bindings",
        "columns": ("point_id", "shared_path_id"),
    },
    "point_monitored_dependency_bindings": {
        "table": "point_monitored_dependency_bindings",
        "columns": ("point_id", "dependency_id"),
    },
}

OPTIONAL_FILE_ROLES = {"current_point_values"}
EXPECTED_FILE_ROLES = set(FILE_DEFINITIONS) | OPTIONAL_FILE_ROLES

ENTITY_ID_FIELDS = {
    "equipment": "equipment",
    "points": "id",
    "zones": "id",
    "systems": "id",
    "pressure_boundaries": "id",
    "shared_system_paths": "id",
    "monitored_dependencies": "id",
}

REFERENCE_RULES = {
    "points": (("equipment_id", "equipment"),),
    "pressure_boundaries": (
        ("upstream_zone_id", "zones"),
        ("downstream_zone_id", "zones"),
    ),
    "equipment_system_memberships": (
        ("equipment_id", "equipment"),
        ("system_id", "systems"),
    ),
    "system_zone_services": (
        ("system_id", "systems"),
        ("zone_id", "zones"),
    ),
    "equipment_shared_path_memberships": (
        ("equipment_id", "equipment"),
        ("shared_path_id", "shared_system_paths"),
    ),
    "shared_path_monitored_dependencies": (
        ("shared_path_id", "shared_system_paths"),
        ("dependency_id", "monitored_dependencies"),
    ),
    "pressure_boundary_system_dependencies": (
        ("pressure_boundary_id", "pressure_boundaries"),
        ("system_id", "systems"),
    ),
    "pressure_boundary_monitored_dependencies": (
        ("pressure_boundary_id", "pressure_boundaries"),
        ("dependency_id", "monitored_dependencies"),
    ),
    "pressure_boundary_cascade_order": (
        ("upstream_boundary_id", "pressure_boundaries"),
        ("downstream_boundary_id", "pressure_boundaries"),
    ),
    "point_zone_bindings": (
        ("point_id", "points"),
        ("zone_id", "zones"),
    ),
    "point_system_bindings": (
        ("point_id", "points"),
        ("system_id", "systems"),
    ),
    "point_pressure_boundary_bindings": (
        ("point_id", "points"),
        ("pressure_boundary_id", "pressure_boundaries"),
    ),
    "point_shared_path_bindings": (
        ("point_id", "points"),
        ("shared_path_id", "shared_system_paths"),
    ),
    "point_monitored_dependency_bindings": (
        ("point_id", "points"),
        ("dependency_id", "monitored_dependencies"),
    ),
}

REQUIRED_ENTITY_IDS = {
    "zones": {
        "ZONE-REFERENCE-CORRIDOR",
        "ZONE-TRANSITION-AIRLOCK",
        "ZONE-PROCESS-LAB",
    },
    "systems": {"SYSTEM-PROCESS-EXHAUST"},
    "pressure_boundaries": {
        "BOUNDARY-CORRIDOR-TRANSITION",
        "BOUNDARY-TRANSITION-LAB",
    },
    "shared_system_paths": {"PATH-EXHAUST-SHARED"},
    "monitored_dependencies": {
        "PERMISSIVE-TREATMENT",
        "DEPENDENCY-SUPPLY-MAKEUP",
    },
}

REQUIRED_RELATIONSHIPS = {
    "equipment_system_memberships": {
        ("FAN-EXHAUST-DUTY", "SYSTEM-PROCESS-EXHAUST", "duty"),
        ("FAN-EXHAUST-STANDBY", "SYSTEM-PROCESS-EXHAUST", "standby"),
    },
    "system_zone_services": {
        ("SYSTEM-PROCESS-EXHAUST", "ZONE-PROCESS-LAB"),
    },
    "equipment_shared_path_memberships": {
        ("FAN-EXHAUST-DUTY", "PATH-EXHAUST-SHARED"),
        ("FAN-EXHAUST-STANDBY", "PATH-EXHAUST-SHARED"),
    },
    "shared_path_monitored_dependencies": {
        ("PATH-EXHAUST-SHARED", "PERMISSIVE-TREATMENT"),
    },
    "pressure_boundary_system_dependencies": {
        ("BOUNDARY-TRANSITION-LAB", "SYSTEM-PROCESS-EXHAUST"),
    },
    "pressure_boundary_monitored_dependencies": {
        ("BOUNDARY-CORRIDOR-TRANSITION", "DEPENDENCY-SUPPLY-MAKEUP"),
        ("BOUNDARY-TRANSITION-LAB", "DEPENDENCY-SUPPLY-MAKEUP"),
    },
    "pressure_boundary_cascade_order": {
        ("BOUNDARY-CORRIDOR-TRANSITION", "BOUNDARY-TRANSITION-LAB"),
    },
}

REQUIRED_BOUNDARY_DIRECTIONS = {
    "BOUNDARY-CORRIDOR-TRANSITION": (
        "ZONE-REFERENCE-CORRIDOR",
        "ZONE-TRANSITION-AIRLOCK",
    ),
    "BOUNDARY-TRANSITION-LAB": (
        "ZONE-TRANSITION-AIRLOCK",
        "ZONE-PROCESS-LAB",
    ),
}

REQUIRED_POINT_CATEGORY_COUNTS = {
    "fan_availability": 2,
    "run_status": 2,
    "fault_status": 2,
    "speed_feedback": 2,
    "exhaust_airflow": 1,
    "duct_static": 1,
    "damper_position": 1,
    "treatment_permissive": 1,
    "supply_makeup_status": 1,
    "zone_pressure": 1,
    "differential_pressure": 2,
}

EXPECTED_POINT_BINDINGS = {
    "point_zone_bindings": {
        ("PROCESS-LAB_ZONE_PRESSURE", "ZONE-PROCESS-LAB"),
    },
    "point_system_bindings": {
        ("PROCESS-EXHAUST_AIRFLOW", "SYSTEM-PROCESS-EXHAUST"),
    },
    "point_pressure_boundary_bindings": {
        (
            "CORRIDOR-TRANSITION_DIFFERENTIAL_PRESSURE",
            "BOUNDARY-CORRIDOR-TRANSITION",
        ),
        (
            "TRANSITION-LAB_DIFFERENTIAL_PRESSURE",
            "BOUNDARY-TRANSITION-LAB",
        ),
    },
    "point_shared_path_bindings": {
        ("EXHAUST-SHARED_DUCT_STATIC", "PATH-EXHAUST-SHARED"),
        ("EXHAUST-SHARED_DAMPER_POSITION", "PATH-EXHAUST-SHARED"),
    },
    "point_monitored_dependency_bindings": {
        ("TREATMENT_PERMISSIVE_STATUS", "PERMISSIVE-TREATMENT"),
        ("SUPPLY-MAKEUP_STATUS", "DEPENDENCY-SUPPLY-MAKEUP"),
    },
}


def _require_stable_id(value, context):
    if not isinstance(value, str) or not STABLE_ID_PATTERN.fullmatch(value):
        raise ValueError(
            f"{context} must be a stable uppercase identifier using A-Z, 0-9, _ or -"
        )


def _read_fixture_csv(csv_path, role, facility_id, fixture_version):
    definition = FILE_DEFINITIONS[role]
    expected_columns = IDENTITY_COLUMNS + definition["columns"]
    with csv_path.open(mode="r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        actual_columns = tuple(reader.fieldnames or ())
        if actual_columns != expected_columns:
            raise ValueError(
                f"Fixture file {role!r} columns must be {expected_columns}; "
                f"received {actual_columns}"
            )

        rows = []
        for row_number, source_row in enumerate(reader, start=2):
            if None in source_row:
                raise ValueError(
                    f"Unexpected extra values in {csv_path} row {row_number}"
                )
            row = {key: value.strip() for key, value in source_row.items()}
            if row["facility_id"] != facility_id:
                raise ValueError(
                    f"Cross-fixture row in {role} at row {row_number}: "
                    f"facility_id {row['facility_id']!r} does not match {facility_id!r}"
                )
            if row["fixture_version"] != fixture_version:
                raise ValueError(
                    f"Fixture-version mismatch in {role} at row {row_number}: "
                    f"{row['fixture_version']!r} does not match {fixture_version!r}"
                )

            normalized = {column: row[column] for column in definition["columns"]}
            if role == "points":
                for field_name in ("normal_min", "normal_max"):
                    normalized[field_name] = (
                        None
                        if not normalized[field_name]
                        else float(normalized[field_name])
                    )
            if role == "monitored_dependencies":
                if normalized["monitoring_only"].lower() not in {
                    "1",
                    "true",
                    "yes",
                }:
                    raise ValueError(
                        "Monitored dependencies must be monitoring_only and cannot "
                        "represent a command"
                    )
                normalized["monitoring_only"] = 1
            rows.append(normalized)

    return rows


def _row_key(role, row):
    return tuple(row[column] for column in FILE_DEFINITIONS[role]["columns"])


def _validate_unique_rows(role, rows):
    keys = [_row_key(role, row) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError(f"Duplicate relationship row in fixture file {role!r}")


def _validate_entity_ids(rows_by_role):
    entity_ids = {}
    for role, id_field in ENTITY_ID_FIELDS.items():
        identifiers = []
        for row_number, row in enumerate(rows_by_role[role], start=2):
            identifier = row[id_field]
            _require_stable_id(identifier, f"{role} row {row_number} identifier")
            identifiers.append(identifier)
        duplicates = sorted(
            identifier
            for identifier, count in Counter(identifiers).items()
            if count > 1
        )
        if duplicates:
            raise ValueError(
                f"Duplicate identifiers in {role}: {', '.join(duplicates)}"
            )
        entity_ids[role] = set(identifiers)
    return entity_ids


def _validate_references(rows_by_role, entity_ids):
    for role, rules in REFERENCE_RULES.items():
        for row_number, row in enumerate(rows_by_role[role], start=2):
            for field_name, target_role in rules:
                reference = row[field_name]
                _require_stable_id(reference, f"{role} row {row_number} {field_name}")
                if reference not in entity_ids[target_role]:
                    raise ValueError(
                        "Cross-fixture or missing relationship reference in "
                        f"{role} row {row_number}: {field_name}={reference!r}"
                    )


def _validate_cascade(rows_by_role):
    links = rows_by_role["pressure_boundary_cascade_order"]
    next_by_boundary = {}
    downstream_ids = set()
    for row in links:
        upstream = row["upstream_boundary_id"]
        downstream = row["downstream_boundary_id"]
        if upstream == downstream:
            raise ValueError("Pressure-boundary cascade ordering cannot self-reference")
        if upstream in next_by_boundary:
            raise ValueError(
                "Pressure-boundary cascade ordering must be a single chain"
            )
        if downstream in downstream_ids:
            raise ValueError(
                "Pressure-boundary cascade ordering must be a single chain"
            )
        next_by_boundary[upstream] = downstream
        downstream_ids.add(downstream)

    for start in next_by_boundary:
        visited = set()
        current = start
        while current in next_by_boundary:
            if current in visited:
                raise ValueError("Pressure-boundary cascade ordering contains a cycle")
            visited.add(current)
            current = next_by_boundary[current]


def _validate_primary_point_bindings(rows_by_role):
    bound_points = []
    for role in EXPECTED_POINT_BINDINGS:
        role_point_ids = [row["point_id"] for row in rows_by_role[role]]
        if len(role_point_ids) != len(set(role_point_ids)):
            raise ValueError(f"Duplicate point binding in {role}")
        bound_points.extend(role_point_ids)

    duplicates = sorted(
        point_id
        for point_id, count in Counter(bound_points).items()
        if count > 1
    )
    if duplicates:
        raise ValueError(
            "A point may have only one primary topology binding: "
            + ", ".join(duplicates)
        )


def _relationship_tuples(role, rows):
    columns = FILE_DEFINITIONS[role]["columns"]
    return {tuple(row[column] for column in columns) for row in rows}


def _validate_required_flagship_topology(rows_by_role, entity_ids):
    for role, required_ids in REQUIRED_ENTITY_IDS.items():
        if entity_ids[role] != required_ids:
            raise ValueError(
                f"Incomplete minimum flagship {role}: expected "
                f"{sorted(required_ids)}, received {sorted(entity_ids[role])}"
            )

    required_fans = {"FAN-EXHAUST-DUTY", "FAN-EXHAUST-STANDBY"}
    if not required_fans.issubset(entity_ids["equipment"]):
        raise ValueError(
            "Minimum flagship equipment must include duty and standby fans"
        )

    boundary_by_id = {
        row["id"]: row for row in rows_by_role["pressure_boundaries"]
    }
    for boundary_id, expected_direction in REQUIRED_BOUNDARY_DIRECTIONS.items():
        row = boundary_by_id[boundary_id]
        actual_direction = (
            row["upstream_zone_id"],
            row["downstream_zone_id"],
        )
        if actual_direction[0] == actual_direction[1]:
            raise ValueError(f"Pressure boundary {boundary_id} cannot self-reference")
        if actual_direction != expected_direction:
            raise ValueError(
                f"Invalid pressure-boundary direction for {boundary_id}: "
                f"expected {expected_direction}, received {actual_direction}"
            )

    for row in rows_by_role["equipment_system_memberships"]:
        if row["equipment_role"] not in {"duty", "standby"}:
            raise ValueError(
                f"Invalid equipment role {row['equipment_role']!r}; "
                "allowed roles are duty and standby"
            )

    for role, required_rows in REQUIRED_RELATIONSHIPS.items():
        actual_rows = _relationship_tuples(role, rows_by_role[role])
        if actual_rows != required_rows:
            raise ValueError(
                f"Incomplete minimum flagship relationship {role}: expected "
                f"{sorted(required_rows)}, received {sorted(actual_rows)}"
            )

    point_category_counts = Counter(
        row["point_type"] for row in rows_by_role["points"]
    )
    if dict(sorted(point_category_counts.items())) != dict(
        sorted(REQUIRED_POINT_CATEGORY_COUNTS.items())
    ):
        raise ValueError(
            "Flagship point categories do not cover the accepted evidence inventory: "
            f"expected {REQUIRED_POINT_CATEGORY_COUNTS}, "
            f"received {dict(point_category_counts)}"
        )

    for role, expected_rows in EXPECTED_POINT_BINDINGS.items():
        actual_rows = _relationship_tuples(role, rows_by_role[role])
        if actual_rows != expected_rows:
            raise ValueError(
                f"Invalid typed point bindings for {role}: expected "
                f"{sorted(expected_rows)}, received {sorted(actual_rows)}"
            )


def read_and_validate_fixture(manifest_path):
    """Read and completely validate a flagship fixture before database mutation."""
    resolved_manifest_path, manifest = read_manifest(manifest_path)
    if manifest.get("manifest_schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported manifest_schema_version; expected {MANIFEST_SCHEMA_VERSION}"
        )
    if manifest.get("package_type") != FLAGSHIP_PACKAGE_TYPE:
        raise ValueError(
            f"Unsupported facility package type: {manifest.get('package_type')!r}"
        )

    identity = manifest_identity(manifest)
    _require_stable_id(identity["facility_id"], "facility_id")
    if not FIXTURE_VERSION_PATTERN.fullmatch(identity["fixture_version"]):
        raise ValueError("fixture_version must use MAJOR.MINOR.PATCH numeric format")
    expected_identity = {
        "facility_id": FLAGSHIP_FACILITY_ID,
        "facility_name": FLAGSHIP_FACILITY_NAME,
        "fixture_version": FLAGSHIP_FIXTURE_VERSION,
    }
    if identity != expected_identity:
        raise ValueError(
            "Minimum flagship manifest identity must remain stable: "
            f"expected {expected_identity}, received {identity}"
        )

    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ValueError("Fixture manifest must define a files object")
    if set(files) != EXPECTED_FILE_ROLES:
        raise ValueError(
            "Fixture manifest file roles must be exactly: "
            + ", ".join(sorted(EXPECTED_FILE_ROLES))
        )
    if files["current_point_values"] is not None:
        raise ValueError(
            "Milestone 2 flagship must not declare current-value observations"
        )

    rows_by_role = {}
    for role in FILE_DEFINITIONS:
        declaration = files[role]
        csv_path = resolve_manifest_file(resolved_manifest_path, declaration)
        if not csv_path.is_relative_to(resolved_manifest_path.parent):
            raise ValueError(
                f"Flagship fixture file {role!r} must stay inside its versioned package"
            )
        rows_by_role[role] = _read_fixture_csv(
            csv_path,
            role,
            identity["facility_id"],
            identity["fixture_version"],
        )

    entity_ids = _validate_entity_ids(rows_by_role)
    for role in FILE_DEFINITIONS:
        if role not in ENTITY_ID_FIELDS:
            _validate_unique_rows(role, rows_by_role[role])
    _validate_references(rows_by_role, entity_ids)
    _validate_cascade(rows_by_role)
    _validate_primary_point_bindings(rows_by_role)
    _validate_required_flagship_topology(rows_by_role, entity_ids)

    return {
        "manifest_path": resolved_manifest_path,
        "identity": identity,
        "rows": rows_by_role,
    }


def _create_application_tables(connection):
    load_alarm_db.create_alarm_table(connection)
    load_alarm_db.create_equipment_table(connection)
    load_alarm_db.create_point_table(connection)
    load_alarm_db.create_alarm_rule_table(connection)
    load_alarm_db.create_point_sample_table(connection)
    load_alarm_db.create_current_point_value_table(connection)
    load_alarm_db.create_generated_alarm_table(connection)
    load_alarm_db.create_alarm_event_table(connection)
    load_alarm_db.create_operational_context_tables(connection)
    create_facility_topology_tables(connection)


def _clear_database_rows(connection):
    for table_name in (
        "alarm_events",
        "generated_alarms",
        "current_point_values",
        "point_samples",
        "alarm_rules",
        "alarm_correlation_members",
        "alarm_correlations",
        "incident_timeline",
        "shift_turnover",
        "equipment_out_of_service",
        "corrective_actions",
        "procedure_references",
        "reliability_reports",
        "facility_scenarios",
    ):
        connection.execute(f"DELETE FROM {table_name}")
    clear_topology_rows(connection)
    connection.execute("DELETE FROM points")
    connection.execute("DELETE FROM equipment")
    connection.execute("DELETE FROM alarms")
    connection.execute("DELETE FROM facility_environments")


def _insert_fixture_rows(connection, fixture):
    for role, definition in FILE_DEFINITIONS.items():
        rows = fixture["rows"][role]
        columns = definition["columns"]
        column_sql = ", ".join(columns)
        placeholder_sql = ", ".join(f":{column}" for column in columns)
        connection.executemany(
            f"INSERT INTO {definition['table']} ({column_sql}) "
            f"VALUES ({placeholder_sql})",
            rows,
        )


def _normalized_db_value(value):
    if isinstance(value, float) and value.is_integer():
        return float(value)
    return value


def _validate_stored_fixture(connection, fixture):
    identity = fixture["identity"]
    stored_identity = [
        tuple(row)
        for row in connection.execute(
        """
        SELECT facility_id, facility_name, fixture_version
        FROM facility_environments
        ORDER BY singleton_id
        """
        ).fetchall()
    ]
    if stored_identity != [
        (
            identity["facility_id"],
            identity["facility_name"],
            identity["fixture_version"],
        )
    ]:
        raise RuntimeError("Post-load facility identity validation failed")

    for role, definition in FILE_DEFINITIONS.items():
        columns = definition["columns"]
        column_sql = ", ".join(columns)
        stored_rows = {
            tuple(_normalized_db_value(value) for value in row)
            for row in connection.execute(
                f"SELECT {column_sql} FROM {definition['table']}"
            ).fetchall()
        }
        expected_rows = {
            tuple(_normalized_db_value(row[column]) for column in columns)
            for row in fixture["rows"][role]
        }
        if stored_rows != expected_rows:
            raise RuntimeError(f"Post-load validation failed for {role}")

    binding_rows = connection.execute(
        """
        SELECT point_id FROM point_zone_bindings
        UNION ALL SELECT point_id FROM point_system_bindings
        UNION ALL SELECT point_id FROM point_pressure_boundary_bindings
        UNION ALL SELECT point_id FROM point_shared_path_bindings
        UNION ALL SELECT point_id FROM point_monitored_dependency_bindings
        """
    ).fetchall()
    bound_point_ids = [row[0] for row in binding_rows]
    if len(bound_point_ids) != len(set(bound_point_ids)):
        raise RuntimeError("Post-load primary point-binding cardinality failed")

    foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_errors:
        raise RuntimeError(
            f"Post-load SQLite foreign-key consistency failed: {foreign_key_errors}"
        )

    topology = get_facility_topology_with_connection(connection, identity)
    ordered_ids = [
        row["id"] for row in topology["pressure_cascade"]["ordered_boundaries"]
    ]
    if ordered_ids != [
        "BOUNDARY-CORRIDOR-TRANSITION",
        "BOUNDARY-TRANSITION-LAB",
    ]:
        raise RuntimeError("Post-load pressure-cascade chain validation failed")


def get_facility_topology_with_connection(connection, identity):
    """Query the uncommitted cascade through the active load connection."""
    boundaries = [
        dict(row)
        for row in connection.execute(
            """
            SELECT
                boundary.id,
                boundary.name,
                boundary.upstream_zone_id,
                upstream.name AS upstream_zone_name,
                boundary.downstream_zone_id,
                downstream.name AS downstream_zone_name,
                boundary.description
            FROM pressure_boundaries AS boundary
            JOIN zones AS upstream ON upstream.id = boundary.upstream_zone_id
            JOIN zones AS downstream ON downstream.id = boundary.downstream_zone_id
            ORDER BY boundary.id
            """
        ).fetchall()
    ]
    links = [
        dict(row)
        for row in connection.execute(
            """
            SELECT upstream_boundary_id, downstream_boundary_id
            FROM pressure_boundary_cascade_order
            ORDER BY upstream_boundary_id, downstream_boundary_id
            """
        ).fetchall()
    ]
    boundary_by_id = {row["id"]: row for row in boundaries}
    ordered = []
    if links:
        downstream_ids = {row["downstream_boundary_id"] for row in links}
        starts = sorted(
            {row["upstream_boundary_id"] for row in links} - downstream_ids
        )
        if len(starts) == 1:
            next_by_id = {
                row["upstream_boundary_id"]: row["downstream_boundary_id"]
                for row in links
            }
            current = starts[0]
            while True:
                ordered.append(boundary_by_id[current])
                if current not in next_by_id:
                    break
                current = next_by_id[current]
    return {
        **identity,
        "pressure_cascade": {
            "ordered_boundaries": [
                {"cascade_position": index, **row}
                for index, row in enumerate(ordered, start=1)
            ],
            "cascade_order": links,
        },
    }


def load_facility_fixture(manifest_path, db_path):
    """Validate and atomically load one explicitly selected flagship database."""
    fixture = read_and_validate_fixture(manifest_path)
    target_path = Path(db_path).resolve()
    if target_path == load_alarm_db.DATABASE_FILE.resolve():
        raise ValueError(
            "Flagship fixture loading requires an explicitly selected isolated "
            "database; the normal project database is not an allowed target"
        )

    target_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(target_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.isolation_level = None
        try:
            connection.execute("BEGIN IMMEDIATE")
            _create_application_tables(connection)
            _clear_database_rows(connection)
            _insert_fixture_rows(connection, fixture)
            record_facility_environment(
                connection,
                **fixture["identity"],
                manifest_path=fixture["manifest_path"],
                loaded_at=load_alarm_db.current_timestamp(),
            )
            _validate_stored_fixture(connection, fixture)
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    counts = {
        f"{role}_records": len(fixture["rows"][role])
        for role in FILE_DEFINITIONS
    }
    counts.update(
        {
            "facility_environment_records": 1,
            "current_point_value_records": 0,
            "point_sample_records": 0,
        }
    )
    return {
        **fixture["identity"],
        "database": str(target_path),
        "record_counts": counts,
    }


def _build_parser():
    parser = argparse.ArgumentParser(
        description="Load or query an explicitly selected facility fixture database"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    load_parser = subparsers.add_parser("load", help="Validate and load a fixture")
    load_parser.add_argument("--manifest", required=True, type=Path)
    load_parser.add_argument("--db", required=True, type=Path)

    query_parser = subparsers.add_parser("query", help="Query stored topology")
    query_parser.add_argument("--db", required=True, type=Path)
    return parser


def main():
    args = _build_parser().parse_args()
    if args.command == "load":
        result = load_facility_fixture(args.manifest, args.db)
    else:
        result = get_facility_topology(args.db)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
