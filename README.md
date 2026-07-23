# FacilityOps Copilot

FacilityOps Copilot is a standards-grounded technical laboratory for critical-environment facilities operations, reliability, controls, and OT assurance. It uses a fictional facility and deterministic scenarios to study how heterogeneous source indications can be normalized, interpreted, compared with versioned synthetic control intent, and reconstructed after an event without creating a control path to a physical facility.

The project prioritizes transferable facilities knowledge, disciplined engineering reasoning, a coherent flagship proof, and technical portfolio value. A possible read-only controls-assurance capability remains a research hypothesis; FacilityOps is not a commercially validated product, universal compliance engine, general facilities integration platform, BAS or SCADA replacement, or AI safety authority.

The approved direction is defined by the change-controlled [`docs/PRODUCT_CHARTER.md`](docs/PRODUCT_CHARTER.md). This README preserves practical setup, API, verification, and implemented-behavior instructions; it does not replace the governance documents or imply that planned capabilities are implemented.

## Governance And Current Status

- [`docs/PRODUCT_CHARTER.md`](docs/PRODUCT_CHARTER.md) defines the approved product purpose, boundaries, principles, and non-goals.
- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) separates verified implemented behavior from partial, planned, and unverified behavior.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) defines the approved milestone order and completion evidence.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) describes the implemented architecture separately from planned direction.
- [`docs/FLAGSHIP_FACILITY.md`](docs/FLAGSHIP_FACILITY.md) describes the fictional flagship facility. Its minimum topology, additive observation topology, controlled applicability basis, canonical observation semantics, and repository synthetic observation replay are implemented; point condition, higher-level inference, evaluation, and human disposition remain planned.
- [`docs/STANDARDS_POSITION.md`](docs/STANDARDS_POSITION.md) defines how controlled references, applicability, synthetic requirements, bounded findings, and human disposition remain distinct.
- [`docs/decisions/README.md`](docs/decisions/README.md) defines the ADR process, indexes accepted ADRs 0001–0006, and maintains the consolidated unresolved-decision backlog.

Deterministic code owns reproducible computation. It produces computed point conditions, inferred states, timing results, replay outputs, evaluations, and bounded findings under identified inputs, assumptions, configuration, and rules. Determinism provides reproducibility, not automatic validity. The following authorities remain with persons or organizations that possess the required qualifications and assigned organizational or legal authority: applicability decisions, requirement approval, test authorization, operational action, commissioning acceptance, waivers, final disposition, determinations of physical safety, and authorization for operation.

A canonical observation remains a reported indication and does not independently prove physical state. After a recorded action or response, FacilityOps may receive new observations. The action or response record does not establish causation or physical effect. Recovery requires new post-action observations and a separate evaluation. Any future AI capability is advisory only and cannot approve its own output, mutate controlled computation, exercise qualified human authority, or command a physical system.

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

To inspect the additive observation point-definition topology through the same isolated loader contract, select `data/facilities/flagship/1.1.0/manifest.json` instead. This loads topology definitions only; it does not execute the repository replay or create canonical observations.

Query the stored facility identity and complete typed flagship topology:

```bash
python3 -m analysis.facility_fixture_loader query \
  --db /tmp/facilityops-flagship.sqlite3
```

Generated database files are local development artifacts and are ignored by git.

### Isolated observation replay database

The canonical observation replay uses a separate, lazily initialized local SQLite store at `db/facilityops-observations.sqlite3`. Application import does not create or open this database. It is created only when an explicit synthetic replay executes. Package inspection validates bounded syntax, identities, digests, and references without claiming that the structural oracle matches derived rows. Execution deterministically builds the complete replay plan, validates every structured oracle expectation against that plan, and only then publishes it in one transaction with foreign-key enforcement.

