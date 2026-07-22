# FacilityOps Copilot

FacilityOps Copilot is a standards-grounded technical laboratory for critical-environment facilities operations, reliability, controls, and OT assurance. It uses a fictional facility and deterministic scenarios to study how heterogeneous source indications can be normalized, interpreted, compared with versioned synthetic control intent, and reconstructed after an event without creating a control path to a physical facility.

The project prioritizes transferable facilities knowledge, disciplined engineering reasoning, a coherent flagship proof, and technical portfolio value. A possible read-only controls-assurance capability remains a research hypothesis; FacilityOps is not a commercially validated product, universal compliance engine, general facilities integration platform, BAS or SCADA replacement, or AI safety authority.

The approved direction is defined by the change-controlled [`docs/PRODUCT_CHARTER.md`](docs/PRODUCT_CHARTER.md). This README preserves practical setup, API, verification, and implemented-behavior instructions; it does not replace the governance documents or imply that planned capabilities are implemented.

## Governance And Current Status

- [`docs/PRODUCT_CHARTER.md`](docs/PRODUCT_CHARTER.md) defines the approved product purpose, boundaries, principles, and non-goals.
- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) separates verified implemented behavior from partial, planned, and unverified behavior.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) defines the approved milestone order and completion evidence.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) describes the implemented architecture separately from planned direction.
- [`docs/FLAGSHIP_FACILITY.md`](docs/FLAGSHIP_FACILITY.md) describes the fictional flagship facility. Its minimum Milestone 2 topology and Milestone 3 applicability and inactive requirement basis are implemented; observations, inference, evaluation, and the golden scenario remain planned.
- [`docs/STANDARDS_POSITION.md`](docs/STANDARDS_POSITION.md) defines how controlled references, applicability, synthetic requirements, bounded findings, and human disposition remain distinct.
- [`docs/decisions/README.md`](docs/decisions/README.md) defines the ADR process, indexes accepted ADRs 0001–0004, and maintains the consolidated unresolved-decision backlog.

Deterministic code owns reproducible computation. It produces computed point conditions, inferred states, timing results, replay outputs, evaluations, and bounded findings under identified inputs, assumptions, configuration, and rules. Determinism provides reproducibility, not automatic validity. Qualified personnel retain authority for applicability decisions, requirement approval, test authorization, operational action, commissioning acceptance, waivers, and final disposition.

A canonical observation remains a reported indication and does not independently prove physical state. A human action must lead to new observations and a separate recovery evaluation; recording an action does not prove its physical effect. Any future AI capability is advisory only and cannot approve its own output, mutate controlled computation, exercise qualified human authority, or command a physical system.

The repository currently uses fictional local data and does not connect to a live BAS, EPMS, PLC, SCADA, DCIM, Modbus device, or customer system. External commands, configuration changes, and write-back are outside the product boundary. Local laboratory writes for simulation, replay, scenarios, alarm evaluation, acknowledgements, audit, testing, and local configuration are allowed.

## Local SQLite Facility Database

The sample equipment, point, current point value, and alarm rule CSV files can be loaded into a local SQLite database:

```bash
python3 analysis/load_alarm_db.py
```

The loader reads the catalog and current value CSV files in `data/`, creates `db/facilityops.sqlite3`, and prints a verification summary. Generated alarms start empty after each loader reset.

This command remains the default Northstar Data Hall loader. It records the stable facility identity `FACILITY-NORTHSTAR-DATA-HALL` and fixture version `1.0.0` without changing existing Northstar catalog identifiers or seeded behavior.

Load the minimum flagship fixture only into an explicitly selected isolated database:

```bash
python3 -m analysis.facility_fixture_loader load \
  --manifest data/facilities/flagship/1.0.0/manifest.json \
  --db /tmp/facilityops-flagship.sqlite3
```

The flagship loader rejects `db/facilityops.sqlite3` as a target, validates the complete manifest and every CSV before database mutation, and then replaces catalog and topology configuration in one transaction. It does not fall back to Northstar after an invalid selection.

Query the stored facility identity and complete typed flagship topology:

```bash
python3 -m analysis.facility_fixture_loader query \
  --db /tmp/facilityops-flagship.sqlite3
```

Generated database files are local development artifacts and are ignored by git.

## Facility And Equipment Context

The implemented environment is **Northstar Data Hall**, a fictional mission-critical data hall documented in [`docs/facility_model.md`](docs/facility_model.md). Northstar is the preserved legacy fixture, regression environment, and secondary data-center demonstration.

The fictional **Advanced Materials Research and Precision-Environment Facility** is the flagship environment. Milestone 2 implements its minimum versioned catalog and typed topology: a corridor-to-transition/airlock-to-process-laboratory pressure cascade, process-exhaust duty and standby fans, a shared exhaust path, monitored treatment and supply/makeup-air dependencies, and explicitly bound observation points.

[ADR 0004](docs/decisions/0004-flagship-fictional-applicability-profile.md) records the bounded fictional profile: a new, privately operated, one-story, sprinklered research facility in the Town of Horseheads, Chemung County, outside incorporated villages and New York City; an assumed Town code-enforcement AHJ and Group B research-laboratory use; bench-scale alumina-based ceramic powder and sintered specimens; a 250 g maximum open batch and 5 kg maximum closed-container laboratory inventory; the stated excluded hazards; and qualitative exhaust, treatment, duty/standby, shared-path, makeup-air, and pressure-direction intent. These are simulation and project assumptions, not verified legal classifications, applicability conclusions, physical design approval, or hazardous-material threshold determinations.

