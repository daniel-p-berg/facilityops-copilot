# FacilityOps Copilot Project Status

## Status basis

- **Status date:** 2026-07-19
- **Checkpoint commit:** `627d37ef99e9d9b3936317cffbe9c5037537b219`
- **Implemented legacy environment:** Fictional Northstar Data Hall
- **Planned flagship:** Fictional Advanced Materials Research and Precision-Environment Facility
- **Planned golden scenario:** Process-exhaust failure causing pressure-cascade degradation

This document reports verified repository reality separately from the intended product in [`PRODUCT_CHARTER.md`](PRODUCT_CHARTER.md). “Implemented” means present in the checkpoint and supported by source inspection plus the verification evidence stated below; it does not imply production readiness or domain certification.

## Verification record

Targeted checks completed successfully against an isolated temporary SQLite database for:

- Sample loading and expected record counts.
- Seeded operations-overview retrieval.
- The five-point Northstar utility/cooling scenario.
- Generated-alarm evaluation into pending state.
- Operational reset and restoration of seeded current values.
- Static Modbus-map preview with zero validation errors.
- Six deterministic CSV replay steps and six ingested samples.

The complete 211-test suite remains **unknown/unverified**. The documented test command did not begin executing tests because importing FastAPI stalled in the local Python 3.12 environment and was interrupted. No full-suite pass is claimed.

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
- Operational reset that preserves catalog and rule configuration, deletes point samples, and reseeds the laboratory baseline and current-value projection.

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

The correlation, root-cause hypothesis, confidence, reliability metrics, and executive summary are curated fictional seeded assertions. They are not calculated from an implemented equipment/system/facility state engine and are not AI-generated at runtime.

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

Alarm trigger snapshots and audit events provide useful evidence. Provenance is incomplete: imports and replay runs lack durable manifests and source hashes, computed determinations do not exist, and operational reset deletes point-sample history, generated alarms, and all audit events before reseeding the baseline. Durable observation and incident retention is planned but not implemented.

### Operator response

Acknowledgement, procedure references, corrective actions, timelines, and turnover records exist. Except for acknowledgement, most are seeded display records rather than an executable response workflow with required transitions and evidence.

### Impairment management

Equipment OOS records and point OOS gating exist. There is no complete impairment lifecycle, authorization model, compensatory monitoring, extension, restoration evidence, or deterministic integration with system and facility state.

### Functional testing and commissioning

Scenarios, replay, deterministic rules, and reset are useful test primitives. There is no implemented test-plan, prerequisite, step, observation, acceptance, exception, abort, or signed recovery workflow.

### Recovery and incident review

Alarm clearing, normalization scenarios, reset, a seeded timeline, and recovery-oriented sample text exist. There is no derived recovery state, retained incident evidence across reset, or reproducible incident reconstruction workflow.

### Consequence and reliability presentation

The dashboard presents curated operational impact, mitigation, correlation, and reliability text. These are not authoritative deterministic consequences or calculated reliability results.

### Training and decision support

The local sandbox can demonstrate deterministic behavior, but it does not yet implement trainee information boundaries, decision checkpoints, expected-versus-observed review, or an advisory AI layer.

## Planned

- The fictional Advanced Materials Research and Precision-Environment Facility catalog and topology.
- The process-exhaust failure and pressure-cascade-degradation golden scenario.
- Explicit deterministic point, equipment, system, and facility state layers.
- Deterministic operational consequences with affected scope, evidence, and uncertainty.
- Durable provenance and evidence that survives clearing active laboratory state.
- Bounded operator-response, impairment, functional-testing, recovery, and incident-review workflows.
- A vendor-neutral read-only adapter contract proven by more than one source profile.
- An optional advisory AI layer that cites authoritative evidence and cannot mutate authoritative state.

Planned capabilities are not implemented and must not be presented as current behavior.

## Unknown/Not Verified

- Complete result of the 211-test suite in the current local environment.
- Startup and live HTTP behavior of every route with the currently installed FastAPI, Starlette, and Pydantic versions.
- Cross-browser behavior and accessibility of the workbench.
- Concurrency, performance, locking, and data-volume limits.
- Behavior with SQLite foreign-key enforcement enabled.
- Backup, restore, database upgrade, and long-term evidence-retention behavior.
- Authentication, authorization, multi-user identity, and deployment security; these are not implemented.
- Production deployment, monitoring, availability, and recovery characteristics.
- Domain correctness of the planned flagship topology, operating modes, pressure relationships, consequence rules, and functional-test criteria.
- Regulatory, industrial-hygiene, process-safety, cleanroom, or commissioning acceptance; no such validation or claim exists.
- Final vocabulary and relationships for alarm priority, point condition, operational risk, advisory classification, and incident severity.
