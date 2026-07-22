# FacilityOps Copilot Architecture

## Document basis

This document describes the verified implementation through commit `bf46e3f`, built on the Milestone 2 base commit `f37f2da01cfe88f38f1f70ea54f98ef51dde44ab`, and separately identifies planned direction. The implemented section is descriptive, not aspirational. Product identity and authority are governed by [`PRODUCT_CHARTER.md`](PRODUCT_CHARTER.md), standards policy is summarized in [`STANDARDS_POSITION.md`](STANDARDS_POSITION.md), and verification status is tracked in [`PROJECT_STATUS.md`](PROJECT_STATUS.md).

## Target conceptual architecture

The following lifecycles govern the architecture. Only the layers explicitly described under implemented architecture exist today.

### Observation, inference, and consequence

```text
source artifact or stream
→ source-native observation as received by FacilityOps
→ versioned mapping and normalization
→ canonical observation
→ point condition
→ equipment, system, and facility inference
→ consequence and uncertainty
```

A canonical observation remains a reported indication. It does not independently prove physical state. Mapping, normalization, point condition, higher-level inference, and consequence are separate transformations or computations that must retain inputs, versions, assumptions, limitations, contradictions, and uncertainty.

A read-only or synthetic controller command/request indication is evidence of what a source reports. FacilityOps does not issue that command, and the indication does not prove controller execution or physical response. Independent airflow, pressure, VFD, motor, or electrical evidence may be required by a controlled synthetic requirement.

### Standards and assurance

```text
reference source
→ applicability decision
→ versioned requirement
→ required evidence
→ deterministic evaluation
→ bounded finding
→ evidence manifest
→ human review and disposition
```

Reference sources, applicability bases, synthetic requirements, executable evaluations, computed findings, and human dispositions remain distinct. The bounded Milestone 3 implementation represents controlled sources, provisional applicability bases, inactive project-authored synthetic requirements, and required evidence categories for one flagship. It does not implement applicability approval, requirement execution, evidence-sufficiency evaluation, findings, evidence manifests, or disposition.

### Computation and human authority

Deterministic code owns reproducible computation. It produces computed point conditions, inferred states, timing results, replay outputs, evaluations, and bounded findings under identified inputs, assumptions, configuration, and rules. Determinism provides reproducibility, not automatic validity. Qualified personnel retain authority for applicability decisions, requirement approval, test authorization, operational action, commissioning acceptance, waivers, and final disposition.

Human response must lead to new source observations and a separate recovery evaluation. A recorded acknowledgement, decision, action, or work record does not prove its physical effect.

Missing, stale, suspect, overridden, late, or conflicting required evidence must be capable of producing an `INDETERMINATE` result. The working external presentation also includes `CONFORMING`, `NONCONFORMING`, and `NOT_APPLICABLE`; internal applicability/result structure remains unresolved.

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
       deterministic rule evaluation and local record changes
                              |
                              v
                  FastAPI JSON routes
                              |
                              v
             plain HTML/JavaScript workbench
