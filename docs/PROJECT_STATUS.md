# FacilityOps Copilot Project Status

## Status basis

- **Status date:** 2026-07-23
- **Current branch:** `codex/m2-flagship-topology` (no configured upstream; local and unpushed)
- **Milestone 3 pre-correction HEAD:** `df83a1fe1a932c6d5194765674fe18799d9c73f6`
- **Milestone 2 base commit:** `f37f2da01cfe88f38f1f70ea54f98ef51dde44ab`
- **Verification base commit:** `5718e5060935ba8b813b7354be094d44f4ee383b`
- **Implemented legacy environment:** Fictional Northstar Data Hall
- **Implemented flagship scope:** Preserved minimum topology `1.0.0`; additive reported-indication topology and standards basis `1.1.0`; canonical source-native and observation semantics; and one allowlisted repository synthetic observation replay
- **Planned golden inference:** Process-exhaust failure and pressure-cascade degradation evaluation from the implemented evidence chain

This document reports verified repository reality separately from the intended product in [`PRODUCT_CHARTER.md`](PRODUCT_CHARTER.md). “Implemented” means present in the described implementation and supported by source inspection plus the verification evidence stated below; it does not imply production readiness or domain certification.

The 2026-07-22 documentation rebaseline changes project identity, standards policy, authority boundaries, and planned milestone order. Milestone 3 then adds a repository-versioned, read-only standards-basis package, validation service, API, and reviewer view without changing database schemas, fixture version `1.0.0`, numerical criteria, alarm behavior, or completed Milestone 1 and Milestone 2 evidence.

The 2026-07-23 bounded tranche implements accepted ADRs 0005 and 0006 through the chain `source delivery → source-native record → canonical observation → reported-observation projection → deterministic synthetic replay`. It adds topology and standards-basis version `1.1.0` without changing either `1.0.0` package, and it stores explicit replay executions in a separate local append-only database. It does not implement point condition, equipment/system/facility inference, physical or temporal criteria, evidence sufficiency or independence, findings, consequences, human workflows, recovery evaluation, alarm changes, live connectivity, external commands, or AI behavior.

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

Representative isolated-database smoke checks load and query the flagship through the documented CLI, exercise `GET /facility-topology`, reset a flagship runtime sample to its declared zero-observation baseline, and load/reset Northstar to its unchanged 17-value baseline. Contemporaneous Milestone 2 verification records reported SHA-256 `39a6538b3689703b95cd2ae00a31ebcd1c5c2f978bbe1d49db3d64bbc2451648` for `db/facilityops.sqlite3` before and after those verification runs; this is historical point-in-time evidence only.

The 2026-07-22 documentation review independently reproduced the current baseline from a fresh temporary Python 3.12.13 environment before editing. Application import completed in 0.660 seconds, and all 226 discovered tests passed in 5.006 seconds of bounded process time. After the documentation-only edits, the same bounded environment completed application import in 0.407 seconds and all 226 tests in 4.500 seconds. Contemporaneous documentation-review records reported the historical SHA-256 above before and after those runs; this is not a statement about the current ignored database file.

Milestone 3 verification used Python 3.12.13, FastAPI 0.136.3, Starlette 1.2.1, Pydantic 2.13.4, Uvicorn 0.49.0, and AnyIO 4.13.0. Application import completed in 0.308 seconds. All 254 discovered tests passed with 0 failures, errors, or skips; the test body completed in 4.770 seconds and the bounded process in 5.027 seconds. The 28 Milestone 3 tests passed separately in 0.133 seconds, all 226 pre-Milestone 3 tests passed separately in 4.321 seconds, and the targeted malformed-reload atomicity test passed in 0.011 seconds. Local Uvicorn and browser inspection confirmed the separate standards workbench loaded all package sections without console errors or horizontal overflow. That verification record reported the normal SQLite database as `39a6538b3689703b95cd2ae00a31ebcd1c5c2f978bbe1d49db3d64bbc2451648`; the acceptance-correction audit described below does not treat that historical report as the current file state.

