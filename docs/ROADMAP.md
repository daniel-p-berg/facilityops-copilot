# FacilityOps Copilot Roadmap

## Governance

This roadmap implements the direction in [PRODUCT_CHARTER.md](PRODUCT_CHARTER.md). Work proceeds one user-approved slice at a time. Progress markers and completion evidence may be updated as work is verified, but milestones may not be reordered, removed, or materially expanded without explicit approval.

Milestones are intentionally bounded and do not promise delivery dates. Every milestone preserves Northstar Data Hall, fixture version `1.0.0`, and existing deterministic behavior unless an explicitly approved change states otherwise.

- When a milestone depends on an unresolved architecture or domain decision, its first slice must produce a proposed ADR.
- Implementation that depends on a proposed decision cannot begin until that ADR is explicitly accepted.
- An accepted ADR authorizes only the stated decision and does not prove implementation.
- Roadmap completion evidence is project verification evidence. It is not commissioning acceptance, code compliance, authorization for physical operation, or a final human disposition.
- Deterministic code owns reproducible computation and bounded findings. The authorities listed in ADR 0003—including determinations of physical safety and authorization for operation—remain with persons or organizations that possess the required qualifications and assigned organizational or legal authority.

The 2026-07-22 rebaseline preserves completed Milestones 1 and 2 and restructures planned work after them around one standards-grounded flagship proof.

## Milestone 1 — Repeatable verification baseline

**Status:** Completed

**Completion evidence:** The bounded application import succeeded, all 211 discovered tests passed, all 8 representative API/dashboard smoke checks passed, and verification used isolated database state without changing the normal application database.

**Scope**

- Diagnose and resolve the local FastAPI import stall without changing product behavior.
- Establish one repeatable command for the complete test suite and one bounded API/dashboard smoke check.
- Record runtime versions and verification results.

**Completion criteria**

- The complete discovered suite runs to completion with a recorded result count.
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

**Status:** Completed

**Completion evidence:** The version `1.0.0` flagship package loads only by explicit manifest and isolated-database selection after complete pre-validation. All ADR 0001 entities, directions, relationships, roles, dependencies, and typed point bindings are stored and returned by a deterministic query. Invalid and cross-fixture packages leave prior database state unchanged, injected write failure rolls back, facility-aware reset preserves configuration and prevents Northstar baseline contamination, all 211 legacy tests pass unchanged, all 15 focused tests pass, and the normal project database hash remains unchanged.

**Scope**

- Add only the minimum fictional flagship areas, zones, equipment, systems, points, and relationships required by the pressure-cascade golden scenario.
- Define the minimum topology through an accepted ADR before implementation.
- Represent only the pressure boundaries and dependencies needed to execute and explain that scenario, without high-fidelity physics.
- Keep Northstar as a separate legacy fixture.

**Completion criteria**

- A loader produces the minimum deterministic flagship catalog from versioned fictional fixtures.
- The golden-scenario topology has explicit point-to-equipment, equipment-to-system, system-to-zone, and dependency relationships.
- Required pressure-boundary relationships are queryable.
- Referential-integrity validation identifies missing or invalid relationships.
- Flagship fixtures and selection remain separate from Northstar Data Hall.

**Tests**

- Fixture-schema and referential-integrity tests.
- Deterministic load and reset tests for both flagship and Northstar environments.

**Non-goals**

- The complete representative research facility described in [FLAGSHIP_FACILITY.md](FLAGSHIP_FACILITY.md).
- Broader facility areas, utilities, electrical systems, or precision spaces unless an accepted ADR establishes that the golden scenario requires them.
- Golden-scenario observations or behavior.
- Standards applicability, executable requirements, conformance findings, or evidence-sufficiency claims.
- Regulatory or cleanroom certification.
- Live facility ingestion.

## Milestone 3 — Controlled applicability and requirement basis

**Status:** Completed

**Purpose**

Establish the minimum controlled basis for one honest synthetic requirement pack before any flagship rule is described as executable.

**Scope**

