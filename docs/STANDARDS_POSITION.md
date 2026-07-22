# FacilityOps Copilot Standards Position

> **Project policy summary — Version 1.0, dated 2026-07-22.** This document summarizes how FacilityOps uses controlled references. It does not replace the detailed dated research baseline, determine legal applicability, reproduce protected standards clauses, or approve a requirement for physical use.

## Detailed dated reference

The complete broad research register reviewed for this rebaseline is preserved as [FacilityOps Standards Baseline, 2026-07-22](references/FacilityOps_Standards_Baseline_2026-07-22.md). The bounded current flagship basis is defined by [ADR 0004](decisions/0004-flagship-fictional-applicability-profile.md) and the [versioned standards-basis manifest](../data/standards/flagship/1.0.0/manifest.json).

That reference is:

- Non-authoritative engineering research for a fictional facility.
- Date-bounded to 2026-07-22.
- Not legal advice, a code analysis for a real project, a design document, a commissioning record, or a determination of safety or compliance.
- Subject to later source verification, licensed-text access, jurisdiction review, domain review, and qualified applicability decisions.

The dated baseline must remain preserved as a historical reference when later research updates the registry. A later reference may supersede its recommendations prospectively but must not silently rewrite the dated record.

## Policy

FacilityOps uses controlled references to make assumptions, applicability, control intent, evidence needs, and limitations visible. It does not attempt to encode every facility code or turn reference documents into executable truth.

Formal standards are one controlled source category. Other possible bases include:

- Laws and regulations.
- Adopted codes, amendments, and enforcement actions.
- Permits, licenses, and consent conditions.
- Owner requirements and project criteria.
- Owner's Project Requirements, Basis of Design, and sequences of operation.
- Manufacturer instructions and equipment requirements.
- Procedures, test plans, and controlled operating documents.
- Project design assumptions.
- Synthetic simulation assumptions.

A source's technical relevance does not establish its legal or project applicability.

## Controlled layers

### 1. Standards Reference Registry

The registry identifies a source without making it executable. A controlled reference should identify, as applicable:

- Publisher and title.
- Publication and edition status.
- Publisher-current edition.
- Jurisdiction-adopted edition.
- Project-effective edition.
- Jurisdiction and adoption path.
- Adoption and enforcement status.
- Scope and applicability trigger.
- Section or clause pointer without reproducing protected text.
- Addenda, errata, interpretations, amendments, enforcement actions, and effective interval.
- Access status and the exact official or licensed text used.

The term “Standards Reference Registry” is retained for consistency with the dated baseline even though the registry may include non-standard controlled source categories.

Milestone 3 implements a bounded form of this layer for one fictional flagship. It is a versioned controlled-source catalog, not a generalized standards database or legal applicability determination.

### 2. Applicable Requirements Baseline

This layer contains requirements deliberately selected or authored for a declared fictional facility, system, equipment item, operating mode, and applicability profile.

Each requirement must identify its basis, rationale, scope, assumptions, exclusions, parameters, effective interval, evidence needs, and approval status. A registry entry does not enter this layer automatically.

Milestone 3 implements a bounded provisional applicability matrix, inactive synthetic requirements, required evidence categories, and visible traceability. It does not implement an applicability-approval workflow, executable parameter set, or status-transition engine.

### 3. Executable Requirements and Tests

This layer contains deterministic evaluations only after applicability, parameter basis, required evidence, evidence-sufficiency behavior, scope, assumptions, and limitations have been defined and approved for the intended laboratory use. It remains unimplemented for the flagship.

Executable code produces a bounded computed finding. It does not produce commissioning acceptance, a safety determination, a waiver, or authorization for physical operation.

## Assurance lifecycle

```text
reference source
→ applicability decision
→ versioned requirement
→ required evidence
→ deterministic evaluation
→ bounded finding
→ evidence manifest
→ human review and disposition
```

The project must keep source requirements, owner or project requirements, synthetic simulation requirements, executable rules, computed findings, and qualified human disposition distinct.

## First golden proof

The first golden proof uses project-authored synthetic sequence-of-operation requirements informed by controlled references. The current ten recorded requirements are qualitative, `ACCEPTED_FOR_SIMULATION`, `INACTIVE`, and non-executable. Two additional project drafts remain `DRAFT`, `PROPOSED`, and `INACTIVE`.

