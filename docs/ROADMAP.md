# FacilityOps Copilot Roadmap

## Governance

This roadmap implements the direction in [`PRODUCT_CHARTER.md`](PRODUCT_CHARTER.md). Work proceeds one user-approved slice at a time. Progress markers and acceptance evidence may be updated as work is verified, but major milestones may not be reordered, removed, or materially expanded without explicit user approval.

Milestones are intentionally small and verifiable. They do not promise delivery dates. Every milestone preserves the Northstar Data Hall fixture and existing deterministic behavior unless an explicitly approved change says otherwise.

- When a milestone depends on an unresolved architectural decision, its first slice must produce a proposed ADR.
- Implementation that depends on the decision cannot begin until the ADR is explicitly accepted.
- An accepted ADR authorizes the decision, not every possible implementation or expansion of scope.

## Milestone 1 — Repeatable verification baseline

**Status:** Planned

**Scope**

- Diagnose and resolve the local FastAPI import stall without changing product behavior.
- Establish one repeatable command for the complete test suite and one bounded API/dashboard smoke check.
- Record runtime versions and verification results.

**Acceptance evidence**

- The complete discovered suite runs to completion with a recorded pass/fail count.
- A smoke check loads the application and exercises representative read and local-write routes against an isolated database.
- No test or smoke check uses a customer system or external facility endpoint.

**Tests**

- Existing 211 test methods.
- Minimal startup, dashboard, summary, scenario, evaluation, reset, replay, and import-preview smoke coverage.

**Non-goals**

- New product features.
- Test-framework replacement.
- Production deployment or continuous integration.

## Milestone 2 — Minimum viable flagship catalog and topology

**Status:** Planned

**Scope**

- Add only the minimum fictional flagship areas, zones, equipment, systems, points, and relationships required by the pressure-cascade golden scenario.
- Define the minimum topology through an accepted ADR before implementation.
- Represent only the pressure boundaries and dependencies needed to execute and explain that scenario, without high-fidelity physics.
- Keep Northstar as a separate legacy fixture.

**Acceptance evidence**

- A loader produces the minimum deterministic flagship catalog from versioned fictional fixtures.
- The golden-scenario topology has explicit point-to-equipment, equipment-to-system, system-to-zone, and dependency relationships.
- Required pressure-boundary relationships are queryable.
- Referential-integrity validation identifies missing or invalid relationships.
- Flagship fixtures and selection remain separate from Northstar Data Hall.

**Tests**

- Fixture-schema and referential-integrity tests.
- Deterministic load and reset tests for both flagship and Northstar environments.

**Non-goals**

- The complete representative research facility described in `FLAGSHIP_FACILITY.md`.
- Broader facility areas, utilities, electrical systems, or precision spaces unless an accepted ADR establishes that the golden scenario requires them.
- Golden-scenario observations or behavior.
- Regulatory or cleanroom certification.
- Live facility ingestion.

## Milestone 3 — Point condition and temporal semantics

**Status:** Planned

**Scope**

- Settle point-condition vocabulary through accepted ADRs where necessary, separately from alarm priority.
- Define event time versus receive time, evaluation time, ordering, late observations, staleness, quality, override, and out-of-service behavior.
- Define the minimum stable observation identity and source reference needed by later replay and state layers.
- Preserve existing Northstar alarm behavior unless a separately approved compatibility change is required.

**Acceptance evidence**

- Each observation produces a deterministic point condition with reason, stable identity, source reference, and evaluation time.
- Out-of-order, late, stale, uncertain, bad, overridden, and OOS cases have explicit outcomes.
- Event-time, receive-time, and evaluation-time behavior is documented and testable.

**Tests**

- Boundary, identity, timestamp, ordering, late-observation, quality, override, OOS, staleness, and compatibility tests.

**Non-goals**

- Equipment aggregation or higher-level state.
- Replay fixtures or durable incident packaging.
- A final cross-product severity model unless approved by ADR.

## Milestone 4 — Golden-scenario observations and replay

**Status:** Planned

**Scope**

- Define the process-exhaust failure scenario phases, synthetic observations, point health, and recovery sequence using the accepted Milestone 3 semantics.
- Package the scenario for deterministic step and run-all replay.
- Define expected observations without yet deriving higher-level state.

**Acceptance evidence**

- Replay starts from a known flagship baseline and produces the same ordered observations on every run.
- Replay-run and replay-step identities are stable and inspectable.
- Source-fixture version and deterministic timestamps are recorded.
- Initiation, degradation, response, and recovery phases are explicit and repeatable.

**Tests**

- Ordering, identity, source-version, filtering, reset, repeatability, point-quality, and invalid-fixture tests.
- Regression tests proving Northstar replay remains unchanged.

