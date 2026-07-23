from pathlib import Path

from fastapi import Body
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse

from backend.adapters.csv_replay_driver import CsvReplayDriver
from backend.adapters.simulated_driver import SimulatedDriver
from backend.domain.observation_semantics import ORDER_AFTER
from backend.domain.observation_semantics import compare_rfc3339_instants
from backend.domain.observation_semantics import require_valid_rfc3339_utc
from backend.importers.modbus_importer import commit_modbus_import
from backend.importers.modbus_importer import DEFAULT_MODBUS_IMPORT_CSV
from backend.importers.modbus_importer import preview_modbus_import
from backend.summary import acknowledge_generated_alarm
from backend.summary import apply_scenario
from backend.summary import create_alarm_rule
from backend.summary import DATABASE_DISPLAY_PATH
from backend.summary import DATABASE_FILE
from backend.summary import LOADER_COMMAND
from backend.summary import evaluate_generated_alarms
from backend.summary import evaluate_point_health
from backend.summary import get_alarm_correlations
from backend.summary import get_alarm_rule_catalog
from backend.summary import get_alarm_summary
from backend.summary import get_current_point_values
from backend.summary import get_corrective_actions
from backend.summary import get_equipment_inventory
from backend.summary import get_equipment_out_of_service_records
from backend.summary import get_alarm_events
from backend.summary import get_facility_scenarios
from backend.summary import get_generated_alarms
from backend.summary import get_incident_timeline
from backend.summary import get_operations_overview
from backend.summary import get_point_dictionary
from backend.summary import get_procedure_references
from backend.summary import get_reliability_reports
from backend.summary import get_rule_evaluations
from backend.summary import get_scenarios
from backend.summary import get_shift_turnover_notes
from backend.summary import update_alarm_rule
from backend.summary import update_current_point_value
from backend.services.csv_replay_runner import run_all_csv_replay_steps
from backend.services.csv_replay_runner import run_csv_replay_step
from backend.services.facility_topology_service import get_facility_topology
from backend.services.operational_reset_service import reset_operational_state
from backend.services.observation_package_service import get_replay_package_detail
from backend.services.observation_package_service import list_replay_packages
from backend.services.observation_replay_service import execute_replay_package
from backend.services.observation_replay_service import get_canonical_lineage
from backend.services.observation_replay_service import get_canonical_observation
from backend.services.observation_replay_service import get_replay_execution
from backend.services.observation_replay_service import (
    get_reported_observation_projection,
)
from backend.services.observation_replay_service import (
    get_reproducibility_manifest,
)
from backend.services.observation_replay_service import get_source_native_record
from backend.services.observation_replay_service import (
    list_canonical_observations,
)
from backend.services.observation_replay_service import list_redelivery_groups
from backend.services.observation_replay_service import list_source_native_records
from backend.services.observation_store import DEFAULT_OBSERVATION_DATABASE_FILE
from backend.services.observation_store import IdempotencyConflictError
from backend.services.observation_store import ImmutableIdentityConflictError
from backend.services.point_ingest_service import ingest_driver_samples
from backend.services.standards_basis_service import get_applicability_matrix
from backend.services.standards_basis_service import get_applicability_profile
from backend.services.standards_basis_service import get_controlled_sources
from backend.services.standards_basis_service import get_evidence_categories
from backend.services.standards_basis_service import get_standards_basis
from backend.services.standards_basis_service import get_standards_traceability
from backend.services.standards_basis_service import get_synthetic_requirements


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_FILE = PROJECT_ROOT / "frontend" / "index.html"
REPLAY_SAMPLE_FILE = PROJECT_ROOT / "data" / "replay_samples.csv"
MODBUS_IMPORT_SAMPLE_FILE = DEFAULT_MODBUS_IMPORT_CSV
OBSERVATION_DATABASE_FILE = DEFAULT_OBSERVATION_DATABASE_FILE

app = FastAPI(title="FacilityOps Copilot API")