- Maintain a controlled source-reference set covering formal standards and other applicable source categories.
- Record the provisional New York State outside New York City reference-jurisdiction assumption without resolving the AHJ or applicability profile by implication.
- Resolve the minimum fictional facility status, use, hazard, quantity, control-area, exhaust, and enforcement assumptions through an explicit fictional decision or an explicit unresolved field; do not infer a real legal determination.
- Define project-authored synthetic sequence-of-operation requirements informed by controlled references.
- State the source, rationale, applicability, assumptions, limitations, parameter basis or explicit unapproved-parameter status, required evidence, and intended evaluation boundary for each controlled requirement.
- Use requirement statuses only at the individual-requirement level and preserve their bounded meanings.
- Define the policy for presenting the working outcomes `CONFORMING`, `NONCONFORMING`, `INDETERMINATE`, and `NOT_APPLICABLE` while deferring their internal separation and any executable evaluation to later ADRs and milestones.

**Completion evidence**

- ADR 0004 records the project-owner fictional profile and qualitative design intent separately from legal applicability.
- Package `STANDARDS-BASIS-FLAGSHIP-1.0.0` contains 18 profile facts, 35 controlled sources, 29 provisional, informative, owner/project, or simulation applicability bases, 19 evidence categories, and 12 project-authored synthetic requirements.
- Ten exact qualitative requirements record the project-owner decision and use `ACCEPTED_FOR_SIMULATION`; two additional drafts remain `DRAFT` and `PROPOSED`.
- All 12 requirements are `INACTIVE`, `executable=false`, and contain no numerical criteria.
- Whole-package validation rejects duplicate identifiers, invalid statuses, missing provenance, invalid multi-source applicability references or basis-category combinations, invalid facility or fixture binding, references outside the bound flagship point-definition catalog, inconsistent evidence representation, altered controlled profile facts, owner-decision provenance chains, or authority notices, and any attempt to make a requirement active or executable.
- Candidate-before-swap loading is atomic; a malformed reload leaves the prior validated snapshot exposed.
- Seven read-only API routes and a separate workbench section expose the profile, sources, provisional applicability, requirements, evidence categories, and `controlled source → applicability basis → synthetic requirement → required evidence category` traceability.
- Evidence records distinguish bound, partial, missing, and non-point-record point-definition representation from observation availability; no flagship baseline observations exist.
- No protected standards clause text, numerical scenario criterion, evaluation outcome, database migration, topology change, alarm-rule change, external control path, or AI runtime behavior was added.

**Verification**

- Deterministic package, malformed-package atomicity, API, workbench, facility-isolation, terminology, and Northstar regression tests.
- Documentation, link, terminology, protected-text, database-hash, accepted-ADR, and fixture-integrity audits.
- Final focused and full-suite counts are recorded in [PROJECT_STATUS.md](PROJECT_STATUS.md).

**Non-goals**

- A standards database or generalized compliance platform.
- A generalized or database-backed requirement persistence schema or status-transition engine.
- Numerical scenario criteria.
- Executable evaluation logic.

## Milestone 4 — Canonical observations, point condition, and temporal semantics

**Status:** Planned

**Purpose**

Create the evidence semantics needed to distinguish what a source reported from what FacilityOps later computes or infers.

**Scope**

- Define and test the conceptual chain from source artifact or stream through source-native observation, versioned mapping and normalization, canonical observation, and point condition.
- Preserve raw source representation alongside normalized value, quantity, unit, transformation identity, and mapping version where required.
- Define stable observation identity and source reference.
- Define event time, receive time, evaluation time, ordering, late observations, staleness, clock limitations, quality, suspect evidence, override, and out-of-service behavior.
- Preserve existing Northstar alarm behavior unless a separately approved compatibility change is required.

**Completion evidence**

- Each canonical observation remains explicitly a reported indication and does not claim physical proof.
- Each computed point condition identifies its observation, reason, evaluation time, applicable temporal semantics, and uncertainty.
- Out-of-order, late, stale, suspect, bad, uncertain, overridden, and OOS cases have deterministic, documented outcomes.
- Versioned mapping and normalization steps are inspectable and reproducible.

**Tests**

- Identity, timestamp, ordering, lateness, staleness, quality, override, OOS, unit, transformation, mapping-version, and Northstar compatibility cases.

**Non-goals**

- Equipment or higher-level inference.
- A universal semantic ontology.
- Live source connectivity.
- Durable incident packaging.

## Milestone 5 — Golden-proof requirements, evidence, and replay

**Status:** Planned

**Purpose**

Package the first project-authored synthetic SOO requirements and the complete deterministic evidence sequences needed to evaluate them later.

**Scope**

