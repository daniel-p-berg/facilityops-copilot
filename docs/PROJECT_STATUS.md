# FacilityOps Copilot Project Status

## Status basis

- **Status date:** 2026-07-22
- **Current branch:** `codex/m2-flagship-topology` (no configured upstream; one commit ahead of `origin/main` by ancestry before this documentation edit)
- **Current implementation commit:** `6c52f8c6b46ecd49f816f04cbd6ba2c5b881f5fc`
- **Milestone 2 base commit:** `f37f2da01cfe88f38f1f70ea54f98ef51dde44ab`
- **Verification base commit:** `5718e5060935ba8b813b7354be094d44f4ee383b`
- **Implemented legacy environment:** Fictional Northstar Data Hall
- **Implemented flagship scope:** Minimum fictional Advanced Materials Research and Precision-Environment Facility catalog and topology
- **Planned golden scenario:** Process-exhaust failure causing pressure-cascade degradation

This document reports verified repository reality separately from the intended product in [`PRODUCT_CHARTER.md`](PRODUCT_CHARTER.md). “Implemented” means present in the described implementation and supported by source inspection plus the verification evidence stated below; it does not imply production readiness or domain certification.

The 2026-07-22 documentation rebaseline changes project identity, standards policy, authority boundaries, and planned milestone order. It does not change application behavior, database schemas, fixture version `1.0.0`, numerical criteria, or the completed Milestone 1 and Milestone 2 evidence.

## Verification record

Milestone 1 verification reproduced the previously reported import stall and identified an environmental cause rather than an application-code or test defect. The reused project-local `.venv` contained both Python 3.12 and 3.14 interpreter/package artifacts, while its default `python` executable selected Python 3.12. On macOS, 1,993 files in that environment were cloud-offloaded `dataless` placeholders. Bounded diagnostics showed Python blocked in `importlib` while reading an offloaded Uvicorn module. Imports completed after the required files were hydrated.

The repeatable baseline uses a fresh Python 3.12 environment outside the cloud-synchronized repository, pinned direct dependencies from `requirements.txt`, and `python scripts/run_verification.py`. The runner records resolved versions, limits the application import to 30 seconds, and limits `python -m unittest discover -s tests` to 300 seconds.

Verification completed with Python 3.12.13, FastAPI 0.136.3, Starlette 1.2.1, Pydantic 2.13.4, Uvicorn 0.49.0, AnyIO 4.13.0, and the Python standard-library `unittest` runner:

- `import backend.main` completed successfully in 0.613 seconds.
- All 211 discovered tests passed: 211 passed, 0 failed, 0 errored, and 0 skipped.
- The test body completed in 2.693 seconds; the bounded suite process completed in 2.949 seconds.
- A bounded eight-test API/dashboard smoke selection passed in 0.364 seconds, covering dashboard loading, operations summary, scenario application, generated-alarm evaluation, operational reset, replay, and Modbus import preview behavior.
- The normal `db/facilityops.sqlite3` SHA-256 remained unchanged before and after verification.

The earlier targeted checks completed successfully against an isolated temporary SQLite database for:

- Sample loading and expected record counts.
- Seeded operations-overview retrieval.
- The five-point Northstar utility/cooling scenario.
- Generated-alarm evaluation into pending state.
- Operational reset and restoration of seeded current values.
- Static Modbus-map preview with zero validation errors.
- Six deterministic CSV replay steps and six ingested samples.

The full-suite result above supersedes the earlier unknown status. It verifies the current 211-test suite in the recorded environment; it does not establish production readiness or validate every possible dependency combination.

