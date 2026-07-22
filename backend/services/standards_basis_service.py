import copy
import json
import re
import threading
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STANDARDS_BASIS_MANIFEST = (
    PROJECT_ROOT / "data" / "standards" / "flagship" / "1.0.0" / "manifest.json"
)
FLAGSHIP_FACILITY_ID = "FACILITY-ADVANCED-MATERIALS-RESEARCH"
FLAGSHIP_FIXTURE_VERSION = "1.0.0"

EXPECTED_FILE_ROLES = {
    "applicability_profile",
    "controlled_sources",
    "applicability_matrix",
    "evidence_categories",
    "requirements",
}

PROFILE_FACT_CATEGORIES = {
    "FACILITY_CONTEXT",
    "JURISDICTION_ASSUMPTION",
    "USE_AND_OCCUPANCY_ASSUMPTION",
    "MATERIAL_PROFILE",
    "SIMULATION_INVENTORY_BOUND",
    "SCOPE_EXCLUSION",
    "OWNER_PROJECT_DESIGN_INTENT",
    "EXTERNAL_CONTROL_BOUNDARY",
}
SOURCE_CATEGORIES = {
    "LAW_OR_REGULATION",
    "ADOPTED_CODE",
    "LOCAL_GOVERNMENT_SOURCE",
    "FORMAL_STANDARD",
    "INFORMATIVE_ENGINEERING_GUIDANCE",
    "RESEARCH_SPECIFICATION",
    "PROPOSED_STANDARD",
    "OWNER_PROJECT_DECISION",
    "SIMULATION_ASSUMPTION",
}
SOURCE_DATE_STATUSES = {"VERIFIED", "NOT_STATED", "CONTINUOUS_MAINTENANCE"}
SOURCE_ADOPTION_STATUSES = {
    "ADOPTED_BY_NEW_YORK_STATE",
    "FEDERAL_REGULATION",
    "LOCAL_ADMINISTRATIVE_SOURCE",
    "NOT_ESTABLISHED_FOR_FLAGSHIP",
    "NOT_A_LEGAL_SOURCE",
    "PROJECT_OWNER_APPROVED",
}
SOURCE_ENFORCEMENT_STATUSES = {
    "GENERALLY_IN_FORCE_SUBJECT_TO_SCOPE",
    "CONDITIONAL_ON_REGULATORY_SCOPE",
    "LOCAL_ROLE_REQUIRES_SITE_VERIFICATION",
    "NOT_ESTABLISHED_FOR_FLAGSHIP",
    "NOT_ENFORCEABLE_AS_LAW_BY_ITSELF",
    "PROJECT_ONLY",
}
SOURCE_ACCESS_STATUSES = {
    "OFFICIAL_PUBLIC_FULL_TEXT",
    "OFFICIAL_PUBLIC_METADATA",
    "AUTHORITATIVE_PUBLIC_PROJECT_SOURCE",
    "PAID_OR_LICENSED_TEXT_REQUIRED",
    "PROJECT_RECORD",
}
APPLICABILITY_STATUSES = {
    "PROVISIONAL_REQUIRES_VERIFICATION",
    "INFORMATIVE_INFLUENCE_ONLY",
    "NOT_TRIGGERED_BY_CURRENT_PROFILE",
    "OWNER_PROJECT_BASIS",
    "SIMULATION_ASSUMPTION",
}
BASIS_CATEGORIES = {
    "LEGAL_OR_REGULATORY",
    "ADOPTED_CODE",
    "OWNER_PROJECT_REQUIREMENT",
    "INFORMATIVE_ENGINEERING_GUIDANCE",
    "RESEARCH_METHOD",
    "PURE_SIMULATION_ASSUMPTION",
}
EVIDENCE_IMPLEMENTATION_STATUSES = {
    "AVAILABLE_IN_FLAGSHIP_TOPOLOGY",
    "PARTIALLY_AVAILABLE_IN_FLAGSHIP_TOPOLOGY",
    "MISSING_REQUIRES_FUTURE_DECISION",
    "FUTURE_RECORD_SET",
}
REQUIREMENT_LIFECYCLE_STATUSES = {"ACCEPTED_FOR_SIMULATION", "DRAFT"}
REQUIREMENT_APPROVAL_STATUSES = {"PROJECT_OWNER_DECISION_RECORDED", "PROPOSED"}

