# FacilityOps Copilot Repository Instructions

Before planning or changing the product, read:

- [`docs/PRODUCT_CHARTER.md`](docs/PRODUCT_CHARTER.md) for the approved product direction and boundaries.
- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) for verified current behavior and gaps.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) for approved milestone order and scope.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the implemented and planned architecture.
- [`docs/FLAGSHIP_FACILITY.md`](docs/FLAGSHIP_FACILITY.md) before planning or changing facility topology, facility-domain behavior, pressure relationships, operating modes, or scenario content.
- [`docs/decisions/README.md`](docs/decisions/README.md) and all relevant accepted ADRs before making architectural or domain-model decisions.

Work on one user-approved roadmap slice at a time. If a slice depends on an unresolved architectural decision, first draft a proposed ADR and stop for explicit approval before implementing that decision. Stop and ask for direction if a request conflicts with the product charter. Do not change the product charter, or reorder, remove, or materially expand major roadmap milestones, without explicit user approval.

## Safety and data

- Never command, configure, or write back to an external BAS, EPMS, PLC, SCADA, DCIM, or physical facility system.
- Local laboratory writes are allowed when they support import, replay, simulation, scenarios, alarm evaluation, acknowledgements, audit, testing, or local configuration.
- Use fictional, synthetic, sanitized, non-sensitive, or explicitly authorized read-only data only.
- Never commit credentials, customer data, proprietary exports, real facility network information, or confidential configurations.
- Treat alarm priority, point condition, operational risk, advisory classification, and incident severity as separate concerns until an approved architecture decision resolves their vocabularies.

## Engineering

- Preserve the implemented Northstar Data Hall fixture and its regression behavior.
- Keep authoritative state and acceptance determinations deterministic. AI may advise in the future but must not own alarm, equipment, system, facility, consequence, or functional-test decisions.
- Prefer readable Python and straightforward designs over clever abstractions.
- Use SQLite, FastAPI, and the minimal frontend consistently with the current architecture unless an approved roadmap slice changes that direction.
- Add deterministic tests for behavior changes and verify in proportion to risk.
- Update relevant documentation and `docs/PROJECT_STATUS.md` whenever verified behavior changes.
- Do not claim planned or unverified behavior as implemented.

## Reporting

Write operational output for facilities personnel. Explain what happened, affected equipment and systems, operational consequences, supporting evidence, uncertainty, and the follow-up an operator or technician should consider. Highlight urgent conditions without assuming the unresolved severity architecture has been settled.

### Technical language

- For engineering, facilities, controls, maintenance, commissioning, and operational content, use direct technical English, active voice, consistent terminology, and explicit conditions.
- Preserve accepted technical and equipment terms when they are more precise than simplified alternatives.
- Use modal verbs consistently: **must** for a requirement, **should** for a recommendation, **may** for permission, and **can** for capability.
- Use operational verbs precisely. Do not treat verify, ensure, monitor, maintain, align, isolate, secure, trip, shut down, start, stop, reset, and restore as interchangeable.
- Distinguish an observed indication from the equipment, system, or facility state inferred from it.
- Distinguish alarms, warnings, permissives, interlocks, trips, simulated command representations, equipment feedback, and operator actions.
- Explain relevant causal chains, assumptions, dependencies, evidence, uncertainty, and failure modes.
- When proposing a threshold or acceptance criterion, state its technical basis, expected normal variability, instrument uncertainty, persistence or delay, applicable hysteresis, credible false-positive conditions, and required response.
- Do not claim formal ADS-STE100 compliance unless the text has been checked against the applicable specification and approved project terminology.
