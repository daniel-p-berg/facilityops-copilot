import tempfile
import unittest
from pathlib import Path

from analysis import analyze_alarms
from analysis import generate_db_briefing
from analysis import load_alarm_db


class AlarmSummaryTests(unittest.TestCase):
    def setUp(self):
        self.alarms = analyze_alarms.load_alarms(analyze_alarms.ALARM_FILE)
        self.summary = analyze_alarms.summarize_alarms(self.alarms)

    def test_sample_alarm_csv_contains_10_records(self):
        self.assertEqual(len(self.alarms), 10)

    def test_severity_counts_match_sample_data(self):
        self.assertEqual(
            dict(self.summary["severity_counts"]),
            {
                "High": 5,
                "Critical": 5,
            },
        )

    def test_source_counts_match_sample_data(self):
        self.assertEqual(
            dict(self.summary["source_counts"]),
            {
                "BMS": 5,
                "EPMS": 5,
            },
        )

    def test_active_critical_alarms_are_identified(self):
        active_critical_alarms = self.summary["active_critical_alarms"]
        equipment_in_alarm = {
            alarm["equipment"]
            for alarm in active_critical_alarms
        }

        self.assertEqual(len(active_critical_alarms), 3)
        self.assertEqual(equipment_in_alarm, {"UPS-A", "GEN-1", "ATS-1"})

        for alarm in active_critical_alarms:
            self.assertEqual(alarm["severity"], "Critical")
            self.assertEqual(alarm["status"], "Active")


class AlarmDatabaseTests(unittest.TestCase):
    def load_temp_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        temp_db_path = Path(temp_dir.name) / "facilityops_test.sqlite3"
        loaded_count = load_alarm_db.load_alarms_to_sqlite(
            csv_path=load_alarm_db.ALARM_FILE,
            db_path=temp_db_path,
        )
        return temp_db_path, loaded_count

    def test_sqlite_loader_creates_temp_database_with_expected_counts(self):
        temp_db_path, loaded_count = self.load_temp_database()

        self.assertNotEqual(temp_db_path, load_alarm_db.DATABASE_FILE)
        self.assertTrue(temp_db_path.exists())
        self.assertEqual(loaded_count, 10)

        alarm_counts = load_alarm_db.get_alarm_counts(temp_db_path)
        self.assertEqual(alarm_counts["total_alarm_records"], 10)
        self.assertEqual(
            alarm_counts["severity_counts"],
            {
                "Critical": 5,
                "High": 5,
            },
        )
        self.assertEqual(
            alarm_counts["source_counts"],
            {
                "BMS": 5,
                "EPMS": 5,
            },
        )

    def test_database_briefing_summary_identifies_active_critical_alarms(self):
        temp_db_path, _loaded_count = self.load_temp_database()

        summary = generate_db_briefing.build_summary(temp_db_path)
        active_critical_alarms = summary["active_critical_alarms"]
        equipment_in_alarm = {
            alarm[2]
            for alarm in active_critical_alarms
        }

        self.assertEqual(summary["total_alarms"], 10)
        self.assertEqual(len(active_critical_alarms), 3)
        self.assertEqual(equipment_in_alarm, {"UPS-A", "GEN-1", "ATS-1"})


if __name__ == "__main__":
    unittest.main()