- Define the process-exhaust failure, standby response, degradation, verification, recovery, and incomplete-recovery phases.
- Add a read-only or synthetic observation of a controller command/request indication; FacilityOps does not issue the command.
- Treat VFD or motor electrical corroboration as a required evidence category.
- Include independent airflow or pressure evidence, makeup-air response, treatment dependency, and both pressure boundaries.
- Cover missing, stale, suspect, overridden, late, and conflicting evidence.
- Package successful standby response, failed standby start, command-versus-status discrepancy, status-versus-independent-evidence discrepancy, degraded facility evidence, recovery, and incomplete-recovery sequences.
- Record stable replay-run and replay-step identity, source fixture version, deterministic timestamps, mappings, normalization configuration, and requirement versions.
- Use an accepted ADR before changing the Milestone 2 point or topology inventory.

**Completion evidence**

- Replay begins from a known flagship baseline and produces the same ordered canonical observations on every run.
- The evidence package covers every required flagship evidence category without assigning unapproved numerical criteria.
- Command/request evidence is explicitly received or synthetic and cannot create a command path.
- Missing or conflicting evidence can support a later `INDETERMINATE` outcome.
- Northstar replay remains unchanged.

**Tests**

- Ordering, identity, version, filtering, reset, repeatability, mapping, quality, invalid-fixture, command-boundary, evidence-gap, and Northstar regression cases.

**Non-goals**

- Equipment, system, facility, or consequence inference.
- Controller programming or automatic duty/standby transfer.
- Direct code-compliance claims.
- Durable evidence manifests, which remain in Milestone 8.

## Milestone 6 — Equipment inference

**Status:** Planned

**Purpose**

Infer bounded equipment conditions from multiple canonical observations without equating a command, status, or alarm with physical response.

**Scope**

- Infer relevant duty fan, standby fan, drive or motor, damper, treatment, makeup-air, and instrument conditions.
- Represent availability, requested operation, reported running, failure, reduced capability, uncertainty, override, and impairment through approved deterministic rules.
- Require independent airflow, pressure, or electrical corroboration where the controlled requirement calls for it.
- Preserve the distinction between source indication, computed point condition, and inferred equipment state.

**Completion evidence**

- Each inference identifies contributing observations, point conditions, rule and requirement versions, evaluation time, assumptions, contradictory evidence, and uncertainty.
- A command/request or run indication alone cannot prove fan operation or delivered airflow.
- Insufficient or contradictory evidence can produce an indeterminate bounded finding.

**Tests**

- Normal, requested-not-running, running-without-flow, stopped, failed, unavailable, conflicting, stale, suspect, overridden, OOS, and electrical-corroboration cases.

**Non-goals**

- Whole-system capacity, pressure-cascade inference, or facility consequence.
- Predictive maintenance.
- Physical safety determination.

## Milestone 7 — System and facility inference, consequence, and uncertainty

**Status:** Planned

**Purpose**

Reconstruct the process-exhaust transition through system, pressure-cascade, and facility layers while preserving bounded evidence claims.

**Scope**

- Combine equipment inferences, redundancy, shared-path, treatment, makeup-air, zone, and pressure-boundary evidence.
- Infer process-exhaust system condition, pressure-cascade condition, and bounded facility condition.
- Compute consequence and uncertainty for the fictional scenario under versioned project requirements.
- Identify affected zones or functions and the evidence needed for human verification.
- Keep consequence classification separate from alarm priority and from operational authorization.

**Completion evidence**

- Every system and facility inference cites its contributing evidence and lower-layer inferences.
- Consequences identify affected scope, assumptions, limitations, contradictory evidence, and uncertainty.
- Normal, reduced-capacity, degraded, lost, uncertain, test, impairment, recovery, and incomplete-recovery cases follow approved rules.
- The result does not claim contaminant exposure, code compliance, safety, or authorization for operation.

**Tests**

- Duty/standby, common-path, treatment, makeup-air, missing-evidence, boundary-persistence, conflicting-pressure, degraded-facility, and recovery cases.

**Non-goals**

- Contaminant dispersion or airflow simulation.
- Universal facility-state vocabulary.
- AI-authored findings.

## Milestone 8 — Bounded evaluation and reproducible evidence manifest

**Status:** Planned

**Purpose**

Evaluate the controlled synthetic requirements reproducibly and retain enough linked evidence to reconstruct each bounded finding.

**Scope**

- Evaluate versioned project requirements against required evidence and explicit sufficiency rules.
- Present the working four outcomes without forcing a binary result.
- Define durable identities and provenance for source artifacts, observations, mappings, requirements, rules, inferences, findings, replay runs, and user records.
- Separate active laboratory reset from retained incident evidence.
- Produce an inspectable evidence manifest containing inputs, versions, mappings, parameters, evaluation code identity, findings, contradictions, and limitations.