**Non-goals**

- Equipment, system, or facility-state conclusions.
- Durable incident packaging, which remains in the later provenance milestone.
- Operator workflow or AI explanation.

## Milestone 5 — Process-exhaust equipment state

**Status:** Planned

**Scope**

- Determine state for the golden scenario's fans, drives, treatment equipment, dampers, and relevant sensors.
- Represent availability, running condition, failure, reduced capability, uncertainty, override, and impairment through approved deterministic rules.

**Acceptance evidence**

- Equipment state identifies contributing points, rule version, timestamp, and uncertainty.
- A single raw alarm is not treated as sufficient evidence when required observations disagree or are unhealthy.

**Tests**

- Normal, failed, stopped, unavailable, conflicting, stale, uncertain, overridden, and OOS cases.

**Non-goals**

- Full exhaust-system capacity or facility consequence.
- Predictive maintenance.

## Milestone 6 — Exhaust-system and pressure-cascade state

**Status:** Planned

**Scope**

- Combine equipment, redundancy, shared-header, supply-response, zone, and pressure-boundary state.
- Determine process-exhaust system state and pressure-cascade state for the golden scenario.

**Acceptance evidence**

- System and cascade determinations cite their equipment and boundary evidence.
- Normal, reduced capacity, degraded, lost, uncertain, test, and impairment cases follow approved transition rules.

**Tests**

- Duty/standby, common-cause, missing-evidence, boundary persistence, incompatible-zone, and recovery cases.

**Non-goals**

- Contaminant dispersion or airflow simulation.
- Facility-wide consequence classification.

## Milestone 7 — Facility state and operational consequences

**Status:** Planned

**Scope**

- Determine facility operating state from affected systems, zones, modes, and impairments.
- Produce deterministic operational consequences, uncertainty, affected scope, and required verification.
- Keep consequence classification separate from alarm priority until approved otherwise.
- Expose facility state, consequences, affected scope, supporting evidence, and uncertainty through the API and a minimal workbench presentation.

**Acceptance evidence**

- Each consequence cites state inputs, applicable rule, affected zones or functions, and uncertainty.
- Golden-scenario output explains what happened, what is affected, why it matters, and the next verification focus.
- An operator can inspect the authoritative facility state and consequence evidence without direct database access.

**Tests**

- Consequence-rule tables, conflicting evidence, partial degradation, recovery, and no-consequence controls.

**Non-goals**

- Regulatory exposure calculation.
- AI-authored authoritative consequences.

## Milestone 8 — Durable provenance and evidence

**Status:** Planned

**Scope**

- Define durable identifiers and provenance for imports, samples, rules, state determinations, consequences, scenarios, and user actions.
- Separate active laboratory reset from evidence retention.
- Produce an inspectable incident evidence package or manifest.

**Acceptance evidence**

- Reset clears approved active state while retained evidence remains queryable and internally linked.
- An evidence package reproduces the golden scenario's authoritative timeline and inputs.
- Source fixture and rule versions are identifiable.

**Tests**

- Retention, referential integrity, repeat export, missing provenance, reset, and tamper-evident metadata tests.

**Non-goals**

- Enterprise records management.
- A guarantee of legal admissibility.

## Milestone 9 — Operator response workflow

**Status:** Planned

**Scope**

- Add local response records for acknowledgement, verification, procedure reference, decision, mitigation, escalation, and handoff.
- Tie response actions to authoritative state and evidence.
- Make the bounded response workflow usable from the local workbench rather than requiring direct database manipulation.

**Acceptance evidence**

- The golden scenario can be advanced through a bounded response workflow without commanding external systems.
- Required and optional actions, actors, timestamps, evidence, and unresolved items are distinguishable.
- An operator can perform and review supported response steps through the local workbench.

**Tests**

- Valid transitions, skipped requirements, duplicate actions, role labels, handoff, and audit tests.

**Non-goals**

- Autonomous action.
- Complete work-order or CMMS behavior.

## Milestone 10 — Impairment management

**Status:** Planned

**Scope**

- Model local impairment declaration, affected function, duration, authorization record, mitigation, compensatory monitoring, extension, and restoration.
- Make impairment state available to deterministic state and consequence rules.

**Acceptance evidence**

- A planned or emergent process-exhaust impairment changes applicable state and consequence logic predictably.
- Restoration requires defined evidence rather than a text-only status change.

**Tests**

- Planned, emergent, overlapping, expired, extended, mitigated, and restored impairment cases.

**Non-goals**

- Enterprise maintenance scheduling.
- External permit approval.

## Milestone 11 — Functional testing and recovery

**Status:** Planned

**Scope**

