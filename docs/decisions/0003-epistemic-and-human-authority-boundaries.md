# ADR 0003: Epistemic and human-authority boundaries

- Status: Accepted
- Date: 2026-07-22
- Approver: Daniel Berg, Project Owner
- Supersedes: None
- Superseded by: None

## Context

FacilityOps receives or creates heterogeneous fictional facility indications and uses deterministic logic to compute point conditions, infer higher-level state, evaluate synthetic control intent, and present bounded findings. The project must make clear what each layer can establish.

The Version 2.0 charter requires two separations:

1. A source or canonical observation reports an indication; it does not independently prove physical equipment, system, or facility state.
2. Deterministic evaluation produces a reproducible computed finding; it does not independently approve applicability, authorize a test or operational action, accept commissioning work, waive a requirement, determine safety, or make a final disposition.

Without a durable decision, future documentation and implementation could again use “authoritative,” “state,” “acceptance,” or “pass/fail” in ways that collapse reported evidence, inference, computation, and qualified judgment.

This ADR addresses epistemic and human-authority boundaries only. It does not select schemas, field names, status-transition roles, numerical criteria, persistence models, workflow implementations, or a generalized conformance language.

## Proposed decision

### Observation and inference boundary

FacilityOps will use the following conceptual chain:

```text
source artifact or stream
→ source-native observation as received by FacilityOps
→ versioned mapping and normalization
→ canonical observation
→ point condition
→ equipment, system, and facility inference
→ consequence and uncertainty
```

Each layer must retain traceability to its inputs and must not claim more than its evidence permits.

- A source-native observation records what FacilityOps received from an identified artifact or stream.
- Mapping and normalization are versioned transformations whose assumptions and limitations remain inspectable.
- A canonical observation remains a reported indication.
- A point condition is a deterministic computation about that indication under stated temporal, quality, override, and other rules.
- Equipment, system, and facility states are inferences supported by lower-layer evidence.
- A computed consequence is an inferred or predicted consequence with affected scope, assumptions, and uncertainty unless separate observations support it as a realized consequence.

An observation created by FacilityOps or a scenario must be identified as synthetic and traceable to its generator and scenario version. It must not be represented as received field evidence.

A controller command/request indication is an observed or synthetic indication only. FacilityOps does not issue the command. A controller-side indication that a command or request was accepted, issued, or executed establishes only what that source reported. It does not independently prove approved control intent, correct field I/O, field-device receipt, actuation, equipment operation, delivered process response, or facility consequence.

Duplicate or derived representations of one underlying source do not constitute independent corroboration merely because FacilityOps presents them as separate points.

Independent airflow, pressure, VFD, motor, electrical, and other corroboration may be required by a later controlled requirement. Their exact selection is outside this ADR.

### Deterministic computation boundary

Deterministic code owns reproducible computation. It produces computed point conditions, inferred states, timing results, replay outputs, evaluations, and bounded findings under identified inputs, assumptions, configuration, and rules.

Determinism provides reproducibility, not automatic validity. A repeated result may still be invalid if its source evidence, mappings, applicability decision, requirement, parameter basis, configuration, or rule is invalid.

Missing, stale, suspect, overridden, late, or conflicting required evidence must be capable of preventing a supported conclusion. The working external outcomes remain `CONFORMING`, `NONCONFORMING`, `INDETERMINATE`, and `NOT_APPLICABLE`. This ADR does not decide their internal data representation or whether applicability and evaluation use separate result objects.

`NOT_APPLICABLE` must trace to a controlled applicability decision made by an authorized person or organization, or to an approved applicability rule applied under its stated conditions. It must not substitute for missing evidence or unresolved applicability. Under the current external outcome model, unresolved applicability produces `INDETERMINATE`; a later ADR may separate applicability and evaluation results internally.

A `CONFORMING` or `NONCONFORMING` finding applies only to its identified requirement, applicability basis, scope, evidence interval, assumptions, configuration, and rule version. It does not establish general standards compliance, commissioning acceptance, physical safety, operability, or authorization for operation.

When an evaluation cannot assess its proposition because required evidence is insufficient, the result must be `INDETERMINATE`. A separate requirement that specifically evaluates evidence availability or quality may find missing or stale evidence `NONCONFORMING`, but that finding does not establish whether the underlying physical response conformed.

### Human-authority boundary

FacilityOps findings do not authorize or direct physical operational or test actions. The following authorities remain with persons or organizations that possess the required qualifications and assigned organizational or legal authority:

- Applicability decisions.
- Requirement approval.
- Test authorization.
- Operational action.
- Commissioning acceptance.
- Waivers.
- Final disposition.
- Determinations of physical safety and authorization for operation.