The normal `db/facilityops.sqlite3` file is ignored by Git and is not a tracked repository artifact. At acceptance-correction preflight it had SHA-256 `57742e8873cdcb23f2b421b5aa7e017812919ef32fdd67ee1071c7f65cc952da`, size 319,488 bytes, and modification time `2026-07-22T21:47:49+0700`. No repository evidence establishes when or why that local file diverged from the historically recorded hash, so this document makes no claim that it remained unchanged across all prior work. The correction pass preserves the file and records pre-verification and post-verification metadata in its external review bundle.

The Milestone 3 acceptance-correction verification used the same Python 3.12.13 dependency set. Application import completed in 0.297 seconds. All 283 discovered tests passed; the test body completed in 4.364 seconds and the bounded process in 4.654 seconds. The 57 focused standards-basis tests passed separately in 0.371 seconds, the 211-test Northstar regression module passed separately in 4.051 seconds, the 15-test flagship-topology module passed separately in 0.354 seconds, and three targeted malformed-package, semantic-atomicity, and controlled-exception tests passed in 0.044 seconds. A local Markdown-link audit checked 88 links across 19 files with no error. The ignored SQLite file retained the same SHA-256, size, and modification time recorded at preflight, which establishes only that this correction pass did not mutate it.

The 2026-07-23 canonical-observation and synthetic-replay verification used Python 3.12.13, FastAPI 0.136.3, Starlette 1.2.1, Pydantic 2.13.4, and Uvicorn 0.49.0. `.venv/bin/python -m unittest discover -s tests` ran all 363 discovered tests successfully in 6.605 seconds. The 80 focused topology, identity, temporal, canonicalization, lineage, projection, store, replay-package, API, and workbench tests passed in 1.959 seconds. Two separate executions of the validated package produced normalized semantic digest `88703f59a062e349b1d3765909275bfebc6062d3f1846c7958677fa808888ec2`. Documentation review checked 126 local Markdown links and all 5 local anchors without error. After those checks, the default observation store remained absent, and the ignored operational database retained SHA-256 `57742e8873cdcb23f2b421b5aa7e017812919ef32fdd67ee1071c7f65cc952da`, size 319,488 bytes, and modification time `2026-07-22T21:47:49+0700`.

## Implemented

### Repository and runtime shape

- Python application using SQLite, FastAPI, Uvicorn, and a plain HTML/JavaScript frontend.
- Local operational-database generation from fictional CSV fixtures plus lazy creation of a separate append-only synthetic observation replay database.
- Root and `/dashboard` routes serving the workbench.
- JSON API routes for catalogs, state, evaluation, legacy CSV replay, synthetic observation replay inspection, import, scenarios, reset, and seeded operations context.

### Northstar catalog and point observations

- Ten fictional Northstar equipment records and seventeen point records in the seeded fixture.
- Seventeen seeded current point values.
- Normal point ingestion appends point-sample history and updates the latest-value `current_point_values` projection.
- Point metadata for value, unit, quality, timestamps, source, protocol, address, stale window, override, and out-of-service status.
- Manual local point updates, deterministic scenario samples, simulated-driver samples, and CSV replay samples.

### Flagship catalog and topology