Milestone 2 verification uses a fresh Python 3.12.13 environment outside the repository with FastAPI 0.136.3, Starlette 1.3.1, Pydantic 2.13.4, Uvicorn 0.49.0, and AnyIO 4.14.2. The bounded application import completes in 1.496 seconds. The implementation retains all 211 Northstar tests and adds 15 focused tests: the legacy 211-test module passes unchanged, the focused Milestone 2 module passes, and all 226 discovered tests pass together. The full test body completes in 5.725 seconds and the bounded suite process completes in 6.440 seconds. Focused coverage verifies exact flagship counts, stable facility identity and fixture version, every ADR 0001 entity and relationship, point ownership and typed bindings, pressure direction and cascade order, duty/standby roles, manifest and cross-fixture rejection, transaction rollback, deterministic topology query output, facility-aware reset, and Northstar compatibility.

Representative isolated-database smoke checks load and query the flagship through the documented CLI, exercise `GET /facility-topology`, reset a flagship runtime sample to its declared zero-observation baseline, and load/reset Northstar to its unchanged 17-value baseline. The normal `db/facilityops.sqlite3` SHA-256 remains `39a6538b3689703b95cd2ae00a31ebcd1c5c2f978bbe1d49db3d64bbc2451648` before and after implementation verification.

The 2026-07-22 documentation review independently reproduced the current baseline from a fresh temporary Python 3.12.13 environment before editing. Application import completed in 0.660 seconds, and all 226 discovered tests passed in 5.006 seconds of bounded process time. After the documentation-only edits, the same bounded environment completed application import in 0.407 seconds and all 226 tests in 4.500 seconds. The normal SQLite database retained the SHA-256 above before and after both runs.

## Implemented

### Repository and runtime shape

- Python application using SQLite, FastAPI, Uvicorn, and a plain HTML/JavaScript frontend.
- Local database generation from fictional CSV fixtures.
- Root and `/dashboard` routes serving the workbench.
- JSON API routes for catalogs, state, evaluation, replay, import, scenarios, reset, and seeded operations context.

### Northstar catalog and point observations

- Ten fictional Northstar equipment records and seventeen point records in the seeded fixture.
- Seventeen seeded current point values.
- Normal point ingestion appends point-sample history and updates the latest-value `current_point_values` projection.
- Point metadata for value, unit, quality, timestamps, source, protocol, address, stale window, override, and out-of-service status.
- Manual local point updates, deterministic scenario samples, simulated-driver samples, and CSV replay samples.

### Minimum flagship catalog and topology

- One versioned JSON/CSV fixture package for facility ID `FACILITY-ADVANCED-MATERIALS-RESEARCH`, fixture version `1.0.0`.
- Ten real equipment records and sixteen equipment-owned point records covering fan availability, run, fault, and speed evidence; airflow; duct static; damper position; treatment permissive; supply/makeup-air status; process-laboratory zone pressure; and both boundary differential pressures.
- Three zones forming the explicit corridor → transition/airlock → process-laboratory chain.
- One process-exhaust system, two directed pressure boundaries, one shared exhaust path, and two monitored dependencies.
- Ten typed topology relationship rows: two duty/standby memberships, one system-zone service, two fan/shared-path memberships, one path/treatment dependency, one boundary/system dependency, two boundary/supply dependencies, and one cascade-order link.
- Eight typed point bindings: one zone, one system, two pressure-boundary, two shared-path, and two monitored-dependency bindings.
- No current-value baseline, numerical pressure limit, point-condition semantics, temporal rules, equipment/system/facility state, consequence logic, scenario observation, or executable control behavior.
- No read-only or synthetic controller command/request observation and no dedicated VFD or motor electrical corroboration point. Exact evidence and topology expansion are deferred.

### Facility fixture loading and topology persistence

- Explicit standard-library JSON manifest selection with standard-library CSV package data.
- Complete in-memory validation before the target database is opened or mutated.
- One explicitly selected facility per SQLite database and rejection of the normal project database as a flagship target.
- Additive typed relational storage with concrete endpoint columns, uniqueness/check constraints, and declared foreign keys; global SQLite foreign-key enforcement remains disabled.
- One-connection, one-transaction replacement of facility identity, catalog, topology, relationships, and typed bindings, with post-load row comparison and foreign-key consistency inspection.
- Rejection of duplicate or unstable IDs, missing endpoints, invalid roles, invalid/self-referential directions, duplicate relationships, incomplete or cyclic cascades, cross-fixture rows/references, and invalid or multiple primary point bindings.
- Rollback preserves the prior database after an injected write failure. Invalid packages fail before the database transaction and leave prior bytes unchanged.

