# FacilityOps Copilot

FacilityOps Copilot is a vendor-neutral, externally read-only critical-environment operations, commissioning, training, and decision-support laboratory. It uses fictional local data to make facility behavior, operational consequences, response decisions, and supporting evidence understandable and reproducible without creating a control path to a physical facility.

The approved product direction is defined by the change-controlled [`docs/PRODUCT_CHARTER.md`](docs/PRODUCT_CHARTER.md). This README is the practical entry point for the repository; it does not replace the governance documents or imply that planned capabilities are implemented.

## Governance And Current Status

- [`docs/PRODUCT_CHARTER.md`](docs/PRODUCT_CHARTER.md) defines the approved product purpose, boundaries, principles, and non-goals.
- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) separates verified implemented behavior from partial, planned, and unverified behavior.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) defines the approved milestone order and acceptance evidence.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) describes the implemented architecture separately from planned direction.
- [`docs/FLAGSHIP_FACILITY.md`](docs/FLAGSHIP_FACILITY.md) describes the planned fictional flagship facility and golden scenario; neither is currently implemented.
- [`docs/decisions/README.md`](docs/decisions/README.md) defines the ADR process and lists unresolved architectural decisions.

Authoritative alarm, point-condition, equipment, system, facility, consequence, and functional-test determinations belong to deterministic, testable code. Any future AI capability is advisory only: it must cite authoritative evidence, express uncertainty, and remain unable to change authoritative state or acceptance results. AI-assisted development is part of the project history, not the product mission.

The repository currently uses fictional local data and does not connect to a live BAS, EPMS, PLC, SCADA, DCIM, Modbus device, or customer system. External commands, configuration changes, and write-back are outside the product boundary. Local laboratory writes for simulation, replay, scenarios, alarm evaluation, acknowledgements, audit, testing, and local configuration are allowed.

## Local SQLite Facility Database

The sample equipment, point, current point value, and alarm rule CSV files can be loaded into a local SQLite database:

```bash
python3 analysis/load_alarm_db.py
```

The loader reads the catalog and current value CSV files in `data/`, creates `db/facilityops.sqlite3`, and prints a verification summary. Generated alarms start empty after each loader reset.

Generated database files are local development artifacts and are ignored by git.

## Facility And Equipment Context

The implemented environment is **Northstar Data Hall**, a fictional mission-critical data hall documented in [`docs/facility_model.md`](docs/facility_model.md). Northstar is the preserved legacy fixture, regression environment, and secondary data-center demonstration.

The planned flagship is the fictional **Advanced Materials Research and Precision-Environment Facility**. Its planned first golden scenario is a **process-exhaust failure causing pressure-cascade degradation**. The flagship catalog, topology, scenario, higher-level state layers, and deterministic consequence engine are not implemented; their scope and sequencing are governed by the roadmap and ADR process.

Equipment inventory is stored in `data/sample_equipment.csv` and loaded into SQLite with the point, current value, and alarm rule data. The inventory adds context such as equipment type, location, criticality, and source system.

Point dictionary records are stored in `data/sample_points.csv`. Current point values are stored in `data/sample_current_point_values.csv`. Alarm rule catalog records are stored in `data/sample_alarm_rules.csv`.

During normal ingestion, each update appends a `point_samples` history row and updates the latest-value `current_point_values` projection. Current point values can be updated manually through the dashboard or the local API. Manual updates create a point sample, update the latest-value projection, use `MANUAL` as the current value source, and do not automatically evaluate generated alarms. This history is not durable across operational reset: reset currently deletes point samples and reseeds the laboratory baseline.

Alarm rules can be created for existing points through the dashboard or the local API for local demo tuning. Existing rule edits are limited to thresholds, clear values, delay, severity, enabled state, and alarm message; creating or editing rules does not automatically evaluate or rewrite generated alarms. Rule creation and edits append `alarm_events` audit rows during normal operation, but those rows are not retained across operational reset.

Point sample health changes are also recorded in `alarm_events`: quality changes, override changes, out-of-service changes, and stale samples found by the explicit point health evaluation endpoint. The app does not run a background staleness scheduler.

The backend includes a small read-only `SimulatedDriver` adapter for deterministic local point reads. `POST /drivers/simulated/read` ingests those samples through the same point sample path used by manual updates and scenarios, updates the current value projection, and does not automatically evaluate generated alarms.

The backend also includes a read-only `CsvReplayDriver` adapter for deterministic point sample replay from `data/replay_samples.csv`. `POST /drivers/csv-replay/read` can ingest all replay samples or a specific sequence step, updates the current value projection, and does not automatically evaluate generated alarms.

The CSV replay runner is the explicit operator/test workflow for replay sequences. `POST /replay/csv/step` runs one selected replay sequence by reading CSV samples, ingesting them, and then evaluating generated alarms at the replay sample timestamp. `POST /replay/csv/run-all` runs every replay sequence in deterministic order. The lower-level CSV replay driver endpoint remains ingest-only.

The backend includes a static Modbus register map importer for local catalog setup only. `POST /imports/modbus/preview` validates a CSV register map without database writes. `POST /imports/modbus/commit` validates again, then creates or updates equipment and point catalog records with `MODBUS` protocol/address metadata. The importer does not poll Modbus devices, create point samples, update current point values, evaluate alarm rules, or create generated alarms.