- The historical JSON/CSV fixture package for facility ID `FACILITY-ADVANCED-MATERIALS-RESEARCH`, fixture version `1.0.0`, remains available and byte-identical.
- Version `1.0.0` contains ten real equipment records and sixteen equipment-owned point-definition records covering potential fan availability, run, fault, and speed indications; airflow; duct static; damper position; treatment permissive; supply/makeup-air status; process-laboratory zone pressure; and both boundary differential pressures.
- Three zones forming the explicit corridor → transition/airlock → process-laboratory chain.
- One process-exhaust system, two directed pressure boundaries, one shared exhaust path, and two monitored dependencies.
- Ten typed topology relationship rows: two duty/standby memberships, one system-zone service, two fan/shared-path memberships, one path/treatment dependency, one boundary/system dependency, two boundary/supply dependencies, and one cascade-order link.
- Eight typed point bindings: one zone, one system, two pressure-boundary, two shared-path, and two monitored-dependency bindings.
- Additive topology `TOPOLOGY-FLAGSHIP-PROCESS-EXHAUST` version `1.1.0` preserves every `1.0.0` row and adds `CONTROLLER-PROCESS-EXHAUST` and `SENSOR-SUPPLY-MAKEUP-AIRFLOW` as real point owners.
- Version `1.1.0` adds twelve reported-indication point definitions: process enabled and permissive; duty and standby controller request, controller-reported execution, VFD state, and motor current; treatment availability; and delivered supply/makeup airflow.
- Four additive typed bindings associate process enabled/permissive with the process-exhaust system, treatment availability with the treatment dependency, and delivered makeup airflow with the supply/makeup dependency. Fan-owned additions reuse the accepted equipment/system/shared-path context.
- Existing shared process-exhaust airflow, makeup-air controller status, fan availability/run/fault/speed, shared-path, zone-pressure, and boundary-pressure point definitions remain reused rather than duplicated.
- Neither topology version has a current-value baseline, numerical pressure limit, point-condition semantics, equipment/system/facility state, consequence logic, inferred-state point, or executable control behavior. Topology point definitions and typed bindings are not observations.

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

### Controlled applicability and requirement basis

- Accepted ADR 0004 records the exact fictional profile and qualitative inactive design intent while separating those project decisions from legal applicability.
- Versioned package `STANDARDS-BASIS-FLAGSHIP-1.0.0` remains bound to facility `FACILITY-ADVANCED-MATERIALS-RESEARCH` and the preserved fixture version `1.0.0`.
- Additive package `STANDARDS-BASIS-FLAGSHIP-1.1.0` binds the exact topology `1.1.0` identity and content digest while preserving the `1.0.0` profile, controlled sources, applicability bases, requirements, lifecycle/activation states, and evidence-category inventory.
- Each package contains 18 profile facts, 35 controlled sources, 29 applicability bases, 19 evidence categories, and 12 project-authored synthetic requirements.
- New York Environmental Conservation Law Article 19 and 6 NYCRR Parts 200, 201, 211, and 212 are represented only as provisional legal or regulatory bases for the fictional outdoor particulate exhaust. Missing emissions, process, control, permit, and exemption facts prevent a permit, exemption, emission-limit, or applicability conclusion, and these bases do not become synthetic SOO requirements.
- The current New York Uniform Code adoption record, the limited July 2, 2026 court-suspension notice, and project-effective edition selection remain distinct. The profile lacks permit-application and construction timing needed to select a project-effective edition.
- Federal OSHA private-sector coverage and New York PESH state/local public-sector coverage are represented separately. NFPA 70 publisher-edition metadata remains separate from provisional New York adoption evidence; NFPA 45 remains a provisional informative scope-review source; OpenBuildingControl has no asserted publication date; and ANSI/AMCA 210-25 plus AMCA Publication 201-23 metadata is preserved.
- Ten requirements use `ACCEPTED_FOR_SIMULATION` with the project-owner decision recorded. Two additional AI drafts remain `DRAFT`, `PROPOSED`, and `INACTIVE`. All 12 are `INACTIVE`, non-executable, and have no numerical criteria.
- Strict whole-package validation rejects duplicate identifiers across documents, invalid statuses, missing provenance, empty, duplicate, malformed, or unresolved source-reference lists, source/basis-category inconsistency, altered recorded profile facts, owner source/basis/requirement provenance chains, or authority notices, invalid facility or fixture bindings, point-definition references outside the bound flagship catalog, inconsistent evidence representation, path traversal, malformed JSON, unexpected requirement fields including numerical criteria, and attempts to make a requirement active or executable.
- The in-memory loader validates a complete candidate before swap, preserves the prior snapshot after a malformed reload, and returns defensive copies.
- Version-aware validation permits only the approved additive `1.1.0` point-definition representation changes and rejects unapproved differences from standards basis `1.0.0`.
- `GET /standards-basis` exposes one atomic snapshot. Six leaf routes expose the profile, controlled sources, provisional applicability matrix, requirements, evidence categories, and compact traceability.
- A separate workbench section displays the default reviewer material independently of active SQLite state. It clearly labels applicability as provisional and all requirements as project-authored, inactive, and non-executable. It distinguishes topology point-definition representation from observation availability and continues to report no flagship observation baseline until a reviewer explicitly selects a separate synthetic replay execution.
- Milestone 3 adds no database table, fixture observation, inference, evaluation outcome, finding, human-disposition workflow, external connector, or equipment-control path.

