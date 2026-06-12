import asyncio
import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from analysis import analyze_alarms
from analysis import generate_db_briefing
from analysis import load_alarm_db
from backend.adapters.simulated_driver import SimulatedDriver
from backend.domain import alarm_evaluator
from backend import main as backend_main
from backend import summary as backend_summary
from backend.services.point_ingest_service import ingest_driver_samples


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

REQUIRED_POINTS = {
    "CHW-P-1_RUN_STATUS",
    "CHW-P-1_SPEED_COMMAND",
    "CHW-P-1_SPEED_FEEDBACK",
    "CHW-P-1_DISCHARGE_PRESSURE",
    "UPS-A_OUTPUT_KW",
    "UPS-A_BATTERY_STATUS",
    "ATS-1_NORMAL_SOURCE_AVAILABLE",
    "CRAC-2_SUPPLY_AIR_TEMP",
    "CRAC-2_RETURN_AIR_TEMP",
    "GEN-1_RUN_STATUS",
    "GEN-1_FUEL_LEVEL",
}

REQUIRED_ALARM_RULES = {
    "RULE-CHW-P-1-FAILED-START",
    "RULE-CHW-P-1-LOW-DISCHARGE-PRESSURE",
    "RULE-UPS-A-HIGH-LOAD",
    "RULE-UPS-A-ON-BATTERY",
    "RULE-ATS-1-NORMAL-SOURCE-UNAVAILABLE",
    "RULE-CRAC-2-HIGH-SUPPLY-AIR-TEMP",
    "RULE-GEN-1-LOW-FUEL",
}

REQUIRED_CURRENT_POINT_VALUES = {
    "CHW-P-1_RUN_STATUS",
    "CHW-P-1_SPEED_COMMAND",
    "CHW-P-1_SPEED_FEEDBACK",
    "CHW-P-1_DISCHARGE_PRESSURE",
    "UPS-A_OUTPUT_KW",
    "UPS-A_BATTERY_STATUS",
    "ATS-1_NORMAL_SOURCE_AVAILABLE",
    "ATS-1_EMERGENCY_SOURCE_AVAILABLE",
    "CRAC-2_SUPPLY_AIR_TEMP",
    "CRAC-2_RETURN_AIR_TEMP",
    "GEN-1_RUN_STATUS",
    "GEN-1_FUEL_LEVEL",
    "PDU-1_LOAD_KW",
    "AHU-1_SUPPLY_AIR_TEMP",
    "TEMP-DH-A-1_SPACE_TEMP",
    "HUM-DH-A-1_RELATIVE_HUMIDITY",
    "MTR-UTILITY-1_VOLTAGE_AB",
}


def get_json_from_asgi_app(app, path, method="GET", body=None):
    async def make_request():
        messages = []
        request_sent = False
        request_body = b""
        request_headers = []
        if body is not None:
            request_body = json.dumps(body).encode("utf-8")
            request_headers = [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(request_body)).encode("utf-8")),
            ]

        async def receive():
            nonlocal request_sent
            if request_sent:
                return {"type": "http.disconnect"}

            request_sent = True
            return {
                "type": "http.request",
                "body": request_body,
                "more_body": False,
            }

        async def send(message):
            messages.append(message)

        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": path,
                "raw_path": path.encode("utf-8"),
                "query_string": b"",
                "headers": request_headers,
                "client": ("testclient", 50000),
                "server": ("testserver", 80),
                "root_path": "",
            },
            receive,
            send,
        )

        response_start = next(
            message
            for message in messages
            if message["type"] == "http.response.start"
        )
        response_body = b"".join(
            message.get("body", b"")
            for message in messages
            if message["type"] == "http.response.body"
        )
        return response_start["status"], json.loads(response_body.decode("utf-8"))

    return asyncio.run(make_request())


def write_csv_rows(csv_path, columns, rows):
    with open(csv_path, mode="w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


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
        self.assertEqual(load_counts["alarm_records"], 0)
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
            legacy_alarm_count = connection.execute(
                "SELECT COUNT(*) FROM alarms"
            ).fetchone()[0]

        self.assertIsNotNone(table_exists)
        self.assertEqual(equipment_count, 10)
        self.assertEqual(legacy_alarm_count, 0)

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

    def test_backend_summary_starts_with_empty_generated_alarm_counts(self):
        temp_db_path, _load_counts = self.load_temp_sample_database()

        summary = backend_summary.get_alarm_summary(temp_db_path)

        self.assertEqual(summary["total_generated_alarm_count"], 0)
        self.assertEqual(summary["active_generated_alarm_count"], 0)
        self.assertEqual(summary["active_unacknowledged_generated_alarm_count"], 0)
        self.assertEqual(summary["active_acknowledged_generated_alarm_count"], 0)
        self.assertEqual(summary["pending_generated_alarm_count"], 0)
        self.assertEqual(summary["active_critical_generated_alarm_count"], 0)
        self.assertEqual(summary["active_warning_generated_alarm_count"], 0)
        self.assertEqual(summary["active_info_generated_alarm_count"], 0)
        self.assertEqual(summary["cleared_generated_alarm_count"], 0)
        self.assertEqual(summary["active_generated_alarm_severity_counts"], {})
        self.assertEqual(summary["generated_alarm_state_counts"], {})
        self.assertEqual(summary["active_generated_alarm_equipment_counts"], {})
        self.assertNotIn("active_critical_alarms", summary)
        self.assertNotIn("total_alarm_records", summary)
        self.assertNotIn("source_counts", summary)


class DashboardGeneratedAlarmSourceTests(unittest.TestCase):
    def test_dashboard_uses_generated_alarm_summary_fields(self):
        frontend_file = Path(__file__).resolve().parents[1] / "frontend" / "index.html"
        dashboard_html = frontend_file.read_text(encoding="utf-8")

        self.assertIn("activeGeneratedAlarmCount", dashboard_html)
        self.assertIn("pendingGeneratedAlarmCount", dashboard_html)
        self.assertIn("active_generated_alarm_count", dashboard_html)
        self.assertIn("pending_generated_alarm_count", dashboard_html)
        self.assertIn("Generated Alarms", dashboard_html)
        self.assertIn("Acknowledged", dashboard_html)
        self.assertIn("Read Simulated Driver Samples", dashboard_html)
        self.assertIn("/drivers/simulated/read", dashboard_html)
        self.assertNotIn("activeCriticalAlarms", dashboard_html)
        self.assertNotIn("active_critical_alarms", dashboard_html)
        self.assertNotIn("totalAlarmRecords", dashboard_html)
        self.assertNotIn("total_alarm_records", dashboard_html)
        self.assertNotIn("sourceCounts", dashboard_html)


class PointAndAlarmRuleCatalogTests(unittest.TestCase):
    def load_temp_sample_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        temp_db_path = Path(temp_dir.name) / "facilityops_test.sqlite3"
        load_counts = load_alarm_db.load_sample_data_to_sqlite(db_path=temp_db_path)
        return temp_db_path, load_counts

    def test_sample_points_csv_exists_with_required_records(self):
        self.assertTrue(load_alarm_db.POINT_FILE.exists())

        with open(load_alarm_db.POINT_FILE, mode="r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            point_ids = {
                row["id"]
                for row in reader
            }

        self.assertTrue(REQUIRED_POINTS.issubset(point_ids))

    def test_sample_alarm_rules_csv_exists_with_required_records(self):
        self.assertTrue(load_alarm_db.ALARM_RULE_FILE.exists())

        with open(load_alarm_db.ALARM_RULE_FILE, mode="r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            rule_ids = {
                row["id"]
                for row in reader
            }

        self.assertTrue(REQUIRED_ALARM_RULES.issubset(rule_ids))

    def test_sqlite_loader_creates_and_loads_points_table(self):
        temp_db_path, load_counts = self.load_temp_sample_database()

        self.assertEqual(load_counts["point_records"], 17)

        with sqlite3.connect(temp_db_path) as connection:
            table_exists = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'points'
                """
            ).fetchone()
            point_count = connection.execute(
                "SELECT COUNT(*) FROM points"
            ).fetchone()[0]
            point_ids = {
                row[0]
                for row in connection.execute(
                    "SELECT id FROM points"
                )
            }

        self.assertIsNotNone(table_exists)
        self.assertEqual(point_count, 17)
        self.assertTrue(REQUIRED_POINTS.issubset(point_ids))

    def test_sqlite_loader_creates_and_loads_alarm_rules_table(self):
        temp_db_path, load_counts = self.load_temp_sample_database()

        self.assertEqual(load_counts["alarm_rule_records"], 7)

        with sqlite3.connect(temp_db_path) as connection:
            table_exists = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'alarm_rules'
                """
            ).fetchone()
            alarm_rule_count = connection.execute(
                "SELECT COUNT(*) FROM alarm_rules"
            ).fetchone()[0]
            rule_ids = {
                row[0]
                for row in connection.execute(
                    "SELECT id FROM alarm_rules"
                )
            }

        self.assertIsNotNone(table_exists)
        self.assertEqual(alarm_rule_count, 7)
        self.assertTrue(REQUIRED_ALARM_RULES.issubset(rule_ids))

    def test_backend_point_dictionary_returns_equipment_context(self):
        temp_db_path, _load_counts = self.load_temp_sample_database()

        points = backend_summary.get_point_dictionary(temp_db_path)
        points_by_id = {
            point["id"]: point
            for point in points
        }

        self.assertEqual(len(points), 17)
        self.assertEqual(points_by_id["UPS-A_OUTPUT_KW"]["equipment_id"], "UPS-A")
        self.assertEqual(points_by_id["UPS-A_OUTPUT_KW"]["location"], "Electrical Room A")
        self.assertEqual(points_by_id["CRAC-2_SUPPLY_AIR_TEMP"]["source_system"], "BMS")

    def test_backend_alarm_rule_catalog_returns_point_context(self):
        temp_db_path, _load_counts = self.load_temp_sample_database()

        alarm_rules = backend_summary.get_alarm_rule_catalog(temp_db_path)
        rules_by_id = {
            rule["id"]: rule
            for rule in alarm_rules
        }

        self.assertEqual(len(alarm_rules), 7)
        self.assertEqual(
            rules_by_id["RULE-UPS-A-ON-BATTERY"]["point_name"],
            "BATTERY_STATUS",
        )
        self.assertEqual(
            rules_by_id["RULE-ATS-1-NORMAL-SOURCE-UNAVAILABLE"]["equipment_id"],
            "ATS-1",
        )
        self.assertTrue(rules_by_id["RULE-GEN-1-LOW-FUEL"]["enabled"])

    def test_loader_normalizes_optional_catalog_values(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        temp_path = Path(temp_dir.name)
        temp_db_path = temp_path / "facilityops_test.sqlite3"
        point_csv_path = temp_path / "points.csv"
        alarm_rule_csv_path = temp_path / "alarm_rules.csv"

        write_csv_rows(
            point_csv_path,
            load_alarm_db.POINT_COLUMNS,
            [
                {
                    "id": "TEST_OPTIONAL_POINT",
                    "equipment_id": "UPS-A",
                    "point_name": "OPTIONAL_POINT",
                    "display_name": "Optional Point",
                    "point_type": "sensor",
                    "data_type": "analog",
                    "unit": "null",
                    "normal_min": "",
                    "normal_max": "n/a",
                    "source_system": "SIMULATED",
                    "description": "Optional field test point",
                    "created_at": "2026-05-01 00:00",
                    "updated_at": "2026-05-01 00:00",
                }
            ],
        )
        write_csv_rows(
            alarm_rule_csv_path,
            load_alarm_db.ALARM_RULE_COLUMNS,
            [
                {
                    "id": "RULE-TEST-OPTIONAL",
                    "point_id": "TEST_OPTIONAL_POINT",
                    "rule_name": "Optional field test rule",
                    "rule_type": "analog_limit",
                    "operator": ">",
                    "threshold_value": "",
                    "clear_value": "null",
                    "severity": "Info",
                    "alarm_message": "Optional field test alarm",
                    "enabled": "false",
                    "delay_seconds": "0",
                    "created_at": "2026-05-01 00:00",
                    "updated_at": "2026-05-01 00:00",
                }
            ],
        )

        load_alarm_db.load_equipment_to_sqlite(db_path=temp_db_path)
        load_alarm_db.load_points_to_sqlite(point_csv_path, temp_db_path)
        load_alarm_db.load_alarm_rules_to_sqlite(alarm_rule_csv_path, temp_db_path)

        with sqlite3.connect(temp_db_path) as connection:
            point_row = connection.execute(
                """
                SELECT unit, normal_min, normal_max
                FROM points
                WHERE id = 'TEST_OPTIONAL_POINT'
                """
            ).fetchone()
            alarm_rule_row = connection.execute(
                """
                SELECT threshold_value, clear_value, enabled
                FROM alarm_rules
                WHERE id = 'RULE-TEST-OPTIONAL'
                """
            ).fetchone()

        self.assertEqual(point_row, ("", None, None))
        self.assertEqual(alarm_rule_row, ("", "", 0))

    def test_points_endpoint_returns_data(self):
        temp_db_path, _load_counts = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "get_point_dictionary",
                lambda: backend_summary.get_point_dictionary(temp_db_path),
            ),
        ):
            status, data = get_json_from_asgi_app(backend_main.app, "/points")

        self.assertEqual(status, 200)
        self.assertIn("points", data)
        self.assertEqual(len(data["points"]), 17)

        points_by_id = {
            point["id"]: point
            for point in data["points"]
        }
        self.assertEqual(
            points_by_id["CHW-P-1_DISCHARGE_PRESSURE"]["equipment_id"],
            "CHW-P-1",
        )
        self.assertEqual(
            points_by_id["CHW-P-1_DISCHARGE_PRESSURE"]["location"],
            "Central Plant",
        )

    def test_alarm_rules_endpoint_returns_data(self):
        temp_db_path, _load_counts = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "get_alarm_rule_catalog",
                lambda: backend_summary.get_alarm_rule_catalog(temp_db_path),
            ),
        ):
            status, data = get_json_from_asgi_app(backend_main.app, "/alarm-rules")

        self.assertEqual(status, 200)
        self.assertIn("alarm_rules", data)
        self.assertEqual(len(data["alarm_rules"]), 7)

        alarm_rules_by_id = {
            rule["id"]: rule
            for rule in data["alarm_rules"]
        }
        self.assertEqual(
            alarm_rules_by_id["RULE-UPS-A-HIGH-LOAD"]["point_id"],
            "UPS-A_OUTPUT_KW",
        )
        self.assertEqual(
            alarm_rules_by_id["RULE-UPS-A-HIGH-LOAD"]["equipment_id"],
            "UPS-A",
        )


class CurrentPointValueTests(unittest.TestCase):
    def load_temp_sample_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        temp_db_path = Path(temp_dir.name) / "facilityops_test.sqlite3"
        load_counts = load_alarm_db.load_sample_data_to_sqlite(db_path=temp_db_path)
        return temp_db_path, load_counts

    def test_sample_current_point_values_csv_exists_with_required_records(self):
        self.assertTrue(load_alarm_db.CURRENT_POINT_VALUE_FILE.exists())

        with open(
            load_alarm_db.CURRENT_POINT_VALUE_FILE,
            mode="r",
            encoding="utf-8",
            newline="",
        ) as file:
            reader = csv.DictReader(file)
            point_ids = {
                row["point_id"]
                for row in reader
            }

        self.assertTrue(REQUIRED_CURRENT_POINT_VALUES.issubset(point_ids))

    def test_sqlite_loader_creates_and_loads_current_point_values_table(self):
        temp_db_path, load_counts = self.load_temp_sample_database()

        self.assertEqual(load_counts["current_point_value_records"], 17)
        self.assertEqual(load_counts["point_sample_records"], 17)
        reload_counts = load_alarm_db.load_sample_data_to_sqlite(db_path=temp_db_path)
        self.assertEqual(reload_counts["current_point_value_records"], 17)
        self.assertEqual(reload_counts["point_sample_records"], 17)

        with sqlite3.connect(temp_db_path) as connection:
            table_exists = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'current_point_values'
                """
            ).fetchone()
            current_value_count = connection.execute(
                "SELECT COUNT(*) FROM current_point_values"
            ).fetchone()[0]
            unique_point_count = connection.execute(
                "SELECT COUNT(DISTINCT point_id) FROM current_point_values"
            ).fetchone()[0]
            current_value_columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(current_point_values)")
            }

        self.assertIsNotNone(table_exists)
        self.assertEqual(current_value_count, 17)
        self.assertEqual(unique_point_count, 17)
        self.assertIn("latest_sample_id", current_value_columns)
        self.assertIn("received_timestamp", current_value_columns)
        self.assertIn("stale_after_seconds", current_value_columns)

    def test_current_point_values_reference_valid_points(self):
        temp_db_path, _load_counts = self.load_temp_sample_database()

        with sqlite3.connect(temp_db_path) as connection:
            missing_point_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM current_point_values
                LEFT JOIN points
                    ON current_point_values.point_id = points.id
                WHERE points.id IS NULL
                """
            ).fetchone()[0]

        self.assertEqual(missing_point_count, 0)

    def test_loader_normalizes_optional_current_point_values(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        temp_path = Path(temp_dir.name)
        temp_db_path = temp_path / "facilityops_test.sqlite3"
        current_point_value_csv_path = temp_path / "current_point_values.csv"

        write_csv_rows(
            current_point_value_csv_path,
            load_alarm_db.CURRENT_POINT_VALUE_COLUMNS,
            [
                {
                    "id": "CPV-TEST-OPTIONAL",
                    "point_id": "UPS-A_OUTPUT_KW",
                    "value": "null",
                    "quality": "",
                    "source": "n/a",
                    "updated_at": "none",
                }
            ],
        )

        load_alarm_db.load_equipment_to_sqlite(db_path=temp_db_path)
        load_alarm_db.load_points_to_sqlite(db_path=temp_db_path)
        load_alarm_db.load_current_point_values_to_sqlite(
            current_point_value_csv_path,
            temp_db_path,
        )

        with sqlite3.connect(temp_db_path) as connection:
            current_value_row = connection.execute(
                """
                SELECT value, quality, source, source_timestamp
                FROM current_point_values
                WHERE id = 'CPV-TEST-OPTIONAL'
                """
            ).fetchone()

        self.assertEqual(current_value_row[0:3], ("", "UNCERTAIN", ""))
        self.assertNotEqual(current_value_row[3], "")

    def test_backend_current_point_values_returns_point_and_equipment_context(self):
        temp_db_path, _load_counts = self.load_temp_sample_database()

        current_values = backend_summary.get_current_point_values(temp_db_path)
        values_by_point_id = {
            point_value["point_id"]: point_value
            for point_value in current_values
        }

        self.assertEqual(len(current_values), 17)
        self.assertEqual(
            values_by_point_id["CHW-P-1_DISCHARGE_PRESSURE"]["equipment_id"],
            "CHW-P-1",
        )
        self.assertEqual(
            values_by_point_id["CHW-P-1_DISCHARGE_PRESSURE"]["display_name"],
            "CHW-P-1 Discharge Pressure",
        )
        self.assertEqual(
            values_by_point_id["CHW-P-1_DISCHARGE_PRESSURE"]["unit"],
            "psi",
        )
        self.assertNotEqual(
            values_by_point_id["CHW-P-1_DISCHARGE_PRESSURE"]["latest_sample_id"],
            "",
        )
        self.assertEqual(
            values_by_point_id["CHW-P-1_DISCHARGE_PRESSURE"]["stale_after_seconds"],
            300,
        )

    def test_current_point_values_endpoint_returns_data(self):
        temp_db_path, _load_counts = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "get_current_point_values",
                lambda: backend_summary.get_current_point_values(temp_db_path),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/current-point-values",
            )

        self.assertEqual(status, 200)
        self.assertIn("current_point_values", data)
        self.assertEqual(len(data["current_point_values"]), 17)

        values_by_point_id = {
            point_value["point_id"]: point_value
            for point_value in data["current_point_values"]
        }
        self.assertEqual(
            values_by_point_id["UPS-A_OUTPUT_KW"]["equipment_id"],
            "UPS-A",
        )
        self.assertEqual(
            values_by_point_id["UPS-A_OUTPUT_KW"]["point_name"],
            "OUTPUT_KW",
        )


