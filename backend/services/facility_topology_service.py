import sqlite3
from pathlib import Path


TOPOLOGY_TABLES_CHILD_FIRST = (
    "point_monitored_dependency_bindings",
    "point_shared_path_bindings",
    "point_pressure_boundary_bindings",
    "point_system_bindings",
    "point_zone_bindings",
    "pressure_boundary_cascade_order",
    "pressure_boundary_monitored_dependencies",
    "pressure_boundary_system_dependencies",
    "shared_path_monitored_dependencies",
    "equipment_shared_path_memberships",
    "system_zone_services",
    "equipment_system_memberships",
    "pressure_boundaries",
    "monitored_dependencies",
    "shared_system_paths",
    "facility_systems",
    "zones",
)


def create_facility_topology_tables(connection):
    """Create the additive Milestone 2 facility and typed-topology tables."""
    statements = (
        """
        CREATE TABLE IF NOT EXISTS facility_environments (
            singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
            facility_id TEXT NOT NULL UNIQUE,
            facility_name TEXT NOT NULL,
            fixture_version TEXT NOT NULL,
            manifest_path TEXT NOT NULL,
            loaded_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS zones (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS facility_systems (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            system_type TEXT NOT NULL,
            description TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS shared_system_paths (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            path_type TEXT NOT NULL,
            description TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS monitored_dependencies (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            dependency_type TEXT NOT NULL,
            monitoring_only INTEGER NOT NULL CHECK (monitoring_only = 1),
            description TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS pressure_boundaries (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            upstream_zone_id TEXT NOT NULL,
            downstream_zone_id TEXT NOT NULL,
            description TEXT NOT NULL,
            CHECK (upstream_zone_id <> downstream_zone_id),
            FOREIGN KEY (upstream_zone_id) REFERENCES zones (id),
            FOREIGN KEY (downstream_zone_id) REFERENCES zones (id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS equipment_system_memberships (
            equipment_id TEXT NOT NULL,
            system_id TEXT NOT NULL,
            equipment_role TEXT NOT NULL CHECK (
                equipment_role IN ('duty', 'standby')
            ),
            PRIMARY KEY (equipment_id, system_id),
            FOREIGN KEY (equipment_id) REFERENCES equipment (equipment),
            FOREIGN KEY (system_id) REFERENCES facility_systems (id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS system_zone_services (
            system_id TEXT NOT NULL,
            zone_id TEXT NOT NULL,
            PRIMARY KEY (system_id, zone_id),
            FOREIGN KEY (system_id) REFERENCES facility_systems (id),
            FOREIGN KEY (zone_id) REFERENCES zones (id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS equipment_shared_path_memberships (
            equipment_id TEXT NOT NULL,
            shared_path_id TEXT NOT NULL,
            PRIMARY KEY (equipment_id, shared_path_id),
            FOREIGN KEY (equipment_id) REFERENCES equipment (equipment),
            FOREIGN KEY (shared_path_id) REFERENCES shared_system_paths (id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS shared_path_monitored_dependencies (
            shared_path_id TEXT NOT NULL,
            dependency_id TEXT NOT NULL,
            PRIMARY KEY (shared_path_id, dependency_id),
            FOREIGN KEY (shared_path_id) REFERENCES shared_system_paths (id),
            FOREIGN KEY (dependency_id) REFERENCES monitored_dependencies (id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS pressure_boundary_system_dependencies (
            pressure_boundary_id TEXT NOT NULL,
            system_id TEXT NOT NULL,
            PRIMARY KEY (pressure_boundary_id, system_id),
            FOREIGN KEY (pressure_boundary_id) REFERENCES pressure_boundaries (id),
            FOREIGN KEY (system_id) REFERENCES facility_systems (id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS pressure_boundary_monitored_dependencies (
            pressure_boundary_id TEXT NOT NULL,
            dependency_id TEXT NOT NULL,
            PRIMARY KEY (pressure_boundary_id, dependency_id),
            FOREIGN KEY (pressure_boundary_id) REFERENCES pressure_boundaries (id),
            FOREIGN KEY (dependency_id) REFERENCES monitored_dependencies (id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS pressure_boundary_cascade_order (
            upstream_boundary_id TEXT NOT NULL,
            downstream_boundary_id TEXT NOT NULL,
            PRIMARY KEY (upstream_boundary_id, downstream_boundary_id),
            CHECK (upstream_boundary_id <> downstream_boundary_id),
            FOREIGN KEY (upstream_boundary_id) REFERENCES pressure_boundaries (id),
            FOREIGN KEY (downstream_boundary_id) REFERENCES pressure_boundaries (id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS point_zone_bindings (
            point_id TEXT PRIMARY KEY,
            zone_id TEXT NOT NULL,
            FOREIGN KEY (point_id) REFERENCES points (id),
            FOREIGN KEY (zone_id) REFERENCES zones (id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS point_system_bindings (
            point_id TEXT PRIMARY KEY,
            system_id TEXT NOT NULL,
            FOREIGN KEY (point_id) REFERENCES points (id),
            FOREIGN KEY (system_id) REFERENCES facility_systems (id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS point_pressure_boundary_bindings (
            point_id TEXT PRIMARY KEY,
            pressure_boundary_id TEXT NOT NULL,
            FOREIGN KEY (point_id) REFERENCES points (id),
            FOREIGN KEY (pressure_boundary_id) REFERENCES pressure_boundaries (id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS point_shared_path_bindings (
            point_id TEXT PRIMARY KEY,
            shared_path_id TEXT NOT NULL,
            FOREIGN KEY (point_id) REFERENCES points (id),
            FOREIGN KEY (shared_path_id) REFERENCES shared_system_paths (id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS point_monitored_dependency_bindings (
            point_id TEXT PRIMARY KEY,
            dependency_id TEXT NOT NULL,
            FOREIGN KEY (point_id) REFERENCES points (id),
            FOREIGN KEY (dependency_id) REFERENCES monitored_dependencies (id)
        )
        """,
    )
    for statement in statements:
        connection.execute(statement)


