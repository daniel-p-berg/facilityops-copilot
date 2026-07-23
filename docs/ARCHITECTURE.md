# FacilityOps Copilot Architecture

## Document basis

This document describes the verified implementation through the 2026-07-23 canonical-observation and repository replay tranche, built on accepted Milestone 3 baseline `e5064b2fabb3e338d1d6108904c176ffc6954faa`, and separately identifies planned direction. The implemented section is descriptive, not aspirational. Product identity and authority are governed by [`PRODUCT_CHARTER.md`](PRODUCT_CHARTER.md), standards policy is summarized in [`STANDARDS_POSITION.md`](STANDARDS_POSITION.md), and verification status is tracked in [`PROJECT_STATUS.md`](PROJECT_STATUS.md).

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

The implemented tranche now reaches a separate rebuildable reported-observation projection:

```text
source delivery
→ immutable source-native record
→ pinned mapping and canonicalization
→ immutable canonical observation
→ source-scoped reported-observation projection
```

The projection uses explicit event-time and knowledge-time cutoffs and ingestion-specific dispositions. It remains a view of what an identified source reported; point condition and every equipment/system/facility inference layer remain unimplemented.

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

Reference sources, applicability bases, synthetic requirements, executable evaluations, computed findings, and human dispositions remain distinct. The bounded Milestone 3 implementation represents controlled sources, provisional applicability bases, inactive project-authored synthetic requirements, and required evidence categories for one flagship. It does not implement applicability approval, requirement execution, evidence-sufficiency evaluation, findings, an incident-level evidence manifest linked to findings, or disposition. The later replay reproducibility manifest is a narrower integrity record.

### Computation and human authority

Deterministic code owns reproducible computation. It produces computed point conditions, inferred states, timing results, replay outputs, evaluations, and bounded findings under identified inputs, assumptions, configuration, and rules. Determinism provides reproducibility, not automatic validity. The following authorities remain with persons or organizations that possess the required qualifications and assigned organizational or legal authority: applicability decisions, requirement approval, test authorization, operational action, commissioning acceptance, waivers, final disposition, determinations of physical safety, and authorization for operation.

After a recorded action or response, FacilityOps may receive new observations. The action or response record does not establish causation or physical effect. Recovery requires new post-action observations and a separate evaluation.

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

The canonical observation replay is a second repository-versioned path with a dedicated local SQLite store:

```text
allowlisted synthetic replay + mapping + topology packages
→ complete bounded structural validation and deterministic canonicalization
→ one-transaction publication to db/facilityops-observations.sqlite3
→ immutable source-native, canonical, lineage, conflict, and manifest records
→ bounded facility-aware APIs
→ observation/replay reviewer workbench
```

This store is initialized lazily only by an explicit replay execution. Application import and legacy operational reset do not open it.

### Data and loading

`analysis/load_alarm_db.py` remains the default Northstar compatibility loader. It loads the existing Northstar equipment catalog, point catalog, seeded current values, alarm rules, and operational-context fixtures. After a successful load it records the stable Northstar facility identity and fixture version through additive facility metadata; it does not rewrite existing Northstar identifiers or values.

`analysis/facility_fixture_loader.py` is the explicit manifest-driven loader for registered flagship fixture versions `1.0.0` and `1.1.0`. The caller must provide both the versioned JSON manifest and an isolated target database. The loader rejects the normal project database, reads and validates every declared CSV before opening the target, and replaces catalog, facility identity, topology, typed relationships, and typed point bindings through one connection and one explicit transaction. A write or post-load validation failure rolls back the complete replacement.

The flagship validator checks manifest/file facility and version agreement, stable and unique identifiers, mandatory point-to-equipment ownership, typed endpoint existence, relationship uniqueness, constrained duty/standby roles, explicit pressure direction, a connected acyclic two-boundary cascade, one primary topology binding per point, and the complete accepted version-specific inventory. Version `1.1.0` carries stable topology identity `TOPOLOGY-FLAGSHIP-PROCESS-EXHAUST`, adds only the point owners, reported-indication definitions, and bindings accepted by ADR 0006, and forbids normal ranges on its observation-only additions. Post-load validation re-queries stored rows and bindings and runs `PRAGMA foreign_key_check` without globally enabling SQLite foreign keys in the legacy facility database.