Milestone 3 implements a separate repository-versioned, read-only standards-basis package for that profile. The planned **process-exhaust failure causing pressure-cascade degradation** scenario, source-native and canonical observations, point conditions, higher-level inference, evidence-sufficiency evaluation, bounded findings, human disposition, and deterministic consequence computation remain unimplemented. The topology still has no process-enabled context, controller request, controller-reported execution, dedicated VFD-state, or motor/electrical-response points. Exact additions require a later accepted ADR.

### How codes, standards, and regulations are used

Codes, regulations, standards, owner/project decisions, informative guidance, and simulation assumptions are controlled references, not executable truth. The catalog records issuer, exact title and identifier, edition or effective date when verified, source category, official URL or repository record, access date, adoption and enforcement status, potential trigger, direct support, and uncertainty. Catalog inclusion does not establish legal or project applicability.

The provisional applicability matrix relates each source to explicit fictional profile facts and preserves the distinction among legal/regulatory source candidates and provisional applicability bases, adopted codes and amendments, owner/project requirements, project-authored synthetic requirements, informative guidance, and simulation assumptions. It records no direct legal applicability determination. Qualified personnel retain applicability and approval authority.

The package contains 18 profile facts, 27 controlled sources, 23 applicability bases, 18 evidence categories, and 12 project-authored synthetic requirements. Ten qualitative requirements have the project-owner decision recorded and are `ACCEPTED_FOR_SIMULATION`; two additional drafts are `PROPOSED`. All 12 are `INACTIVE`, non-executable, and contain no numerical criteria. Reviewers can inspect `controlled source → applicability basis → synthetic requirement → required evidence category` in the workbench or read-only API.

FacilityOps does not establish code compliance, commissioning acceptance, physical safety, operability, or authorization for operation.

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

The operational reset endpoint restores the local sandbox to the baseline registered for the database's exact facility ID and fixture version without deleting catalog or topology configuration. `POST /scenario/reset-operational-state` clears generated alarms, alarm/audit events, point samples, and current values before loading that selected baseline. Northstar restores its 17 seeded values. The Milestone 2 flagship declares no observation baseline, so flagship reset loads zero values and cannot inject Northstar values. Reset fails without mutation when the database has no exact registered facility context.

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

The API includes `/facility-topology`, which identifies the selected SQLite facility and fixture version and returns the deterministic typed topology. The dashboard does not provide facility selection or a topology presentation.

The repository-versioned standards basis is independent of active SQLite state. `GET /standards-basis` returns one atomic reviewer snapshot. Read-only leaf routes expose `/standards-basis/profile`, `/standards-basis/controlled-sources`, `/standards-basis/applicability-matrix`, `/standards-basis/requirements`, `/standards-basis/evidence-categories`, and `/standards-basis/traceability`. The workbench presents the same material in a separate flagship review section and does not evaluate it.

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

Call the selected facility topology endpoint:

```bash
curl http://127.0.0.1:8000/facility-topology
```

Call the complete read-only flagship standards-basis endpoint:

```bash
curl http://127.0.0.1:8000/standards-basis
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

Use Python 3.12 and create a fresh virtual environment. Do not reuse a virtual environment after changing Python minor versions. On macOS, a checkout under a cloud-synchronized folder can offload virtual-environment files as `dataless` placeholders and block imports while macOS retrieves them; place the verification environment under `/tmp` or another non-synchronized local path.

The following commands create a disposable environment, install the pinned direct dependencies, print the resolved runtime versions, bound the application import to 30 seconds, and bound the complete suite to 300 seconds:

```bash
FACILITYOPS_VERIFY_ROOT="$(mktemp -d /tmp/facilityops-verify.XXXXXX)"
python3.12 -m venv "$FACILITYOPS_VERIFY_ROOT/venv"
"$FACILITYOPS_VERIFY_ROOT/venv/bin/python" -m pip install -r requirements.txt
"$FACILITYOPS_VERIFY_ROOT/venv/bin/python" scripts/run_verification.py
```

The bounded runner invokes the existing standard-library test command without skipping or rewriting tests:

```bash
python -m unittest discover -s tests
```

All mutating test cases use isolated temporary SQLite databases. The verification runner and suite do not load, reset, or overwrite the normal `db/facilityops.sqlite3` database.

## Current Stack

- Python
- SQLite
- FastAPI
- Uvicorn
- Plain HTML and JavaScript dashboard
- Markdown reports

## Planned Direction

Milestones 1–3 are complete. The remaining approved roadmap develops the flagship proof in this order:

1. Source-native observations, versioned mapping and normalization, canonical observations, computed point conditions, and temporal semantics.
2. A deterministic golden-scenario evidence and replay package, including controller-request, controller-reported execution, VFD, motor/electrical, airflow, dependency, pressure, and post-action evidence.
3. Traceable equipment, system, facility, consequence, and uncertainty inference.
4. Evidence-sufficiency evaluation, bounded findings, and a reproducible evidence manifest.
5. Separate human verification, recovery evidence, review, and disposition.
6. A coherent technical and portfolio demonstration that remains usable with AI disabled.

The consolidated next-review artifact is [PROPOSED—INACTIVE: Flagship Observation, Evidence, and Golden-Scenario Decision Packet](docs/decision-packets/0001-flagship-observation-and-scenario.md). It is documentation only and is not loaded by the application. Broad adapter coverage, controller-language comparison, and advisory AI are optional later research. Remaining planned capabilities are unimplemented until [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) records verified behavior.