The observation store is append-only after acceptance and is not opened or cleared by `POST /scenario/reset-operational-state`. This protects the new replay evidence from the legacy operational reset, but it is a bounded laboratory retention mechanism rather than the complete incident-retention architecture planned for a later milestone. No destructive observation reset endpoint exists.

## Facility And Equipment Context

The implemented environment is **Northstar Data Hall**, a fictional mission-critical data hall documented in [`docs/facility_model.md`](docs/facility_model.md). Northstar is the preserved legacy fixture, regression environment, and secondary data-center demonstration.

The fictional **Advanced Materials Research and Precision-Environment Facility** is the flagship environment. Topology `1.0.0` remains the preserved minimum catalog and typed topology: a corridor-to-transition/airlock-to-process-laboratory pressure cascade, process-exhaust duty and standby fans, a shared exhaust path, monitored treatment and supply/makeup-air dependencies, and explicitly bound point definitions.

The additive topology `TOPOLOGY-FLAGSHIP-PROCESS-EXHAUST` version `1.1.0` preserves that inventory and adds 2 point-owning equipment records, 12 reported-indication point definitions, and 4 typed bindings for process context and permissive, controller request and execution assertions, VFD state, motor current, treatment availability, and delivered makeup airflow. Existing shared process-exhaust airflow, fan status and speed, makeup controller status, shared-path, and pressure point definitions remain reused. Neither topology version declares a current-value baseline, and topology point definitions are not received observations.

[ADR 0004](docs/decisions/0004-flagship-fictional-applicability-profile.md) records the bounded fictional profile: a new, privately operated, one-story, sprinklered research facility in the Town of Horseheads, Chemung County, outside incorporated villages and New York City; an assumed Town code-enforcement AHJ and Group B research-laboratory use; bench-scale alumina-based ceramic powder and sintered specimens; a 250 g maximum open batch and 5 kg maximum closed-container laboratory inventory; the stated excluded hazards; and qualitative exhaust, treatment, duty/standby, shared-path, makeup-air, and pressure-direction intent. These are simulation and project assumptions, not verified legal classifications, applicability conclusions, physical design approval, or hazardous-material threshold determinations.

Milestone 3 implements the preserved repository-versioned, read-only standards-basis package for that profile. An additive standards-basis version `1.1.0` binds the same profile, sources, provisional applicability bases, qualitative requirements, and evidence categories to topology `1.1.0`. It updates only approved point-definition representation and related explanatory text. Every requirement remains inactive, non-executable, and without numerical criteria.

ADRs 0005 and 0006 implement the bounded evidence chain `source delivery → source-native record → canonical observation → reported-observation projection → deterministic synthetic replay`. The allowlisted replay is an observation-only package named `flagship-process-exhaust-evidence-sequence`. It does not determine duty-fan failure, standby changeover, equipment/system/facility state, pressure-cascade or containment condition, evidence sufficiency or independence, consequence, conformance, safety, authorization, or recovery.

### How codes, standards, and regulations are used

Codes, regulations, standards, owner/project decisions, informative guidance, and simulation assumptions are controlled references, not executable truth. The catalog records issuer, exact title and identifier, edition or effective date when verified, source category, official URL or repository record, access date, adoption and enforcement status, potential trigger, direct support, and uncertainty. Catalog inclusion does not establish legal or project applicability.

The provisional applicability matrix relates one or more controlled sources to explicit fictional profile facts and preserves the distinction among legal/regulatory source candidates and provisional applicability bases, adopted codes and amendments, owner/project requirements, project-authored synthetic requirements, informative guidance, and simulation assumptions. It records no direct legal applicability determination. Applicability and approval authority remain within the complete human-authority boundary stated above.