def database_not_found_response():
    if not DATABASE_FILE.exists():
        return JSONResponse(
            status_code=404,
            content={
                "error": f"Database not found: {DATABASE_DISPLAY_PATH}",
                "run_first": LOADER_COMMAND,
            },
        )

    return None


@app.get("/summary")
def read_summary():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return get_alarm_summary()


@app.get("/equipment")
def read_equipment():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return {"equipment": get_equipment_inventory()}


@app.get("/facility-topology")
def read_facility_topology():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    try:
        return get_facility_topology(DATABASE_FILE)
    except LookupError as error:
        return JSONResponse(
            status_code=404,
            content={"error": str(error)},
        )


@app.get("/standards-basis")
def read_standards_basis():
    return get_standards_basis()


@app.get("/standards-basis/profile")
def read_standards_basis_profile():
    return get_applicability_profile()


@app.get("/standards-basis/controlled-sources")
def read_standards_basis_controlled_sources():
    return get_controlled_sources()


@app.get("/standards-basis/applicability-matrix")
def read_standards_basis_applicability_matrix():
    return get_applicability_matrix()


@app.get("/standards-basis/requirements")
def read_standards_basis_requirements():
    return get_synthetic_requirements()


@app.get("/standards-basis/evidence-categories")
def read_standards_basis_evidence_categories():
    return get_evidence_categories()


@app.get("/standards-basis/traceability")
def read_standards_basis_traceability():
    return get_standards_traceability()


def observation_api_error_response(error):
    if isinstance(
        error,
        (IdempotencyConflictError, ImmutableIdentityConflictError),
    ):
        status_code = 409
    elif isinstance(error, LookupError):
        status_code = 404
    else:
        status_code = 400
    return JSONResponse(
        status_code=status_code,
        content={"error": str(error)},
    )


def require_replay_execution(facility_id: str, replay_execution_id: str):
    return get_replay_execution(
        OBSERVATION_DATABASE_FILE,
        facility_id,
        replay_execution_id,
    )


@app.get("/facilities/{facility_id}/observation-replay/packages")
def read_observation_replay_packages(facility_id: str):
    try:
        result = list_replay_packages(facility_id)
        if not result["replay_packages"]:
            raise LookupError(
                "No allowlisted observation replay packages were found for "
                "the selected facility"
            )
        return result
    except (LookupError, ValueError) as error:
        return observation_api_error_response(error)


@app.get(
    "/facilities/{facility_id}/observation-replay/packages/"
    "{package_id}/versions/{package_version}"
)
def read_observation_replay_package(
    facility_id: str,
    package_id: str,
    package_version: str,
):
    try:
        return get_replay_package_detail(
            facility_id,
            package_id,
            package_version,
        )
    except (LookupError, ValueError) as error:
        return observation_api_error_response(error)


@app.post("/facilities/{facility_id}/observation-replay/executions")
def create_observation_replay_execution(
    facility_id: str,
    payload: dict | None = Body(default=None),
):
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=400,
            content={"error": "Observation replay request body must be an object"},
        )

    allowed_fields = {
        "package_id",
        "package_version",
        "idempotency_key",
        "replay_execution_id",
    }
    unknown_fields = sorted(set(payload) - allowed_fields)
    if unknown_fields:
        return JSONResponse(
            status_code=400,
            content={
                "error": (
                    "Observation replay request contains unsupported fields: "
                    + ", ".join(unknown_fields)
                )
            },
        )
    missing_fields = [
        field_name
        for field_name in (
            "package_id",
            "package_version",
            "idempotency_key",
        )
        if field_name not in payload
    ]
    if missing_fields:
        return JSONResponse(
            status_code=400,
            content={
                "error": (
                    "Observation replay request is missing required fields: "
                    + ", ".join(missing_fields)
                )
            },
        )

    try:
        return execute_replay_package(
            OBSERVATION_DATABASE_FILE,
            facility_id=facility_id,
            package_id=payload["package_id"],
            package_version=payload["package_version"],
            idempotency_key=payload["idempotency_key"],
            replay_execution_id=payload.get("replay_execution_id"),
        )
    except (
        LookupError,
        ValueError,
        IdempotencyConflictError,
        ImmutableIdentityConflictError,
    ) as error:
        return observation_api_error_response(error)


