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

ADRs 0001 through 0006 have been accepted.

| ADR | Title | Status | Date | Approver | Supersedes |
|---|---|---|---|---|---|
| [ADR 0001](0001-minimum-flagship-topology.md) | Minimum flagship topology | Accepted | 2026-07-20 | Daniel Berg | None |
| [ADR 0002](0002-facility-fixture-identity-and-topology-persistence.md) | Facility fixture identity and minimum topology persistence | Accepted | 2026-07-20 | Daniel Berg | None |
| [ADR 0003](0003-epistemic-and-human-authority-boundaries.md) | Epistemic and human-authority boundaries | Accepted | 2026-07-22 | Daniel Berg, Project Owner | None |
| [ADR 0004](0004-flagship-fictional-applicability-profile.md) | Flagship fictional applicability profile and qualitative design intent | Accepted | 2026-07-22 | Daniel Berg, Project Owner | None |
| [ADR 0005](0005-source-native-and-canonical-observation-semantics.md) | Source-native and canonical observation semantics | Accepted | 2026-07-23 | Daniel Berg, Project Owner | None |
| [ADR 0006](0006-synthetic-flagship-replay-and-topology-evolution.md) | Synthetic flagship replay and topology evolution | Accepted | 2026-07-23 | Daniel Berg, Project Owner | None |

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
2. **Flagship applicability verification and later evidence evolution:** ADR 0004 records the fictional profile and qualitative intent. ADR 0006 settles the minimum additive topology `1.1.0` point-definition inventory, owners, typed bindings, and reported-indication categories for the bounded synthetic replay while preserving topology `1.0.0`. Actual agency jurisdiction, local amendments, enforcement status, control and fire areas, material classification, process-exhaust applicability, instrument and source suitability, and any evidence expansion beyond ADR 0006 remain unresolved.
3. **Point condition and criteria beyond accepted observation semantics:** ADR 0005 settles the bounded source-native, canonical, identity, mapping, lineage, event-time/knowledge-time, ordering, conflict, reported-observation projection, and dedicated append-only replay-store semantics. Point-condition logic; evaluation-time semantics; quality, suspect, override, and OOS interpretation; approved lateness, staleness, freshness, persistence, and recovery-hold criteria; clock-sufficiency decisions; and physical or operational inference remain unresolved.
4. **Inference and operational vocabularies:** State names, precedence, uncertainty, transition ownership, and mappings among point condition, equipment/system/facility inference, alarm priority, operational risk, consequence, advisory classification, and incident severity.
5. **Evidence sufficiency and outcome structure:** Required-evidence rules, contradiction handling, bounded finding vocabulary, and the internal separation of applicability from evaluation while preserving the working `CONFORMING`, `NONCONFORMING`, `INDETERMINATE`, and `NOT_APPLICABLE` presentation.
6. **Consequence model:** Rule representation, affected scope, assumptions, uncertainty, escalation, recovery, and the boundary between computed consequence and advisory text.
7. **Inference and evaluation scenarios beyond the accepted observation replay:** ADR 0006 settles the allowlisted synthetic package, pinned mappings and topology, replay-execution identity, reproducibility boundary, structural oracle, and observation-only 23-entry narrative. Expected equipment, system, facility, consequence, or finding outcomes; physical criteria; evidence-sufficiency decisions; scenario branches; recovery and incomplete-recovery evaluation; and cross-fixture inference compatibility remain unresolved. `E230` and `E240` remain non-executed tranche-boundary markers.
8. **Evidence manifest, retention, and persistence evolution beyond the replay store:** ADRs 0005 and 0006 settle immutable observation-replay identities, lineage, content and semantic digests, one-transaction publication, reset-isolated retention, and a bounded reproducibility manifest in the dedicated local replay store. Incident-level evidence manifests linking later inferences, findings, human records, and recovery evidence; retention and export policy; tamper-evident metadata beyond the accepted digests; and broader database migration, transaction, concurrency, and upgrade behavior remain unresolved.
9. **Human review, test, impairment, recovery, and disposition:** Contextual roles and authority; test authorization; plans, prerequisites, steps, exceptions, aborts, and computed results; impairment and mitigation records; waivers; commissioning acceptance; new recovery evidence; final disposition; and bounded local identity without premature enterprise scope.
10. **Read-only source and comparison contracts:** Allowed adapter capabilities, mapping, provenance, sanitization, error behavior, technical prevention of external writes, and any bounded CDL/CXF or controller-conformance comparison.
11. **Advisory AI boundary implementation:** Evidence citation, uncertainty, prompt and data boundaries, audit, failure behavior, self-approval prevention, and prevention of mutation or exercise of human authority.
12. **Domain validation:** Review scopes and qualified disciplines for fictional facility assumptions, synthetic requirements, evidence needs, pressure relationships, consequences, test content, and recovery criteria.

[ADR 0003](0003-epistemic-and-human-authority-boundaries.md) settles the cross-cutting epistemic and human-authority boundaries. [ADR 0004](0004-flagship-fictional-applicability-profile.md) records the bounded fictional profile and qualitative inactive design intent. [ADR 0005](0005-source-native-and-canonical-observation-semantics.md) settles the bounded observation semantics, and [ADR 0006](0006-synthetic-flagship-replay-and-topology-evolution.md) settles the additive reported-indication topology and synthetic observation replay. These decisions do not approve point, equipment, system, or facility inference; physical or temporal criteria; evidence-independence or evidence-sufficiency conclusions; findings; recovery evaluation; or human disposition. The consolidated [PROPOSED—INACTIVE historical packet](../decision-packets/0001-flagship-observation-and-scenario.md) retains the earlier recommendations and identifies the portions superseded by ADRs 0005 and 0006.
