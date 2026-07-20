import asyncio
import csv
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from analysis import facility_fixture_loader
from analysis import load_alarm_db
from backend import main as backend_main
from backend import summary as backend_summary
from backend.services import operational_reset_service
from backend.services.facility_package_registry import FLAGSHIP_FACILITY_ID
from backend.services.facility_package_registry import FLAGSHIP_FIXTURE_VERSION
from backend.services.facility_package_registry import FLAGSHIP_MANIFEST
from backend.services.facility_package_registry import NORTHSTAR_FACILITY_ID
from backend.services.facility_package_registry import NORTHSTAR_FIXTURE_VERSION
from backend.services.facility_topology_service import get_facility_identity
from backend.services.facility_topology_service import get_facility_topology


EXPECTED_FLAGSHIP_COUNTS = {
    "facility_environments": 1,
    "alarms": 0,
    "equipment": 10,
    "points": 16,
    "alarm_rules": 0,
    "generated_alarms": 0,
    "alarm_events": 0,
    "facility_scenarios": 0,
    "alarm_correlations": 0,
    "alarm_correlation_members": 0,
    "incident_timeline": 0,
    "shift_turnover": 0,
    "equipment_out_of_service": 0,
    "corrective_actions": 0,
    "procedure_references": 0,
    "reliability_reports": 0,
    "zones": 3,
    "facility_systems": 1,
    "pressure_boundaries": 2,
    "shared_system_paths": 1,
    "monitored_dependencies": 2,
    "equipment_system_memberships": 2,
    "system_zone_services": 1,
    "equipment_shared_path_memberships": 2,
    "shared_path_monitored_dependencies": 1,
    "pressure_boundary_system_dependencies": 1,
    "pressure_boundary_monitored_dependencies": 2,
    "pressure_boundary_cascade_order": 1,
    "point_zone_bindings": 1,
    "point_system_bindings": 1,
    "point_pressure_boundary_bindings": 2,
    "point_shared_path_bindings": 2,
    "point_monitored_dependency_bindings": 2,
    "current_point_values": 0,
    "point_samples": 0,
}


def get_json_from_asgi_app(app, path, method="GET"):
    async def make_request():
        messages = []
        request_sent = False

        async def receive():
            nonlocal request_sent
            if request_sent:
                return {"type": "http.disconnect"}
            request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}

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
                "headers": [],
                "client": ("testclient", 50000),
                "server": ("testserver", 80),
                "root_path": "",
            },
            receive,
            send,
        )
        status = next(
            item["status"]
            for item in messages
            if item["type"] == "http.response.start"
        )
        body = b"".join(
            item.get("body", b"")
            for item in messages
            if item["type"] == "http.response.body"
        )
        return status, json.loads(body.decode("utf-8"))

    return asyncio.run(make_request())


class FlagshipFixtureTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.temp_root = Path(self.temp_dir.name)

    def db_path(self, name="flagship.sqlite3"):
        return self.temp_root / name

    def load_flagship(self, db_path=None, manifest_path=FLAGSHIP_MANIFEST):
        target = db_path or self.db_path()
        result = facility_fixture_loader.load_facility_fixture(
            manifest_path,
            target,
        )
        return target, result

    def copy_flagship_package(self, name):
        target = self.temp_root / name
        shutil.copytree(FLAGSHIP_MANIFEST.parent, target)
        return target / "manifest.json"

    def read_package_rows(self, manifest_path, role):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        csv_path = manifest_path.parent / manifest["files"][role]
        with csv_path.open(mode="r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            return csv_path, tuple(reader.fieldnames or ()), list(reader)

    def write_package_rows(self, csv_path, fieldnames, rows):
        with csv_path.open(mode="w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def mutate_rows(self, manifest_path, role, mutation):
        csv_path, fieldnames, rows = self.read_package_rows(manifest_path, role)
        mutation(rows)
        self.write_package_rows(csv_path, fieldnames, rows)

    def table_counts(self, db_path):
        with sqlite3.connect(db_path) as connection:
            return {
                table_name: connection.execute(
                    f"SELECT COUNT(*) FROM {table_name}"
                ).fetchone()[0]
                for table_name in EXPECTED_FLAGSHIP_COUNTS
            }


class FlagshipFixtureLoadTests(FlagshipFixtureTestCase):
    def test_manifest_loads_exact_minimum_record_counts_and_identity(self):
        db_path, result = self.load_flagship()

        self.assertEqual(result["facility_id"], FLAGSHIP_FACILITY_ID)
        self.assertEqual(result["fixture_version"], FLAGSHIP_FIXTURE_VERSION)
        self.assertEqual(self.table_counts(db_path), EXPECTED_FLAGSHIP_COUNTS)
        self.assertEqual(
            get_facility_identity(db_path),
            {
                "facility_id": FLAGSHIP_FACILITY_ID,
                "facility_name": (
                    "Advanced Materials Research and Precision-Environment Facility"
                ),
                "fixture_version": FLAGSHIP_FIXTURE_VERSION,
            },
        )

    def test_every_point_has_one_real_equipment_owner(self):
        db_path, _result = self.load_flagship()
        with sqlite3.connect(db_path) as connection:
            missing_owners = connection.execute(
                """
                SELECT points.id
                FROM points
                LEFT JOIN equipment ON equipment.equipment = points.equipment_id
                WHERE equipment.equipment IS NULL
                """
            ).fetchall()
            point_count = connection.execute(
                "SELECT COUNT(*) FROM points"
            ).fetchone()[0]

        self.assertEqual(point_count, 16)
        self.assertEqual(missing_owners, [])

    def test_typed_tables_declare_foreign_keys_without_global_enforcement(self):
        db_path, _result = self.load_flagship()
        with sqlite3.connect(db_path) as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 0)
            binding_targets = {
                row[2]
                for row in connection.execute(
                    "PRAGMA foreign_key_list(point_pressure_boundary_bindings)"
                )
            }
            membership_targets = {
                row[2]
                for row in connection.execute(
                    "PRAGMA foreign_key_list(equipment_system_memberships)"
                )
            }
            integrity_errors = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

        self.assertEqual(binding_targets, {"points", "pressure_boundaries"})
        self.assertEqual(
            membership_targets,
            {"equipment", "facility_systems"},
        )
        self.assertEqual(integrity_errors, [])

    def test_repeated_load_has_same_counts_and_query(self):
        db_path, first_result = self.load_flagship()
        first_query = get_facility_topology(db_path)

        second_result = facility_fixture_loader.load_facility_fixture(
            FLAGSHIP_MANIFEST,
            db_path,
        )

        self.assertEqual(second_result["record_counts"], first_result["record_counts"])
        self.assertEqual(get_facility_topology(db_path), first_query)

    def test_loader_rejects_normal_project_database_target_unchanged(self):
        normal_db = self.db_path("normal.sqlite3")
        original = b"normal project database sentinel"
        normal_db.write_bytes(original)

        with (
            mock.patch.object(load_alarm_db, "DATABASE_FILE", normal_db),
            self.assertRaisesRegex(ValueError, "isolated database"),
        ):
            facility_fixture_loader.load_facility_fixture(
                FLAGSHIP_MANIFEST,
                normal_db,
            )

        self.assertEqual(normal_db.read_bytes(), original)


class FlagshipTopologyQueryTests(FlagshipFixtureTestCase):
    def test_query_returns_complete_adr_0001_chain(self):
        db_path, _result = self.load_flagship()
        topology = get_facility_topology(db_path)

        self.assertEqual(topology["facility_id"], FLAGSHIP_FACILITY_ID)
        self.assertEqual(topology["fixture_version"], "1.0.0")
        ordered_boundaries = topology["pressure_cascade"]["ordered_boundaries"]
        self.assertEqual(
            [row["id"] for row in topology["pressure_cascade"]["ordered_zones"]],
            [
                "ZONE-REFERENCE-CORRIDOR",
                "ZONE-TRANSITION-AIRLOCK",
                "ZONE-PROCESS-LAB",
            ],
        )
        self.assertEqual(
            [row["id"] for row in ordered_boundaries],
            [
                "BOUNDARY-CORRIDOR-TRANSITION",
                "BOUNDARY-TRANSITION-LAB",
            ],
        )
        self.assertEqual(
            [
                (row["upstream_zone_id"], row["downstream_zone_id"])
                for row in ordered_boundaries
            ],
            [
                ("ZONE-REFERENCE-CORRIDOR", "ZONE-TRANSITION-AIRLOCK"),
                ("ZONE-TRANSITION-AIRLOCK", "ZONE-PROCESS-LAB"),
            ],
        )

        process_exhaust = topology["process_exhaust"]
        self.assertEqual(
            {
                (row["equipment_id"], row["equipment_role"])
                for row in process_exhaust["equipment_memberships"]
            },
            {
                ("FAN-EXHAUST-DUTY", "duty"),
                ("FAN-EXHAUST-STANDBY", "standby"),
            },
        )
        self.assertEqual(
            {
                (row["equipment_id"], row["shared_path_id"])
                for row in process_exhaust["equipment_shared_paths"]
            },
            {
                ("FAN-EXHAUST-DUTY", "PATH-EXHAUST-SHARED"),
                ("FAN-EXHAUST-STANDBY", "PATH-EXHAUST-SHARED"),
            },
        )
        self.assertEqual(
            process_exhaust["system_zone_services"],
            [
                {
                    "system_id": "SYSTEM-PROCESS-EXHAUST",
                    "zone_id": "ZONE-PROCESS-LAB",
                    "zone_name": "Process Laboratory",
                }
            ],
        )
        self.assertEqual(
            {
                row["dependency_id"]
                for row in process_exhaust["shared_path_monitored_dependencies"]
            },
            {"PERMISSIVE-TREATMENT"},
        )
        self.assertEqual(
            {
                row["pressure_boundary_id"]
                for row in process_exhaust[
                    "pressure_boundary_monitored_dependencies"
                ]
            },
            {
                "BOUNDARY-CORRIDOR-TRANSITION",
                "BOUNDARY-TRANSITION-LAB",
            },
        )
        self.assertEqual(
            process_exhaust["pressure_boundary_system_dependencies"],
            [
                {
                    "pressure_boundary_id": "BOUNDARY-TRANSITION-LAB",
                    "system_id": "SYSTEM-PROCESS-EXHAUST",
                }
            ],
        )

        bindings = topology["point_bindings"]
        self.assertEqual(sum(len(rows) for rows in bindings.values()), 8)
        self.assertEqual(
            {row["target_type"] for rows in bindings.values() for row in rows},
            {
                "zone",
                "system",
                "pressure_boundary",
                "shared_path",
                "monitored_dependency",
            },
        )

    def test_api_returns_deterministic_flagship_topology(self):
        db_path, _result = self.load_flagship()
        with mock.patch.object(backend_main, "DATABASE_FILE", db_path):
            first_status, first_body = get_json_from_asgi_app(
                backend_main.app,
                "/facility-topology",
            )
            second_status, second_body = get_json_from_asgi_app(
                backend_main.app,
                "/facility-topology",
            )

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertEqual(first_body, second_body)
        self.assertEqual(first_body["facility_id"], FLAGSHIP_FACILITY_ID)


class FlagshipFixtureValidationTests(FlagshipFixtureTestCase):
    def assert_invalid_fixture_preserves_database(
        self,
        name,
        role,
        mutation,
        expected_error,
    ):
        db_path, _result = self.load_flagship()
        previous_bytes = db_path.read_bytes()
        manifest_path = self.copy_flagship_package(name)
        self.mutate_rows(manifest_path, role, mutation)

        with self.assertRaisesRegex(ValueError, expected_error):
            facility_fixture_loader.load_facility_fixture(manifest_path, db_path)

        self.assertEqual(db_path.read_bytes(), previous_bytes)

    def test_required_invalid_fixture_cases_are_rejected(self):
        cases = (
            (
                "unstable-id",
                "equipment",
                lambda rows: rows[0].__setitem__("equipment", "fan lower"),
                "stable uppercase identifier",
            ),
            (
                "duplicate-id",
                "equipment",
                lambda rows: rows.append(dict(rows[0])),
                "Duplicate identifiers",
            ),
            (
                "missing-reference",
                "points",
                lambda rows: rows[0].__setitem__(
                    "equipment_id",
                    "FAN-OTHER-FIXTURE",
                ),
                "Cross-fixture or missing relationship reference",
            ),
            (
                "invalid-role",
                "equipment_system_memberships",
                lambda rows: rows[0].__setitem__("equipment_role", "lead"),
                "Invalid equipment role",
            ),
            (
                "invalid-direction",
                "pressure_boundaries",
                lambda rows: (
                    rows[0].__setitem__(
                        "upstream_zone_id",
                        "ZONE-TRANSITION-AIRLOCK",
                    ),
                    rows[0].__setitem__(
                        "downstream_zone_id",
                        "ZONE-REFERENCE-CORRIDOR",
                    ),
                ),
                "Invalid pressure-boundary direction",
            ),
            (
                "self-direction",
                "pressure_boundaries",
                lambda rows: rows[0].__setitem__(
                    "downstream_zone_id",
                    rows[0]["upstream_zone_id"],
                ),
                "cannot self-reference",
            ),
            (
                "incomplete-chain",
                "pressure_boundary_cascade_order",
                lambda rows: rows.clear(),
                "Incomplete minimum flagship relationship",
            ),
            (
                "cross-fixture",
                "zones",
                lambda rows: rows[0].__setitem__(
                    "facility_id",
                    NORTHSTAR_FACILITY_ID,
                ),
                "Cross-fixture row",
            ),
        )

        for name, role, mutation, expected_error in cases:
            with self.subTest(case=name):
                self.assert_invalid_fixture_preserves_database(
                    name,
                    role,
                    mutation,
                    expected_error,
                )

    def test_duplicate_relationship_cycle_and_multiple_primary_binding_rejected(self):
        cases = (
            (
                "duplicate-relationship",
                "system_zone_services",
                lambda rows: rows.append(dict(rows[0])),
                "Duplicate relationship row",
            ),
            (
                "cascade-cycle",
                "pressure_boundary_cascade_order",
                lambda rows: rows.append(
                    {
                        **rows[0],
                        "upstream_boundary_id": "BOUNDARY-TRANSITION-LAB",
                        "downstream_boundary_id": "BOUNDARY-CORRIDOR-TRANSITION",
                    }
                ),
                "contains a cycle",
            ),
            (
                "multiple-binding",
                "point_zone_bindings",
                lambda rows: rows.append(
                    {
                        **rows[0],
                        "point_id": "PROCESS-EXHAUST_AIRFLOW",
                    }
                ),
                "only one primary topology binding",
            ),
        )

        for name, role, mutation, expected_error in cases:
            with self.subTest(case=name):
                self.assert_invalid_fixture_preserves_database(
                    name,
                    role,
                    mutation,
                    expected_error,
                )

    def test_fixture_version_mismatch_and_missing_file_rejected(self):
        version_manifest = self.copy_flagship_package("version-mismatch")
        self.mutate_rows(
            version_manifest,
            "zones",
            lambda rows: rows[0].__setitem__("fixture_version", "9.9.9"),
        )
        missing_manifest = self.copy_flagship_package("missing-file")
        manifest = json.loads(missing_manifest.read_text(encoding="utf-8"))
        manifest["files"]["zones"] = "missing-zones.csv"
        missing_manifest.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "Fixture-version mismatch"):
            facility_fixture_loader.read_and_validate_fixture(version_manifest)
        with self.assertRaisesRegex(ValueError, "file not found"):
            facility_fixture_loader.read_and_validate_fixture(missing_manifest)

    def test_write_failure_rolls_back_prior_database(self):
        db_path, _result = self.load_flagship()
        topology_before = get_facility_topology(db_path)
        counts_before = self.table_counts(db_path)
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """
                CREATE TRIGGER reject_fixture_equipment_insert
                BEFORE INSERT ON equipment
                BEGIN
                    SELECT RAISE(ABORT, 'test fixture insert failure');
                END
                """
            )

        with self.assertRaisesRegex(sqlite3.IntegrityError, "insert failure"):
            facility_fixture_loader.load_facility_fixture(
                FLAGSHIP_MANIFEST,
                db_path,
            )

        self.assertEqual(get_facility_topology(db_path), topology_before)
        self.assertEqual(self.table_counts(db_path), counts_before)
        with sqlite3.connect(db_path) as connection:
            trigger_count = connection.execute(
                """
                SELECT COUNT(*) FROM sqlite_master
                WHERE type = 'trigger'
                  AND name = 'reject_fixture_equipment_insert'
                """
            ).fetchone()[0]
        self.assertEqual(trigger_count, 1)

        post_load_db = self.db_path("post-load-failure.sqlite3")
        self.load_flagship(post_load_db)
        post_load_topology_before = get_facility_topology(post_load_db)
        post_load_counts_before = self.table_counts(post_load_db)
        with (
            mock.patch.object(
                facility_fixture_loader,
                "_validate_stored_fixture",
                side_effect=RuntimeError("test post-load validation failure"),
            ),
            self.assertRaisesRegex(RuntimeError, "post-load validation failure"),
        ):
            facility_fixture_loader.load_facility_fixture(
                FLAGSHIP_MANIFEST,
                post_load_db,
            )

        self.assertEqual(
            get_facility_topology(post_load_db),
            post_load_topology_before,
        )
        self.assertEqual(self.table_counts(post_load_db), post_load_counts_before)


