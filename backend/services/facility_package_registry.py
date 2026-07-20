import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

NORTHSTAR_FACILITY_ID = "FACILITY-NORTHSTAR-DATA-HALL"
NORTHSTAR_FIXTURE_VERSION = "1.0.0"
FLAGSHIP_FACILITY_ID = "FACILITY-ADVANCED-MATERIALS-RESEARCH"
FLAGSHIP_FACILITY_NAME = (
    "Advanced Materials Research and Precision-Environment Facility"
)
FLAGSHIP_FIXTURE_VERSION = "1.0.0"

NORTHSTAR_MANIFEST = (
    PROJECT_ROOT
    / "data"
    / "facilities"
    / "northstar"
    / NORTHSTAR_FIXTURE_VERSION
    / "manifest.json"
)
FLAGSHIP_MANIFEST = (
    PROJECT_ROOT
    / "data"
    / "facilities"
    / "flagship"
    / FLAGSHIP_FIXTURE_VERSION
    / "manifest.json"
)

REGISTERED_MANIFESTS = {
    (NORTHSTAR_FACILITY_ID, NORTHSTAR_FIXTURE_VERSION): NORTHSTAR_MANIFEST,
    (FLAGSHIP_FACILITY_ID, FLAGSHIP_FIXTURE_VERSION): FLAGSHIP_MANIFEST,
}


def read_manifest(manifest_path):
    """Read a JSON fixture manifest using only the Python standard library."""
    path = Path(manifest_path).resolve()
    try:
        with path.open(mode="r", encoding="utf-8") as file:
            manifest = json.load(file)
    except FileNotFoundError as error:
        raise ValueError(f"Fixture manifest not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid fixture manifest JSON: {path}: {error}") from error

    if not isinstance(manifest, dict):
        raise ValueError("Fixture manifest root must be a JSON object")

    return path, manifest


def manifest_identity(manifest):
    """Return the required facility identity fields from a manifest."""
    facility = manifest.get("facility")
    if not isinstance(facility, dict):
        raise ValueError("Fixture manifest must define a facility object")

    identity = {}
    for field_name in ("facility_id", "facility_name", "fixture_version"):
        value = facility.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"Fixture manifest facility.{field_name} must be a non-blank string"
            )
        identity[field_name] = value.strip()

    return identity


def resolve_manifest_file(manifest_path, relative_path):
    """Resolve an existing file declared relative to its fixture manifest."""
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ValueError("Fixture package file paths must be non-blank strings")

    resolved_path = (Path(manifest_path).parent / relative_path).resolve()
    if not resolved_path.is_file():
        raise ValueError(f"Fixture package file not found: {resolved_path}")

    return resolved_path


def resolve_registered_fixture(facility_id, fixture_version):
    """Resolve one exact registered facility/version context without fallback."""
    manifest_path = REGISTERED_MANIFESTS.get((facility_id, fixture_version))
    if manifest_path is None:
        raise LookupError(
            "No registered fixture package for facility "
            f"{facility_id!r} at version {fixture_version!r}"
        )

    resolved_manifest_path, manifest = read_manifest(manifest_path)
    identity = manifest_identity(manifest)
    if identity["facility_id"] != facility_id:
        raise ValueError(
            "Registered fixture manifest facility_id does not match the registry key"
        )
    if identity["fixture_version"] != fixture_version:
        raise ValueError(
            "Registered fixture manifest fixture_version does not match the "
            "registry key"
        )

    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ValueError("Registered fixture manifest must define a files object")

    baseline_declaration = files.get("current_point_values")
    baseline_path = None
    if baseline_declaration is not None:
        baseline_path = resolve_manifest_file(
            resolved_manifest_path,
            baseline_declaration,
        )

    return {
        **identity,
        "manifest_path": resolved_manifest_path,
        "package_type": manifest.get("package_type", ""),
        "current_point_value_path": baseline_path,
    }
