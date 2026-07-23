# FacilityOps Copilot Product Charter

> **Change-controlled document — Version 2.0, approved 2026-07-22.** This version supersedes Version 1.0, approved 2026-07-19. It defines the accepted project identity and authority boundaries. Future tasks may not change it without explicit approval for a charter revision.

## Revision summary

Version 2.0 reorients FacilityOps Copilot from a broadly framed operations and commissioning product toward a standards-grounded technical laboratory. It makes technical competence, engineering reasoning, a coherent flagship demonstration, and portfolio value the primary outcomes; treats commercial differentiation as an unproven hypothesis; establishes controlled standards and assurance lifecycles; and separates deterministic computation from qualified human acceptance and disposition.

This revision preserves the compatible Version 1.0 commitments to external read-only operation, fictional and controlled data, scenario-driven verification, evidence-oriented reasoning, deterministic reproducibility, explicit uncertainty, and advisory-only AI.

## Project identity

FacilityOps Copilot is a standards-grounded technical laboratory for critical-environment facilities operations, reliability, controls, and operational-technology assurance.

It uses a fictional facility and deterministic scenarios to develop and demonstrate how heterogeneous facility evidence can be normalized, interpreted, compared with versioned control intent, and reconstructed after an event.

The project exists primarily to:

1. Develop technically transferable competence across critical-facility operations, maintenance, controls, electrical systems, OT data, commissioning, reliability, and incident analysis.
2. Integrate Daniel's nuclear operations, data-center facilities, building-automation, switchgear, and controls experience with deeper software and systems-engineering capability.
3. Produce a credible technical portfolio demonstrating disciplined engineering reasoning, not merely application-development skill.
4. Provide a safe laboratory in which equipment behavior, control sequences, abnormal conditions, evidence quality, operator response, and recovery can be studied.
5. Explore a possible controls-assurance capability without assuming that a standalone commercial product opportunity exists.

This charter defines intended direction. It does not assert that every capability is implemented. Verified repository behavior is maintained separately in [PROJECT_STATUS.md](PROJECT_STATUS.md).

## Project priorities

FacilityOps must optimize for:

- Technical depth rather than feature breadth.
- Transferable facilities knowledge rather than software novelty alone.
- Standards-grounded engineering rather than invented universal rules.
- Explicit assumptions, applicability, uncertainty, and evidence sufficiency.
- Deterministic and reproducible evaluation.
- Separation of a reported indication from inferred physical state.
- Separation of a computed finding from qualified human acceptance or disposition.
- A coherent flagship demonstration rather than a general integration platform.
- Career and portfolio value even if the commercial thesis is later rejected.

## Commercial position

Commercial white space has not been established. Existing products already provide portions of fault detection and diagnostics, semantic normalization, commissioning workflow, functional testing, historians and event analysis, controller-conformance testing, OT integration, and visualization.

The potentially differentiated capability remains a hypothesis:

> A read-only, deterministic evaluation of critical-facility transitions using heterogeneous evidence, versioned control intent, explicit evidence sufficiency, and reproducible findings.

FacilityOps may eventually become deployable, support professional services, or suggest a commercial product. None of those outcomes currently defines project success.

## Observation and inference lifecycle

The conceptual observation chain is:

```text
source artifact or stream
→ source-native observation as received by FacilityOps
→ versioned mapping and normalization
→ canonical observation
→ point condition
→ equipment, system, and facility inference
→ consequence and uncertainty
```

A canonical observation remains a reported indication from an identified source within its stated quality, timing, mapping, and transformation limits. It does not independently prove the physical state of equipment, a system, or the facility.

After a recorded action or response, FacilityOps may receive new observations. The action or response record does not establish causation or physical effect. Recovery requires new post-action observations and a separate evaluation. An acknowledgement, controller command/request indication, or work record likewise does not prove that its intended physical effect occurred.

## Standards and assurance lifecycle

Formal standards are one controlled source category. Other possible bases include:

- Laws and regulations.
- Jurisdiction-adopted codes and amendments.
- Permits, licenses, and consent conditions.
- Owner requirements.
- Owner's Project Requirements, Basis of Design, and sequences of operation.
- Manufacturer instructions and equipment requirements.
- Procedures and controlled test documents.
- Project design assumptions.
- Synthetic simulation assumptions.