### Canonical observation and temporal semantics

- Accepted ADR 0005 defines distinct package, replay-execution, delivery, request-idempotency, source-event, source-native, canonical-observation, mapping, canonicalizer, and topology identities.
- Each accepted synthetic delivery creates an immutable delivery audit record and source-native record bound to facility, source/channel, mapping, package, topology, and replay execution.
- Source-native records preserve exact repository payload representation and digest; supplied event identity, sequence, and session/boot epoch; original source timestamp text, offset, and precision; source-reported quality without reinterpretation; transport and synthetic provenance; virtual receipt time; and deterministic ingestion ordinal.
- Valid source timestamps normalize to UTC. Missing or invalid source time remains explicit and is not replaced with receipt time. Receipt time is treated as a knowledge-time fact, not physical event order or causation.
- Source sequence is compared only within its declared facility/source/channel/session scope. Ordering facts preserve out-of-order arrival, sequence/time disagreement, a declared new epoch, and ambiguous reset without an epoch. No lateness, staleness, freshness, persistence, validity, or recovery-hold threshold is implemented.
- Exact source-event redelivery retains every delivery and source-native record while producing one logical canonical derivation. Conflicting redelivery retains every native and canonical variant with no selected winner, including across mapping versions. Equal payload under another source-event identity remains distinct, and missing stable identity does not trigger content-based deduplication.
- Canonical observations contain one typed value, unit when applicable, normalized valid source time and time basis, source-quality provenance, mapping identity/version/digest, canonicalizer version, synthetic provenance, ordering facts, and exact lineage to source-native records and fields.
- The mapping implementation supports one source record producing multiple canonical observations, a declared pair of source register records producing one canonical value, partial decode, direct Boolean/enum normalization, signed register decoding, decimal scaling and precision, and same-dimension unit conversion. Register pairs preserve every valid logical component combination, collapse only exact stable-event component redeliveries, retain prior canonical history when a later component cannot be paired, and propagate known component conflicts through lineage. A new mapping version produces a separate derivation rather than rewriting prior records.
- A rebuildable reported-observation projection is scoped by facility, replay execution, source/channel binding, canonical point, and mapping identity/version/digest. It requires explicit `as_of_observed_at` and `known_by_received_at` cutoffs and exposes `REPORTED`, `CONFLICT_PRESENT`, `UNORDERED`, `NO_OBSERVATION`, or `NO_ELIGIBLE_REPORT` without merging sources or claiming actual point/equipment state. Distinct equal-order events with equivalent normalized report material retain all identities while returning their common reported scalar.

### Repository-versioned synthetic observation replay

