# FacilityOps Copilot Repository Instructions

Before planning or changing the product, read:

- [`docs/PRODUCT_CHARTER.md`](docs/PRODUCT_CHARTER.md) for the approved product direction and boundaries.
- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) for verified current behavior and gaps.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) for approved milestone order and scope.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the implemented and planned architecture.
- [`docs/STANDARDS_POSITION.md`](docs/STANDARDS_POSITION.md) for controlled-reference, applicability, synthetic-requirement, finding, and human-disposition policy.
- [`docs/FLAGSHIP_FACILITY.md`](docs/FLAGSHIP_FACILITY.md) before planning or changing facility topology, facility-domain behavior, pressure relationships, operating modes, or scenario content.
- [`docs/decisions/README.md`](docs/decisions/README.md) and all relevant accepted ADRs before making architectural or domain-model decisions.

Work on one user-approved roadmap slice at a time. If a slice depends on an unresolved architectural decision, first draft a proposed ADR and stop for explicit approval before implementing that decision. Stop and ask for direction if a request conflicts with the product charter. Do not change the product charter, or reorder, remove, or materially expand major roadmap milestones, without explicit user approval.

## Safety and data

- Never command, configure, or write back to an external BAS, EPMS, PLC, SCADA, DCIM, or physical facility system.
- Local laboratory writes are allowed when they support import, replay, simulation, scenarios, alarm evaluation, acknowledgements, audit, testing, or local configuration.
- Use fictional, synthetic, sanitized, non-sensitive, or explicitly authorized read-only data only.
- Never commit credentials, customer data, proprietary exports, real facility network information, or confidential configurations.
- Treat alarm priority, point condition, operational risk, advisory classification, and incident severity as separate concerns until an approved architecture decision resolves their vocabularies.
- Treat a source or canonical observation as a reported indication within its stated quality, timing, mapping, and transformation limits. It does not independently prove physical state.
- A read-only or synthetic controller command/request indication is evidence only. FacilityOps must not issue the command.
- A recorded human action must not be treated as proof of physical effect; recovery requires new observations and a separate evaluation.

## Engineering

- Preserve the implemented Northstar Data Hall fixture and its regression behavior.
- Deterministic code owns reproducible computation. It produces computed point conditions, inferred states, timing results, replay outputs, evaluations, and bounded findings under identified inputs, assumptions, configuration, and rules. Determinism provides reproducibility, not automatic validity.
- Qualified personnel retain authority for applicability decisions, requirement approval, test authorization, operational action, commissioning acceptance, waivers, safety decisions, and final disposition.
- AI may draft or advise in the future, but it must not approve its own output, mutate controlled computation, exercise qualified human authority, or command a physical system. Deterministic operation must remain available with AI disabled.
- Prefer readable Python and straightforward designs over clever abstractions.
- Use SQLite, FastAPI, and the minimal frontend consistently with the current architecture unless an approved roadmap slice changes that direction.
- Add deterministic tests for behavior changes and verify in proportion to risk.
- Update relevant documentation and `docs/PROJECT_STATUS.md` whenever verified behavior changes.
- Do not claim planned or unverified behavior as implemented.
- Preserve an `INDETERMINATE` path when required evidence is missing, stale, suspect, overridden, late, or conflicting. Do not force a binary result.
- Do not describe a topology, source registry entry, synthetic requirement, deterministic finding, or domain review as code compliant, owner approved, commissioning accepted, safe, or authorized for physical operation.
- Do not propose a pressure band, timer, airflow threshold, recovery interval, or other criterion without its source category, applicability, parameter basis, units, uncertainty, persistence, limitations, evidence needs, and review status.

## Reporting

Write technical output for facilities personnel and engineering reviewers. Explain what a source reported, what FacilityOps computed or inferred, affected equipment and systems, operational consequences, supporting and contradictory evidence, uncertainty, and the verification a qualified person should consider. Highlight urgent indications without claiming physical safety, operational authorization, or a severity model that has not been approved.

### Technical language

- For engineering, facilities, controls, maintenance, commissioning, and operational content, use direct technical English, active voice, consistent terminology, and explicit conditions.
- Preserve accepted technical and equipment terms when they are more precise than simplified alternatives.
- Use modal verbs consistently: **must** for a requirement, **should** for a recommendation, **may** for permission, and **can** for capability.
- Use operational verbs precisely. Do not treat verify, ensure, monitor, maintain, align, isolate, secure, trip, shut down, start, stop, reset, and restore as interchangeable.
- Distinguish an observed indication from the equipment, system, or facility state inferred from it.
- Distinguish alarms, warnings, permissives, interlocks, trips, simulated command representations, equipment feedback, and operator actions.
- Explain relevant causal chains, applicability, assumptions, dependencies, evidence sufficiency, uncertainty, and failure modes.
- When proposing a threshold or evaluation criterion, state its source category, technical and applicability basis, expected normal variability, instrument uncertainty, persistence or delay, applicable hysteresis, credible false-positive conditions, evidence needs, limitations, and required human review.
- Do not claim formal ADS-STE100 compliance unless the text has been checked against the applicable specification and approved project terminology.
