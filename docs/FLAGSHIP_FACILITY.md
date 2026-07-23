# Flagship Facility and Golden Proof

> **Status: minimum Milestone 2 topology and Milestone 3 fictional profile, controlled-source catalog, provisional applicability matrix, inactive requirements, evidence categories, and traceability implemented; observations, inference, evaluation, human review, recovery behavior, and the golden scenario remain planned.** This document defines a fictional technical-laboratory environment. It does not describe a real facility, certify a design, establish code applicability, approve physical control intent, determine safety, or claim behavior beyond [PROJECT_STATUS.md](PROJECT_STATUS.md).

## Flagship purpose

The **Advanced Materials Research and Precision-Environment Facility** is the fictional flagship for FacilityOps Copilot. Its primary purpose is to support a standards-grounded technical proof involving process exhaust, pressure relationships, control indications, independent equipment evidence, degraded operation, human verification, recovery, and incident reconstruction.

The broader fictional facility may eventually include precision environments, utilities, and electrical support. Those areas are not the present scope. The first coherent proof remains the process-exhaust and pressure-cascade scenario.

## Recorded fictional profile and provisional legal applicability

[ADR 0004](decisions/0004-flagship-fictional-applicability-profile.md) records the following project-owner decisions for the fictional proof:

- A new, privately operated, one-story, sprinklered research facility in the Town of Horseheads, Chemung County, New York, outside incorporated villages and New York City.
- The Town code-enforcement authority as the assumed local AHJ for the exercise.
- A Group B research-laboratory occupancy assumption, excluding healthcare, pharmaceutical compounding, semiconductor production, pilot manufacturing, and full production.
- Bench-scale alumina-based ceramic powder and sintered ceramic specimens used for weighing, wet mixing, preparation, and characterization.
- A 250 g maximum open powder batch and 5 kg maximum laboratory inventory in closed containers.
- A noncombustible, nonreactive material assumption with particulate inhalation and contamination concern.
- Exclusion of combustible dust, flammable-gas and flammable-liquid processes, explosives, pyrophoric and water-reactive materials, oxidizers, highly toxic gases, radioactive materials, biological agents, classified electrical locations, and quantities intended to create a high-hazard occupancy.
- Corridor, transition/airlock, and process-laboratory zones with intended pressure direction from corridor to airlock to laboratory, without a numerical pressure criterion.
- A dedicated process-exhaust system, monitored particulate treatment, duty/standby VFD fan pair, common shared exhaust and treatment dependencies, and supporting supply/makeup air.
- A read-only FacilityOps boundary with no external command or controller-configuration path.

These are simulation and project assumptions. They do not establish actual territorial or agency jurisdiction, adopted editions or amendments, enforcement or permit responsibility, legal occupancy, construction or sprinkler classification, fire/control areas, hazardous-material thresholds, SDS or composition, exposure limits, process-exhaust applicability, or physical design approval.

The first ten golden-proof requirements are project-authored qualitative synthetic sequence-of-operation requirements informed by controlled references. They have the project-owner decision recorded at the individual-requirement level and use `ACCEPTED_FOR_SIMULATION`; all remain `INACTIVE` and non-executable. Two additional drafts remain `DRAFT`, `PROPOSED`, and `INACTIVE`. FacilityOps does not represent any of them as directly code-required, commissioning-accepted, or authorized for physical operation.

## Implemented Milestone 2 boundary

ADRs 0001 and 0002 define the implemented minimum topology and persistence boundary. The version `1.0.0` flagship fixture contains:

- The reference corridor, transition/airlock, and process laboratory.
- Two explicitly directed pressure boundaries forming the corridor-to-transition-to-laboratory cascade.
- One process-exhaust system.
- Duty and standby process-exhaust fans.
- One shared exhaust path.
- A monitored treatment permissive dependency.
- A monitored supply or makeup-air dependency.
- Equipment-owned point definitions and typed bindings for potential availability, run, fault, speed, airflow, duct static, damper position, treatment, supply/makeup-air, zone-pressure, and boundary-differential indications. These definitions are not observations.