`backend/services/standards_basis_service.py` validates either registered standards-basis version independently of active SQLite state. Version `1.0.0` remains the default historical review package. Version `1.1.0` binds the exact topology `1.1.0` identity and content digest and may differ from `1.0.0` only in the approved point-definition representation and corresponding explanatory text. Both packages retain the same profile, sources, provisional applicability, requirements, inactive/non-executable state, fixed qualitative schema, `NO_NUMERICAL_CRITERIA_APPROVED` parameter status, and `NO_FLAGSHIP_OBSERVATION_BASELINE`. Only a fully valid candidate replaces the in-memory snapshot. Failed reload leaves the prior snapshot exposed, and every read returns a defensive copy.

`backend/services/observation_package_service.py` maintains the exact allowlist for one repository mapping package and one repository synthetic replay package. It resolves only registered manifests, requires the bounded package layout, enforces aggregate package, per-file, delivery-count, and per-delivery payload limits, verifies parsed-content digests and exact topology/mapping/source pins, rejects path escape and prohibited evidentiary claims, and structurally validates the complete narrative, deliveries, and structural oracle—including every oracle reference—before returning a package. There is no arbitrary path, archive, URL, upload, or live-ingestion contract.

`backend/services/observation_replay_service.py` converts a structurally validated package into a complete in-memory replay plan before persistence. It classifies source-event identities and redeliveries, preserves temporal and ordering facts, applies only the pinned mapping version, emits typed canonical observations and exact field lineage, builds projection summaries, and computes run-independent semantic digests. It uses fixed package clocks; wall-clock time does not determine replay results.

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

Milestone 3 adds no SQLite table or migration and does not alter the flagship topology package or fixture version `1.0.0`. The later topology `1.1.0` is a separate additive fixture version, not a migration of an existing facility database.

### Dedicated observation replay store

`backend/services/observation_store.py` uses `db/facilityops-observations.sqlite3` by default. This database is separate from the legacy operational database because legacy reset deliberately deletes runtime point and audit history and because the accepted observation schema requires enabled foreign keys and immutable evidence. Importing the application has no observation-store side effect. Explicit replay execution initializes the directory and schema in a rollback-capable transaction.

The store contains:

- Immutable package/configuration snapshots: `topology_snapshots`, `source_bindings`, `mapping_snapshots`, and `replay_package_snapshots`.
- Execution identity and retry records: `replay_executions` and `replay_execution_requests`.
- Source evidence: `source_event_groups`, `replay_deliveries`, and `source_native_records`.
- Derived reported evidence: `canonical_observations`, `canonical_observation_lineage`, and `canonical_decode_issues`.
- Narrative and reproducibility records: `replay_annotations` and `reproducibility_manifests`.

Every connection enables and verifies `PRAGMA foreign_keys = ON`. Concrete composite keys bind facility, execution, source, event group, topology, mapping, and package scopes. Typed canonical-value columns permit Boolean, integer, decimal, text, or enum values with one active storage representation. Triggers reject update or deletion of accepted evidence, and an additional trigger prevents lineage from crossing execution, facility, source, mapping, or source-event scope.

The service validates and canonicalizes the entire replay before opening the publication transaction. One `BEGIN IMMEDIATE` transaction inserts or verifies immutable snapshots and publishes the execution, deliveries, native records, canonical records, lineage, decode issues, annotations, and manifest. Injected schema or replay failure rolls back. The store exposes no destructive reset. This is an additive laboratory evidence store without a general migration, backup, export, or production retention architecture.

List queries require facility and execution scope and cap page size at 100. JSON and package payloads are bounded. These constraints are abuse and reviewability controls for the local laboratory, not performance or production-scale guarantees.

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

### Canonical observation semantics and projection

`backend/domain/observation_semantics.py` owns deterministic JSON hashing, strict RFC 3339 parsing and UTC normalization, decimal normalization, signed 32-bit register decoding, strict Boolean and direct enum normalization, and source ordering/temporal facts. Source-native time preserves the original text, offset, precision, and fractional-second count separately from normalized UTC. Missing and invalid time remain explicit. Receipt time is a separate knowledge-time fact.

