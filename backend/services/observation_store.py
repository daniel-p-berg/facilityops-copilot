"""Append-only SQLite persistence for synthetic observation replay evidence.

This store is deliberately separate from the legacy operational database.
Application import does not initialize it, and the legacy operational reset
does not open it.
"""

from __future__ import annotations

import json
import re
import sqlite3
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from backend.domain.observation_semantics import (
    ORDER_AFTER,
    ORDER_BEFORE,
    ORDER_EQUAL,
    TIMESTAMP_INVALID,
    TIMESTAMP_MISSING,
    TIMESTAMP_VALID,
    compare_rfc3339_instants,
    parse_rfc3339_timestamp,
    require_valid_rfc3339_utc,
)


SCHEMA_VERSION = 1
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 50
MAX_JSON_TEXT_BYTES = 1_048_576
_SQLITE_MAX_INTEGER = (1 << 63) - 1
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OBSERVATION_DATABASE_FILE = (
    PROJECT_ROOT / "db" / "facilityops-observations.sqlite3"
)

_LOWERCASE_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ObservationStoreError(RuntimeError):
    """Base error for observation-store persistence failures."""


class IdempotencyConflictError(ObservationStoreError):
    """Raised when an idempotency key is reused for different content."""


class ImmutableIdentityConflictError(ObservationStoreError):
    """Raised when a versioned identity is reused with another digest."""


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS observation_store_metadata (
        singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
        schema_version INTEGER NOT NULL CHECK (schema_version >= 1)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS topology_snapshots (
        topology_id TEXT NOT NULL,
        topology_version TEXT NOT NULL,
        content_digest TEXT NOT NULL,
        facility_id TEXT NOT NULL,
        manifest_json TEXT NOT NULL,
        PRIMARY KEY (topology_id, topology_version),
        UNIQUE (topology_id, topology_version, content_digest),
        UNIQUE (
            facility_id,
            topology_id,
            topology_version,
            content_digest
        )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_bindings (
        facility_id TEXT NOT NULL,
        source_binding_id TEXT NOT NULL,
        source_id TEXT NOT NULL,
        channel TEXT NOT NULL,
        dependency_provenance_json TEXT NOT NULL,
        PRIMARY KEY (facility_id, source_binding_id),
        UNIQUE (facility_id, source_id, channel)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS mapping_snapshots (
        mapping_id TEXT NOT NULL,
        mapping_version TEXT NOT NULL,
        content_digest TEXT NOT NULL,
        facility_id TEXT NOT NULL,
        topology_id TEXT NOT NULL,
        topology_version TEXT NOT NULL,
        topology_digest TEXT NOT NULL,
        source_binding_id TEXT NOT NULL,
        definition_json TEXT NOT NULL,
        PRIMARY KEY (mapping_id, mapping_version),
        UNIQUE (mapping_id, mapping_version, content_digest),
        UNIQUE (
            facility_id,
            mapping_id,
            mapping_version,
            content_digest
        ),
        FOREIGN KEY (
            facility_id,
            topology_id,
            topology_version,
            topology_digest
        ) REFERENCES topology_snapshots (
            facility_id,
            topology_id,
            topology_version,
            content_digest
        ),
        FOREIGN KEY (
            facility_id,
            source_binding_id
        ) REFERENCES source_bindings (
            facility_id,
            source_binding_id
        )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS replay_package_snapshots (
        package_id TEXT NOT NULL,
        package_version TEXT NOT NULL,
        content_digest TEXT NOT NULL,
        facility_id TEXT NOT NULL,
        topology_id TEXT NOT NULL,
        topology_version TEXT NOT NULL,
        topology_digest TEXT NOT NULL,
        manifest_json TEXT NOT NULL,
        PRIMARY KEY (package_id, package_version),
        UNIQUE (package_id, package_version, content_digest),
        UNIQUE (
            facility_id,
            package_id,
            package_version,
            content_digest
        ),
        FOREIGN KEY (
            facility_id,
            topology_id,
            topology_version,
            topology_digest
        ) REFERENCES topology_snapshots (
            facility_id,
            topology_id,
            topology_version,
            content_digest
        )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS replay_executions (
        replay_execution_id TEXT PRIMARY KEY,
        facility_id TEXT NOT NULL,
        package_id TEXT NOT NULL,
        package_version TEXT NOT NULL,
        package_digest TEXT NOT NULL,
        topology_id TEXT NOT NULL,
        topology_version TEXT NOT NULL,
        topology_digest TEXT NOT NULL,
        canonicalizer_version TEXT NOT NULL,
        request_digest TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status = 'COMPLETED'),
        recorded_at TEXT NOT NULL,
        normalized_semantic_digest TEXT NOT NULL,
        UNIQUE (replay_execution_id, facility_id),
        FOREIGN KEY (
            facility_id,
            package_id,
            package_version,
            package_digest
        ) REFERENCES replay_package_snapshots (
            facility_id,
            package_id,
            package_version,
            content_digest
        ),
        FOREIGN KEY (
            facility_id,
            topology_id,
            topology_version,
            topology_digest
        ) REFERENCES topology_snapshots (
            facility_id,
            topology_id,
            topology_version,
            content_digest
        )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS replay_execution_requests (
        facility_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        request_digest TEXT NOT NULL,
        replay_execution_id TEXT NOT NULL,
        PRIMARY KEY (facility_id, idempotency_key),
        UNIQUE (replay_execution_id, idempotency_key),
        FOREIGN KEY (replay_execution_id, facility_id)
            REFERENCES replay_executions (
                replay_execution_id,
                facility_id
            )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_event_groups (
        replay_execution_id TEXT NOT NULL,
        source_event_group_key TEXT NOT NULL,
        facility_id TEXT NOT NULL,
        source_binding_id TEXT NOT NULL,
        identity_kind TEXT NOT NULL CHECK (
            identity_kind IN (
                'SOURCE_EVENT_ID',
                'SEQUENCE_IN_DECLARED_EPOCH',
                'NO_STABLE_ID'
            )
        ),
        source_event_id TEXT,
        source_session_epoch TEXT,
        source_sequence INTEGER,
        CHECK (
            (identity_kind = 'SOURCE_EVENT_ID'
                AND source_event_id IS NOT NULL)
            OR
            (identity_kind = 'SEQUENCE_IN_DECLARED_EPOCH'
                AND source_event_id IS NULL
                AND source_session_epoch IS NOT NULL
                AND source_sequence IS NOT NULL)
            OR
            (identity_kind = 'NO_STABLE_ID'
                AND source_event_id IS NULL)
        ),
        PRIMARY KEY (replay_execution_id, source_event_group_key),
        UNIQUE (
            replay_execution_id,
            source_event_group_key,
            facility_id,
            source_binding_id
        ),
        FOREIGN KEY (replay_execution_id, facility_id)
            REFERENCES replay_executions (
                replay_execution_id,
                facility_id
            ),
        FOREIGN KEY (facility_id, source_binding_id)
            REFERENCES source_bindings (facility_id, source_binding_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS replay_deliveries (
        replay_execution_id TEXT NOT NULL,
        delivery_id TEXT NOT NULL,
        facility_id TEXT NOT NULL,
        ingestion_ordinal INTEGER NOT NULL CHECK (ingestion_ordinal > 0),
        idempotency_key TEXT NOT NULL,
        request_digest TEXT NOT NULL,
        source_binding_id TEXT NOT NULL,
        source_event_group_key TEXT NOT NULL,
        redelivery_classification TEXT NOT NULL CHECK (
            redelivery_classification IN (
                'NEW_EVENT',
                'NO_STABLE_ID',
                'EXACT_REDELIVERY',
                'CONFLICTING_REDELIVERY'
            )
        ),
        received_at_utc TEXT NOT NULL,
        source_native_record_id TEXT NOT NULL UNIQUE,
        PRIMARY KEY (replay_execution_id, delivery_id),
        UNIQUE (replay_execution_id, ingestion_ordinal),
        UNIQUE (replay_execution_id, idempotency_key),
        UNIQUE (
            replay_execution_id,
            delivery_id,
            facility_id,
            source_binding_id,
            source_event_group_key
        ),
        FOREIGN KEY (replay_execution_id, facility_id)
            REFERENCES replay_executions (
                replay_execution_id,
                facility_id
            ),
        FOREIGN KEY (facility_id, source_binding_id)
            REFERENCES source_bindings (facility_id, source_binding_id),
        FOREIGN KEY (
            replay_execution_id,
            source_event_group_key,
            facility_id,
            source_binding_id
        ) REFERENCES source_event_groups (
            replay_execution_id,
            source_event_group_key,
            facility_id,
            source_binding_id
        ),
        FOREIGN KEY (
            replay_execution_id,
            delivery_id,
            source_native_record_id
        ) REFERENCES source_native_records (
            replay_execution_id,
            delivery_id,
            source_native_record_id
        )
            DEFERRABLE INITIALLY DEFERRED
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_native_records (
        source_native_record_id TEXT PRIMARY KEY,
        replay_execution_id TEXT NOT NULL,
        delivery_id TEXT NOT NULL,
        facility_id TEXT NOT NULL,
        source_binding_id TEXT NOT NULL,
        source_event_group_key TEXT NOT NULL,
        source_event_variant_digest TEXT NOT NULL,
        mapping_id TEXT NOT NULL,
        mapping_version TEXT NOT NULL,
        mapping_digest TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        payload_digest TEXT NOT NULL,
        original_observed_at_text TEXT,
        original_timezone_offset TEXT,
        timestamp_precision TEXT,
        fractional_second_digits INTEGER,
        observed_at_status TEXT NOT NULL CHECK (
            observed_at_status IN ('VALID', 'MISSING', 'INVALID')
        ),
        observed_at_utc TEXT,
        received_at_utc TEXT NOT NULL,
        source_sequence INTEGER,
        source_session_epoch TEXT,
        source_quality_json TEXT NOT NULL,
        source_metadata_json TEXT NOT NULL,
        transport_provenance_json TEXT NOT NULL,
        synthetic_provenance_json TEXT NOT NULL,
        ordering_facts_json TEXT NOT NULL,
        CHECK (
            (observed_at_status = 'VALID' AND observed_at_utc IS NOT NULL)
            OR
            (observed_at_status IN ('MISSING', 'INVALID')
                AND observed_at_utc IS NULL)
        ),
        UNIQUE (replay_execution_id, delivery_id),
        UNIQUE (
            replay_execution_id,
            delivery_id,
            source_native_record_id
        ),
        FOREIGN KEY (
            replay_execution_id,
            delivery_id,
            facility_id,
            source_binding_id,
            source_event_group_key
        ) REFERENCES replay_deliveries (
            replay_execution_id,
            delivery_id,
            facility_id,
            source_binding_id,
            source_event_group_key
        ),
        FOREIGN KEY (
            facility_id,
            mapping_id,
            mapping_version,
            mapping_digest
        ) REFERENCES mapping_snapshots (
            facility_id,
            mapping_id,
            mapping_version,
            content_digest
        )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS canonical_observations (
        canonical_observation_id TEXT PRIMARY KEY,
        replay_execution_id TEXT NOT NULL,
        facility_id TEXT NOT NULL,
        source_binding_id TEXT NOT NULL,
        source_event_group_key TEXT,
        source_event_variant_digest TEXT NOT NULL,
        canonical_point_definition_id TEXT NOT NULL,
        mapping_id TEXT NOT NULL,
        mapping_version TEXT NOT NULL,
        mapping_digest TEXT NOT NULL,
        canonicalizer_version TEXT NOT NULL,
        derivation_key TEXT NOT NULL,
        value_type TEXT NOT NULL CHECK (
            value_type IN ('BOOLEAN', 'INTEGER', 'DECIMAL', 'TEXT', 'ENUM')
        ),
        value_boolean INTEGER CHECK (value_boolean IN (0, 1)),
        value_integer INTEGER,
        value_decimal TEXT,
        value_text TEXT,
        unit TEXT,
        time_basis TEXT NOT NULL CHECK (
            time_basis = 'SOURCE_REPORTED_OBSERVED_AT'
        ),
        observed_at_status TEXT NOT NULL CHECK (
            observed_at_status IN ('VALID', 'MISSING', 'INVALID')
        ),
        observed_at_utc TEXT,
        received_at_utc TEXT NOT NULL,
        source_sequence INTEGER,
        source_session_epoch TEXT,
        source_quality_provenance_json TEXT NOT NULL,
        synthetic_provenance_json TEXT NOT NULL,
        report_material_digest TEXT NOT NULL,
        ordering_facts_json TEXT NOT NULL,
        UNIQUE (
            replay_execution_id,
            derivation_key,
            canonical_point_definition_id
        ),
        UNIQUE (
            replay_execution_id,
            source_binding_id,
            source_event_group_key,
            source_event_variant_digest,
            canonical_point_definition_id,
            mapping_id,
            mapping_version,
            mapping_digest
        ),
        CHECK (
            (value_type = 'BOOLEAN'
                AND value_boolean IS NOT NULL
                AND value_integer IS NULL
                AND value_decimal IS NULL
                AND value_text IS NULL)
            OR
            (value_type = 'INTEGER'
                AND value_boolean IS NULL
                AND value_integer IS NOT NULL
                AND value_decimal IS NULL
                AND value_text IS NULL)
            OR
            (value_type = 'DECIMAL'
                AND value_boolean IS NULL
                AND value_integer IS NULL
                AND value_decimal IS NOT NULL
                AND value_text IS NULL)
            OR
            (value_type IN ('TEXT', 'ENUM')
                AND value_boolean IS NULL
                AND value_integer IS NULL
                AND value_decimal IS NULL
                AND value_text IS NOT NULL)
        ),
        CHECK (
            (observed_at_status = 'VALID' AND observed_at_utc IS NOT NULL)
            OR
            (observed_at_status IN ('MISSING', 'INVALID')
                AND observed_at_utc IS NULL)
        ),
        FOREIGN KEY (replay_execution_id, facility_id)
            REFERENCES replay_executions (
                replay_execution_id,
                facility_id
            ),
        FOREIGN KEY (facility_id, source_binding_id)
            REFERENCES source_bindings (facility_id, source_binding_id),
        FOREIGN KEY (
            replay_execution_id,
            source_event_group_key,
            facility_id,
            source_binding_id
        ) REFERENCES source_event_groups (
            replay_execution_id,
            source_event_group_key,
            facility_id,
            source_binding_id
        ),
        FOREIGN KEY (
            facility_id,
            mapping_id,
            mapping_version,
            mapping_digest
        ) REFERENCES mapping_snapshots (
            facility_id,
            mapping_id,
            mapping_version,
            content_digest
        )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS canonical_observation_lineage (
        canonical_observation_id TEXT NOT NULL,
        source_native_record_id TEXT NOT NULL,
        input_ordinal INTEGER NOT NULL CHECK (input_ordinal > 0),
        lineage_role TEXT NOT NULL,
        source_field_path TEXT NOT NULL,
        PRIMARY KEY (
            canonical_observation_id,
            source_native_record_id,
            input_ordinal,
            source_field_path
        ),
        FOREIGN KEY (canonical_observation_id)
            REFERENCES canonical_observations (canonical_observation_id),
        FOREIGN KEY (source_native_record_id)
            REFERENCES source_native_records (source_native_record_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS canonical_decode_issues (
        replay_execution_id TEXT NOT NULL,
        issue_id TEXT NOT NULL,
        source_native_record_id TEXT,
        mapping_id TEXT NOT NULL,
        mapping_version TEXT NOT NULL,
        issue_code TEXT NOT NULL,
        detail_json TEXT NOT NULL,
        PRIMARY KEY (replay_execution_id, issue_id),
        FOREIGN KEY (replay_execution_id)
            REFERENCES replay_executions (replay_execution_id),
        FOREIGN KEY (source_native_record_id)
            REFERENCES source_native_records (source_native_record_id),
        FOREIGN KEY (mapping_id, mapping_version)
            REFERENCES mapping_snapshots (mapping_id, mapping_version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS replay_annotations (
        replay_execution_id TEXT NOT NULL,
        narrative_event_id TEXT NOT NULL,
        annotation_kind TEXT NOT NULL CHECK (
            annotation_kind = 'ASSERTED_ACTION'
        ),
        annotation_json TEXT NOT NULL,
        PRIMARY KEY (replay_execution_id, narrative_event_id),
        FOREIGN KEY (replay_execution_id)
            REFERENCES replay_executions (replay_execution_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reproducibility_manifests (
        replay_execution_id TEXT PRIMARY KEY,
        manifest_digest TEXT NOT NULL,
        normalized_semantic_digest TEXT NOT NULL,
        manifest_json TEXT NOT NULL,
        FOREIGN KEY (replay_execution_id)
            REFERENCES replay_executions (replay_execution_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS source_native_scope_index
    ON source_native_records (
        facility_id,
        replay_execution_id,
        source_binding_id,
        received_at_utc
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS canonical_projection_scope_index
    ON canonical_observations (
        facility_id,
        replay_execution_id,
        source_binding_id,
        canonical_point_definition_id,
        mapping_id,
        mapping_version,
        observed_at_utc,
        received_at_utc
    )
    """,
)

IMMUTABLE_TABLES = (
    "topology_snapshots",
    "source_bindings",
    "mapping_snapshots",
    "replay_package_snapshots",
    "replay_executions",
    "replay_execution_requests",
    "source_event_groups",
    "replay_deliveries",
    "source_native_records",
    "canonical_observations",
    "canonical_observation_lineage",
    "canonical_decode_issues",
    "replay_annotations",
    "reproducibility_manifests",
)

VALIDATION_TRIGGER_STATEMENTS = (
    """
    CREATE TRIGGER IF NOT EXISTS validate_canonical_lineage_scope
    BEFORE INSERT ON canonical_observation_lineage
    WHEN NOT EXISTS (
        SELECT 1
        FROM canonical_observations AS observation
        JOIN source_native_records AS native
          ON native.source_native_record_id =
                NEW.source_native_record_id
        WHERE observation.canonical_observation_id =
                NEW.canonical_observation_id
          AND observation.replay_execution_id =
                native.replay_execution_id
          AND observation.facility_id = native.facility_id
          AND observation.source_binding_id =
                native.source_binding_id
          AND observation.mapping_id = native.mapping_id
          AND observation.mapping_version = native.mapping_version
          AND observation.mapping_digest = native.mapping_digest
          AND (
                observation.source_event_group_key IS NULL
                OR observation.source_event_group_key =
                    native.source_event_group_key
          )
    )
    BEGIN
        SELECT RAISE(
            ABORT,
            'canonical lineage crosses replay, facility, source, mapping, or event scope'
        );
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS validate_source_native_mapping_scope
    BEFORE INSERT ON source_native_records
    WHEN NOT EXISTS (
        SELECT 1
        FROM replay_executions AS execution
        JOIN mapping_snapshots AS mapping
          ON mapping.facility_id = execution.facility_id
         AND mapping.topology_id = execution.topology_id
         AND mapping.topology_version = execution.topology_version
         AND mapping.topology_digest = execution.topology_digest
        WHERE execution.replay_execution_id = NEW.replay_execution_id
          AND execution.facility_id = NEW.facility_id
          AND mapping.mapping_id = NEW.mapping_id
          AND mapping.mapping_version = NEW.mapping_version
          AND mapping.content_digest = NEW.mapping_digest
          AND mapping.source_binding_id = NEW.source_binding_id
    )
    BEGIN
        SELECT RAISE(
            ABORT,
            'source-native mapping crosses replay topology, facility, or source-binding scope'
        );
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS validate_canonical_mapping_scope
    BEFORE INSERT ON canonical_observations
    WHEN NOT EXISTS (
        SELECT 1
        FROM replay_executions AS execution
        JOIN mapping_snapshots AS mapping
          ON mapping.facility_id = execution.facility_id
         AND mapping.topology_id = execution.topology_id
         AND mapping.topology_version = execution.topology_version
         AND mapping.topology_digest = execution.topology_digest
        WHERE execution.replay_execution_id = NEW.replay_execution_id
          AND execution.facility_id = NEW.facility_id
          AND mapping.mapping_id = NEW.mapping_id
          AND mapping.mapping_version = NEW.mapping_version
          AND mapping.content_digest = NEW.mapping_digest
          AND mapping.source_binding_id = NEW.source_binding_id
    )
    BEGIN
        SELECT RAISE(
            ABORT,
            'canonical mapping crosses replay topology, facility, or source-binding scope'
        );
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS validate_canonical_decode_issue_scope
    BEFORE INSERT ON canonical_decode_issues
    WHEN NOT EXISTS (
        SELECT 1
        FROM replay_executions AS execution
        JOIN mapping_snapshots AS mapping
          ON mapping.facility_id = execution.facility_id
         AND mapping.topology_id = execution.topology_id
         AND mapping.topology_version = execution.topology_version
         AND mapping.topology_digest = execution.topology_digest
        WHERE execution.replay_execution_id = NEW.replay_execution_id
          AND mapping.mapping_id = NEW.mapping_id
          AND mapping.mapping_version = NEW.mapping_version
          AND (
                NEW.source_native_record_id IS NULL
                OR EXISTS (
                    SELECT 1
                    FROM source_native_records AS native
                    WHERE native.source_native_record_id =
                            NEW.source_native_record_id
                      AND native.replay_execution_id =
                            NEW.replay_execution_id
                      AND native.facility_id = execution.facility_id
                      AND native.mapping_id = NEW.mapping_id
                      AND native.mapping_version = NEW.mapping_version
                )
          )
    )
    BEGIN
        SELECT RAISE(
            ABORT,
            'canonical decode issue crosses replay, topology, facility, mapping, or source-native scope'
        );
    END
    """,
)


def _connect(db_path: Path | str, *, require_exists: bool = False):
    target = Path(db_path)
    if require_exists and not target.is_file():
        raise LookupError(f"Observation replay store not found: {target}")
    connection = sqlite3.connect(target, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA recursive_triggers = ON")
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        connection.close()
        raise ObservationStoreError(
            "SQLite foreign-key enforcement is required for the observation store"
        )
    return connection


def initialize_observation_store(
    db_path: Path | str,
    *,
    inject_failure_after_statement: int | None = None,
) -> None:
    """Initialize the additive schema in one rollback-capable transaction."""

    target = Path(db_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = _connect(target)
    connection.isolation_level = None
    try:
        connection.execute("BEGIN IMMEDIATE")
        for ordinal, statement in enumerate(SCHEMA_STATEMENTS, start=1):
            connection.execute(statement)
            if inject_failure_after_statement == ordinal:
                raise RuntimeError("Injected observation schema initialization failure")

        existing = connection.execute(
            """
            SELECT schema_version
            FROM observation_store_metadata
            WHERE singleton_id = 1
            """
        ).fetchone()
        if existing is None:
            connection.execute(
                """
                INSERT INTO observation_store_metadata (
                    singleton_id,
                    schema_version
                )
                VALUES (1, ?)
                """,
                (SCHEMA_VERSION,),
            )
        elif existing["schema_version"] != SCHEMA_VERSION:
            raise ObservationStoreError(
                "Unsupported observation store schema version: "
                f"{existing['schema_version']}"
            )

        for table_name in IMMUTABLE_TABLES:
            for operation in ("UPDATE", "DELETE"):
                trigger_name = (
                    f"prevent_{table_name}_{operation.lower()}"
                )
                connection.execute(
                    f"""
                    CREATE TRIGGER IF NOT EXISTS {trigger_name}
                    BEFORE {operation} ON {table_name}
                    BEGIN
                        SELECT RAISE(
                            ABORT,
                            '{table_name} records are append-only'
                        );
                    END
                    """
                )
        for statement in VALIDATION_TRIGGER_STATEMENTS:
            connection.execute(statement)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _insert_or_verify(
    connection: sqlite3.Connection,
    *,
    table: str,
    identity_columns: tuple[str, ...],
    row: dict[str, Any],
    digest_column: str | None = None,
) -> None:
    trusted_tables = {
        "topology_snapshots",
        "source_bindings",
        "mapping_snapshots",
        "replay_package_snapshots",
    }
    if table not in trusted_tables:
        raise ValueError(f"Unsupported immutable snapshot table: {table}")
    _validate_row(connection, table, row)

    where_sql = " AND ".join(f"{column} = ?" for column in identity_columns)
    existing = connection.execute(
        f"SELECT * FROM {table} WHERE {where_sql}",
        tuple(row[column] for column in identity_columns),
    ).fetchone()
    if existing is not None:
        existing_values = {column: existing[column] for column in row}
        if existing_values == row:
            return
        if (
            digest_column is not None
            and existing[digest_column] != row[digest_column]
        ):
            identity = ", ".join(
                f"{column}={row[column]!r}" for column in identity_columns
            )
            raise ImmutableIdentityConflictError(
                f"{table} immutable identity digest mismatch: {identity}"
            )
        identity = ", ".join(
            f"{column}={row[column]!r}" for column in identity_columns
        )
        raise ImmutableIdentityConflictError(
            f"{table} immutable identity mismatch: {identity}"
        )

    columns = tuple(row)
    connection.execute(
        f"""
        INSERT INTO {table} ({", ".join(columns)})
        VALUES ({", ".join("?" for _ in columns)})
        """,
        tuple(row[column] for column in columns),
    )


def persist_replay_execution(
    db_path: Path | str,
    plan: dict[str, Any],
    *,
    inject_failure_after_native_record: int | None = None,
) -> dict[str, Any]:
    """Publish one completely prepared replay plan atomically."""

    initialize_observation_store(db_path)
    execution = plan["execution"]
    facility_id = execution["facility_id"]
    idempotency_key = plan["request"]["idempotency_key"]
    request_digest = execution["request_digest"]

    connection = _connect(db_path)
    connection.isolation_level = None
    try:
        connection.execute("BEGIN IMMEDIATE")

        prior_request = connection.execute(
            """
            SELECT request_digest, replay_execution_id
            FROM replay_execution_requests
            WHERE facility_id = ? AND idempotency_key = ?
            """,
            (facility_id, idempotency_key),
        ).fetchone()
        if prior_request is not None:
            if prior_request["request_digest"] != request_digest:
                raise IdempotencyConflictError(
                    "Replay request idempotency key was reused with different content"
                )
            connection.rollback()
            return {
                "replay_execution_id": prior_request["replay_execution_id"],
                "idempotent_replay": True,
            }

        prior_execution = connection.execute(
            """
            SELECT request_digest
            FROM replay_executions
            WHERE replay_execution_id = ?
            """,
            (execution["replay_execution_id"],),
        ).fetchone()
        if prior_execution is not None:
            raise IdempotencyConflictError(
                "Replay execution ID is already bound to another accepted request"
            )

        _insert_or_verify(
            connection,
            table="topology_snapshots",
            identity_columns=("topology_id", "topology_version"),
            row=plan["topology_snapshot"],
            digest_column="content_digest",
        )
        for source_binding in plan["source_bindings"]:
            _insert_or_verify(
                connection,
                table="source_bindings",
                identity_columns=("facility_id", "source_binding_id"),
                row=source_binding,
            )
        for mapping in plan["mapping_snapshots"]:
            _insert_or_verify(
                connection,
                table="mapping_snapshots",
                identity_columns=("mapping_id", "mapping_version"),
                row=mapping,
                digest_column="content_digest",
            )
        _insert_or_verify(
            connection,
            table="replay_package_snapshots",
            identity_columns=("package_id", "package_version"),
            row=plan["package_snapshot"],
            digest_column="content_digest",
        )

        _insert_row(connection, "replay_executions", execution)
        _insert_row(
            connection,
            "replay_execution_requests",
            {
                "facility_id": facility_id,
                "idempotency_key": idempotency_key,
                "request_digest": request_digest,
                "replay_execution_id": execution["replay_execution_id"],
            },
        )
        for group in plan["source_event_groups"]:
            _insert_row(connection, "source_event_groups", group)
        for delivery in plan["deliveries"]:
            _insert_row(connection, "replay_deliveries", delivery)
        for ordinal, native_record in enumerate(plan["source_native_records"], start=1):
            _insert_row(connection, "source_native_records", native_record)
            if inject_failure_after_native_record == ordinal:
                raise RuntimeError("Injected replay transaction failure")
        for observation in plan["canonical_observations"]:
            _insert_row(connection, "canonical_observations", observation)
        for lineage in plan["lineage"]:
            _insert_row(connection, "canonical_observation_lineage", lineage)
        for issue in plan.get("decode_issues", []):
            _insert_row(connection, "canonical_decode_issues", issue)
        for annotation in plan.get("annotations", []):
            _insert_row(connection, "replay_annotations", annotation)
        _insert_row(
            connection,
            "reproducibility_manifests",
            plan["reproducibility_manifest"],
        )

        _validate_execution_completeness(
            connection,
            execution["replay_execution_id"],
        )
        foreign_key_errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
        if foreign_key_errors:
            raise ObservationStoreError(
                "Observation store foreign-key validation failed: "
                f"{[tuple(row) for row in foreign_key_errors]}"
            )
        connection.commit()
        return {
            "replay_execution_id": execution["replay_execution_id"],
            "idempotent_replay": False,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _insert_row(
    connection: sqlite3.Connection,
    table: str,
    row: dict[str, Any],
) -> None:
    trusted_tables = {
        "replay_executions",
        "replay_execution_requests",
        "source_event_groups",
        "replay_deliveries",
        "source_native_records",
        "canonical_observations",
        "canonical_observation_lineage",
        "canonical_decode_issues",
        "replay_annotations",
        "reproducibility_manifests",
    }
    if table not in trusted_tables:
        raise ValueError(f"Unsupported replay insert table: {table}")
    _validate_row(connection, table, row)
    columns = tuple(row)
    connection.execute(
        f"""
        INSERT INTO {table} ({", ".join(columns)})
        VALUES ({", ".join("?" for _ in columns)})
        """,
        tuple(row[column] for column in columns),
    )


def _validate_row(
    connection: sqlite3.Connection,
    table: str,
    row: dict[str, Any],
) -> None:
    """Reject malformed prepared-plan rows before constructing SQL."""

    if not isinstance(row, dict) or not row:
        raise ValueError(f"{table} row must be a non-empty dictionary")
    declared_columns = {
        column["name"]
        for column in connection.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }
    unexpected_columns = sorted(set(row) - declared_columns)
    if unexpected_columns:
        raise ValueError(
            f"{table} row contains unsupported columns: "
            f"{', '.join(unexpected_columns)}"
        )

    for field_name, value in row.items():
        if field_name.endswith("_digest") and value is not None:
            if (
                not isinstance(value, str)
                or _LOWERCASE_SHA256.fullmatch(value) is None
            ):
                raise ValueError(
                    f"{table}.{field_name} must be a lowercase SHA-256 digest"
                )
        if field_name.endswith("_json") and value is not None:
            _validate_json_text(
                value,
                field_name=f"{table}.{field_name}",
            )

    for field_name in ("received_at_utc", "observed_at_utc"):
        value = row.get(field_name)
        if value is not None:
            normalized = require_valid_rfc3339_utc(
                value,
                field_name=f"{table}.{field_name}",
            )
            if normalized != value:
                raise ValueError(
                    f"{table}.{field_name} must be normalized UTC text"
                )
    if row.get("recorded_at") is not None:
        require_valid_rfc3339_utc(
            row["recorded_at"],
            field_name=f"{table}.recorded_at",
        )

    if table == "source_native_records":
        _validate_source_native_time(row)
    elif table == "canonical_observations":
        _validate_canonical_value(row)


def _validate_json_text(value: Any, *, field_name: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be JSON text")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{field_name} must be valid UTF-8") from exc
    if len(encoded) > MAX_JSON_TEXT_BYTES:
        raise ValueError(
            f"{field_name} exceeds the {MAX_JSON_TEXT_BYTES}-byte limit"
        )
    try:
        json.loads(
            value,
            parse_constant=lambda constant: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON number {constant}")
            ),
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{field_name} must contain valid JSON") from exc


def _validate_source_native_time(row: dict[str, Any]) -> None:
    status = row.get("observed_at_status")
    if status not in {
        TIMESTAMP_VALID,
        TIMESTAMP_MISSING,
        TIMESTAMP_INVALID,
    }:
        return
    parsed = parse_rfc3339_timestamp(row.get("original_observed_at_text"))
    if parsed["status"] != status:
        raise ValueError(
            "source-native timestamp status does not match preserved source text"
        )
    expected = {
        "original_timezone_offset": parsed["raw_offset"],
        "timestamp_precision": parsed["precision"],
        "fractional_second_digits": parsed["fractional_second_digits"],
        "observed_at_utc": parsed["utc"],
    }
    for field_name, expected_value in expected.items():
        if row.get(field_name) != expected_value:
            raise ValueError(
                "source-native timestamp metadata does not match preserved "
                f"source text: {field_name}"
            )


def _validate_canonical_value(row: dict[str, Any]) -> None:
    value_type = row.get("value_type")
    if value_type == "BOOLEAN":
        value = row.get("value_boolean")
        if not (
            isinstance(value, bool)
            or (
                isinstance(value, int)
                and not isinstance(value, bool)
                and value in {0, 1}
            )
        ):
            raise ValueError(
                "canonical BOOLEAN values must be Boolean or integer 0/1"
            )
    elif value_type == "INTEGER":
        value = row.get("value_integer")
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("canonical INTEGER values must be integers")
    elif value_type == "DECIMAL":
        value = row.get("value_decimal")
        if not isinstance(value, str) or value != value.strip() or not value:
            raise ValueError(
                "canonical DECIMAL values must be non-empty decimal text"
            )
        try:
            parsed = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(
                "canonical DECIMAL values must be decimal text"
            ) from exc
        if not parsed.is_finite() or format(parsed, "f") != value:
            raise ValueError(
                "canonical DECIMAL values must be finite, non-exponential text"
            )
    elif value_type in {"TEXT", "ENUM"}:
        if not isinstance(row.get("value_text"), str):
            raise ValueError(
                f"canonical {value_type} values must be text"
            )


def _validate_execution_completeness(
    connection: sqlite3.Connection,
    replay_execution_id: str,
) -> None:
    _validate_delivery_semantics(connection, replay_execution_id)

    missing_lineage = connection.execute(
        """
        SELECT observation.canonical_observation_id
        FROM canonical_observations AS observation
        LEFT JOIN canonical_observation_lineage AS lineage
          ON lineage.canonical_observation_id =
                observation.canonical_observation_id
        WHERE observation.replay_execution_id = ?
        GROUP BY observation.canonical_observation_id
        HAVING COUNT(lineage.source_native_record_id) = 0
        LIMIT 1
        """,
        (replay_execution_id,),
    ).fetchone()
    if missing_lineage is not None:
        raise ObservationStoreError(
            "Canonical observation has no source-native lineage: "
            f"{missing_lineage['canonical_observation_id']}"
        )

    missing_exact_redelivery_lineage = connection.execute(
        """
        SELECT
            observation.canonical_observation_id,
            native.source_native_record_id
        FROM canonical_observations AS observation
        JOIN source_native_records AS native
          ON native.replay_execution_id =
                observation.replay_execution_id
         AND native.source_binding_id =
                observation.source_binding_id
         AND native.source_event_group_key =
                observation.source_event_group_key
         AND native.source_event_variant_digest =
                observation.source_event_variant_digest
         AND native.mapping_id = observation.mapping_id
         AND native.mapping_version = observation.mapping_version
         AND native.mapping_digest = observation.mapping_digest
        LEFT JOIN canonical_observation_lineage AS lineage
          ON lineage.canonical_observation_id =
                observation.canonical_observation_id
         AND lineage.source_native_record_id =
                native.source_native_record_id
        WHERE observation.replay_execution_id = ?
          AND observation.source_event_group_key IS NOT NULL
          AND lineage.source_native_record_id IS NULL
        LIMIT 1
        """,
        (replay_execution_id,),
    ).fetchone()
    if missing_exact_redelivery_lineage is not None:
        raise ObservationStoreError(
            "Canonical observation omits exact-redelivery lineage: "
            f"{missing_exact_redelivery_lineage['canonical_observation_id']} "
            f"-> {missing_exact_redelivery_lineage['source_native_record_id']}"
        )
    _validate_canonical_availability_times(connection, replay_execution_id)


def _validate_delivery_semantics(
    connection: sqlite3.Connection,
    replay_execution_id: str,
) -> None:
    rows = connection.execute(
        """
        SELECT
            delivery.ingestion_ordinal,
            delivery.received_at_utc AS delivery_received_at,
            delivery.redelivery_classification,
            native.received_at_utc AS native_received_at,
            native.source_event_variant_digest,
            native.source_sequence AS native_sequence,
            native.source_session_epoch AS native_epoch,
            groups.source_event_group_key,
            groups.identity_kind,
            groups.source_sequence AS group_sequence,
            groups.source_session_epoch AS group_epoch
        FROM replay_deliveries AS delivery
        JOIN source_native_records AS native
          ON native.replay_execution_id = delivery.replay_execution_id
         AND native.delivery_id = delivery.delivery_id
         AND native.source_native_record_id =
                delivery.source_native_record_id
        JOIN source_event_groups AS groups
          ON groups.replay_execution_id = delivery.replay_execution_id
         AND groups.source_event_group_key =
                delivery.source_event_group_key
        WHERE delivery.replay_execution_id = ?
        ORDER BY delivery.ingestion_ordinal
        """,
        (replay_execution_id,),
    ).fetchall()

    prior_received_at = None
    grouped_rows: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        if row["delivery_received_at"] != row["native_received_at"]:
            raise ObservationStoreError(
                "Delivery and source-native receipt times must match"
            )
        if row["native_epoch"] != row["group_epoch"]:
            raise ObservationStoreError(
                "Source-native epoch does not match its event group namespace"
            )
        if (
            row["identity_kind"] == "SEQUENCE_IN_DECLARED_EPOCH"
            and row["native_sequence"] != row["group_sequence"]
        ):
            raise ObservationStoreError(
                "Source-native sequence does not match its sequence-identity "
                "event group"
            )
        if prior_received_at is not None and compare_rfc3339_instants(
            row["delivery_received_at"],
            prior_received_at,
        ) == ORDER_BEFORE:
            raise ObservationStoreError(
                "Virtual receipt time must not move backward by ingestion ordinal"
            )
        prior_received_at = row["delivery_received_at"]
        grouped_rows.setdefault(row["source_event_group_key"], []).append(row)

    for group_key, group_rows in grouped_rows.items():
        identity_kind = group_rows[0]["identity_kind"]
        if identity_kind == "NO_STABLE_ID":
            if (
                len(group_rows) != 1
                or group_rows[0]["redelivery_classification"]
                != "NO_STABLE_ID"
            ):
                raise ObservationStoreError(
                    "A no-stable-identity delivery must have its own event "
                    f"group and NO_STABLE_ID classification: {group_key}"
                )
            continue

        seen_variants: set[str] = set()
        for group_ordinal, row in enumerate(group_rows):
            variant_digest = row["source_event_variant_digest"]
            if group_ordinal == 0:
                expected = "NEW_EVENT"
            elif variant_digest in seen_variants:
                expected = "EXACT_REDELIVERY"
            else:
                expected = "CONFLICTING_REDELIVERY"
            if row["redelivery_classification"] != expected:
                raise ObservationStoreError(
                    "Redelivery classification does not match source-event "
                    f"identity and material variant: {group_key}"
                )
            seen_variants.add(variant_digest)


def _validate_canonical_availability_times(
    connection: sqlite3.Connection,
    replay_execution_id: str,
) -> None:
    observations = connection.execute(
        """
        SELECT canonical_observation_id, source_event_group_key, received_at_utc
        FROM canonical_observations
        WHERE replay_execution_id = ?
        ORDER BY canonical_observation_id
        """,
        (replay_execution_id,),
    ).fetchall()
    for observation in observations:
        lineage_rows = connection.execute(
            """
            SELECT
                lineage.input_ordinal,
                native.received_at_utc
            FROM canonical_observation_lineage AS lineage
            JOIN source_native_records AS native
              ON native.source_native_record_id =
                    lineage.source_native_record_id
            WHERE lineage.canonical_observation_id = ?
            ORDER BY lineage.input_ordinal, native.source_native_record_id
            """,
            (observation["canonical_observation_id"],),
        ).fetchall()
        first_receipt_by_input: dict[int, str] = {}
        for lineage in lineage_rows:
            input_ordinal = lineage["input_ordinal"]
            received_at = lineage["received_at_utc"]
            current = first_receipt_by_input.get(input_ordinal)
            if current is None or compare_rfc3339_instants(
                received_at,
                current,
            ) == ORDER_BEFORE:
                first_receipt_by_input[input_ordinal] = received_at

        if observation["source_event_group_key"] is not None and len(
            first_receipt_by_input
        ) != 1:
            raise ObservationStoreError(
                "A single-source-event canonical derivation must use one "
                "logical input ordinal"
            )

        available_at = None
        for first_receipt in first_receipt_by_input.values():
            if available_at is None or compare_rfc3339_instants(
                first_receipt,
                available_at,
            ) == ORDER_AFTER:
                available_at = first_receipt
        if observation["received_at_utc"] != available_at:
            raise ObservationStoreError(
                "Canonical receipt time must equal the first knowledge time "
                "at which all declared logical inputs were available: "
                f"{observation['canonical_observation_id']}"
            )


def get_replay_execution(
    db_path: Path | str,
    facility_id: str,
    replay_execution_id: str,
) -> dict[str, Any]:
    connection = _connect(db_path, require_exists=True)
    try:
        row = connection.execute(
            """
            SELECT *
            FROM replay_executions
            WHERE facility_id = ? AND replay_execution_id = ?
            """,
            (facility_id, replay_execution_id),
        ).fetchone()
        if row is None:
            raise LookupError("Replay execution not found for the selected facility")
        result = dict(row)
        counts = {}
        for label, table_name in (
            ("deliveries", "replay_deliveries"),
            ("source_native_records", "source_native_records"),
            ("canonical_observations", "canonical_observations"),
            ("decode_issues", "canonical_decode_issues"),
        ):
            counts[label] = connection.execute(
                f"""
                SELECT COUNT(*)
                FROM {table_name}
                WHERE replay_execution_id = ?
                """,
                (replay_execution_id,),
            ).fetchone()[0]
        result["record_counts"] = counts
        return result
    finally:
        connection.close()


def get_reproducibility_manifest(
    db_path: Path | str,
    facility_id: str,
    replay_execution_id: str,
) -> dict[str, Any]:
    connection = _connect(db_path, require_exists=True)
    try:
        row = connection.execute(
            """
            SELECT manifest.manifest_json
            FROM reproducibility_manifests AS manifest
            JOIN replay_executions AS execution
              ON execution.replay_execution_id = manifest.replay_execution_id
            WHERE execution.facility_id = ?
              AND execution.replay_execution_id = ?
            """,
            (facility_id, replay_execution_id),
        ).fetchone()
        if row is None:
            raise LookupError("Replay manifest not found for the selected facility")
        return json.loads(row["manifest_json"])
    finally:
        connection.close()


def list_source_native_records(
    db_path: Path | str,
    facility_id: str,
    replay_execution_id: str,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    source_binding_id: str | None = None,
    source_event_group_key: str | None = None,
    observed_at_status: str | None = None,
) -> dict[str, Any]:
    page, page_size, offset = _page_values(page, page_size)
    clauses = [
        "native.facility_id = ?",
        "native.replay_execution_id = ?",
    ]
    parameters: list[Any] = [facility_id, replay_execution_id]
    for column, value in (
        ("native.source_binding_id", source_binding_id),
        ("native.source_event_group_key", source_event_group_key),
        ("native.observed_at_status", observed_at_status),
    ):
        if value is not None:
            clauses.append(f"{column} = ?")
            parameters.append(value)
    where_sql = " AND ".join(clauses)

    connection = _connect(db_path, require_exists=True)
    try:
        total = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM source_native_records AS native
            WHERE {where_sql}
            """,
            parameters,
        ).fetchone()[0]
        rows = connection.execute(
            f"""
            SELECT
                native.*,
                delivery.ingestion_ordinal,
                delivery.redelivery_classification,
                event_group.identity_kind,
                event_group.source_event_id,
                binding.source_id,
                binding.channel
            FROM source_native_records AS native
            JOIN replay_deliveries AS delivery
              ON delivery.replay_execution_id = native.replay_execution_id
             AND delivery.delivery_id = native.delivery_id
            JOIN source_bindings AS binding
              ON binding.facility_id = native.facility_id
             AND binding.source_binding_id = native.source_binding_id
            JOIN source_event_groups AS event_group
              ON event_group.replay_execution_id =
                    native.replay_execution_id
             AND event_group.source_event_group_key =
                    native.source_event_group_key
            WHERE {where_sql}
            ORDER BY delivery.ingestion_ordinal
            LIMIT ? OFFSET ?
            """,
            (*parameters, page_size, offset),
        ).fetchall()
        return _page_result(
            "source_native_records",
            [_decode_source_native_row(row) for row in rows],
            total,
            page,
            page_size,
        )
    finally:
        connection.close()


def get_source_native_record(
    db_path: Path | str,
    facility_id: str,
    source_native_record_id: str,
) -> dict[str, Any]:
    connection = _connect(db_path, require_exists=True)
    try:
        row = connection.execute(
            """
            SELECT
                native.*,
                delivery.ingestion_ordinal,
                delivery.redelivery_classification,
                delivery.idempotency_key,
                event_group.identity_kind,
                event_group.source_event_id,
                binding.source_id,
                binding.channel
            FROM source_native_records AS native
            JOIN replay_deliveries AS delivery
              ON delivery.replay_execution_id = native.replay_execution_id
             AND delivery.delivery_id = native.delivery_id
            JOIN source_bindings AS binding
              ON binding.facility_id = native.facility_id
             AND binding.source_binding_id = native.source_binding_id
            JOIN source_event_groups AS event_group
              ON event_group.replay_execution_id =
                    native.replay_execution_id
             AND event_group.source_event_group_key =
                    native.source_event_group_key
            WHERE native.facility_id = ?
              AND native.source_native_record_id = ?
            """,
            (facility_id, source_native_record_id),
        ).fetchone()
        if row is None:
            raise LookupError(
                "Source-native record not found for the selected facility"
            )
        return _decode_source_native_row(row)
    finally:
        connection.close()


def list_canonical_observations(
    db_path: Path | str,
    facility_id: str,
    replay_execution_id: str,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    source_binding_id: str | None = None,
    point_id: str | None = None,
    mapping_id: str | None = None,
    observed_from: str | None = None,
    observed_to: str | None = None,
) -> dict[str, Any]:
    page, page_size, offset = _page_values(page, page_size)
    normalized_observed_from = (
        require_valid_rfc3339_utc(
            observed_from,
            field_name="observed_from",
        )
        if observed_from is not None
        else None
    )
    normalized_observed_to = (
        require_valid_rfc3339_utc(
            observed_to,
            field_name="observed_to",
        )
        if observed_to is not None
        else None
    )
    if (
        normalized_observed_from is not None
        and normalized_observed_to is not None
        and compare_rfc3339_instants(
            normalized_observed_from,
            normalized_observed_to,
        )
        == ORDER_AFTER
    ):
        raise ValueError("observed_from must not be after observed_to")

    clauses = [
        "observation.facility_id = ?",
        "observation.replay_execution_id = ?",
    ]
    parameters: list[Any] = [facility_id, replay_execution_id]
    for column, value in (
        ("observation.source_binding_id", source_binding_id),
        ("observation.canonical_point_definition_id", point_id),
        ("observation.mapping_id", mapping_id),
    ):
        if value is not None:
            clauses.append(f"{column} = ?")
            parameters.append(value)
    where_sql = " AND ".join(clauses)

    connection = _connect(db_path, require_exists=True)
    try:
        rows = connection.execute(
            f"""
            SELECT
                observation.*,
                binding.source_id,
                binding.channel
            FROM canonical_observations AS observation
            JOIN source_bindings AS binding
              ON binding.facility_id = observation.facility_id
             AND binding.source_binding_id = observation.source_binding_id
            WHERE {where_sql}
            ORDER BY
                observation.received_at_utc,
                observation.canonical_observation_id
            """,
            parameters,
        ).fetchall()
        decoded_rows = [_decode_canonical_row(row) for row in rows]
        if (
            normalized_observed_from is not None
            or normalized_observed_to is not None
        ):
            filtered_rows = []
            for row in decoded_rows:
                observed_at_utc = row["observed_at_utc"]
                if observed_at_utc is None:
                    continue
                if (
                    normalized_observed_from is not None
                    and compare_rfc3339_instants(
                        observed_at_utc,
                        normalized_observed_from,
                    )
                    == ORDER_BEFORE
                ):
                    continue
                if (
                    normalized_observed_to is not None
                    and compare_rfc3339_instants(
                        observed_at_utc,
                        normalized_observed_to,
                    )
                    == ORDER_AFTER
                ):
                    continue
                filtered_rows.append(row)
            decoded_rows = filtered_rows
        total = len(decoded_rows)
        return _page_result(
            "canonical_observations",
            decoded_rows[offset : offset + page_size],
            total,
            page,
            page_size,
        )
    finally:
        connection.close()


def get_canonical_observation(
    db_path: Path | str,
    facility_id: str,
    canonical_observation_id: str,
) -> dict[str, Any]:
    connection = _connect(db_path, require_exists=True)
    try:
        row = connection.execute(
            """
            SELECT
                observation.*,
                binding.source_id,
                binding.channel
            FROM canonical_observations AS observation
            JOIN source_bindings AS binding
              ON binding.facility_id = observation.facility_id
             AND binding.source_binding_id = observation.source_binding_id
            WHERE observation.facility_id = ?
              AND observation.canonical_observation_id = ?
            """,
            (facility_id, canonical_observation_id),
        ).fetchone()
        if row is None:
            raise LookupError(
                "Canonical observation not found for the selected facility"
            )
        return _decode_canonical_row(row)
    finally:
        connection.close()


def get_canonical_lineage(
    db_path: Path | str,
    facility_id: str,
    canonical_observation_id: str,
) -> dict[str, Any]:
    observation = get_canonical_observation(
        db_path,
        facility_id,
        canonical_observation_id,
    )
    connection = _connect(db_path, require_exists=True)
    try:
        rows = connection.execute(
            """
            SELECT
                lineage.input_ordinal,
                lineage.lineage_role,
                lineage.source_field_path,
                native.source_native_record_id,
                native.delivery_id,
                native.payload_digest,
                native.source_event_group_key,
                native.source_event_variant_digest
            FROM canonical_observation_lineage AS lineage
            JOIN source_native_records AS native
              ON native.source_native_record_id =
                    lineage.source_native_record_id
            WHERE lineage.canonical_observation_id = ?
            ORDER BY
                lineage.input_ordinal,
                native.source_native_record_id,
                lineage.source_field_path
            """,
            (canonical_observation_id,),
        ).fetchall()
        return {
            "canonical_observation": observation,
            "source_native_lineage": [dict(row) for row in rows],
        }
    finally:
        connection.close()


def list_redelivery_groups(
    db_path: Path | str,
    facility_id: str,
    replay_execution_id: str,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    page, page_size, offset = _page_values(page, page_size)
    connection = _connect(db_path, require_exists=True)
    try:
        total = connection.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT groups.source_event_group_key
                FROM source_event_groups AS groups
                JOIN source_native_records AS native
                  ON native.replay_execution_id =
                        groups.replay_execution_id
                 AND native.source_event_group_key =
                        groups.source_event_group_key
                WHERE groups.facility_id = ?
                  AND groups.replay_execution_id = ?
                GROUP BY groups.source_event_group_key
                HAVING COUNT(native.source_native_record_id) > 1
            )
            """,
            (facility_id, replay_execution_id),
        ).fetchone()[0]
        group_rows = connection.execute(
            """
            SELECT
                groups.source_event_group_key,
                groups.identity_kind,
                groups.source_event_id,
                groups.source_session_epoch,
                groups.source_sequence,
                groups.source_binding_id,
                binding.source_id,
                binding.channel,
                COUNT(native.source_native_record_id) AS delivery_count,
                COUNT(DISTINCT native.source_event_variant_digest)
                    AS variant_count,
                SUM(
                    CASE
                        WHEN delivery.redelivery_classification =
                            'EXACT_REDELIVERY'
                        THEN 1 ELSE 0
                    END
                ) AS exact_redelivery_count,
                SUM(
                    CASE
                        WHEN delivery.redelivery_classification =
                            'CONFLICTING_REDELIVERY'
                        THEN 1 ELSE 0
                    END
                ) AS conflicting_redelivery_count
            FROM source_event_groups AS groups
            JOIN source_bindings AS binding
              ON binding.facility_id = groups.facility_id
             AND binding.source_binding_id = groups.source_binding_id
            JOIN source_native_records AS native
              ON native.replay_execution_id = groups.replay_execution_id
             AND native.source_event_group_key =
                    groups.source_event_group_key
            JOIN replay_deliveries AS delivery
              ON delivery.replay_execution_id = native.replay_execution_id
             AND delivery.delivery_id = native.delivery_id
            WHERE groups.facility_id = ?
              AND groups.replay_execution_id = ?
            GROUP BY
                groups.source_event_group_key,
                groups.identity_kind,
                groups.source_event_id,
                groups.source_session_epoch,
                groups.source_sequence,
                groups.source_binding_id,
                binding.source_id,
                binding.channel
            HAVING COUNT(native.source_native_record_id) > 1
            ORDER BY groups.source_event_group_key
            LIMIT ? OFFSET ?
            """,
            (facility_id, replay_execution_id, page_size, offset),
        ).fetchall()
        return _page_result(
            "redelivery_groups",
            [dict(row) for row in group_rows],
            total,
            page,
            page_size,
        )
    finally:
        connection.close()


def require_projection_scope(
    db_path: Path | str,
    facility_id: str,
    replay_execution_id: str,
    *,
    source_binding_id: str,
    point_id: str,
    mapping_id: str,
    mapping_version: str,
    mapping_digest: str,
) -> dict[str, Any]:
    """Resolve an exact stored projection scope or reject the reference."""

    connection = _connect(db_path, require_exists=True)
    try:
        row = connection.execute(
            """
            SELECT
                binding.source_id,
                binding.channel,
                mapping.definition_json
            FROM replay_executions AS execution
            JOIN source_bindings AS binding
              ON binding.facility_id = execution.facility_id
             AND binding.source_binding_id = ?
            JOIN mapping_snapshots AS mapping
              ON mapping.facility_id = execution.facility_id
             AND mapping.source_binding_id = binding.source_binding_id
             AND mapping.mapping_id = ?
             AND mapping.mapping_version = ?
             AND mapping.content_digest = ?
             AND mapping.topology_id = execution.topology_id
             AND mapping.topology_version = execution.topology_version
             AND mapping.topology_digest = execution.topology_digest
            WHERE execution.facility_id = ?
              AND execution.replay_execution_id = ?
            """,
            (
                source_binding_id,
                mapping_id,
                mapping_version,
                mapping_digest,
                facility_id,
                replay_execution_id,
            ),
        ).fetchone()
        if row is None:
            raise LookupError(
                "Reported-observation projection source or mapping scope "
                "was not found for the selected facility and replay execution"
            )
        definition = json.loads(row["definition_json"])
        transformation = definition.get("transformation", {})
        if transformation.get("kind") == "FIELD_SET":
            target_points = {
                output.get("target_point_id")
                for output in transformation.get("outputs", [])
                if isinstance(output, dict)
            }
        elif transformation.get("kind") == "REGISTER_PAIR_SIGNED_INT32_BE":
            target_points = {transformation.get("target_point_id")}
        else:
            target_points = set()
        if point_id not in target_points:
            raise LookupError(
                "Reported-observation projection point is not declared by "
                "the selected mapping scope"
            )
        return {
            "facility_id": facility_id,
            "replay_execution_id": replay_execution_id,
            "source_binding_id": source_binding_id,
            "source_id": row["source_id"],
            "channel": row["channel"],
            "point_id": point_id,
            "mapping_id": mapping_id,
            "mapping_version": mapping_version,
            "mapping_digest": mapping_digest,
        }
    finally:
        connection.close()


def projection_candidates(
    db_path: Path | str,
    facility_id: str,
    replay_execution_id: str,
    *,
    source_binding_id: str,
    point_id: str,
    mapping_id: str,
    mapping_version: str,
    mapping_digest: str,
    known_by_received_at: str,
) -> list[dict[str, Any]]:
    """Return canonical candidates with conflict state at a knowledge cutoff."""

    normalized_known_by = require_valid_rfc3339_utc(
        known_by_received_at,
        field_name="known_by_received_at",
    )
    connection = _connect(db_path, require_exists=True)
    try:
        rows = connection.execute(
            """
            SELECT
                observation.*,
                binding.source_id,
                binding.channel
            FROM canonical_observations AS observation
            JOIN source_bindings AS binding
              ON binding.facility_id = observation.facility_id
             AND binding.source_binding_id = observation.source_binding_id
            WHERE observation.facility_id = ?
              AND observation.replay_execution_id = ?
              AND observation.source_binding_id = ?
              AND observation.canonical_point_definition_id = ?
              AND observation.mapping_id = ?
              AND observation.mapping_version = ?
              AND observation.mapping_digest = ?
            ORDER BY
                observation.received_at_utc,
                observation.canonical_observation_id
            """,
            (
                facility_id,
                replay_execution_id,
                source_binding_id,
                point_id,
                mapping_id,
                mapping_version,
                mapping_digest,
            ),
        ).fetchall()
        native_variant_rows = connection.execute(
            """
            SELECT
                source_event_group_key,
                source_event_variant_digest,
                received_at_utc
            FROM source_native_records
            WHERE facility_id = ?
              AND replay_execution_id = ?
              AND source_binding_id = ?
            ORDER BY source_event_group_key, source_native_record_id
            """,
            (
                facility_id,
                replay_execution_id,
                source_binding_id,
            ),
        ).fetchall()
        known_variants_by_group: dict[str, set[str]] = {}
        for native in native_variant_rows:
            if native["source_event_group_key"] is None:
                # Identityless records do not form an inferred source event
                # merely because they share a scope or mapping.
                continue
            if compare_rfc3339_instants(
                native["received_at_utc"],
                normalized_known_by,
            ) not in {ORDER_BEFORE, ORDER_EQUAL}:
                continue
            known_variants_by_group.setdefault(
                native["source_event_group_key"],
                set(),
            ).add(native["source_event_variant_digest"])

        candidates = []
        for row in rows:
            decoded = _decode_canonical_row(row)
            lineage_rows = connection.execute(
                """
                SELECT
                    lineage.source_native_record_id,
                    native.received_at_utc,
                    native.source_event_group_key,
                    MIN(input_ordinal) AS first_input_ordinal
                FROM canonical_observation_lineage AS lineage
                JOIN source_native_records AS native
                  ON native.source_native_record_id =
                        lineage.source_native_record_id
                WHERE lineage.canonical_observation_id = ?
                GROUP BY
                    lineage.source_native_record_id,
                    native.received_at_utc,
                    native.source_event_group_key
                ORDER BY
                    first_input_ordinal,
                    lineage.source_native_record_id
                """,
                (row["canonical_observation_id"],),
            ).fetchall()
            source_event_group_key = row["source_event_group_key"]
            if source_event_group_key is not None:
                known_variant_count = len(
                    known_variants_by_group.get(
                        source_event_group_key,
                        set(),
                    )
                )
                source_event_conflict = known_variant_count > 1
            else:
                component_variant_counts = [
                    len(known_variants_by_group.get(group_key, set()))
                    for group_key in {
                        lineage["source_event_group_key"]
                        for lineage in lineage_rows
                        if lineage["source_event_group_key"] is not None
                    }
                ]
                source_event_conflict = any(
                    count > 1 for count in component_variant_counts
                )
                known_variant_count = (
                    max(component_variant_counts)
                    if source_event_conflict
                    else 0
                )
            shared = {
                "point_id": decoded["canonical_point_definition_id"],
                "normalized_value_type": decoded["value_type"],
                "normalized_value": decoded["normalized_value"],
                "source_event_conflict": source_event_conflict,
                "known_source_event_variant_count": known_variant_count,
            }
            if source_event_group_key is not None:
                # A direct canonical derivation is one logical source-event
                # variant. Return one candidate row per retained delivery so
                # the pure projector can enforce the knowledge cutoff and
                # report exact redeliveries without creating another logical
                # observation.
                for lineage in lineage_rows:
                    candidate = dict(decoded)
                    candidate.update(
                        {
                            **shared,
                            "received_at_utc": lineage[
                                "received_at_utc"
                            ],
                            "source_native_record_ids": [
                                lineage["source_native_record_id"]
                            ],
                        }
                    )
                    candidates.append(candidate)
            else:
                # A multi-source derivation becomes knowable only at its
                # stored canonical receipt time. Keep it as one candidate and
                # expose only lineage already known at this query cutoff.
                candidate = dict(decoded)
                candidate.update(
                    {
                        **shared,
                        "source_native_record_ids": [
                            lineage["source_native_record_id"]
                            for lineage in lineage_rows
                            if compare_rfc3339_instants(
                                lineage["received_at_utc"],
                                normalized_known_by,
                            )
                            in {ORDER_BEFORE, ORDER_EQUAL}
                        ],
                    }
                )
                candidates.append(candidate)
        return candidates
    finally:
        connection.close()


def _decode_source_native_row(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    for field_name in (
        "payload_json",
        "source_quality_json",
        "source_metadata_json",
        "transport_provenance_json",
        "synthetic_provenance_json",
        "ordering_facts_json",
    ):
        result[field_name.removesuffix("_json")] = json.loads(
            result.pop(field_name)
        )
    return result


def _decode_canonical_row(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    value_type = result["value_type"]
    if value_type == "BOOLEAN":
        normalized_value: Any = bool(result["value_boolean"])
    elif value_type == "INTEGER":
        normalized_value = result["value_integer"]
    elif value_type == "DECIMAL":
        normalized_value = result["value_decimal"]
    else:
        normalized_value = result["value_text"]
    result["normalized_value"] = normalized_value
    for field_name in (
        "source_quality_provenance_json",
        "synthetic_provenance_json",
        "ordering_facts_json",
    ):
        result[field_name.removesuffix("_json")] = json.loads(
            result.pop(field_name)
        )
    for field_name in (
        "value_boolean",
        "value_integer",
        "value_decimal",
        "value_text",
    ):
        result.pop(field_name, None)
    return result


def _page_values(page: int, page_size: int) -> tuple[int, int, int]:
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise ValueError("page must be a positive integer")
    if (
        isinstance(page_size, bool)
        or not isinstance(page_size, int)
        or page_size < 1
        or page_size > MAX_PAGE_SIZE
    ):
        raise ValueError(
            f"page_size must be an integer from 1 through {MAX_PAGE_SIZE}"
        )
    offset = (page - 1) * page_size
    if offset > _SQLITE_MAX_INTEGER:
        raise ValueError("page is too large for the bounded SQLite query")
    return page, page_size, offset


def _page_result(
    key: str,
    records: list[dict[str, Any]],
    total: int,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    return {
        key: records,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_records": total,
            "has_more": page * page_size < total,
        },
    }