APPROVED_QUALITATIVE_REQUIREMENTS = {
    "REQ-SOO-001": (
        "The external control system may enable the scoped process only when the "
        "treatment path, process-exhaust capability, supply/makeup-air dependency, "
        "and required pressure-control evidence are available."
    ),
    "REQ-SOO-002": (
        "When the process is enabled, the external control system requests operation "
        "of the selected duty fan. FacilityOps observes the request but does not issue it."
    ),
    "REQ-SOO-003": (
        "A fan command or request does not establish fan operation. Future fan-operation "
        "inference must distinguish controller request, VFD indication, motor/electrical "
        "response, and delivered airflow."
    ),
    "REQ-SOO-004": (
        "VFD feedback and motor/electrical response are separate evidence categories. "
        "Their provenance must determine whether they constitute independent corroboration."
    ),
    "REQ-SOO-005": (
        "Process-containment inference additionally requires differential-pressure "
        "evidence supporting the intended corridor-to-airlock-to-laboratory pressure direction."
    ),
    "REQ-SOO-006": (
        "If supported duty-fan performance is lost, the external control system removes "
        "or withholds the process permissive and requests the standby fan. A standby "
        "request alone does not establish successful changeover."
    ),
    "REQ-SOO-007": (
        "A standby fan cannot compensate for loss of the shared exhaust path, treatment "
        "availability, or another required common dependency."
    ),
    "REQ-SOO-008": (
        "Loss of treatment availability or required makeup-air capability removes or "
        "withholds the process permissive. Exact safe-mode fan behavior remains unresolved."
    ),
    "REQ-SOO-009": (
        "Missing, stale, suspect, overridden, late, duplicated, or conflicting required "
        "evidence must be capable of preventing a supported conclusion."
    ),
    "REQ-SOO-010": (
        "Recovery requires new post-action observations and a separate recovery evaluation. "
        "Alarm acknowledgment, reset, command completion, or return-to-normal indication "
        "alone does not establish recovery."
    ),
}

IDENTIFIER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._-]*$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class StandardsBasisValidationError(ValueError):
    """Raised when a standards-basis package is incomplete or inconsistent."""


def _fail(message):
    raise StandardsBasisValidationError(message)


def _require(condition, message):
    if not condition:
        _fail(message)


def _require_exact_keys(value, expected_keys, context):
    _require(isinstance(value, dict), f"{context} must be an object")
    actual_keys = set(value)
    expected_keys = set(expected_keys)
    missing = sorted(expected_keys - actual_keys)
    unexpected = sorted(actual_keys - expected_keys)
    _require(
        not missing and not unexpected,
        f"{context} keys invalid; missing={missing}, unexpected={unexpected}",
    )


def _require_nonblank(value, context):
    _require(isinstance(value, str) and value.strip(), f"{context} must be nonblank")


def _require_identifier(value, context):
    _require_nonblank(value, context)
    _require(
        IDENTIFIER_PATTERN.fullmatch(value) is not None,
        f"{context} must be a stable uppercase identifier",
    )


def _require_date(value, context):
    _require(
        isinstance(value, str) and DATE_PATTERN.fullmatch(value) is not None,
        f"{context} must use YYYY-MM-DD",
    )


def _require_string_list(value, context, allow_empty=False):
    _require(isinstance(value, list), f"{context} must be a list")
    if not allow_empty:
        _require(value, f"{context} must not be empty")
    for index, item in enumerate(value):
        _require_nonblank(item, f"{context}[{index}]")
    _require(len(value) == len(set(value)), f"{context} contains duplicates")