@app.get(
    "/facilities/{facility_id}/observation-replay/executions/"
    "{replay_execution_id}"
)
def read_observation_replay_execution(
    facility_id: str,
    replay_execution_id: str,
):
    try:
        return {
            "replay_execution": require_replay_execution(
                facility_id,
                replay_execution_id,
            )
        }
    except (LookupError, ValueError) as error:
        return observation_api_error_response(error)


@app.get(
    "/facilities/{facility_id}/observation-replay/executions/"
    "{replay_execution_id}/manifest"
)
def read_observation_replay_manifest(
    facility_id: str,
    replay_execution_id: str,
):
    try:
        require_replay_execution(facility_id, replay_execution_id)
        return {
            "reproducibility_manifest": get_reproducibility_manifest(
                OBSERVATION_DATABASE_FILE,
                facility_id,
                replay_execution_id,
            )
        }
    except (LookupError, ValueError) as error:
        return observation_api_error_response(error)


@app.get(
    "/facilities/{facility_id}/observation-replay/executions/"
    "{replay_execution_id}/source-native-records"
)
def read_source_native_records(
    facility_id: str,
    replay_execution_id: str,
    page: int = 1,
    page_size: int = 50,
    source_binding_id: str | None = None,
    source_event_group_key: str | None = None,
    observed_at_status: str | None = None,
):
    try:
        require_replay_execution(facility_id, replay_execution_id)
        return list_source_native_records(
            OBSERVATION_DATABASE_FILE,
            facility_id,
            replay_execution_id,
            page=page,
            page_size=page_size,
            source_binding_id=source_binding_id,
            source_event_group_key=source_event_group_key,
            observed_at_status=observed_at_status,
        )
    except (LookupError, ValueError) as error:
        return observation_api_error_response(error)


@app.get(
    "/facilities/{facility_id}/observation-replay/executions/"
    "{replay_execution_id}/source-native-records/{source_native_record_id}"
)
def read_source_native_record(
    facility_id: str,
    replay_execution_id: str,
    source_native_record_id: str,
):
    try:
        require_replay_execution(facility_id, replay_execution_id)
        record = get_source_native_record(
            OBSERVATION_DATABASE_FILE,
            facility_id,
            source_native_record_id,
        )
        if record["replay_execution_id"] != replay_execution_id:
            raise LookupError(
                "Source-native record not found for the selected replay execution"
            )
        return {"source_native_record": record}
    except (LookupError, ValueError) as error:
        return observation_api_error_response(error)


@app.get(
    "/facilities/{facility_id}/observation-replay/executions/"
    "{replay_execution_id}/canonical-observations"
)
def read_canonical_observations(
    facility_id: str,
    replay_execution_id: str,
    page: int = 1,
    page_size: int = 50,
    source_binding_id: str | None = None,
    point_id: str | None = None,
    mapping_id: str | None = None,
    observed_from: str | None = None,
    observed_to: str | None = None,
):
    try:
        require_replay_execution(facility_id, replay_execution_id)
        normalized_observed_from = (
            require_valid_rfc3339_utc(
                observed_from,
                field_name="observed_from",
            )
            if observed_from is not None
            else None
        )
        normalized_observed_to = (
            require_valid_rfc3339_utc(
                observed_to,
                field_name="observed_to",
            )
            if observed_to is not None
            else None
        )
        if (
            normalized_observed_from is not None
            and normalized_observed_to is not None
            and compare_rfc3339_instants(
                normalized_observed_from,
                normalized_observed_to,
            )
            == ORDER_AFTER
        ):
            raise ValueError(
                "observed_from must not be after observed_to"
            )
        return list_canonical_observations(
            OBSERVATION_DATABASE_FILE,
            facility_id,
            replay_execution_id,
            page=page,
            page_size=page_size,
            source_binding_id=source_binding_id,
            point_id=point_id,
            mapping_id=mapping_id,
            observed_from=normalized_observed_from,
            observed_to=normalized_observed_to,
        )
    except (LookupError, ValueError) as error:
        return observation_api_error_response(error)