The identity classifier keeps request retry, delivery receipt, source-event identity, native record, canonical record, and replay execution separate. When a stable source identity exists, equal payload and material metadata create an exact redelivery group; different material creates unresolved variants even when the deliveries pin different mapping versions. When no stable identity exists, FacilityOps does not infer one from equal content, timestamp, value, or digest.

Canonicalization is restricted to declared source-representation transforms. One source-native snapshot may yield multiple point reports; a declared decode group and component roles may combine multiple native register records into one reported value; and partial payloads yield only fields actually present. Register-component derivation enumerates every distinct complete logical component combination, deduplicates only exact stable-event redeliveries, and retains valid earlier composites when a later variant cannot be paired. Component source-event conflicts remain visible through lineage at the requested knowledge cutoff. Every canonical record carries an exact mapping ID/version/digest and canonicalizer version. Reprocessing under another mapping creates another derivation and never updates the prior record.

`backend/domain/reported_observation_projection.py` rebuilds one reported-observation projection from immutable candidates. Its scope includes facility, replay execution, source/channel binding, canonical point, and mapping derivation. Both `as_of_observed_at` and `known_by_received_at` are mandatory. Exact redelivery collapses only as a logical candidate; valid older events do not displace valid newer events; future-at-event-cutoff and not-yet-known-at-receipt-cutoff reports are ineligible; and missing/invalid order is not promoted by receipt order.

The projection returns no scalar value for a latest conflict, materially different equal-order reports, sequence/time disagreement, or unordered frontier, and it never falls back silently to an older candidate. Distinct source-event identities remain distinct logical candidates; when their equal-order normalized report material is equivalent, the projection may return their common reported scalar while retaining every canonical and native identity in the selected candidate. Its dispositions (`NO_OBSERVATION`, `NO_ELIGIBLE_REPORT`, `REPORTED`, `CONFLICT_PRESENT`, and `UNORDERED`) describe ingestion evidence only. The projection does not merge distinct source bindings, compute point condition, or infer physical state.

### Golden synthetic observation replay

The mapping package `MAPPING-PACKAGE-FLAGSHIP-SYNTHETIC-INDICATIONS` version `1.0.0` is bound to the exact topology `1.1.0` digest and canonicalizer `facilityops-canonicalizer/1.0.0`. Source bindings carry declared or `UNKNOWN` controller, gateway, device, measurement-chain, power, timestamp, and derivation origins. The data model makes no evidence-independence conclusion.

The allowlisted `flagship-process-exhaust-evidence-sequence` version `1.0.0` is an observation replay, not an outcome scenario. Its 20 narrative entries contain received-indication groups and one non-authoritative asserted-action annotation. Package context is pinned separately in the manifest. Its oracle specifies only structural record counts, identity groups, lineage, ordering facts, and projection dispositions. Recovery evaluation, findings, and human disposition are not implemented.

Each execution receives a separate replay-execution ID and per-execution record identities. The request idempotency key is facility-scoped: identical normalized request content returns the accepted execution, while different content under the same key is rejected. Separate executions retain separate records but produce the same normalized semantic digest. The per-execution manifest pins package, topology, mapping, canonicalizer, input, derived-record, duplicate/conflict, and projection facts while excluding random run IDs and non-semantic creation time from its semantic digest.

The replay provides no point condition, fan-failure or changeover result, equipment/system/facility inference, pressure-cascade or containment conclusion, physical or temporal criterion, evidence-sufficiency or independence evaluation, consequence, conformance finding, human disposition, authorization, or recovery evaluation.

### Scenarios and operational reset

`backend/summary.py` defines deterministic Northstar alarm scenarios in Python. Applying a scenario writes local point samples and current values but does not automatically evaluate generated alarms. The checkpoint adds a multi-point utility, UPS, generator-readiness, and cooling scenario.

`backend/services/operational_reset_service.py` reads the exact facility ID and fixture version from the selected database and resolves only that registered package context before beginning a write transaction. It preserves facility identity, equipment, points, alarm rules, topology, typed relationships, typed bindings, and imported Modbus catalog metadata. It deletes generated alarms, alarm events, current-value rows, and point samples before recreating only the selected fixture's baseline projection.