class QualityAwarePointSampleTests(unittest.TestCase):
    def load_temp_sample_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        temp_db_path = Path(temp_dir.name) / "facilityops_test.sqlite3"
        load_alarm_db.load_sample_data_to_sqlite(db_path=temp_db_path)
        with sqlite3.connect(temp_db_path) as connection:
            connection.execute("UPDATE alarm_rules SET delay_seconds = 0")
        return temp_db_path

    def evaluations_by_rule_id(self, db_path):
        return {
            evaluation["id"]: evaluation
            for evaluation in backend_summary.get_rule_evaluations(db_path)
        }

    def ingest_ups_output_sample(self, db_path, value, quality="GOOD", **metadata):
        return backend_summary.ingest_point_sample(
            "UPS-A_OUTPUT_KW",
            value,
            quality=quality,
            source="MANUAL",
            db_path=db_path,
            **metadata,
        )

    def test_loader_creates_point_samples_table(self):
        temp_db_path = self.load_temp_sample_database()

        with sqlite3.connect(temp_db_path) as connection:
            table_exists = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'point_samples'
                """
            ).fetchone()
            sample_count = connection.execute(
                "SELECT COUNT(*) FROM point_samples"
            ).fetchone()[0]

        self.assertIsNotNone(table_exists)
        self.assertEqual(sample_count, 17)

    def test_seeded_current_values_reference_latest_sample_id(self):
        temp_db_path = self.load_temp_sample_database()

        with sqlite3.connect(temp_db_path) as connection:
            missing_sample_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM current_point_values
                LEFT JOIN point_samples
                    ON current_point_values.latest_sample_id = point_samples.id
                WHERE point_samples.id IS NULL
                """
            ).fetchone()[0]

        self.assertEqual(missing_sample_count, 0)

    def test_manual_current_value_update_creates_point_sample(self):
        temp_db_path = self.load_temp_sample_database()

        with sqlite3.connect(temp_db_path) as connection:
            before_count = connection.execute(
                "SELECT COUNT(*) FROM point_samples"
            ).fetchone()[0]

        current_point_value = backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "245",
            quality="GOOD",
            source="MANUAL",
            db_path=temp_db_path,
        )

        with sqlite3.connect(temp_db_path) as connection:
            after_count = connection.execute(
                "SELECT COUNT(*) FROM point_samples"
            ).fetchone()[0]
            sample_quality = connection.execute(
                """
                SELECT quality
                FROM point_samples
                WHERE id = ?
                """,
                (current_point_value["latest_sample_id"],),
            ).fetchone()[0]

        self.assertEqual(after_count, before_count + 1)
        self.assertEqual(sample_quality, "GOOD")
        self.assertEqual(current_point_value["value"], "245")

    def test_manual_point_update_rolls_back_sample_when_projection_update_fails(self):
        temp_db_path = self.load_temp_sample_database()

        with sqlite3.connect(temp_db_path) as connection:
            before_count = connection.execute(
                "SELECT COUNT(*) FROM point_samples"
            ).fetchone()[0]
            before_current_value = connection.execute(
                """
                SELECT value, latest_sample_id
                FROM current_point_values
                WHERE point_id = 'UPS-A_OUTPUT_KW'
                """
            ).fetchone()

        with (
            mock.patch.object(
                backend_summary,
                "upsert_current_point_value_projection",
                side_effect=RuntimeError("projection failed"),
            ),
            self.assertRaises(RuntimeError),
        ):
            backend_summary.update_current_point_value(
                "UPS-A_OUTPUT_KW",
                "245",
                quality="GOOD",
                source="MANUAL",
                db_path=temp_db_path,
            )

        with sqlite3.connect(temp_db_path) as connection:
            after_count = connection.execute(
                "SELECT COUNT(*) FROM point_samples"
            ).fetchone()[0]
            after_current_value = connection.execute(
                """
                SELECT value, latest_sample_id
                FROM current_point_values
                WHERE point_id = 'UPS-A_OUTPUT_KW'
                """
            ).fetchone()

        self.assertEqual(after_count, before_count)
        self.assertEqual(after_current_value, before_current_value)

    def test_scenario_apply_creates_point_samples(self):
        temp_db_path = self.load_temp_sample_database()

        with sqlite3.connect(temp_db_path) as connection:
            before_count = connection.execute(
                "SELECT COUNT(*) FROM point_samples"
            ).fetchone()[0]

        scenario_result = backend_summary.apply_scenario(
            "trigger-ups-high-load",
            db_path=temp_db_path,
        )

        with sqlite3.connect(temp_db_path) as connection:
            after_count = connection.execute(
                "SELECT COUNT(*) FROM point_samples"
            ).fetchone()[0]

        self.assertEqual(after_count, before_count + 1)
        self.assertEqual(scenario_result["current_point_values"][0]["value"], "245")
        self.assertEqual(scenario_result["current_point_values"][0]["source"], "SCENARIO")

    def test_current_point_values_projection_updates_after_sample_ingest(self):
        temp_db_path = self.load_temp_sample_database()

        current_point_value = self.ingest_ups_output_sample(
            temp_db_path,
            "246",
            protocol="SIM",
            address="sim://ups-a/output_kw",
            stale_after_seconds=600,
        )

        self.assertEqual(current_point_value["value"], "246")
        self.assertEqual(current_point_value["protocol"], "SIM")
        self.assertEqual(current_point_value["address"], "sim://ups-a/output_kw")
        self.assertEqual(current_point_value["stale_after_seconds"], 600)
        self.assertFalse(current_point_value["overridden"])
        self.assertFalse(current_point_value["out_of_service"])

    def test_good_sample_can_trigger_rule_evaluation(self):
        temp_db_path = self.load_temp_sample_database()

        self.ingest_ups_output_sample(temp_db_path, "245", quality="GOOD")
        evaluation = self.evaluations_by_rule_id(temp_db_path)["RULE-UPS-A-HIGH-LOAD"]

        self.assertTrue(evaluation["is_triggered"])
        self.assertEqual(evaluation["evaluation_status"], "Triggered")

    def test_bad_sample_does_not_trigger_process_alarm_evaluation(self):
        temp_db_path = self.load_temp_sample_database()

        self.ingest_ups_output_sample(temp_db_path, "245", quality="BAD")
        evaluation = self.evaluations_by_rule_id(temp_db_path)["RULE-UPS-A-HIGH-LOAD"]

        self.assertFalse(evaluation["is_triggered"])
        self.assertEqual(evaluation["evaluation_status"], "BAD_QUALITY")

    def test_uncertain_sample_does_not_trigger_process_alarm_evaluation(self):
        temp_db_path = self.load_temp_sample_database()

        self.ingest_ups_output_sample(temp_db_path, "245", quality="UNKNOWN")
        evaluation = self.evaluations_by_rule_id(temp_db_path)["RULE-UPS-A-HIGH-LOAD"]

        self.assertFalse(evaluation["is_triggered"])
        self.assertEqual(evaluation["quality"], "UNCERTAIN")
        self.assertEqual(evaluation["evaluation_status"], "UNCERTAIN_QUALITY")

    def test_stale_sample_does_not_trigger_process_alarm_evaluation(self):
        temp_db_path = self.load_temp_sample_database()

        self.ingest_ups_output_sample(
            temp_db_path,
            "245",
            quality="GOOD",
            received_timestamp="2026-05-01 12:00:00",
            stale_after_seconds=30,
        )
        with mock.patch.object(
            backend_summary,
            "current_timestamp",
            return_value="2026-05-01 12:01:00",
        ):
            evaluation = self.evaluations_by_rule_id(temp_db_path)[
                "RULE-UPS-A-HIGH-LOAD"
            ]

        self.assertFalse(evaluation["is_triggered"])
        self.assertEqual(evaluation["evaluation_status"], "STALE")

    def test_stale_quality_sample_does_not_trigger_process_alarm_evaluation(self):
        temp_db_path = self.load_temp_sample_database()

        self.ingest_ups_output_sample(temp_db_path, "245", quality="STALE")
        evaluation = self.evaluations_by_rule_id(temp_db_path)["RULE-UPS-A-HIGH-LOAD"]

        self.assertFalse(evaluation["is_triggered"])
        self.assertEqual(evaluation["evaluation_status"], "STALE")

    def test_overridden_sample_does_not_trigger_process_alarm_evaluation(self):
        temp_db_path = self.load_temp_sample_database()

        self.ingest_ups_output_sample(
            temp_db_path,
            "245",
            quality="GOOD",
            overridden=True,
        )
        evaluation = self.evaluations_by_rule_id(temp_db_path)["RULE-UPS-A-HIGH-LOAD"]

        self.assertFalse(evaluation["is_triggered"])
        self.assertEqual(evaluation["evaluation_status"], "OVERRIDDEN")

    def test_out_of_service_sample_does_not_trigger_process_alarm_evaluation(self):
        temp_db_path = self.load_temp_sample_database()

        self.ingest_ups_output_sample(
            temp_db_path,
            "245",
            quality="GOOD",
            out_of_service=True,
        )
        evaluation = self.evaluations_by_rule_id(temp_db_path)["RULE-UPS-A-HIGH-LOAD"]

        self.assertFalse(evaluation["is_triggered"])
        self.assertEqual(evaluation["evaluation_status"], "OUT_OF_SERVICE")

    def test_generated_alarm_evaluation_does_not_create_from_ineligible_sample(self):
        temp_db_path = self.load_temp_sample_database()

        self.ingest_ups_output_sample(temp_db_path, "245", quality="BAD")
        summary = backend_summary.evaluate_generated_alarms(temp_db_path)
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        self.assertEqual(summary["created_count"], 0)
        self.assertEqual(generated_alarms, [])


class PointHealthAuditTests(unittest.TestCase):
    def load_temp_sample_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        temp_db_path = Path(temp_dir.name) / "facilityops_test.sqlite3"
        load_alarm_db.load_sample_data_to_sqlite(db_path=temp_db_path)
        with sqlite3.connect(temp_db_path) as connection:
            connection.execute("UPDATE alarm_rules SET delay_seconds = 0")
        return temp_db_path

    def point_health_events(self, db_path, event_type=None):
        events = [
            event
            for event in backend_summary.get_alarm_events(db_path)
            if event["event_type"].startswith("POINT_")
        ]
        if event_type is not None:
            events = [
                event
                for event in events
                if event["event_type"] == event_type
            ]
        return events

    def test_ingesting_changed_quality_inserts_quality_changed_event(self):
        temp_db_path = self.load_temp_sample_database()

        current_point_value = backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "245",
            quality="BAD",
            source="MANUAL",
            db_path=temp_db_path,
        )
        events = self.point_health_events(temp_db_path, "POINT_QUALITY_CHANGED")

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["rule_id"], None)
        self.assertEqual(events[0]["point_id"], "UPS-A_OUTPUT_KW")
        self.assertEqual(events[0]["equipment_id"], "UPS-A")
        self.assertEqual(events[0]["sample_id"], current_point_value["latest_sample_id"])
        self.assertEqual(events[0]["previous_state"], "GOOD")
        self.assertEqual(events[0]["new_state"], "BAD")
        details = json.loads(events[0]["details_json"])
        self.assertEqual(details["changed_field"], "quality")
        self.assertEqual(details["old_value"], "GOOD")
        self.assertEqual(details["new_value"], "BAD")

    def test_ingesting_same_quality_again_does_not_duplicate_quality_change_event(self):
        temp_db_path = self.load_temp_sample_database()

        backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "245",
            quality="BAD",
            source="MANUAL",
            db_path=temp_db_path,
        )
        backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "246",
            quality="BAD",
            source="MANUAL",
            db_path=temp_db_path,
        )
        events = self.point_health_events(temp_db_path, "POINT_QUALITY_CHANGED")

        self.assertEqual(len(events), 1)

    def test_changing_overridden_flag_inserts_override_changed_event(self):
        temp_db_path = self.load_temp_sample_database()

        backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "245",
            quality="GOOD",
            source="MANUAL",
            overridden=True,
            db_path=temp_db_path,
        )
        events = self.point_health_events(temp_db_path, "POINT_OVERRIDE_CHANGED")

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["point_id"], "UPS-A_OUTPUT_KW")
        details = json.loads(events[0]["details_json"])
        self.assertEqual(details["changed_field"], "overridden")
        self.assertFalse(details["old_value"])
        self.assertTrue(details["new_value"])

    def test_changing_out_of_service_flag_inserts_out_of_service_changed_event(self):
        temp_db_path = self.load_temp_sample_database()

        backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "245",
            quality="GOOD",
            source="MANUAL",
            out_of_service=True,
            db_path=temp_db_path,
        )
        events = self.point_health_events(temp_db_path, "POINT_OUT_OF_SERVICE_CHANGED")

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["point_id"], "UPS-A_OUTPUT_KW")
        details = json.loads(events[0]["details_json"])
        self.assertEqual(details["changed_field"], "out_of_service")
        self.assertFalse(details["old_value"])
        self.assertTrue(details["new_value"])

    def test_point_sample_ingest_rolls_back_when_health_event_insert_fails(self):
        temp_db_path = self.load_temp_sample_database()

        with sqlite3.connect(temp_db_path) as connection:
            before_sample_count = connection.execute(
                "SELECT COUNT(*) FROM point_samples"
            ).fetchone()[0]
            before_current_value = connection.execute(
                """
                SELECT value, quality, latest_sample_id
                FROM current_point_values
                WHERE point_id = 'UPS-A_OUTPUT_KW'
                """
            ).fetchone()

        with (
            mock.patch.object(
                backend_summary,
                "insert_alarm_event",
                side_effect=RuntimeError("point health event failed"),
            ),
            self.assertRaises(RuntimeError),
        ):
            backend_summary.update_current_point_value(
                "UPS-A_OUTPUT_KW",
                "245",
                quality="BAD",
                source="MANUAL",
                db_path=temp_db_path,
            )

        with sqlite3.connect(temp_db_path) as connection:
            after_sample_count = connection.execute(
                "SELECT COUNT(*) FROM point_samples"
            ).fetchone()[0]
            after_current_value = connection.execute(
                """
                SELECT value, quality, latest_sample_id
                FROM current_point_values
                WHERE point_id = 'UPS-A_OUTPUT_KW'
                """
            ).fetchone()

        self.assertEqual(after_sample_count, before_sample_count)
        self.assertEqual(after_current_value, before_current_value)
        self.assertEqual(self.point_health_events(temp_db_path), [])

    def test_point_health_evaluation_inserts_stale_event_for_newly_stale_point(self):
        temp_db_path = self.load_temp_sample_database()
        current_point_value = backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "245",
            quality="GOOD",
            source="MANUAL",
            received_timestamp="2026-05-01 12:00:00",
            stale_after_seconds=30,
            db_path=temp_db_path,
        )

        summary = backend_summary.evaluate_point_health(
            temp_db_path,
            evaluation_timestamp="2026-05-01 12:01:00",
        )
        events = self.point_health_events(temp_db_path, "POINT_STALE")

        self.assertEqual(summary["checked_count"], 17)
        self.assertEqual(summary["stale_count"], 1)
        self.assertEqual(summary["new_stale_events_count"], 1)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["point_id"], "UPS-A_OUTPUT_KW")
        self.assertEqual(events[0]["sample_id"], current_point_value["latest_sample_id"])
        self.assertEqual(events[0]["previous_state"], "Not stale")
        self.assertEqual(events[0]["new_state"], "Stale")
        details = json.loads(events[0]["details_json"])
        self.assertEqual(details["stale_after_seconds"], 30)
        self.assertEqual(details["evaluation_timestamp"], "2026-05-01 12:01:00")

    def test_repeated_point_health_evaluation_does_not_duplicate_stale_event(self):
        temp_db_path = self.load_temp_sample_database()
        backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "245",
            quality="GOOD",
            source="MANUAL",
            received_timestamp="2026-05-01 12:00:00",
            stale_after_seconds=30,
            db_path=temp_db_path,
        )

        first_summary = backend_summary.evaluate_point_health(
            temp_db_path,
            evaluation_timestamp="2026-05-01 12:01:00",
        )
        second_summary = backend_summary.evaluate_point_health(
            temp_db_path,
            evaluation_timestamp="2026-05-01 12:02:00",
        )
        events = self.point_health_events(temp_db_path, "POINT_STALE")

        self.assertEqual(first_summary["new_stale_events_count"], 1)
        self.assertEqual(second_summary["new_stale_events_count"], 0)
        self.assertEqual(len(events), 1)

    def test_point_health_evaluate_endpoint_returns_summary_counts(self):
        temp_db_path = self.load_temp_sample_database()
        backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "245",
            quality="GOOD",
            source="MANUAL",
            received_timestamp="2026-05-01 12:00:00",
            stale_after_seconds=30,
            db_path=temp_db_path,
        )

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "evaluate_point_health",
                lambda: backend_summary.evaluate_point_health(
                    temp_db_path,
                    evaluation_timestamp="2026-05-01 12:01:00",
                ),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/point-health/evaluate",
                method="POST",
            )

        self.assertEqual(status, 200)
        self.assertEqual(data["checked_count"], 17)
        self.assertEqual(data["stale_count"], 1)
        self.assertEqual(data["new_stale_events_count"], 1)

    def test_alarm_events_endpoint_returns_point_health_context(self):
        temp_db_path = self.load_temp_sample_database()
        backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "245",
            quality="BAD",
            source="MANUAL",
            db_path=temp_db_path,
        )

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "get_alarm_events",
                lambda: backend_summary.get_alarm_events(temp_db_path),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/alarm-events",
            )

        self.assertEqual(status, 200)
        self.assertEqual(len(data["alarm_events"]), 1)

        event = data["alarm_events"][0]
        self.assertEqual(event["event_type"], "POINT_QUALITY_CHANGED")
        self.assertEqual(event["rule_id"], None)
        self.assertEqual(event["rule_name"], "")
        self.assertEqual(event["point_id"], "UPS-A_OUTPUT_KW")
        self.assertEqual(event["point_name"], "OUTPUT_KW")
        self.assertEqual(event["display_name"], "UPS-A Output kW")
        self.assertEqual(event["equipment_id"], "UPS-A")

    def test_generated_alarm_evaluation_does_not_create_from_bad_health_sample(self):
        temp_db_path = self.load_temp_sample_database()

        backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "245",
            quality="BAD",
            source="MANUAL",
            db_path=temp_db_path,
        )
        summary = backend_summary.evaluate_generated_alarms(temp_db_path)
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        self.assertEqual(summary["created_count"], 0)
        self.assertEqual(generated_alarms, [])