FacilityOps distinguishes three conceptual layers:

1. **Standards Reference Registry** — identifies a source, edition, jurisdiction, adoption status, enforcement status, scope, section pointer, and access status.
2. **Applicable Requirements Baseline** — contains requirements deliberately selected for a defined fictional facility, system, equipment item, operating mode, applicability profile, and effective interval.
3. **Executable Requirements and Tests** — contains deterministic evaluations only after applicability, parameter basis, evidence needs, scope, assumptions, and limitations have been defined.

The assurance lifecycle is:

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

A source does not become an applicable or executable requirement merely because it appears in a registry. The project must distinguish publisher-current, jurisdiction-adopted, and project-effective editions; enforcement status; source requirements; owner or project requirements; synthetic simulation requirements; executable rules; computed findings; and qualified human acceptance or disposition.

For the first golden proof, requirements must remain project-authored synthetic sequence-of-operation requirements informed by controlled references. They must not be characterized as directly code-required, owner-approved, commissioning-accepted, or suitable for physical operation unless later applicability and approval decisions establish that basis.

Individual controlled requirements may use the working statuses `DRAFT`, `ACCEPTED_FOR_SIMULATION`, `DOMAIN_REVIEWED`, and `RETIRED`. These statuses do not apply to topology, reference sources, standards, or ADRs:

- `ACCEPTED_FOR_SIMULATION` means only that a synthetic requirement may be used in the fictional laboratory.
- `DOMAIN_REVIEWED` records a bounded technical review. It does not imply code compliance, commissioning acceptance, or authorization for physical operation.

This charter does not select a requirement schema, field set, or single status-transition state machine.

## Deterministic computation and human authority

Deterministic code owns reproducible computation. It produces computed point conditions, inferred states, timing results, replay outputs, evaluations, and bounded findings under identified inputs, assumptions, configuration, and rules. Determinism provides reproducibility, not automatic validity. The following authorities remain with persons or organizations that possess the required qualifications and assigned organizational or legal authority: applicability decisions, requirement approval, test authorization, operational action, commissioning acceptance, waivers, final disposition, determinations of physical safety, and authorization for operation.

Deterministic evaluation must preserve insufficient-evidence behavior. Missing, stale, suspect, overridden, late, or conflicting evidence must be capable of producing an `INDETERMINATE` result rather than a forced binary result. The working external outcome set is `CONFORMING`, `NONCONFORMING`, `INDETERMINATE`, and `NOT_APPLICABLE`; the internal separation between applicability and evaluation results remains a later architecture decision.

AI may draft mappings, requirements, tests, explanations, and troubleshooting suggestions. AI must not approve its own output, determine applicability, authorize a test or operational action, accept commissioning work, waive a requirement, make a final disposition, or serve as the safety authority. All deterministic computation, evidence review, and non-AI laboratory workflows must remain available when AI is disabled.

## External-system and safety boundaries

FacilityOps must not:

- Command or configure a physical BAS, EPMS, PLC, SCADA, DCIM, controller, drive, or other facility system.
- Create an external write-back or control path.
- Certify commissioning.
- Independently determine that a physical system is safe.
- Authorize physical testing, lockout/tagout, energized work, impairment, restoration, or return to service.
- Treat controller execution as proof of approved control intent or actual physical response.
- Treat a protocol-quality flag, point value, command/request indication, or status indication as proof beyond what that source reports.

Local laboratory writes are permitted for fictional imports, replay, simulation, scenarios, rules, acknowledgements, review records, test records, audit, and local configuration. They must remain distinguishable from source-native observations and must never create an external control path.

## Data and evidence principles

### Fictional and controlled data

Repository fixtures must remain fictional. Any future ingestion must use synthetic, sanitized, non-sensitive, or explicitly authorized read-only data. Credentials, customer data, proprietary exports, real facility network information, and confidential configurations must never be committed.

### Evidence before assertion

Computed conditions, inferences, evaluations, and findings must identify their inputs, applicable rules, mappings, timestamps, configuration, provenance, assumptions, limitations, contradictory evidence, and uncertainty. Clearing active laboratory state must not destroy durable evidence in the intended architecture.

### Scenario-driven verification

