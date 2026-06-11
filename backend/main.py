from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse

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


@app.get("/current-point-values")
def read_current_point_values():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return {"current_point_values": get_current_point_values()}


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


@app.post("/generated-alarms/evaluate")
def evaluate_generated_alarm_state():
    error_response = database_not_found_response()
    if error_response:
        return error_response

    return evaluate_generated_alarms()


@app.get("/dashboard")
def read_dashboard():
    return FileResponse(FRONTEND_FILE)
