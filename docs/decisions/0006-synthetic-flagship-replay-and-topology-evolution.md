# ADR 0006: Synthetic flagship replay and topology evolution

- Status: Accepted
- Date: 2026-07-23
- Approver: Daniel Berg, Project Owner
- Supersedes: None
- Superseded by: None

## Context

[ADR 0005](0005-source-native-and-canonical-observation-semantics.md)
defines the observation, identity, temporal, mapping, lineage, persistence, and
reported-observation projection boundaries. The flagship topology version
`1.0.0` predates the approved process operating-context, controller request,
controller-reported execution, dedicated VFD-state, motor/electrical-response,
treatment-availability, and delivered makeup-air evidence categories.

The accepted Milestone 3 standards package identifies those missing or partial
point-definition representations but remains bound to topology `1.0.0`,
inactive, and non-executable. The corrected decision packet records a proposed
23-entry evidence sequence. This decision accepts only its received-indication
and recorded-action subset for replay; the proposed evaluation and finding
concepts remain inactive and are not replay events. This decision does not
authorize equipment-state, system-state, facility-state, finding, or recovery
computation.

The project-owner directive dated 2026-07-23 approves the minimum additive
topology, mapping, replay, and reviewer boundaries recorded below. Synthetic
values and timestamps in the package are software fixture data only. They are
not engineering criteria or expected physical response.

## Decision

### Additive topology version

Flagship topology `1.0.0` remains byte-identical and available as the historical
minimum topology. The stable topology identity is
`TOPOLOGY-FLAGSHIP-PROCESS-EXHAUST`; it remains separate from facility, replay,
and mapping identity. A new additive topology package, version `1.1.0`, retains
all existing entities, relationships, point definitions, and typed bindings.
Replay and observation records bind the topology ID, version, and digest over
the exact declared package content rather than a repository path.

Version `1.1.0` adds two equipment records needed to own the new point
definitions without creating placeholder topology entities:

| Equipment ID | Type | Boundary |
|---|---|---|
| `CONTROLLER-PROCESS-EXHAUST` | Process exhaust controller | Owns external controller-reported operating-context and process-permissive indications. FacilityOps has no command or configuration path. |
| `SENSOR-SUPPLY-MAKEUP-AIRFLOW` | Airflow instrument | Owns a reported delivered supply or makeup-air response. |

It adds these twelve point definitions:

| Point-definition ID | Owner | Reported indication |
|---|---|---|
| `PROCESS_ENABLED_STATUS` | `CONTROLLER-PROCESS-EXHAUST` | External controller-reported process-enabled operating context. |
| `PROCESS_PERMISSIVE_STATUS` | `CONTROLLER-PROCESS-EXHAUST` | External controller-reported process permissive. |
| `FAN-EXHAUST-DUTY_REQUEST` | `FAN-EXHAUST-DUTY` | External controller request concerning the duty fan. |
| `FAN-EXHAUST-DUTY_CONTROLLER_EXECUTION_STATUS` | `FAN-EXHAUST-DUTY` | Controller's own execution assertion concerning the duty fan. |
| `FAN-EXHAUST-DUTY_VFD_STATE` | `FAN-EXHAUST-DUTY` | VFD-reported state indication. |
| `FAN-EXHAUST-DUTY_MOTOR_CURRENT` | `FAN-EXHAUST-DUTY` | Reported motor-current indication in amperes. |
| `FAN-EXHAUST-STANDBY_REQUEST` | `FAN-EXHAUST-STANDBY` | External controller request concerning the standby fan. |
| `FAN-EXHAUST-STANDBY_CONTROLLER_EXECUTION_STATUS` | `FAN-EXHAUST-STANDBY` | Controller's own execution assertion concerning the standby fan. |
| `FAN-EXHAUST-STANDBY_VFD_STATE` | `FAN-EXHAUST-STANDBY` | VFD-reported state indication. |
| `FAN-EXHAUST-STANDBY_MOTOR_CURRENT` | `FAN-EXHAUST-STANDBY` | Reported motor-current indication in amperes. |
| `TREATMENT_AVAILABILITY_STATUS` | `MONITOR-TREATMENT` | Reported treatment-availability indication, separate from treatment permissive. |
| `SUPPLY-MAKEUP_AIRFLOW` | `SENSOR-SUPPLY-MAKEUP-AIRFLOW` | Delivered supply or makeup-air response, separate from controller-reported status. |

