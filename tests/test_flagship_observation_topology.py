import csv
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from analysis import facility_fixture_loader
from backend.services.facility_package_registry import FLAGSHIP_FACILITY_ID
from backend.services.facility_package_registry import FLAGSHIP_FIXTURE_VERSION
from backend.services.facility_package_registry import FLAGSHIP_MANIFEST
from backend.services.facility_package_registry import (
    FLAGSHIP_OBSERVATION_FIXTURE_VERSION,
)
from backend.services.facility_package_registry import (
    FLAGSHIP_OBSERVATION_MANIFEST,
)
from backend.services.facility_package_registry import FLAGSHIP_TOPOLOGY_ID
from backend.services.facility_package_registry import (
    facility_package_content_digest,
)
from backend.services.facility_package_registry import resolve_registered_fixture
from backend.services.standards_basis_service import (
    DEFAULT_STANDARDS_BASIS_MANIFEST,
)
from backend.services.standards_basis_service import (
    EXPECTED_1_1_EVIDENCE_POINT_BINDINGS,
)
from backend.services.standards_basis_service import (
    EXPECTED_1_1_EVIDENCE_TEXT_UPDATES,
)
from backend.services.standards_basis_service import (
    FLAGSHIP_OBSERVATION_STANDARDS_BASIS_MANIFEST,
)
from backend.services.standards_basis_service import (
    load_standards_basis_package,
)


HISTORICAL_TOPOLOGY_DIGEST = (
    "1a1d9101c8b38c8b7cbb126e62c748d39b7b1648313c19a61ce6e4e134c27c83"
)
HISTORICAL_STANDARDS_DIGEST = (
    "91a2780fd4315ed9ff49276131196004cb0bc64135d123f2a07dc21224b7bc73"
)
OBSERVATION_TOPOLOGY_DIGEST = (
    "cd6aeddbeaf9756c28b1cd66461b008542c4a5010dd0bcf634e4ffb825a42672"
)

EXPECTED_ADDED_EQUIPMENT_IDS = {
    "CONTROLLER-PROCESS-EXHAUST",
    "SENSOR-SUPPLY-MAKEUP-AIRFLOW",
}
EXPECTED_ADDED_POINT_IDS = {
    "PROCESS_ENABLED_STATUS",
    "PROCESS_PERMISSIVE_STATUS",
    "FAN-EXHAUST-DUTY_REQUEST",
    "FAN-EXHAUST-DUTY_CONTROLLER_EXECUTION_STATUS",
    "FAN-EXHAUST-DUTY_VFD_STATE",
    "FAN-EXHAUST-DUTY_MOTOR_CURRENT",
    "FAN-EXHAUST-STANDBY_REQUEST",
    "FAN-EXHAUST-STANDBY_CONTROLLER_EXECUTION_STATUS",
    "FAN-EXHAUST-STANDBY_VFD_STATE",
    "FAN-EXHAUST-STANDBY_MOTOR_CURRENT",
    "TREATMENT_AVAILABILITY_STATUS",
    "SUPPLY-MAKEUP_AIRFLOW",
}
EXPECTED_ADDED_BINDINGS = {
    "point_system_bindings": {
        ("PROCESS_ENABLED_STATUS", "SYSTEM-PROCESS-EXHAUST"),
        ("PROCESS_PERMISSIVE_STATUS", "SYSTEM-PROCESS-EXHAUST"),
    },
    "point_monitored_dependency_bindings": {
        ("TREATMENT_AVAILABILITY_STATUS", "PERMISSIVE-TREATMENT"),
        ("SUPPLY-MAKEUP_AIRFLOW", "DEPENDENCY-SUPPLY-MAKEUP"),
    },
}


def read_csv_rows(manifest_path, role):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    path = Path(manifest_path).parent / manifest["files"][role]
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def without_fixture_identity(row):
    return {
        key: value
        for key, value in row.items()
        if key not in {"facility_id", "fixture_version"}
    }


class FlagshipObservationTopologyTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.temp_root = Path(self.temp_directory.name)

    def test_registered_1_1_package_loads_with_exact_identity_and_counts(self):
        context = resolve_registered_fixture(
            FLAGSHIP_FACILITY_ID,
            FLAGSHIP_OBSERVATION_FIXTURE_VERSION,
        )
        self.assertEqual(context["topology_id"], FLAGSHIP_TOPOLOGY_ID)
        self.assertEqual(context["topology_version"], "1.1.0")
        self.assertEqual(
            context["package_content_digest"],
            OBSERVATION_TOPOLOGY_DIGEST,
        )

        database_path = self.temp_root / "flagship-observation.sqlite3"
        result = facility_fixture_loader.load_facility_fixture(
            FLAGSHIP_OBSERVATION_MANIFEST,
            database_path,
        )
        self.assertEqual(result["facility_id"], FLAGSHIP_FACILITY_ID)
        self.assertEqual(result["fixture_version"], "1.1.0")
        expected_counts = {
            "equipment_records": 12,
            "points_records": 28,
            "point_system_bindings_records": 3,
            "point_monitored_dependency_bindings_records": 4,
        }
        for table, count in expected_counts.items():
            self.assertEqual(result["record_counts"][table], count)

        with sqlite3.connect(database_path) as connection:
            added_equipment = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT equipment FROM equipment
                    WHERE equipment IN (?, ?)
                    """,
                    tuple(sorted(EXPECTED_ADDED_EQUIPMENT_IDS)),
                )
            }
            added_points = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT id FROM points
                    WHERE id IN ({})
                    """.format(
                        ",".join("?" for _ in EXPECTED_ADDED_POINT_IDS)
                    ),
                    tuple(sorted(EXPECTED_ADDED_POINT_IDS)),
                )
            }
        self.assertEqual(added_equipment, EXPECTED_ADDED_EQUIPMENT_IDS)
        self.assertEqual(added_points, EXPECTED_ADDED_POINT_IDS)

    def test_1_1_is_the_exact_additive_topology_diff(self):
        historical = facility_fixture_loader.read_and_validate_fixture(
            FLAGSHIP_MANIFEST
        )
        observation = facility_fixture_loader.read_and_validate_fixture(
            FLAGSHIP_OBSERVATION_MANIFEST
        )
        self.assertEqual(
            observation["identity"]["fixture_version"],
            FLAGSHIP_OBSERVATION_FIXTURE_VERSION,
        )

        historical_equipment = {
            row["equipment"]: without_fixture_identity(row)
            for row in read_csv_rows(FLAGSHIP_MANIFEST, "equipment")
        }
        observation_equipment = {
            row["equipment"]: without_fixture_identity(row)
            for row in read_csv_rows(FLAGSHIP_OBSERVATION_MANIFEST, "equipment")
        }
        self.assertEqual(
            set(observation_equipment) - set(historical_equipment),
            EXPECTED_ADDED_EQUIPMENT_IDS,
        )
        for equipment_id, row in historical_equipment.items():
            self.assertEqual(observation_equipment[equipment_id], row)

        historical_points = {
            row["id"]: without_fixture_identity(row)
            for row in read_csv_rows(FLAGSHIP_MANIFEST, "points")
        }
        observation_points = {
            row["id"]: without_fixture_identity(row)
            for row in read_csv_rows(FLAGSHIP_OBSERVATION_MANIFEST, "points")
        }
        self.assertEqual(
            set(observation_points) - set(historical_points),
            EXPECTED_ADDED_POINT_IDS,
        )
        for point_id, row in historical_points.items():
            self.assertEqual(observation_points[point_id], row)

        for role in facility_fixture_loader.FILE_DEFINITIONS:
            if role in {
                "equipment",
                "points",
                "point_system_bindings",
                "point_monitored_dependency_bindings",
            }:
                continue
            historical_rows = {
                tuple(sorted(without_fixture_identity(row).items()))
                for row in read_csv_rows(FLAGSHIP_MANIFEST, role)
            }
            observation_rows = {
                tuple(sorted(without_fixture_identity(row).items()))
                for row in read_csv_rows(FLAGSHIP_OBSERVATION_MANIFEST, role)
            }
            self.assertEqual(observation_rows, historical_rows, role)

        for role, expected_additions in EXPECTED_ADDED_BINDINGS.items():
            columns = facility_fixture_loader.FILE_DEFINITIONS[role]["columns"]
            historical_rows = {
                tuple(row[column] for column in columns)
                for row in read_csv_rows(FLAGSHIP_MANIFEST, role)
            }
            observation_rows = {
                tuple(row[column] for column in columns)
                for row in read_csv_rows(FLAGSHIP_OBSERVATION_MANIFEST, role)
            }
            self.assertEqual(
                observation_rows - historical_rows,
                expected_additions,
                role,
            )

        self.assertEqual(len(historical["rows"]["equipment"]), 10)
        self.assertEqual(len(observation["rows"]["equipment"]), 12)
        self.assertEqual(len(historical["rows"]["points"]), 16)
        self.assertEqual(len(observation["rows"]["points"]), 28)

    def test_historical_topology_and_standards_packages_remain_byte_exact(self):
        self.assertEqual(FLAGSHIP_FIXTURE_VERSION, "1.0.0")
        self.assertEqual(FLAGSHIP_MANIFEST.parent.name, "1.0.0")
        self.assertEqual(
            facility_package_content_digest(FLAGSHIP_MANIFEST),
            HISTORICAL_TOPOLOGY_DIGEST,
        )
        self.assertEqual(
            facility_package_content_digest(DEFAULT_STANDARDS_BASIS_MANIFEST),
            HISTORICAL_STANDARDS_DIGEST,
        )

    def test_loader_rejects_a_missing_1_1_addition_before_database_mutation(self):
        package_root = self.temp_root / "invalid-1.1.0"
        shutil.copytree(FLAGSHIP_OBSERVATION_MANIFEST.parent, package_root)
        manifest_path = package_root / "manifest.json"
        point_path = package_root / "points.csv"
        with point_path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            fieldnames = reader.fieldnames
            rows = [
                row
                for row in reader
                if row["id"] != "PROCESS_ENABLED_STATUS"
            ]
        with point_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        database_path = self.temp_root / "sentinel.sqlite3"
        sentinel = b"unmodified database sentinel"
        database_path.write_bytes(sentinel)
        with self.assertRaisesRegex(
            ValueError,
            "missing relationship reference|point inventory",
        ):
            facility_fixture_loader.read_and_validate_fixture(manifest_path)
        self.assertEqual(database_path.read_bytes(), sentinel)

    def test_standards_1_1_validates_only_the_additive_point_representations(self):
        historical = load_standards_basis_package(
            DEFAULT_STANDARDS_BASIS_MANIFEST
        )
        observation = load_standards_basis_package(
            FLAGSHIP_OBSERVATION_STANDARDS_BASIS_MANIFEST
        )
        manifest = observation["manifest"]
        self.assertEqual(manifest["package_id"], "STANDARDS-BASIS-FLAGSHIP-1.1.0")
        self.assertEqual(manifest["package_version"], "1.1.0")
        self.assertEqual(manifest["facility"]["fixture_version"], "1.1.0")
        self.assertEqual(
            manifest["topology"],
            {
                "topology_id": FLAGSHIP_TOPOLOGY_ID,
                "topology_version": "1.1.0",
                "topology_content_digest": OBSERVATION_TOPOLOGY_DIGEST,
            },
        )

        for role in (
            "applicability_profile",
            "controlled_sources",
            "applicability_matrix",
            "requirements",
        ):
            self.assertEqual(observation[role], historical[role], role)

        historical_evidence = {
            record["id"]: record for record in historical["evidence_categories"]
        }
        observation_evidence = {
            record["id"]: record for record in observation["evidence_categories"]
        }
        self.assertEqual(set(observation_evidence), set(historical_evidence))
        for evidence_id, record in observation_evidence.items():
            expected = dict(historical_evidence[evidence_id])
            if evidence_id in EXPECTED_1_1_EVIDENCE_POINT_BINDINGS:
                representation, point_ids = (
                    EXPECTED_1_1_EVIDENCE_POINT_BINDINGS[evidence_id]
                )
                expected["point_definition_representation"] = representation
                expected["bound_point_definition_ids"] = point_ids
            expected.update(
                EXPECTED_1_1_EVIDENCE_TEXT_UPDATES.get(evidence_id, {})
            )
            self.assertEqual(record, expected, evidence_id)
            self.assertEqual(
                record["observation_availability"],
                "NO_FLAGSHIP_OBSERVATION_BASELINE",
            )

        for requirement in observation["requirements"]:
            self.assertEqual(requirement["activation_status"], "INACTIVE")
            self.assertIs(requirement["executable"], False)


if __name__ == "__main__":
    unittest.main()