class FacilityAwareResetTests(FlagshipFixtureTestCase):
    def test_flagship_reset_preserves_configuration_without_northstar_values(self):
        db_path, _result = self.load_flagship()
        backend_summary.ingest_point_sample(
            "FAN-EXHAUST-DUTY_RUN_STATUS",
            "true",
            source="MANUAL",
            db_path=db_path,
        )
        topology_before = get_facility_topology(db_path)
        catalog_counts_before = self.table_counts(db_path)

        result = operational_reset_service.reset_operational_state(db_path=db_path)

        topology_after = get_facility_topology(db_path)
        catalog_counts_after = self.table_counts(db_path)
        self.assertEqual(result["facility_id"], FLAGSHIP_FACILITY_ID)
        self.assertEqual(result["fixture_version"], FLAGSHIP_FIXTURE_VERSION)
        self.assertEqual(result["point_samples_deleted"], 1)
        self.assertEqual(result["current_values_reset"], 0)
        self.assertEqual(topology_after, topology_before)
        for table_name in EXPECTED_FLAGSHIP_COUNTS:
            if table_name not in {"point_samples", "current_point_values"}:
                self.assertEqual(
                    catalog_counts_after[table_name],
                    catalog_counts_before[table_name],
                )
        with sqlite3.connect(db_path) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM equipment WHERE equipment = 'UPS-A'"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM current_point_values"
                ).fetchone()[0],
                0,
            )

    def test_northstar_default_load_records_context_and_reset_preserves_ids(self):
        db_path = self.db_path("northstar.sqlite3")
        load_alarm_db.load_sample_data_to_sqlite(db_path=db_path)
        with sqlite3.connect(db_path) as connection:
            equipment_before = {
                row[0] for row in connection.execute("SELECT equipment FROM equipment")
            }
            points_before = {
                row[0] for row in connection.execute("SELECT id FROM points")
            }
            connection.execute(
                """
                UPDATE current_point_values
                SET value = '245'
                WHERE point_id = 'UPS-A_OUTPUT_KW'
                """
            )

        result = operational_reset_service.reset_operational_state(db_path=db_path)
        identity = get_facility_identity(db_path)
        topology = get_facility_topology(db_path)
        with sqlite3.connect(db_path) as connection:
            equipment_after = {
                row[0] for row in connection.execute("SELECT equipment FROM equipment")
            }
            points_after = {
                row[0] for row in connection.execute("SELECT id FROM points")
            }
            ups_value = connection.execute(
                """
                SELECT value FROM current_point_values
                WHERE point_id = 'UPS-A_OUTPUT_KW'
                """
            ).fetchone()[0]

        self.assertEqual(identity["facility_id"], NORTHSTAR_FACILITY_ID)
        self.assertEqual(identity["fixture_version"], NORTHSTAR_FIXTURE_VERSION)
        self.assertEqual(result["current_values_reset"], 17)
        self.assertEqual(ups_value, "185")
        self.assertEqual(equipment_after, equipment_before)
        self.assertEqual(points_after, points_before)
        self.assertEqual(len(equipment_after), 10)
        self.assertEqual(len(points_after), 17)
        self.assertEqual(topology["pressure_cascade"]["ordered_boundaries"], [])

    def test_unknown_fixture_context_fails_without_database_change(self):
        db_path, _result = self.load_flagship()
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                "UPDATE facility_environments SET fixture_version = '9.9.9'"
            )
        previous_bytes = db_path.read_bytes()

        with self.assertRaisesRegex(LookupError, "No registered fixture package"):
            operational_reset_service.reset_operational_state(db_path=db_path)

        self.assertEqual(db_path.read_bytes(), previous_bytes)

    def test_reset_rejects_cross_fixture_baseline_override_unchanged(self):
        db_path, _result = self.load_flagship()
        previous_bytes = db_path.read_bytes()

        with self.assertRaisesRegex(ValueError, "does not match"):
            operational_reset_service.reset_operational_state(
                db_path=db_path,
                current_point_value_csv_path=load_alarm_db.CURRENT_POINT_VALUE_FILE,
            )

        self.assertEqual(db_path.read_bytes(), previous_bytes)


if __name__ == "__main__":
    unittest.main()