def _require_provenance(value, context):
    _require_exact_keys(
        value,
        {"basis_type", "reference", "recorded_on"},
        context,
    )
    _require_nonblank(value["basis_type"], f"{context}.basis_type")
    _require_nonblank(value["reference"], f"{context}.reference")
    _require_date(value["recorded_on"], f"{context}.recorded_on")


def _read_json(path, context):
    try:
        with path.open(encoding="utf-8") as file:
            value = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        _fail(f"Unable to read {context} at {path}: {error}")
    return value


def _resolve_package_file(package_root, relative_path, role):
    _require_nonblank(relative_path, f"manifest.files.{role}")
    candidate = (package_root / relative_path).resolve()
    _require(
        candidate == package_root or package_root in candidate.parents,
        f"manifest.files.{role} escapes the package directory",
    )
    _require(candidate.is_file(), f"manifest.files.{role} does not exist: {candidate}")
    return candidate


def _validate_manifest(manifest):
    _require_exact_keys(
        manifest,
        {
            "schema_version",
            "package_type",
            "package_id",
            "package_version",
            "status",
            "facility",
            "files",
            "accepted_qualitative_requirement_ids",
            "notices",
            "provenance",
        },
        "manifest",
    )
    _require(manifest["schema_version"] == 1, "manifest.schema_version must be 1")
    _require(
        manifest["package_type"] == "flagship_standards_requirement_basis",
        "manifest.package_type is invalid",
    )
    _require_identifier(manifest["package_id"], "manifest.package_id")
    _require_nonblank(manifest["package_version"], "manifest.package_version")
    _require(
        manifest["status"] == "READ_ONLY_NON_EXECUTABLE",
        "manifest.status must be READ_ONLY_NON_EXECUTABLE",
    )

    _require_exact_keys(
        manifest["facility"],
        {"facility_id", "facility_name", "fixture_version"},
        "manifest.facility",
    )
    _require(
        manifest["facility"]["facility_id"] == FLAGSHIP_FACILITY_ID,
        "standards basis must bind to the flagship facility",
    )
    _require_nonblank(manifest["facility"]["facility_name"], "manifest.facility.facility_name")
    _require(
        manifest["facility"]["fixture_version"] == FLAGSHIP_FIXTURE_VERSION,
        "standards basis must bind to flagship fixture version 1.0.0",
    )

    _require_exact_keys(manifest["files"], EXPECTED_FILE_ROLES, "manifest.files")
    _require(
        len(set(manifest["files"].values())) == len(EXPECTED_FILE_ROLES),
        "manifest.files must use one distinct file per role",
    )
    _require_string_list(
        manifest["accepted_qualitative_requirement_ids"],
        "manifest.accepted_qualitative_requirement_ids",
    )
    _require(
        set(manifest["accepted_qualitative_requirement_ids"])
        == set(APPROVED_QUALITATIVE_REQUIREMENTS),
        "manifest.accepted_qualitative_requirement_ids must match the project-owner decision",
    )

    _require_exact_keys(
        manifest["notices"],
        {
            "applicability",
            "authorship",
            "execution",
            "authority",
        },
        "manifest.notices",
    )
    for key, value in manifest["notices"].items():
        _require_nonblank(value, f"manifest.notices.{key}")

    _require_exact_keys(
        manifest["provenance"],
        {"recorded_on", "owner_approval_reference", "research_access_date"},
        "manifest.provenance",
    )
    _require_date(manifest["provenance"]["recorded_on"], "manifest.provenance.recorded_on")
    _require_nonblank(
        manifest["provenance"]["owner_approval_reference"],
        "manifest.provenance.owner_approval_reference",
    )
    _require_date(
        manifest["provenance"]["research_access_date"],
        "manifest.provenance.research_access_date",
    )


