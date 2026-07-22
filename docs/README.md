# FacilityOps Copilot Documentation

This directory contains the change-controlled project direction, verified status, architecture, fictional facility definition, standards policy, and architecture decisions.

## Document authority and purpose

1. [PRODUCT_CHARTER.md](PRODUCT_CHARTER.md) defines the approved project identity, priorities, commercial posture, authority boundaries, and non-goals.
2. [ROADMAP.md](ROADMAP.md) defines approved milestone order, scope, completion evidence, and deferred work.
3. [PROJECT_STATUS.md](PROJECT_STATUS.md) reports verified repository behavior and known gaps. It must not describe planned behavior as implemented.
4. [ARCHITECTURE.md](ARCHITECTURE.md) describes implemented architecture separately from planned direction.
5. [STANDARDS_POSITION.md](STANDARDS_POSITION.md) defines project policy for controlled references, applicability, synthetic requirements, evaluation outcomes, and human disposition.
6. [FLAGSHIP_FACILITY.md](FLAGSHIP_FACILITY.md) defines the recorded fictional flagship profile, implemented boundary, and provisional legal applicability.
7. [decisions/README.md](decisions/README.md) defines ADR governance and indexes accepted ADRs 0001–0004.

The current bounded machine-readable review basis starts at the [flagship standards-basis manifest](../data/standards/flagship/1.0.0/manifest.json). The complete non-authoritative, date-bounded broad research register reviewed for the 2026-07-22 rebaseline remains preserved under [references](references/FacilityOps_Standards_Baseline_2026-07-22.md); the bounded package does not silently rewrite that historical record.

## Historical and supporting documents

- [facility_model.md](facility_model.md) describes Northstar Data Hall, the preserved legacy regression fixture and secondary data-center demonstration.
- Accepted ADRs remain historical decision records. Later implementation or project reorientation does not authorize rewriting their original context or decision.
- [PROPOSED—INACTIVE: Flagship Observation, Evidence, and Golden-Scenario Decision Packet](decision-packets/0001-flagship-observation-and-scenario.md) consolidates the next review questions. It is non-authoritative, inactive, and not loaded by the application.

## Interpretation rules

- The charter governs identity and authority boundaries.
- ADRs may clarify architecture but cannot override the charter.
- Status documentation governs claims about what is implemented.
- A reference source is not automatically applicable.
- A deterministic result is a computed result, not qualified human acceptance or a safety determination.
- A canonical observation is a reported indication, not proof of physical state.
- Planned capability must remain clearly labeled as planned.

## Change discipline

Documentation changes must preserve completed history, distinguish decisions from implementation, maintain internal links, and update [PROJECT_STATUS.md](PROJECT_STATUS.md) when verified behavior or verification evidence changes.