### Facility topology query

- Deterministic service, CLI, and `GET /facility-topology` output identifies the active facility ID and fixture version.
- The flagship result exposes both directed boundaries and ordered zones, process-exhaust service, duty/standby fan roles, shared-path memberships, treatment and supply/makeup-air dependencies, cascade ordering, and all relevant typed point bindings.

### Deterministic alarm behavior

- Seven seeded alarm rules covering analog, boolean, and enum comparisons.
- Stateless deterministic rule evaluation.
- Point-health gating for bad, uncertain, stale, overridden, and out-of-service samples.
- Generated `PENDING`, `ACTIVE`, and `CLEARED` alarm states.
- Configured delays and analog clear-value hysteresis.
- Local alarm acknowledgement without automatic clear or suppression.
- Rule and triggering-sample snapshots on generated alarms.
- Audit events for alarm lifecycle, acknowledgement, alarm-rule creation or change, point-health changes, stale detection, and Modbus import commit.

### Replay, import, scenarios, and reset

- Deterministic local `SimulatedDriver` reads.
- Sequence-filtered CSV replay ingestion.
- Explicit step and run-all replay workflows that evaluate alarms at replay timestamps.
- Static Modbus register-map preview and local catalog commit.
- Northstar point-trigger and normalization scenarios.
- A five-point Northstar utility, UPS, generator-readiness, and cooling scenario.
- Facility-aware operational reset that preserves catalog, rule, facility, topology, relationship, and binding configuration; deletes current runtime samples, values, generated alarms, and audit events; and resolves only the exact selected fixture baseline.
- Northstar reset restores the unchanged 17-value baseline. Flagship reset restores zero observations and cannot load Northstar point values.

### Seeded operational context

- One fictional Northstar facility-scenario record.
- One curated correlation with five curated evidence-member rows.
- Nine fictional timeline events.
- One shift-turnover record.
- Two equipment out-of-service records.
- Four corrective-action records.
- Four fictional procedure references.
- One fictional reliability report.
- API and frontend display for the records above.

The correlation, root-cause hypothesis, confidence, reliability metrics, and executive summary are curated fictional seeded assertions. They are not calculated from implemented equipment, system, or facility inference and are not AI-generated at runtime.

### External-system boundary

- No live external BAS, EPMS, PLC, SCADA, DCIM, Modbus device, or customer system is connected.
- No external command, configuration-change, or write-back path is implemented.
- Existing writes affect only the local laboratory database and files explicitly selected by a local user or developer.

## Partially Implemented

### Vendor neutrality

The point and equipment catalogs use generally vendor-neutral fields, and the static Modbus importer is separated from alarm evaluation. However, only one import shape and two local sample adapters exist, and Modbus equipment/location inference contains Northstar-specific assumptions. A canonical adapter contract has not been proven across multiple source profiles.

### Read-only product boundary

The checkpoint has no live external connectivity or control path, which is consistent with the boundary. It does not yet contain a formal adapter capability model or technical guard proving that future external adapters cannot expose command methods.

### Point state and health

Quality, staleness, override, out-of-service, and rule eligibility are implemented. A distinct, approved point-condition model and complete temporal semantics for out-of-order observations are not.

### Auditable evidence

Alarm trigger snapshots and audit events provide useful evidence. Provenance is incomplete: imports and replay runs lack durable manifests and source hashes, higher-layer inferences and bounded findings do not exist, and operational reset deletes point-sample history, generated alarms, and all audit events before reseeding the baseline. Durable observation and incident retention is planned but not implemented.

### Standards, applicability, requirements, and findings