def _validate_document_header(document, manifest, role):
    _require_exact_keys(
        document,
        {
            "schema_version",
            "package_id",
            "facility_id",
            "facility_fixture_version",
            "records",
        },
        role,
    )
    _require(document["schema_version"] == 1, f"{role}.schema_version must be 1")
    _require(
        document["package_id"] == manifest["package_id"],
        f"{role}.package_id does not match the manifest",
    )
    _require(
        document["facility_id"] == manifest["facility"]["facility_id"],
        f"{role}.facility_id does not match the manifest",
    )
    _require(
        document["facility_fixture_version"]
        == manifest["facility"]["fixture_version"],
        f"{role}.facility_fixture_version does not match the manifest",
    )
    _require(isinstance(document["records"], list), f"{role}.records must be a list")


def _index_records(records, role):
    index = {}
    for position, record in enumerate(records):
        context = f"{role}.records[{position}]"
        _require(isinstance(record, dict), f"{context} must be an object")
        _require_identifier(record.get("id"), f"{context}.id")
        _require(record["id"] not in index, f"Duplicate identifier: {record['id']}")
        index[record["id"]] = record
    return index


def _validate_record_facility(record, facility_id, context):
    _require(
        record["facility_id"] == facility_id,
        f"{context}.facility_id does not match the package binding",
    )


def _validate_profile(records, facility_id):
    expected_keys = {
        "id",
        "facility_id",
        "category",
        "status",
        "statement",
        "limitations",
        "provenance",
    }
    for record in records:
        context = f"applicability_profile.{record['id']}"
        _require_exact_keys(record, expected_keys, context)
        _validate_record_facility(record, facility_id, context)
        _require(record["category"] in PROFILE_FACT_CATEGORIES, f"{context}.category is invalid")
        _require(
            record["status"] == "OWNER_APPROVED_FICTIONAL_ASSUMPTION",
            f"{context}.status is invalid",
        )
        _require_nonblank(record["statement"], f"{context}.statement")
        _require_nonblank(record["limitations"], f"{context}.limitations")
        _require_provenance(record["provenance"], f"{context}.provenance")


def _validate_sources(records, facility_id, profile_fact_ids):
    expected_keys = {
        "id",
        "facility_id",
        "issuer",
        "title",
        "identifier",
        "edition_or_effective_date",
        "date_status",
        "source_category",
        "official_url",
        "repository_reference",
        "accessed_on",
        "adoption_status",
        "enforcement_status",
        "potential_applicability_trigger",
        "profile_fact_ids",
        "direct_support",
        "uncertainty",
        "access_status",
        "provenance",
    }
    for record in records:
        context = f"controlled_sources.{record['id']}"
        _require_exact_keys(record, expected_keys, context)
        _validate_record_facility(record, facility_id, context)
        for key in (
            "issuer",
            "title",
            "identifier",
            "edition_or_effective_date",
            "potential_applicability_trigger",
            "direct_support",
            "uncertainty",
        ):
            _require_nonblank(record[key], f"{context}.{key}")
        _require(record["date_status"] in SOURCE_DATE_STATUSES, f"{context}.date_status is invalid")
        _require(record["source_category"] in SOURCE_CATEGORIES, f"{context}.source_category is invalid")
        _require(record["adoption_status"] in SOURCE_ADOPTION_STATUSES, f"{context}.adoption_status is invalid")
        _require(record["enforcement_status"] in SOURCE_ENFORCEMENT_STATUSES, f"{context}.enforcement_status is invalid")
        _require(record["access_status"] in SOURCE_ACCESS_STATUSES, f"{context}.access_status is invalid")
        _require_date(record["accessed_on"], f"{context}.accessed_on")
        official_url = record["official_url"]
        repository_reference = record["repository_reference"]
        _require(
            official_url is not None or repository_reference is not None,
            f"{context} must provide an official URL or repository reference",
        )
        if official_url is not None:
            _require(
                isinstance(official_url, str) and official_url.startswith("https://"),
                f"{context}.official_url must be an HTTPS URL",
            )
        if repository_reference is not None:
            _require_nonblank(repository_reference, f"{context}.repository_reference")
        _require_string_list(
            record["profile_fact_ids"],
            f"{context}.profile_fact_ids",
            allow_empty=True,
        )
        missing_facts = sorted(set(record["profile_fact_ids"]) - profile_fact_ids)
        _require(not missing_facts, f"{context} references unknown profile facts: {missing_facts}")
        _require_provenance(record["provenance"], f"{context}.provenance")