- One allowlisted package, `flagship-process-exhaust-evidence-sequence` version `1.0.0`, binds the exact flagship facility, topology `1.1.0` digest, mapping package, mapping digests, canonicalizer, source bindings, source-event facts, virtual receipt clock, source quality, and synthetic generator.
- Its 23-entry narrative contains context, initial and later reported indications, a non-authoritative asserted-action annotation, new post-action underlying indications, and two unexecuted tranche-boundary markers. Event names and the structural oracle assert no fan failure, successful standby changeover, pressure-cascade or containment state, conformance, consequence, authorization, safety, or recovery result.
- The repository mapping package records ten synthetic source/channel bindings and versioned mappings for controller, VFD, motor-current, process/shared-path, treatment, makeup-air, and pressure reports. Dependency metadata records declared or unknown origins without an evidence-independence or sufficiency conclusion.
- The validated package structurally expects 41 deliveries, 41 source-native records, 39 source-event groups, 40 logical variants, 76 canonical observations across all 28 topology point definitions, 82 lineage edges, 5 declared register decode groups, 1 exact-redelivery group, 1 conflicting-redelivery group, 1 missing-source-time record, 1 invalid-source-time record, no decode issue, and 4 context/action/boundary annotations.
- Package validation is allowlist-only and bounded. It rejects arbitrary paths, archives, URLs, uploads, unregistered mappings, identity/digest mismatches, invalid facility/topology/source references, oversized payloads, malformed time/identity structures, and prohibited evidentiary claims before persistence.
- Every replay execution is an isolated run. Matching request content and idempotency key returns the prior execution; reuse of the key for different content is rejected. A separate execution creates separate run-scoped records but reproduces equivalent normalized semantic output.
- The execution manifest records pinned package/topology/mapping/canonicalizer identities, input and derived record counts/digests, duplicate/conflict and projection summaries, and a normalized semantic digest that excludes run-scoped random IDs and non-semantic creation timestamps.
- Manifest and content hashes establish reproducibility and integrity of represented data only. They do not establish authenticity, correctness, applicability, evidence independence, physical truth, or physical outcome.

### Isolated append-only observation persistence

- New replay evidence is stored separately at local path `db/facilityops-observations.sqlite3`; it does not use or migrate the legacy `db/facilityops.sqlite3`.
- Application import does not create or mutate the observation store. The schema is lazily initialized only by an explicit local synthetic replay.
- Typed relational tables preserve immutable topology, source-binding, mapping, package, execution, request, source-event group, delivery, source-native, canonical, lineage, decode-issue, annotation, and reproducibility-manifest records.
- The store enables SQLite foreign keys and recursive triggers, enforces typed-value and identity constraints, prevents accepted-record update or deletion, and bounds payload and list-page sizes.
- Replay data is completely validated and canonicalized before one explicit transaction publishes it. Schema or replay fault injection rolls back without exposing a partial execution.
- The existing operational reset does not open or delete this store, and no destructive observation reset endpoint exists. This is durable laboratory replay evidence within the tranche, not complete production or incident-level retention.

### Observation replay API and workbench

- Facility-nested routes catalog and inspect the one allowlisted replay package and create an isolated execution from package ID/version plus a request idempotency key; the API accepts no arbitrary package path.
- Execution routes return status and the reproducibility manifest.
- Paginated source-native and canonical-observation list routes support bounded source/event/point/mapping/time filters, and execution-scoped detail routes prevent cross-facility or cross-execution record access.
- A canonical lineage route returns exact source-native records, source fields, roles, and input order. A paginated redelivery-group route exposes delivery/variant counts and exact versus conflicting redelivery classifications.
- The reported-observation projection route requires source binding, point, mapping ID/version/digest, event-time cutoff, and knowledge-time cutoff. It does not infer missing scope or merge source bindings.
- List page size defaults to 50 and is capped at 100. Bad request and missing-scope responses remain bounded; idempotency or immutable-identity conflicts return HTTP 409.
- The synthetic observation replay workbench lets a reviewer select the structurally validated package, inspect package/topology/mapping/canonicalizer identity and structural oracle, start a local execution, compare observed and received time, inspect source-native/canonical records and exact lineage, review redelivery/conflict groups, rebuild a projection with explicit cutoffs, and inspect the manifest.
- The standards workbench retains `NO_FLAGSHIP_OBSERVATION_BASELINE` by default. Selecting a replay execution does not mutate that standards declaration.
- API and UI language describes reported indications and unresolved evidence; it makes no actual-equipment-state, failure, successful-changeover, airflow-sufficiency, containment, pressure-cascade, facility-safety, conformance, authorization, commissioning, or recovery claim.

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

