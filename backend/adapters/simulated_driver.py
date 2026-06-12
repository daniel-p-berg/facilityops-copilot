from datetime import UTC
from datetime import datetime


class SimulatedDriver:
    """Read-only deterministic source for local simulated point samples."""

    def __init__(self, read_timestamp=None):
        self.read_timestamp = read_timestamp

    def current_timestamp(self):
        """Return a UTC timestamp for simulated source and receive time."""
        if self.read_timestamp:
            return self.read_timestamp

        return datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat(sep=" ")

    def read_samples(self):
        """Return deterministic simulated samples for existing points."""
        timestamp = self.current_timestamp()
        samples = [
            {
                "point_id": "UPS-A_OUTPUT_KW",
                "value": "205",
                "quality": "GOOD",
                "address": "simulated://northstar/ups-a/output_kw",
                "stale_after_seconds": 300,
            },
            {
                "point_id": "CRAC-2_SUPPLY_AIR_TEMP",
                "value": "61.5",
                "quality": "GOOD",
                "address": "simulated://northstar/crac-2/supply_air_temp",
                "stale_after_seconds": 300,
            },
            {
                "point_id": "GEN-1_FUEL_LEVEL",
                "value": "78",
                "quality": "GOOD",
                "address": "simulated://northstar/gen-1/fuel_level",
                "stale_after_seconds": 300,
            },
        ]

        return [
            {
                **sample,
                "source": "SIMULATED",
                "protocol": "SIMULATED",
                "source_timestamp": timestamp,
                "received_timestamp": timestamp,
                "overridden": False,
                "out_of_service": False,
            }
            for sample in samples
        ]

    def read_current_samples(self):
        """Alias for callers that prefer current-sample wording."""
        return self.read_samples()