def _validate_applicability(records, facility_id, source_ids, profile_fact_ids):
    expected_keys = {
        "id",
        "facility_id",
        "source_id",
        "status",
        "basis_category",
        "trigger",
        "profile_fact_ids",
        "conclusion",
        "uncertainty",
        "future_verification",
        "provenance",
    }
    for record in records:
        context = f"applicability_matrix.{record['id']}"
        _require_exact_keys(record, expected_keys, context)
        _validate_record_facility(record, facility_id, context)
        _require(record["source_id"] in source_ids, f"{context}.source_id is unresolved")
        _require(record["status"] in APPLICABILITY_STATUSES, f"{context}.status is invalid")
        _require(record["basis_category"] in BASIS_CATEGORIES, f"{context}.basis_category is invalid")
        for key in ("trigger", "conclusion", "uncertainty", "future_verification"):
            _require_nonblank(record[key], f"{context}.{key}")
        _require_string_list(record["profile_fact_ids"], f"{context}.profile_fact_ids")
        missing_facts = sorted(set(record["profile_fact_ids"]) - profile_fact_ids)
        _require(not missing_facts, f"{context} references unknown profile facts: {missing_facts}")
        _require_provenance(record["provenance"], f"{context}.provenance")


def _validate_evidence_categories(records, facility_id):
    expected_keys = {
        "id",
        "facility_id",
        "label",
        "evidence_kind",
        "status",
        "implementation_status",
        "current_point_ids",
        "description",
        "provenance_consideration",
        "limitations",
        "provenance",
    }
    for record in records:
        context = f"evidence_categories.{record['id']}"
        _require_exact_keys(record, expected_keys, context)
        _validate_record_facility(record, facility_id, context)
        for key in (
            "label",
            "evidence_kind",
            "description",
            "provenance_consideration",
            "limitations",
        ):
            _require_nonblank(record[key], f"{context}.{key}")
        _require(
            record["status"] == "DEFINED_FOR_NON_EXECUTABLE_TRACEABILITY",
            f"{context}.status is invalid",
        )
        _require(
            record["implementation_status"] in EVIDENCE_IMPLEMENTATION_STATUSES,
            f"{context}.implementation_status is invalid",
        )
        _require_string_list(
            record["current_point_ids"],
            f"{context}.current_point_ids",
            allow_empty=True,
        )
        _require_provenance(record["provenance"], f"{context}.provenance")