**Completion evidence**

- Missing, stale, suspect, overridden, late, or conflicting required evidence can produce `INDETERMINATE`.
- A `CONFORMING` computed finding is not represented as commissioning acceptance or proof of safety.
- Reset clears only approved active state while retained evidence remains queryable and internally linked.
- Re-evaluation with the same controlled inputs, configuration, and code identity reproduces the same computed result.

**Tests**

- All four presented outcomes, evidence sufficiency, conflicting evidence, repeat evaluation, retention, referential integrity, reset, missing provenance, and tamper-evident metadata cases.

**Non-goals**

- Enterprise records management.
- Legal-admissibility claims.
- Human acceptance or waiver automation.

## Milestone 9 — Human verification, recovery, disposition, and incident reconstruction

**Status:** Planned

**Purpose**

Complete the flagship assurance loop by recording qualified human decisions separately from computation and requiring new evidence for recovery.

**Scope**

- Add bounded local records for acknowledgement, verification request, observation, procedure reference, decision, action, mitigation, escalation, waiver, review, and disposition.
- Record role and authority context without assuming enterprise identity or granting physical authority.
- Require new post-action observations and a separate recovery evaluation after a recorded action or response; the record must not establish causation or physical effect.
- Evaluate successful recovery and incomplete recovery from new evidence; a recorded action alone cannot establish restoration.
- Reconstruct the scenario timeline from retained observations, inferences, findings, human records, and recovery evidence.
- Include only the impairment and functional-test concepts necessary for the flagship demonstration.

**Completion evidence**

- Computed findings and human review or disposition are separate, linked records.
- A test cannot be represented as authorized or commissioning-accepted solely because its deterministic evaluation completed.
- Recovery requires defined new evidence and a separate computed evaluation.
- Reviewers can reconstruct the initiating event, degradation, human verification, response, recovery, and unresolved remainder.

**Tests**

- Valid record transitions, insufficient role context, skipped verification, duplicate action, waiver separation, recovery evidence, incomplete recovery, handoff, and reconstruction cases.

**Non-goals**

- Autonomous response.
- General CMMS, work-order, impairment-management, commissioning-management, or training platforms.
- Authorization for physical testing or operation.
- Personnel performance scoring.

## Milestone 10 — Flagship technical and portfolio demonstration

**Status:** Planned

**Purpose**

Present one coherent, reproducible proof of standards-grounded engineering reasoning.

**Scope**

- Provide a guided end-to-end demonstration of the implemented process-exhaust and pressure-cascade scenario.
- Present the minimum topology, evidence chain, requirement basis, inferences, consequences, uncertainty, findings, human review, recovery, and evidence manifest.
- Document setup, replay, verification, recovery, rerun, and incident-review procedures.
- Add screenshots or equivalent technical review artifacts.
- Clearly label fictional data, provisional applicability, synthetic requirements, implemented behavior, planned behavior, and known limitations.

**Completion evidence**

- A reviewer can reproduce and understand the flagship scenario without reading source code.
- Every computed finding traces to controlled requirements and retained evidence.
- The demonstration explains what was observed, what was inferred, what remains uncertain, what a human decided, and what new evidence supports recovery.
- The demonstration remains fully usable with AI disabled.

**Tests**

- Guided-flow smoke coverage, deterministic reset and rerun, documentation-step verification, evidence-link checks, and implemented-versus-planned labeling checks.

**Non-goals**

- A generic dashboard or BMS graphics framework.
- High-fidelity facility graphics.
- Commercial product packaging.
- Broad integrations unrelated to the flagship proof.

## Milestone 11 — Optional comparative controls-assurance research

**Status:** Planned after the flagship proof; may remain deferred

**Purpose**

Compare the FacilityOps evidence-oriented method with selected controller-conformance, control-description, semantic, or adapter approaches without turning the project into a general platform.

**Scope**

- Optionally compare one bounded duty/standby sequence with a pinned ASHRAE Standard 231 CDL/CXF representation or other controlled research reference.
- Study OpenBuildingControl-style replay, mapping, unit, tolerance, and reproducibility patterns.
- Define a read-only adapter/import contract only if needed for a bounded second-source proof.
- Preserve native source identity, quality, timestamps, override or priority evidence, and mapping provenance.

