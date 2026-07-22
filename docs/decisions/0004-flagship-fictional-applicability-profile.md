# ADR 0004: Flagship fictional applicability profile and qualitative design intent

- Status: Accepted
- Date: 2026-07-22
- Approver: Daniel Berg, Project Owner
- Supersedes: None
- Superseded by: None

## Context

Milestone 3 needs a bounded fictional profile before controlled sources can be reviewed honestly or project-authored synthetic sequence-of-operation requirements can be recorded. Facility labels alone cannot establish occupancy, material hazards, code applicability, exhaust requirements, authority having jurisdiction, or suitable operating criteria.

The project owner supplied the profile and qualitative design intent in this decision. FacilityOps records those facts as fictional project decisions; it does not originate them or convert them into legal conclusions.

Focused official-source research supports use of the 2025 New York Uniform Code as the current jurisdictional reference set and supports the Town of Horseheads code-enforcement office as a reasonable fictional local-authority assumption for Town territory outside incorporated villages. The research does not establish section-level applicability, actual parcel jurisdiction, local amendments, permit responsibility, a hazardous-exhaust trigger, or that the selected fan, treatment, pressure, permissive, and recovery arrangements are legally required.

## Decision

### Nature and authority of the profile

The following facts are accepted as the versioned fictional applicability profile for the Advanced Materials Research and Precision-Environment Facility. They are project assumptions for a technical laboratory. They are not legal, permitting, code-compliance, design-acceptance, commissioning-acceptance, physical-safety, operability, or authorization determinations.

Applicability remains a separate qualified human decision supported by controlled sources. Official-source metadata, titles, public summaries, and research findings do not make a provision applicable by themselves.

### Facility and jurisdiction assumptions

- The facility is new, privately operated, one story, and sprinklered.
- It is fictionally located in the Town of Horseheads, Chemung County, New York, outside every incorporated village and outside New York City.
- For this laboratory exercise, the Town code-enforcement authority is the assumed local authority having jurisdiction.
- Actual agency jurisdiction, adopted editions, amendments, enforcement authority, intermunicipal agreements, and permit responsibility remain subject to controlled-source verification.
- The scoped space is a research laboratory, not healthcare, pharmaceutical compounding, semiconductor production, pilot manufacturing, or full production.
- Group B research-laboratory use is the intended fictional occupancy assumption, not a verified legal classification.

### Material and process assumptions

- The process uses bench-scale alumina-based ceramic powder and sintered ceramic specimens for weighing, wet mixing, preparation, and characterization.
- The maximum open powder batch is 250 g.
- The maximum laboratory powder inventory is 5 kg in closed containers.
- Those quantities are simulation inventory bounds and do not independently establish compliance with a hazardous-material threshold.
- The scoped material is assumed noncombustible and nonreactive but presents a particulate inhalation and contamination concern.
- The proof excludes combustible dust, flammable-gas processes, flammable-liquid processes, explosives, pyrophoric materials, water-reactive materials, oxidizers, highly toxic gases, radioactive materials, biological agents, classified electrical locations, and quantities intended to produce a high-hazard occupancy.

The material assumptions do not replace a supplier safety data sheet, CAS identity, composition, particle-size distribution, crystalline-silica assessment, hazard classification, or exposure assessment.

### Accepted qualitative system intent

- The existing zones remain the corridor, transition or airlock, and process laboratory.
- Intended pressure direction is corridor to transition or airlock to process laboratory.
- No numerical differential-pressure criterion is approved.
- A dedicated process-exhaust system serves the process enclosure and laboratory.
- Exhaust passes through monitored particulate treatment before outdoor discharge.
- Treatment is an owner or project dependency. This decision does not claim that a specific code requires it.
- Two VFD-driven fans form a duty and standby pair. Either fan can provide the intended normal duty.
- The shared exhaust path and treatment unit are common dependencies.
- A supply or makeup-air subsystem supports the pressure cascade.
- FacilityOps remains read-only and must never issue a command or configure a controller.

### Accepted qualitative, non-executable synthetic SOO requirements

The following project-authored requirements are accepted for simulation as qualitative intent only. They remain inactive and non-executable. Acceptance records the project-owner decision; it does not establish an external-source mandate or approve any parameter, mapping, configuration, evaluation rule, or physical use.