Separately authorized automatic control and protection functions remain outside FacilityOps and are not prohibited by this decision.

A deterministic finding may inform authorized decisions but cannot substitute for them.

A recorded human action or response does not establish its intended physical effect. A finding that recovery succeeded requires post-action observations and a separate recovery evaluation under controlled timing, quality, and evidence-sufficiency rules. Alarm acknowledgment, reset, return-to-normal indication, or command completion does not independently establish recovery. A computed recovery finding does not establish operability or authorize return to service. This boundary does not prevent authorized personnel from taking interim or conservative action while recovery remains unverified.

AI may draft candidate mappings, requirements, and tests; explain or summarize controlled computed findings; and propose troubleshooting suggestions. AI-generated content remains advisory and identifiable as such. AI must not originate, approve, or alter a controlled computed finding; approve or activate its own proposed controlled inputs, mappings, parameters, configurations, or rules; exercise human authority; or command a physical system. Controlled deterministic evaluation and its results must remain available when AI is disabled.

### Terminology boundary

Project documentation and interfaces must qualify ambiguous terms:

- Use **source indication**, **canonical observation**, **computed point condition**, **inferred equipment/system/facility state**, **computed consequence**, **bounded finding**, and **human disposition** when the distinction matters.
- Do not use **authoritative state** to imply physical truth.
- Do not use **acceptance** for a deterministic evaluation result.
- Do not use unqualified **pass/fail** where applicability or evidence sufficiency can be unresolved.

A human disposition records a separate authorized judgment. It does not rewrite the underlying observations, historical computed findings, or physical history, and it does not make missing evidence present.

## Consequences

The decision makes FacilityOps conclusions more reviewable and prevents a deterministic or AI subsystem from acquiring authority it does not have. Documentation, rules, APIs, and future user interfaces will require explicit labels and traceability across the observation, inference, finding, and disposition layers.

Some current repository terms, especially “authoritative determination” and deterministic “acceptance,” must be reworded. Acceptance of this ADR does not modify the existing deterministic alarm implementation. It changes how that behavior is interpreted and documented; it does not establish the alarm logic as a standards-based requirement or qualified disposition.

Future work must support insufficient-evidence behavior and new recovery evidence. This may require later architecture decisions, but this ADR does not choose their schemas or implementation.

## Alternatives considered

### Treat source values or controller state as physical truth

This is rejected because reported command, status, quality, or execution cannot independently establish correct mapping, field wiring, sensing, actuation, delivered airflow, pressure response, or equipment performance.

### Treat deterministic results as qualified acceptance

This is rejected because repeatability does not establish valid applicability, approved control intent, sufficient evidence, commissioning authority, safety, or authorization for physical operation.

### Allow AI to resolve ambiguity or approve its own drafts

This is rejected because AI cannot supply missing evidence or possess the required qualifications and assigned organizational or legal authority for applicability, approval, authorization, waiver, acceptance, or final disposition.

### Leave terminology contextual

This is rejected because the prior documentation used “authoritative,” “state,” and “acceptance” ambiguously enough to obscure the required boundaries.

## Verification and implementation impact

If accepted, documentation reviews must audit ambiguous authority and state terminology against this decision.

Later approved implementation slices would need tests showing that:

- Observation and inference layers remain traceable and distinguishable.
- Identical identified inputs, configuration, and rules reproduce the same result with AI disabled.
- A command/request indication does not prove physical operation.
- Required corroborating evidence can affect a bounded finding.
- Insufficient or conflicting evidence can produce an indeterminate result.
- Missing evidence cannot be reported as `NOT_APPLICABLE`.
- A computed `CONFORMING` result cannot be presented as commissioning acceptance, safety approval, or authorization for operation.
- Synthetic observations remain distinguishable from received observations.
- An operator action or alarm reset cannot establish recovery without post-action evidence and a separate recovery evaluation.
- Computed findings and human disposition remain separate.
- A waiver or human disposition does not replace or rewrite the underlying computed finding.
- AI cannot mutate controlled results or exercise human authority.

This proposed ADR makes no schema, field, role-transition, parameter, persistence, workflow, or generalized conformance-language decision. It does not authorize application changes.

## References

- [FacilityOps Copilot Product Charter](../PRODUCT_CHARTER.md)
- [FacilityOps Copilot Roadmap](../ROADMAP.md)
- [FacilityOps Copilot Architecture](../ARCHITECTURE.md)
- [FacilityOps Copilot Standards Position](../STANDARDS_POSITION.md)
- [FacilityOps Copilot Project Status](../PROJECT_STATUS.md)
- [Architecture Decision Records](README.md)
