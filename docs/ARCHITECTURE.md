# FacilityOps Copilot Architecture

## Document basis

This document describes the repository at checkpoint commit `627d37ef99e9d9b3936317cffbe9c5037537b219` and separately identifies planned direction. The implemented section is descriptive, not aspirational. Product intent is governed by [`PRODUCT_CHARTER.md`](PRODUCT_CHARTER.md), and verification status is tracked in [`PROJECT_STATUS.md`](PROJECT_STATUS.md).

## Implemented architecture

### System shape

FacilityOps Copilot is a local, single-process FastAPI application backed by SQLite and a plain HTML/JavaScript frontend. Project-owned Python uses the standard library plus FastAPI and Uvicorn. There is no separate frontend build, task queue, background worker, external identity provider, or runtime AI service.

The principal flow is:

```text
Fictional CSV fixtures / local simulated driver / local CSV replay
                              |
                              v
             loaders, importer, and ingest services
                              |
                              v
              SQLite point and operations records
                              |
                              v
       deterministic rule evaluation and local state changes
                              |
                              v
                  FastAPI JSON routes
                              |
                              v
             plain HTML/JavaScript workbench
```

### Data and loading

`analysis/load_alarm_db.py` creates and loads the local SQLite database from fictional CSV fixtures. It loads the Northstar equipment catalog, point catalog, seeded current values, alarm rules, and the operational-context fixtures introduced in the checkpoint.

Seeded current values create point-sample history and a `current_point_values` latest-value projection. Generated alarms and alarm events begin empty after a full sample-data load. The legacy `alarms` table is created and cleared; the current dashboard uses generated alarms rather than the legacy alarm CSV.

`analysis/analyze_alarms.py` and `analysis/generate_db_briefing.py` remain legacy reporting scripts. Their reports are not the authoritative source for the current generated-alarm dashboard.

### SQLite model

The checkpoint defines these implemented tables:

- Core catalog and observation: `equipment`, `points`, `point_samples`, and `current_point_values`.
- Alarm configuration and state: `alarm_rules`, `generated_alarms`, and `alarm_events`.
- Legacy data: `alarms`.
- Seeded operations context: `facility_scenarios`, `alarm_correlations`, `alarm_correlation_members`, `incident_timeline`, `shift_turnover`, `equipment_out_of_service`, `corrective_actions`, `procedure_references`, and `reliability_reports`.

SQLite schema creation and compatibility migrations are embedded in loader and backend functions rather than managed by a dedicated migration framework. Foreign-key clauses exist in table definitions, but repository behavior has not been verified with SQLite foreign-key enforcement enabled.

### Point ingestion and health

`backend/services/point_ingest_service.py` ingests local driver samples through the same append-and-project path used by manual updates and scenarios. During normal point ingestion, each successful ingest appends a point-sample history row and updates the current-value projection within a transaction.

Implemented point metadata includes value, unit, quality, source and receive timestamps, stale window, source, protocol, address, override flag, out-of-service flag, and creator. Quality is normalized to `GOOD`, `UNCERTAIN`, `BAD`, or `STALE`; `UNKNOWN` becomes `UNCERTAIN`.

Changes in quality, override, and point out-of-service state append `alarm_events` audit rows. Staleness is evaluated only when the explicit point-health endpoint is called. There is no background stale-data scheduler.

### Deterministic alarm evaluation

`backend/domain/alarm_evaluator.py` contains deterministic rule evaluation for:

- Analog limits with `>`, `>=`, `<`, or `<=` operators.
- Boolean state comparison.
- Enum comparison.

Process alarm rules are ineligible when the current sample is bad, uncertain, stale, overridden, or out of service. The evaluator itself is stateless; generated alarm persistence is handled in `backend/summary.py`.

Generated alarms implement `PENDING`, `ACTIVE`, and `CLEARED` states. Configured delays create pending alarms, later explicit evaluations may promote them, and analog alarms use a clear value for hysteresis. Boolean and enum alarms clear when their triggering condition is no longer true. Acknowledgement records operator identity and an audit event but does not clear or suppress an alarm.

Alarm creation snapshots rule and triggering-sample facts. Lifecycle and acknowledgement transitions append `alarm_events`. Rule creation and edits also create audit rows. The event table is an audit aid, not a complete immutable event-sourcing or evidence system.

The repository currently uses conflicting severity and risk vocabularies. The relationship among alarm priority, point condition, operational risk, advisory classification, and incident severity is unresolved and must not be inferred from the current labels.

### Local adapters, replay, and import

- `SimulatedDriver` returns deterministic local samples for selected Northstar points.
- `CsvReplayDriver` reads ordered samples from `data/replay_samples.csv` and may filter by sequence.
- The lower-level replay-driver endpoint ingests samples without evaluating alarms.
- `backend/services/csv_replay_runner.py` runs one or all replay steps and explicitly evaluates generated alarms at replay timestamps.
- `backend/importers/modbus_importer.py` previews and validates a static Modbus register-map CSV. Commit creates or updates local equipment and point catalog records and appends a local audit event.

