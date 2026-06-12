from backend.adapters.csv_replay_driver import CsvReplayDriver
from backend.adapters.csv_replay_driver import normalize_text
from backend.adapters.csv_replay_driver import sequence_sort_key
from backend.summary import DATABASE_FILE
from backend.summary import evaluate_generated_alarms
from backend.summary import get_alarm_summary
from backend.services.point_ingest_service import ingest_driver_samples


def require_sequence(sequence):
    """Normalize a required replay sequence value."""
    if isinstance(sequence, bool):
        raise ValueError("sequence is required and must match a replay CSV sequence")

    normalized_sequence = normalize_text(sequence)
    if not normalized_sequence:
        raise ValueError("Missing required field: sequence")

    return normalized_sequence


def latest_source_timestamp(samples):
    """Return the latest source timestamp in a replay step."""
    timestamps = [
        normalize_text(sample.get("source_timestamp", ""))
        for sample in samples
        if isinstance(sample, dict) and normalize_text(sample.get("source_timestamp", ""))
    ]
    if not timestamps:
        return None

    return max(timestamps)


def updated_point_ids(samples, failed_samples):
    """Return point ids for samples that ingested successfully."""
    failed_indexes = {
        failed_sample["index"]
        for failed_sample in failed_samples
    }
    return sorted(
        {
            normalize_text(sample.get("point_id", ""))
            for index, sample in enumerate(samples)
            if index not in failed_indexes
            and isinstance(sample, dict)
            and normalize_text(sample.get("point_id", ""))
        }
    )


def available_sequences(driver):
    """Return distinct replay sequences in deterministic order."""
    samples = driver.read_samples()
    sequences = {
        normalize_text(sample.get("sequence", ""))
        for sample in samples
        if normalize_text(sample.get("sequence", ""))
    }
    return sorted(sequences, key=lambda sequence: sequence_sort_key({"sequence": sequence}))


def replay_step_result(sequence, samples, ingest_summary, evaluation_summary, db_path):
    """Build the structured replay runner response for one sequence."""
    generated_alarm_summary = get_alarm_summary(db_path)
    failed_samples = ingest_summary["failed_samples"]

    return {
        "sequence": normalize_text(sequence),
        "samples_read": len(samples),
        "samples_ingested": ingest_summary["samples_ingested"],
        "points_updated": updated_point_ids(samples, failed_samples),
        "failed_samples": failed_samples,
        "alarm_evaluation": evaluation_summary,
        "alarms_created": evaluation_summary["created_count"],
        "alarms_updated_or_promoted": evaluation_summary["updated_count"],
        "alarms_cleared": evaluation_summary["cleared_count"],
        "generated_alarm_summary": generated_alarm_summary,
    }


def run_csv_replay_step(sequence, csv_path, db_path=DATABASE_FILE):
    """Run one deterministic CSV replay sequence and explicitly evaluate alarms."""
    normalized_sequence = require_sequence(sequence)
    driver = CsvReplayDriver(csv_path)
    samples = driver.read_samples(sequence=normalized_sequence)
    if not samples:
        raise LookupError(f"Replay sequence not found: {normalized_sequence}")

    ingest_summary = ingest_driver_samples(samples, db_path=db_path)
    evaluation_summary = evaluate_generated_alarms(
        db_path,
        evaluation_timestamp=latest_source_timestamp(samples),
    )
    return replay_step_result(
        normalized_sequence,
        samples,
        ingest_summary,
        evaluation_summary,
        db_path,
    )


def run_all_csv_replay_steps(csv_path, db_path=DATABASE_FILE):
    """Run every CSV replay sequence in deterministic order."""
    driver = CsvReplayDriver(csv_path)
    sequences = available_sequences(driver)
    if not sequences:
        raise ValueError("CSV replay file does not contain any replay sequences")

    step_results = [
        run_csv_replay_step(sequence, csv_path, db_path=db_path)
        for sequence in sequences
    ]

    return {
        "sequences": sequences,
        "step_results": step_results,
        "steps_run": len(step_results),
        "samples_ingested": sum(
            result["samples_ingested"]
            for result in step_results
        ),
        "failed_samples": [
            {
                **failed_sample,
                "sequence": result["sequence"],
            }
            for result in step_results
            for failed_sample in result["failed_samples"]
        ],
        "generated_alarm_summary": get_alarm_summary(db_path),
    }