class SimulatedDriverIngestTests(unittest.TestCase):
    def load_temp_sample_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        temp_db_path = Path(temp_dir.name) / "facilityops_test.sqlite3"
        load_alarm_db.load_sample_data_to_sqlite(db_path=temp_db_path)
        return temp_db_path

    def fixed_driver(self):
        return SimulatedDriver(read_timestamp="2026-05-01 12:00:00")

    def current_values_by_point(self, db_path):
        return {
            point_value["point_id"]: point_value
            for point_value in backend_summary.get_current_point_values(db_path)
        }

    def test_simulated_driver_returns_deterministic_sample_dictionaries(self):
        driver = self.fixed_driver()

        first_samples = driver.read_samples()
        second_samples = driver.read_current_samples()
        point_ids = {
            sample["point_id"]
            for sample in first_samples
        }

        self.assertEqual(first_samples, second_samples)
        self.assertEqual(
            point_ids,
            {
                "UPS-A_OUTPUT_KW",
                "CRAC-2_SUPPLY_AIR_TEMP",
                "GEN-1_FUEL_LEVEL",
            },
        )
        self.assertEqual(first_samples[0]["value"], "205")

    def test_simulated_samples_include_required_metadata(self):
        samples = self.fixed_driver().read_samples()

        for sample in samples:
            self.assertIn("point_id", sample)
            self.assertIn("value", sample)
            self.assertEqual(sample["quality"], "GOOD")
            self.assertEqual(sample["source"], "SIMULATED")
            self.assertEqual(sample["protocol"], "SIMULATED")
            self.assertEqual(sample["source_timestamp"], "2026-05-01 12:00:00")
            self.assertEqual(sample["received_timestamp"], "2026-05-01 12:00:00")
            self.assertTrue(sample["address"].startswith("simulated://"))
            self.assertEqual(sample["stale_after_seconds"], 300)
            self.assertFalse(sample["overridden"])
            self.assertFalse(sample["out_of_service"])

    def test_ingest_driver_samples_updates_current_value_projection(self):
        temp_db_path = self.load_temp_sample_database()

        with sqlite3.connect(temp_db_path) as connection:
            before_sample_count = connection.execute(
                "SELECT COUNT(*) FROM point_samples"
            ).fetchone()[0]

        summary = ingest_driver_samples(
            self.fixed_driver().read_samples(),
            db_path=temp_db_path,
        )

        with sqlite3.connect(temp_db_path) as connection:
            after_sample_count = connection.execute(
                "SELECT COUNT(*) FROM point_samples"
            ).fetchone()[0]
        current_values = self.current_values_by_point(temp_db_path)

        self.assertEqual(summary["samples_received"], 3)
        self.assertEqual(summary["samples_ingested"], 3)
        self.assertEqual(summary["failed_samples"], [])
        self.assertEqual(after_sample_count, before_sample_count + 3)
        self.assertEqual(current_values["UPS-A_OUTPUT_KW"]["value"], "205")
        self.assertEqual(current_values["UPS-A_OUTPUT_KW"]["source"], "SIMULATED")
        self.assertEqual(current_values["UPS-A_OUTPUT_KW"]["protocol"], "SIMULATED")
        self.assertEqual(
            current_values["UPS-A_OUTPUT_KW"]["address"],
            "simulated://northstar/ups-a/output_kw",
        )
        self.assertEqual(current_values["GEN-1_FUEL_LEVEL"]["value"], "78")

    def test_simulated_driver_read_endpoint_ingests_samples(self):
        temp_db_path = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "SimulatedDriver",
                lambda: self.fixed_driver(),
            ),
            mock.patch.object(
                backend_main,
                "ingest_driver_samples",
                lambda samples: ingest_driver_samples(samples, db_path=temp_db_path),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/drivers/simulated/read",
                method="POST",
            )

        current_values = self.current_values_by_point(temp_db_path)

        self.assertEqual(status, 200)
        self.assertEqual(data["samples_received"], 3)
        self.assertEqual(data["samples_ingested"], 3)
        self.assertEqual(data["failed_samples"], [])
        self.assertEqual(current_values["CRAC-2_SUPPLY_AIR_TEMP"]["value"], "61.5")
        self.assertEqual(current_values["CRAC-2_SUPPLY_AIR_TEMP"]["source"], "SIMULATED")

    def test_simulated_driver_read_does_not_create_generated_alarms(self):
        temp_db_path = self.load_temp_sample_database()

        ingest_driver_samples(
            self.fixed_driver().read_samples(),
            db_path=temp_db_path,
        )
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        self.assertEqual(generated_alarms, [])

    def test_invalid_simulated_sample_is_reported_without_blocking_valid_samples(self):
        temp_db_path = self.load_temp_sample_database()
        samples = self.fixed_driver().read_samples() + [
            {
                "point_id": "DOES-NOT-EXIST",
                "value": "1",
                "quality": "GOOD",
                "source": "SIMULATED",
                "protocol": "SIMULATED",
            },
        ]

        summary = ingest_driver_samples(samples, db_path=temp_db_path)
        current_values = self.current_values_by_point(temp_db_path)

        self.assertEqual(summary["samples_received"], 4)
        self.assertEqual(summary["samples_ingested"], 3)
        self.assertEqual(len(summary["failed_samples"]), 1)
        self.assertEqual(summary["failed_samples"][0]["point_id"], "DOES-NOT-EXIST")
        self.assertIn("Point not found", summary["failed_samples"][0]["error"])
        self.assertEqual(current_values["UPS-A_OUTPUT_KW"]["value"], "205")


class ManualCurrentPointValueUpdateTests(unittest.TestCase):
    def load_temp_sample_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        temp_db_path = Path(temp_dir.name) / "facilityops_test.sqlite3"
        load_alarm_db.load_sample_data_to_sqlite(db_path=temp_db_path)
        return temp_db_path

    def test_updating_existing_current_point_value_works(self):
        temp_db_path = self.load_temp_sample_database()

        current_point_value = backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "245",
            quality="GOOD",
            source="MANUAL",
            db_path=temp_db_path,
        )

        self.assertEqual(current_point_value["point_id"], "UPS-A_OUTPUT_KW")
        self.assertEqual(current_point_value["value"], "245")
        self.assertEqual(current_point_value["quality"], "GOOD")
        self.assertEqual(current_point_value["source"], "MANUAL")
        self.assertEqual(current_point_value["equipment_id"], "UPS-A")
        self.assertEqual(current_point_value["display_name"], "UPS-A Output kW")

    def test_creating_current_point_value_for_existing_point_works(self):
        temp_db_path = self.load_temp_sample_database()

        with sqlite3.connect(temp_db_path) as connection:
            connection.execute(
                """
                DELETE FROM current_point_values
                WHERE point_id = 'UPS-A_OUTPUT_KW'
                """
            )

        current_point_value = backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "210",
            quality="GOOD",
            source="MANUAL",
            db_path=temp_db_path,
        )

        self.assertEqual(current_point_value["id"], "CPV-UPS-A_OUTPUT_KW")
        self.assertEqual(current_point_value["point_id"], "UPS-A_OUTPUT_KW")
        self.assertEqual(current_point_value["value"], "210")
        self.assertEqual(current_point_value["source"], "MANUAL")

    def test_invalid_manual_update_inputs_raise_predictable_errors(self):
        temp_db_path = self.load_temp_sample_database()

        with self.assertRaises(LookupError):
            backend_summary.update_current_point_value(
                "DOES_NOT_EXIST",
                "1",
                db_path=temp_db_path,
            )
        with self.assertRaises(ValueError):
            backend_summary.update_current_point_value(
                "UPS-A_OUTPUT_KW",
                "245",
                quality="INVALID",
                db_path=temp_db_path,
            )
        with self.assertRaises(ValueError):
            backend_summary.update_current_point_value(
                "UPS-A_OUTPUT_KW",
                "245",
                source="INVALID",
                db_path=temp_db_path,
            )

    def test_update_endpoint_returns_context(self):
        temp_db_path = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "update_current_point_value",
                lambda point_id, value, quality="GOOD", source="MANUAL": (
                    backend_summary.update_current_point_value(
                        point_id,
                        value,
                        quality=quality,
                        source=source,
                        db_path=temp_db_path,
                    )
                ),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/current-point-values/UPS-A_OUTPUT_KW",
                method="PUT",
                body={
                    "value": "245",
                    "quality": "GOOD",
                    "source": "MANUAL",
                },
            )

        self.assertEqual(status, 200)
        current_point_value = data["current_point_value"]
        self.assertEqual(current_point_value["point_id"], "UPS-A_OUTPUT_KW")
        self.assertEqual(current_point_value["value"], "245")
        self.assertEqual(current_point_value["quality"], "GOOD")
        self.assertEqual(current_point_value["source"], "MANUAL")
        self.assertEqual(current_point_value["equipment_id"], "UPS-A")
        self.assertEqual(current_point_value["point_name"], "OUTPUT_KW")
        self.assertEqual(current_point_value["unit"], "kW")

    def test_update_endpoint_returns_error_for_invalid_point_id(self):
        temp_db_path = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "update_current_point_value",
                lambda point_id, value, quality="GOOD", source="MANUAL": (
                    backend_summary.update_current_point_value(
                        point_id,
                        value,
                        quality=quality,
                        source=source,
                        db_path=temp_db_path,
                    )
                ),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/current-point-values/DOES_NOT_EXIST",
                method="PUT",
                body={
                    "value": "1",
                    "quality": "GOOD",
                    "source": "MANUAL",
                },
            )

        self.assertEqual(status, 404)
        self.assertIn("Point not found", data["error"])

    def test_update_endpoint_returns_error_for_invalid_quality(self):
        temp_db_path = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "update_current_point_value",
                lambda point_id, value, quality="GOOD", source="MANUAL": (
                    backend_summary.update_current_point_value(
                        point_id,
                        value,
                        quality=quality,
                        source=source,
                        db_path=temp_db_path,
                    )
                ),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/current-point-values/UPS-A_OUTPUT_KW",
                method="PUT",
                body={
                    "value": "245",
                    "quality": "INVALID",
                    "source": "MANUAL",
                },
            )

        self.assertEqual(status, 400)
        self.assertIn("quality must be one of", data["error"])

    def test_update_endpoint_returns_error_for_invalid_source(self):
        temp_db_path = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "update_current_point_value",
                lambda point_id, value, quality="GOOD", source="MANUAL": (
                    backend_summary.update_current_point_value(
                        point_id,
                        value,
                        quality=quality,
                        source=source,
                        db_path=temp_db_path,
                    )
                ),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/current-point-values/UPS-A_OUTPUT_KW",
                method="PUT",
                body={
                    "value": "245",
                    "quality": "GOOD",
                    "source": "INVALID",
                },
            )

        self.assertEqual(status, 400)
        self.assertIn("source must be one of", data["error"])

    def test_rule_evaluations_reflect_manual_updates(self):
        temp_db_path = self.load_temp_sample_database()

        backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "245",
            quality="GOOD",
            source="MANUAL",
            db_path=temp_db_path,
        )
        evaluations = backend_summary.get_rule_evaluations(temp_db_path)
        evaluations_by_rule_id = {
            evaluation["id"]: evaluation
            for evaluation in evaluations
        }

        self.assertTrue(evaluations_by_rule_id["RULE-UPS-A-HIGH-LOAD"]["is_triggered"])
        self.assertEqual(
            evaluations_by_rule_id["RULE-UPS-A-HIGH-LOAD"]["current_value"],
            "245",
        )
        self.assertEqual(
            evaluations_by_rule_id["RULE-UPS-A-HIGH-LOAD"]["source"],
            "MANUAL",
        )

    def test_manual_update_does_not_create_generated_alarms(self):
        temp_db_path = self.load_temp_sample_database()

        backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "245",
            quality="GOOD",
            source="MANUAL",
            db_path=temp_db_path,
        )

        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        self.assertEqual(generated_alarms, [])