1. The external control system may enable the scoped process only when the treatment path, process-exhaust capability, supply/makeup-air dependency, and required pressure-control evidence are available.
2. When the process is enabled, the external control system requests operation of the selected duty fan. FacilityOps observes the request but does not issue it.
3. A fan command or request does not establish fan operation. Future fan-operation inference must distinguish controller request, VFD indication, motor/electrical response, and delivered airflow.
4. VFD feedback and motor/electrical response are separate evidence categories. Their provenance must determine whether they constitute independent corroboration.
5. Process-containment inference additionally requires differential-pressure evidence supporting the intended corridor-to-airlock-to-laboratory pressure direction.
6. If supported duty-fan performance is lost, the external control system removes or withholds the process permissive and requests the standby fan. A standby request alone does not establish successful changeover.
7. A standby fan cannot compensate for loss of the shared exhaust path, treatment availability, or another required common dependency.
8. Loss of treatment availability or required makeup-air capability removes or withholds the process permissive. Exact safe-mode fan behavior remains unresolved.
9. Missing, stale, suspect, overridden, late, duplicated, or conflicting required evidence must be capable of preventing a supported conclusion.
10. Recovery requires new post-action observations and a separate recovery evaluation. Alarm acknowledgment, reset, command completion, or return-to-normal indication alone does not establish recovery.

### Source and implementation boundary

The repository may record a controlled source catalog, provisional applicability matrix, evidence categories, and traceability for these decisions. Each external source relationship must state whether it is a provisional applicability candidate or an informative influence. No external source reviewed for this decision directly supplies the complete qualitative sequence above.

The Milestone 3 representation must remain read-only, repository-versioned, facility-bound, and non-executable. It must not create a database migration, alter the tracked database, change flagship topology version `1.0.0`, add scenario observations, modify alarm rules, evaluate conformance outcomes, or command equipment.

## Consequences

Milestone 3 can now distinguish owner/project intent, simulation assumptions, adopted-code research, conditional federal requirements, and informative standards influences. Reviewers can inspect why a source may matter without treating it as directly applicable or executable.

The exact supplier material, SDS, hazard classification, employee-exposure basis, control and fire areas, adopted clause applicability, electrical design, ventilation criteria, instrument assumptions, detailed controller sequence, and recovery parameters remain unresolved. Later work must preserve an indeterminate path when required evidence is insufficient.

The accepted profile may require prospective revision if later controlled evidence conflicts with a fictional assumption. Such a revision requires a new project-owner decision; research or implementation must not silently change this ADR.

## Alternatives considered

### Infer applicability from the laboratory label

Rejected. A research-laboratory label does not resolve occupancy, chemical scope, hazardous exhaust, exposure, material quantity, fire area, control area, permit, or local-jurisdiction facts.

### Treat the selected fan, treatment, and pressure arrangement as code-required

Rejected. The available source research does not establish that conclusion. The arrangement remains owner/project synthetic intent.

### Delay all work until a complete legal and licensed-source review exists

Rejected for the fictional laboratory. The project can safely record explicit assumptions, uncertainty, source metadata, and inactive qualitative requirements without making a real-world legal or physical-use determination.

## Verification and implementation impact

This decision authorizes a bounded, read-only Milestone 3 standards-basis package and reviewer presentation. Validation must reject duplicate IDs, invalid statuses, unresolved references, missing provenance, invalid facility bindings, and executable requirements. A malformed package must not become partially visible.

This decision does not authorize Milestone 4 observation semantics, topology changes, scenario observations, numerical criteria, inference, evaluation outcomes, human disposition, external connectivity, or equipment control.

## References

- [FacilityOps Copilot Product Charter](../PRODUCT_CHARTER.md)
- [FacilityOps Copilot Standards Position](../STANDARDS_POSITION.md)
- [FacilityOps Copilot Roadmap, Milestone 3](../ROADMAP.md#milestone-3--controlled-applicability-and-requirement-basis)
- [Flagship Facility and Golden Proof](../FLAGSHIP_FACILITY.md)
- [ADR 0001: Minimum flagship topology](0001-minimum-flagship-topology.md)
- [ADR 0002: Facility fixture identity and minimum topology persistence](0002-facility-fixture-identity-and-topology-persistence.md)
- [ADR 0003: Epistemic and human-authority boundaries](0003-epistemic-and-human-authority-boundaries.md)
- [Architecture Decision Records](README.md)
