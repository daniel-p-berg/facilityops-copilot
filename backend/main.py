from pathlib import Path

from fastapi import Body
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse

from backend.summary import acknowledge_generated_alarm
from backend.summary import apply_scenario
from backend.summary import create_alarm_rule
from backend.summary import DATABASE_DISPLAY_PATH
from backend.summary import DATABASE_FILE
from backend.summary import LOADER_COMMAND
from backend.summary import evaluate_generated_alarms
from backend.summary import get_alarm_rule_catalog
from backend.summary import get_alarm_summary
from backend.summary import get_current_point_values
from backend.summary import get_equipment_inventory
from backend.summary import get_generated_alarms
from backend.summary import get_point_dictionary
from backend.summary import get_rule_evaluations
from backend.summary import get_scenarios
from backend.summary import update_alarm_rule
from backend.summary import update_current_point_value


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_FILE = PROJECT_ROOT / "frontend" / "index.html"

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


@app.get("/dashboard")
def read_dashboard():
    return FileResponse(FRONTEND_FILE)