The process-enabled and process-permissive points bind to
`SYSTEM-PROCESS-EXHAUST`. The treatment-availability point binds to
`PERMISSIVE-TREATMENT`. The delivered makeup-air point binds to
`DEPENDENCY-SUPPLY-MAKEUP`. Fan-owned additions require no new primary binding;
the accepted equipment-system and shared-path memberships provide their
topology context.

The version reuses, without duplication:

- `PROCESS-EXHAUST_AIRFLOW` as the shared delivered process-exhaust indication
  downstream of the duty/standby arrangements and common path. It is one shared
  indication, not a per-fan measurement. It must not be attributed
  independently to the duty fan or standby fan and is not proof that either fan
  delivered airflow.
- `SUPPLY-MAKEUP_STATUS` as the makeup-air controller-reported status.
- The existing run, fault, availability, and speed indications for both fans.
- The existing shared-path, process-laboratory pressure, and two boundary
  differential-pressure indications.

No recovered point, fan-failed point, inferred state point, new zone, system,
pressure boundary, shared path, monitored dependency, or relationship family is
added.

### Additive standards-basis version

The complete `STANDARDS-BASIS-FLAGSHIP-1.0.0` package remains byte-identical. An
additive `STANDARDS-BASIS-FLAGSHIP-1.1.0` package binds the same controlled
profile, sources, applicability bases, qualitative requirements, and evidence
categories to topology `1.1.0`.

The new package updates only package/version bindings and point-definition
representation for the newly available evidence points. Every requirement keeps
its prior lifecycle, approval, activation, parameter, and executable status.
All requirements remain inactive and non-executable, and no numerical criterion
or evaluation rule is added. Observation availability remains
`NO_FLAGSHIP_OBSERVATION_BASELINE` unless a reviewer explicitly selects a
separate synthetic replay execution.

### Versioned synthetic mappings

One repository-versioned mapping package is bound to the exact flagship
facility and topology `1.1.0` digest. Every mapping has an ID, semantic version,
and content digest, and the package pins the canonicalizer implementation
version.

The mappings perform only approved source-representation transformations:

- Direct field selection and boolean normalization for controller indications.
- Direct enum normalization and numeric scaling for VFD snapshots.
- Signed multi-register decoding and declared scaling for motor-current reports.
- Direct numeric parsing and same-dimension unit conversion for process,
  pressure, shared-path, treatment, and makeup-air reports.
- Partial decode that emits observations only for fields actually supplied.

A VFD or process snapshot may produce multiple canonical observations from one
source-native record. A declared pair of high- and low-word register records may
produce one canonical motor-current observation with exact two-record lineage.
Records are combined only through a source-declared decode-group identity and
declared component role, never through receipt adjacency.

Source bindings record known controller, device, gateway, measurement-chain,
power, timestamp, and derivation origins or explicitly record that the
dependency is unknown. They do not assert `independent=true`, count
corroboration, assign weights, or evaluate sufficiency.

### Golden observation replay

The allowlisted repository package is named
`flagship-process-exhaust-evidence-sequence`. It is a synthetic observation
replay, not a failure, changeover, containment, or recovery scenario outcome.

Its manifest pins:

- Package ID, semantic version, and content digest.
- Facility ID.
- Topology ID, version, and content digest.
- Every mapping ID, version, and digest.
- Canonicalizer implementation version.
- Fixed source-event identities, source sessions or boot epochs, sequences,
  source timestamp representations, and virtual receipt times.
- Exact source payloads and source-reported quality.
- Synthetic generator provenance.
- A human-readable structural oracle.

The package manifest declares pinned facility, topology, mapping,
canonicalizer, generator, and replay context separately from narrative events.
The package retains a corrected 20-entry narrative:

1. `E010` through `E170` receive initial, duty-divergence, standby-related,
   dependency, shared-path, and pressure indications.
2. `E180` records only an asserted action and actor/authority context. It does
   not establish authorization, causation, execution, or physical effect.
3. `E190` through `E220` receive new post-action underlying indications.

Recovery evaluation, findings, and human disposition are later capabilities
and are not implemented by this package.

The package and focused mutation tests cover exact redelivery, conflicting
redelivery, equal content under distinct event identities, out-of-order arrival,
missing and invalid source time, source time after receipt, equal source time
with different reports, sequence/time disagreement, declared and ambiguous
sequence reset, mapping-version transition, one-to-many decode, many-to-one
decode, partial decode, repeated replay, restart rebuild, and transaction
failure.

