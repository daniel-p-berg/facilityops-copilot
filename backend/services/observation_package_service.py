"""Validation and allowlisting for repository synthetic observation packages."""

from __future__ import annotations

import csv
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from backend.domain.observation_semantics import (
    canonical_json_sha256,
    canonical_json_text,
    parse_rfc3339_timestamp,
)
from backend.services.facility_package_registry import (
    FLAGSHIP_FACILITY_ID,
    FLAGSHIP_OBSERVATION_MANIFEST,
    FLAGSHIP_TOPOLOGY_ID,
    FLAGSHIP_TOPOLOGY_VERSION,
    facility_package_content_digest,
    read_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANONICALIZER_VERSION = "facilityops-canonicalizer/1.0.0"

MAPPING_PACKAGE_ID = "MAPPING-PACKAGE-FLAGSHIP-SYNTHETIC-INDICATIONS"
MAPPING_PACKAGE_VERSION = "1.0.0"
MAPPING_PACKAGE_MANIFEST = (
    PROJECT_ROOT
    / "data"
    / "observation_mappings"
    / "flagship-synthetic-indications"
    / MAPPING_PACKAGE_VERSION
    / "manifest.json"
)

FLAGSHIP_REPLAY_PACKAGE_ID = "flagship-process-exhaust-evidence-sequence"
FLAGSHIP_REPLAY_PACKAGE_VERSION = "1.0.0"
FLAGSHIP_REPLAY_MANIFEST = (
    PROJECT_ROOT
    / "data"
    / "observation_replays"
    / FLAGSHIP_REPLAY_PACKAGE_ID
    / FLAGSHIP_REPLAY_PACKAGE_VERSION
    / "manifest.json"
)

REGISTERED_MAPPING_PACKAGES = {
    (MAPPING_PACKAGE_ID, MAPPING_PACKAGE_VERSION): MAPPING_PACKAGE_MANIFEST,
}
REGISTERED_REPLAY_PACKAGES = {
    (
        FLAGSHIP_FACILITY_ID,
        FLAGSHIP_REPLAY_PACKAGE_ID,
        FLAGSHIP_REPLAY_PACKAGE_VERSION,
    ): FLAGSHIP_REPLAY_MANIFEST,
}

MAX_PACKAGE_FILE_BYTES = 1_000_000
MAX_REPOSITORY_PACKAGE_BYTES = 4_000_000
MAX_DELIVERIES = 500
MAX_SOURCE_PAYLOAD_BYTES = 65_536
MAX_TEXT_LENGTH = 16_384

_SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")

_EXPECTED_MAPPING_FILES = {
    "source_bindings": "source_bindings.json",
    "mappings": "mappings.json",
}
_EXPECTED_REPLAY_FILES = {
    "narrative": "narrative.json",
    "deliveries": "deliveries.json",
    "oracle": "oracle.json",
}
_ALLOWED_VALUE_TYPES = {"BOOLEAN", "INTEGER", "DECIMAL", "TEXT", "ENUM"}
_ALLOWED_FIELD_NORMALIZATIONS = {
    "STRICT_BOOLEAN",
    "DIRECT_ENUM",
    "DECIMAL",
    "DECIMAL_SCALE",
    "UNIT_CONVERSION",
}
_PROHIBITED_PACKAGE_KEYS = {
    "independent",
    "evidence_sufficient",
    "authorized",
    "code_compliant",
    "commissioning_accepted",
}
_REQUIRED_DEPENDENCY_PROVENANCE_FIELDS = {
    "controller_logic_origin",
    "source_device_origin",
    "gateway_origin",
    "measurement_chain_origin",
    "power_origin",
    "timestamp_origin",
    "derivation_origin",
}
_RECEIVED_INDICATION_EVENT_PATTERN = re.compile(
    r"^E\d{3}-[A-Z0-9-]+-INDICATIONS?-RECEIVED$"
)
_APPROVED_REPLAY_OBSERVATION_EVENT_IDS = {
    "E010-BASELINE-DEPENDENCY-INDICATIONS-RECEIVED",
    "E020-BASELINE-PERMISSIVE-INDICATION-RECEIVED",
    "E025-PROCESS-ENABLED-INDICATION-RECEIVED",
    "E030-DUTY-REQUEST-INDICATION-RECEIVED",
    "E040-DUTY-EXECUTION-INDICATION-RECEIVED",
    "E050-DUTY-DEVICE-INDICATIONS-RECEIVED",
    "E060-BASELINE-PROCESS-INDICATIONS-RECEIVED",
    "E100-DUTY-INDICATIONS-RECEIVED",
    "E110-AIRFLOW-AND-PATH-INDICATIONS-RECEIVED",
    "E120-PROCESS-PERMISSIVE-INDICATION-RECEIVED",
    "E130-STANDBY-REQUEST-INDICATION-RECEIVED",
    "E140-STANDBY-EXECUTION-INDICATION-RECEIVED",
    "E150-STANDBY-DEVICE-INDICATIONS-RECEIVED",
    "E160-SHARED-AIRFLOW-AND-PATH-INDICATIONS-RECEIVED",
    "E170-PRESSURE-INDICATIONS-RECEIVED",
    "E190-POST-ACTION-DEPENDENCY-INDICATIONS-RECEIVED",
    "E200-POST-ACTION-FAN-INDICATIONS-RECEIVED",
    "E210-POST-ACTION-PROCESS-INDICATIONS-RECEIVED",
    "E220-PROCESS-PERMISSIVE-INDICATION-RECEIVED",
}
_PROHIBITED_OUTCOME_PHRASES = (
    "fan failed",
    "fan failure",
    "fan operating",
    "standby succeeded",
    "successful changeover",
    "airflow sufficient",
    "containment maintained",
    "containment lost",
    "pressure cascade adequate",
    "cascade restored",
    "facility safe",
    "recovery verified",
    "recovery evaluation requested",
    "recovery finding computed",
    "authorized action",
    "code compliant",
    "commissioning accepted",
)


class ObservationPackageValidationError(ValueError):
    """Raised when a registered package violates the approved package contract."""


def package_content_digest(
    manifest: dict[str, Any],
    files: dict[str, Any],
) -> str:
    """Digest parsed package content without the self-referential digest field."""

    unsigned_manifest = deepcopy(manifest)
    unsigned_manifest.pop("content_digest", None)
    return canonical_json_sha256(
        {
            "manifest": unsigned_manifest,
            "files": {role: files[role] for role in sorted(files)},
        }
    )


def mapping_definition_digest(mapping: dict[str, Any]) -> str:
    """Digest one mapping definition without its self-referential digest."""

    unsigned_mapping = deepcopy(mapping)
    unsigned_mapping.pop("content_digest", None)
    return canonical_json_sha256(unsigned_mapping)


def source_binding_definition_digest(binding: dict[str, Any]) -> str:
    """Digest one source-binding definition without its self digest."""

    unsigned_binding = deepcopy(binding)
    unsigned_binding.pop("content_digest", None)
    return canonical_json_sha256(unsigned_binding)


def list_replay_packages(facility_id: str) -> dict[str, Any]:
    """Return validated allowlisted packages for one exact facility."""

    packages = []
    for registered_facility_id, package_id, package_version in sorted(
        REGISTERED_REPLAY_PACKAGES
    ):
        if registered_facility_id != facility_id:
            continue
        loaded = load_replay_package(
            facility_id,
            package_id,
            package_version,
        )
        packages.append(_package_summary(loaded))
    return {"replay_packages": packages}


def get_replay_package_detail(
    facility_id: str,
    package_id: str,
    package_version: str,
) -> dict[str, Any]:
    """Return a reviewer-facing detail view of a structurally validated package."""

    loaded = load_replay_package(facility_id, package_id, package_version)
    mapping_package = loaded["mapping_package"]
    return {
        **_package_summary(loaded),
        "structural_validation": "VALID",
        "narrative": loaded["narrative"],
        "oracle": loaded["oracle"],
        "source_bindings": mapping_package["source_bindings"],
        "mappings": mapping_package["mappings"],
        "delivery_count": len(loaded["deliveries"]),
        "limitations": deepcopy(loaded["manifest"].get("limitations", [])),
    }


def load_replay_package(
    facility_id: str,
    package_id: str,
    package_version: str,
) -> dict[str, Any]:
    """Load and structurally validate one exact allowlisted repository package."""

    manifest_path = REGISTERED_REPLAY_PACKAGES.get(
        (facility_id, package_id, package_version)
    )
    if manifest_path is None:
        raise LookupError(
            "No allowlisted observation replay package for facility "
            f"{facility_id!r}, package {package_id!r}, version "
            f"{package_version!r}"
        )

    manifest, files = _read_package(
        manifest_path,
        expected_files=_EXPECTED_REPLAY_FILES,
    )
    _validate_common_manifest(
        manifest,
        package_type="synthetic_observation_replay",
        package_id=package_id,
        package_version=package_version,
        facility_id=facility_id,
    )
    _validate_declared_digest(manifest, files, label="replay package")
    topology = _validate_topology_binding(manifest.get("topology"))

    mapping_pin = _require_object(
        manifest.get("mapping_package"),
        "replay manifest mapping_package",
    )
    mapping_package = load_mapping_package(
        _require_text(mapping_pin.get("package_id"), "mapping package_id"),
        _require_semver(
            mapping_pin.get("package_version"),
            "mapping package_version",
        ),
    )
    if mapping_pin.get("content_digest") != mapping_package["content_digest"]:
        raise ObservationPackageValidationError(
            "Replay package mapping-package digest does not match the "
            "registered package"
        )
    if mapping_package["facility_id"] != facility_id:
        raise ObservationPackageValidationError(
            "Replay and mapping package facility bindings differ"
        )
    if mapping_package["topology"] != topology:
        raise ObservationPackageValidationError(
            "Replay and mapping package topology bindings differ"
        )
    _validate_source_binding_pins(
        manifest.get("source_bindings"),
        mapping_package["source_bindings"],
    )
    _validate_mapping_pins(
        manifest.get("mappings"),
        mapping_package["mappings"],
    )
    _validate_replay_generator(manifest.get("generator"))

    narrative = _require_object(files["narrative"], "narrative file")
    deliveries_file = _require_object(files["deliveries"], "deliveries file")
    oracle = _require_object(files["oracle"], "oracle file")
    events = _validate_narrative(narrative)
    deliveries = _validate_deliveries(
        deliveries_file,
        events=events,
        mapping_package=mapping_package,
    )
    _validate_oracle(
        oracle,
        deliveries=deliveries,
        mapping_package=mapping_package,
    )

    return {
        "manifest_path": manifest_path,
        "manifest": manifest,
        "package_id": package_id,
        "package_version": package_version,
        "content_digest": manifest["content_digest"],
        "facility_id": facility_id,
        "topology": topology,
        "topology_manifest": _topology_manifest_snapshot(),
        "canonicalizer_version": CANONICALIZER_VERSION,
        "mapping_package": mapping_package,
        "narrative": narrative,
        "deliveries": deliveries,
        "oracle": oracle,
    }


def load_mapping_package(
    package_id: str,
    package_version: str,
) -> dict[str, Any]:
    """Load and structurally validate one exact registered mapping package."""

    manifest_path = REGISTERED_MAPPING_PACKAGES.get((package_id, package_version))
    if manifest_path is None:
        raise ObservationPackageValidationError(
            "Replay references an unregistered mapping package"
        )
    manifest, files = _read_package(
        manifest_path,
        expected_files=_EXPECTED_MAPPING_FILES,
    )
    facility_id = _require_text(
        manifest.get("facility_id"),
        "mapping manifest facility_id",
    )
    _validate_common_manifest(
        manifest,
        package_type="synthetic_observation_mapping",
        package_id=package_id,
        package_version=package_version,
        facility_id=facility_id,
    )
    _validate_declared_digest(manifest, files, label="mapping package")
    topology = _validate_topology_binding(manifest.get("topology"))

    binding_file = _require_object(
        files["source_bindings"],
        "source bindings file",
    )
    mapping_file = _require_object(files["mappings"], "mappings file")
    source_bindings = _validate_source_bindings(binding_file)
    mappings = _validate_mappings(
        mapping_file,
        source_bindings=source_bindings,
        point_ids=_topology_point_ids(),
    )
    return {
        "manifest_path": manifest_path,
        "manifest": manifest,
        "package_id": package_id,
        "package_version": package_version,
        "content_digest": manifest["content_digest"],
        "facility_id": facility_id,
        "topology": topology,
        "canonicalizer_version": CANONICALIZER_VERSION,
        "source_bindings": source_bindings,
        "mappings": mappings,
    }


def _read_package(
    manifest_path: Path,
    *,
    expected_files: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    resolved_manifest = manifest_path.resolve()
    package_size = _bounded_file_size(
        resolved_manifest,
        label="package manifest",
    )
    if package_size > MAX_REPOSITORY_PACKAGE_BYTES:
        raise ObservationPackageValidationError(
            "Repository package exceeds the "
            f"{MAX_REPOSITORY_PACKAGE_BYTES}-byte limit"
        )
    manifest = _read_bounded_json(resolved_manifest, label="package manifest")
    manifest = _require_object(manifest, "package manifest")
    declarations = _require_object(
        manifest.get("files"),
        "package manifest files",
    )
    if declarations != expected_files:
        raise ObservationPackageValidationError(
            "Package file declarations must match the registered bounded layout"
        )

    files = {}
    package_directory = resolved_manifest.parent
    for role, expected_name in expected_files.items():
        declared_name = declarations[role]
        if declared_name != expected_name:
            raise ObservationPackageValidationError(
                f"Package file role {role!r} has an unexpected path"
            )
        file_path = (package_directory / declared_name).resolve()
        if (
            not file_path.is_relative_to(package_directory)
            or file_path.parent != package_directory
        ):
            raise ObservationPackageValidationError(
                f"Package file role {role!r} escapes its registered directory"
            )
        package_size += _bounded_file_size(
            file_path,
            label=f"{role} file",
        )
        if package_size > MAX_REPOSITORY_PACKAGE_BYTES:
            raise ObservationPackageValidationError(
                "Repository package exceeds the "
                f"{MAX_REPOSITORY_PACKAGE_BYTES}-byte limit"
            )
        files[role] = _read_bounded_json(file_path, label=f"{role} file")
    return manifest, files


def _bounded_file_size(path: Path, *, label: str) -> int:
    try:
        size = path.stat().st_size
    except FileNotFoundError as exc:
        raise ObservationPackageValidationError(
            f"Registered {label} not found: {path}"
        ) from exc
    if size > MAX_PACKAGE_FILE_BYTES:
        raise ObservationPackageValidationError(
            f"{label.capitalize()} exceeds the {MAX_PACKAGE_FILE_BYTES}-byte limit"
        )
    return size


def _read_bounded_json(path: Path, *, label: str) -> Any:
    _bounded_file_size(path, label=label)
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except UnicodeDecodeError as exc:
        raise ObservationPackageValidationError(
            f"{label.capitalize()} is not valid UTF-8"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ObservationPackageValidationError(
            f"{label.capitalize()} is not valid JSON: {exc}"
        ) from exc


def _validate_common_manifest(
    manifest: dict[str, Any],
    *,
    package_type: str,
    package_id: str,
    package_version: str,
    facility_id: str,
) -> None:
    if manifest.get("schema_version") != 1:
        raise ObservationPackageValidationError(
            "Package schema_version must be 1"
        )
    expected = {
        "package_type": package_type,
        "package_id": package_id,
        "package_version": package_version,
        "facility_id": facility_id,
        "canonicalizer_version": CANONICALIZER_VERSION,
    }
    for field_name, expected_value in expected.items():
        if manifest.get(field_name) != expected_value:
            raise ObservationPackageValidationError(
                f"Package manifest {field_name} does not match its "
                "registered identity"
            )
    _require_semver(package_version, "package_version")
    _require_digest(manifest.get("content_digest"), "package content_digest")
    _reject_prohibited_keys(manifest, path="manifest")


def _validate_declared_digest(
    manifest: dict[str, Any],
    files: dict[str, Any],
    *,
    label: str,
) -> None:
    computed = package_content_digest(manifest, files)
    if manifest.get("content_digest") != computed:
        raise ObservationPackageValidationError(
            f"{label.capitalize()} content digest mismatch: declared "
            f"{manifest.get('content_digest')!r}, computed {computed!r}"
        )


def _validate_topology_binding(value: Any) -> dict[str, str]:
    topology = _require_object(value, "topology binding")
    expected = {
        "topology_id": FLAGSHIP_TOPOLOGY_ID,
        "topology_version": FLAGSHIP_TOPOLOGY_VERSION,
        "content_digest": facility_package_content_digest(
            FLAGSHIP_OBSERVATION_MANIFEST
        ),
    }
    if topology != expected:
        raise ObservationPackageValidationError(
            "Package topology binding does not match the registered immutable "
            "flagship topology snapshot"
        )
    return deepcopy(expected)


def _topology_manifest_snapshot() -> dict[str, Any]:
    _, manifest = read_manifest(FLAGSHIP_OBSERVATION_MANIFEST)
    return manifest


def _topology_point_ids() -> set[str]:
    manifest_path, manifest = read_manifest(FLAGSHIP_OBSERVATION_MANIFEST)
    files = _require_object(manifest.get("files"), "topology manifest files")
    points_name = _require_text(files.get("points"), "topology points file")
    points_path = (manifest_path.parent / points_name).resolve()
    if (
        not points_path.is_relative_to(manifest_path.parent)
        or not points_path.is_file()
    ):
        raise ObservationPackageValidationError(
            "Registered topology points file is unavailable"
        )
    with points_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    return {
        _require_text(row.get("id"), "topology point id")
        for row in rows
        if row.get("facility_id") == FLAGSHIP_FACILITY_ID
    }


def _validate_source_bindings(value: dict[str, Any]) -> list[dict[str, Any]]:
    raw_bindings = value.get("source_bindings")
    if not isinstance(raw_bindings, list) or not raw_bindings:
        raise ObservationPackageValidationError(
            "Source bindings file must contain a non-empty source_bindings list"
        )
    bindings = []
    identities: set[str] = set()
    source_channels: set[tuple[str, str]] = set()
    for index, raw_binding in enumerate(raw_bindings):
        binding = _require_object(
            raw_binding,
            f"source_bindings[{index}]",
        )
        binding_id = _require_text(
            binding.get("source_binding_id"),
            f"source_bindings[{index}].source_binding_id",
        )
        source_id = _require_text(
            binding.get("source_id"),
            f"source_bindings[{index}].source_id",
        )
        channel = _require_text(
            binding.get("channel"),
            f"source_bindings[{index}].channel",
        )
        _require_text(
            binding.get("description"),
            f"source_bindings[{index}].description",
        )
        dependency = _require_object(
            binding.get("dependency_provenance"),
            f"source_bindings[{index}].dependency_provenance",
        )
        missing_dependency_fields = sorted(
            _REQUIRED_DEPENDENCY_PROVENANCE_FIELDS - set(dependency)
        )
        if missing_dependency_fields:
            raise ObservationPackageValidationError(
                f"Source binding {binding_id} must preserve every dependency "
                "origin or an explicit UNKNOWN value; missing: "
                + ", ".join(missing_dependency_fields)
            )
        for field_name in sorted(_REQUIRED_DEPENDENCY_PROVENANCE_FIELDS):
            _require_text(
                dependency[field_name],
                f"source binding {binding_id} dependency {field_name}",
            )
        binding_version = _require_semver(
            binding.get("source_binding_version"),
            f"source_bindings[{index}].source_binding_version",
        )
        binding_digest = _require_digest(
            binding.get("content_digest"),
            f"source_bindings[{index}].content_digest",
        )
        if source_binding_definition_digest(binding) != binding_digest:
            raise ObservationPackageValidationError(
                f"Source binding {binding_id} {binding_version} content "
                "digest mismatch"
            )
        _reject_prohibited_keys(binding, path=f"source_bindings[{index}]")
        if binding_id in identities:
            raise ObservationPackageValidationError(
                f"Duplicate source binding ID: {binding_id}"
            )
        if (source_id, channel) in source_channels:
            raise ObservationPackageValidationError(
                "Source ID and channel pairs must be unique"
            )
        identities.add(binding_id)
        source_channels.add((source_id, channel))
        bindings.append(deepcopy(binding))
    return bindings


def _validate_source_binding_pins(
    raw_pins: Any,
    source_bindings: list[dict[str, Any]],
) -> None:
    if not isinstance(raw_pins, list):
        raise ObservationPackageValidationError(
            "Replay manifest must pin a source_bindings list"
        )
    expected = sorted(
        [
            {
                "source_binding_id": binding["source_binding_id"],
                "source_binding_version": binding[
                    "source_binding_version"
                ],
                "content_digest": binding["content_digest"],
            }
            for binding in source_bindings
        ],
        key=lambda item: item["source_binding_id"],
    )
    actual = []
    for index, raw_pin in enumerate(raw_pins):
        pin = _require_object(
            raw_pin,
            f"replay source_bindings[{index}]",
        )
        actual.append(
            {
                "source_binding_id": _require_text(
                    pin.get("source_binding_id"),
                    f"replay source_bindings[{index}].source_binding_id",
                ),
                "source_binding_version": _require_semver(
                    pin.get("source_binding_version"),
                    f"replay source_bindings[{index}].source_binding_version",
                ),
                "content_digest": _require_digest(
                    pin.get("content_digest"),
                    f"replay source_bindings[{index}].content_digest",
                ),
            }
        )
        if set(pin) != {
            "source_binding_id",
            "source_binding_version",
            "content_digest",
        }:
            raise ObservationPackageValidationError(
                "Replay source-binding pins may contain only identity, "
                "version, and digest"
            )
    actual.sort(key=lambda item: item["source_binding_id"])
    if actual != expected:
        raise ObservationPackageValidationError(
            "Replay source-binding pins do not match the mapping package"
        )


def _validate_mapping_pins(
    raw_pins: Any,
    mappings: list[dict[str, Any]],
) -> None:
    if not isinstance(raw_pins, list):
        raise ObservationPackageValidationError(
            "Replay manifest must pin a mappings list"
        )
    expected = sorted(
        [
            {
                "mapping_id": mapping["mapping_id"],
                "mapping_version": mapping["mapping_version"],
                "content_digest": mapping["content_digest"],
            }
            for mapping in mappings
        ],
        key=lambda item: (item["mapping_id"], item["mapping_version"]),
    )
    actual = []
    for index, raw_pin in enumerate(raw_pins):
        pin = _require_object(raw_pin, f"replay mappings[{index}]")
        actual.append(
            {
                "mapping_id": _require_text(
                    pin.get("mapping_id"),
                    f"replay mappings[{index}].mapping_id",
                ),
                "mapping_version": _require_semver(
                    pin.get("mapping_version"),
                    f"replay mappings[{index}].mapping_version",
                ),
                "content_digest": _require_digest(
                    pin.get("content_digest"),
                    f"replay mappings[{index}].content_digest",
                ),
            }
        )
        if set(pin) != {
            "mapping_id",
            "mapping_version",
            "content_digest",
        }:
            raise ObservationPackageValidationError(
                "Replay mapping pins may contain only identity, version, "
                "and digest"
            )
    actual.sort(key=lambda item: (item["mapping_id"], item["mapping_version"]))
    if actual != expected:
        raise ObservationPackageValidationError(
            "Replay mapping pins do not match the mapping package"
        )


def _validate_replay_generator(value: Any) -> None:
    generator = _require_object(value, "replay manifest generator")
    _require_text(generator.get("generator_id"), "replay generator_id")
    _require_semver(
        generator.get("generator_version"),
        "replay generator_version",
    )
    if (
        generator.get("synthetic") is not True
        or generator.get("fictional") is not True
    ):
        raise ObservationPackageValidationError(
            "Replay generator must be explicitly synthetic and fictional"
        )


def _validate_mappings(
    value: dict[str, Any],
    *,
    source_bindings: list[dict[str, Any]],
    point_ids: set[str],
) -> list[dict[str, Any]]:
    raw_mappings = value.get("mappings")
    if not isinstance(raw_mappings, list) or not raw_mappings:
        raise ObservationPackageValidationError(
            "Mappings file must contain a non-empty mappings list"
        )
    binding_ids = {
        binding["source_binding_id"] for binding in source_bindings
    }
    identities: set[tuple[str, str]] = set()
    mappings = []
    for index, raw_mapping in enumerate(raw_mappings):
        mapping = _require_object(raw_mapping, f"mappings[{index}]")
        mapping_id = _require_text(
            mapping.get("mapping_id"),
            f"mappings[{index}].mapping_id",
        )
        mapping_version = _require_semver(
            mapping.get("mapping_version"),
            f"mappings[{index}].mapping_version",
        )
        mapping_digest = _require_digest(
            mapping.get("content_digest"),
            f"mappings[{index}].content_digest",
        )
        if mapping_definition_digest(mapping) != mapping_digest:
            raise ObservationPackageValidationError(
                f"Mapping {mapping_id} {mapping_version} content digest mismatch"
            )
        binding_id = _require_text(
            mapping.get("source_binding_id"),
            f"mappings[{index}].source_binding_id",
        )
        if binding_id not in binding_ids:
            raise ObservationPackageValidationError(
                f"Mapping {mapping_id} references an unknown source binding"
            )
        _require_text(
            mapping.get("description"),
            f"mappings[{index}].description",
        )
        _validate_transformation(
            mapping.get("transformation"),
            point_ids=point_ids,
            label=f"mapping {mapping_id} {mapping_version}",
        )
        identity = (mapping_id, mapping_version)
        if identity in identities:
            raise ObservationPackageValidationError(
                f"Duplicate mapping identity: {mapping_id} {mapping_version}"
            )
        identities.add(identity)
        _reject_prohibited_keys(mapping, path=f"mappings[{index}]")
        mappings.append(deepcopy(mapping))
    return mappings


def _validate_transformation(
    value: Any,
    *,
    point_ids: set[str],
    label: str,
) -> None:
    transformation = _require_object(value, f"{label} transformation")
    kind = transformation.get("kind")
    if kind == "FIELD_SET":
        outputs = transformation.get("outputs")
        if not isinstance(outputs, list) or not outputs:
            raise ObservationPackageValidationError(
                f"{label} FIELD_SET must declare outputs"
            )
        targets = set()
        for output_index, raw_output in enumerate(outputs):
            output = _require_object(
                raw_output,
                f"{label} outputs[{output_index}]",
            )
            _require_field_path(
                output.get("source_field"),
                f"{label} outputs[{output_index}].source_field",
                allow_bare=True,
            )
            target = _require_text(
                output.get("target_point_id"),
                f"{label} outputs[{output_index}].target_point_id",
            )
            if target not in point_ids:
                raise ObservationPackageValidationError(
                    f"{label} references unknown point {target!r}"
                )
            if target in targets:
                raise ObservationPackageValidationError(
                    f"{label} declares point {target!r} more than once"
                )
            targets.add(target)
            value_type = output.get("value_type")
            if value_type not in _ALLOWED_VALUE_TYPES:
                raise ObservationPackageValidationError(
                    f"{label} output value_type is unsupported"
                )
            normalization = _require_object(
                output.get("normalization"),
                f"{label} output normalization",
            )
            normalization_kind = normalization.get("kind")
            if normalization_kind not in _ALLOWED_FIELD_NORMALIZATIONS:
                raise ObservationPackageValidationError(
                    f"{label} output normalization is unsupported"
                )
            _validate_normalization(
                normalization,
                value_type=value_type,
                label=label,
            )
            _validate_unit(output.get("unit"), value_type=value_type, label=label)
        return

    if kind == "REGISTER_PAIR_SIGNED_INT32_BE":
        for field_name in (
            "decode_group_field",
            "component_role_field",
            "value_field",
        ):
            _require_field_path(
                transformation.get(field_name),
                f"{label} {field_name}",
                allow_bare=True,
            )
        high_role = _require_text(
            transformation.get("high_role"),
            f"{label} high_role",
        )
        low_role = _require_text(
            transformation.get("low_role"),
            f"{label} low_role",
        )
        if high_role == low_role:
            raise ObservationPackageValidationError(
                f"{label} register roles must differ"
            )
        target = _require_text(
            transformation.get("target_point_id"),
            f"{label} target_point_id",
        )
        if target not in point_ids:
            raise ObservationPackageValidationError(
                f"{label} references unknown point {target!r}"
            )
        if transformation.get("value_type") != "DECIMAL":
            raise ObservationPackageValidationError(
                f"{label} register-pair output must use DECIMAL"
            )
        _require_decimal_text(transformation.get("factor"), f"{label} factor")
        _require_decimal_text(transformation.get("quantum"), f"{label} quantum")
        _require_text(transformation.get("unit"), f"{label} unit")
        return

    raise ObservationPackageValidationError(
        f"{label} transformation kind is unsupported"
    )


def _validate_normalization(
    normalization: dict[str, Any],
    *,
    value_type: str,
    label: str,
) -> None:
    kind = normalization["kind"]
    if kind == "STRICT_BOOLEAN":
        if value_type != "BOOLEAN":
            raise ObservationPackageValidationError(
                f"{label} STRICT_BOOLEAN output must use BOOLEAN"
            )
        true_values = normalization.get("true_values", [True])
        false_values = normalization.get("false_values", [False])
        if (
            not isinstance(true_values, list)
            or not true_values
            or not isinstance(false_values, list)
            or not false_values
        ):
            raise ObservationPackageValidationError(
                f"{label} Boolean token declarations must be non-empty lists"
            )
        return
    if kind == "DIRECT_ENUM":
        enum_mapping = normalization.get("mapping")
        if (
            value_type != "ENUM"
            or not isinstance(enum_mapping, dict)
            or not enum_mapping
            or any(
                not isinstance(key, str)
                or not key
                or not isinstance(item, str)
                or not item
                for key, item in enum_mapping.items()
            )
        ):
            raise ObservationPackageValidationError(
                f"{label} DIRECT_ENUM must declare exact string mappings"
            )
        return
    if kind in {"DECIMAL", "DECIMAL_SCALE", "UNIT_CONVERSION"}:
        if value_type != "DECIMAL":
            raise ObservationPackageValidationError(
                f"{label} decimal normalization must use DECIMAL"
            )
        _require_decimal_text(normalization.get("factor"), f"{label} factor")
        _require_decimal_text(normalization.get("quantum"), f"{label} quantum")
        return


def _validate_unit(value: Any, *, value_type: str, label: str) -> None:
    if value is None:
        return
    unit = _require_text(value, f"{label} unit")
    if value_type in {"BOOLEAN", "TEXT", "ENUM"} and unit:
        raise ObservationPackageValidationError(
            f"{label} {value_type} output cannot declare a unit"
        )


def _validate_narrative(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_events = value.get("events")
    if not isinstance(raw_events, list) or not raw_events:
        raise ObservationPackageValidationError(
            "Narrative file must contain a non-empty events list"
        )
    events: dict[str, dict[str, Any]] = {}
    orders: set[int] = set()
    for index, raw_event in enumerate(raw_events):
        event = _require_object(raw_event, f"narrative events[{index}]")
        event_id = _require_text(
            event.get("event_id"),
            f"narrative events[{index}].event_id",
        )
        order = event.get("order")
        if isinstance(order, bool) or not isinstance(order, int) or order < 0:
            raise ObservationPackageValidationError(
                f"Narrative event {event_id} order must be a non-negative integer"
            )
        if event_id in events or order in orders:
            raise ObservationPackageValidationError(
                "Narrative event IDs and orders must be unique"
            )
        _require_text(event.get("label"), f"narrative event {event_id} label")
        _require_text(
            event.get("description"),
            f"narrative event {event_id} description",
        )
        if event.get("executed") is not True:
            raise ObservationPackageValidationError(
                f"Narrative event {event_id} must be an implemented replay entry"
            )
        kind = event.get("kind")
        if kind == "ACTION_CONTEXT":
            valid_identity = event_id == "E180-HUMAN-ACTION-RECORDED"
        elif kind == "OBSERVATION_GROUP":
            valid_identity = (
                _RECEIVED_INDICATION_EVENT_PATTERN.fullmatch(event_id)
                is not None
                and event_id in _APPROVED_REPLAY_OBSERVATION_EVENT_IDS
            )
        else:
            valid_identity = False
        if not valid_identity:
            raise ObservationPackageValidationError(
                f"Narrative event {event_id} must be the approved "
                "recorded-action annotation or a received-indication "
                "observation group"
            )
        events[event_id] = event
        orders.add(order)
    _reject_prohibited_outcome_phrases(
        value,
        label="Replay narrative",
    )
    return events


def _validate_deliveries(
    value: dict[str, Any],
    *,
    events: dict[str, dict[str, Any]],
    mapping_package: dict[str, Any],
) -> list[dict[str, Any]]:
    raw_deliveries = value.get("deliveries")
    if not isinstance(raw_deliveries, list) or not raw_deliveries:
        raise ObservationPackageValidationError(
            "Deliveries file must contain a non-empty deliveries list"
        )
    if len(raw_deliveries) > MAX_DELIVERIES:
        raise ObservationPackageValidationError(
            f"Replay package exceeds the {MAX_DELIVERIES}-delivery limit"
        )
    binding_by_id = {
        binding["source_binding_id"]: binding
        for binding in mapping_package["source_bindings"]
    }
    mapping_by_identity = {
        (mapping["mapping_id"], mapping["mapping_version"]): mapping
        for mapping in mapping_package["mappings"]
    }
    delivery_ids: set[str] = set()
    deliveries = []
    for index, raw_delivery in enumerate(raw_deliveries):
        delivery = _require_object(raw_delivery, f"deliveries[{index}]")
        delivery_id = _require_text(
            delivery.get("delivery_id"),
            f"deliveries[{index}].delivery_id",
        )
        if delivery_id in delivery_ids:
            raise ObservationPackageValidationError(
                f"Duplicate replay delivery ID: {delivery_id}"
            )
        delivery_ids.add(delivery_id)
        narrative_event_id = _require_text(
            delivery.get("narrative_event_id"),
            f"delivery {delivery_id} narrative_event_id",
        )
        if narrative_event_id not in events:
            raise ObservationPackageValidationError(
                f"Delivery {delivery_id} references an unknown narrative event"
            )
        if not events[narrative_event_id]["executed"]:
            raise ObservationPackageValidationError(
                f"Delivery {delivery_id} references a non-executed narrative event"
            )
        binding_id = _require_text(
            delivery.get("source_binding_id"),
            f"delivery {delivery_id} source_binding_id",
        )
        if binding_id not in binding_by_id:
            raise ObservationPackageValidationError(
                f"Delivery {delivery_id} references an unknown source binding"
            )
        mapping_pin = _require_object(
            delivery.get("mapping"),
            f"delivery {delivery_id} mapping",
        )
        mapping_id = _require_text(
            mapping_pin.get("mapping_id"),
            f"delivery {delivery_id} mapping_id",
        )
        mapping_version = _require_semver(
            mapping_pin.get("mapping_version"),
            f"delivery {delivery_id} mapping_version",
        )
        mapping = mapping_by_identity.get((mapping_id, mapping_version))
        if mapping is None:
            raise ObservationPackageValidationError(
                f"Delivery {delivery_id} references an unresolved mapping"
            )
        if mapping_pin.get("content_digest") != mapping["content_digest"]:
            raise ObservationPackageValidationError(
                f"Delivery {delivery_id} mapping digest mismatch"
            )
        if mapping["source_binding_id"] != binding_id:
            raise ObservationPackageValidationError(
                f"Delivery {delivery_id} mapping and source binding differ"
            )
        received = parse_rfc3339_timestamp(delivery.get("received_at"))
        if received["status"] != "VALID":
            raise ObservationPackageValidationError(
                f"Delivery {delivery_id} received_at must be valid RFC 3339"
            )
        observed_at = delivery.get("observed_at")
        if observed_at is not None and not isinstance(observed_at, str):
            raise ObservationPackageValidationError(
                f"Delivery {delivery_id} observed_at must be a string or null"
            )
        source_event = _require_object(
            delivery.get("source_event"),
            f"delivery {delivery_id} source_event",
        )
        _validate_source_event(source_event, delivery_id=delivery_id)
        payload = _require_object(
            delivery.get("payload"),
            f"delivery {delivery_id} payload",
        )
        if len(canonical_json_text(payload).encode("utf-8")) > MAX_SOURCE_PAYLOAD_BYTES:
            raise ObservationPackageValidationError(
                f"Delivery {delivery_id} payload exceeds the "
                f"{MAX_SOURCE_PAYLOAD_BYTES}-byte limit"
            )
        for field_name in (
            "source_quality",
            "source_metadata",
            "transport_provenance",
            "synthetic_provenance",
        ):
            _require_object(
                delivery.get(field_name),
                f"delivery {delivery_id} {field_name}",
            )
        if delivery["synthetic_provenance"].get("synthetic") is not True:
            raise ObservationPackageValidationError(
                f"Delivery {delivery_id} must be explicitly synthetic"
            )
        _reject_prohibited_keys(delivery, path=f"delivery {delivery_id}")
        deliveries.append(deepcopy(delivery))
    return deliveries


def _validate_source_event(value: dict[str, Any], *, delivery_id: str) -> None:
    event_id = value.get("event_id")
    if event_id is not None:
        _require_text(event_id, f"delivery {delivery_id} source event_id")
    epoch = value.get("session_epoch")
    if epoch is not None:
        _require_text(epoch, f"delivery {delivery_id} source session_epoch")
    sequence = value.get("sequence")
    if sequence is not None and (
        isinstance(sequence, bool) or not isinstance(sequence, int)
    ):
        raise ObservationPackageValidationError(
            f"Delivery {delivery_id} source sequence must be an integer or null"
        )
    for optional_text in ("decode_group_id", "component_role"):
        if value.get(optional_text) is not None:
            _require_text(
                value[optional_text],
                f"delivery {delivery_id} source {optional_text}",
            )


def _validate_oracle(
    value: dict[str, Any],
    *,
    deliveries: list[dict[str, Any]],
    mapping_package: dict[str, Any],
) -> None:
    if not value:
        raise ObservationPackageValidationError(
            "Replay oracle must describe expected structural behavior"
        )
    _reject_prohibited_keys(value, path="oracle")
    _reject_prohibited_outcome_phrases(value, label="Replay oracle")

    delivery_by_id = {
        delivery["delivery_id"]: delivery for delivery in deliveries
    }
    source_binding_ids = {
        binding["source_binding_id"]
        for binding in mapping_package["source_bindings"]
    }
    mapping_by_identity = {
        (mapping["mapping_id"], mapping["mapping_version"]): mapping
        for mapping in mapping_package["mappings"]
    }
    point_ids = _topology_point_ids()

    for index, raw_group in enumerate(value.get("identity_groups", [])):
        group = _require_object(
            raw_group,
            f"oracle identity_groups[{index}]",
        )
        delivery_ids = _require_resolved_oracle_delivery_ids(
            group.get("delivery_ids"),
            label=f"oracle identity_groups[{index}].delivery_ids",
            delivery_by_id=delivery_by_id,
        )
        binding_id = _require_text(
            group.get("source_binding_id"),
            f"oracle identity_groups[{index}].source_binding_id",
        )
        if binding_id not in source_binding_ids:
            raise ObservationPackageValidationError(
                f"Oracle identity group references unknown source binding "
                f"{binding_id!r}"
            )
        if any(
            delivery_by_id[delivery_id]["source_binding_id"] != binding_id
            for delivery_id in delivery_ids
        ):
            raise ObservationPackageValidationError(
                "Oracle identity group source binding does not match its "
                "deliveries"
            )
        declared_event_id = group.get("source_event_id")
        if declared_event_id is not None:
            declared_event_id = _require_text(
                declared_event_id,
                f"oracle identity_groups[{index}].source_event_id",
            )
            if any(
                delivery_by_id[delivery_id]["source_event"].get("event_id")
                != declared_event_id
                for delivery_id in delivery_ids
            ):
                raise ObservationPackageValidationError(
                    "Oracle identity group source event does not match its "
                    "deliveries"
                )
        declared_event_ids = group.get("source_event_ids")
        if declared_event_ids is not None:
            if (
                not isinstance(declared_event_ids, list)
                or not declared_event_ids
                or any(
                    not isinstance(event_id, str) or not event_id
                    for event_id in declared_event_ids
                )
            ):
                raise ObservationPackageValidationError(
                    "Oracle identity group source_event_ids must be a "
                    "non-empty text list"
                )
            actual_event_ids = {
                delivery_by_id[delivery_id]["source_event"].get("event_id")
                for delivery_id in delivery_ids
            }
            if set(declared_event_ids) != actual_event_ids:
                raise ObservationPackageValidationError(
                    "Oracle identity group source events do not match its "
                    "deliveries"
                )

    for index, raw_lineage in enumerate(value.get("decode_lineage", [])):
        lineage = _require_object(
            raw_lineage,
            f"oracle decode_lineage[{index}]",
        )
        _require_resolved_oracle_delivery_ids(
            lineage.get("source_delivery_ids"),
            label=f"oracle decode_lineage[{index}].source_delivery_ids",
            delivery_by_id=delivery_by_id,
        )
        target_point_id = _require_text(
            lineage.get("target_point_id"),
            f"oracle decode_lineage[{index}].target_point_id",
        )
        if target_point_id not in point_ids:
            raise ObservationPackageValidationError(
                f"Oracle decode lineage references unknown point "
                f"{target_point_id!r}"
            )

    for index, raw_fact in enumerate(value.get("ordering_facts", [])):
        fact = _require_object(
            raw_fact,
            f"oracle ordering_facts[{index}]",
        )
        referenced_delivery_ids: list[str] = []
        for field_name, field_value in fact.items():
            if (
                field_name == "delivery_id"
                or field_name.endswith("_delivery_id")
            ):
                referenced_delivery_ids.append(
                    _require_text(
                        field_value,
                        f"oracle ordering_facts[{index}].{field_name}",
                    )
                )
            elif (
                field_name == "delivery_ids"
                or field_name.endswith("_delivery_ids")
            ):
                if not isinstance(field_value, list):
                    raise ObservationPackageValidationError(
                        f"Oracle ordering fact {field_name} must be a list"
                    )
                referenced_delivery_ids.extend(field_value)
        _require_resolved_oracle_delivery_ids(
            referenced_delivery_ids,
            label=f"oracle ordering_facts[{index}] delivery references",
            delivery_by_id=delivery_by_id,
        )
        if fact.get("fact_kind") == "MAPPING_VERSION_TRANSITION":
            mapping_id = _require_text(
                fact.get("mapping_id"),
                f"oracle ordering_facts[{index}].mapping_id",
            )
            for version_field in ("from_version", "to_version"):
                mapping_version = _require_semver(
                    fact.get(version_field),
                    f"oracle ordering_facts[{index}].{version_field}",
                )
                if (mapping_id, mapping_version) not in mapping_by_identity:
                    raise ObservationPackageValidationError(
                        "Oracle mapping transition references an unresolved "
                        f"mapping {mapping_id} {mapping_version}"
                    )

    for index, raw_expectation in enumerate(
        value.get("projection_expectations", [])
    ):
        expectation = _require_object(
            raw_expectation,
            f"oracle projection_expectations[{index}]",
        )
        scope = _require_object(
            expectation.get("scope"),
            f"oracle projection_expectations[{index}].scope",
        )
        binding_id = _require_text(
            scope.get("source_binding_id"),
            f"oracle projection_expectations[{index}] source_binding_id",
        )
        if binding_id not in source_binding_ids:
            raise ObservationPackageValidationError(
                f"Oracle projection references unknown source binding "
                f"{binding_id!r}"
            )
        point_id = _require_text(
            scope.get("point_id"),
            f"oracle projection_expectations[{index}] point_id",
        )
        if point_id not in point_ids:
            raise ObservationPackageValidationError(
                f"Oracle projection references unknown point {point_id!r}"
            )
        mapping_id = _require_text(
            scope.get("mapping_id"),
            f"oracle projection_expectations[{index}] mapping_id",
        )
        mapping_version = _require_semver(
            scope.get("mapping_version"),
            f"oracle projection_expectations[{index}] mapping_version",
        )
        mapping = mapping_by_identity.get((mapping_id, mapping_version))
        if mapping is None:
            raise ObservationPackageValidationError(
                "Oracle projection references an unresolved mapping "
                f"{mapping_id} {mapping_version}"
            )
        if mapping["source_binding_id"] != binding_id:
            raise ObservationPackageValidationError(
                "Oracle projection mapping and source binding differ"
            )


def _require_resolved_oracle_delivery_ids(
    value: Any,
    *,
    label: str,
    delivery_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise ObservationPackageValidationError(
            f"{label} must be a non-empty text list"
        )
    missing = sorted(set(value) - set(delivery_by_id))
    if missing:
        raise ObservationPackageValidationError(
            f"{label} contains unresolved delivery references: "
            + ", ".join(missing)
        )
    return value


def _reject_prohibited_outcome_phrases(value: Any, *, label: str) -> None:
    serialized = canonical_json_text(value).lower().replace("-", " ")
    matched = next(
        (
            phrase
            for phrase in _PROHIBITED_OUTCOME_PHRASES
            if phrase in serialized
        ),
        None,
    )
    if matched is not None:
        raise ObservationPackageValidationError(
            f"{label} contains an unapproved physical, outcome, conformance, "
            f"authorization, or recovery claim: {matched!r}"
        )


def _package_summary(loaded: dict[str, Any]) -> dict[str, Any]:
    return {
        "package_id": loaded["package_id"],
        "package_version": loaded["package_version"],
        "content_digest": loaded["content_digest"],
        "facility_id": loaded["facility_id"],
        "topology": deepcopy(loaded["topology"]),
        "mapping_package": {
            "package_id": loaded["mapping_package"]["package_id"],
            "package_version": loaded["mapping_package"]["package_version"],
            "content_digest": loaded["mapping_package"]["content_digest"],
        },
        "canonicalizer_version": loaded["canonicalizer_version"],
        "synthetic": True,
        "description": loaded["manifest"].get("description", ""),
    }


def _reject_prohibited_keys(value: Any, *, path: str) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in _PROHIBITED_PACKAGE_KEYS:
                raise ObservationPackageValidationError(
                    f"{path} contains prohibited conclusion field {key!r}"
                )
            _reject_prohibited_keys(nested, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_prohibited_keys(nested, path=f"{path}[{index}]")


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ObservationPackageValidationError(f"{label} must be a JSON object")
    return value


def _require_text(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > MAX_TEXT_LENGTH
    ):
        raise ObservationPackageValidationError(
            f"{label} must be a bounded non-blank string without outer whitespace"
        )
    return value


def _require_semver(value: Any, label: str) -> str:
    text = _require_text(value, label)
    if _SEMVER_PATTERN.fullmatch(text) is None:
        raise ObservationPackageValidationError(
            f"{label} must be a semantic version"
        )
    return text


def _require_digest(value: Any, label: str) -> str:
    text = _require_text(value, label)
    if _DIGEST_PATTERN.fullmatch(text) is None:
        raise ObservationPackageValidationError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return text


def _require_field_path(
    value: Any,
    label: str,
    *,
    allow_bare: bool = False,
) -> str:
    text = _require_text(value, label)
    if allow_bare and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", text):
        return text
    if re.fullmatch(r"\$\.[A-Za-z_][A-Za-z0-9_.]*", text) is None:
        raise ObservationPackageValidationError(
            f"{label} must be a bounded simple JSON field path"
        )
    return text


def _require_decimal_text(value: Any, label: str) -> str:
    text = _require_text(value, label)
    try:
        from decimal import Decimal

        parsed = Decimal(text)
    except Exception as exc:
        raise ObservationPackageValidationError(
            f"{label} must be a finite decimal string"
        ) from exc
    if not parsed.is_finite():
        raise ObservationPackageValidationError(
            f"{label} must be a finite decimal string"
        )
    return text
