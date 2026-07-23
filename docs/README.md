# FacilityOps Copilot Documentation

This directory contains the change-controlled project direction, verified status, architecture, fictional facility definition, standards policy, and architecture decisions.

## Document authority and purpose

1. [PRODUCT_CHARTER.md](PRODUCT_CHARTER.md) defines the approved project identity, priorities, commercial posture, authority boundaries, and non-goals.
2. [ROADMAP.md](ROADMAP.md) defines approved milestone order, scope, completion evidence, and deferred work.
3. [PROJECT_STATUS.md](PROJECT_STATUS.md) reports verified repository behavior and known gaps. It must not describe planned behavior as implemented.
4. [ARCHITECTURE.md](ARCHITECTURE.md) describes implemented architecture separately from planned direction.
5. [STANDARDS_POSITION.md](STANDARDS_POSITION.md) defines project policy for controlled references, applicability, synthetic requirements, evaluation outcomes, and human disposition.
6. [FLAGSHIP_FACILITY.md](FLAGSHIP_FACILITY.md) defines the recorded fictional flagship profile, implemented boundary, and provisional legal applicability.
7. [decisions/README.md](decisions/README.md) defines ADR governance and indexes accepted ADRs 0001–0006.

The bounded machine-readable standards review basis starts at the preserved [flagship standards-basis `1.0.0` manifest](../data/standards/flagship/1.0.0/manifest.json). The additive [standards-basis `1.1.0` manifest](../data/standards/flagship/1.1.0/manifest.json) binds the same inactive, non-executable requirements to the additive observation topology without changing the default no-observation-baseline statement. The complete non-authoritative, date-bounded broad research register reviewed for the 2026-07-22 rebaseline remains preserved under [references](references/FacilityOps_Standards_Baseline_2026-07-22.md); the bounded packages do not silently rewrite that historical record.

The implemented observation tranche is governed by [ADR 0005](decisions/0005-source-native-and-canonical-observation-semantics.md) and [ADR 0006](decisions/0006-synthetic-flagship-replay-and-topology-evolution.md). Its repository-versioned inputs are the [mapping package](../data/observation_mappings/flagship-synthetic-indications/1.0.0/manifest.json) and the allowlisted [synthetic replay package](../data/observation_replays/flagship-process-exhaust-evidence-sequence/1.0.0/manifest.json). These packages implement reported-indication evidence only; they do not implement point condition, equipment/system/facility inference, findings, evidence sufficiency or independence, human disposition, or recovery evaluation.

## Historical and supporting documents

- [facility_model.md](facility_model.md) describes Northstar Data Hall, the preserved legacy regression fixture and secondary data-center demonstration.
- Accepted ADRs remain historical decision records. Later implementation or project reorientation does not authorize rewriting their original context or decision.
- [PROPOSED—INACTIVE: Flagship Observation, Evidence, and Golden-Scenario Decision Packet](decision-packets/0001-flagship-observation-and-scenario.md) preserves the earlier recommendation history and identifies the architectural portions superseded by ADRs 0005 and 0006. Its criteria, inference, evidence-sufficiency, finding, human-workflow, and recovery proposals remain non-authoritative, inactive, and not loaded by the application.

## Interpretation rules

- The charter governs identity and authority boundaries.
- ADRs may clarify architecture but cannot override the charter.
- Status documentation governs claims about what is implemented.
- A reference source is not automatically applicable.
- A deterministic result is a computed result, not qualified human acceptance or a safety determination.
- A canonical observation is a reported indication, not proof of physical state.
- A reported-observation projection remains scoped evidence, not actual or authoritative equipment state.
- Planned capability must remain clearly labeled as planned.

## Change discipline

Documentation changes must preserve completed history, distinguish decisions from implementation, maintain internal links, and update [PROJECT_STATUS.md](PROJECT_STATUS.md) when verified behavior or verification evidence changes.