class AlarmRuleEditingTests(unittest.TestCase):
    def load_temp_sample_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        temp_db_path = Path(temp_dir.name) / "facilityops_test.sqlite3"
        load_alarm_db.load_sample_data_to_sqlite(db_path=temp_db_path)
        return temp_db_path

    def rule_by_id(self, db_path, rule_id):
        alarm_rules = backend_summary.get_alarm_rule_catalog(db_path)
        return {
            rule["id"]: rule
            for rule in alarm_rules
        }[rule_id]

    def evaluations_by_rule_id(self, db_path):
        return {
            evaluation["id"]: evaluation
            for evaluation in backend_summary.get_rule_evaluations(db_path)
        }

    def test_updating_threshold_value_works(self):
        temp_db_path = self.load_temp_sample_database()

        alarm_rule = backend_summary.update_alarm_rule(
            "RULE-UPS-A-HIGH-LOAD",
            {"threshold_value": "250"},
            db_path=temp_db_path,
        )

        self.assertEqual(alarm_rule["threshold_value"], "250")
        self.assertEqual(
            self.rule_by_id(temp_db_path, "RULE-UPS-A-HIGH-LOAD")["threshold_value"],
            "250",
        )

    def test_updating_clear_value_works(self):
        temp_db_path = self.load_temp_sample_database()

        alarm_rule = backend_summary.update_alarm_rule(
            "RULE-UPS-A-HIGH-LOAD",
            {"clear_value": "225"},
            db_path=temp_db_path,
        )

        self.assertEqual(alarm_rule["clear_value"], "225")

    def test_blank_threshold_and_clear_values_normalize_to_empty_strings(self):
        temp_db_path = self.load_temp_sample_database()

        alarm_rule = backend_summary.update_alarm_rule(
            "RULE-UPS-A-HIGH-LOAD",
            {
                "threshold_value": "null",
                "clear_value": "",
            },
            db_path=temp_db_path,
        )

        self.assertEqual(alarm_rule["threshold_value"], "")
        self.assertEqual(alarm_rule["clear_value"], "")

    def test_updating_delay_seconds_works(self):
        temp_db_path = self.load_temp_sample_database()

        alarm_rule = backend_summary.update_alarm_rule(
            "RULE-UPS-A-HIGH-LOAD",
            {"delay_seconds": "45"},
            db_path=temp_db_path,
        )

        self.assertEqual(alarm_rule["delay_seconds"], 45)

    def test_updating_severity_works(self):
        temp_db_path = self.load_temp_sample_database()

        alarm_rule = backend_summary.update_alarm_rule(
            "RULE-UPS-A-HIGH-LOAD",
            {"severity": "Critical"},
            db_path=temp_db_path,
        )

        self.assertEqual(alarm_rule["severity"], "Critical")

    def test_updating_enabled_works(self):
        temp_db_path = self.load_temp_sample_database()

        alarm_rule = backend_summary.update_alarm_rule(
            "RULE-UPS-A-HIGH-LOAD",
            {"enabled": "false"},
            db_path=temp_db_path,
        )

        self.assertFalse(alarm_rule["enabled"])

    def test_alarm_rule_update_endpoint_returns_context(self):
        temp_db_path = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "update_alarm_rule",
                lambda rule_id, payload: backend_summary.update_alarm_rule(
                    rule_id,
                    payload,
                    db_path=temp_db_path,
                ),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/alarm-rules/RULE-UPS-A-HIGH-LOAD",
                method="PUT",
                body={
                    "threshold_value": "250",
                    "clear_value": "230",
                    "delay_seconds": 30,
                    "severity": "Critical",
                    "alarm_message": "UPS-A load is above edited threshold",
                    "enabled": True,
                },
            )

        self.assertEqual(status, 200)
        alarm_rule = data["alarm_rule"]
        self.assertEqual(alarm_rule["id"], "RULE-UPS-A-HIGH-LOAD")
        self.assertEqual(alarm_rule["threshold_value"], "250")
        self.assertEqual(alarm_rule["clear_value"], "230")
        self.assertEqual(alarm_rule["delay_seconds"], 30)
        self.assertEqual(alarm_rule["severity"], "Critical")
        self.assertTrue(alarm_rule["enabled"])
        self.assertEqual(alarm_rule["point_id"], "UPS-A_OUTPUT_KW")
        self.assertEqual(alarm_rule["equipment_id"], "UPS-A")
        self.assertEqual(alarm_rule["point_name"], "OUTPUT_KW")

    def test_alarm_rule_update_endpoint_returns_error_for_invalid_rule_id(self):
        temp_db_path = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "update_alarm_rule",
                lambda rule_id, payload: backend_summary.update_alarm_rule(
                    rule_id,
                    payload,
                    db_path=temp_db_path,
                ),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/alarm-rules/DOES-NOT-EXIST",
                method="PUT",
                body={"threshold_value": "250"},
            )

        self.assertEqual(status, 404)
        self.assertIn("Alarm rule not found", data["error"])

    def test_alarm_rule_update_endpoint_returns_error_for_invalid_severity(self):
        temp_db_path = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "update_alarm_rule",
                lambda rule_id, payload: backend_summary.update_alarm_rule(
                    rule_id,
                    payload,
                    db_path=temp_db_path,
                ),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/alarm-rules/RULE-UPS-A-HIGH-LOAD",
                method="PUT",
                body={"severity": "Emergency"},
            )

        self.assertEqual(status, 400)
        self.assertIn("severity must be one of", data["error"])

    def test_alarm_rule_update_endpoint_returns_error_for_invalid_delay_seconds(self):
        temp_db_path = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "update_alarm_rule",
                lambda rule_id, payload: backend_summary.update_alarm_rule(
                    rule_id,
                    payload,
                    db_path=temp_db_path,
                ),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/alarm-rules/RULE-UPS-A-HIGH-LOAD",
                method="PUT",
                body={"delay_seconds": "-1"},
            )

        self.assertEqual(status, 400)
        self.assertIn("delay_seconds must be a non-negative integer", data["error"])

    def test_invalid_enabled_value_returns_predictable_error(self):
        temp_db_path = self.load_temp_sample_database()

        with self.assertRaises(ValueError):
            backend_summary.update_alarm_rule(
                "RULE-UPS-A-HIGH-LOAD",
                {"enabled": "maybe"},
                db_path=temp_db_path,
            )

    def test_read_only_alarm_rule_fields_cannot_be_updated(self):
        temp_db_path = self.load_temp_sample_database()

        with self.assertRaises(ValueError):
            backend_summary.update_alarm_rule(
                "RULE-UPS-A-HIGH-LOAD",
                {"point_id": "GEN-1_FUEL_LEVEL"},
                db_path=temp_db_path,
            )

    def test_disabling_rule_makes_rule_evaluation_disabled(self):
        temp_db_path = self.load_temp_sample_database()
        backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "245",
            db_path=temp_db_path,
        )

        backend_summary.update_alarm_rule(
            "RULE-UPS-A-HIGH-LOAD",
            {"enabled": False},
            db_path=temp_db_path,
        )
        evaluation = self.evaluations_by_rule_id(temp_db_path)["RULE-UPS-A-HIGH-LOAD"]

        self.assertFalse(evaluation["enabled"])
        self.assertFalse(evaluation["is_triggered"])
        self.assertEqual(evaluation["evaluation_status"], "Disabled")

    def test_updating_threshold_changes_rule_evaluation_result(self):
        temp_db_path = self.load_temp_sample_database()
        evaluation_before = self.evaluations_by_rule_id(temp_db_path)[
            "RULE-UPS-A-HIGH-LOAD"
        ]

        backend_summary.update_alarm_rule(
            "RULE-UPS-A-HIGH-LOAD",
            {"threshold_value": "180"},
            db_path=temp_db_path,
        )
        evaluation_after = self.evaluations_by_rule_id(temp_db_path)[
            "RULE-UPS-A-HIGH-LOAD"
        ]

        self.assertFalse(evaluation_before["is_triggered"])
        self.assertTrue(evaluation_after["is_triggered"])
        self.assertEqual(evaluation_after["threshold_value"], "180")

    def test_updating_rule_does_not_create_generated_alarms(self):
        temp_db_path = self.load_temp_sample_database()
        backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "245",
            db_path=temp_db_path,
        )

        backend_summary.update_alarm_rule(
            "RULE-UPS-A-HIGH-LOAD",
            {"threshold_value": "230"},
            db_path=temp_db_path,
        )
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        self.assertEqual(generated_alarms, [])


class AlarmRuleCreationTests(unittest.TestCase):
    def load_temp_sample_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        temp_db_path = Path(temp_dir.name) / "facilityops_test.sqlite3"
        load_alarm_db.load_sample_data_to_sqlite(db_path=temp_db_path)
        return temp_db_path

    def base_payload(self, **overrides):
        payload = {
            "id": "RULE-TEST-UPS-HIGH-LOAD",
            "point_id": "UPS-A_OUTPUT_KW",
            "rule_name": "Test UPS high load",
            "rule_type": "analog_limit",
            "operator": ">",
            "threshold_value": "200",
            "clear_value": "180",
            "delay_seconds": "0",
            "severity": "Warning",
            "alarm_message": "UPS-A load is above the test limit",
            "enabled": True,
        }
        payload.update(overrides)
        return payload

    def rules_by_id(self, db_path):
        return {
            rule["id"]: rule
            for rule in backend_summary.get_alarm_rule_catalog(db_path)
        }

    def evaluations_by_rule_id(self, db_path):
        return {
            evaluation["id"]: evaluation
            for evaluation in backend_summary.get_rule_evaluations(db_path)
        }

    def test_creating_analog_limit_rule_works(self):
        temp_db_path = self.load_temp_sample_database()

        alarm_rule = backend_summary.create_alarm_rule(
            self.base_payload(),
            db_path=temp_db_path,
        )

        self.assertEqual(alarm_rule["id"], "RULE-TEST-UPS-HIGH-LOAD")
        self.assertEqual(alarm_rule["rule_type"], "analog_limit")
        self.assertEqual(alarm_rule["operator"], ">")
        self.assertEqual(alarm_rule["threshold_value"], "200")
        self.assertEqual(alarm_rule["clear_value"], "180")
        self.assertEqual(alarm_rule["delay_seconds"], 0)
        self.assertTrue(alarm_rule["enabled"])
        self.assertEqual(alarm_rule["point_id"], "UPS-A_OUTPUT_KW")
        self.assertEqual(alarm_rule["equipment_id"], "UPS-A")

    def test_creating_boolean_state_rule_works(self):
        temp_db_path = self.load_temp_sample_database()

        alarm_rule = backend_summary.create_alarm_rule(
            self.base_payload(
                id="RULE-TEST-PUMP-STOPPED",
                point_id="CHW-P-1_RUN_STATUS",
                rule_name="Test pump stopped",
                rule_type="boolean_state",
                operator="==",
                threshold_value="false",
                clear_value="true",
                severity="Critical",
                alarm_message="CHW-P-1 is not running",
                enabled="yes",
            ),
            db_path=temp_db_path,
        )

        self.assertEqual(alarm_rule["id"], "RULE-TEST-PUMP-STOPPED")
        self.assertEqual(alarm_rule["rule_type"], "boolean_state")
        self.assertEqual(alarm_rule["operator"], "==")
        self.assertEqual(alarm_rule["threshold_value"], "false")
        self.assertEqual(alarm_rule["clear_value"], "true")
        self.assertEqual(alarm_rule["equipment_id"], "CHW-P-1")
        self.assertTrue(alarm_rule["enabled"])

    def test_creating_enum_match_rule_works(self):
        temp_db_path = self.load_temp_sample_database()

        alarm_rule = backend_summary.create_alarm_rule(
            self.base_payload(
                id="RULE-TEST-UPS-BATTERY",
                point_id="UPS-A_BATTERY_STATUS",
                rule_name="Test UPS battery",
                rule_type="enum_match",
                operator="==",
                threshold_value="On Battery",
                clear_value="Normal",
                severity="Critical",
                alarm_message="UPS-A is on battery",
                enabled="1",
            ),
            db_path=temp_db_path,
        )

        self.assertEqual(alarm_rule["id"], "RULE-TEST-UPS-BATTERY")
        self.assertEqual(alarm_rule["rule_type"], "enum_match")
        self.assertEqual(alarm_rule["threshold_value"], "On Battery")
        self.assertEqual(alarm_rule["point_id"], "UPS-A_BATTERY_STATUS")
        self.assertEqual(alarm_rule["equipment_id"], "UPS-A")

    def test_duplicate_rule_id_returns_error(self):
        temp_db_path = self.load_temp_sample_database()

        with self.assertRaises(ValueError):
            backend_summary.create_alarm_rule(
                self.base_payload(id="RULE-UPS-A-HIGH-LOAD"),
                db_path=temp_db_path,
            )

    def test_invalid_point_id_returns_error(self):
        temp_db_path = self.load_temp_sample_database()

        with self.assertRaises(LookupError):
            backend_summary.create_alarm_rule(
                self.base_payload(point_id="DOES_NOT_EXIST"),
                db_path=temp_db_path,
            )

    def test_invalid_rule_type_returns_error(self):
        temp_db_path = self.load_temp_sample_database()

        with self.assertRaises(ValueError):
            backend_summary.create_alarm_rule(
                self.base_payload(rule_type="rate_of_change"),
                db_path=temp_db_path,
            )

    def test_invalid_operator_for_rule_type_returns_error(self):
        temp_db_path = self.load_temp_sample_database()

        with self.assertRaises(ValueError):
            backend_summary.create_alarm_rule(
                self.base_payload(
                    rule_type="boolean_state",
                    operator=">",
                    threshold_value="false",
                ),
                db_path=temp_db_path,
            )

    def test_invalid_severity_returns_error(self):
        temp_db_path = self.load_temp_sample_database()

        with self.assertRaises(ValueError):
            backend_summary.create_alarm_rule(
                self.base_payload(severity="Emergency"),
                db_path=temp_db_path,
            )

    def test_invalid_delay_seconds_returns_error(self):
        temp_db_path = self.load_temp_sample_database()

        with self.assertRaises(ValueError):
            backend_summary.create_alarm_rule(
                self.base_payload(delay_seconds="-1"),
                db_path=temp_db_path,
            )

    def test_create_alarm_rule_endpoint_returns_context(self):
        temp_db_path = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "create_alarm_rule",
                lambda payload: backend_summary.create_alarm_rule(
                    payload,
                    db_path=temp_db_path,
                ),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/alarm-rules",
                method="POST",
                body=self.base_payload(),
            )

        self.assertEqual(status, 200)
        alarm_rule = data["alarm_rule"]
        self.assertEqual(alarm_rule["id"], "RULE-TEST-UPS-HIGH-LOAD")
        self.assertEqual(alarm_rule["point_id"], "UPS-A_OUTPUT_KW")
        self.assertEqual(alarm_rule["point_name"], "OUTPUT_KW")
        self.assertEqual(alarm_rule["equipment_id"], "UPS-A")

    def test_create_alarm_rule_endpoint_returns_error_for_duplicate_id(self):
        temp_db_path = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "create_alarm_rule",
                lambda payload: backend_summary.create_alarm_rule(
                    payload,
                    db_path=temp_db_path,
                ),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/alarm-rules",
                method="POST",
                body=self.base_payload(id="RULE-UPS-A-HIGH-LOAD"),
            )

        self.assertEqual(status, 400)
        self.assertIn("Alarm rule already exists", data["error"])

    def test_create_alarm_rule_endpoint_returns_error_for_invalid_point_id(self):
        temp_db_path = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "create_alarm_rule",
                lambda payload: backend_summary.create_alarm_rule(
                    payload,
                    db_path=temp_db_path,
                ),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/alarm-rules",
                method="POST",
                body=self.base_payload(point_id="DOES_NOT_EXIST"),
            )

        self.assertEqual(status, 404)
        self.assertIn("Point not found", data["error"])

    def test_create_alarm_rule_endpoint_returns_error_for_invalid_operator(self):
        temp_db_path = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "create_alarm_rule",
                lambda payload: backend_summary.create_alarm_rule(
                    payload,
                    db_path=temp_db_path,
                ),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/alarm-rules",
                method="POST",
                body=self.base_payload(rule_type="enum_match", operator=">"),
            )

        self.assertEqual(status, 400)
        self.assertIn("operator for enum_match must be one of", data["error"])

    def test_created_rule_appears_in_alarm_rules_and_rule_evaluations(self):
        temp_db_path = self.load_temp_sample_database()
        backend_summary.create_alarm_rule(
            self.base_payload(threshold_value="180"),
            db_path=temp_db_path,
        )

        rules_by_id = self.rules_by_id(temp_db_path)
        evaluations_by_rule_id = self.evaluations_by_rule_id(temp_db_path)

        self.assertIn("RULE-TEST-UPS-HIGH-LOAD", rules_by_id)
        self.assertIn("RULE-TEST-UPS-HIGH-LOAD", evaluations_by_rule_id)
        self.assertTrue(evaluations_by_rule_id["RULE-TEST-UPS-HIGH-LOAD"]["is_triggered"])
        self.assertEqual(
            evaluations_by_rule_id["RULE-TEST-UPS-HIGH-LOAD"]["equipment_id"],
            "UPS-A",
        )

    def test_created_rule_appears_in_get_endpoints(self):
        temp_db_path = self.load_temp_sample_database()
        backend_summary.create_alarm_rule(
            self.base_payload(threshold_value="180"),
            db_path=temp_db_path,
        )

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "get_alarm_rule_catalog",
                lambda: backend_summary.get_alarm_rule_catalog(temp_db_path),
            ),
            mock.patch.object(
                backend_main,
                "get_rule_evaluations",
                lambda: backend_summary.get_rule_evaluations(temp_db_path),
            ),
        ):
            rules_status, rules_data = get_json_from_asgi_app(
                backend_main.app,
                "/alarm-rules",
            )
            evaluations_status, evaluations_data = get_json_from_asgi_app(
                backend_main.app,
                "/rule-evaluations",
            )

        rule_ids = {
            rule["id"]
            for rule in rules_data["alarm_rules"]
        }
        evaluation_ids = {
            evaluation["id"]
            for evaluation in evaluations_data["rule_evaluations"]
        }

        self.assertEqual(rules_status, 200)
        self.assertEqual(evaluations_status, 200)
        self.assertIn("RULE-TEST-UPS-HIGH-LOAD", rule_ids)
        self.assertIn("RULE-TEST-UPS-HIGH-LOAD", evaluation_ids)

    def test_creating_rule_does_not_create_generated_alarms(self):
        temp_db_path = self.load_temp_sample_database()

        backend_summary.create_alarm_rule(
            self.base_payload(threshold_value="180"),
            db_path=temp_db_path,
        )
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        self.assertEqual(generated_alarms, [])