```

The separate Milestone 3 review path is repository-versioned and does not use SQLite:

```text
versioned flagship standards-basis JSON package
→ complete deterministic validation
→ atomic read-only in-memory store
→ read-only FastAPI routes
→ separate reviewer workbench section
```

### Data and loading

`analysis/load_alarm_db.py` remains the default Northstar compatibility loader. It loads the existing Northstar equipment catalog, point catalog, seeded current values, alarm rules, and operational-context fixtures. After a successful load it records the stable Northstar facility identity and fixture version through additive facility metadata; it does not rewrite existing Northstar identifiers or values.

`analysis/facility_fixture_loader.py` is the explicit manifest-driven loader for the minimum flagship fixture. The caller must provide both the versioned JSON manifest and an isolated target database. The loader rejects the normal project database, reads and validates every declared CSV before opening the target, and replaces catalog, facility identity, topology, typed relationships, and typed point bindings through one connection and one explicit transaction. A write or post-load validation failure rolls back the complete replacement.

The flagship validator checks manifest/file facility and version agreement, stable and unique identifiers, mandatory point-to-equipment ownership, typed endpoint existence, relationship uniqueness, constrained duty/standby roles, explicit pressure direction, a connected acyclic two-boundary cascade, one primary topology binding per point, and the complete ADR 0001 inventory. Post-load validation re-queries stored rows and bindings and runs `PRAGMA foreign_key_check` without globally enabling SQLite foreign keys.

`backend/services/standards_basis_service.py` loads `data/standards/flagship/1.0.0/manifest.json` independently of the active database. It reads every declared document into a candidate snapshot, validates exact facility and fixture identity, whole-package identifier uniqueness, statuses, provenance, references, the exact recorded qualitative requirements, inactive/non-executable state, absence of numerical criteria, and evidence-point references against the unchanged flagship `1.0.0` catalog. Only a fully valid candidate replaces the in-memory snapshot. Failed reload leaves the previous snapshot exposed, and every read returns a defensive copy.

Seeded current values create point-sample history and a `current_point_values` latest-value projection. Generated alarms and alarm events begin empty after a full sample-data load. The legacy `alarms` table is created and cleared; the current dashboard uses generated alarms rather than the legacy alarm CSV.

`analysis/analyze_alarms.py` and `analysis/generate_db_briefing.py` remain legacy reporting scripts. Their reports are not the current generated-alarm data source for the dashboard.

### SQLite model

The implementation retains these pre-Milestone 2 tables:

- Core catalog and observation: `equipment`, `points`, `point_samples`, and `current_point_values`.
- Alarm configuration and lifecycle records: `alarm_rules`, `generated_alarms`, and `alarm_events`.
- Legacy data: `alarms`.
- Seeded operations context: `facility_scenarios`, `alarm_correlations`, `alarm_correlation_members`, `incident_timeline`, `shift_turnover`, `equipment_out_of_service`, `corrective_actions`, `procedure_references`, and `reliability_reports`.

Milestone 2 adds these tables without changing existing Northstar keys:

- Facility identity: `facility_environments`, constrained to one active record per database.
- Topology entities: `zones`, `facility_systems`, `pressure_boundaries`, `shared_system_paths`, and `monitored_dependencies`.
- Typed relationships: `equipment_system_memberships`, `system_zone_services`, `equipment_shared_path_memberships`, `shared_path_monitored_dependencies`, `pressure_boundary_system_dependencies`, `pressure_boundary_monitored_dependencies`, and `pressure_boundary_cascade_order`.
- Typed observation context: `point_zone_bindings`, `point_system_bindings`, `point_pressure_boundary_bindings`, `point_shared_path_bindings`, and `point_monitored_dependency_bindings`.

One facility is stored per SQLite database. Relationship endpoints use concrete columns and declared foreign keys to typed tables; there is no generic graph, EAV structure, polymorphic entity reference, or facility-scoped composite key. SQLite foreign-key enforcement remains disabled by default, consistent with ADR 0002.

SQLite schema creation and compatibility migrations are embedded in loader and backend functions rather than managed by a dedicated migration framework. Foreign-key clauses exist in table definitions, but repository behavior has not been verified with SQLite foreign-key enforcement enabled.

Milestone 3 adds no SQLite table or migration and does not alter the flagship topology package or fixture version `1.0.0`.

### Point ingestion and health

`backend/services/point_ingest_service.py` ingests local driver samples through the same append-and-project path used by manual updates and scenarios. During normal point ingestion, each successful ingest appends a point-sample history row and updates the current-value projection within a transaction.

Implemented point metadata includes value, unit, quality, source and receive timestamps, stale window, source, protocol, address, override flag, out-of-service flag, and creator. Quality is normalized to `GOOD`, `UNCERTAIN`, `BAD`, or `STALE`; `UNKNOWN` becomes `UNCERTAIN`.

Changes in quality, override, and the point out-of-service flag append `alarm_events` audit rows. Staleness is evaluated only when the explicit point-health endpoint is called. There is no background stale-data scheduler.

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

`backend/services/operational_reset_service.py` reads the exact facility ID and fixture version from the selected database and resolves only that registered package context before beginning a write transaction. It preserves facility identity, equipment, points, alarm rules, topology, typed relationships, typed bindings, and imported Modbus catalog metadata. It deletes generated alarms, alarm events, current-value rows, and point samples before recreating only the selected fixture's baseline projection.

Northstar reset restores the unchanged 17-value baseline. The Milestone 2 flagship has no observation baseline, so its reset loads zero current values. Missing or unknown facility context, an unavailable baseline, or a cross-fixture baseline override fails before mutation; reset never falls back to Northstar.

Because reset deletes `point_samples` and `alarm_events`, it destroys current point-sample history and local audit history before reseeding the laboratory baseline. This is implemented behavior. Durable observation and incident retention is planned, and the target direction is to separate clearing active laboratory state from durable provenance and incident evidence, but no such retention architecture is implemented.

### Seeded operations context

The checkpoint loads and exposes a fictional Northstar utility-disturbance story: a facility scenario, one alarm correlation with evidence members, an incident timeline, shift turnover, equipment OOS records, corrective actions, procedure references, and a reliability report.

These records are curated CSV assertions. They are returned and displayed, not computed through the planned point-condition and equipment/system/facility inference chain. Correlation confidence, root-cause hypothesis, availability, MTTR, alarm counts, OOS hours, and executive summary are seeded values rather than derived results.

### API and frontend

`backend/main.py` exposes local JSON routes for summaries, catalogs, values, rule evaluations, alarm state, audit events, point health, simulated reads, replay, Modbus import, scenarios, operational reset, seeded operations context, deterministic facility topology, and the standards basis. `GET /facility-topology` identifies the active SQLite facility and fixture version and returns the complete ordered pressure cascade, process-exhaust relationships, dependencies, and typed point bindings. Mutating routes write only to the local laboratory database.

`GET /standards-basis` returns one complete atomic reviewer snapshot. The read-only leaf routes are `/standards-basis/profile`, `/standards-basis/controlled-sources`, `/standards-basis/applicability-matrix`, `/standards-basis/requirements`, `/standards-basis/evidence-categories`, and `/standards-basis/traceability`. They remain bound to the repository-versioned flagship package, do not depend on the active SQLite database, and expose no mutation method.

`frontend/index.html` is a single plain HTML, CSS, and JavaScript workbench served at `/` and `/dashboard`. It loads data with `fetch`, renders tables and panels, and provides local buttons or forms for scenario application, reset, sample reads, replay, Modbus import, alarm evaluation and acknowledgement, point updates, point-health evaluation, and alarm-rule creation or editing. A separate read-only section displays the flagship profile, source catalog, provisional applicability matrix, inactive requirements, evidence categories, and compact source-to-evidence traceability. A standards-package load error does not blank the preserved operational panels.

There is no client-side framework, package build, generated asset bundle, or separate web server in the repository.

### External read-only boundary

No live BAS, EPMS, PLC, SCADA, DCIM, Modbus device, or customer system is connected at the checkpoint. All adapters and fixtures are local. There is no implemented external command or write-back path.

The product boundary prohibits any future external command, configuration change, or write-back. Local imports, samples, scenarios, acknowledgements, rule changes, tests, and audit records remain permitted laboratory writes.

### Verification architecture

The repository retains the 211-test Northstar module and 15 focused Milestone 2 tests. Milestone 3 adds deterministic package, validation, atomicity, API, workbench, facility-isolation, terminology, and Northstar-preservation tests. `scripts/run_verification.py` bounds application import to 30 seconds and the complete discovered suite to 300 seconds. See [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for the final counts and timings.

Milestone 1 reproduced the reported import stall in a reused project-local virtual environment and traced it to a mixed Python 3.12/3.14 environment containing macOS cloud-offloaded package files. No application-code or test change was required. With the recorded Python 3.12 dependency set, the application import completed within its bound and all 211 tests passed against isolated test state. See [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for exact versions, timings, counts, and remaining limits.

## Implemented limitations

The current implementation does not include:

- Polling, subscription, background scheduling, or continuous evaluation.
- Live external connectivity or an external read-only adapter.
- Any physical command or external write-back path.
- Separate source-native observation, mapping/normalization, and canonical-observation records.
- A canonical hierarchy from computed point condition to equipment, system, and facility inference.
- Deterministic consequence computation from that hierarchy.
- Numerical or state-determining process-exhaust and pressure-cascade behavior.
- A process-enabled operating-context point, read-only or synthetic controller command/request observation, or dedicated VFD/motor electrical corroboration point.
- The flagship golden scenario or any broader flagship topology beyond the accepted minimum.
- A generalized standards database, persistent applicability workflow, executable requirement pack, requirement status-transition engine, or licensed standards text.
- Evidence-sufficiency rules, bounded findings, the working four-outcome presentation, or qualified human disposition records.
- Durable evidence packaging, provenance manifests, import hashes, or evidence retention across reset.
- Executable alarm-response, impairment, commissioning, functional-test, recovery, or incident-review workflows.
- Runtime AI or an advisory AI boundary.
- Authentication, authorization, multi-user identity, or role enforcement.
- A documented deployment, production hardening, backup, restore, monitoring, or upgrade architecture.
- Performance, concurrency, scale, accessibility, or cross-browser guarantees.

## Planned architecture direction

The following is intended direction, not implemented architecture:

- Explicit source-native observations, versioned mappings and normalization, canonical observations, computed point conditions, and temporal semantics.
- A versioned golden-scenario evidence and replay package, including a read-only or synthetic controller command/request indication and VFD or motor electrical corroboration.
- Traceable equipment, system, pressure-cascade, facility, consequence, and uncertainty inference.
- Required-evidence rules that preserve an indeterminate result when evidence is insufficient or contradictory.
- Bounded findings and reproducible evidence manifests that survive approved active-state reset.
- Separate qualified human verification, authorization, action, waiver, commissioning acceptance, recovery review, and final-disposition records.
- New recovery observations and a separate recovery evaluation.
- A guided technical and portfolio demonstration that remains usable with AI disabled.
- Optional bounded controls-assurance comparisons, read-only adapters, and advisory AI only after the flagship proof.

Exact schemas, fields, state vocabularies, temporal semantics, outcome structure, persistence, human-record models, evidence retention, topology expansion, and adapter contracts require approved ADRs and roadmap slices. This section must not be used to claim those capabilities exist.