Each standards-basis version contains 18 profile facts, 35 controlled sources, 29 applicability bases, 19 evidence categories, and 12 project-authored synthetic requirements. Ten qualitative requirements have the project-owner decision recorded and are `ACCEPTED_FOR_SIMULATION`; two additional drafts are `PROPOSED`. All 12 are `INACTIVE`, non-executable, and contain no numerical criteria. Reviewers can inspect `controlled source → applicability basis → synthetic requirement → required evidence category` in the workbench or read-only API. Every evidence category continues to record `NO_FLAGSHIP_OBSERVATION_BASELINE`; observations become visible only after a reviewer explicitly starts and selects a separate synthetic replay execution.

FacilityOps does not establish code compliance, commissioning acceptance, physical safety, operability, or authorization for operation.

Equipment inventory is stored in `data/sample_equipment.csv` and loaded into SQLite with the point, current value, and alarm rule data. The inventory adds context such as equipment type, location, criticality, and source system.

Point dictionary records are stored in `data/sample_points.csv`. Current point values are stored in `data/sample_current_point_values.csv`. Alarm rule catalog records are stored in `data/sample_alarm_rules.csv`.

During normal ingestion, each update appends a `point_samples` history row and updates the latest-value `current_point_values` projection. Current point values can be updated manually through the dashboard or the local API. Manual updates create a point sample, update the latest-value projection, use `MANUAL` as the current value source, and do not automatically evaluate generated alarms. This history is not durable across operational reset: reset currently deletes point samples and reseeds the laboratory baseline.

Alarm rules can be created for existing points through the dashboard or the local API for local demo tuning. Existing rule edits are limited to thresholds, clear values, delay, severity, enabled state, and alarm message; creating or editing rules does not automatically evaluate or rewrite generated alarms. Rule creation and edits append `alarm_events` audit rows during normal operation, but those rows are not retained across operational reset.

Point sample health changes are also recorded in `alarm_events`: quality changes, override changes, out-of-service changes, and stale samples found by the explicit point health evaluation endpoint. The app does not run a background staleness scheduler.

The backend includes a small read-only `SimulatedDriver` adapter for deterministic local point reads. `POST /drivers/simulated/read` ingests those samples through the same point sample path used by manual updates and scenarios, updates the current value projection, and does not automatically evaluate generated alarms.

The backend also includes a read-only `CsvReplayDriver` adapter for deterministic point sample replay from `data/replay_samples.csv`. `POST /drivers/csv-replay/read` can ingest all replay samples or a specific sequence step, updates the current value projection, and does not automatically evaluate generated alarms.

The CSV replay runner is the explicit operator/test workflow for replay sequences. `POST /replay/csv/step` runs one selected replay sequence by reading CSV samples, ingesting them, and then evaluating generated alarms at the replay sample timestamp. `POST /replay/csv/run-all` runs every replay sequence in deterministic order. The lower-level CSV replay driver endpoint remains ingest-only.

The flagship synthetic observation replay is separate from the legacy Northstar CSV replay. It accepts only one explicitly allowlisted repository package; there is no arbitrary package path, archive, URL, upload, or live-ingestion endpoint. Each execution preserves separate package, execution, delivery, request-idempotency, source-event, source-native, canonical-observation, mapping, canonicalizer, and topology identities.

An exact source-event redelivery retains every delivery and source-native record while deriving its logical canonical variant once. A source-event identity reused with materially different payload or metadata retains every variant as an unresolved conflict and selects no winner, including when the variants use different mapping versions. Equal payloads under different source-event identities remain distinct, and records without a stable source identity are not deduplicated by value, timestamp, or digest. Distinct logical reports with equivalent normalized material can share a reported scalar at an equal-order projection frontier without being collapsed into one source event.

`observed_at` records when the source asserts that an indication occurred; `received_at` records when FacilityOps accepted the delivery. Valid source timestamps are normalized to UTC while the original text, offset, and precision remain preserved. Missing or invalid source time remains explicit and is never replaced by receipt time. Source sequence is comparable only inside its declared source/session namespace. The implementation exposes out-of-order arrival and sequence/time disagreement without inventing a lateness, staleness, freshness, persistence, or recovery-hold threshold.