class AlarmRuleAuditTests(unittest.TestCase):
    def load_temp_sample_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        temp_db_path = Path(temp_dir.name) / "facilityops_test.sqlite3"
        load_alarm_db.load_sample_data_to_sqlite(db_path=temp_db_path)
        return temp_db_path

    def base_payload(self, **overrides):
        payload = {
            "id": "RULE-TEST-AUDIT-UPS-HIGH-LOAD",
            "point_id": "UPS-A_OUTPUT_KW",
            "rule_name": "Test audited UPS high load",
            "rule_type": "analog_limit",
            "operator": ">",
            "threshold_value": "200",
            "clear_value": "180",
            "delay_seconds": "0",
            "severity": "Warning",
            "alarm_message": "UPS-A load is above the audited test limit",
            "enabled": True,
        }
        payload.update(overrides)
        return payload

    def rule_by_id(self, db_path, rule_id):
        return {
            rule["id"]: rule
            for rule in backend_summary.get_alarm_rule_catalog(db_path)
        }.get(rule_id)

    def test_creating_alarm_rule_inserts_rule_created_event(self):
        temp_db_path = self.load_temp_sample_database()

        with mock.patch.object(
            backend_summary,
            "current_timestamp",
            return_value="2026-05-01 14:00:00",
        ):
            backend_summary.create_alarm_rule(
                self.base_payload(),
                db_path=temp_db_path,
            )

        events = backend_summary.get_alarm_events(temp_db_path)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "RULE_CREATED")
        self.assertIsNone(events[0]["generated_alarm_id"])
        self.assertEqual(events[0]["rule_id"], "RULE-TEST-AUDIT-UPS-HIGH-LOAD")
        self.assertEqual(events[0]["point_id"], "UPS-A_OUTPUT_KW")
        self.assertEqual(events[0]["equipment_id"], "UPS-A")
        self.assertEqual(events[0]["acknowledged_by"], "local-operator")
        self.assertEqual(events[0]["event_timestamp"], "2026-05-01 14:00:00")
        details = json.loads(events[0]["details_json"])
        created_rule = details["created_rule"]
        self.assertEqual(created_rule["threshold_value"], "200")
        self.assertEqual(created_rule["clear_value"], "180")
        self.assertEqual(created_rule["delay_seconds"], 0)
        self.assertTrue(created_rule["enabled"])

    def test_editing_alarm_rule_inserts_rule_updated_event(self):
        temp_db_path = self.load_temp_sample_database()

        with mock.patch.object(
            backend_summary,
            "current_timestamp",
            return_value="2026-05-01 14:05:00",
        ):
            backend_summary.update_alarm_rule(
                "RULE-UPS-A-HIGH-LOAD",
                {
                    "threshold_value": "250",
                    "clear_value": "225",
                    "delay_seconds": 60,
                    "severity": "Critical",
                    "alarm_message": "UPS-A load is above the edited audit limit",
                    "enabled": False,
                },
                db_path=temp_db_path,
            )

        events = backend_summary.get_alarm_events(temp_db_path)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "RULE_UPDATED")
        self.assertIsNone(events[0]["generated_alarm_id"])
        self.assertEqual(events[0]["rule_id"], "RULE-UPS-A-HIGH-LOAD")
        self.assertEqual(events[0]["point_name"], "OUTPUT_KW")
        self.assertEqual(events[0]["equipment_id"], "UPS-A")
        self.assertEqual(events[0]["acknowledged_by"], "local-operator")
        details = json.loads(events[0]["details_json"])
        self.assertEqual(
            details["changed_fields"],
            [
                "threshold_value",
                "clear_value",
                "delay_seconds",
                "severity",
                "alarm_message",
                "enabled",
            ],
        )
        self.assertEqual(details["old_values"]["threshold_value"], "240")
        self.assertEqual(details["new_values"]["threshold_value"], "250")
        self.assertEqual(details["old_values"]["clear_value"], "220")
        self.assertEqual(details["new_values"]["clear_value"], "225")
        self.assertEqual(details["old_values"]["delay_seconds"], 300)
        self.assertEqual(details["new_values"]["delay_seconds"], 60)
        self.assertEqual(details["old_values"]["severity"], "Warning")
        self.assertEqual(details["new_values"]["severity"], "Critical")
        self.assertTrue(details["old_values"]["enabled"])
        self.assertFalse(details["new_values"]["enabled"])

    def test_noop_alarm_rule_update_does_not_insert_event(self):
        temp_db_path = self.load_temp_sample_database()

        alarm_rule = backend_summary.update_alarm_rule(
            "RULE-UPS-A-HIGH-LOAD",
            {
                "threshold_value": "240",
                "clear_value": "220",
                "delay_seconds": "300",
                "severity": "Warning",
                "alarm_message": "UPS-A load is above the preferred operating range",
                "enabled": True,
            },
            db_path=temp_db_path,
        )
        events = backend_summary.get_alarm_events(temp_db_path)

        self.assertEqual(alarm_rule["threshold_value"], "240")
        self.assertEqual(events, [])

    def test_rule_create_rolls_back_when_audit_event_insert_fails(self):
        temp_db_path = self.load_temp_sample_database()

        with (
            mock.patch.object(
                backend_summary,
                "insert_alarm_event",
                side_effect=RuntimeError("audit insert failed"),
            ),
            self.assertRaises(RuntimeError),
        ):
            backend_summary.create_alarm_rule(
                self.base_payload(),
                db_path=temp_db_path,
            )

        self.assertIsNone(
            self.rule_by_id(temp_db_path, "RULE-TEST-AUDIT-UPS-HIGH-LOAD"),
        )
        self.assertEqual(backend_summary.get_alarm_events(temp_db_path), [])

    def test_rule_update_rolls_back_when_audit_event_insert_fails(self):
        temp_db_path = self.load_temp_sample_database()

        with (
            mock.patch.object(
                backend_summary,
                "insert_alarm_event",
                side_effect=RuntimeError("audit insert failed"),
            ),
            self.assertRaises(RuntimeError),
        ):
            backend_summary.update_alarm_rule(
                "RULE-UPS-A-HIGH-LOAD",
                {"threshold_value": "250"},
                db_path=temp_db_path,
            )

        alarm_rule = self.rule_by_id(temp_db_path, "RULE-UPS-A-HIGH-LOAD")

        self.assertEqual(alarm_rule["threshold_value"], "240")
        self.assertEqual(backend_summary.get_alarm_events(temp_db_path), [])

    def test_alarm_events_endpoint_returns_rule_audit_context(self):
        temp_db_path = self.load_temp_sample_database()
        backend_summary.create_alarm_rule(
            self.base_payload(),
            db_path=temp_db_path,
        )

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "get_alarm_events",
                lambda: backend_summary.get_alarm_events(temp_db_path),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/alarm-events",
            )

        self.assertEqual(status, 200)
        self.assertEqual(len(data["alarm_events"]), 1)

        event = data["alarm_events"][0]
        self.assertEqual(event["event_type"], "RULE_CREATED")
        self.assertEqual(event["rule_id"], "RULE-TEST-AUDIT-UPS-HIGH-LOAD")
        self.assertEqual(event["rule_name"], "Test audited UPS high load")
        self.assertEqual(event["point_name"], "OUTPUT_KW")
        self.assertEqual(event["display_name"], "UPS-A Output kW")
        self.assertEqual(event["equipment_id"], "UPS-A")
        self.assertEqual(event["acknowledged_by"], "local-operator")
        self.assertIn("created_rule", json.loads(event["details_json"]))


class AlarmScenarioTests(unittest.TestCase):
    def load_temp_sample_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        temp_db_path = Path(temp_dir.name) / "facilityops_test.sqlite3"
        load_alarm_db.load_sample_data_to_sqlite(db_path=temp_db_path)
        return temp_db_path

    def test_scenarios_endpoint_returns_available_scenarios(self):
        temp_db_path = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "get_scenarios",
                lambda: backend_summary.get_scenarios(temp_db_path),
            ),
        ):
            status, data = get_json_from_asgi_app(backend_main.app, "/scenarios")

        scenario_ids = {
            scenario["scenario_id"]
            for scenario in data["scenarios"]
        }
        ups_scenario = [
            scenario
            for scenario in data["scenarios"]
            if scenario["scenario_id"] == "trigger-ups-high-load"
        ][0]

        self.assertEqual(status, 200)
        self.assertIn("trigger-ups-high-load", scenario_ids)
        self.assertIn("normalize-ups-high-load", scenario_ids)
        self.assertIn("trigger-crah-high-supply-temp", scenario_ids)
        self.assertIn("normalize-crah-high-supply-temp", scenario_ids)
        self.assertIn("trigger-generator-low-fuel", scenario_ids)
        self.assertIn("normalize-generator-low-fuel", scenario_ids)
        self.assertEqual(
            ups_scenario["affected_points"][0]["point_id"],
            "UPS-A_OUTPUT_KW",
        )
        self.assertEqual(
            ups_scenario["affected_points"][0]["display_name"],
            "UPS-A Output kW",
        )

    def test_trigger_scenario_updates_expected_current_point_value(self):
        temp_db_path = self.load_temp_sample_database()

        result = backend_summary.apply_scenario(
            "trigger-ups-high-load",
            db_path=temp_db_path,
        )
        current_point_value = backend_summary.get_current_point_value(
            "UPS-A_OUTPUT_KW",
            temp_db_path,
        )

        self.assertEqual(result["updated_count"], 1)
        self.assertEqual(current_point_value["value"], "245")
        self.assertEqual(current_point_value["quality"], "GOOD")
        self.assertEqual(current_point_value["source"], "SCENARIO")

    def test_normalize_scenario_updates_expected_current_point_value(self):
        temp_db_path = self.load_temp_sample_database()

        backend_summary.apply_scenario("trigger-ups-high-load", db_path=temp_db_path)
        backend_summary.apply_scenario("normalize-ups-high-load", db_path=temp_db_path)
        current_point_value = backend_summary.get_current_point_value(
            "UPS-A_OUTPUT_KW",
            temp_db_path,
        )

        self.assertEqual(current_point_value["value"], "185")
        self.assertEqual(current_point_value["quality"], "GOOD")
        self.assertEqual(current_point_value["source"], "SCENARIO")

    def test_apply_scenario_endpoint_updates_current_point_value(self):
        temp_db_path = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "apply_scenario",
                lambda scenario_id: backend_summary.apply_scenario(
                    scenario_id,
                    db_path=temp_db_path,
                ),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/scenarios/trigger-generator-low-fuel/apply",
                method="POST",
            )

        self.assertEqual(status, 200)
        self.assertEqual(data["updated_count"], 1)
        self.assertEqual(
            data["current_point_values"][0]["point_id"],
            "GEN-1_FUEL_LEVEL",
        )
        self.assertEqual(data["current_point_values"][0]["value"], "30")
        self.assertEqual(data["current_point_values"][0]["source"], "SCENARIO")

    def test_applying_scenario_changes_rule_evaluation_results(self):
        temp_db_path = self.load_temp_sample_database()

        backend_summary.apply_scenario("trigger-generator-low-fuel", db_path=temp_db_path)
        evaluations = backend_summary.get_rule_evaluations(temp_db_path)
        evaluations_by_rule_id = {
            evaluation["id"]: evaluation
            for evaluation in evaluations
        }

        self.assertTrue(evaluations_by_rule_id["RULE-GEN-1-LOW-FUEL"]["is_triggered"])
        self.assertEqual(
            evaluations_by_rule_id["RULE-GEN-1-LOW-FUEL"]["current_value"],
            "30",
        )
        self.assertEqual(
            evaluations_by_rule_id["RULE-GEN-1-LOW-FUEL"]["source"],
            "SCENARIO",
        )

    def test_applying_scenario_does_not_create_generated_alarms(self):
        temp_db_path = self.load_temp_sample_database()

        backend_summary.apply_scenario("trigger-ups-high-load", db_path=temp_db_path)
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        self.assertEqual(generated_alarms, [])

    def test_multi_point_scenario_rolls_back_when_one_update_fails(self):
        temp_db_path = self.load_temp_sample_database()
        original_ingest = backend_summary.ingest_point_sample_with_connection
        call_count = {"count": 0}
        test_scenario = {
            "label": "Test Multi Point Failure",
            "description": "Exercise transactional scenario rollback.",
            "updates": [
                {
                    "point_id": "UPS-A_OUTPUT_KW",
                    "value": "245",
                    "quality": "GOOD",
                    "source": "SCENARIO",
                },
                {
                    "point_id": "CRAC-2_SUPPLY_AIR_TEMP",
                    "value": "72",
                    "quality": "GOOD",
                    "source": "SCENARIO",
                },
            ],
        }

        def fail_second_ingest(connection, *args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 2:
                raise RuntimeError("scenario update failed")

            return original_ingest(connection, *args, **kwargs)

        with sqlite3.connect(temp_db_path) as connection:
            before_sample_count = connection.execute(
                "SELECT COUNT(*) FROM point_samples"
            ).fetchone()[0]
            before_ups_value = connection.execute(
                """
                SELECT value, source
                FROM current_point_values
                WHERE point_id = 'UPS-A_OUTPUT_KW'
                """
            ).fetchone()

        with (
            mock.patch.dict(
                backend_summary.ALARM_SCENARIOS,
                {"test-multi-point-failure": test_scenario},
            ),
            mock.patch.object(
                backend_summary,
                "ingest_point_sample_with_connection",
                side_effect=fail_second_ingest,
            ),
            self.assertRaises(RuntimeError),
        ):
            backend_summary.apply_scenario(
                "test-multi-point-failure",
                db_path=temp_db_path,
            )

        with sqlite3.connect(temp_db_path) as connection:
            after_sample_count = connection.execute(
                "SELECT COUNT(*) FROM point_samples"
            ).fetchone()[0]
            after_ups_value = connection.execute(
                """
                SELECT value, source
                FROM current_point_values
                WHERE point_id = 'UPS-A_OUTPUT_KW'
                """
            ).fetchone()

        self.assertEqual(after_sample_count, before_sample_count)
        self.assertEqual(after_ups_value, before_ups_value)

    def test_applying_scenario_does_not_update_generated_summary_until_evaluation(self):
        temp_db_path = self.load_temp_sample_database()

        backend_summary.apply_scenario("trigger-ups-high-load", db_path=temp_db_path)
        summary_before_evaluation = backend_summary.get_alarm_summary(temp_db_path)
        backend_summary.evaluate_generated_alarms(temp_db_path)
        summary_after_evaluation = backend_summary.get_alarm_summary(temp_db_path)

        self.assertEqual(summary_before_evaluation["total_generated_alarm_count"], 0)
        self.assertEqual(summary_before_evaluation["active_generated_alarm_count"], 0)
        self.assertEqual(summary_before_evaluation["pending_generated_alarm_count"], 0)
        self.assertEqual(summary_after_evaluation["total_generated_alarm_count"], 1)
        self.assertEqual(summary_after_evaluation["active_generated_alarm_count"], 0)
        self.assertEqual(summary_after_evaluation["pending_generated_alarm_count"], 1)
        self.assertEqual(summary_after_evaluation["active_warning_generated_alarm_count"], 0)
        self.assertEqual(summary_after_evaluation["active_generated_alarm_severity_counts"], {})
        self.assertEqual(summary_after_evaluation["generated_alarm_state_counts"], {"PENDING": 1})
        self.assertEqual(summary_after_evaluation["active_generated_alarm_equipment_counts"], {})

    def test_invalid_scenario_endpoint_returns_error(self):
        temp_db_path = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "apply_scenario",
                lambda scenario_id: backend_summary.apply_scenario(
                    scenario_id,
                    db_path=temp_db_path,
                ),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/scenarios/not-a-scenario/apply",
                method="POST",
            )

        self.assertEqual(status, 404)
        self.assertIn("Scenario not found", data["error"])


class DomainAlarmEvaluatorTests(unittest.TestCase):
    def active_analog_evaluation(self, operator, current_value, clear_value):
        return {
            "enabled": True,
            "is_triggered": False,
            "evaluation_status": "Normal",
            "rule_type": "analog_limit",
            "operator": operator,
            "clear_value": clear_value,
            "quality": "GOOD",
            "current_value": current_value,
        }

    def test_good_sample_is_eligible(self):
        status = alarm_evaluator.sample_eligibility_status(
            "GOOD",
            received_timestamp="2026-05-01 12:00:00",
            stale_after_seconds=300,
            evaluation_timestamp="2026-05-01 12:01:00",
        )

        self.assertEqual(status, "ELIGIBLE")

    def test_bad_sample_is_ineligible(self):
        status = alarm_evaluator.sample_eligibility_status("BAD")

        self.assertEqual(status, "BAD_QUALITY")

    def test_uncertain_sample_is_ineligible(self):
        status = alarm_evaluator.sample_eligibility_status("UNCERTAIN")

        self.assertEqual(status, "UNCERTAIN_QUALITY")

    def test_stale_quality_sample_is_ineligible(self):
        status = alarm_evaluator.sample_eligibility_status("STALE")

        self.assertEqual(status, "STALE")

    def test_stale_timeout_sample_is_ineligible(self):
        status = alarm_evaluator.sample_eligibility_status(
            "GOOD",
            received_timestamp="2026-05-01 12:00:00",
            stale_after_seconds=30,
            evaluation_timestamp="2026-05-01 12:01:00",
        )

        self.assertEqual(status, "STALE")

    def test_overridden_sample_is_ineligible(self):
        status = alarm_evaluator.sample_eligibility_status(
            "GOOD",
            overridden=True,
        )

        self.assertEqual(status, "OVERRIDDEN")

    def test_out_of_service_sample_is_ineligible(self):
        status = alarm_evaluator.sample_eligibility_status(
            "GOOD",
            out_of_service=True,
        )

        self.assertEqual(status, "OUT_OF_SERVICE")

    def test_analog_greater_than_trigger(self):
        result = alarm_evaluator.evaluate_alarm_rule(
            "analog_limit",
            ">",
            "240",
            "245",
            "GOOD",
            enabled=True,
        )

        self.assertTrue(result["is_triggered"])
        self.assertEqual(result["evaluation_status"], "Triggered")

    def test_analog_less_than_trigger(self):
        result = alarm_evaluator.evaluate_alarm_rule(
            "analog_limit",
            "<",
            "40",
            "30",
            "GOOD",
            enabled=True,
        )

        self.assertTrue(result["is_triggered"])
        self.assertEqual(result["evaluation_status"], "Triggered")

    def test_boolean_equals_trigger(self):
        result = alarm_evaluator.evaluate_alarm_rule(
            "boolean_state",
            "==",
            "false",
            "false",
            "GOOD",
            enabled=True,
        )

        self.assertTrue(result["is_triggered"])
        self.assertEqual(result["evaluation_status"], "Triggered")

    def test_enum_equals_trigger(self):
        result = alarm_evaluator.evaluate_alarm_rule(
            "enum_match",
            "==",
            "On Battery",
            "on battery",
            "GOOD",
            enabled=True,
        )

        self.assertTrue(result["is_triggered"])
        self.assertEqual(result["evaluation_status"], "Triggered")

    def test_greater_than_analog_clear_hysteresis(self):
        keep_active = alarm_evaluator.active_generated_alarm_should_clear(
            self.active_analog_evaluation(">", "235", "220"),
        )
        clear_active = alarm_evaluator.active_generated_alarm_should_clear(
            self.active_analog_evaluation(">", "219", "220"),
        )

        self.assertFalse(keep_active)
        self.assertTrue(clear_active)

    def test_less_than_analog_clear_hysteresis(self):
        keep_active = alarm_evaluator.active_generated_alarm_should_clear(
            self.active_analog_evaluation("<", "45", "50"),
        )
        clear_active = alarm_evaluator.active_generated_alarm_should_clear(
            self.active_analog_evaluation("<", "51", "50"),
        )

        self.assertFalse(keep_active)
        self.assertTrue(clear_active)