Important behavior must be developed through small, repeatable scenarios with declared preconditions, observations, expected transitions, evidence needs, insufficient-evidence cases, consequences, recovery criteria, and reproducible outputs.

### Vendor and protocol boundaries

The core observation, inference, requirement, finding, and evidence concepts must not depend on a single control-system vendor. This compatibility goal does not make FacilityOps a universal integration platform. Protocol and vendor adapters remain bounded translators or research artifacts, not the project identity.

## Intended participants and reviewers

- Critical-environment operators, facility engineers, reliability personnel, and shift leads.
- Controls, BAS, EPMS, PLC, and integration practitioners.
- Mechanical, electrical, commissioning, maintenance, process-safety, and industrial-hygiene reviewers.
- Instructors and trainees using fictional scenarios.
- Technical portfolio reviewers evaluating engineering reasoning, traceability, and software discipline.

Qualified roles and review authority for specific requirements or scenarios remain contextual decisions; this list grants no approval authority.

## Preservation constraints

Completed foundations must be preserved while the documentation is rebaselined:

- The Milestone 1 repeatable 211-test verification history.
- The Milestone 2 addition of 15 focused tests and the current 226-test baseline.
- Deterministic alarm evaluation and lifecycle logic.
- Point catalogs, point-sample history, current-value projections, and point-health concepts.
- Static Modbus-map preview and import.
- Deterministic CSV replay and simulated reads.
- Scenarios and facility-aware operational reset.
- Generated-alarm acknowledgement and audit events.
- Fixture version `1.0.0`, the Northstar isolation boundary, atomic flagship loading, rollback behavior, reset behavior, and database-hash evidence.
- The accepted decisions in ADR 0001 and ADR 0002.
- The fictional Northstar Data Hall as a legacy regression environment and secondary data-center demonstration.

Preservation does not convert existing laboratory rules, topology, or observations into standards-based requirements, conformance evidence, or evidence-sufficiency determinations. Current operational reset also deletes point samples and audit events; durable evidence retention remains planned.

## Flagship commitment

The flagship remains the fictional **Advanced Materials Research and Precision-Environment Facility** and its process-exhaust and pressure-cascade scenario.

The first coherent proof must cover:

- Duty process-exhaust fan failure and standby-fan response.
- A read-only or synthetic observation of a controller command/request indication compared with status.
- Independent airflow or pressure evidence.
- VFD or motor electrical corroboration.
- Makeup-air response, zone-pressure consequences, and treatment dependency.
- Missing, stale, suspect, overridden, late, or conflicting evidence.
- Failed standby start and degraded facility inference.
- Human verification, recovery, incomplete recovery, and reproducible incident evidence.

The exact command/request, VFD, and motor points and any topology expansion require a later ADR and roadmap slice. Duty/standby redundancy, pressure criteria, timers, airflow thresholds, and recovery intervals remain synthetic project intent unless a later applicability decision establishes another basis.

New York State outside New York City is a provisional reference-jurisdiction assumption only. Exact AHJ, local amendments, enforcement status, new/existing/altered status, facility use, material hazards, quantities, control areas, and process-exhaust applicability remain unresolved.

## Non-goals

FacilityOps Copilot is not:

- A BAS, EPMS, PLC, SCADA, DCIM, autonomous controller, or external control interface.
- A general-purpose facilities integration platform.
- A universal facilities ontology or comprehensive standards-compliance engine.
- A system that certifies commissioning, determines physical safety, or replaces qualified judgment.
- An AI-controlled or AI-approved operational system.
- A commercially validated product.
- A complete CMMS, work-order, document-control, or enterprise asset-management platform.
- A high-fidelity airflow, contaminant, process, electrical-transient, or CFD simulator.
- Primarily a software playground detached from facilities-engineering purpose.

## Change control

- This approved version is 2.0, dated 2026-07-22, and supersedes Version 1.0 dated 2026-07-19.
- Future tasks may not edit this file without explicit user approval for a charter revision.
- A proposed revision must identify the policy being changed, its reason, affected authority boundaries and roadmap consequences, and compatibility with preservation constraints.
- ADRs may clarify architecture and implementation choices but cannot override this charter.
- [PROJECT_STATUS.md](PROJECT_STATUS.md) and [ARCHITECTURE.md](ARCHITECTURE.md) must continue to distinguish verified repository behavior from intended direction.