The Modbus importer does not connect to a device, poll registers, create point samples, update current values, evaluate alarms, or command equipment. Its equipment and location inference contains Northstar-oriented defaults and does not by itself prove vendor neutrality.

### Scenarios and operational reset

`backend/summary.py` defines deterministic Northstar alarm scenarios in Python. Applying a scenario writes local point samples and current values but does not automatically evaluate generated alarms. The checkpoint adds a multi-point utility, UPS, generator-readiness, and cooling scenario.

`backend/services/operational_reset_service.py` restores seeded current values and samples while preserving equipment, points, alarm rules, and imported Modbus catalog metadata. It deletes all generated alarms, alarm events, current-value rows, and point samples before recreating the seeded current projection.

Because reset deletes `point_samples` and `alarm_events`, it destroys current point-sample history and local audit history before reseeding the laboratory baseline. This is implemented behavior. Durable observation and incident retention is planned, and the target direction is to separate clearing active laboratory state from durable provenance and incident evidence, but no such retention architecture is implemented.

### Seeded operations context

The checkpoint loads and exposes a fictional Northstar utility-disturbance story: a facility scenario, one alarm correlation with evidence members, an incident timeline, shift turnover, equipment OOS records, corrective actions, procedure references, and a reliability report.

These records are curated CSV assertions. They are returned and displayed, not computed from a point-to-equipment-to-system-to-facility state engine. Correlation confidence, root-cause hypothesis, availability, MTTR, alarm counts, OOS hours, and executive summary are seeded values rather than derived results.

### API and frontend

`backend/main.py` exposes local JSON routes for summaries, catalogs, values, rule evaluations, alarm state, audit events, point health, simulated reads, replay, Modbus import, scenarios, operational reset, and seeded operations context. Mutating routes write only to the local laboratory database.

`frontend/index.html` is a single plain HTML, CSS, and JavaScript workbench served at `/` and `/dashboard`. It loads data with `fetch`, renders tables and panels, and provides local buttons or forms for scenario application, reset, sample reads, replay, Modbus import, alarm evaluation and acknowledgement, point updates, point-health evaluation, and alarm-rule creation or editing.

There is no client-side framework, package build, generated asset bundle, or separate web server in the repository.

### External read-only boundary

No live BAS, EPMS, PLC, SCADA, DCIM, Modbus device, or customer system is connected at the checkpoint. All adapters and fixtures are local. There is no implemented external command or write-back path.

The product boundary prohibits any future external command, configuration change, or write-back. Local imports, samples, scenarios, acknowledgements, rule changes, tests, and audit records remain permitted laboratory writes.

### Verification architecture

The repository contains one standard-library `unittest` module with 211 test methods covering legacy summaries, SQLite loading, catalogs, point ingestion and health, adapters, replay, reset, Modbus import, rule editing and creation, scenarios, deterministic evaluation, generated-alarm lifecycle, audit behavior, and API/dashboard behavior. `scripts/run_verification.py` bounds application import to 30 seconds and the complete suite to 300 seconds while invoking the existing unittest discovery command unchanged.

Milestone 1.1 reproduced the reported import stall in a reused project-local virtual environment and traced it to a mixed Python 3.12/3.14 environment containing macOS cloud-offloaded package files. No application-code or test change was required. With the recorded Python 3.12 dependency set, the application import completed within its bound and all 211 tests passed against isolated test state. See [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for exact versions, timings, counts, and remaining limits.

## Implemented limitations

The checkpoint does not implement:

- Polling, subscription, background scheduling, or continuous evaluation.
- Live external connectivity or an external read-only adapter.
- Any physical command or external write-back path.
- A canonical hierarchy from point condition to equipment, system, and facility state.
- Deterministic consequence computation from that hierarchy.
- A process-exhaust or pressure-cascade model.
- The planned flagship facility or golden scenario.
- Durable evidence packaging, provenance manifests, import hashes, or evidence retention across reset.
- Executable alarm-response, impairment, commissioning, functional-test, recovery, or incident-review workflows.
- Runtime AI or an advisory AI boundary.
- Authentication, authorization, multi-user identity, or role enforcement.
- A documented deployment, production hardening, backup, restore, monitoring, or upgrade architecture.
- Performance, concurrency, scale, accessibility, or cross-browser guarantees.

## Planned architecture direction

The following is intended direction, not implemented architecture:

- A vendor-neutral facility topology connecting zones, equipment, systems, dependencies, operating modes, and evidence.
- Deterministic layers for point condition, equipment state, system state, facility state, and operational consequences.
- Scenario and replay packages with explicit preconditions, expected transitions, acceptance criteria, and provenance.
- Durable evidence records that survive active-state reset and support incident reconstruction.
- Local workflows for operator response, impairment, functional testing, recovery, and review.
- Adapter contracts for synthetic, sanitized, non-sensitive, or explicitly authorized read-only sources.
- An advisory AI layer that cites deterministic state and evidence and never owns authoritative determinations.

Exact schemas, state vocabularies, temporal semantics, workflow models, evidence retention, and adapter contracts require approved architecture decisions and roadmap slices. This section must not be used to claim those capabilities exist.
