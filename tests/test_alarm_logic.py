import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from analysis import analyze_alarms
from analysis import generate_db_briefing
from analysis import load_alarm_db
from backend import summary as backend_summary


REQUIRED_EQUIPMENT = {
    "UPS-A",
    "GEN-1",
    "ATS-1",
    "PDU-1",
    "CRAC-2",
    "AHU-1",
    "CHW-P-1",
    "TEMP-DH-A-1",
    "HUM-DH-A-1",
    "MTR-UTILITY-1",
}


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


class EquipmentInventoryTests(unittest.TestCase):
    def load_temp_sample_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        temp_db_path = Path(temp_dir.name) / "facilityops_test.sqlite3"
        load_counts = load_alarm_db.load_sample_data_to_sqlite(db_path=temp_db_path)
        return temp_db_path, load_counts

    def test_sample_equipment_csv_exists_with_required_records(self):
        self.assertTrue(load_alarm_db.EQUIPMENT_FILE.exists())

        with open(load_alarm_db.EQUIPMENT_FILE, mode="r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            equipment_names = {
                row["equipment"]
                for row in reader
            }

        self.assertTrue(REQUIRED_EQUIPMENT.issubset(equipment_names))

    def test_sqlite_loader_creates_and_loads_equipment_table(self):
        temp_db_path, load_counts = self.load_temp_sample_database()

        self.assertNotEqual(temp_db_path, load_alarm_db.DATABASE_FILE)
        self.assertEqual(load_counts["alarm_records"], 10)
        self.assertEqual(load_counts["equipment_records"], 10)

        with sqlite3.connect(temp_db_path) as connection:
            table_exists = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'equipment'
                """
            ).fetchone()
            equipment_count = connection.execute(
                "SELECT COUNT(*) FROM equipment"
            ).fetchone()[0]

        self.assertIsNotNone(table_exists)
        self.assertEqual(equipment_count, 10)

    def test_equipment_table_includes_key_critical_equipment(self):
        temp_db_path, _load_counts = self.load_temp_sample_database()

        with sqlite3.connect(temp_db_path) as connection:
            equipment_names = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT equipment
                    FROM equipment
                    WHERE equipment IN ('UPS-A', 'GEN-1', 'ATS-1')
                    """
                )
            }

        self.assertEqual(equipment_names, {"UPS-A", "GEN-1", "ATS-1"})

    def test_backend_summary_includes_equipment_context_for_active_critical_alarms(self):
        temp_db_path, _load_counts = self.load_temp_sample_database()

        summary = backend_summary.get_alarm_summary(temp_db_path)
        active_critical_alarms = summary["active_critical_alarms"]
        alarms_by_equipment = {
            alarm["equipment"]: alarm
            for alarm in active_critical_alarms
        }

        self.assertEqual(len(active_critical_alarms), 3)
        self.assertEqual(set(alarms_by_equipment), {"UPS-A", "GEN-1", "ATS-1"})
        self.assertEqual(alarms_by_equipment["UPS-A"]["location"], "Electrical Room A")
        self.assertEqual(alarms_by_equipment["GEN-1"]["location"], "Generator Yard")
        self.assertEqual(alarms_by_equipment["ATS-1"]["criticality"], "Critical")
        self.assertEqual(alarms_by_equipment["UPS-A"]["source_system"], "EPMS")


if __name__ == "__main__":
    unittest.main()
