# ADR 0001: Minimum flagship topology

- Status: Accepted
- Date: 2026-07-20
- Approver: Daniel Berg
- Supersedes: None
- Superseded by: None

## Context

Milestone 2 requires the minimum fictional flagship catalog and topology needed by the process-exhaust-failure and pressure-cascade-degradation golden scenario. The topology must make point-to-equipment, equipment-to-system, system-to-zone, pressure-boundary, redundancy, shared-path, and minimum supply-dependency relationships explicit before implementation begins.

The planned Advanced Materials Research and Precision-Environment Facility is intentionally broader than the first golden scenario. Implementing the complete representative facility now would add areas, utilities, electrical systems, and precision-environment relationships that are not required to demonstrate the first cascade and would materially expand Milestone 2. Conversely, one room and one boundary are too narrow: they can demonstrate loss of a single pressure relationship, but not a directional cascade through an intermediate zone or progressive degradation from the most negative zone toward a reference area.

The repository currently implements only the fictional Northstar Data Hall. It has no flagship facility, canonical facility topology, process-exhaust model, pressure-cascade model, or higher-level state hierarchy. This ADR proposes a topology decision only. It does not claim implementation or domain validation.

## Decision

If accepted, the first flagship topology will use the following minimum fictional, vendor-neutral entities and relationships. Identifiers below are conceptual labels for the decision; this ADR does not prescribe a storage schema or naming convention for future fixtures.

### Entity inventory

| Conceptual identifier | Entity type | Purpose and boundary |
|---|---|---|
| `ZONE-REFERENCE-CORRIDOR` | Zone | Reference corridor and least-negative zone in this minimum containment-oriented cascade. |
| `ZONE-TRANSITION-AIRLOCK` | Zone | Intermediate transition/airlock zone separating the reference corridor from the process laboratory. |
| `ZONE-PROCESS-LAB` | Zone | Process laboratory, served by process exhaust and represented as the most negative zone. |
| `BOUNDARY-CORRIDOR-TRANSITION` | Directed pressure relationship | Represents intended airflow from the reference corridor toward the transition/airlock. |
| `BOUNDARY-TRANSITION-LAB` | Directed pressure relationship | Represents intended airflow from the transition/airlock toward the process laboratory. |
| `SYSTEM-PROCESS-EXHAUST` | System | Single process-exhaust system serving the process laboratory. |
| `FAN-EXHAUST-DUTY` | Equipment | Duty exhaust fan belonging to the process-exhaust system. |
| `FAN-EXHAUST-STANDBY` | Equipment | Standby exhaust fan belonging to the process-exhaust system. |
| `PATH-EXHAUST-SHARED` | Shared system path | Common exhaust path used by the duty and standby arrangements; it may carry evidence such as airflow, duct static, and relevant damper position. |
| `PERMISSIVE-TREATMENT` | Monitored dependency | Treatment availability or permissive required as monitored evidence for the shared exhaust path; it does not authorize a command. |
| `DEPENDENCY-SUPPLY-MAKEUP` | Monitored dependency | Minimum supply or makeup-air status needed to explain that directional pressure depends on both supply and exhaust. It is not a complete AHU, airflow network, or supply-control sequence. |

### Relationship inventory

| Subject | Relationship | Object | Required meaning |
|---|---|---|---|
| `ZONE-REFERENCE-CORRIDOR` | is upstream side of | `BOUNDARY-CORRIDOR-TRANSITION` | Intended airflow progresses from the corridor toward the transition/airlock. |
| `ZONE-TRANSITION-AIRLOCK` | is downstream side of | `BOUNDARY-CORRIDOR-TRANSITION` | The transition/airlock is intermediate between the corridor and laboratory. |
| `ZONE-TRANSITION-AIRLOCK` | is upstream side of | `BOUNDARY-TRANSITION-LAB` | Intended airflow progresses from the transition/airlock toward the laboratory. |
| `ZONE-PROCESS-LAB` | is downstream side of | `BOUNDARY-TRANSITION-LAB` | The process laboratory is represented as the most negative zone. |
| `FAN-EXHAUST-DUTY` | is equipment member of, role `duty` | `SYSTEM-PROCESS-EXHAUST` | The duty role is topology/configuration data, not an executable control sequence. |
| `FAN-EXHAUST-STANDBY` | is equipment member of, role `standby` | `SYSTEM-PROCESS-EXHAUST` | The standby role is topology/configuration data, not an executable control sequence. |
| `FAN-EXHAUST-DUTY` | uses | `PATH-EXHAUST-SHARED` | Either fan arrangement depends on the common exhaust path. |
| `FAN-EXHAUST-STANDBY` | uses | `PATH-EXHAUST-SHARED` | The shared path makes common evidence and common limitations inspectable. |
| `PATH-EXHAUST-SHARED` | has monitored dependency | `PERMISSIVE-TREATMENT` | Treatment permissive is observed and does not create an external write path. |
| `SYSTEM-PROCESS-EXHAUST` | serves | `ZONE-PROCESS-LAB` | Provides the minimum equipment-to-system and system-to-zone chain. |
| `BOUNDARY-TRANSITION-LAB` | depends on | `SYSTEM-PROCESS-EXHAUST` | The laboratory boundary depends on effective process-exhaust capacity. |
| Both directed pressure relationships | depend on | `DEPENDENCY-SUPPLY-MAKEUP` | Supply or makeup-air status is relevant evidence for both relationships without modeling supply control. |
| `BOUNDARY-CORRIDOR-TRANSITION` | is cascade-upstream of | `BOUNDARY-TRANSITION-LAB` | The two boundaries form one inspectable corridor-to-transition-to-laboratory cascade. |