def _validate_requirements(
    records,
    facility_id,
    approved_requirement_ids,
    applicability_ids,
    evidence_category_ids,
):
    expected_keys = {
        "id",
        "facility_id",
        "ordinal",
        "title",
        "version",
        "statement",
        "requirement_type",
        "lifecycle_status",
        "approval_status",
        "activation_status",
        "parameter_status",
        "executable",
        "applicability_basis_ids",
        "evidence_category_ids",
        "rationale",
        "assumptions",
        "limitations",
        "provenance",
    }
    accepted_ids = set()
    ordinals = set()
    for record in records:
        context = f"requirements.{record['id']}"
        _require_exact_keys(record, expected_keys, context)
        _validate_record_facility(record, facility_id, context)
        _require(
            isinstance(record["ordinal"], int) and record["ordinal"] > 0,
            f"{context}.ordinal must be a positive integer",
        )
        _require(record["ordinal"] not in ordinals, f"Duplicate requirement ordinal: {record['ordinal']}")
        ordinals.add(record["ordinal"])
        _require_nonblank(record["title"], f"{context}.title")
        _require_nonblank(record["version"], f"{context}.version")
        _require_nonblank(record["statement"], f"{context}.statement")
        _require(
            record["requirement_type"] == "PROJECT_AUTHORED_SYNTHETIC_SOO",
            f"{context}.requirement_type is invalid",
        )
        _require(
            record["lifecycle_status"] in REQUIREMENT_LIFECYCLE_STATUSES,
            f"{context}.lifecycle_status is invalid",
        )
        _require(
            record["approval_status"] in REQUIREMENT_APPROVAL_STATUSES,
            f"{context}.approval_status is invalid",
        )
        _require(
            record["activation_status"] == "INACTIVE",
            f"{context}.activation_status must remain INACTIVE",
        )
        _require(
            record["parameter_status"] == "NO_NUMERICAL_CRITERIA_APPROVED",
            f"{context}.parameter_status is invalid",
        )
        _require(
            record["executable"] is False,
            f"{context} attempts to mark a requirement executable",
        )
        if record["approval_status"] == "PROJECT_OWNER_DECISION_RECORDED":
            _require(
                record["lifecycle_status"] == "ACCEPTED_FOR_SIMULATION",
                f"{context} has an invalid approved status combination",
            )
            _require(
                APPROVED_QUALITATIVE_REQUIREMENTS.get(record["id"])
                == record["statement"],
                f"{context} does not match the recorded project-owner wording",
            )
            accepted_ids.add(record["id"])
        else:
            _require(
                record["lifecycle_status"] == "DRAFT",
                f"{context} has an invalid proposed status combination",
            )
        _require_string_list(
            record["applicability_basis_ids"],
            f"{context}.applicability_basis_ids",
        )
        _require_string_list(
            record["evidence_category_ids"],
            f"{context}.evidence_category_ids",
        )
        _require_nonblank(record["rationale"], f"{context}.rationale")
        missing_basis = sorted(set(record["applicability_basis_ids"]) - applicability_ids)
        missing_evidence = sorted(set(record["evidence_category_ids"]) - evidence_category_ids)
        _require(not missing_basis, f"{context} references unknown applicability bases: {missing_basis}")
        _require(not missing_evidence, f"{context} references unknown evidence categories: {missing_evidence}")
        _require_string_list(record["assumptions"], f"{context}.assumptions", allow_empty=True)
        _require_string_list(record["limitations"], f"{context}.limitations")
        _require_provenance(record["provenance"], f"{context}.provenance")
        for text in (
            record["statement"],
            record["rationale"],
            *record["assumptions"],
            *record["limitations"],
        ):
            _require(
                re.search(r"\d", text) is None,
                f"{context} contains an unapproved numerical criterion",
            )

    _require(
        accepted_ids == set(approved_requirement_ids),
        "manifest accepted requirement IDs must exactly match recorded qualitative requirements",
    )


def load_standards_basis_package(manifest_path=DEFAULT_STANDARDS_BASIS_MANIFEST):
    """Read and completely validate a standards-basis package without side effects."""
    manifest_path = Path(manifest_path).resolve()
    manifest = _read_json(manifest_path, "standards-basis manifest")
    _validate_manifest(manifest)

    package_root = manifest_path.parent.resolve()
    documents = {}
    for role in sorted(EXPECTED_FILE_ROLES):
        document_path = _resolve_package_file(package_root, manifest["files"][role], role)
        document = _read_json(document_path, role)
        _validate_document_header(document, manifest, role)
        documents[role] = document

    indexes = {
        role: _index_records(document["records"], role)
        for role, document in documents.items()
    }
    facility_id = manifest["facility"]["facility_id"]
    profile_fact_ids = set(indexes["applicability_profile"])
    source_ids = set(indexes["controlled_sources"])
    applicability_ids = set(indexes["applicability_matrix"])
    evidence_category_ids = set(indexes["evidence_categories"])

    _validate_profile(documents["applicability_profile"]["records"], facility_id)
    _validate_sources(
        documents["controlled_sources"]["records"],
        facility_id,
        profile_fact_ids,
    )
    _validate_applicability(
        documents["applicability_matrix"]["records"],
        facility_id,
        source_ids,
        profile_fact_ids,
    )
    _validate_evidence_categories(
        documents["evidence_categories"]["records"],
        facility_id,
    )
    _validate_requirements(
        documents["requirements"]["records"],
        facility_id,
        manifest["accepted_qualitative_requirement_ids"],
        applicability_ids,
        evidence_category_ids,
    )

    return {
        "manifest": manifest,
        "manifest_path": str(manifest_path),
        "applicability_profile": documents["applicability_profile"]["records"],
        "controlled_sources": documents["controlled_sources"]["records"],
        "applicability_matrix": documents["applicability_matrix"]["records"],
        "evidence_categories": documents["evidence_categories"]["records"],
        "requirements": sorted(
            documents["requirements"]["records"],
            key=lambda record: record["ordinal"],
        ),
    }