def clear_topology_rows(connection):
    """Clear typed topology while leaving catalog and runtime tables to callers."""
    for table_name in TOPOLOGY_TABLES_CHILD_FIRST:
        connection.execute(f"DELETE FROM {table_name}")


def record_facility_environment(
    connection,
    facility_id,
    facility_name,
    fixture_version,
    manifest_path,
    loaded_at,
):
    """Replace the single active facility identity inside the caller transaction."""
    connection.execute("DELETE FROM facility_environments")
    connection.execute(
        """
        INSERT INTO facility_environments (
            singleton_id,
            facility_id,
            facility_name,
            fixture_version,
            manifest_path,
            loaded_at
        )
        VALUES (1, ?, ?, ?, ?, ?)
        """,
        (
            facility_id,
            facility_name,
            fixture_version,
            str(manifest_path),
            loaded_at,
        ),
    )


def get_facility_identity(db_path):
    """Return the exact active facility identity recorded in one SQLite database."""
    target_path = Path(db_path)
    if not target_path.is_file():
        raise LookupError(f"Database not found: {target_path}")

    with sqlite3.connect(target_path) as connection:
        connection.row_factory = sqlite3.Row
        table_exists = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'facility_environments'
            """
        ).fetchone()
        if table_exists is None:
            raise LookupError("Database has no recorded facility environment")

        rows = connection.execute(
            """
            SELECT facility_id, facility_name, fixture_version
            FROM facility_environments
            ORDER BY singleton_id
            """
        ).fetchall()

    if len(rows) != 1:
        raise LookupError(
            "Database must contain exactly one recorded facility environment"
        )

    return dict(rows[0])


def _rows_as_dicts(connection, query, parameters=()):
    return [dict(row) for row in connection.execute(query, parameters).fetchall()]


def _point_bindings(connection, table_name, target_column, target_type):
    trusted_bindings = {
        "point_zone_bindings": "zone_id",
        "point_system_bindings": "system_id",
        "point_pressure_boundary_bindings": "pressure_boundary_id",
        "point_shared_path_bindings": "shared_path_id",
        "point_monitored_dependency_bindings": "dependency_id",
    }
    if trusted_bindings.get(table_name) != target_column:
        raise ValueError("Unsupported typed point binding query")

    rows = _rows_as_dicts(
        connection,
        f"""
        SELECT
            binding.point_id,
            points.equipment_id,
            points.point_name,
            points.display_name,
            points.point_type,
            binding.{target_column} AS target_id
        FROM {table_name} AS binding
        JOIN points ON points.id = binding.point_id
        ORDER BY binding.{target_column}, binding.point_id
        """,
    )
    for row in rows:
        row["target_type"] = target_type
    return rows


def get_facility_topology(db_path):
    """Return a deterministic, inspectable view of the active facility topology."""
    identity = get_facility_identity(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row

        zones = _rows_as_dicts(
            connection,
            "SELECT id, name, description FROM zones ORDER BY id",
        )
        systems = _rows_as_dicts(
            connection,
            """
            SELECT id, name, system_type, description
            FROM facility_systems
            ORDER BY id
            """,
        )
        boundaries = _rows_as_dicts(
            connection,
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
            """,
        )
        cascade_order = _rows_as_dicts(
            connection,
            """
            SELECT upstream_boundary_id, downstream_boundary_id
            FROM pressure_boundary_cascade_order
            ORDER BY upstream_boundary_id, downstream_boundary_id
            """,
        )

        ordered_boundary_ids = []
        if cascade_order:
            upstream_ids = {row["upstream_boundary_id"] for row in cascade_order}
            downstream_ids = {row["downstream_boundary_id"] for row in cascade_order}
            starts = sorted(upstream_ids - downstream_ids)
            if len(starts) == 1:
                current = starts[0]
                ordered_boundary_ids.append(current)
                links = {
                    row["upstream_boundary_id"]: row["downstream_boundary_id"]
                    for row in cascade_order
                }
                while current in links:
                    current = links[current]
                    ordered_boundary_ids.append(current)
        elif len(boundaries) == 1:
            ordered_boundary_ids = [boundaries[0]["id"]]

        boundary_by_id = {row["id"]: row for row in boundaries}
        ordered_boundaries = [
            {"cascade_position": position, **boundary_by_id[boundary_id]}
            for position, boundary_id in enumerate(ordered_boundary_ids, start=1)
        ]
        zone_by_id = {row["id"]: row for row in zones}
        ordered_zone_ids = []
        if ordered_boundaries:
            ordered_zone_ids.append(ordered_boundaries[0]["upstream_zone_id"])
            ordered_zone_ids.extend(
                row["downstream_zone_id"] for row in ordered_boundaries
            )
        ordered_zones = [
            {
                "cascade_position": position,
                **zone_by_id[zone_id],
            }
            for position, zone_id in enumerate(ordered_zone_ids, start=1)
        ]

        equipment_memberships = _rows_as_dicts(
            connection,
            """
            SELECT
                membership.equipment_id,
                equipment.equipment_type,
                equipment.location,
                membership.system_id,
                membership.equipment_role
            FROM equipment_system_memberships AS membership
            JOIN equipment ON equipment.equipment = membership.equipment_id
            ORDER BY membership.system_id, membership.equipment_role,
                     membership.equipment_id
            """,
        )
        system_zone_services = _rows_as_dicts(
            connection,
            """
            SELECT service.system_id, service.zone_id, zones.name AS zone_name
            FROM system_zone_services AS service
            JOIN zones ON zones.id = service.zone_id
            ORDER BY service.system_id, service.zone_id
            """,
        )
        shared_paths = _rows_as_dicts(
            connection,
            """
            SELECT id, name, path_type, description
            FROM shared_system_paths
            ORDER BY id
            """,
        )
        equipment_shared_paths = _rows_as_dicts(
            connection,
            """
            SELECT equipment_id, shared_path_id
            FROM equipment_shared_path_memberships
            ORDER BY equipment_id, shared_path_id
            """,
        )
        shared_path_dependencies = _rows_as_dicts(
            connection,
            """
            SELECT
                relationship.shared_path_id,
                relationship.dependency_id,
                dependency.name AS dependency_name,
                dependency.dependency_type,
                dependency.monitoring_only
            FROM shared_path_monitored_dependencies AS relationship
            JOIN monitored_dependencies AS dependency
              ON dependency.id = relationship.dependency_id
            ORDER BY relationship.shared_path_id, relationship.dependency_id
            """,
        )
        boundary_system_dependencies = _rows_as_dicts(
            connection,
            """
            SELECT pressure_boundary_id, system_id
            FROM pressure_boundary_system_dependencies
            ORDER BY pressure_boundary_id, system_id
            """,
        )
        boundary_monitored_dependencies = _rows_as_dicts(
            connection,
            """
            SELECT
                relationship.pressure_boundary_id,
                relationship.dependency_id,
                dependency.name AS dependency_name,
                dependency.dependency_type,
                dependency.monitoring_only
            FROM pressure_boundary_monitored_dependencies AS relationship
            JOIN monitored_dependencies AS dependency
              ON dependency.id = relationship.dependency_id
            ORDER BY relationship.pressure_boundary_id, relationship.dependency_id
            """,
        )
        point_bindings = {
            "zones": _point_bindings(
                connection,
                "point_zone_bindings",
                "zone_id",
                "zone",
            ),
            "systems": _point_bindings(
                connection,
                "point_system_bindings",
                "system_id",
                "system",
            ),
            "pressure_boundaries": _point_bindings(
                connection,
                "point_pressure_boundary_bindings",
                "pressure_boundary_id",
                "pressure_boundary",
            ),
            "shared_paths": _point_bindings(
                connection,
                "point_shared_path_bindings",
                "shared_path_id",
                "shared_path",
            ),
            "monitored_dependencies": _point_bindings(
                connection,
                "point_monitored_dependency_bindings",
                "dependency_id",
                "monitored_dependency",
            ),
        }

    return {
        **identity,
        "zones": zones,
        "systems": systems,
        "pressure_cascade": {
            "ordered_zones": ordered_zones,
            "ordered_boundaries": ordered_boundaries,
            "cascade_order": cascade_order,
        },
        "process_exhaust": {
            "equipment_memberships": equipment_memberships,
            "system_zone_services": system_zone_services,
            "shared_paths": shared_paths,
            "equipment_shared_paths": equipment_shared_paths,
            "shared_path_monitored_dependencies": shared_path_dependencies,
            "pressure_boundary_system_dependencies": (
                boundary_system_dependencies
            ),
            "pressure_boundary_monitored_dependencies": (
                boundary_monitored_dependencies
            ),
        },
        "point_bindings": point_bindings,
    }
