# ADR 0005: Source-native and canonical observation semantics

- Status: Accepted
- Date: 2026-07-23
- Approver: Daniel Berg, Project Owner
- Supersedes: None
- Superseded by: None

## Context

FacilityOps needs a durable observation boundary before it can infer point,
equipment, system, pressure-cascade, or facility conditions. The accepted
architecture distinguishes a source report from every later computation:

```text
source delivery
→ source-native record
→ versioned mapping and normalization
→ canonical observation
→ reported-observation projection
```

The existing Northstar `point_samples` and `current_point_values` behavior is a
compatibility path. It does not preserve all source-native payloads, delivery
identities, mapping versions, redelivery conflicts, or bitemporal reconstruction
required by the flagship proof. Existing operational reset also deletes those
legacy runtime records.

The project-owner directive dated 2026-07-23 approves the identity, temporal,
canonicalization, projection, persistence, and read-only inspection boundaries
recorded below. This decision does not approve point-condition logic, physical
criteria, evidence-sufficiency rules, or higher-level inference.

## Decision

### Record and identity boundaries

FacilityOps will keep these identities distinct:

1. Replay package ID, semantic version, and content digest.
2. Replay execution ID.
3. Per-execution delivery ID.
4. Request idempotency key.
5. Source-event identity, when the source supplies one.
6. Immutable source-native record ID.
7. Immutable canonical-observation ID.
8. Mapping ID, semantic version, and content digest.
9. Canonicalizer implementation version.
10. Topology ID, version, and content digest.

A delivery represents one receipt by FacilityOps. A source-event identity is an
identity asserted by a source within its declared namespace. A canonical
observation is a derived normalized report. These records do not establish
physical equipment, system, or facility state.

Every new evidence record is facility-bound and source-bound. Synthetic replay
records are also replay-execution-bound and explicitly synthetic. Accepted
deliveries, source-native records, canonical observations, and lineage records
are append-only. A correction, reinterpretation, or new mapping creates a new
record or derivation and does not update prior evidence in place.

### Delivery, retry, and source-event behavior

A delivery ID is unique within one replay execution. A request idempotency key
identifies a retry and is not a source-event identity.

- Reusing an idempotency key with byte-equivalent normalized request content
  returns the original accepted result.
- Reusing an idempotency key with different request content is rejected.
- A source-event identity is namespaced by facility, source, channel, and a
  source session or boot epoch when one is declared.
- The same source-event identity with identical source payload and material
  source metadata is an exact redelivery. Every delivery and source-native
  record remains retained, but the logical variant is canonicalized only once
  within that execution.
- The same source-event identity with different payload or material source
  metadata is an unresolved conflicting redelivery. Every delivery, native
  record, and canonical variant remains retained. FacilityOps does not select a
  winner.
- Equal content under different source-event identities represents distinct
  source events.
- If the source supplies no stable event identity, FacilityOps does not infer
  identity from a value, timestamp, sequence-free content digest, or payload
  equality.
- A sequence reset without a declared session or boot epoch remains ambiguous.

A content digest establishes byte integrity and repeatability for the represented
content. It does not establish authenticity, correctness, independence, or
physical truth.

### Source-native records

An immutable source-native record preserves:

- The exact source payload or exact repository fixture representation and its
  digest.
- Source-event identity, source sequence, and session or boot epoch when
  supplied.
- Original source timestamp text, timezone offset, and precision when supplied.
- Source-reported quality fields without silently translating their meaning.
- Source, channel, transport, and synthetic provenance.
- Facility, mapping, topology, replay package, and replay-execution bindings.
- FacilityOps receipt time.
- A deterministic database ingestion ordinal.

Receipt-specific metadata is not used to rewrite source metadata. Exact
redelivery and conflict classification remains inspectable.

### Temporal semantics

`observed_at` is the time at which the source asserts that the report occurred.
`received_at` is the time at which FacilityOps accepted a complete delivery. A
repository-only synthetic replay uses the package's explicit virtual receipt
clock.

FacilityOps will:

- Preserve original timestamp text, offset, and precision separately from the
  normalized timestamp.
- Normalize a valid timestamp to UTC.
- Keep missing or invalid `observed_at` explicit and never substitute
  `received_at`.
- Treat `received_at` as a knowledge-time fact, not proof of physical event
  order or causation.
- Compare a source sequence only inside its declared source namespace and
  session or boot epoch.
- Expose a sequence/timestamp disagreement instead of selecting one silently.
- Factually identify an out-of-order arrival when the declared source order or
  valid event time shows that relationship.
- Avoid the term `late` unless a future approved lateness basis exists.

No staleness, freshness, persistence, recovery-hold, validity, or
allowed-lateness threshold is approved by this decision.

Queries preserve two explicit cutoffs:

- `as_of_observed_at` reconstructs source reports whose valid event times are at
  or before the event-time cutoff.
- `known_by_received_at` reconstructs what FacilityOps had accepted by the
  knowledge-time cutoff.

A later delivery may change a later retrospective event-time view. It must not
rewrite the result for an earlier knowledge-time cutoff. Tests and synthetic
replays use explicit clocks and do not use wall-clock time to determine results.

### Canonical observations and mappings

A canonical observation contains:

- Canonical point-definition ID.
- One typed normalized value and a unit when applicable.
- Normalized `observed_at` when valid and explicit time-basis metadata.
- Source-quality provenance without an unapproved quality interpretation.
- Mapping ID, version, and digest.
- Canonicalizer implementation version.
- Synthetic provenance.
- Exact lineage to one or more source-native records and source fields.