Event and delivery labels describe received indications. The oracle contains
only expected structural counts, identity groups, decode lineage, ordering
facts, and projection dispositions. It contains no equipment, system, facility,
conformance, consequence, safety, authorization, or recovery outcome.

### Replay execution and reproducibility

Each replay execution is an isolated laboratory run with a distinct execution
ID and per-execution delivery IDs. A same-execution retry is idempotent when the
request content matches. A separate execution creates separate run-scoped
records.

Separate executions of the same package must produce equivalent normalized
semantic results and the same normalized semantic digest. The reproducibility
manifest includes package, topology, mapping, canonicalizer, input digest,
derived-record, duplicate/conflict, and projection summaries. It excludes
per-execution random IDs and non-semantic creation timestamps from the semantic
digest.

The manifest hash establishes reproducibility and integrity of the represented
data only. It does not establish authenticity, correctness, applicability,
evidence independence, or physical truth.

### Interface boundary

Bounded APIs and a minimal workbench may:

- Catalog the allowlisted package.
- Start an isolated local replay.
- Inspect package, topology, mapping, delivery, source-native, canonical,
  lineage, redelivery/conflict, projection, and reproducibility records.
- Query the reported-observation projection only with explicit event-time and
  knowledge-time cutoffs.

List APIs use bounded pages and explicit facility filters. Cross-facility
references are rejected. The interface does not accept arbitrary paths, files,
archives, URLs, generic uploads, or live inputs, and it exposes no destructive
observation reset.

The existing standards view continues to say that no observation baseline
exists until a reviewer explicitly selects a synthetic replay execution.

## Consequences

Topology `1.1.0` can represent every approved reported-indication category
without altering the historical topology or creating inferred-state points.
The additive standards package keeps the inactive requirement history intact
while making the new point-definition representation reviewable.

The replay proves deterministic software behavior for one fictional evidence
sequence. It does not prove the fictional sequence is physically accurate, code
compliant, safe, operable, commissioned, or authorized.

Equipment-state inference, standby-changeover determination, system and facility
inference, criteria, findings, evidence sufficiency or independence, human
disposition, and recovery remain outside this decision's implementation scope.

## Alternatives considered

### Add separate duty- and standby-airflow points

Rejected. The accepted topology has one shared process-exhaust airflow
instrument. Duplicating it as fan-specific evidence would invent an unapproved
source or physical interpretation.

### Reinterpret run status as controller execution or speed as VFD state

Rejected. Those indications are distinct evidence categories with distinct
source semantics.

### Modify topology or standards package `1.0.0`

Rejected. Historical package bytes and regression behavior must remain
preserved.

### Encode expected failure, changeover, containment, or recovery outcomes

Rejected. Those are later inference and evaluation decisions, not observation
replay semantics.

## Verification and implementation impact

Implementation requires topology `1.1.0`, standards-basis `1.1.0`, versioned
mappings, the allowlisted replay package, replay validation and execution,
source-native and canonical persistence, exact lineage, bitemporal projection,
reproducibility manifests, bounded APIs, a reviewer workbench, and focused
regression tests.

Verification must prove package and transaction atomicity, deterministic digest
equivalence across executions, restart projection rebuild, facility isolation,
preservation of topology and standards version `1.0.0`, preservation of
Northstar and legacy CSV replay/reset/alarm behavior, and absence of inference
or active requirements.

## References

- [FacilityOps Copilot Product Charter](../PRODUCT_CHARTER.md)
- [FacilityOps Copilot Roadmap, Milestones 4 and 5](../ROADMAP.md#milestone-4--canonical-observations-point-condition-and-temporal-semantics)
- [FacilityOps Copilot Architecture](../ARCHITECTURE.md)
- [Flagship Facility and Golden Proof](../FLAGSHIP_FACILITY.md)
- [ADR 0001: Minimum flagship topology](0001-minimum-flagship-topology.md)
- [ADR 0002: Facility fixture identity and minimum topology persistence](0002-facility-fixture-identity-and-topology-persistence.md)
- [ADR 0005: Source-native and canonical observation semantics](0005-source-native-and-canonical-observation-semantics.md)
- [PROPOSED—INACTIVE observation and scenario packet](../decision-packets/0001-flagship-observation-and-scenario.md)