It must not characterize duty/standby redundancy, controller response, pressure criteria, airflow thresholds, timers, treatment dependencies, makeup-air relationships, or recovery intervals as directly code-required unless a later qualified applicability decision establishes that basis.

[ADR 0004](decisions/0004-flagship-fictional-applicability-profile.md) records these fictional profile facts: a new, privately operated, one-story, sprinklered research facility in the Town of Horseheads outside incorporated villages and New York City; an assumed Town code-enforcement AHJ and Group B research-laboratory use; bench-scale alumina-based ceramic powder and sintered specimens; a 250 g maximum open batch and 5 kg maximum closed-container inventory; the stated excluded hazards; and qualitative pressure-direction, process-exhaust, treatment, duty/standby, shared-path, and makeup-air intent.

Those facts do not resolve the following legal, regulatory, or technical verification gaps:

- Real parcel and agency jurisdiction, intermunicipal arrangements, local amendments, enforcement status, and permit responsibility.
- Legal occupancy classification, construction and sprinkler determinations, control areas, fire areas, and hazardous-material thresholds.
- Supplier SDS, CAS identity, composition and additives, particle-size distribution, silica content, exposure assessment, and industrial-hygiene basis.
- Whether hazardous, laboratory, or other process-exhaust provisions apply to a real design.
- Project-specific OPR, BOD, SOO, manufacturer, procedure, test, commissioning, parameter, and instrument bases.

The current profile, topology, and requirements remain fictional laboratory abstractions.

## Requirement statuses

The working statuses `DRAFT`, `ACCEPTED_FOR_SIMULATION`, `DOMAIN_REVIEWED`, and `RETIRED` apply only to individual controlled requirements.

- `DRAFT` indicates incomplete project-authored intent not authorized for deterministic scenario evaluation.
- `ACCEPTED_FOR_SIMULATION` means only that a synthetic requirement has a recorded project decision for the fictional laboratory. It does not activate the requirement; every current requirement remains `INACTIVE` and non-executable.
- `DOMAIN_REVIEWED` indicates a bounded review by a stated domain role against a stated scope. It does not imply code compliance, commissioning acceptance, owner approval, safety, or authorization for physical operation.
- `RETIRED` means the requirement is no longer used prospectively; its historical versions and linked evidence remain traceable.

These terms do not apply to topology, source references, standards, fixtures, ADRs, computed findings, or human dispositions. The bounded package validates its declared status fields but implements no status-transition engine or universal transition model.

## Evaluation outcomes and insufficient evidence

The working external outcome presentation is:

- `CONFORMING`
- `NONCONFORMING`
- `INDETERMINATE`
- `NOT_APPLICABLE`

Missing, stale, suspect, overridden, late, or conflicting required evidence must be capable of producing `INDETERMINATE`. Deterministic evaluation must not force a binary result when the declared evidence basis is insufficient.

The internal separation of applicability decisions from evaluation results remains unresolved and requires a later ADR. These outcome labels do not themselves define a persistence schema or generalized conformance language.

## Authority boundary

Deterministic code owns reproducible computation. It produces computed point conditions, inferred states, timing results, replay outputs, evaluations, and bounded findings under identified inputs, assumptions, configuration, and rules. Determinism provides reproducibility, not automatic validity.

Qualified personnel retain authority for applicability decisions, requirement approval, test authorization, operational action, commissioning acceptance, waivers, and final disposition. AI may assist with drafting and explanation but must not approve its own output or serve as the safety authority.

## Source access and protected text

- Use official or properly licensed text for clause-level research.
- Preserve precise citations, edition details, access status, and section pointers.
- Do not copy protected standards clauses or large excerpts into repository documents or data.
- Do not infer clause content from titles, summaries, or secondary descriptions when an executable abstraction depends on exact wording.
- Record project-authored paraphrases as project content, not as quoted source requirements.

## Decisions deferred beyond Milestone 3

- Generalized or persistent registry, applicability, requirement, evidence, revision-history, and licensed-text architecture.
- Status-transition roles and permissions.
- Profile-revision governance and verified legal applicability.
- Clause-level abstractions and parameter selection.
- Evidence-sufficiency algorithms and internal outcome structure.
- Command/request, VFD, motor, and electrical point or topology expansion.
- Finding, review, waiver, and final-disposition persistence.
- Evidence manifests, hashes, retention, and export format.
- Optional CDL/CXF or controller-conformance comparison.

See [Architecture Decision Records](decisions/README.md) for the consolidated decision backlog.
