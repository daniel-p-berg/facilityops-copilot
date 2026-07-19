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

No ADRs have been accepted yet.

| ADR | Title | Status | Date | Supersedes |
|---|---|---|---|---|
| — | — | — | — | — |

The index must be updated whenever an ADR is added or changes status.

## Supersession rules

- Never rewrite an accepted ADR to hide a prior decision.
- Create a new ADR that identifies the earlier ADR and explains the replacement.
- Mark the earlier ADR `Superseded` and link the new ADR in both files and in the index.
- Rejected and superseded ADRs remain in the repository as decision history.
- When implementation lags an accepted ADR, [`../PROJECT_STATUS.md`](../PROJECT_STATUS.md) must continue to report actual behavior rather than the intended decision.
- A superseding ADR still cannot conflict with the product charter.

## Unresolved architectural decisions

The following topics are intentionally unresolved. Listing them does not approve a design:

1. **Operational vocabularies:** Separate models and mappings for alarm priority, point condition, operational risk, advisory classification, and incident severity.
2. **Canonical state hierarchy:** State names, precedence, uncertainty, and transition ownership for point, equipment, system, and facility layers.
3. **Temporal semantics:** Event time versus receive time, ordering, late data, persistence, staleness, hold times, and replay clocks.
4. **Facility topology:** Representation of zones, pressure boundaries, airflow direction, equipment membership, redundancy, shared capacity, and dependencies.
5. **Consequence model:** Rule representation, affected scope, uncertainty, escalation, recovery, and the boundary between consequence and advisory text.
6. **Evidence and provenance:** Durable identifiers, source manifests, hashes, rule versions, retention, export, and tamper-evident metadata.
7. **Reset semantics:** Which active laboratory records reset may clear and which provenance or incident evidence must survive.
8. **Scenario package format:** Versioning, preconditions, observations, expected states, branches, recovery, and compatibility across fixtures.
9. **Impairment workflow:** Types, authorization records, mitigations, extensions, compensatory monitoring, expiry, and restoration criteria.
10. **Functional-test model:** Plans, prerequisites, steps, observations, deterministic acceptance, exceptions, aborts, recovery, and evidence.
11. **Read-only adapter contract:** Allowed capabilities, mapping, provenance, sanitization, error behavior, and technical prevention of external writes.
12. **Persistence evolution:** SQLite foreign-key enforcement, migration strategy, transaction boundaries, concurrency, and evidence retention.
13. **Identity and authorization:** Local actor identity now and any future multi-user roles, without expanding into enterprise identity prematurely.
14. **Advisory AI boundary:** Evidence citation, uncertainty, prompt and data boundaries, audit, failure behavior, and prevention of authoritative mutation.
15. **Domain validation:** Approval process for synthetic facility assumptions, pressure relationships, operational consequences, and functional-test criteria.