The rebuildable reported-observation projection is scoped to one facility, replay execution, source/channel binding, canonical point, and mapping derivation. Every query requires both an event-time cutoff (`as_of_observed_at`) and a knowledge-time cutoff (`known_by_received_at`). A sequence/time contradiction touching the maximal source-order frontier remains `UNORDERED`; a missing- or invalid-time report at the same or greater sequence in one declared epoch prevents fallback to an older scalar. Projection dispositions such as `REPORTED`, `CONFLICT_PRESENT`, `UNORDERED`, `NO_OBSERVATION`, and `NO_ELIGIBLE_REPORT` describe received evidence only; they are not equipment state, actual condition, conformance, or recovery results.

Every canonical observation contains one typed normalized value, mapping and canonicalizer identity, time-basis and source-quality provenance, synthetic provenance, and exact lineage to one or more source-native records and fields. The mappings demonstrate one-native-to-many-canonical, many-native-to-one-canonical, partial decode, direct enum and Boolean normalization, signed register decoding, decimal scaling, and same-dimension unit conversion. Register-component exact redeliveries retain lineage without adding a logical composite; conflicting complete component variants retain each valid derivation, and an unpairable conflicting component remains visible through the retained component lineage. Components with different non-null declared source session or boot epochs remain separate and emit `REGISTER_PAIR_SOURCE_EPOCH_MISMATCH`. The mappings perform no point-condition or physical inference.

Each completed replay has a reproducibility manifest with pinned package, topology, mapping, and canonicalizer identities; record counts and digests; duplicate/conflict and projection summaries; and a normalized semantic digest that excludes run-scoped random identifiers and non-semantic creation time. Equivalent separate executions produce the same normalized semantic result. These hashes establish reproducibility and integrity of represented data only, not authenticity, correctness, applicability, evidence independence, or physical truth.

The backend includes a static Modbus register map importer for local catalog setup only. `POST /imports/modbus/preview` validates a CSV register map without database writes. `POST /imports/modbus/commit` validates again, then creates or updates equipment and point catalog records with `MODBUS` protocol/address metadata. The importer does not poll Modbus devices, create point samples, update current point values, evaluate alarm rules, or create generated alarms.

Alarm scenarios are deterministic dashboard and API controls that set known current point values into alarm or normal demo conditions. Scenario updates create point samples, use `SCENARIO` as the current value source, and do not automatically evaluate generated alarms.

The dashboard also includes a deterministic operations overview for an end-to-end facility scenario: utility disturbance, ATS source loss indication, UPS battery support, generator fuel readiness constraint, and CRAC supply temperature drift. This overview is seeded local data, not an AI-generated root cause engine. It demonstrates explainable correlation evidence, event history, shift turnover notes, equipment out-of-service records, corrective actions, MOP/SOP/EOP references, and management-level reliability reporting.

The operational reset endpoint restores the local sandbox to the baseline registered for the database's exact facility ID and fixture version without deleting catalog or topology configuration. `POST /scenario/reset-operational-state` clears generated alarms, alarm/audit events, point samples, and current values before loading that selected baseline. Northstar restores its 17 seeded values. Both registered flagship topology packages declare no current-value baseline, so flagship reset loads zero values and cannot inject Northstar values. Reset fails without mutation when the database has no exact registered facility context.

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

Facility-aware observation routes use `/facilities/{facility_id}/observation-replay`. The API includes:

- `GET /packages` and `GET /packages/{package_id}/versions/{package_version}`.
- `POST /executions`, with exact package identity/version and a request idempotency key.
- `GET /executions/{replay_execution_id}` and `/manifest`.
- Paginated `/source-native-records` and `/canonical-observations` list/detail routes.
- `/canonical-observations/{canonical_observation_id}/lineage`.
- Paginated `/redelivery-groups`.
- `/reported-observation-projection`, requiring source binding, point, mapping ID/version/digest, `as_of_observed_at`, and `known_by_received_at`.