@app.get(
    "/facilities/{facility_id}/observation-replay/executions/"
    "{replay_execution_id}/canonical-observations/"
    "{canonical_observation_id}"
)
def read_canonical_observation(
    facility_id: str,
    replay_execution_id: str,
    canonical_observation_id: str,
):
    try:
        require_replay_execution(facility_id, replay_execution_id)
        observation = get_canonical_observation(
            OBSERVATION_DATABASE_FILE,
            facility_id,
            canonical_observation_id,
        )
        if observation["replay_execution_id"] != replay_execution_id:
            raise LookupError(
                "Canonical observation not found for the selected replay "
                "execution"
            )
        return {"canonical_observation": observation}
    except (LookupError, ValueError) as error:
        return observation_api_error_response(error)


@app.get(
    "/facilities/{facility_id}/observation-replay/executions/"
    "{replay_execution_id}/canonical-observations/"
    "{canonical_observation_id}/lineage"
)
def read_canonical_observation_lineage(
    facility_id: str,
    replay_execution_id: str,
    canonical_observation_id: str,
):
    try:
        require_replay_execution(facility_id, replay_execution_id)
        result = get_canonical_lineage(
            OBSERVATION_DATABASE_FILE,
            facility_id,
            canonical_observation_id,
        )
        if (
            result["canonical_observation"]["replay_execution_id"]
            != replay_execution_id
        ):
            raise LookupError(
                "Canonical lineage not found for the selected replay execution"
            )
        return result
    except (LookupError, ValueError) as error:
        return observation_api_error_response(error)


@app.get(
    "/facilities/{facility_id}/observation-replay/executions/"
    "{replay_execution_id}/redelivery-groups"
)
def read_observation_redelivery_groups(
    facility_id: str,
    replay_execution_id: str,
    page: int = 1,
    page_size: int = 50,
):
    try:
        require_replay_execution(facility_id, replay_execution_id)
        return list_redelivery_groups(
            OBSERVATION_DATABASE_FILE,
            facility_id,
            replay_execution_id,
            page=page,
            page_size=page_size,
        )
    except (LookupError, ValueError) as error:
        return observation_api_error_response(error)


@app.get(
    "/facilities/{facility_id}/observation-replay/executions/"
    "{replay_execution_id}/reported-observation-projection"
)
def read_reported_observation_projection(
    facility_id: str,
    replay_execution_id: str,
    source_binding_id: str,
    point_id: str,
    mapping_id: str,
    mapping_version: str,
    mapping_digest: str,
    as_of_observed_at: str,
    known_by_received_at: str,
):
    try:
        require_replay_execution(facility_id, replay_execution_id)
        return get_reported_observation_projection(
            OBSERVATION_DATABASE_FILE,
            facility_id=facility_id,
            replay_execution_id=replay_execution_id,
            source_binding_id=source_binding_id,
            point_id=point_id,
            mapping_id=mapping_id,
            mapping_version=mapping_version,
            mapping_digest=mapping_digest,
            as_of_observed_at=as_of_observed_at,
            known_by_received_at=known_by_received_at,
        )
    except (LookupError, ValueError) as error:
        return observation_api_error_response(error)


@app.get("/operations/overview")
def read_operations_overview():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return get_operations_overview()


@app.get("/facility-scenarios")
def read_facility_scenarios():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return {"facility_scenarios": get_facility_scenarios()}


@app.get("/alarm-correlations")
def read_alarm_correlations():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return {"alarm_correlations": get_alarm_correlations()}


@app.get("/incident-timeline")
def read_incident_timeline():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return {"incident_timeline": get_incident_timeline()}


@app.get("/shift-turnover")
def read_shift_turnover_notes():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return {"shift_turnover": get_shift_turnover_notes()}


