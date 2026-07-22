# Architecture Decision Records

## Purpose and authority

Architecture Decision Records (ADRs) capture significant technical and domain-model decisions, their context, and their consequences. ADRs make decisions reviewable; they do not prove that a decision has been implemented.

ADRs cannot override [`../PRODUCT_CHARTER.md`](../PRODUCT_CHARTER.md). If a proposed decision conflicts with the charter, work must stop until the user explicitly approves a charter change. Roadmap ordering and scope remain governed by [`../ROADMAP.md`](../ROADMAP.md).

## Filename convention

Use four-digit sequential identifiers and a short lowercase slug:

```text
0001-short-decision-title.md
0002-next-decision-title.md
```

Numbers are never reused, including for rejected or superseded decisions.

## Status lifecycle

- **Proposed:** Ready for review but not authoritative.
- **Accepted:** Explicitly approved and authoritative for in-scope future work.
- **Rejected:** Considered and not approved.
- **Superseded:** Replaced by a later accepted ADR.
- **Deprecated:** Previously accepted but no longer recommended; retained for history until superseded or removed by an approved decision.

Only an accepted ADR governs implementation. A code change, draft document, or pull request does not implicitly accept an ADR.

## Required template

```markdown
# ADR NNNN: Decision title

- Status: Proposed | Accepted | Rejected | Superseded | Deprecated
- Date: YYYY-MM-DD
- Approver: user or named decision authority
- Supersedes: ADR NNNN or None
- Superseded by: ADR NNNN or None

## Context

What problem requires a durable decision? What verified current behavior and constraints apply?

## Decision

What is decided? Define terms and boundaries precisely.

## Consequences

What becomes easier, harder, required, or prohibited?

## Alternatives considered

What credible alternatives were evaluated and why were they not selected?

## Verification and implementation impact

What code, data, tests, migrations, documentation, status entries, or compatibility work would be required? Do not claim it is complete unless verified.

## References

Link the charter, roadmap milestone, architecture, status evidence, and related ADRs.
```

## Decision index

ADRs 0001 through 0004 have been accepted.

| ADR | Title | Status | Date | Supersedes |
|---|---|---|---|---|
| [ADR 0001](0001-minimum-flagship-topology.md) | Minimum flagship topology | Accepted | 2026-07-20 | None |
| [ADR 0002](0002-facility-fixture-identity-and-topology-persistence.md) | Facility fixture identity and minimum topology persistence | Accepted | 2026-07-20 | None |
| [ADR 0003](0003-epistemic-and-human-authority-boundaries.md) | Epistemic and human-authority boundaries | Accepted | 2026-07-22 | None |
| [ADR 0004](0004-flagship-fictional-applicability-profile.md) | Flagship fictional applicability profile and qualitative design intent | Accepted | 2026-07-22 | None |

The index must be updated whenever an ADR is added or changes status.

## Supersession rules

- Never rewrite an accepted ADR to hide a prior decision.
- Create a new ADR that identifies the earlier ADR and explains the replacement.
- Mark the earlier ADR `Superseded` and link the new ADR in both files and in the index.
- Rejected and superseded ADRs remain in the repository as decision history.
- When implementation lags an accepted ADR, [`../PROJECT_STATUS.md`](../PROJECT_STATUS.md) must continue to report actual behavior rather than the intended decision.
- A superseding ADR still cannot conflict with the product charter.

## Consolidated unresolved decision backlog

The following topics are intentionally unresolved. Listing them does not approve a design, schema, requirement, parameter, workflow, or implementation:

1. **Controlled sources, applicability, and requirements:** Milestone 3 implements one bounded flagship representation. Generalized persistence, revision and status history, licensed-source access, clause-level verification, project-effective parameter selection, qualified applicability decisions, and future profile evolution remain unresolved.
2. **Flagship applicability verification and evidence expansion:** ADR 0004 records the fictional location, construction status, research use, occupancy assumption, material and quantity bounds, exclusions, qualitative exhaust intent, and assumed local AHJ. Actual agency jurisdiction, local amendments, enforcement status, control and fire areas, material classification, process-exhaust applicability, and the exact process-enabled context, command/request, VFD, motor, and electrical evidence beyond the accepted Milestone 2 topology remain unresolved.
3. **Canonical observation and temporal semantics:** Source-native preservation, versioned mapping and normalization, units, provenance, observation identity, event/receive/evaluation time, ordering, lateness, staleness, clock limitations, quality, suspect data, override, OOS, persistence, and recovery holds.
4. **Inference and operational vocabularies:** State names, precedence, uncertainty, transition ownership, and mappings among point condition, equipment/system/facility inference, alarm priority, operational risk, consequence, advisory classification, and incident severity.
5. **Evidence sufficiency and outcome structure:** Required-evidence rules, contradiction handling, bounded finding vocabulary, and the internal separation of applicability from evaluation while preserving the working `CONFORMING`, `NONCONFORMING`, `INDETERMINATE`, and `NOT_APPLICABLE` presentation.
6. **Consequence model:** Rule representation, affected scope, assumptions, uncertainty, escalation, recovery, and the boundary between computed consequence and advisory text.
7. **Scenario and replay package:** Versioning, preconditions, source observations, expected inferences and findings, branches, command/request indications, recovery, incomplete recovery, and compatibility across fixtures.
8. **Evidence manifest, retention, and persistence evolution:** Durable identifiers, source manifests, hashes, mapping and rule versions, retained evidence, reset survival, export, tamper-evident metadata, SQLite foreign-key enforcement, migrations, transactions, concurrency, and upgrade behavior.
9. **Human review, test, impairment, recovery, and disposition:** Contextual roles and authority; test authorization; plans, prerequisites, steps, exceptions, aborts, and computed results; impairment and mitigation records; waivers; commissioning acceptance; new recovery evidence; final disposition; and bounded local identity without premature enterprise scope.
10. **Read-only source and comparison contracts:** Allowed adapter capabilities, mapping, provenance, sanitization, error behavior, technical prevention of external writes, and any bounded CDL/CXF or controller-conformance comparison.
11. **Advisory AI boundary implementation:** Evidence citation, uncertainty, prompt and data boundaries, audit, failure behavior, self-approval prevention, and prevention of mutation or exercise of human authority.
12. **Domain validation:** Review scopes and qualified disciplines for fictional facility assumptions, synthetic requirements, evidence needs, pressure relationships, consequences, test content, and recovery criteria.

[ADR 0003](0003-epistemic-and-human-authority-boundaries.md) settles the cross-cutting epistemic and human-authority boundaries. [ADR 0004](0004-flagship-fictional-applicability-profile.md) records the bounded fictional profile and qualitative inactive design intent. Neither resolves the remaining detailed decisions above. The consolidated [PROPOSED—INACTIVE next-review packet](../decision-packets/0001-flagship-observation-and-scenario.md) records recommendations without accepting or activating them.