The topology represents synthetic project intent. It does not establish a physical design, approved sequence of operation, applicable redundancy requirement, pressure criterion, capacity threshold, controller behavior, or evidence-sufficiency rule. ADR 0004 separately records qualitative inactive design intent; topology alone does not establish it.

The implemented fixture intentionally contains no current-value baseline or golden-scenario observations. It also contains no process-enabled operating-context or controller command/request point definition and no dedicated VFD or motor electrical corroboration point definition. Those evidence categories are required by the rebaselined proof, but exact point definitions, relationships, and topology changes require a later ADR and approved roadmap slice.

## Implemented Milestone 3 boundary

The separate version `1.0.0` standards-basis package contains 18 profile facts, 35 controlled sources, 29 provisional, informative, owner/project, or simulation applicability bases, 19 evidence categories, and 12 project-authored synthetic requirements.

Whole-package validation enforces exact flagship and fixture binding, global identifier uniqueness, permitted statuses, provenance, multi-source reference resolution and basis-category consistency, point-definition references to the unchanged flagship catalog, the exact profile facts and ten recorded qualitative requirements, and inactive/non-executable state. Evidence records separately identify point-definition representation and observation availability; the current package declares no flagship observation baseline. A malformed candidate cannot partially replace the prior in-memory snapshot.

Seven read-only routes and a separate reviewer workbench display the package and the visible chain `controlled source → applicability basis → synthetic requirement → required evidence category`. The package is independent of active SQLite state and adds no database schema or topology change.

The Milestone 3 feature does not evaluate a requirement; compute `CONFORMING`, `NONCONFORMING`, `INDETERMINATE`, or `NOT_APPLICABLE`; infer equipment, system, or facility state; approve a legal applicability determination; or authorize physical operation.

## Observation and inference chain

The flagship proof must follow this conceptual chain:

```text
source artifact or stream
→ source-native observation as received by FacilityOps
→ versioned mapping and normalization
→ canonical observation
→ point condition
→ equipment, system, and facility inference
→ consequence and uncertainty
```

A canonical observation remains a reported indication. Examples include a controller command/request indication, run-status indication, fault bit, speed feedback, motor current, VFD state, measured airflow, or differential pressure. No single indication independently proves physical equipment response or facility condition.

The future proof must identify which evidence is:

- Directly reported by a source.
- Normalized or derived through a versioned mapping.
- Used to compute a point condition.
- Used to infer equipment, system, pressure-cascade, or facility state.
- Contradictory, missing, stale, suspect, overridden, late, or otherwise insufficient.

## Golden-proof evidence categories

The first coherent proof must cover:

### Duty-fan initiating event

- Duty-fan availability, run, and fault indications.
- A read-only or synthetic observation of a controller command/request indication. FacilityOps does not issue the command.
- Speed feedback and VFD or motor electrical corroboration.
- Independent delivered-airflow or relevant pressure evidence.

### Standby response

- Standby availability.
- Read-only or synthetic command/request indication.
- Run and fault status.
- Speed and VFD or motor electrical corroboration.
- Independent airflow or pressure response.
- Successful response and failed-start cases.

### Shared-path and dependency evidence

- Shared-path airflow or duct-static indication.
- Relevant damper-position indication.
- Treatment availability or permissive indication.
- Supply or makeup-air response.
- Common-path limitation or conflicting evidence where applicable.

### Pressure-cascade consequence

- Process-laboratory zone pressure.
- Corridor-to-transition differential pressure.
- Transition-to-laboratory differential pressure.
- Direction, persistence, and uncertainty evaluated under later controlled synthetic requirements.
- Bounded consequence and affected-scope inference without contaminant-exposure or safety claims.

### Evidence health and sufficiency

- Missing evidence.
- Stale evidence.
- Suspect or uncertain evidence.
- Overridden or out-of-service evidence.
- Late or out-of-order evidence.
- Conflicting command, status, airflow, pressure, VFD, motor, or electrical evidence.

The working external outcomes are `CONFORMING`, `NONCONFORMING`, `INDETERMINATE`, and `NOT_APPLICABLE`. Missing or contradictory required evidence must be capable of producing `INDETERMINATE`; the internal separation of applicability from evaluation remains a later ADR decision.

## Planned deterministic scenario phases