@app.get("/equipment-out-of-service")
def read_equipment_out_of_service_records():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return {
        "equipment_out_of_service": get_equipment_out_of_service_records(),
    }


@app.get("/corrective-actions")
def read_corrective_actions():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return {"corrective_actions": get_corrective_actions()}


@app.get("/procedure-references")
def read_procedure_references():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return {"procedure_references": get_procedure_references()}


@app.get("/reliability-reports")
def read_reliability_reports():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return {"reliability_reports": get_reliability_reports()}


@app.get("/points")
def read_points():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return {"points": get_point_dictionary()}


@app.get("/alarm-rules")
def read_alarm_rules():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return {"alarm_rules": get_alarm_rule_catalog()}


@app.post("/alarm-rules")
def create_alarm_rule_state(payload: dict = Body(...)):
    error_response = database_not_found_response()
    if error_response:
        return error_response

    try:
        alarm_rule = create_alarm_rule(payload)
    except LookupError as error:
        return JSONResponse(
            status_code=404,
            content={"error": str(error)},
        )
    except ValueError as error:
        return JSONResponse(
            status_code=400,
            content={"error": str(error)},
        )

    return {"alarm_rule": alarm_rule}


@app.put("/alarm-rules/{rule_id}")
def update_alarm_rule_state(rule_id: str, payload: dict = Body(...)):
    error_response = database_not_found_response()
    if error_response:
        return error_response

    try:
        alarm_rule = update_alarm_rule(rule_id, payload)
    except LookupError as error:
        return JSONResponse(
            status_code=404,
            content={"error": str(error)},
        )
    except ValueError as error:
        return JSONResponse(
            status_code=400,
            content={"error": str(error)},
        )

    return {"alarm_rule": alarm_rule}


@app.get("/current-point-values")
def read_current_point_values():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return {"current_point_values": get_current_point_values()}


@app.put("/current-point-values/{point_id}")
def update_point_value(point_id: str, payload: dict = Body(...)):
    error_response = database_not_found_response()
    if error_response:
        return error_response

    if "value" not in payload:
        return JSONResponse(
            status_code=400,
            content={"error": "Missing required field: value"},
        )

    sample_options = {}
    for field_name in (
        "source_timestamp",
        "received_timestamp",
        "protocol",
        "address",
        "stale_after_seconds",
        "overridden",
        "out_of_service",
        "created_by",
    ):
        if field_name in payload:
            sample_options[field_name] = payload[field_name]

    try:
        current_point_value = update_current_point_value(
            point_id,
            payload["value"],
            quality=payload.get("quality", "GOOD"),
            source=payload.get("source", "MANUAL"),
            **sample_options,
        )
    except LookupError as error:
        return JSONResponse(
            status_code=404,
            content={"error": str(error)},
        )
    except ValueError as error:
        return JSONResponse(
            status_code=400,
            content={"error": str(error)},
        )

    return {"current_point_value": current_point_value}


@app.get("/rule-evaluations")
def read_rule_evaluations():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return {"rule_evaluations": get_rule_evaluations()}


@app.get("/generated-alarms")
def read_generated_alarms():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return {"generated_alarms": get_generated_alarms()}


@app.get("/alarm-events")
def read_alarm_events():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return {"alarm_events": get_alarm_events()}


@app.post("/point-health/evaluate")
def evaluate_point_health_state():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return evaluate_point_health()


@app.post("/drivers/simulated/read")
def read_simulated_driver_samples():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    driver = SimulatedDriver()
    samples = driver.read_samples()
    return ingest_driver_samples(samples)


@app.post("/drivers/csv-replay/read")
def read_csv_replay_driver_samples(payload: dict | None = Body(default=None)):
    error_response = database_not_found_response()
    if error_response:
        return error_response

    payload = payload or {}
    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=400,
            content={"error": "CSV replay request body must be an object"},
        )

    driver = CsvReplayDriver(REPLAY_SAMPLE_FILE)
    try:
        samples = driver.read_samples(sequence=payload.get("sequence"))
    except ValueError as error:
        return JSONResponse(
            status_code=400,
            content={"error": str(error)},
        )

    summary = ingest_driver_samples(samples)
    return {
        "samples_read": len(samples),
        "samples_ingested": summary["samples_ingested"],
        "failed_samples": summary["failed_samples"],
    }