class RuleEvaluationTests(unittest.TestCase):
    def load_temp_sample_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        temp_db_path = Path(temp_dir.name) / "facilityops_test.sqlite3"
        load_alarm_db.load_sample_data_to_sqlite(db_path=temp_db_path)
        return temp_db_path

    def test_enabled_analog_rules_evaluate_correctly(self):
        triggered_result = backend_summary.evaluate_alarm_rule(
            "analog_limit",
            ">",
            "240",
            "245",
            "GOOD",
            enabled=True,
        )
        normal_result = backend_summary.evaluate_alarm_rule(
            "analog_limit",
            ">",
            "240",
            "185",
            "GOOD",
            enabled=True,
        )

        self.assertTrue(triggered_result["is_triggered"])
        self.assertEqual(triggered_result["evaluation_status"], "Triggered")
        self.assertFalse(normal_result["is_triggered"])
        self.assertEqual(normal_result["evaluation_status"], "Normal")

    def test_enabled_boolean_rules_evaluate_correctly(self):
        triggered_result = backend_summary.evaluate_alarm_rule(
            "boolean_state",
            "==",
            "false",
            "false",
            "GOOD",
            enabled=True,
        )
        normal_result = backend_summary.evaluate_alarm_rule(
            "boolean_state",
            "==",
            "false",
            "true",
            "GOOD",
            enabled=True,
        )

        self.assertTrue(triggered_result["is_triggered"])
        self.assertEqual(triggered_result["evaluation_status"], "Triggered")
        self.assertFalse(normal_result["is_triggered"])
        self.assertEqual(normal_result["evaluation_status"], "Normal")

    def test_enabled_enum_rules_evaluate_correctly(self):
        triggered_result = backend_summary.evaluate_alarm_rule(
            "enum_match",
            "==",
            "On Battery",
            "on battery",
            "GOOD",
            enabled=True,
        )
        normal_result = backend_summary.evaluate_alarm_rule(
            "enum_match",
            "==",
            "On Battery",
            "Normal",
            "GOOD",
            enabled=True,
        )

        self.assertTrue(triggered_result["is_triggered"])
        self.assertEqual(triggered_result["evaluation_status"], "Triggered")
        self.assertFalse(normal_result["is_triggered"])
        self.assertEqual(normal_result["evaluation_status"], "Normal")

    def test_disabled_rules_do_not_trigger(self):
        result = backend_summary.evaluate_alarm_rule(
            "analog_limit",
            ">",
            "240",
            "245",
            "GOOD",
            enabled=False,
        )

        self.assertFalse(result["is_triggered"])
        self.assertEqual(result["evaluation_status"], "Disabled")

    def test_missing_or_invalid_values_do_not_crash_evaluation(self):
        missing_value_result = backend_summary.evaluate_alarm_rule(
            "analog_limit",
            ">",
            "240",
            None,
            "GOOD",
            enabled=True,
        )
        bad_quality_result = backend_summary.evaluate_alarm_rule(
            "analog_limit",
            ">",
            "240",
            "245",
            "BAD",
            enabled=True,
        )
        invalid_analog_result = backend_summary.evaluate_alarm_rule(
            "analog_limit",
            ">",
            "240",
            "not-a-number",
            "GOOD",
            enabled=True,
        )
        unsupported_operator_result = backend_summary.evaluate_alarm_rule(
            "analog_limit",
            "=",
            "240",
            "245",
            "GOOD",
            enabled=True,
        )

        self.assertFalse(missing_value_result["is_triggered"])
        self.assertEqual(missing_value_result["evaluation_status"], "No current value")
        self.assertFalse(bad_quality_result["is_triggered"])
        self.assertEqual(bad_quality_result["evaluation_status"], "BAD_QUALITY")
        self.assertFalse(invalid_analog_result["is_triggered"])
        self.assertEqual(invalid_analog_result["evaluation_status"], "Invalid analog value")
        self.assertFalse(unsupported_operator_result["is_triggered"])
        self.assertEqual(
            unsupported_operator_result["evaluation_status"],
            "Unsupported operator",
        )

    def test_rule_evaluations_handle_missing_and_invalid_current_values(self):
        temp_db_path = self.load_temp_sample_database()

        with sqlite3.connect(temp_db_path) as connection:
            connection.execute(
                """
                DELETE FROM current_point_values
                WHERE point_id = 'UPS-A_OUTPUT_KW'
                """
            )
            connection.execute(
                """
                UPDATE current_point_values
                SET value = 'not-a-number'
                WHERE point_id = 'GEN-1_FUEL_LEVEL'
                """
            )

        evaluations = backend_summary.get_rule_evaluations(temp_db_path)
        evaluations_by_rule_id = {
            evaluation["id"]: evaluation
            for evaluation in evaluations
        }

        self.assertEqual(
            evaluations_by_rule_id["RULE-UPS-A-HIGH-LOAD"]["evaluation_status"],
            "No current value",
        )
        self.assertEqual(
            evaluations_by_rule_id["RULE-GEN-1-LOW-FUEL"]["evaluation_status"],
            "Invalid analog value",
        )

    def test_rule_evaluations_endpoint_returns_all_rules_with_context(self):
        temp_db_path = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "get_rule_evaluations",
                lambda: backend_summary.get_rule_evaluations(temp_db_path),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/rule-evaluations",
            )

        self.assertEqual(status, 200)
        self.assertIn("rule_evaluations", data)
        self.assertEqual(len(data["rule_evaluations"]), 7)

        evaluations_by_rule_id = {
            evaluation["id"]: evaluation
            for evaluation in data["rule_evaluations"]
        }
        ups_high_load = evaluations_by_rule_id["RULE-UPS-A-HIGH-LOAD"]

        self.assertEqual(ups_high_load["equipment_id"], "UPS-A")
        self.assertEqual(ups_high_load["point_id"], "UPS-A_OUTPUT_KW")
        self.assertEqual(ups_high_load["point_name"], "OUTPUT_KW")
        self.assertEqual(ups_high_load["display_name"], "UPS-A Output kW")
        self.assertEqual(ups_high_load["data_type"], "analog")
        self.assertEqual(ups_high_load["unit"], "kW")
        self.assertEqual(ups_high_load["current_value"], "185")
        self.assertEqual(ups_high_load["quality"], "GOOD")
        self.assertFalse(ups_high_load["is_triggered"])
        self.assertEqual(ups_high_load["evaluation_status"], "Normal")


