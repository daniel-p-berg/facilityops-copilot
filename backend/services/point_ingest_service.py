import sqlite3

from backend.summary import begin_transaction
from backend.summary import DATABASE_FILE
from backend.summary import ensure_alarm_event_table
from backend.summary import ensure_current_point_value_table
from backend.summary import ensure_point_sample_table
from backend.summary import ingest_point_sample_with_connection
from backend.summary import normalize_text


def failed_sample(index, sample, error):
    """Return a compact failed sample summary."""
    point_id = ""
    if isinstance(sample, dict):
        point_id = normalize_text(sample.get("point_id", ""))

    return {
        "index": index,
        "point_id": point_id,
        "error": str(error),
    }


def ingest_driver_samples(samples, db_path=DATABASE_FILE):
    """Ingest driver sample dictionaries using the existing point sample path."""
    samples = list(samples or [])
    summary = {
        "samples_received": len(samples),
        "samples_ingested": 0,
        "failed_samples": [],
    }

    with sqlite3.connect(db_path) as connection:
        ensure_point_sample_table(connection)
        ensure_current_point_value_table(connection)
        ensure_alarm_event_table(connection)
        with connection:
            begin_transaction(connection)
            for index, sample in enumerate(samples):
                if not isinstance(sample, dict):
                    summary["failed_samples"].append(
                        failed_sample(index, sample, "sample must be an object"),
                    )
                    continue

                connection.execute("SAVEPOINT driver_sample")
                try:
                    ingest_point_sample_with_connection(
                        connection,
                        sample.get("point_id", ""),
                        sample.get("value", ""),
                        quality=sample.get("quality", "GOOD"),
                        source=sample.get("source", "SIMULATED"),
                        unit=sample.get("unit"),
                        source_timestamp=sample.get("source_timestamp"),
                        received_timestamp=sample.get("received_timestamp"),
                        protocol=sample.get("protocol", "SIMULATED"),
                        address=sample.get("address", ""),
                        stale_after_seconds=sample.get("stale_after_seconds"),
                        overridden=sample.get("overridden", False),
                        out_of_service=sample.get("out_of_service", False),
                        created_by=sample.get("created_by", "simulated-driver"),
                    )
                except (LookupError, ValueError) as error:
                    connection.execute("ROLLBACK TO SAVEPOINT driver_sample")
                    connection.execute("RELEASE SAVEPOINT driver_sample")
                    summary["failed_samples"].append(failed_sample(index, sample, error))
                    continue

                connection.execute("RELEASE SAVEPOINT driver_sample")
                summary["samples_ingested"] += 1

    return summary