The repository contains no implemented Standards Reference Registry, Applicable Requirements Baseline, executable synthetic SOO requirement pack, evidence-sufficiency evaluation, bounded-finding record, evidence manifest, or human review/disposition model.

Existing alarm rules are deterministic local laboratory rules. They are not controlled standards requirements, code-compliance tests, owner-approved criteria, commissioning criteria, or evidence that the flagship topology conforms to an applicable requirement.

The dated standards baseline and [STANDARDS_POSITION.md](STANDARDS_POSITION.md) are documentation references only. They do not retrofit standards, conformance, or evidence-sufficiency claims into Milestones 1 or 2.

### Operator response

Acknowledgement, procedure references, corrective actions, timelines, and turnover records exist. Except for acknowledgement, most are seeded display records rather than an executable response workflow with required transitions and evidence.

### Impairment management

Equipment OOS records and point OOS gating exist. There is no complete impairment lifecycle, authorization model, compensatory monitoring, extension, restoration evidence, or deterministic integration with system and facility inference.

### Functional testing and commissioning

Scenarios, replay, deterministic rules, and reset are useful test primitives. There is no implemented test plan, prerequisite, step, controlled test observation, deterministic evaluation record, exception, abort, qualified human acceptance, or signed recovery workflow.

### Recovery and incident review

Alarm clearing, normalization scenarios, reset, a seeded timeline, and recovery-oriented sample text exist. There is no computed recovery inference, retained incident evidence across reset, or reproducible incident reconstruction workflow.

### Consequence and reliability presentation

The dashboard presents curated operational impact, mitigation, correlation, and reliability text. These are not computed consequences from implemented inference rules or calculated reliability results.

### Training and decision support

The local sandbox can demonstrate deterministic behavior, but it does not yet implement trainee information boundaries, decision checkpoints, expected-versus-observed review, or an advisory AI layer.

## Planned

- Only the bounded flagship topology and evidence expansions required by an approved technical question beyond the accepted Milestone 2 minimum.
- A controlled applicability profile and project-authored synthetic SOO requirement pack informed by controlled references.
- The process-exhaust failure and pressure-cascade-degradation golden scenario.
- Source-native observation preservation, versioned mapping and normalization, canonical observations, computed point conditions, and explicit equipment/system/facility inference layers.
- A read-only or synthetic controller command/request observation and VFD or motor electrical corroboration evidence.
- Deterministic operational consequences with affected scope, evidence, and uncertainty.
- Bounded findings with explicit insufficient-evidence behavior and the working four-outcome presentation.
- Durable provenance, evidence manifests, and evidence that survives clearing active laboratory state.
- Separate human verification, test authorization, operational action, commissioning acceptance, waiver, recovery review, and final-disposition records.
- An optional bounded read-only adapter or controls-assurance comparison after the flagship proof.
- An optional advisory AI layer that cites controlled evidence and cannot mutate computed records or exercise human authority.

Planned capabilities are not implemented and must not be presented as current behavior.

## Unknown/Not Verified

- Live Uvicorn startup and network HTTP behavior of every route. Application import and in-process ASGI route behavior are covered by the verified suite.
- Cross-browser behavior and accessibility of the workbench.
- Concurrency, performance, locking, and data-volume limits.
- Behavior with SQLite foreign-key enforcement enabled.
- Backup, restore, database upgrade, and long-term evidence-retention behavior.
- Authentication, authorization, multi-user identity, and deployment security; these are not implemented.
- Production deployment, monitoring, availability, and recovery characteristics.
- Domain validation of the implemented minimum fictional topology and of all planned operating modes, numerical pressure relationships, consequence rules, and functional-test criteria.
- Regulatory, industrial-hygiene, process-safety, cleanroom, code-compliance, or commissioning acceptance status; no such validation or qualified human disposition exists.
- Final vocabulary and relationships for alarm priority, point condition, operational risk, advisory classification, and incident severity.