class GeneratedAlarmStateTests(unittest.TestCase):
    def load_temp_sample_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        temp_db_path = Path(temp_dir.name) / "facilityops_test.sqlite3"
        load_alarm_db.load_sample_data_to_sqlite(db_path=temp_db_path)
        with sqlite3.connect(temp_db_path) as connection:
            connection.execute("UPDATE alarm_rules SET delay_seconds = 0")
        return temp_db_path

    def trigger_ups_high_load_rule(self, db_path):
        self.set_current_point_value(db_path, "UPS-A_OUTPUT_KW", "245")

    def clear_ups_high_load_rule(self, db_path):
        self.set_current_point_value(db_path, "UPS-A_OUTPUT_KW", "185")

    def set_current_point_value(self, db_path, point_id, value, quality="GOOD"):
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """
                UPDATE current_point_values
                SET value = ?,
                    quality = ?
                WHERE point_id = ?
                """,
                (value, quality, point_id),
            )

    def set_alarm_rule_values(
        self,
        db_path,
        rule_id,
        operator=None,
        threshold_value=None,
        clear_value=None,
        delay_seconds=None,
    ):
        assignments = []
        parameters = []
        if operator is not None:
            assignments.append("operator = ?")
            parameters.append(operator)
        if threshold_value is not None:
            assignments.append("threshold_value = ?")
            parameters.append(threshold_value)
        if clear_value is not None:
            assignments.append("clear_value = ?")
            parameters.append(clear_value)
        if delay_seconds is not None:
            assignments.append("delay_seconds = ?")
            parameters.append(delay_seconds)

        if not assignments:
            return

        parameters.append(rule_id)
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                f"""
                UPDATE alarm_rules
                SET {", ".join(assignments)}
                WHERE id = ?
                """,
                parameters,
            )

    def test_loader_creates_empty_generated_alarms_table(self):
        temp_db_path = self.load_temp_sample_database()

        with sqlite3.connect(temp_db_path) as connection:
            table_exists = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'generated_alarms'
                """
            ).fetchone()
            alarm_event_table_exists = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'alarm_events'
                """
            ).fetchone()
            generated_alarm_count = connection.execute(
                "SELECT COUNT(*) FROM generated_alarms"
            ).fetchone()[0]
            alarm_event_count = connection.execute(
                "SELECT COUNT(*) FROM alarm_events"
            ).fetchone()[0]
            generated_alarm_columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(generated_alarms)")
            }
            alarm_event_columns = {
                row[1]: row
                for row in connection.execute("PRAGMA table_info(alarm_events)")
            }

        self.assertIsNotNone(table_exists)
        self.assertIsNotNone(alarm_event_table_exists)
        self.assertEqual(generated_alarm_count, 0)
        self.assertEqual(alarm_event_count, 0)
        self.assertIn("pending_started_at", generated_alarm_columns)
        self.assertIn("acknowledged", generated_alarm_columns)
        self.assertIn("acknowledged_at", generated_alarm_columns)
        self.assertIn("acknowledged_by", generated_alarm_columns)
        self.assertIn("threshold_value_at_trigger", generated_alarm_columns)
        self.assertIn("clear_value_at_trigger", generated_alarm_columns)
        self.assertIn("delay_seconds_at_trigger", generated_alarm_columns)
        self.assertIn("triggering_sample_id", generated_alarm_columns)
        self.assertIn("triggering_value", generated_alarm_columns)
        self.assertIn("triggering_quality", generated_alarm_columns)
        self.assertEqual(alarm_event_columns["generated_alarm_id"][3], 0)
        self.assertEqual(alarm_event_columns["rule_id"][3], 0)

    def test_evaluate_creates_active_alarm_for_triggered_rule(self):
        temp_db_path = self.load_temp_sample_database()
        self.trigger_ups_high_load_rule(temp_db_path)

        summary = backend_summary.evaluate_generated_alarms(temp_db_path)
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        self.assertEqual(summary["created_count"], 1)
        self.assertEqual(summary["active_count"], 1)
        self.assertEqual(len(generated_alarms), 1)
        self.assertEqual(generated_alarms[0]["rule_id"], "RULE-UPS-A-HIGH-LOAD")
        self.assertEqual(generated_alarms[0]["state"], "ACTIVE")
        self.assertEqual(generated_alarms[0]["triggered_value"], "245")
        self.assertFalse(generated_alarms[0]["acknowledged"])
        self.assertEqual(generated_alarms[0]["acknowledged_at"], "")
        self.assertEqual(generated_alarms[0]["acknowledged_by"], "")

    def test_generated_alarm_snapshots_rule_and_sample_facts_at_trigger(self):
        temp_db_path = self.load_temp_sample_database()

        current_point_value = backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "245",
            quality="GOOD",
            source="MANUAL",
            db_path=temp_db_path,
        )
        backend_summary.evaluate_generated_alarms(temp_db_path)
        generated_alarm = backend_summary.get_generated_alarms(temp_db_path)[0]

        self.assertEqual(generated_alarm["rule_name_at_trigger"], "UPS high load")
        self.assertEqual(generated_alarm["rule_type_at_trigger"], "analog_limit")
        self.assertEqual(generated_alarm["operator_at_trigger"], ">")
        self.assertEqual(generated_alarm["threshold_value_at_trigger"], "240")
        self.assertEqual(generated_alarm["clear_value_at_trigger"], "220")
        self.assertEqual(generated_alarm["delay_seconds_at_trigger"], 0)
        self.assertEqual(generated_alarm["severity_at_trigger"], "Warning")
        self.assertEqual(
            generated_alarm["alarm_message_at_trigger"],
            "UPS-A load is above the preferred operating range",
        )
        self.assertEqual(
            generated_alarm["triggering_sample_id"],
            current_point_value["latest_sample_id"],
        )
        self.assertEqual(generated_alarm["triggering_value"], "245")
        self.assertEqual(generated_alarm["triggering_quality"], "GOOD")
        self.assertEqual(
            generated_alarm["triggering_source_timestamp"],
            current_point_value["source_timestamp"],
        )
        self.assertEqual(
            generated_alarm["triggering_received_timestamp"],
            current_point_value["received_timestamp"],
        )

    def test_rule_edit_does_not_rewrite_existing_alarm_snapshot(self):
        temp_db_path = self.load_temp_sample_database()

        backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "245",
            quality="GOOD",
            source="MANUAL",
            db_path=temp_db_path,
        )
        backend_summary.evaluate_generated_alarms(temp_db_path)
        alarm_id = backend_summary.get_generated_alarms(temp_db_path)[0]["id"]

        backend_summary.update_alarm_rule(
            "RULE-UPS-A-HIGH-LOAD",
            {
                "threshold_value": "260",
                "clear_value": "230",
                "delay_seconds": 45,
                "severity": "Critical",
                "alarm_message": "UPS-A load is above edited threshold",
            },
            db_path=temp_db_path,
        )
        backend_summary.evaluate_generated_alarms(temp_db_path)
        generated_alarm = [
            alarm
            for alarm in backend_summary.get_generated_alarms(temp_db_path)
            if alarm["id"] == alarm_id
        ][0]

        self.assertEqual(generated_alarm["threshold_value_at_trigger"], "240")
        self.assertEqual(generated_alarm["clear_value_at_trigger"], "220")
        self.assertEqual(generated_alarm["delay_seconds_at_trigger"], 0)
        self.assertEqual(generated_alarm["severity_at_trigger"], "Warning")
        self.assertEqual(
            generated_alarm["alarm_message_at_trigger"],
            "UPS-A load is above the preferred operating range",
        )

    def test_new_generated_alarm_uses_updated_rule_snapshot(self):
        temp_db_path = self.load_temp_sample_database()

        backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "245",
            quality="GOOD",
            source="MANUAL",
            db_path=temp_db_path,
        )
        backend_summary.evaluate_generated_alarms(temp_db_path)
        backend_summary.update_alarm_rule(
            "RULE-UPS-A-HIGH-LOAD",
            {
                "threshold_value": "260",
                "clear_value": "230",
                "delay_seconds": 0,
                "severity": "Critical",
                "alarm_message": "UPS-A load is above edited threshold",
            },
            db_path=temp_db_path,
        )
        backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "220",
            quality="GOOD",
            source="MANUAL",
            db_path=temp_db_path,
        )
        backend_summary.evaluate_generated_alarms(temp_db_path)
        backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "265",
            quality="GOOD",
            source="MANUAL",
            db_path=temp_db_path,
        )
        backend_summary.evaluate_generated_alarms(temp_db_path)
        active_alarm = [
            alarm
            for alarm in backend_summary.get_generated_alarms(temp_db_path)
            if alarm["state"] == "ACTIVE"
        ][0]

        self.assertEqual(active_alarm["threshold_value_at_trigger"], "260")
        self.assertEqual(active_alarm["clear_value_at_trigger"], "230")
        self.assertEqual(active_alarm["delay_seconds_at_trigger"], 0)
        self.assertEqual(active_alarm["severity_at_trigger"], "Critical")
        self.assertEqual(
            active_alarm["alarm_message_at_trigger"],
            "UPS-A load is above edited threshold",
        )
        self.assertEqual(active_alarm["triggering_value"], "265")

    def test_rule_with_delay_creates_pending_alarm_when_first_triggered(self):
        temp_db_path = self.load_temp_sample_database()
        self.set_alarm_rule_values(
            temp_db_path,
            "RULE-UPS-A-HIGH-LOAD",
            delay_seconds=300,
        )
        self.trigger_ups_high_load_rule(temp_db_path)

        with mock.patch.object(
            backend_summary,
            "current_timestamp",
            return_value="2026-05-01 12:00:00",
        ):
            summary = backend_summary.evaluate_generated_alarms(temp_db_path)

        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)
        alarm_summary = backend_summary.get_alarm_summary(temp_db_path)

        self.assertEqual(summary["created_count"], 1)
        self.assertEqual(summary["active_count"], 0)
        self.assertEqual(summary["pending_count"], 1)
        self.assertEqual(generated_alarms[0]["state"], "PENDING")
        self.assertEqual(generated_alarms[0]["pending_started_at"], "2026-05-01 12:00:00")
        self.assertEqual(generated_alarms[0]["triggered_at"], "")
        self.assertEqual(generated_alarms[0]["evaluation_note"], "Pending delay")
        self.assertEqual(alarm_summary["active_generated_alarm_count"], 0)
        self.assertEqual(alarm_summary["pending_generated_alarm_count"], 1)
        self.assertEqual(alarm_summary["active_warning_generated_alarm_count"], 0)
        self.assertEqual(alarm_summary["generated_alarm_state_counts"], {"PENDING": 1})
        self.assertEqual(alarm_summary["active_generated_alarm_severity_counts"], {})

    def test_pending_alarm_remains_pending_before_delay_elapses(self):
        temp_db_path = self.load_temp_sample_database()
        self.set_alarm_rule_values(
            temp_db_path,
            "RULE-UPS-A-HIGH-LOAD",
            delay_seconds=300,
        )
        self.trigger_ups_high_load_rule(temp_db_path)

        with mock.patch.object(
            backend_summary,
            "current_timestamp",
            side_effect=[
                "2026-05-01 12:00:00",
                "2026-05-01 12:04:59",
            ],
        ):
            backend_summary.evaluate_generated_alarms(temp_db_path)
            summary = backend_summary.evaluate_generated_alarms(temp_db_path)

        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        self.assertEqual(summary["active_count"], 0)
        self.assertEqual(summary["pending_count"], 1)
        self.assertEqual(summary["updated_count"], 1)
        self.assertEqual(generated_alarms[0]["state"], "PENDING")
        self.assertEqual(generated_alarms[0]["pending_started_at"], "2026-05-01 12:00:00")
        self.assertEqual(generated_alarms[0]["triggered_at"], "")
        self.assertEqual(generated_alarms[0]["last_evaluated_at"], "2026-05-01 12:04:59")

    def test_pending_alarm_becomes_active_after_delay_elapses(self):
        temp_db_path = self.load_temp_sample_database()
        self.set_alarm_rule_values(
            temp_db_path,
            "RULE-UPS-A-HIGH-LOAD",
            delay_seconds=300,
        )
        self.trigger_ups_high_load_rule(temp_db_path)

        with mock.patch.object(
            backend_summary,
            "current_timestamp",
            side_effect=[
                "2026-05-01 12:00:00",
                "2026-05-01 12:05:00",
            ],
        ):
            backend_summary.evaluate_generated_alarms(temp_db_path)
            summary = backend_summary.evaluate_generated_alarms(temp_db_path)

        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        self.assertEqual(summary["active_count"], 1)
        self.assertEqual(summary["pending_count"], 0)
        self.assertEqual(summary["updated_count"], 1)
        self.assertEqual(generated_alarms[0]["state"], "ACTIVE")
        self.assertEqual(generated_alarms[0]["pending_started_at"], "2026-05-01 12:00:00")
        self.assertEqual(generated_alarms[0]["triggered_at"], "2026-05-01 12:05:00")
        self.assertEqual(generated_alarms[0]["evaluation_note"], "Triggered")

    def test_pending_to_active_preserves_original_trigger_sample_facts(self):
        temp_db_path = self.load_temp_sample_database()
        self.set_alarm_rule_values(
            temp_db_path,
            "RULE-UPS-A-HIGH-LOAD",
            delay_seconds=300,
        )
        first_current_value = backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "245",
            quality="GOOD",
            source="MANUAL",
            db_path=temp_db_path,
        )

        with mock.patch.object(
            backend_summary,
            "current_timestamp",
            return_value="2026-05-01 12:00:00",
        ):
            backend_summary.evaluate_generated_alarms(temp_db_path)

        second_current_value = backend_summary.update_current_point_value(
            "UPS-A_OUTPUT_KW",
            "260",
            quality="GOOD",
            source="MANUAL",
            db_path=temp_db_path,
        )
        with mock.patch.object(
            backend_summary,
            "current_timestamp",
            return_value="2026-05-01 12:05:00",
        ):
            backend_summary.evaluate_generated_alarms(temp_db_path)

        generated_alarm = backend_summary.get_generated_alarms(temp_db_path)[0]

        self.assertEqual(generated_alarm["state"], "ACTIVE")
        self.assertEqual(generated_alarm["triggered_value"], "260")
        self.assertEqual(
            generated_alarm["triggering_sample_id"],
            first_current_value["latest_sample_id"],
        )
        self.assertNotEqual(
            generated_alarm["triggering_sample_id"],
            second_current_value["latest_sample_id"],
        )
        self.assertEqual(generated_alarm["triggering_value"], "245")
        self.assertEqual(
            generated_alarm["triggering_source_timestamp"],
            first_current_value["source_timestamp"],
        )
        self.assertEqual(
            generated_alarm["triggering_received_timestamp"],
            first_current_value["received_timestamp"],
        )
        self.assertEqual(generated_alarm["threshold_value_at_trigger"], "240")
        self.assertEqual(generated_alarm["clear_value_at_trigger"], "220")
        self.assertEqual(generated_alarm["delay_seconds_at_trigger"], 300)

    def test_pending_alarm_clears_if_rule_returns_normal_before_delay_elapses(self):
        temp_db_path = self.load_temp_sample_database()
        self.set_alarm_rule_values(
            temp_db_path,
            "RULE-UPS-A-HIGH-LOAD",
            delay_seconds=300,
        )
        self.trigger_ups_high_load_rule(temp_db_path)

        with mock.patch.object(
            backend_summary,
            "current_timestamp",
            return_value="2026-05-01 12:00:00",
        ):
            backend_summary.evaluate_generated_alarms(temp_db_path)

        self.clear_ups_high_load_rule(temp_db_path)
        with mock.patch.object(
            backend_summary,
            "current_timestamp",
            return_value="2026-05-01 12:01:00",
        ):
            summary = backend_summary.evaluate_generated_alarms(temp_db_path)

        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        self.assertEqual(summary["active_count"], 0)
        self.assertEqual(summary["pending_count"], 0)
        self.assertEqual(summary["cleared_count"], 1)
        self.assertEqual(generated_alarms[0]["state"], "CLEARED")
        self.assertEqual(generated_alarms[0]["pending_started_at"], "2026-05-01 12:00:00")
        self.assertEqual(generated_alarms[0]["triggered_at"], "")
        self.assertEqual(generated_alarms[0]["cleared_at"], "2026-05-01 12:01:00")
        self.assertEqual(generated_alarms[0]["evaluation_note"], "Normal")

    def test_blank_delay_seconds_creates_active_alarm_immediately(self):
        temp_db_path = self.load_temp_sample_database()
        self.set_alarm_rule_values(
            temp_db_path,
            "RULE-UPS-A-HIGH-LOAD",
            delay_seconds="",
        )
        self.trigger_ups_high_load_rule(temp_db_path)

        summary = backend_summary.evaluate_generated_alarms(temp_db_path)
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        self.assertEqual(summary["created_count"], 1)
        self.assertEqual(summary["active_count"], 1)
        self.assertEqual(summary["pending_count"], 0)
        self.assertEqual(generated_alarms[0]["state"], "ACTIVE")

    def test_rule_evaluations_remain_stateless_when_generated_alarm_is_pending(self):
        temp_db_path = self.load_temp_sample_database()
        self.set_alarm_rule_values(
            temp_db_path,
            "RULE-UPS-A-HIGH-LOAD",
            delay_seconds=300,
        )
        self.trigger_ups_high_load_rule(temp_db_path)
        backend_summary.evaluate_generated_alarms(temp_db_path)

        evaluations = backend_summary.get_rule_evaluations(temp_db_path)
        ups_high_load = [
            evaluation
            for evaluation in evaluations
            if evaluation["id"] == "RULE-UPS-A-HIGH-LOAD"
        ][0]

        self.assertTrue(ups_high_load["is_triggered"])
        self.assertEqual(ups_high_load["evaluation_status"], "Triggered")
        self.assertNotIn("state", ups_high_load)

    def test_rerunning_evaluation_does_not_duplicate_active_alarms(self):
        temp_db_path = self.load_temp_sample_database()
        self.trigger_ups_high_load_rule(temp_db_path)

        first_summary = backend_summary.evaluate_generated_alarms(temp_db_path)
        second_summary = backend_summary.evaluate_generated_alarms(temp_db_path)

        with sqlite3.connect(temp_db_path) as connection:
            active_alarm_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM generated_alarms
                WHERE rule_id = 'RULE-UPS-A-HIGH-LOAD'
                  AND state = 'ACTIVE'
                """
            ).fetchone()[0]

        self.assertEqual(first_summary["created_count"], 1)
        self.assertEqual(second_summary["created_count"], 0)
        self.assertEqual(second_summary["updated_count"], 1)
        self.assertEqual(active_alarm_count, 1)

    def test_evaluate_clears_active_alarm_when_rule_is_no_longer_triggered(self):
        temp_db_path = self.load_temp_sample_database()
        self.trigger_ups_high_load_rule(temp_db_path)
        backend_summary.evaluate_generated_alarms(temp_db_path)

        self.clear_ups_high_load_rule(temp_db_path)
        summary = backend_summary.evaluate_generated_alarms(temp_db_path)
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        self.assertEqual(summary["active_count"], 0)
        self.assertEqual(summary["cleared_count"], 1)
        self.assertEqual(len(generated_alarms), 1)
        self.assertEqual(generated_alarms[0]["state"], "CLEARED")
        self.assertNotEqual(generated_alarms[0]["cleared_at"], "")
        self.assertEqual(generated_alarms[0]["evaluation_note"], "Normal")

    def test_greater_than_analog_alarm_remains_active_between_threshold_and_clear_value(self):
        temp_db_path = self.load_temp_sample_database()
        self.trigger_ups_high_load_rule(temp_db_path)
        backend_summary.evaluate_generated_alarms(temp_db_path)

        self.set_current_point_value(temp_db_path, "UPS-A_OUTPUT_KW", "235")
        summary = backend_summary.evaluate_generated_alarms(temp_db_path)
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)
        rule_evaluations = backend_summary.get_rule_evaluations(temp_db_path)
        ups_high_load_evaluation = [
            evaluation
            for evaluation in rule_evaluations
            if evaluation["id"] == "RULE-UPS-A-HIGH-LOAD"
        ][0]

        self.assertFalse(ups_high_load_evaluation["is_triggered"])
        self.assertEqual(ups_high_load_evaluation["evaluation_status"], "Normal")
        self.assertEqual(summary["active_count"], 1)
        self.assertEqual(summary["cleared_count"], 0)
        self.assertEqual(summary["updated_count"], 1)
        self.assertEqual(generated_alarms[0]["state"], "ACTIVE")
        self.assertEqual(generated_alarms[0]["triggered_value"], "235")
        self.assertEqual(generated_alarms[0]["evaluation_note"], "Waiting for clear value")

    def test_greater_than_analog_alarm_clears_only_below_clear_value(self):
        temp_db_path = self.load_temp_sample_database()
        self.trigger_ups_high_load_rule(temp_db_path)
        backend_summary.evaluate_generated_alarms(temp_db_path)

        self.set_current_point_value(temp_db_path, "UPS-A_OUTPUT_KW", "235")
        backend_summary.evaluate_generated_alarms(temp_db_path)
        self.set_current_point_value(temp_db_path, "UPS-A_OUTPUT_KW", "219")
        summary = backend_summary.evaluate_generated_alarms(temp_db_path)
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        self.assertEqual(summary["active_count"], 0)
        self.assertEqual(summary["cleared_count"], 1)
        self.assertEqual(generated_alarms[0]["state"], "CLEARED")
        self.assertEqual(generated_alarms[0]["evaluation_note"], "Normal")

    def test_greater_equal_analog_alarm_uses_clear_value_hysteresis(self):
        temp_db_path = self.load_temp_sample_database()
        self.set_alarm_rule_values(
            temp_db_path,
            "RULE-UPS-A-HIGH-LOAD",
            operator=">=",
        )
        self.set_current_point_value(temp_db_path, "UPS-A_OUTPUT_KW", "240")
        backend_summary.evaluate_generated_alarms(temp_db_path)

        self.set_current_point_value(temp_db_path, "UPS-A_OUTPUT_KW", "230")
        keep_summary = backend_summary.evaluate_generated_alarms(temp_db_path)
        self.set_current_point_value(temp_db_path, "UPS-A_OUTPUT_KW", "219")
        clear_summary = backend_summary.evaluate_generated_alarms(temp_db_path)
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        self.assertEqual(keep_summary["active_count"], 1)
        self.assertEqual(keep_summary["cleared_count"], 0)
        self.assertEqual(clear_summary["active_count"], 0)
        self.assertEqual(clear_summary["cleared_count"], 1)
        self.assertEqual(generated_alarms[0]["state"], "CLEARED")

    def test_less_than_analog_alarm_remains_active_between_threshold_and_clear_value(self):
        temp_db_path = self.load_temp_sample_database()
        self.set_current_point_value(temp_db_path, "GEN-1_FUEL_LEVEL", "30")
        backend_summary.evaluate_generated_alarms(temp_db_path)

        self.set_current_point_value(temp_db_path, "GEN-1_FUEL_LEVEL", "45")
        summary = backend_summary.evaluate_generated_alarms(temp_db_path)
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)
        low_fuel_alarm = [
            alarm
            for alarm in generated_alarms
            if alarm["rule_id"] == "RULE-GEN-1-LOW-FUEL"
        ][0]

        self.assertEqual(summary["active_count"], 1)
        self.assertEqual(summary["cleared_count"], 0)
        self.assertEqual(summary["updated_count"], 1)
        self.assertEqual(low_fuel_alarm["state"], "ACTIVE")
        self.assertEqual(low_fuel_alarm["triggered_value"], "45")
        self.assertEqual(low_fuel_alarm["evaluation_note"], "Waiting for clear value")

    def test_less_than_analog_alarm_clears_only_above_clear_value(self):
        temp_db_path = self.load_temp_sample_database()
        self.set_current_point_value(temp_db_path, "GEN-1_FUEL_LEVEL", "30")
        backend_summary.evaluate_generated_alarms(temp_db_path)

        self.set_current_point_value(temp_db_path, "GEN-1_FUEL_LEVEL", "45")
        backend_summary.evaluate_generated_alarms(temp_db_path)
        self.set_current_point_value(temp_db_path, "GEN-1_FUEL_LEVEL", "51")
        summary = backend_summary.evaluate_generated_alarms(temp_db_path)
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)
        low_fuel_alarm = [
            alarm
            for alarm in generated_alarms
            if alarm["rule_id"] == "RULE-GEN-1-LOW-FUEL"
        ][0]

        self.assertEqual(summary["active_count"], 0)
        self.assertEqual(summary["cleared_count"], 1)
        self.assertEqual(low_fuel_alarm["state"], "CLEARED")
        self.assertEqual(low_fuel_alarm["evaluation_note"], "Normal")

    def test_less_equal_analog_alarm_uses_clear_value_hysteresis(self):
        temp_db_path = self.load_temp_sample_database()
        self.set_alarm_rule_values(
            temp_db_path,
            "RULE-GEN-1-LOW-FUEL",
            operator="<=",
        )
        self.set_current_point_value(temp_db_path, "GEN-1_FUEL_LEVEL", "40")
        backend_summary.evaluate_generated_alarms(temp_db_path)

        self.set_current_point_value(temp_db_path, "GEN-1_FUEL_LEVEL", "45")
        keep_summary = backend_summary.evaluate_generated_alarms(temp_db_path)
        self.set_current_point_value(temp_db_path, "GEN-1_FUEL_LEVEL", "51")
        clear_summary = backend_summary.evaluate_generated_alarms(temp_db_path)
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)
        low_fuel_alarm = [
            alarm
            for alarm in generated_alarms
            if alarm["rule_id"] == "RULE-GEN-1-LOW-FUEL"
        ][0]

        self.assertEqual(keep_summary["active_count"], 1)
        self.assertEqual(keep_summary["cleared_count"], 0)
        self.assertEqual(clear_summary["active_count"], 0)
        self.assertEqual(clear_summary["cleared_count"], 1)
        self.assertEqual(low_fuel_alarm["state"], "CLEARED")

    def test_analog_alarm_clear_behavior_falls_back_when_clear_value_is_blank(self):
        temp_db_path = self.load_temp_sample_database()
        self.set_alarm_rule_values(
            temp_db_path,
            "RULE-UPS-A-HIGH-LOAD",
            clear_value="",
        )
        self.trigger_ups_high_load_rule(temp_db_path)
        backend_summary.evaluate_generated_alarms(temp_db_path)

        self.set_current_point_value(temp_db_path, "UPS-A_OUTPUT_KW", "235")
        summary = backend_summary.evaluate_generated_alarms(temp_db_path)
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        self.assertEqual(summary["active_count"], 0)
        self.assertEqual(summary["cleared_count"], 1)
        self.assertEqual(generated_alarms[0]["state"], "CLEARED")

    def test_boolean_generated_alarm_behavior_still_clears_without_hysteresis(self):
        temp_db_path = self.load_temp_sample_database()
        self.set_current_point_value(temp_db_path, "CHW-P-1_RUN_STATUS", "false")
        backend_summary.evaluate_generated_alarms(temp_db_path)

        self.set_current_point_value(temp_db_path, "CHW-P-1_RUN_STATUS", "true")
        summary = backend_summary.evaluate_generated_alarms(temp_db_path)
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)
        pump_alarm = [
            alarm
            for alarm in generated_alarms
            if alarm["rule_id"] == "RULE-CHW-P-1-FAILED-START"
        ][0]

        self.assertEqual(summary["active_count"], 0)
        self.assertEqual(summary["cleared_count"], 1)
        self.assertEqual(pump_alarm["state"], "CLEARED")
        self.assertEqual(pump_alarm["evaluation_note"], "Normal")

    def test_enum_generated_alarm_behavior_still_clears_without_hysteresis(self):
        temp_db_path = self.load_temp_sample_database()
        self.set_current_point_value(temp_db_path, "UPS-A_BATTERY_STATUS", "On Battery")
        backend_summary.evaluate_generated_alarms(temp_db_path)

        self.set_current_point_value(temp_db_path, "UPS-A_BATTERY_STATUS", "Normal")
        summary = backend_summary.evaluate_generated_alarms(temp_db_path)
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)
        battery_alarm = [
            alarm
            for alarm in generated_alarms
            if alarm["rule_id"] == "RULE-UPS-A-ON-BATTERY"
        ][0]

        self.assertEqual(summary["active_count"], 0)
        self.assertEqual(summary["cleared_count"], 1)
        self.assertEqual(battery_alarm["state"], "CLEARED")
        self.assertEqual(battery_alarm["evaluation_note"], "Normal")

    def test_generated_alarms_endpoint_returns_context(self):
        temp_db_path = self.load_temp_sample_database()
        self.trigger_ups_high_load_rule(temp_db_path)
        backend_summary.evaluate_generated_alarms(temp_db_path)

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "get_generated_alarms",
                lambda: backend_summary.get_generated_alarms(temp_db_path),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/generated-alarms",
            )

        self.assertEqual(status, 200)
        self.assertIn("generated_alarms", data)
        self.assertEqual(len(data["generated_alarms"]), 1)

        alarm = data["generated_alarms"][0]
        self.assertEqual(alarm["rule_id"], "RULE-UPS-A-HIGH-LOAD")
        self.assertEqual(alarm["rule_name"], "UPS high load")
        self.assertEqual(alarm["point_id"], "UPS-A_OUTPUT_KW")
        self.assertEqual(alarm["point_name"], "OUTPUT_KW")
        self.assertEqual(alarm["display_name"], "UPS-A Output kW")
        self.assertEqual(alarm["equipment_id"], "UPS-A")
        self.assertEqual(alarm["equipment_type"], "UPS")
        self.assertEqual(alarm["unit"], "kW")
        self.assertEqual(alarm["threshold_value_at_trigger"], "240")
        self.assertEqual(alarm["clear_value_at_trigger"], "220")
        self.assertNotEqual(alarm["triggering_sample_id"], "")
        self.assertEqual(alarm["triggering_value"], "245")
        self.assertFalse(alarm["acknowledged"])
        self.assertEqual(alarm["acknowledged_at"], "")
        self.assertEqual(alarm["acknowledged_by"], "")

    def test_generated_alarm_evaluate_endpoint_creates_active_alarm(self):
        temp_db_path = self.load_temp_sample_database()
        self.trigger_ups_high_load_rule(temp_db_path)

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "evaluate_generated_alarms",
                lambda: backend_summary.evaluate_generated_alarms(temp_db_path),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/generated-alarms/evaluate",
                method="POST",
            )

        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        self.assertEqual(status, 200)
        self.assertEqual(data["created_count"], 1)
        self.assertEqual(data["active_count"], 1)
        self.assertEqual(data["pending_count"], 0)
        self.assertEqual(len(generated_alarms), 1)
        self.assertEqual(generated_alarms[0]["state"], "ACTIVE")

    def test_acknowledge_generated_alarm_endpoint_sets_acknowledgement_fields(self):
        temp_db_path = self.load_temp_sample_database()
        self.trigger_ups_high_load_rule(temp_db_path)
        backend_summary.evaluate_generated_alarms(temp_db_path)
        alarm_id = backend_summary.get_generated_alarms(temp_db_path)[0]["id"]

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "acknowledge_generated_alarm",
                lambda alarm_id, acknowledged_by="local-operator": (
                    backend_summary.acknowledge_generated_alarm(
                        alarm_id,
                        acknowledged_by=acknowledged_by,
                        db_path=temp_db_path,
                    )
                ),
            ),
            mock.patch.object(
                backend_summary,
                "current_timestamp",
                return_value="2026-05-01 13:00:00",
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                f"/generated-alarms/{alarm_id}/acknowledge",
                method="POST",
                body={"acknowledged_by": "operator-a"},
            )

        self.assertEqual(status, 200)
        self.assertTrue(data["generated_alarm"]["acknowledged"])
        self.assertEqual(data["generated_alarm"]["acknowledged_at"], "2026-05-01 13:00:00")
        self.assertEqual(data["generated_alarm"]["acknowledged_by"], "operator-a")
        self.assertEqual(data["generated_alarm"]["state"], "ACTIVE")

    def test_pending_alarm_creation_inserts_event(self):
        temp_db_path = self.load_temp_sample_database()
        self.set_alarm_rule_values(
            temp_db_path,
            "RULE-UPS-A-HIGH-LOAD",
            delay_seconds=300,
        )
        self.trigger_ups_high_load_rule(temp_db_path)

        with mock.patch.object(
            backend_summary,
            "current_timestamp",
            return_value="2026-05-01 12:00:00",
        ):
            backend_summary.evaluate_generated_alarms(temp_db_path)

        events = backend_summary.get_alarm_events(temp_db_path)
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        self.assertEqual(generated_alarms[0]["state"], "PENDING")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "PENDING_CREATED")
        self.assertEqual(events[0]["rule_id"], "RULE-UPS-A-HIGH-LOAD")
        self.assertEqual(events[0]["previous_state"], "")
        self.assertEqual(events[0]["new_state"], "PENDING")
        self.assertEqual(events[0]["value"], "245")
        self.assertNotEqual(events[0]["sample_id"], "")

    def test_immediate_active_alarm_creation_inserts_event(self):
        temp_db_path = self.load_temp_sample_database()
        self.trigger_ups_high_load_rule(temp_db_path)

        with mock.patch.object(
            backend_summary,
            "current_timestamp",
            return_value="2026-05-01 12:00:00",
        ):
            backend_summary.evaluate_generated_alarms(temp_db_path)

        events = backend_summary.get_alarm_events(temp_db_path)
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        self.assertEqual(generated_alarms[0]["state"], "ACTIVE")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "ALARM_ACTIVATED")
        self.assertEqual(events[0]["previous_state"], "")
        self.assertEqual(events[0]["new_state"], "ACTIVE")
        self.assertEqual(events[0]["event_timestamp"], "2026-05-01 12:00:00")
        event_details = json.loads(events[0]["details_json"])
        self.assertEqual(event_details["threshold_value"], "240")
        self.assertEqual(event_details["clear_value"], "220")
        self.assertEqual(event_details["triggering_value"], "245")
        self.assertNotEqual(event_details["triggering_sample_id"], "")

    def test_generated_alarm_creation_rolls_back_when_event_insert_fails(self):
        temp_db_path = self.load_temp_sample_database()
        self.trigger_ups_high_load_rule(temp_db_path)

        with (
            mock.patch.object(
                backend_summary,
                "insert_alarm_event_for_evaluation",
                side_effect=RuntimeError("event insert failed"),
            ),
            self.assertRaises(RuntimeError),
        ):
            backend_summary.evaluate_generated_alarms(temp_db_path)

        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)
        events = backend_summary.get_alarm_events(temp_db_path)

        self.assertEqual(generated_alarms, [])
        self.assertEqual(events, [])

    def test_promoting_pending_alarm_to_active_inserts_event(self):
        temp_db_path = self.load_temp_sample_database()
        self.set_alarm_rule_values(
            temp_db_path,
            "RULE-UPS-A-HIGH-LOAD",
            delay_seconds=300,
        )
        self.trigger_ups_high_load_rule(temp_db_path)

        with mock.patch.object(
            backend_summary,
            "current_timestamp",
            side_effect=[
                "2026-05-01 12:00:00",
                "2026-05-01 12:05:00",
            ],
        ):
            backend_summary.evaluate_generated_alarms(temp_db_path)
            backend_summary.evaluate_generated_alarms(temp_db_path)

        events = backend_summary.get_alarm_events(temp_db_path)
        event_types = [event["event_type"] for event in events]
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        self.assertEqual(generated_alarms[0]["state"], "ACTIVE")
        self.assertEqual(event_types, ["ALARM_ACTIVATED", "PENDING_CREATED"])
        self.assertEqual(events[0]["previous_state"], "PENDING")
        self.assertEqual(events[0]["new_state"], "ACTIVE")

    def test_repeated_evaluation_without_state_change_does_not_duplicate_events(self):
        temp_db_path = self.load_temp_sample_database()
        self.trigger_ups_high_load_rule(temp_db_path)

        backend_summary.evaluate_generated_alarms(temp_db_path)
        backend_summary.evaluate_generated_alarms(temp_db_path)

        events = backend_summary.get_alarm_events(temp_db_path)
        activation_events = [
            event
            for event in events
            if event["event_type"] == "ALARM_ACTIVATED"
        ]

        self.assertEqual(len(events), 1)
        self.assertEqual(len(activation_events), 1)

    def test_clearing_alarm_inserts_event(self):
        temp_db_path = self.load_temp_sample_database()
        self.trigger_ups_high_load_rule(temp_db_path)
        backend_summary.evaluate_generated_alarms(temp_db_path)

        self.clear_ups_high_load_rule(temp_db_path)
        backend_summary.evaluate_generated_alarms(temp_db_path)
        events = backend_summary.get_alarm_events(temp_db_path)
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)

        clear_events = [
            event
            for event in events
            if event["event_type"] == "ALARM_CLEARED"
        ]

        self.assertEqual(generated_alarms[0]["state"], "CLEARED")
        self.assertEqual(len(clear_events), 1)
        self.assertEqual(clear_events[0]["previous_state"], "ACTIVE")
        self.assertEqual(clear_events[0]["new_state"], "CLEARED")
        self.assertEqual(clear_events[0]["message"], "Normal")

    def test_acknowledging_alarm_inserts_event(self):
        temp_db_path = self.load_temp_sample_database()
        self.trigger_ups_high_load_rule(temp_db_path)
        backend_summary.evaluate_generated_alarms(temp_db_path)
        alarm_id = backend_summary.get_generated_alarms(temp_db_path)[0]["id"]

        with mock.patch.object(
            backend_summary,
            "current_timestamp",
            return_value="2026-05-01 13:00:00",
        ):
            backend_summary.acknowledge_generated_alarm(
                alarm_id,
                acknowledged_by="operator-a",
                db_path=temp_db_path,
            )

        events = backend_summary.get_alarm_events(temp_db_path)
        generated_alarm = backend_summary.get_generated_alarms(temp_db_path)[0]
        acknowledgement_events = [
            event
            for event in events
            if event["event_type"] == "ALARM_ACKNOWLEDGED"
        ]

        self.assertTrue(generated_alarm["acknowledged"])
        self.assertEqual(generated_alarm["acknowledged_by"], "operator-a")
        self.assertEqual(len(acknowledgement_events), 1)
        self.assertEqual(acknowledgement_events[0]["generated_alarm_id"], alarm_id)
        self.assertEqual(acknowledgement_events[0]["previous_state"], "ACTIVE")
        self.assertEqual(acknowledgement_events[0]["new_state"], "ACTIVE")
        self.assertEqual(acknowledgement_events[0]["acknowledged_by"], "operator-a")
        self.assertEqual(
            acknowledgement_events[0]["event_timestamp"],
            "2026-05-01 13:00:00",
        )

    def test_acknowledge_rolls_back_when_event_insert_fails(self):
        temp_db_path = self.load_temp_sample_database()
        self.trigger_ups_high_load_rule(temp_db_path)
        backend_summary.evaluate_generated_alarms(temp_db_path)
        alarm_id = backend_summary.get_generated_alarms(temp_db_path)[0]["id"]

        with (
            mock.patch.object(
                backend_summary,
                "insert_alarm_event",
                side_effect=RuntimeError("event insert failed"),
            ),
            self.assertRaises(RuntimeError),
        ):
            backend_summary.acknowledge_generated_alarm(
                alarm_id,
                acknowledged_by="operator-a",
                db_path=temp_db_path,
            )

        generated_alarm = backend_summary.get_generated_alarms(temp_db_path)[0]
        acknowledgement_events = [
            event
            for event in backend_summary.get_alarm_events(temp_db_path)
            if event["event_type"] == "ALARM_ACKNOWLEDGED"
        ]

        self.assertFalse(generated_alarm["acknowledged"])
        self.assertEqual(generated_alarm["acknowledged_at"], "")
        self.assertEqual(generated_alarm["acknowledged_by"], "")
        self.assertEqual(acknowledgement_events, [])

    def test_alarm_events_endpoint_returns_context(self):
        temp_db_path = self.load_temp_sample_database()
        self.trigger_ups_high_load_rule(temp_db_path)
        backend_summary.evaluate_generated_alarms(temp_db_path)

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "get_alarm_events",
                lambda: backend_summary.get_alarm_events(temp_db_path),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/alarm-events",
            )

        self.assertEqual(status, 200)
        self.assertIn("alarm_events", data)
        self.assertEqual(len(data["alarm_events"]), 1)

        event = data["alarm_events"][0]
        self.assertEqual(event["event_type"], "ALARM_ACTIVATED")
        self.assertEqual(event["rule_id"], "RULE-UPS-A-HIGH-LOAD")
        self.assertEqual(event["rule_name"], "UPS high load")
        self.assertEqual(event["point_id"], "UPS-A_OUTPUT_KW")
        self.assertEqual(event["point_name"], "OUTPUT_KW")
        self.assertEqual(event["display_name"], "UPS-A Output kW")
        self.assertEqual(event["equipment_id"], "UPS-A")
        self.assertEqual(event["message"], "Triggered")

    def test_acknowledge_generated_alarm_endpoint_returns_error_for_invalid_id(self):
        temp_db_path = self.load_temp_sample_database()

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "acknowledge_generated_alarm",
                lambda alarm_id, acknowledged_by="local-operator": (
                    backend_summary.acknowledge_generated_alarm(
                        alarm_id,
                        acknowledged_by=acknowledged_by,
                        db_path=temp_db_path,
                    )
                ),
            ),
        ):
            status, data = get_json_from_asgi_app(
                backend_main.app,
                "/generated-alarms/not-a-real-alarm/acknowledge",
                method="POST",
            )

        self.assertEqual(status, 404)
        self.assertIn("Generated alarm not found", data["error"])

    def test_acknowledged_active_alarm_can_later_clear_normally(self):
        temp_db_path = self.load_temp_sample_database()
        self.trigger_ups_high_load_rule(temp_db_path)
        backend_summary.evaluate_generated_alarms(temp_db_path)
        alarm_id = backend_summary.get_generated_alarms(temp_db_path)[0]["id"]
        backend_summary.acknowledge_generated_alarm(
            alarm_id,
            acknowledged_by="operator-a",
            db_path=temp_db_path,
        )

        self.clear_ups_high_load_rule(temp_db_path)
        summary = backend_summary.evaluate_generated_alarms(temp_db_path)
        generated_alarm = backend_summary.get_generated_alarms(temp_db_path)[0]

        self.assertEqual(summary["active_count"], 0)
        self.assertEqual(summary["cleared_count"], 1)
        self.assertEqual(generated_alarm["state"], "CLEARED")
        self.assertTrue(generated_alarm["acknowledged"])
        self.assertEqual(generated_alarm["acknowledged_by"], "operator-a")

    def test_new_generated_alarm_after_cleared_acknowledged_alarm_starts_unacknowledged(self):
        temp_db_path = self.load_temp_sample_database()
        self.trigger_ups_high_load_rule(temp_db_path)
        backend_summary.evaluate_generated_alarms(temp_db_path)
        alarm_id = backend_summary.get_generated_alarms(temp_db_path)[0]["id"]
        backend_summary.acknowledge_generated_alarm(
            alarm_id,
            acknowledged_by="operator-a",
            db_path=temp_db_path,
        )

        self.clear_ups_high_load_rule(temp_db_path)
        backend_summary.evaluate_generated_alarms(temp_db_path)
        self.trigger_ups_high_load_rule(temp_db_path)
        summary = backend_summary.evaluate_generated_alarms(temp_db_path)
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)
        active_alarm = [
            alarm
            for alarm in generated_alarms
            if alarm["state"] == "ACTIVE"
        ][0]
        cleared_alarm = [
            alarm
            for alarm in generated_alarms
            if alarm["state"] == "CLEARED"
        ][0]

        self.assertEqual(summary["created_count"], 1)
        self.assertEqual(len(generated_alarms), 2)
        self.assertFalse(active_alarm["acknowledged"])
        self.assertEqual(active_alarm["acknowledged_at"], "")
        self.assertEqual(active_alarm["acknowledged_by"], "")
        self.assertTrue(cleared_alarm["acknowledged"])

    def test_summary_counts_acknowledged_and_unacknowledged_active_alarms(self):
        temp_db_path = self.load_temp_sample_database()
        self.trigger_ups_high_load_rule(temp_db_path)
        self.set_current_point_value(temp_db_path, "GEN-1_FUEL_LEVEL", "30")
        backend_summary.evaluate_generated_alarms(temp_db_path)
        generated_alarms = backend_summary.get_generated_alarms(temp_db_path)
        ups_alarm = [
            alarm
            for alarm in generated_alarms
            if alarm["rule_id"] == "RULE-UPS-A-HIGH-LOAD"
        ][0]
        backend_summary.acknowledge_generated_alarm(
            ups_alarm["id"],
            acknowledged_by="operator-a",
            db_path=temp_db_path,
        )

        summary = backend_summary.get_alarm_summary(temp_db_path)

        self.assertEqual(summary["active_generated_alarm_count"], 2)
        self.assertEqual(summary["active_acknowledged_generated_alarm_count"], 1)
        self.assertEqual(summary["active_unacknowledged_generated_alarm_count"], 1)

    def test_summary_endpoint_returns_generated_alarm_counts(self):
        temp_db_path = self.load_temp_sample_database()
        self.trigger_ups_high_load_rule(temp_db_path)
        backend_summary.evaluate_generated_alarms(temp_db_path)

        with (
            mock.patch.object(backend_main, "DATABASE_FILE", temp_db_path),
            mock.patch.object(
                backend_main,
                "get_alarm_summary",
                lambda: backend_summary.get_alarm_summary(temp_db_path),
            ),
        ):
            status, data = get_json_from_asgi_app(backend_main.app, "/summary")

        self.assertEqual(status, 200)
        self.assertEqual(data["total_generated_alarm_count"], 1)
        self.assertEqual(data["active_generated_alarm_count"], 1)
        self.assertEqual(data["active_unacknowledged_generated_alarm_count"], 1)
        self.assertEqual(data["active_acknowledged_generated_alarm_count"], 0)
        self.assertEqual(data["pending_generated_alarm_count"], 0)
        self.assertEqual(data["active_warning_generated_alarm_count"], 1)
        self.assertEqual(data["active_critical_generated_alarm_count"], 0)
        self.assertEqual(data["cleared_generated_alarm_count"], 0)
        self.assertEqual(data["active_generated_alarm_severity_counts"], {"Warning": 1})
        self.assertEqual(data["active_generated_alarm_equipment_counts"], {"UPS-A": 1})
        self.assertNotIn("total_alarm_records", data)
        self.assertNotIn("active_critical_alarms", data)


if __name__ == "__main__":
    unittest.main()