Northstar reset restores the unchanged 17-value baseline. Both registered flagship topology packages have no current-value baseline, so their reset loads zero current values. Missing or unknown facility context, an unavailable baseline, or a cross-fixture baseline override fails before mutation; reset never falls back to Northstar.

Because reset deletes legacy `point_samples` and `alarm_events`, it destroys current Northstar-compatible point-sample history and local alarm/audit history before reseeding that laboratory baseline. This remains implemented behavior. Reset does not open or delete the separate append-only observation replay store, so accepted canonical replay evidence survives an operational reset. That isolation is bounded replay retention only; complete incident retention linking future inferences, findings, human records, and recovery evidence remains planned.

### Seeded operations context

The checkpoint loads and exposes a fictional Northstar utility-disturbance story: a facility scenario, one alarm correlation with evidence members, an incident timeline, shift turnover, equipment OOS records, corrective actions, procedure references, and a reliability report.

These records are curated CSV assertions. They are returned and displayed, not computed through the planned point-condition and equipment/system/facility inference chain. Correlation confidence, root-cause hypothesis, availability, MTTR, alarm counts, OOS hours, and executive summary are seeded values rather than derived results.

### API and frontend

`backend/main.py` exposes local JSON routes for summaries, catalogs, values, rule evaluations, alarm state, audit events, point health, simulated reads, legacy CSV replay, Modbus import, scenarios, operational reset, seeded operations context, deterministic facility topology, the standards basis, and synthetic observation replay inspection. `GET /facility-topology` identifies the active legacy SQLite facility and fixture version and returns the complete ordered pressure cascade, process-exhaust relationships, dependencies, and typed point bindings. Mutating routes write only to the applicable local laboratory database.

`GET /standards-basis` returns one complete atomic reviewer snapshot. The read-only leaf routes are `/standards-basis/profile`, `/standards-basis/controlled-sources`, `/standards-basis/applicability-matrix`, `/standards-basis/requirements`, `/standards-basis/evidence-categories`, and `/standards-basis/traceability`. They remain bound to the repository-versioned flagship package, do not depend on the active SQLite database, and expose no mutation method.

Facility-aware observation routes use the prefix `/facilities/{facility_id}/observation-replay`. They provide:

- `GET /packages` and `GET /packages/{package_id}/versions/{package_version}` for the allowlisted catalog and structurally validated package detail.
- `POST /executions` for explicit local execution from package identity/version and an idempotency key. The optional execution ID is a distinct field; arbitrary package-path fields are rejected.
- `GET /executions/{replay_execution_id}` and `/manifest` for status and the reproducibility manifest.
- Paginated source-native and canonical-observation list routes with source/event/time filters, plus execution-scoped detail routes.
- An execution-scoped canonical lineage route and paginated redelivery/conflict groups.
- A reported-observation projection route requiring complete source/mapping scope plus `as_of_observed_at` and `known_by_received_at`.

List page size defaults to 50 and is capped at 100. Routes verify facility and execution scope before returning records, reject cross-execution detail references, normalize canonical observation time-range filters, and map request/digest identity conflicts to HTTP 409. The API exposes no generic ingest, arbitrary package path, or observation reset.

`frontend/index.html` is a single plain HTML, CSS, and JavaScript workbench served at `/` and `/dashboard`. It loads data with `fetch`, renders tables and panels, and provides local buttons or forms for scenario application, reset, sample reads, legacy CSV replay, Modbus import, alarm evaluation and acknowledgement, point updates, point-health evaluation, and alarm-rule creation or editing.

A separate synthetic observation replay section catalogs the allowlisted package, displays package/topology/mapping/canonicalizer identities and digests plus the structural oracle, starts an isolated execution with an explicit idempotency key, compares source-reported observed time with FacilityOps receipt time, inspects source-native records, canonical observations, exact lineage, redelivery/conflict groups, explicit-cutoff projection results, and the reproducibility manifest. It states that the section computes no equipment, system, facility, conformance, safety, authorization, or recovery conclusion.

