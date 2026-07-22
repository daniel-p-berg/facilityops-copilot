import json
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.services.standards_basis_service import APPROVED_QUALITATIVE_REQUIREMENTS
from backend.services.standards_basis_service import DEFAULT_STANDARDS_BASIS_MANIFEST
from backend.services.standards_basis_service import FLAGSHIP_FACILITY_ID
from backend.services.standards_basis_service import StandardsBasisStore
from backend.services.standards_basis_service import StandardsBasisValidationError
from backend.services.standards_basis_service import get_standards_traceability
from backend.services.standards_basis_service import load_standards_basis_package


class StandardsBasisPackageTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.temp_root = Path(self.temp_dir.name)

    def copy_package(self, name="standards-basis"):
        target = self.temp_root / name
        shutil.copytree(DEFAULT_STANDARDS_BASIS_MANIFEST.parent, target)
        return target / "manifest.json"

    def read_json(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    def write_json(self, path, value):
        path.write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def role_path(self, manifest_path, role):
        manifest = self.read_json(manifest_path)
        return manifest_path.parent / manifest["files"][role]

    def mutate_role(self, manifest_path, role, mutation):
        path = self.role_path(manifest_path, role)
        value = self.read_json(path)
        mutation(value)
        self.write_json(path, value)


class StandardsBasisLoadTests(StandardsBasisPackageTestCase):
    def test_loads_complete_flagship_basis_with_exact_record_counts(self):
        package = load_standards_basis_package()

        self.assertEqual(package["manifest"]["facility"]["facility_id"], FLAGSHIP_FACILITY_ID)
        self.assertEqual(package["manifest"]["facility"]["fixture_version"], "1.0.0")
        self.assertEqual(package["manifest"]["status"], "READ_ONLY_NON_EXECUTABLE")
        self.assertEqual(
            {
                role: len(package[role])
                for role in (
                    "applicability_profile",
                    "controlled_sources",
                    "applicability_matrix",
                    "evidence_categories",
                    "requirements",
                )
            },
            {
                "applicability_profile": 18,
                "controlled_sources": 27,
                "applicability_matrix": 23,
                "evidence_categories": 17,
                "requirements": 12,
            },
        )

    def test_profile_records_exact_owner_decisions_and_legal_limitations(self):
        package = load_standards_basis_package()
        facts = {record["id"]: record for record in package["applicability_profile"]}

        self.assertEqual(
            facts["PROFILE-OPEN-BATCH-BOUND"]["statement"],
            "The maximum open powder batch is 250 g.",
        )
        self.assertEqual(
            facts["PROFILE-INVENTORY-BOUND"]["statement"],
            "The maximum powder inventory in the laboratory is 5 kg in closed containers.",
        )
        self.assertIn("not a verified legal classification", facts["PROFILE-GROUP-B-ASSUMPTION"]["limitations"])
        self.assertIn("No numerical differential-pressure criterion", facts["PROFILE-PRESSURE-DIRECTION"]["limitations"])

    def test_exact_ten_recorded_requirements_are_accepted_and_all_are_inactive(self):
        package = load_standards_basis_package()
        requirements = {record["id"]: record for record in package["requirements"]}
        accepted = {
            requirement_id
            for requirement_id, record in requirements.items()
            if record["approval_status"] == "PROJECT_OWNER_DECISION_RECORDED"
        }

        self.assertEqual(accepted, set(APPROVED_QUALITATIVE_REQUIREMENTS))
        for requirement_id, statement in APPROVED_QUALITATIVE_REQUIREMENTS.items():
            record = requirements[requirement_id]
            self.assertEqual(record["statement"], statement)
            self.assertEqual(record["lifecycle_status"], "ACCEPTED_FOR_SIMULATION")
            self.assertEqual(record["activation_status"], "INACTIVE")
            self.assertEqual(record["parameter_status"], "NO_NUMERICAL_CRITERIA_APPROVED")
            self.assertIs(record["executable"], False)

        proposed = [record for record in requirements.values() if record["approval_status"] == "PROPOSED"]
        self.assertEqual(len(proposed), 2)
        self.assertTrue(all(record["lifecycle_status"] == "DRAFT" for record in proposed))
        self.assertTrue(all(record["activation_status"] == "INACTIVE" for record in proposed))

    def test_traceability_resolves_source_to_basis_to_requirement_to_evidence(self):
        result = get_standards_traceability(
            StandardsBasisStore(DEFAULT_STANDARDS_BASIS_MANIFEST)
        )

        self.assertEqual(len(result["traceability"]), 12)
        for chain in result["traceability"]:
            requirement = chain["requirement"]
            self.assertTrue(chain["controlled_sources"])
            self.assertTrue(chain["applicability_bases"])
            self.assertTrue(chain["required_evidence_categories"])
            self.assertEqual(
                [record["id"] for record in chain["applicability_bases"]],
                requirement["applicability_basis_ids"],
            )
            self.assertEqual(
                [record["id"] for record in chain["required_evidence_categories"]],
                requirement["evidence_category_ids"],
            )

    def test_repeated_load_is_deterministic_and_returns_independent_copies(self):
        store = StandardsBasisStore(DEFAULT_STANDARDS_BASIS_MANIFEST)
        first = store.load()
        second = store.load()
        self.assertEqual(first, second)

        first["requirements"][0]["title"] = "mutated caller copy"
        self.assertNotEqual(store.get()["requirements"][0]["title"], "mutated caller copy")


class StandardsBasisValidationTests(StandardsBasisPackageTestCase):
    def assert_invalid(self, manifest_path, pattern):
        with self.assertRaisesRegex(StandardsBasisValidationError, pattern):
            load_standards_basis_package(manifest_path)

    def test_rejects_duplicate_identifiers(self):
        manifest_path = self.copy_package()

        def duplicate(value):
            value["records"].append(dict(value["records"][0]))

        self.mutate_role(manifest_path, "applicability_profile", duplicate)
        self.assert_invalid(manifest_path, "Duplicate identifier")

    def test_rejects_invalid_status(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["status"] = "APPLICABLE"

        self.mutate_role(manifest_path, "applicability_matrix", invalidate)
        self.assert_invalid(manifest_path, "status is invalid")

    def test_rejects_unresolved_source_reference(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["source_id"] = "SRC-DOES-NOT-EXIST"

        self.mutate_role(manifest_path, "applicability_matrix", invalidate)
        self.assert_invalid(manifest_path, "source_id is unresolved")

    def test_rejects_unresolved_profile_fact_reference(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["profile_fact_ids"] = ["PROFILE-DOES-NOT-EXIST"]

        self.mutate_role(manifest_path, "controlled_sources", invalidate)
        self.assert_invalid(manifest_path, "unknown profile facts")

    def test_rejects_unresolved_evidence_reference(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["evidence_category_ids"] = ["EVIDENCE-DOES-NOT-EXIST"]

        self.mutate_role(manifest_path, "requirements", invalidate)
        self.assert_invalid(manifest_path, "unknown evidence categories")

    def test_rejects_missing_provenance(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            del value["records"][0]["provenance"]

        self.mutate_role(manifest_path, "controlled_sources", invalidate)
        self.assert_invalid(manifest_path, "keys invalid")

    def test_rejects_wrong_facility_binding(self):
        manifest_path = self.copy_package()
        manifest = self.read_json(manifest_path)
        manifest["facility"]["facility_id"] = "FACILITY-NORTHSTAR-DATA-HALL"
        self.write_json(manifest_path, manifest)

        self.assert_invalid(manifest_path, "must bind to the flagship facility")

    def test_rejects_cross_fixture_record(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["facility_id"] = "FACILITY-NORTHSTAR-DATA-HALL"

        self.mutate_role(manifest_path, "requirements", invalidate)
        self.assert_invalid(manifest_path, "does not match the package binding")

    def test_rejects_attempt_to_mark_requirement_executable(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["executable"] = True

        self.mutate_role(manifest_path, "requirements", invalidate)
        self.assert_invalid(manifest_path, "attempts to mark a requirement executable")

    def test_rejects_nonallowlisted_accepted_requirement(self):
        manifest_path = self.copy_package()
        manifest = self.read_json(manifest_path)
        manifest["accepted_qualitative_requirement_ids"].append("REQ-SOO-PROPOSED-011")
        self.write_json(manifest_path, manifest)

        self.assert_invalid(manifest_path, "must match the project-owner decision")

    def test_rejects_numerical_criterion_payload(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["numerical_criterion"] = {"value": 1, "unit": "Pa"}

        self.mutate_role(manifest_path, "requirements", invalidate)
        self.assert_invalid(manifest_path, "unexpected=.*numerical_criterion")

    def test_rejects_numerical_criterion_hidden_in_requirement_text(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][-1]["statement"] = "A proposed delay is 30 seconds."

        self.mutate_role(manifest_path, "requirements", invalidate)
        self.assert_invalid(manifest_path, "unapproved numerical criterion")

    def test_rejects_manifest_path_traversal(self):
        manifest_path = self.copy_package()
        manifest = self.read_json(manifest_path)
        manifest["files"]["requirements"] = "../requirements.json"
        self.write_json(manifest_path, manifest)

        self.assert_invalid(manifest_path, "escapes the package directory")

    def test_rejects_malformed_json(self):
        manifest_path = self.copy_package()
        self.role_path(manifest_path, "requirements").write_text("{", encoding="utf-8")
        self.assert_invalid(manifest_path, "Unable to read requirements")

    def test_failed_reload_preserves_prior_atomic_snapshot(self):
        valid_manifest = self.copy_package("valid")
        invalid_manifest = self.copy_package("invalid")
        store = StandardsBasisStore(valid_manifest)
        original = store.load()

        def invalidate(value):
            value["records"][0]["executable"] = True

        self.mutate_role(invalid_manifest, "requirements", invalidate)
        with self.assertRaises(StandardsBasisValidationError):
            store.load(invalid_manifest)

        self.assertEqual(store.get(), original)


if __name__ == "__main__":
    unittest.main()
