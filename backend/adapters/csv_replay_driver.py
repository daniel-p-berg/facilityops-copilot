import csv
from pathlib import Path


REQUIRED_REPLAY_COLUMNS = {
    "sequence",
    "point_id",
    "value",
    "quality",
    "source_timestamp",
    "source",
    "protocol",
    "address",
    "stale_after_seconds",
    "overridden",
    "out_of_service",
}


def normalize_text(value):
    """Return stripped text for replay CSV values."""
    if value is None:
        return ""

    return str(value).strip()


def parse_replay_bool(value):
    """Parse simple boolean CSV values for replay samples."""
    normalized_value = normalize_text(value).lower()
    return normalized_value in {"1", "true", "yes", "on"}


def sequence_sort_key(sample):
    """Sort replay samples by sequence, preserving stable order for text values."""
    sequence = normalize_text(sample.get("sequence", ""))
    try:
        return (0, int(sequence))
    except ValueError:
        return (1, sequence)


class CsvReplayDriver:
    """Read-only deterministic point sample replay from a local CSV file."""

    def __init__(self, csv_path):
        self.csv_path = Path(csv_path)

    def read_rows(self):
        """Read raw CSV rows and validate the replay header."""
        with self.csv_path.open(mode="r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            fieldnames = set(reader.fieldnames or [])
            missing_columns = sorted(REQUIRED_REPLAY_COLUMNS - fieldnames)
            if missing_columns:
                raise ValueError(
                    "CSV replay file missing required column(s): "
                    + ", ".join(missing_columns),
                )

            return list(reader)

    def sample_from_row(self, row):
        """Convert one replay CSV row to a point sample dictionary."""
        return {
            "sequence": normalize_text(row.get("sequence", "")),
            "point_id": normalize_text(row.get("point_id", "")),
            "value": normalize_text(row.get("value", "")),
            "quality": normalize_text(row.get("quality", "")) or "GOOD",
            "source_timestamp": normalize_text(row.get("source_timestamp", "")),
            "source": normalize_text(row.get("source", "")) or "SIMULATED",
            "protocol": normalize_text(row.get("protocol", "")) or "CSV_REPLAY",
            "address": normalize_text(row.get("address", "")),
            "stale_after_seconds": normalize_text(row.get("stale_after_seconds", "")),
            "overridden": parse_replay_bool(row.get("overridden", "")),
            "out_of_service": parse_replay_bool(row.get("out_of_service", "")),
            "created_by": "csv-replay-driver",
        }

    def read_samples(self, sequence=None):
        """Return replay samples, optionally filtered to one sequence value."""
        sequence_filter = normalize_text(sequence)
        samples = [
            self.sample_from_row(row)
            for row in self.read_rows()
            if not sequence_filter
            or normalize_text(row.get("sequence", "")) == sequence_filter
        ]

        return sorted(samples, key=sequence_sort_key)