Legacy Northstar quality, staleness, override, out-of-service, and alarm-rule eligibility remain implemented. The canonical observation path now has approved source identity, source-time, receipt-time, bitemporal cutoff, ordering, conflict, and reported-observation projection semantics. A distinct computed point-condition model and canonical quality/suspect/override/OOS interpretation are not implemented, and no approved staleness, freshness, lateness, persistence, recovery-hold, validity, or uncertainty criterion exists.

### Auditable evidence

Alarm trigger snapshots and audit events provide useful legacy evidence. The new synthetic observation replay preserves immutable source payloads and digests, exact mapping/topology/package identities, canonical lineage, and a reproducibility manifest in a reset-isolated append-only database. This is bounded replay provenance, not complete incident evidence: imports and legacy Northstar CSV replay lack equivalent durable manifests; higher-layer inferences, findings, and human records do not exist; legacy operational reset still deletes point-sample history, generated alarms, and all alarm/audit events; and incident-level retention/export policy remains planned.

### Standards, applicability, requirements, and findings

The bounded flagship controlled-source catalog, provisional applicability matrix, inactive synthetic requirement set, evidence-category catalog, and source-to-evidence traceability are implemented as repository-versioned review data. This is not a generalized standards database, approved legal applicability baseline, executable requirement pack, or status-transition workflow.

Evidence-sufficiency evaluation, the working outcome presentation, bounded-finding records, incident-level evidence manifests linked to evaluations/findings, and human review or disposition remain unimplemented. The replay reproducibility manifest does not fill those roles.

Existing alarm rules are deterministic local laboratory rules. They are not controlled standards requirements, code-compliance tests, owner-approved criteria, commissioning criteria, or evidence that the flagship topology conforms to an applicable requirement.

The dated broad standards baseline remains a historical research reference. The bounded Milestone 3 package supplies project-authored metadata, summaries, links, and provisional traceability; it does not retrofit standards, conformance, or evidence-sufficiency claims into Milestones 1 or 2.

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

- Computed point conditions under separately approved evaluation-time, quality, suspect, override, out-of-service, staleness, freshness, lateness, persistence, recovery-hold, validity, and uncertainty semantics.
- The process-exhaust failure and pressure-cascade-degradation inference and evaluation over the implemented reported-indication evidence chain.
- Explicit equipment, system, pressure-cascade, and facility inference layers.
- Deterministic operational consequences with affected scope, evidence, and uncertainty.
- Bounded findings with explicit insufficient-evidence behavior and the working four-outcome presentation.
- Incident-level durable provenance and evidence manifests beyond the implemented replay-integrity manifest.
- Separate human verification, test authorization, operational action, commissioning acceptance, waiver, recovery review, and final-disposition records.
- An optional bounded read-only adapter or controls-assurance comparison after the flagship proof.
- An optional advisory AI layer that cites controlled evidence and cannot mutate computed records or exercise human authority.

Planned capabilities are not implemented and must not be presented as current behavior.

## Unknown/Not Verified

- Network HTTP behavior of every route. Prior live Uvicorn inspection covered the workbench and consolidated standards-basis route; all standards-basis routes and the new observation replay routes have in-process ASGI coverage.
- Cross-browser behavior and accessibility of the workbench.
- Concurrency, performance, locking, and data-volume limits beyond the bounded observation payload/page constraints and tested transaction behavior.
- Legacy operational-database behavior with SQLite foreign-key enforcement enabled; the isolated observation store requires and verifies it.
- Backup, restore, database upgrade, and long-term evidence-retention behavior for both local SQLite stores.
- Authentication, authorization, multi-user identity, and deployment security; these are not implemented.
- Production deployment, monitoring, availability, and recovery characteristics.
- Domain validation of the implemented minimum fictional topology and of all planned operating modes, numerical pressure relationships, consequence rules, and functional-test criteria.
- Regulatory, industrial-hygiene, process-safety, cleanroom, code-compliance, or commissioning acceptance status; no such validation or qualified human disposition exists.
- Final vocabulary and relationships for alarm priority, point condition, operational risk, advisory classification, and incident severity.