The model must preserve direction explicitly rather than infer it from zone names. The intended airflow direction progresses from corridor to transition/airlock to process laboratory. This topology does not define numerical pressure bands, tolerances, persistence delays, or recovery hold times.

Duty and standby are descriptive topology roles. The future product may determine whether expected capacity is available from observations, but this ADR does not define a control language, sequence-of-operations engine, fan-start command, automatic transfer behavior, or simulated controller.

### Point categories

Future fixtures for this topology must identify the following observation categories without assigning final thresholds or decision semantics:

- Fan availability.
- Run status.
- Fault status.
- Speed or motor-current evidence.
- Exhaust airflow or duct-static evidence.
- Relevant damper position.
- Treatment permissive.
- Supply or makeup-air status.
- Zone-pressure observations.
- Differential-pressure observations across both boundaries.
- Observation quality and timestamp provenance.

These categories identify the evidence the topology must be able to associate with entities. They do not settle which observations are mandatory, sufficient, conflicting, healthy, late, or authoritative.

### Golden-scenario-phase coverage

| Phase | Topology traversed | Minimum evidence categories | Coverage provided by this decision |
|---|---|---|---|
| Verified baseline | Both fans and shared path; process-exhaust system; both directed boundaries; monitored supply dependency | Availability, run, fault, speed or current, exhaust airflow or duct static, damper position, treatment permissive, supply or makeup-air status, both boundary differentials, quality, and timestamps | Allows future rules to verify exhaust operation and both corridor-to-transition-to-laboratory relationships without defining those rules. |
| Duty-fan loss | Duty fan to process-exhaust system to shared path | Duty run, fault, speed or current, and airflow or duct-static evidence with quality and timestamps | Locates the initiating loss at equipment level while retaining independent evidence of delivered exhaust. |
| Standby path does not restore sufficient exhaust | Standby fan to process-exhaust system and shared path, including treatment permissive | Standby availability, run, fault, speed or current, airflow or duct static, damper position, and treatment permissive | Supports later scenarios in which standby is unavailable, fails to establish flow, or runs without sufficient capacity; no automatic start sequence is assumed. |
| Exhaust capacity becomes insufficient | Both fan memberships, shared path, treatment permissive, and system-to-zone service relationship | Combined fan and shared-path observations with quality and timestamps | Provides the relationship chain needed for a future deterministic system-capacity conclusion without defining state names or thresholds. |
| Cascade degradation | Process-exhaust system to laboratory; transition-to-laboratory boundary followed by possible corridor-to-transition degradation; monitored supply dependency | Zone and boundary differential pressure plus supply or makeup-air and exhaust evidence | Demonstrates progressive loss across two directional relationships instead of treating a single boundary as a cascade. |
| Recovery verification | Restored fan/shared-path evidence, process-exhaust service relationship, and both directed boundaries | Verified exhaust evidence, treatment permissive, supply or makeup-air status, both boundary differentials, quality, and timestamps | Provides the topology needed to require verified exhaust restoration and restoration of both directional relationships; timing and hold criteria remain deferred. |

### Fixture separation and claims

The flagship topology must be a separate fixture and selectable environment from Northstar Data Hall. Northstar remains the implemented legacy fixture, regression environment, and secondary data-center demonstration. Future flagship work must not change Northstar identifiers, inferred topology, seeded behavior, or regression expectations unless separately approved.

All entities and relationships in this ADR are fictional and vendor-neutral. The topology is not domain-validated and makes no containment, cleanroom, industrial-hygiene, regulatory, safety, or commissioning-compliance claim. It is an operational laboratory abstraction, not a physical design or certification.

### Explicitly deferred decisions

This ADR does not decide:

- Point, equipment, system, pressure-cascade, facility, alarm-priority, operational-risk, advisory, or incident-severity vocabularies or precedence.
- Event time, receive time, ordering, late data, staleness, persistence, delays, recovery hold times, or other temporal semantics.
- Numerical pressure bands, airflow or duct-static thresholds, fan-capacity limits, tolerances, or acceptance values.
- Operational consequence rules, affected-scope classification, escalation, or advisory text.
- Durable evidence identifiers, provenance manifests, hashes, retention, reset survival, or export.
- Scenario package schema, versioning, replay identity, branching, observations, or expected-state format.
- Impairment types, authorization, mitigation, compensatory monitoring, expiry, extension, or restoration workflow.
- Functional-test prerequisites, steps, deterministic acceptance, exceptions, abort conditions, or signed recovery.
- Simulated sequence-of-operations logic, controller behavior, automatic duty/standby transfer, control language, or external command execution.
- Adapter contracts, persistence migrations, API representations, or frontend presentation.
- Domain-validation authority or approval of future synthetic values and criteria.

## Consequences

If accepted, this topology gives Milestone 2 a bounded vertical target: three zones, two directed pressure relationships, one process-exhaust system, two role-labelled fans, one shared exhaust path, one monitored treatment permissive, and one minimum monitored supply dependency. It supports a genuine cascade and exposes redundancy and common-path relationships while keeping the fixture small.

Future catalog and topology work will be required to represent explicit direction, equipment membership, duty/standby roles, shared-path use, monitored dependencies, system service, boundary dependency, and fixture identity. Referential-integrity checks will need to reject missing endpoints, invalid role assignments, cross-fixture references, and incomplete relationship chains.

The chosen transition/airlock adds one zone and one boundary beyond the smallest single-room model. That cost is necessary to demonstrate progressive cascade degradation. The topology deliberately cannot represent the broader research facility, detailed supply-air behavior, campus utilities, electrical dependencies, precision environments, or complete process-exhaust treatment train without later approved expansion.

Acceptance of this ADR would authorize the topology decision only. It would not authorize implementation beyond a separately approved roadmap slice, and it would not make any deferred decision implicitly authoritative.

## Alternatives considered

### One process laboratory and one corridor boundary

This is smaller, but it can only demonstrate a single pressure relationship changing. Without an intermediate transition zone and a second directed boundary, there is no observable cascade or progressive degradation toward the reference corridor. It was rejected as too narrow for the golden-scenario commitment.

### Complete representative flagship facility

Modeling all planned laboratories, precision spaces, airlocks, utilities, electrical support, treatment equipment, and dependencies would provide broader demonstration value. It is deferred because most of those entities do not contribute to the first golden scenario and would expand Milestone 2 before the canonical state and temporal decisions exist.

### Single exhaust fan without standby role

This would reduce equipment count but would not exercise the planned distinction among duty availability, standby availability, insufficient restored capacity, and common-path evidence. It was rejected because the golden scenario explicitly needs a failed or insufficient standby response to explain continued degradation.

### Executable supply and duty/standby control model

A simulated AHU, airflow network, automatic transfer sequence, or sequence-of-operations engine could produce richer behavior. It is deferred because the product needs deterministic observation and state semantics before simulated control behavior, and external control remains prohibited.

## Verification and implementation impact

This proposed ADR changes documentation only. No topology, fixture, loader, database schema, API, frontend, scenario, state engine, or test behavior is implemented by it.

If the ADR is later accepted and a separate implementation slice is approved, likely impacts include:

- New versioned flagship catalog and topology fixtures under `data/`, kept separate from Northstar fixtures.
- Explicit zone, system, pressure-boundary, membership, role, shared-path, dependency, and fixture-identity representations in the local SQLite model.
- Loader changes that select and validate a flagship environment without changing Northstar load behavior.
- Query support for the minimum topology and its relationship chains.
- Deterministic fixture-schema, referential-integrity, load, environment-selection, reset, and Northstar regression tests.
- Documentation and `PROJECT_STATUS.md` updates only after behavior has been implemented and verified.

Implementation acceptance would require evidence that all inventory entities and relationships load deterministically, both directed pressure relationships are queryable, invalid or cross-fixture references are rejected, and Northstar behavior remains unchanged. Exact files and schemas remain an implementation decision within the future approved slice.

## References

- [FacilityOps Copilot Product Charter](../PRODUCT_CHARTER.md)
- [FacilityOps Copilot Project Status](../PROJECT_STATUS.md)
- [FacilityOps Copilot Roadmap, Milestone 2](../ROADMAP.md#milestone-2--minimum-viable-flagship-catalog-and-topology)
- [FacilityOps Copilot Architecture](../ARCHITECTURE.md)
- [Planned Flagship Facility](../FLAGSHIP_FACILITY.md)
- [Architecture Decision Records](README.md)
