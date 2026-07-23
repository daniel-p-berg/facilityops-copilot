import asyncio
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend import main as backend_main
from backend.services.standards_basis_service import APPROVED_QUALITATIVE_REQUIREMENTS
from backend.services.standards_basis_service import DEFAULT_STANDARDS_BASIS_MANIFEST
from backend.services.standards_basis_service import FLAGSHIP_FACILITY_ID
from backend.services.standards_basis_service import StandardsBasisStore
from backend.services.standards_basis_service import StandardsBasisValidationError
from backend.services.standards_basis_service import get_standards_traceability
from backend.services.standards_basis_service import load_standards_basis_package


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
            package["manifest"]["provenance"]["project_owner_decision_reference"],
            "ADR 0004 and the project-owner directive dated 2026-07-22",
        )
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
                "controlled_sources": 35,
                "applicability_matrix": 29,
                "evidence_categories": 19,
                "requirements": 12,
            },
        )

    def test_profile_records_exact_owner_decisions_and_legal_limitations(self):
        package = load_standards_basis_package()
        facts = {record["id"]: record for record in package["applicability_profile"]}

        self.assertEqual(
            {record["status"] for record in facts.values()},
            {"PROJECT_OWNER_DECISION_RECORDED"},
        )
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

        owner_source = next(
            record
            for record in package["controlled_sources"]
            if record["id"] == "SRC-OWNER-DIRECTIVE-2026-07-22"
        )
        self.assertEqual(
            owner_source["adoption_status"],
            "PROJECT_OWNER_DECISION_RECORDED",
        )

        sources = {record["id"]: record for record in package["controlled_sources"]}
        electrical_source = sources["SRC-NFPA-70-ELECTRICAL"]
        self.assertEqual(electrical_source["identifier"], "NFPA 70-2023")
        self.assertEqual(
            electrical_source["edition_or_effective_date"],
            "2023 edition",
        )
        self.assertEqual(
            electrical_source["official_url"],
            "https://link.nfpa.org/all-publications/70/2023",
        )
        self.assertEqual(
            sources["SRC-ASHRAE-MEASUREMENT-METHODS"]["edition_or_effective_date"],
            "2026, 2025, and 2023 editions, respectively",
        )

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
        self.assertIn(
            "EVIDENCE-PROCESS-ENABLED-CONTEXT",
            requirements["REQ-SOO-002"]["evidence_category_ids"],
        )

    def test_point_definitions_are_separate_from_absent_baseline_observations(self):
        package = load_standards_basis_package()
        evidence = {record["id"]: record for record in package["evidence_categories"]}

        self.assertEqual(
            {record["observation_availability"] for record in evidence.values()},
            {"NO_FLAGSHIP_OBSERVATION_BASELINE"},
        )
        self.assertEqual(
            evidence["EVIDENCE-SUPPLY-MAKEUP-CONTROLLER-STATUS"][
                "bound_point_definition_ids"
            ],
            ["SUPPLY-MAKEUP_STATUS"],
        )
        self.assertEqual(
            evidence["EVIDENCE-SUPPLY-MAKEUP-DELIVERED-RESPONSE"][
                "point_definition_representation"
            ],
            "MISSING_POINT_DEFINITIONS",
        )
        self.assertEqual(
            evidence["EVIDENCE-SUPPLY-MAKEUP-DELIVERED-RESPONSE"][
                "bound_point_definition_ids"
            ],
            [],
        )

    def test_multi_source_bases_are_structural_and_new_scope_bases_are_not_requirements(self):
        package = load_standards_basis_package()
        bases = {record["id"]: record for record in package["applicability_matrix"]}

        self.assertEqual(
            bases["BASIS-TOWN-AHJ-ASSUMPTION"]["source_ids"],
            [
                "SRC-TOWN-HORSEHEADS-CHAPTER-83",
                "SRC-TOWN-HORSEHEADS-CODE-ENFORCEMENT",
                "SRC-NYS-EXECUTIVE-LAW-ARTICLE-18",
                "SRC-NYS-19-NYCRR-PART-1203",
            ],
        )
        self.assertEqual(
            bases["BASIS-ELECTRICAL-INSTALLATION"]["source_ids"],
            [
                "SRC-NFPA-70-ELECTRICAL",
                "SRC-NYS-UNIFORM-CODE-ADOPTION-2025",
                "SRC-NYS-BUILDING-CODE-2025",
            ],
        )
        self.assertEqual(
            bases["BASIS-FAN-RATING-AND-SYSTEM-EFFECT"]["source_ids"],
            ["SRC-AMCA-210-2025", "SRC-AMCA-201-2023"],
        )

        unlinked_basis_ids = {
            "BASIS-NYS-ECL-AIR-CONTROL",
            "BASIS-NYS-AIR-SOURCE-CLASSIFICATION",
            "BASIS-NYS-AIR-PERMITTING",
            "BASIS-NYS-AIR-GENERAL-PROHIBITIONS",
            "BASIS-NYS-PROCESS-OPERATIONS",
            "BASIS-NFPA-45-LABORATORY-SCOPE",
        }
        linked_basis_ids = {
            basis_id
            for requirement in package["requirements"]
            for basis_id in requirement["applicability_basis_ids"]
        }
        self.assertTrue(unlinked_basis_ids.isdisjoint(linked_basis_ids))

    def test_corrected_source_metadata_is_preserved(self):
        package = load_standards_basis_package()
        sources = {record["id"]: record for record in package["controlled_sources"]}

        self.assertEqual(
            sources["SRC-LBNL-OPENBUILDINGCONTROL"]["date_status"],
            "NOT_STATED",
        )
        self.assertIn(
            "No edition or report date stated",
            sources["SRC-LBNL-OPENBUILDINGCONTROL"][
                "edition_or_effective_date"
            ],
        )
        self.assertEqual(
            sources["SRC-AMCA-210-2025"]["identifier"],
            "ANSI/AMCA 210-25 and ANSI/ASHRAE 51-25",
        )
        self.assertEqual(
            sources["SRC-AMCA-201-2023"]["identifier"],
            "AMCA Publication 201-23",
        )
        court_support = sources[
            "SRC-NYS-UNIFORM-CODE-COURT-NOTICE-2026-07-02"
        ]["direct_support"]
        self.assertIn("19 NYCRR Section 1240.6", court_support)
        self.assertIn("fossil-fuel equipment and building systems", court_support)
        for part in ("200", "201", "211", "212"):
            self.assertEqual(
                sources[f"SRC-NYS-6-NYCRR-PART-{part}"]["access_status"],
                "OFFICIAL_PUBLIC_METADATA",
            )

    def test_traceability_resolves_source_to_basis_to_requirement_to_evidence(self):
        store = StandardsBasisStore(DEFAULT_STANDARDS_BASIS_MANIFEST)
        package = store.get()
        requirements = {record["id"]: record for record in package["requirements"]}
        result = get_standards_traceability(store)

        self.assertEqual(len(result["traceability"]), 12)
        for chain in result["traceability"]:
            requirement = chain["requirement"]
            source_requirement = requirements[requirement["id"]]
            self.assertEqual(
                set(requirement),
                {
                    "id",
                    "lifecycle_status",
                    "approval_status",
                    "provenance_basis_type",
                    "provenance_reference",
                    "activation_status",
                    "executable",
                },
            )
            self.assertTrue(chain["controlled_sources"])
            self.assertTrue(chain["applicability_bases"])
            self.assertTrue(chain["required_evidence_categories"])
            self.assertEqual(
                [record["id"] for record in chain["applicability_bases"]],
                source_requirement["applicability_basis_ids"],
            )
            self.assertEqual(
                [record["id"] for record in chain["required_evidence_categories"]],
                source_requirement["evidence_category_ids"],
            )
            expected_source_links = [
                (basis["id"], source_id)
                for basis in chain["applicability_bases"]
                for source_id in basis["source_ids"]
            ]
            self.assertEqual(
                [
                    (source["applicability_basis_id"], source["id"])
                    for source in chain["controlled_sources"]
                ],
                expected_source_links,
            )
            self.assertTrue(
                all(
                    {
                        "source_category",
                        "adoption_status",
                        "enforcement_status",
                    }
                    <= set(source)
                    for source in chain["controlled_sources"]
                )
            )
            self.assertTrue(
                all(
                    {
                        "basis_category",
                        "status",
                        "source_ids",
                    }
                    <= set(basis)
                    for basis in chain["applicability_bases"]
                )
            )
            self.assertTrue(
                all(
                    {
                        "point_definition_representation",
                        "bound_point_definition_ids",
                        "observation_availability",
                    }
                    <= set(category)
                    for category in chain["required_evidence_categories"]
                )
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

    def test_rejects_duplicate_identifier_across_package_roles(self):
        manifest_path = self.copy_package()
        controlled_sources = self.read_json(
            self.role_path(manifest_path, "controlled_sources")
        )
        duplicate_id = controlled_sources["records"][0]["id"]

        def duplicate_across_roles(value):
            value["records"][0]["id"] = duplicate_id

        self.mutate_role(
            manifest_path,
            "applicability_profile",
            duplicate_across_roles,
        )
        self.assert_invalid(manifest_path, "Duplicate identifier across package roles")

    def test_rejects_invalid_status(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["status"] = "APPLICABLE"

        self.mutate_role(manifest_path, "applicability_matrix", invalidate)
        self.assert_invalid(manifest_path, "status is invalid")

    def test_rejects_unresolved_source_reference(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["source_ids"] = ["SRC-DOES-NOT-EXIST"]

        self.mutate_role(manifest_path, "applicability_matrix", invalidate)
        self.assert_invalid(manifest_path, "source_ids contain unresolved references")

    def test_rejects_empty_source_ids(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["source_ids"] = []

        self.mutate_role(manifest_path, "applicability_matrix", invalidate)
        self.assert_invalid(manifest_path, "source_ids must not be empty")

    def test_rejects_duplicate_source_ids(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            source_id = value["records"][0]["source_ids"][0]
            value["records"][0]["source_ids"] = [source_id, source_id]

        self.mutate_role(manifest_path, "applicability_matrix", invalidate)
        self.assert_invalid(manifest_path, "source_ids contains duplicates")

    def test_rejects_malformed_source_identifier(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["source_ids"] = ["not a stable source id"]

        self.mutate_role(manifest_path, "applicability_matrix", invalidate)
        self.assert_invalid(manifest_path, "must be a stable uppercase identifier")

    def test_rejects_legacy_singular_source_id(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["source_id"] = value["records"][0].pop(
                "source_ids"
            )[0]

        self.mutate_role(manifest_path, "applicability_matrix", invalidate)
        self.assert_invalid(manifest_path, "missing=.*source_ids")

    def test_rejects_legal_basis_backed_only_by_simulation_source(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            record = next(
                item
                for item in value["records"]
                if item["id"] == "BASIS-TOWN-AHJ-ASSUMPTION"
            )
            record["source_ids"] = ["SRC-SIMULATION-PROFILE-1.0.0"]

        self.mutate_role(manifest_path, "applicability_matrix", invalidate)
        self.assert_invalid(manifest_path, "legal or adopted-code basis lacks a legal source")

    def test_rejects_legal_basis_backed_only_by_informative_source(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            record = next(
                item
                for item in value["records"]
                if item["id"] == "BASIS-TOWN-AHJ-ASSUMPTION"
            )
            record["source_ids"] = ["SRC-AMCA-201-2023"]

        self.mutate_role(manifest_path, "applicability_matrix", invalidate)
        self.assert_invalid(manifest_path, "legal or adopted-code basis lacks a legal source")

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

    def test_rejects_wrong_flagship_facility_name(self):
        manifest_path = self.copy_package()
        manifest = self.read_json(manifest_path)
        manifest["facility"]["facility_name"] = "Northstar Data Hall"
        self.write_json(manifest_path, manifest)

        self.assert_invalid(manifest_path, "accepted flagship facility name")

    def test_rejects_cross_fixture_record(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["facility_id"] = "FACILITY-NORTHSTAR-DATA-HALL"

        self.mutate_role(manifest_path, "requirements", invalidate)
        self.assert_invalid(manifest_path, "does not match the package binding")

    def test_rejects_point_reference_outside_bound_flagship_fixture(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["point_definition_representation"] = (
                "BOUND_POINT_DEFINITIONS"
            )
            value["records"][0]["bound_point_definition_ids"] = ["UPS-A_OUTPUT_KW"]

        self.mutate_role(manifest_path, "evidence_categories", invalidate)
        self.assert_invalid(manifest_path, "outside the bound flagship fixture")

    def test_rejects_attempt_to_mark_requirement_executable(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["executable"] = True

        self.mutate_role(manifest_path, "requirements", invalidate)
        self.assert_invalid(manifest_path, "attempts to mark a requirement executable")

    def test_rejects_attempt_to_mark_accepted_requirement_active(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["activation_status"] = "ACTIVE"

        self.mutate_role(manifest_path, "requirements", invalidate)
        self.assert_invalid(manifest_path, "activation_status must remain INACTIVE")

    def test_rejects_accepted_requirement_without_owner_basis(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["applicability_basis_ids"].remove(
                "BASIS-OWNER-QUALITATIVE-SOO"
            )

        self.mutate_role(manifest_path, "requirements", invalidate)
        self.assert_invalid(
            manifest_path,
            "accepted requirement lacks the recorded qualitative SOO basis",
        )

    def test_rejects_accepted_requirement_without_owner_provenance(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["provenance"]["basis_type"] = (
                "AI_DRAFT_NOT_APPROVED"
            )

        self.mutate_role(manifest_path, "requirements", invalidate)
        self.assert_invalid(manifest_path, "lacks exact owner-decision provenance")

    def test_rejects_accepted_requirement_with_substituted_owner_reference(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["provenance"]["reference"] = "AI draft"

        self.mutate_role(manifest_path, "requirements", invalidate)
        self.assert_invalid(manifest_path, "lacks exact owner-decision provenance")

    def test_rejects_proposed_requirement_claiming_owner_provenance(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][-1]["provenance"]["basis_type"] = (
                "PROJECT_OWNER_DECISION_RECORDED"
            )

        self.mutate_role(manifest_path, "requirements", invalidate)
        self.assert_invalid(manifest_path, "claims owner provenance")

    def test_rejects_proposed_requirement_with_owner_directive_provenance(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][-1]["provenance"]["basis_type"] = (
                "PROJECT_OWNER_DIRECTIVE"
            )

        self.mutate_role(manifest_path, "requirements", invalidate)
        self.assert_invalid(manifest_path, "claims owner provenance")

    def test_rejects_proposed_requirement_claiming_owner_basis(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][-1]["applicability_basis_ids"].append(
                "BASIS-OWNER-QUALITATIVE-SOO"
            )

        self.mutate_role(manifest_path, "requirements", invalidate)
        self.assert_invalid(manifest_path, "claims an owner/project basis")

    def test_rejects_nonallowlisted_accepted_requirement(self):
        manifest_path = self.copy_package()
        manifest = self.read_json(manifest_path)
        manifest["accepted_qualitative_requirement_ids"].append("REQ-SOO-PROPOSED-011")
        self.write_json(manifest_path, manifest)

        self.assert_invalid(manifest_path, "must match the project-owner decision")

    def test_rejects_modified_recorded_profile_fact(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["statement"] = "A substituted profile fact."

        self.mutate_role(manifest_path, "applicability_profile", invalidate)
        self.assert_invalid(manifest_path, "does not match the recorded project-owner fact")

    def test_rejects_modified_recorded_profile_fact_category(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["category"] = "MATERIAL_PROFILE"

        self.mutate_role(manifest_path, "applicability_profile", invalidate)
        self.assert_invalid(manifest_path, "category does not match the recorded project-owner fact")

    def test_rejects_modified_recorded_profile_fact_provenance(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["provenance"]["basis_type"] = (
                "AI_DRAFT_NOT_APPROVED"
            )

        self.mutate_role(manifest_path, "applicability_profile", invalidate)
        self.assert_invalid(
            manifest_path,
            "provenance does not match the recorded project-owner fact",
        )

    def test_rejects_modified_owner_source_anchor(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            record = next(
                item
                for item in value["records"]
                if item["id"] == "SRC-OWNER-DIRECTIVE-2026-07-22"
            )
            record["adoption_status"] = "NOT_A_LEGAL_SOURCE"

        self.mutate_role(manifest_path, "controlled_sources", invalidate)
        self.assert_invalid(manifest_path, "does not match the recorded owner source")

    def test_rejects_modified_owner_basis_anchor(self):
        for field, replacement in (
            ("status", "PROVISIONAL_REQUIRES_VERIFICATION"),
            ("conclusion", "A substituted owner-basis conclusion."),
        ):
            with self.subTest(field=field):
                manifest_path = self.copy_package(f"owner-basis-{field}")

                def invalidate(value, field=field, replacement=replacement):
                    record = next(
                        item
                        for item in value["records"]
                        if item["id"] == "BASIS-OWNER-QUALITATIVE-SOO"
                    )
                    record[field] = replacement

                self.mutate_role(manifest_path, "applicability_matrix", invalidate)
                self.assert_invalid(
                    manifest_path,
                    "does not match the recorded qualitative SOO basis",
                )

    def test_rejects_modified_accepted_requirement_statement(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["statement"] = "A substituted requirement."

        self.mutate_role(manifest_path, "requirements", invalidate)
        self.assert_invalid(manifest_path, "does not match the recorded project-owner wording")

    def test_rejects_modified_controlled_notice(self):
        for notice_name in ("applicability", "authorship", "execution", "authority"):
            with self.subTest(notice_name=notice_name):
                manifest_path = self.copy_package(f"notice-{notice_name}")
                manifest = self.read_json(manifest_path)
                manifest["notices"][notice_name] = "A substituted controlled notice."
                self.write_json(manifest_path, manifest)

                self.assert_invalid(
                    manifest_path,
                    "must match the controlled authority notices",
                )

    def test_rejects_point_definition_representation_without_required_ids(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            record = next(
                item
                for item in value["records"]
                if item["id"] == "EVIDENCE-FAN-AVAILABILITY"
            )
            record["bound_point_definition_ids"] = []

        self.mutate_role(manifest_path, "evidence_categories", invalidate)
        self.assert_invalid(manifest_path, "requires bound identifiers")

    def test_rejects_partial_point_definition_representation_without_ids(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            record = next(
                item
                for item in value["records"]
                if item["id"] == "EVIDENCE-VFD-STATE"
            )
            record["bound_point_definition_ids"] = []

        self.mutate_role(manifest_path, "evidence_categories", invalidate)
        self.assert_invalid(manifest_path, "requires bound identifiers")

    def test_rejects_missing_point_definition_representation_with_ids(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            record = next(
                item
                for item in value["records"]
                if item["id"] == "EVIDENCE-PROCESS-PERMISSIVE"
            )
            record["bound_point_definition_ids"] = ["PROCESS-EXHAUST_AIRFLOW"]

        self.mutate_role(manifest_path, "evidence_categories", invalidate)
        self.assert_invalid(manifest_path, "requires no bound identifiers")

    def test_rejects_claimed_flagship_observation_availability(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["observation_availability"] = (
                "BASELINE_OBSERVATIONS_AVAILABLE"
            )

        self.mutate_role(manifest_path, "evidence_categories", invalidate)
        self.assert_invalid(manifest_path, "observation_availability is invalid")

    def test_rejects_numerical_criterion_payload(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["numerical_criterion"] = {"value": 1, "unit": "Pa"}

        self.mutate_role(manifest_path, "requirements", invalidate)
        self.assert_invalid(manifest_path, "unexpected=.*numerical_criterion")

    def test_rejects_manifest_path_traversal(self):
        manifest_path = self.copy_package()
        manifest = self.read_json(manifest_path)
        manifest["files"]["requirements"] = "../requirements.json"
        self.write_json(manifest_path, manifest)

        self.assert_invalid(manifest_path, "escapes the package directory")

    def test_unhashable_manifest_file_value_raises_controlled_validation_error(self):
        manifest_path = self.copy_package()
        manifest = self.read_json(manifest_path)
        manifest["files"]["requirements"] = ["requirements.json"]
        self.write_json(manifest_path, manifest)

        with self.assertRaises(StandardsBasisValidationError):
            load_standards_basis_package(manifest_path)

    def test_unhashable_enum_value_raises_controlled_validation_error(self):
        manifest_path = self.copy_package()

        def invalidate(value):
            value["records"][0]["source_category"] = ["LAW_OR_REGULATION"]

        self.mutate_role(manifest_path, "controlled_sources", invalidate)
        with self.assertRaises(StandardsBasisValidationError):
            load_standards_basis_package(manifest_path)

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

    def test_failed_semantic_reload_preserves_prior_atomic_snapshot(self):
        valid_manifest = self.copy_package("valid-semantic")
        invalid_manifest = self.copy_package("invalid-semantic")
        store = StandardsBasisStore(valid_manifest)
        original = store.load()

        def invalidate(value):
            value["records"][2]["source_ids"] = ["SRC-SIMULATION-PROFILE-1.0.0"]

        self.mutate_role(invalid_manifest, "applicability_matrix", invalidate)
        with self.assertRaises(StandardsBasisValidationError):
            store.load(invalid_manifest)

        self.assertEqual(store.get(), original)


class StandardsBasisApiTests(StandardsBasisPackageTestCase):
    def test_consolidated_route_returns_one_complete_flagship_snapshot(self):
        status, payload = get_json_from_asgi_app(backend_main.app, "/standards-basis")

        self.assertEqual(status, 200)
        self.assertEqual(payload["facility_id"], FLAGSHIP_FACILITY_ID)
        self.assertEqual(payload["facility_fixture_version"], "1.0.0")
        self.assertEqual(payload["status"], "READ_ONLY_NON_EXECUTABLE")
        self.assertEqual(len(payload["applicability_profile"]), 18)
        self.assertEqual(len(payload["controlled_sources"]), 35)
        self.assertEqual(len(payload["applicability_matrix"]), 29)
        self.assertEqual(len(payload["evidence_categories"]), 19)
        self.assertEqual(len(payload["requirements"]), 12)
        self.assertEqual(len(payload["traceability"]), 12)
        self.assertIn("provisional", payload["notices"]["applicability"])
        self.assertIn("non-executable", payload["notices"]["execution"])
        self.assertIn(
            "assigned organizational or legal authority",
            payload["notices"]["authority"],
        )

    def test_leaf_routes_are_read_only_and_repeat_facility_binding(self):
        routes = {
            "/standards-basis/profile": "applicability_profile",
            "/standards-basis/controlled-sources": "controlled_sources",
            "/standards-basis/applicability-matrix": "applicability_matrix",
            "/standards-basis/requirements": "requirements",
            "/standards-basis/evidence-categories": "evidence_categories",
            "/standards-basis/traceability": "traceability",
        }

        for path, response_key in routes.items():
            with self.subTest(path=path):
                status, payload = get_json_from_asgi_app(backend_main.app, path)
                self.assertEqual(status, 200)
                self.assertEqual(payload["facility_id"], FLAGSHIP_FACILITY_ID)
                self.assertEqual(payload["facility_fixture_version"], "1.0.0")
                self.assertTrue(payload[response_key])

                method_status, _method_payload = get_json_from_asgi_app(
                    backend_main.app,
                    path,
                    method="POST",
                )
                self.assertEqual(method_status, 405)

    def test_routes_do_not_depend_on_or_mutate_active_sqlite_database(self):
        database_path = self.temp_root / "northstar-sentinel.sqlite3"
        original = b"northstar database sentinel"
        database_path.write_bytes(original)

        with mock.patch.object(backend_main, "DATABASE_FILE", database_path):
            status, payload = get_json_from_asgi_app(
                backend_main.app,
                "/standards-basis",
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["facility_id"], FLAGSHIP_FACILITY_ID)
        self.assertEqual(database_path.read_bytes(), original)

    def test_consolidated_route_is_deterministic(self):
        first_status, first_payload = get_json_from_asgi_app(
            backend_main.app,
            "/standards-basis",
        )
        second_status, second_payload = get_json_from_asgi_app(
            backend_main.app,
            "/standards-basis",
        )

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertEqual(first_payload, second_payload)

    def test_workbench_presents_flagship_basis_as_separate_read_only_review(self):
        html = backend_main.FRONTEND_FILE.read_text(encoding="utf-8")

        self.assertIn("Flagship Applicability and Requirement Basis", html)
        self.assertIn("Provisional applicability matrix", html)
        self.assertIn("Project-authored synthetic requirements — INACTIVE / NON-EXECUTABLE", html)
        self.assertIn("Visible source-to-evidence traceability", html)
        self.assertIn("Point-definition representation", html)
        self.assertIn("Observation availability", html)
        self.assertIn("the flagship fixture\n        declares no observation baseline", html)
        self.assertIn("chain.requirement.provenance_reference", html)
        self.assertIn("Structurally validated read-only package loaded", html)
        self.assertIn('fetch("/standards-basis")', html)
        self.assertIn("loadStandardsBasis();", html)
        self.assertIn("loadWorkbench();", html)
        self.assertIn("This package is\n        separate from the active SQLite facility", html)


if __name__ == "__main__":
    unittest.main()