- Define local test plans, prerequisites, steps, synthetic observations, deterministic acceptance criteria, exceptions, abort conditions, and recovery checks.
- Exercise exhaust failure, standby response, pressure restoration, and hold-time verification.

**Acceptance evidence**

- The golden scenario has a repeatable functional test whose pass/fail result is owned by deterministic code.
- Failed prerequisites or recovery criteria prevent a passing result.
- All test observations and determinations are retained as evidence.

**Tests**

- Pass, fail, abort, incomplete, invalid prerequisite, repeated run, and recovery-hold cases.

**Non-goals**

- Commanding equipment to execute a test.
- Replacing commissioning authority or signed field documentation.

## Milestone 12 — Incident review and training

**Status:** Planned

**Scope**

- Reconstruct the golden scenario from retained observations, states, consequences, actions, impairments, tests, and recovery evidence.
- Provide deterministic expected-versus-observed review and trainee decision checkpoints.
- Present an operator-readable event and state timeline. Purposeful point trends may be included only when they directly support evidence and incident review.

**Acceptance evidence**

- Reviewers can trace every authoritative conclusion to retained evidence.
- Training mode separates scenario truth, trainee-visible information, trainee actions, and after-action review.
- Operators can read the event and state sequence without querying the database or reading source code.

**Tests**

- Timeline reconstruction, missing evidence, alternate trainee action, replay repeatability, and review-output tests.

**Non-goals**

- Personnel performance scoring for employment decisions.
- Generic chat-based training without facility evidence.
- A generic historian, trending product, or graphics framework.

## Milestone 13 — Vendor-neutral adapter proof

**Status:** Planned

**Scope**

- Define a read-only adapter/import contract for canonical observations and catalogs.
- Prove the contract with a second synthetic or sanitized source profile distinct from the existing static Modbus-map shape.
- Record source identity and transformation provenance without exposing sensitive infrastructure.

**Acceptance evidence**

- Two different source profiles produce equivalent canonical records for the same synthetic facility facts.
- No adapter exposes command or configuration-write methods.

**Tests**

- Contract, mapping, invalid data, provenance, capability-boundary, and no-write-path tests.

**Non-goals**

- Live customer connectivity.
- Broad vendor coverage.

## Milestone 14 — Guided operator workbench and portfolio demonstration

**Status:** Planned

**Scope**

- Provide a guided end-to-end demonstration of the implemented golden scenario.
- Present the minimum facility topology and dependencies concisely.
- Provide operator-readable point, equipment, system, facility, consequence, response, recovery, and evidence views.
- Document a reproducible demonstration procedure.
- Add screenshots or equivalent repository documentation suitable for technical review.
- Clearly label fictional data, implemented behavior, planned behavior, and known limitations.

**Acceptance evidence**

- A reviewer can set up, run, recover, and understand the golden scenario without reading source code.
- The demonstration procedure produces repeatable authoritative results and identifies the evidence supporting them.
- Repository documentation includes current visual or equivalent review artifacts and explicit scope labels.
- The demonstration remains useful with AI disabled.

**Tests**

- Guided-flow smoke coverage, deterministic reset and rerun, documentation-step verification, and implemented-versus-planned labeling checks.

**Non-goals**

- A drag-and-drop BMS graphics editor.
- A generic dashboard framework.
- High-fidelity facility graphics.
- Commercial product packaging.
- Replacing deterministic evidence with presentation text.

## Milestone 15 — Advisory AI boundary

**Status:** Planned

**Scope**

- Add an optional advisory interface over authoritative state and evidence.
- Require citations to deterministic facts, explicit uncertainty, and clear advisory labeling.
- Prevent advisory output from changing authoritative state or functional-test acceptance.

**Acceptance evidence**

- Advisory output is traceable to evidence and cannot mutate authoritative records.
- The application remains fully operable for authoritative workflows with AI disabled.

**Tests**

- Citation, missing-evidence, contradictory-evidence, disabled-AI, prompt-boundary, and attempted-mutation tests.

**Non-goals**

- Autonomous control or response.
- AI-owned alarm, state, consequence, operating-mode, or acceptance decisions.

## Deferred or Parking Lot

These items are not approved roadmap milestones and require explicit review before promotion:

- Live read-only connectivity to a real facility.
- Production authentication, authorization, multi-tenancy, and enterprise identity.
- Cloud deployment, high availability, backup orchestration, and disaster recovery.
- High-volume historian storage and streaming infrastructure.
- High-fidelity airflow, contaminant, process, or electrical simulation.
- Regulatory compliance automation or certification claims.
- Full CMMS, work-order, document-control, or enterprise asset-management scope.
- Multi-site portfolio analytics.
- Mobile applications and notification delivery.