class StandardsBasisStore:
    """Atomically exposes only a completely validated in-memory package."""

    def __init__(self, manifest_path=DEFAULT_STANDARDS_BASIS_MANIFEST):
        self._manifest_path = Path(manifest_path).resolve()
        self._package = None
        self._lock = threading.RLock()

    def load(self, manifest_path=None):
        candidate_path = (
            Path(manifest_path).resolve()
            if manifest_path is not None
            else self._manifest_path
        )
        candidate = load_standards_basis_package(candidate_path)
        with self._lock:
            self._package = candidate
            self._manifest_path = candidate_path
            return copy.deepcopy(self._package)

    def get(self):
        with self._lock:
            package = self._package
        if package is None:
            return self.load()
        return copy.deepcopy(package)


DEFAULT_STANDARDS_BASIS_STORE = StandardsBasisStore()


def _package_metadata(package):
    manifest = package["manifest"]
    return {
        "package_id": manifest["package_id"],
        "package_version": manifest["package_version"],
        "status": manifest["status"],
        "facility_id": manifest["facility"]["facility_id"],
        "facility_name": manifest["facility"]["facility_name"],
        "facility_fixture_version": manifest["facility"]["fixture_version"],
        "notices": manifest["notices"],
        "provenance": manifest["provenance"],
    }


def get_standards_basis_summary(store=DEFAULT_STANDARDS_BASIS_STORE):
    package = store.get()
    result = _package_metadata(package)
    result["record_counts"] = {
        role: len(package[role])
        for role in (
            "applicability_profile",
            "controlled_sources",
            "applicability_matrix",
            "evidence_categories",
            "requirements",
        )
    }
    return result


def _section_response(section, store):
    package = store.get()
    result = _package_metadata(package)
    result[section] = package[section]
    return result


def get_applicability_profile(store=DEFAULT_STANDARDS_BASIS_STORE):
    return _section_response("applicability_profile", store)


def get_controlled_sources(store=DEFAULT_STANDARDS_BASIS_STORE):
    return _section_response("controlled_sources", store)


def get_applicability_matrix(store=DEFAULT_STANDARDS_BASIS_STORE):
    return _section_response("applicability_matrix", store)


def get_evidence_categories(store=DEFAULT_STANDARDS_BASIS_STORE):
    return _section_response("evidence_categories", store)


def get_synthetic_requirements(store=DEFAULT_STANDARDS_BASIS_STORE):
    return _section_response("requirements", store)


def get_standards_traceability(store=DEFAULT_STANDARDS_BASIS_STORE):
    package = store.get()
    sources = {record["id"]: record for record in package["controlled_sources"]}
    applicability = {
        record["id"]: record for record in package["applicability_matrix"]
    }
    evidence = {record["id"]: record for record in package["evidence_categories"]}
    chains = []
    for requirement in package["requirements"]:
        bases = [
            applicability[basis_id]
            for basis_id in requirement["applicability_basis_ids"]
        ]
        chains.append(
            {
                "requirement": requirement,
                "applicability_bases": bases,
                "controlled_sources": [
                    sources[basis["source_id"]]
                    for basis in bases
                ],
                "required_evidence_categories": [
                    evidence[evidence_id]
                    for evidence_id in requirement["evidence_category_ids"]
                ],
            }
        )

    result = _package_metadata(package)
    result["traceability"] = chains
    return result
