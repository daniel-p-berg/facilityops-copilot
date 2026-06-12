# FacilityOps Copilot

FacilityOps Copilot is a simulated BMS/EPMS monitoring stack for mission-critical facility operations.

The project uses sample building automation and electrical power monitoring data to demonstrate how equipment records, point catalogs, current point values, alarm rule catalogs, and generated alarms can be stored, evaluated, and displayed for operations review.

## Project Goals

- Practice Git and GitHub workflow
- Build a simple full-stack application over time
- Model realistic BMS/EPMS equipment, point, current value, alarm rule, and generated alarm data
- Create a local database for operational records
- Expose summary data through a backend API
- Build a simple dashboard for operations review
- Generate daily facility operations briefings
- Explore how AI-assisted coding can expand the capabilities of controls technicians

## Initial Scope

The first version uses simulated data only. It does not connect to live BMS, EPMS, Niagara, Schneider, BACnet, Modbus, or customer systems.

## Local SQLite Facility Database

The sample equipment, point, current point value, and alarm rule CSV files can be loaded into a local SQLite database:

```bash
python3 analysis/load_alarm_db.py
```

The loader reads the catalog and current value CSV files in `data/`, creates `db/facilityops.sqlite3`, and prints a verification summary. Generated alarms start empty after each loader reset.

Generated database files are local development artifacts and are ignored by git.

## Facility And Equipment Context

The simulated facility is **Northstar Data Hall**, a fictional mission-critical data hall documented in `docs/facility_model.md`.

Equipment inventory is stored in `data/sample_equipment.csv` and loaded into SQLite with the point, current value, and alarm rule data. The inventory adds context such as equipment type, location, criticality, and source system.

Point dictionary records are stored in `data/sample_points.csv`. Current point values are stored in `data/sample_current_point_values.csv`. Alarm rule catalog records are stored in `data/sample_alarm_rules.csv`.

Current point values are maintained as the latest-value projection of append-only `point_samples` records. Current point values can be updated manually through the dashboard or the local API. Manual updates create a point sample, update the latest-value projection, use `MANUAL` as the current value source, and do not automatically evaluate generated alarms.

Alarm rules can be created for existing points through the dashboard or the local API for local demo tuning. Existing rule edits are limited to thresholds, clear values, delay, severity, enabled state, and alarm message; creating or editing rules does not automatically evaluate or rewrite generated alarms.

Alarm scenarios are deterministic dashboard and API controls that set known current point values into alarm or normal demo conditions. Scenario updates create point samples, use `SCENARIO` as the current value source, and do not automatically evaluate generated alarms.

Rule evaluations are read-only, stateless checks of the alarm rule catalog against current point values. Process alarm rules only evaluate against eligible samples: `GOOD` quality, not stale, not overridden, and not out of service. `UNKNOWN` quality is normalized to `UNCERTAIN`.

Generated alarms are simple output records created from rule evaluations. The dashboard alarm summary and alarm table use generated alarms only; the old seeded sample alarm CSV is no longer the dashboard alarm source. Triggered rules with positive `delay_seconds` create PENDING generated alarms until a later explicit evaluation confirms the delay has elapsed. Rules with no delay create ACTIVE generated alarms immediately. Analog generated alarms use `clear_value` hysteresis before clearing; boolean and enum generated alarms clear when their rule no longer triggers. Local operators can acknowledge generated alarms from the dashboard or API; acknowledgement does not clear, suppress, or stop future evaluations. The app does not run a background timer or polling loop, and it does not implement suppression, latching, comments, shelving, or a separate alarm history table.

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

The dashboard calls `/summary`, `/scenarios`, `/generated-alarms`, `/current-point-values`, `/rule-evaluations`, `/points`, and `/alarm-rules` and displays generated alarm totals, alarm scenarios, generated alarms, current point values, alarm rule evaluations, the point dictionary, and the alarm rule catalog. Current values can be updated and alarm rules can be created or edited from the dashboard.

To create generated alarms for a demo, apply an alarm scenario or manually update a current point value, review `/rule-evaluations`, then run generated alarm evaluation. Applying scenarios or manual point updates does not automatically create generated alarms.

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

Manually update a current point value:

```bash
curl -X PUT http://127.0.0.1:8000/current-point-values/UPS-A_OUTPUT_KW \
  -H "Content-Type: application/json" \
  -d '{"value": "245", "quality": "GOOD", "source": "MANUAL"}'
```

List alarm scenarios:

```bash
curl http://127.0.0.1:8000/scenarios
```

Apply an alarm scenario:

```bash
curl -X POST http://127.0.0.1:8000/scenarios/trigger-ups-high-load/apply
```

Call the read-only rule evaluations endpoint:

```bash
curl http://127.0.0.1:8000/rule-evaluations
```

Call the generated alarms endpoint:

```bash
curl http://127.0.0.1:8000/generated-alarms
```

Run generated alarm evaluation:

```bash
curl -X POST http://127.0.0.1:8000/generated-alarms/evaluate
```

Call the alarm rule catalog endpoint:

```bash
curl http://127.0.0.1:8000/alarm-rules
```

Create an alarm rule for an existing point:

```bash
curl -X POST http://127.0.0.1:8000/alarm-rules \
  -H "Content-Type: application/json" \
  -d '{"id":"RULE-TEST-UPS-HIGH-LOAD","point_id":"UPS-A_OUTPUT_KW","rule_name":"Test UPS high load","rule_type":"analog_limit","operator":">","threshold_value":"250","clear_value":"230","delay_seconds":60,"severity":"Warning","enabled":true,"alarm_message":"UPS-A load is above edited threshold"}'
```

Update an existing alarm rule:

```bash
curl -X PUT http://127.0.0.1:8000/alarm-rules/RULE-UPS-A-HIGH-LOAD \
  -H "Content-Type: application/json" \
  -d '{"threshold_value":"250","clear_value":"230","delay_seconds":60,"severity":"Warning","enabled":true,"alarm_message":"UPS-A load is above edited threshold"}'
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