@app.post("/replay/csv/step")
def run_csv_replay_sequence_step(payload: dict | None = Body(default=None)):
    error_response = database_not_found_response()
    if error_response:
        return error_response

    payload = payload or {}
    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=400,
            content={"error": "CSV replay step request body must be an object"},
        )

    try:
        return run_csv_replay_step(
            payload.get("sequence"),
            REPLAY_SAMPLE_FILE,
            db_path=DATABASE_FILE,
        )
    except LookupError as error:
        return JSONResponse(
            status_code=404,
            content={"error": str(error)},
        )
    except ValueError as error:
        return JSONResponse(
            status_code=400,
            content={"error": str(error)},
        )


@app.post("/replay/csv/run-all")
def run_all_csv_replay_sequences():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    try:
        return run_all_csv_replay_steps(REPLAY_SAMPLE_FILE, db_path=DATABASE_FILE)
    except ValueError as error:
        return JSONResponse(
            status_code=400,
            content={"error": str(error)},
        )


@app.post("/imports/modbus/preview")
def preview_modbus_register_map(payload: dict | None = Body(default=None)):
    error_response = database_not_found_response()
    if error_response:
        return error_response

    payload = payload or {}
    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=400,
            content={"error": "Modbus import preview body must be an object"},
        )

    return preview_modbus_import(
        payload.get("csv_path", MODBUS_IMPORT_SAMPLE_FILE),
        db_path=DATABASE_FILE,
    )


@app.post("/imports/modbus/commit")
def commit_modbus_register_map(payload: dict | None = Body(default=None)):
    error_response = database_not_found_response()
    if error_response:
        return error_response

    payload = payload or {}
    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=400,
            content={"error": "Modbus import commit body must be an object"},
        )

    result = commit_modbus_import(
        payload.get("csv_path", MODBUS_IMPORT_SAMPLE_FILE),
        db_path=DATABASE_FILE,
    )
    if not result["committed"]:
        return JSONResponse(status_code=400, content=result)

    return result


@app.post("/generated-alarms/{alarm_id}/acknowledge")
def acknowledge_generated_alarm_state(alarm_id: str, payload: dict | None = Body(default=None)):
    error_response = database_not_found_response()
    if error_response:
        return error_response

    payload = payload or {}
    try:
        generated_alarm = acknowledge_generated_alarm(
            alarm_id,
            acknowledged_by=payload.get("acknowledged_by", "local-operator"),
        )
    except LookupError as error:
        return JSONResponse(
            status_code=404,
            content={"error": str(error)},
        )

    return {"generated_alarm": generated_alarm}


@app.post("/generated-alarms/evaluate")
def evaluate_generated_alarm_state():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return evaluate_generated_alarms()


@app.get("/scenarios")
def read_scenarios():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return {"scenarios": get_scenarios()}


@app.post("/scenario/reset-operational-state")
def reset_scenario_operational_state():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    try:
        return reset_operational_state(db_path=DATABASE_FILE)
    except (LookupError, ValueError) as error:
        return JSONResponse(
            status_code=409,
            content={"error": str(error)},
        )


@app.post("/scenarios/{scenario_id}/apply")
def apply_alarm_scenario(scenario_id: str):
    error_response = database_not_found_response()
    if error_response:
        return error_response

    try:
        return apply_scenario(scenario_id)
    except LookupError as error:
        return JSONResponse(
            status_code=404,
            content={"error": str(error)},
        )
    except ValueError as error:
        return JSONResponse(
            status_code=400,
            content={"error": str(error)},
        )


def dashboard_response():
    return FileResponse(FRONTEND_FILE)


@app.get("/")
def read_root_dashboard():
    return dashboard_response()


@app.get("/dashboard")
def read_dashboard():
    return dashboard_response()