Lineage supports one native record producing multiple canonical observations,
multiple native records decoding one source-reported value, and partial decode
without inventing an absent field. Reprocessing with another mapping produces a
separate derivation.

An approved synthetic mapping may perform parsing, field selection, type
normalization, direct enum normalization, explicit same-dimension unit
conversion, and combination of source fields or registers required to decode one
reported value. It may not infer operation, failure, successful execution,
changeover, airflow or treatment sufficiency, pressure-cascade adequacy,
containment, recovery, conformance, safety, operability, or authorization.

Every replay delivery pins one exact mapping ID, version, and digest. There is no
implicit current mapping. Reusing a mapping ID and version with a different
digest is rejected.

### Reported-observation projection

The rebuildable projection is scoped by facility, replay execution,
source/channel binding, canonical point, and mapping derivation. Different
source bindings are not merged into an authoritative value.

Every query requires both explicit time cutoffs. Selection follows these rules:

- Exact redelivery does not create another logical candidate.
- A valid older event received after a valid newer event does not displace the
  newer event.
- A future event relative to `as_of_observed_at` is ineligible.
- A delivery accepted after `known_by_received_at` is ineligible.
- Missing or invalid event order remains visible and is not promoted by receipt
  order or database identity.
- Equal-order candidates with materially different reports are unresolved.
- A conflicting latest source-event identity is unresolved and has no selected
  scalar value.
- A latest unresolved conflict or unordered candidate does not cause silent
  fallback to an older report.
- A sequence/timestamp disagreement remains unresolved.

Projection dispositions use ingestion-specific terms such as
`NO_OBSERVATION`, `NO_ELIGIBLE_REPORT`, `REPORTED`, `CONFLICT_PRESENT`, and
`UNORDERED`. They do not describe equipment state, success, failure,
conformance, safety, or recovery.

### Persistence and reset isolation

The new observation model uses typed relational SQLite tables with declared and
enabled foreign keys, uniqueness constraints, bounded payloads, bounded list
pages, and immutable-record triggers. A replay is completely validated and
canonicalized before its records become visible. One explicit transaction
publishes an execution; malformed input or an injected failure exposes no
partial execution.

The append-only evidence tables use a dedicated local observation-replay
database rather than the legacy operational database. Application import does
not create or mutate this store. Only an explicit local synthetic replay creates
it. The existing operational reset neither opens nor deletes records from it.
This isolation is laboratory evidence retention for this tranche, not the
complete incident-retention architecture planned later.

Only allowlisted repository-versioned packages may execute. FacilityOps will not
accept arbitrary package paths, archives, URLs, generic uploads, or live
facility ingestion through this interface. No destructive reset endpoint is
provided.

### Provenance dependency metadata

Records may capture possible common upstream controller, gateway, device, power,
timestamp, and derivation origins. Unknown dependency remains unknown. This
tranche does not emit an independence conclusion, count corroborating evidence,
weight evidence, or evaluate sufficiency.

## Consequences

The model preserves delivery audit, exact source representation, deterministic
normalization, conflicts, bitemporal reconstruction, and projection rebuild
without changing legacy Northstar observation or alarm behavior.

The separate append-only store adds explicit schema and query work. It also
prevents legacy operational reset from deleting the new evidence and prevents a
flagship synthetic replay from contaminating the normal Northstar database.

Canonical observations and reported-observation projections remain evidence
views. Equipment state, system state, facility state, findings, consequences,
human disposition, and recovery evaluation remain later decisions.

## Alternatives considered

### Extend `point_samples` and `current_point_values`

Rejected for this tranche. Those tables implement legacy arrival-oriented
runtime behavior, are deleted by operational reset, and do not carry the
approved delivery, source-event, mapping, lineage, or bitemporal boundaries.

### Deduplicate by content digest

Rejected. Equal content does not prove equal source-event identity, and a digest
does not establish authenticity or physical truth.

### Select a conflict winner by receipt time or database ID

Rejected. Those tie breakers would silently create an evidentiary decision that
the project owner has not approved.

### Merge all sources into one current value

Rejected. No cross-source precedence or authority rule is approved.

## Verification and implementation impact

Implementation requires repository package validation, mapping validation,
append-only schema initialization, delivery and redelivery classification,
canonicalization, exact lineage, bitemporal projection, reproducibility
manifests, bounded APIs, a reviewer workbench, and deterministic tests for the
approved edge cases.

Verification must use fresh temporary databases, prove atomic rollback and
restart rebuild, preserve Northstar and alarm regressions, and confirm that the
normal ignored database remains unchanged.

## References

- [FacilityOps Copilot Product Charter](../PRODUCT_CHARTER.md)
- [FacilityOps Copilot Roadmap, Milestones 4 and 5](../ROADMAP.md#milestone-4--canonical-observations-point-condition-and-temporal-semantics)
- [FacilityOps Copilot Architecture](../ARCHITECTURE.md)
- [Flagship Facility and Golden Proof](../FLAGSHIP_FACILITY.md)
- [ADR 0003: Epistemic and human-authority boundaries](0003-epistemic-and-human-authority-boundaries.md)
- [PROPOSED—INACTIVE observation and scenario packet](../decision-packets/0001-flagship-observation-and-scenario.md)
