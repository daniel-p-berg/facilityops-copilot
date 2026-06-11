from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse

from backend.summary import DATABASE_DISPLAY_PATH
from backend.summary import DATABASE_FILE
from backend.summary import LOADER_COMMAND
from backend.summary import get_alarm_summary
from backend.summary import get_equipment_inventory


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


@app.get("/dashboard")
def read_dashboard():
    return FileResponse(FRONTEND_FILE)
