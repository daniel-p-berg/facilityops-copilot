import sqlite3

from analysis.load_alarm_db import CURRENT_POINT_VALUE_FILE
from analysis.load_alarm_db import DEFAULT_STALE_AFTER_SECONDS
from analysis.load_alarm_db import point_sample_id
from analysis.load_alarm_db import read_current_point_value_rows
from backend.summary import begin_transaction
from backend.summary import current_timestamp
from backend.summary import DATABASE_FILE
from backend.summary import ensure_alarm_event_table
from backend.summary import ensure_current_point_value_table
from backend.summary import ensure_generated_alarm_table
from backend.summary import ensure_point_sample_table


def table_count(connection, table_name):
    """Return a table row count for trusted operational tables."""
    if table_name not in {
        "generated_alarms",
        "alarm_events",
        "point_samples",
        "current_point_values",
    }:
        raise ValueError(f"Unsupported operational table: {table_name}")

    return connection.execute(
        f"SELECT COUNT(*) FROM {table_name}"
    ).fetchone()[0]


def reload_seed_current_values(connection, rows, received_timestamp):
    """Reload deterministic seed current values and seed point samples."""
    units_by_point_id = {
        point_id: unit
        for point_id, unit in connection.execute("SELECT id, unit FROM points")
    }

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


def reset_operational_state(
    db_path=DATABASE_FILE,
    current_point_value_csv_path=CURRENT_POINT_VALUE_FILE,
):
    """Reset volatile local runtime state while preserving catalog configuration."""
    seed_rows = read_current_point_value_rows(current_point_value_csv_path)
    received_timestamp = current_timestamp()

    with sqlite3.connect(db_path) as connection:
        ensure_point_sample_table(connection)
        ensure_current_point_value_table(connection)
        ensure_generated_alarm_table(connection)
        ensure_alarm_event_table(connection)
        with connection:
            begin_transaction(connection)
            generated_alarms_deleted = table_count(connection, "generated_alarms")
            alarm_events_deleted = table_count(connection, "alarm_events")
            point_samples_deleted = table_count(connection, "point_samples")

            connection.execute("DELETE FROM alarm_events")
            connection.execute("DELETE FROM generated_alarms")
            connection.execute("DELETE FROM current_point_values")
            connection.execute("DELETE FROM point_samples")

            reload_seed_current_values(
                connection,
                seed_rows,
                received_timestamp,
            )

    return {
        "generated_alarms_deleted": generated_alarms_deleted,
        "alarm_events_deleted": alarm_events_deleted,
        "point_samples_deleted": point_samples_deleted,
        "current_values_reset": len(seed_rows),
        "message": "Operational state reset",
    }