List page size defaults to 50 and is capped at 100. Execution-scoped routes reject cross-facility and cross-execution references. The execution endpoint accepts no arbitrary filesystem path, archive, URL, or upload field, and the API exposes no destructive observation reset.

The dashboard calls the preserved operational and standards APIs plus these observation routes. Its synthetic replay section lets a reviewer select the allowlisted package, inspect package/topology/mapping identities and digests, start an isolated replay, compare observed and received time, inspect source-native and canonical records, follow exact lineage, review redelivery/conflict groups, rebuild the projection with explicit cutoffs, and inspect the reproducibility manifest. The standards section continues to state `NO_FLAGSHIP_OBSERVATION_BASELINE` unless a separate replay is explicitly selected; replay selection does not mutate that declaration.

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

List allowlisted synthetic observation replay packages:

```bash
curl http://127.0.0.1:8000/facilities/FACILITY-ADVANCED-MATERIALS-RESEARCH/observation-replay/packages
```

Inspect the syntax/reference-validated repository package metadata:

```bash
curl http://127.0.0.1:8000/facilities/FACILITY-ADVANCED-MATERIALS-RESEARCH/observation-replay/packages/flagship-process-exhaust-evidence-sequence/versions/1.0.0
```

Start one isolated local synthetic replay:

```bash
curl -X POST http://127.0.0.1:8000/facilities/FACILITY-ADVANCED-MATERIALS-RESEARCH/observation-replay/executions \
  -H "Content-Type: application/json" \
  -d '{"package_id":"flagship-process-exhaust-evidence-sequence","package_version":"1.0.0","idempotency_key":"readme-replay-001"}'
```

Use the returned `replay_execution_id` to query status, manifest, paginated source-native and canonical records, lineage, redelivery groups, and the reported-observation projection. Projection requests must include the exact source binding, point, mapping ID/version/digest, `as_of_observed_at`, and `known_by_received_at` shown by that execution.

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

The 2026-07-23 observation-and-replay acceptance-correction verification ran all 371 discovered tests successfully, including 88 focused canonical-observation, topology, replay, persistence, API, and workbench tests. Exact environment and timing evidence is recorded in [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md).

All mutating test cases use isolated temporary SQLite databases. The verification runner and suite do not load, reset, or overwrite the normal `db/facilityops.sqlite3` database or the default `db/facilityops-observations.sqlite3` replay store.

## Current Stack

- Python
- SQLite
- FastAPI
- Uvicorn
- Plain HTML and JavaScript dashboard
- Markdown reports

## Planned Direction

Milestones 1–3 are complete. The canonical-observation and repository replay tranches of Milestones 4 and 5 are also complete. Remaining approved work develops the flagship proof in this order:

1. Computed point-condition semantics, including any later approved quality, override, out-of-service, evaluation-time, staleness, persistence, lateness, recovery-hold, and uncertainty rules.
2. Traceable equipment, system, pressure-cascade, facility, consequence, and uncertainty inference.
3. Evidence-sufficiency evaluation, bounded findings, and an incident-level reproducible evidence manifest beyond the implemented replay manifest.
4. Separate human verification, recovery evidence and evaluation, review, and disposition.
5. A coherent technical and portfolio demonstration that remains usable with AI disabled.

The consolidated [PROPOSED—INACTIVE: Flagship Observation, Evidence, and Golden-Scenario Decision Packet](docs/decision-packets/0001-flagship-observation-and-scenario.md) preserves the earlier recommendations. ADRs 0005 and 0006 supersede only its accepted observation/replay architecture; all physical criteria, point/equipment/system/facility inference, evidence-sufficiency and independence conclusions, findings, human workflows, and recovery rules remain proposed and inactive. Broad adapter coverage, controller-language comparison, deployment, and advisory AI remain optional later research. Remaining planned capabilities are unimplemented until [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) records verified behavior.