**Completion evidence**

- The comparison states exactly what controller behavior or interoperability evidence it covers and what physical behavior it cannot prove.
- Any adapter exposes no command or configuration-write capability.
- Exact external resource and implementation versions are pinned.

**Tests**

- Comparison reproducibility, mapping, units, tolerance, invalid data, provenance, capability boundary, and no-write-path cases.

**Non-goals**

- A general CDL engine.
- Broad vendor coverage or live customer connectivity.
- A universal ontology or integration platform.
- Controller conformance represented as facility conformance.

## Milestone 12 — Optional advisory AI boundary

**Status:** Planned after deterministic flagship completion; may remain deferred

**Purpose**

Study whether advisory AI adds value over the completed deterministic evidence chain.

**Scope**

- Permit drafting, explanation, comparison, and troubleshooting suggestions over controlled evidence.
- Require citations to deterministic records, explicit uncertainty, and advisory labeling.
- Prevent AI output from changing requirements, applicability decisions, computed records, human disposition, or physical systems.

**Completion evidence**

- Advisory output is traceable to evidence and cannot mutate controlled or human-authority records.
- AI cannot approve its own mappings, requirements, tests, findings, or recommendations.
- All deterministic evaluation, review, and evidence functions remain available with AI disabled.

**Tests**

- Citation, missing-evidence, contradictory-evidence, disabled-AI, prompt-boundary, self-approval, and attempted-mutation cases.

**Non-goals**

- Autonomous control, response, applicability, authorization, acceptance, waiver, or final disposition.
- AI-owned point condition, state inference, consequence, or finding.

## Deferred or parking lot

These items are not approved milestones and require explicit review before promotion:

- Live read-only connectivity to a real facility.
- Commercial packaging, product-market validation, pricing, or go-to-market work.
- Production authentication, authorization, multi-tenancy, and enterprise identity.
- Cloud deployment, high availability, backup orchestration, and disaster recovery.
- High-volume historian storage and streaming infrastructure.
- High-fidelity airflow, contaminant, process, or electrical simulation.
- Comprehensive regulatory-compliance automation or certification claims.
- Full CMMS, work-order, document-control, commissioning-management, or enterprise asset-management scope.
- General impairment-management and training platforms beyond the bounded flagship proof.
- Multi-site portfolio analytics.
- Broad protocol and vendor integration.
- Mobile applications and notification delivery.

## 2026-07-22 roadmap rebaseline mapping

This mapping preserves completed history and records how the prior planned milestones were consolidated:

| Prior milestone | Rebaselined location | Treatment |
|---|---|---|
| 1 — Repeatable verification baseline | 1 | Preserved as the completed 211-test milestone. |
| 2 — Minimum viable flagship catalog and topology | 2 | Preserved as the completed addition of 15 focused tests and the 226-test baseline. |
| New standards/applicability work | 3 | Added ahead of executable flagship requirements. |
| 3 — Point condition and temporal semantics | 4 | Expanded to include source-native observations, mapping, normalization, and canonical observations. |
| 4 — Golden-scenario observations and replay | 5 | Combined with the controlled synthetic requirement and evidence package. |
| 5 — Process-exhaust equipment state | 6 | Reframed as bounded equipment inference with independent corroboration. |
| 6 — Exhaust-system and pressure-cascade state | 7 | Consolidated with the facility-inference portion of prior Milestone 7. |
| 7 — Facility state and operational consequences | 7 | Consolidated into system/facility inference, consequence, and uncertainty. |
| 8 — Durable provenance and evidence | 8 | Expanded into bounded evaluation and a reproducible evidence manifest. |
| 9 — Operator response workflow | 9 | Narrowed to human verification and records required by the flagship proof. |
| 10 — Impairment management | 9 or parking lot | Only flagship-required concepts remain in Milestone 9; general scope is deferred. |
| 11 — Functional testing and recovery | 9 | Reframed around computed evaluation, human authority, new recovery evidence, and separate disposition. |
| 12 — Incident review and training | 9 or parking lot | Incident reconstruction remains; general training-platform scope is deferred. |
| 13 — Vendor-neutral adapter proof | 11 | Deferred until after the flagship and made optional comparative research. |
| 14 — Guided operator workbench and portfolio demonstration | 10 | Refocused as the coherent technical and portfolio demonstration. |
| 15 — Advisory AI boundary | 12 | Retained as optional work only after the deterministic flagship proof. |