1. **Declared baseline:** The applicable synthetic requirement versions, facility assumptions, mappings, observations, evidence-health conditions, and operating context are identified.
2. **Duty-fan failure:** Duty-fan indications and independent evidence show a bounded initiating discrepancy or loss.
3. **Standby request and response:** A read-only or synthetic command/request indication is compared with status, VFD or motor electrical evidence, and independent delivered-airflow or pressure evidence.
4. **Failed or insufficient standby response:** Missing response, contradictory indications, insufficient capacity evidence, or failed start is evaluated without treating controller execution as physical proof.
5. **Dependency response:** Treatment, shared-path, damper, and supply/makeup-air evidence are evaluated.
6. **Pressure-cascade degradation:** Boundary and zone observations support a bounded inference of degradation, loss, or uncertainty.
7. **Facility consequence and uncertainty:** Deterministic rules compute affected scope, consequence, uncertainty, and required verification without determining safety or authorizing action.
8. **Human verification and response:** Persons or organizations that possess the required qualifications and assigned organizational or legal authority review evidence and record decisions or actions separately from computed findings.
9. **Recovery observations:** After a recorded action or response, FacilityOps may receive new observations. The action or response record does not establish causation or physical effect.
10. **Recovery evaluation:** New evidence is evaluated against the controlled synthetic recovery requirements.
11. **Human disposition:** Persons or organizations that possess the required qualifications and assigned organizational or legal authority review the recovery finding, unresolved evidence, and any incomplete remainder.
12. **Incident reconstruction:** Retained versions, observations, mappings, inferences, findings, human records, and recovery evidence reproduce the event.

## Parameter and source basis

No universal numerical pressure band, standby-start time, airflow threshold, delay, hysteresis, recovery interval, or hold time is approved by this document.

Each future parameter must identify:

- Whether its basis is synthetic simulation intent, project or owner requirement, OPR/BOD/SOO, manufacturer instruction, procedure, permit, regulation, adopted code, or formal standard.
- The exact source and effective version.
- Applicability and approval status.
- Units, tolerance, expected normal variability, and measurement uncertainty.
- Persistence, delay, hysteresis, recovery behavior, and credible false-positive conditions.
- Required evidence and insufficient-evidence behavior.
- Assumptions, exclusions, limitations, and review scope.

Until a later qualified decision establishes another basis, duty/standby redundancy, pressure relationships, timers, airflow criteria, and recovery intervals remain synthetic project intent.

## Human and safety boundaries

Deterministic code may compute point conditions, inferred states, timing results, evaluations, and bounded findings reproducibly. Determinism does not make the requirement, mapping, evidence, inference, or finding automatically valid.

The following authorities remain with persons or organizations that possess the required qualifications and assigned organizational or legal authority: applicability decisions, requirement approval, test authorization, operational action, commissioning acceptance, waivers, final disposition, determinations of physical safety, and authorization for operation. FacilityOps must not command equipment, certify commissioning, authorize physical testing, independently determine safety, or treat a recorded action as proof of restoration.

## Broader facility context

Later research may add only those facility areas and dependencies that materially deepen a defined technical question. Candidate contexts include:

- Additional process laboratories and transition zones.
- Exhaust treatment and discharge evidence.
- Supply and makeup-air systems.
- Electrical service, switchgear, motor control, VFDs, UPS, ATS, and standby power where they support the flagship evidence chain.
- Utilities and precision environments where they create a specific dependency or recovery question.

Expansion requires an approved roadmap slice and, where it changes accepted topology or relationships, a new ADR. FacilityOps is not intended to become a comprehensive campus model or universal facilities platform.

## Use limitations

- All facility, equipment, observations, requirements, and scenarios are fictional.
- Pressure and airflow behavior will be a deterministic operational abstraction, not high-fidelity physics.
- The scenario will not calculate contaminant transport, exposure, regulatory compliance, or physical safety.
- Technical content requires review by the relevant facility operations, controls, commissioning, mechanical, electrical, process-safety, and industrial-hygiene disciplines before it may be described as representative practice.
- No statement in this document establishes cleanroom classification, containment certification, code compliance, commissioning acceptance, or authorization for operation.