The standards section continues to display the flagship profile, source catalog, provisional applicability matrix, inactive requirements, evidence categories, and compact source-to-evidence traceability. It explicitly retains `NO_FLAGSHIP_OBSERVATION_BASELINE` until a reviewer selects a separate replay execution and states that selection does not modify the standards package. A standards-package or replay-package load error does not blank the preserved operational panels.

There is no client-side framework, package build, generated asset bundle, or separate web server in the repository.

### External read-only boundary

No live BAS, EPMS, PLC, SCADA, DCIM, Modbus device, or customer system is connected at the checkpoint. All adapters and fixtures are local. There is no implemented external command or write-back path.

The product boundary prohibits any future external command, configuration change, or write-back. Local imports, samples, scenarios, acknowledgements, rule changes, tests, and audit records remain permitted laboratory writes.

### Verification architecture

The repository retains the 211-test Northstar module, 15 focused Milestone 2 tests, and 57 focused Milestone 3 tests. The observation tranche adds 88 focused topology-version, package, identity, time, canonicalization, lineage, projection, persistence, atomicity, retry, restart, manifest, API, workbench, facility-isolation, terminology, and validation tests; all 371 discovered tests pass together. `scripts/run_verification.py` bounds application import to 30 seconds and the complete discovered suite to 300 seconds. See [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for exact timings and verification limits.

Milestone 1 reproduced the reported import stall in a reused project-local virtual environment and traced it to a mixed Python 3.12/3.14 environment containing macOS cloud-offloaded package files. No application-code or test change was required. With the recorded Python 3.12 dependency set, the application import completed within its bound and all 211 tests passed against isolated test state. See [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for exact versions, timings, counts, and remaining limits.

## Implemented limitations

The current implementation does not include:

- Polling, subscription, background scheduling, or continuous evaluation.
- Live external connectivity or an external read-only adapter.
- Any physical command or external write-back path.
- A computed point-condition layer or a canonical hierarchy from point condition to equipment, system, and facility inference.
- Deterministic consequence computation from that hierarchy.
- Numerical or state-determining process-exhaust and pressure-cascade behavior.
- Any interpretation of the implemented process-context, request, controller-execution, VFD, motor-current, airflow, dependency, or pressure indications as proof of physical response.
- A flagship failure, changeover, containment, degradation, or recovery outcome scenario. The implemented replay is observation-only.
- A generalized standards database, persistent applicability workflow, executable requirement pack, requirement status-transition engine, or licensed standards text.
- Evidence-sufficiency rules, bounded findings, the working four-outcome presentation, or qualified human disposition records.
- Incident-level evidence packaging linking future inference, findings, human records, and recovery evidence. The implemented replay manifest and reset-isolated observation store are narrower.
- Executable alarm-response, impairment, commissioning, functional-test, recovery, or incident-review workflows.
- Runtime AI or an advisory AI boundary.
- Authentication, authorization, multi-user identity, or role enforcement.
- A documented deployment, production hardening, backup, restore, monitoring, or upgrade architecture.
- Performance, concurrency, scale, accessibility, or cross-browser guarantees.

## Planned architecture direction

The following is intended direction, not implemented architecture:

- Computed point conditions under separately approved evaluation-time, quality, suspect, override, out-of-service, staleness, freshness, lateness, persistence, recovery-hold, validity, and uncertainty semantics.
- Traceable equipment, system, pressure-cascade, facility, consequence, and uncertainty inference.
- Required-evidence rules that preserve an indeterminate result when evidence is insufficient or contradictory.
- Bounded findings and incident-level reproducible evidence manifests beyond the implemented replay-integrity manifest.
- Separate qualified human verification, authorization, action, waiver, commissioning acceptance, recovery review, and final-disposition records.
- Approved recovery-evidence selection and a separate recovery evaluation; the replay's post-action reports are not yet interpreted as recovery evidence.
- A guided technical and portfolio demonstration that remains usable with AI disabled.
- Optional bounded controls-assurance comparisons, read-only adapters, and advisory AI only after the flagship proof.

Exact point-condition and inference schemas, physical and temporal criteria, state vocabularies, outcome structure, human-record models, incident retention, later topology expansion, and adapter contracts require approved ADRs and roadmap slices. This section must not be used to claim those capabilities exist.
