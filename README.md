# FacilityOps Copilot

FacilityOps Copilot is a simulated BMS/EPMS monitoring stack for mission-critical facility operations.

The project uses sample building automation and electrical power monitoring data to demonstrate how alarms, equipment records, point catalogs, current point values, and alarm rule catalogs can be stored, analyzed, and summarized into an operations briefing.

## Project Goals

- Practice Git and GitHub workflow
- Build a simple full-stack application over time
- Model realistic BMS/EPMS alarm, equipment, point, current value, and alarm rule data
- Create a local database for operational records
- Expose summary data through a backend API
- Build a simple dashboard for operations review
- Generate daily facility operations briefings
- Explore how AI-assisted coding can expand the capabilities of controls technicians

## Initial Scope

The first version uses simulated data only. It does not connect to live BMS, EPMS, Niagara, Schneider, BACnet, Modbus, or customer systems.

## Local SQLite Facility Database

The sample alarm, equipment, point, current point value, and alarm rule CSV files can be loaded into a local SQLite database:

```bash
python3 analysis/load_alarm_db.py
```

The loader reads the sample CSV files in `data/`, creates `db/facilityops.sqlite3`, and prints a verification summary with total records and alarm counts by severity, source, and equipment.

After loading the database, generate a database-backed daily briefing:

```bash
python3 analysis/generate_db_briefing.py
```

The database-backed briefing is written to `reports/daily_briefing_from_db.md`.

Generated database files are local development artifacts and are ignored by git.

## Facility And Equipment Context

The simulated facility is **Northstar Data Hall**, a fictional mission-critical data hall documented in `docs/facility_model.md`.

Equipment inventory is stored in `data/sample_equipment.csv` and loaded into SQLite with the alarm data. The inventory adds context such as equipment type, location, criticality, and source system.

Point dictionary records are stored in `data/sample_points.csv`. Current point values are stored in `data/sample_current_point_values.csv`. Alarm rule catalog records are stored in `data/sample_alarm_rules.csv`.

Rule evaluations are read-only, stateless checks of the alarm rule catalog against current point values. They do not create generated alarms, alarm lifecycle state, acknowledgements, suppression, latching, clearing, or history.

## Local API Server

Create a local virtual environment and install the API dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Load the SQLite database before starting the API:

```bash
python3 analysis/load_alarm_db.py
```

Start the FastAPI server:

```bash
.venv/bin/python -m uvicorn backend.main:app --reload
```

Open the dashboard:

```text
http://127.0.0.1:8000/dashboard
```

The dashboard calls `/summary`, `/current-point-values`, `/rule-evaluations`, `/points`, and `/alarm-rules` and displays alarm totals, active Critical alarms, current point values, alarm rule evaluations, the point dictionary, and the alarm rule catalog.

Call the summary endpoint directly:

```bash
curl http://127.0.0.1:8000/summary
```

Call the equipment inventory endpoint:

```bash
curl http://127.0.0.1:8000/equipment
```

Call the point dictionary endpoint:

```bash
curl http://127.0.0.1:8000/points
```

Call the current point values endpoint:

```bash
curl http://127.0.0.1:8000/current-point-values
```

Call the read-only rule evaluations endpoint:

```bash
curl http://127.0.0.1:8000/rule-evaluations
```

Call the alarm rule catalog endpoint:

```bash
curl http://127.0.0.1:8000/alarm-rules
```

The `.venv` folder is local development environment data and should not be committed.

## Running Tests

Run the standard-library unittest suite:

```bash
python3 -m unittest discover -s tests
```

## Planned Stack

- Git and GitHub
- Python
- SQLite
- FastAPI
- Pandas
- HTML dashboard
- Markdown reports
- AI-assisted coding tools

## Long-Term Vision

The long-term goal is to explore how AI agents could assist facilities teams by monitoring alarms, identifying recurring issues, summarizing equipment behavior, and helping operators understand the full context behind BMS and EPMS events.