Alarm scenarios are deterministic dashboard and API controls that set known current point values into alarm or normal demo conditions. Scenario updates create point samples, use `SCENARIO` as the current value source, and do not automatically evaluate generated alarms.

The dashboard also includes a deterministic operations overview for an end-to-end facility scenario: utility disturbance, ATS source loss indication, UPS battery support, generator fuel readiness constraint, and CRAC supply temperature drift. This overview is seeded local data, not an AI-generated root cause engine. It demonstrates explainable correlation evidence, event history, shift turnover notes, equipment out-of-service records, corrective actions, MOP/SOP/EOP references, and management-level reliability reporting.

The operational reset endpoint restores the local sandbox to a deterministic runtime baseline without deleting catalog configuration. `POST /scenario/reset-operational-state` clears generated alarms and alarm/audit events, replaces point samples with the seeded baseline samples, and resets current point values from `data/sample_current_point_values.csv`. Equipment, points, alarm rules, imported Modbus point catalog records, and point protocol/address metadata are preserved.

Rule evaluations are read-only, stateless checks of the alarm rule catalog against current point values. Process alarm rules only evaluate against eligible samples: `GOOD` quality, not stale, not overridden, and not out of service. `UNKNOWN` quality is normalized to `UNCERTAIN`.

Generated alarms are simple output records created from rule evaluations. The dashboard alarm summary and alarm table use generated alarms only; the old seeded sample alarm CSV is no longer the dashboard alarm source. Triggered rules with positive `delay_seconds` create PENDING generated alarms until a later explicit evaluation confirms the delay has elapsed. Rules with no delay create ACTIVE generated alarms immediately. Analog generated alarms use `clear_value` hysteresis before clearing; boolean and enum generated alarms clear when their rule no longer triggers. Local operators can acknowledge generated alarms from the dashboard or API; acknowledgement does not clear, suppress, or stop future evaluations. Generated alarm lifecycle transitions append `alarm_events` rows for local audit review during normal operation. Operational reset deletes generated alarms and audit events before reseeding the laboratory baseline, so the current implementation is not a durable event-sourcing or incident-evidence system. The app does not run a background timer or polling loop, and it does not implement suppression, latching, comments, or shelving.

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

The dashboard calls `/summary`, `/operations/overview`, `/scenarios`, `/scenario/reset-operational-state`, `/drivers/simulated/read`, `/drivers/csv-replay/read`, `/replay/csv/step`, `/replay/csv/run-all`, `/imports/modbus/preview`, `/imports/modbus/commit`, `/generated-alarms`, `/alarm-events`, `/current-point-values`, `/rule-evaluations`, `/points`, and `/alarm-rules` and displays generated alarm totals, operations scenario context, explainable alarm correlation, incident timeline, shift turnover, equipment OOS records, corrective actions, procedure references, reliability reporting, alarm scenarios, generated alarms, alarm/audit events, current point values, alarm rule evaluations, the point dictionary, and the alarm rule catalog. Current values can be updated, operational state can be reset, simulated driver samples can be read, CSV replay samples can be read, CSV replay steps can be run with explicit alarm evaluation, the sample Modbus register map can be previewed and committed, point health can be evaluated, and alarm rules can be created or edited from the dashboard.

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

Preview the sample static Modbus register map:

```bash
curl -X POST http://127.0.0.1:8000/imports/modbus/preview \
  -H "Content-Type: application/json" \
  -d '{}'
```

Commit the sample static Modbus register map after reviewing preview errors and warnings:

```bash
curl -X POST http://127.0.0.1:8000/imports/modbus/commit \
  -H "Content-Type: application/json" \
  -d '{}'
```

Run one CSV replay step and explicitly evaluate generated alarms after ingest:

```bash
curl -X POST http://127.0.0.1:8000/replay/csv/step \
  -H "Content-Type: application/json" \
  -d '{"sequence": 2}'
```

Run every CSV replay step in deterministic order:

```bash
curl -X POST http://127.0.0.1:8000/replay/csv/run-all
```

Reset volatile operational state to the seeded local baseline:

```bash
curl -X POST http://127.0.0.1:8000/scenario/reset-operational-state
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

Call the operations overview endpoint:

```bash
curl http://127.0.0.1:8000/operations/overview
```

Apply an alarm scenario:

```bash
curl -X POST http://127.0.0.1:8000/scenarios/trigger-ups-high-load/apply
```

Apply the end-to-end facility scenario, then explicitly evaluate generated alarms:

```bash
curl -X POST http://127.0.0.1:8000/scenarios/trigger-utility-cooling-event/apply
curl -X POST http://127.0.0.1:8000/generated-alarms/evaluate
```

Call the read-only rule evaluations endpoint:

```bash
curl http://127.0.0.1:8000/rule-evaluations
```

Call the generated alarms endpoint:

```bash
curl http://127.0.0.1:8000/generated-alarms
```

Call the generated alarm event audit trail endpoint:

```bash
curl http://127.0.0.1:8000/alarm-events
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

## Current Stack

- Python
- SQLite
- FastAPI
- Uvicorn
- Plain HTML and JavaScript dashboard
- Markdown reports

## Planned Direction

The approved roadmap incrementally adds the minimum flagship topology, explicit deterministic point/equipment/system/facility state, operational consequences, durable provenance, bounded operator and commissioning workflows, a vendor-neutral read-only adapter proof, and an optional advisory AI layer. These capabilities remain planned until [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) records verified implementation.
