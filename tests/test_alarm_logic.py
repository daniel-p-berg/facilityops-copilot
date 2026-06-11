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
from backend import main as backend_main
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
        reload_counts = load_alarm_db.load_sample_data_to_sqlite(db_path=temp_db_path)
        self.assertEqual(reload_counts["current_point_value_records"], 17)

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

        self.assertIsNotNone(table_exists)
        self.assertEqual(current_value_count, 17)
        self.assertEqual(unique_point_count, 17)

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
                SELECT value, quality, source, updated_at
                FROM current_point_values
                WHERE id = 'CPV-TEST-OPTIONAL'
                """
            ).fetchone()

        self.assertEqual(current_value_row, ("", "UNKNOWN", "", ""))

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
        self.assertEqual(bad_quality_result["evaluation_status"], "Bad quality")
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
        return temp_db_path

    def trigger_ups_high_load_rule(self, db_path):
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """
                UPDATE current_point_values
                SET value = '245'
                WHERE point_id = 'UPS-A_OUTPUT_KW'
                """
            )

    def clear_ups_high_load_rule(self, db_path):
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """
                UPDATE current_point_values
                SET value = '185'
                WHERE point_id = 'UPS-A_OUTPUT_KW'
                """
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
            generated_alarm_count = connection.execute(
                "SELECT COUNT(*) FROM generated_alarms"
            ).fetchone()[0]

        self.assertIsNotNone(table_exists)
        self.assertEqual(generated_alarm_count, 0)

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
        self.assertEqual(len(generated_alarms), 1)
        self.assertEqual(generated_alarms[0]["state"], "ACTIVE")


if __name__ == "__main__":
    unittest.main()
