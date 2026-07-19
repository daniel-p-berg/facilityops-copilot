# FacilityOps Copilot Product Charter

> **Change-controlled document — Version 1.0, approved 2026-07-19.** This charter describes the approved intended product. It may not be changed in a future task without explicit user approval for the charter change.

## Purpose

FacilityOps Copilot is a vendor-neutral, read-only critical-environment operations, commissioning, training, and decision-support laboratory.

It imports, replays, or simulates facility data; determines point, equipment, system, and facility state; identifies operational consequences; supports operator response, impairment management, functional testing, recovery, and incident review; and produces auditable evidence.

The product exists to make facility behavior, operational risk, response decisions, and supporting evidence understandable and reproducible in a safe laboratory. AI-assisted development is part of project history, not the product mission.

This charter defines the intended product. It does not assert that every capability is currently implemented. Current verified behavior is maintained separately in [`PROJECT_STATUS.md`](PROJECT_STATUS.md).

## Intended users

- Critical-environment operators and shift leads reviewing alarms, impairments, recovery, and turnover risk.
- Controls and integration technicians validating point mappings and deterministic behavior.
- Commissioning personnel planning, executing, and reviewing functional tests.
- Facility engineers and reliability personnel investigating dependencies and operational consequences.
- Instructors and trainees rehearsing response and recovery in a fictional environment.
- Reviewers who need traceable evidence for how a conclusion or action was reached.

## Intended outcomes

- Facility data can be safely imported, replayed, or simulated without controlling an external facility.
- Point observations can be translated into explicit equipment, system, and facility state.
- Operators can see what happened, what is affected, why it matters, what evidence supports the conclusion, and what uncertainty remains.
- Alarm response, impairment, functional testing, recovery, and incident-review activities can be rehearsed and reviewed reproducibly.
- Authoritative determinations are explainable, deterministic, testable, and auditable.
- Advisory AI, when introduced, adds interpretation without replacing deterministic authority.

## Product principles

### Read-only toward external facilities

Read-only means FacilityOps Copilot must never issue a command, make a configuration change, or write back to an external BAS, EPMS, PLC, SCADA, DCIM, or physical facility system.

Local laboratory writes are allowed. These include simulated samples, imported catalogs, scenarios, alarm rules, acknowledgements, audit records, functional-test results, and local configuration. Local writes must remain distinguishable from source observations and must not create an external control path.

### Deterministic authority

Deterministic code, not AI, owns alarm state, point condition, equipment and system state, operating modes, consequence rules, functional-test acceptance, and other authoritative determinations. Rules and transitions must be testable and their inputs and outputs must be reviewable.

AI is a future advisory layer. It may summarize, explain, compare, or help users navigate evidence, but its output must be labeled advisory and traceable to authoritative data and rules.

### Evidence before assertion

Operational conclusions must identify their inputs, applicable rules, state transitions, timestamps, provenance, and uncertainty. Clearing active laboratory state must not destroy durable provenance or incident evidence in the intended product.

### Vendor-neutral core

The canonical facility, point, state, consequence, workflow, and evidence models must not depend on a single control-system vendor. Protocol- or vendor-specific adapters translate into the canonical model rather than redefining it.

### Safe and truthful data use

Current repository fixtures are fictional. Future ingestion may use synthetic, sanitized, non-sensitive, or explicitly authorized read-only data. Credentials, customer data, proprietary exports, real facility network information, and confidential configurations must never be committed.

### Scenario-driven verification

Important behavior is developed through small, repeatable scenarios with defined preconditions, observations, expected transitions, consequences, recovery criteria, and evidence.

### Explicit uncertainty and vocabulary

The product must not silently equate alarm priority, point condition, operational risk, advisory classification, and incident severity. Their vocabularies and relationships remain an open architectural decision until explicitly approved.

## Product boundaries

The intended product may:

- Import static catalogs and authorized read-only observations.
- Replay recorded or synthetic sequences.
- Simulate point observations and local operating conditions.
- Maintain local scenario, workflow, test, acknowledgement, and audit state.
- Determine point, equipment, system, and facility state through deterministic logic.
- Determine operational consequences and required verification through deterministic rules.
- Support human decisions with procedures, evidence, context, and future advisory AI.
- Export or present auditable laboratory evidence.

The intended product must not create a control path to an external facility.

## Non-goals

FacilityOps Copilot is not:

- A replacement BAS, EPMS, PLC, SCADA, DCIM, or autonomous controller.
- An autonomous operator or a system authorized to execute physical actions.
- A complete CMMS, work-order, document-control, or enterprise asset-management platform.
- A generic chatbot detached from facility evidence and deterministic state.
- A high-fidelity physics, airflow, process, electrical-transient, or computational-fluid-dynamics simulator.
- A regulatory compliance engine or a guarantee of cleanroom, containment, safety, or commissioning compliance.
- A repository for real customer secrets, credentials, proprietary exports, or confidential facility configurations.

## Preservation constraints

Useful implemented foundations must be preserved while the product is reoriented:

- Deterministic alarm evaluation and lifecycle logic.
- The point catalog and current-value projection.
- Point-sample history, current-value projection, and point-health concepts.
- Static Modbus-map preview and import.
- Deterministic CSV replay and simulated reads.
- Scenarios and operational reset.
- Generated-alarm acknowledgement and audit events.
- Existing tests and the Northstar Data Hall fixture.

Northstar Data Hall remains an implemented legacy fixture, regression environment, and secondary data-center demonstration. It is not the flagship environment.

Preservation does not mean that every existing behavior is target-complete. In particular, current operational reset deletes generated alarms and audit events. The intended direction is to clear active laboratory state without destroying durable provenance or incident evidence, but that change requires a future approved roadmap slice.

## Flagship commitment

The planned flagship is a fictional **Advanced Materials Research and Precision-Environment Facility**. It will provide a richer environment for process exhaust, pressure relationships, precision environmental control, utilities, electrical support, commissioning, impairment, response, and recovery.

The flagship is planned and is not implemented at charter version 1.0. Its current target description is in [`FLAGSHIP_FACILITY.md`](FLAGSHIP_FACILITY.md).

## Golden-scenario commitment

The planned first golden scenario is a **process-exhaust failure causing pressure-cascade degradation**. It will be developed as a deterministic, evidence-producing scenario with explicit preconditions, observations, equipment and system state, operational consequences, response, impairment, functional verification, recovery, and incident review.

The golden scenario is planned and is not implemented at charter version 1.0.

## Change control

- This approved version is 1.0, dated 2026-07-19.
- Future tasks may not edit this file without explicit user approval that specifically authorizes a product-charter change.
- A proposed charter change must identify the exact text or policy being changed, the reason, affected boundaries and roadmap milestones, and compatibility with preservation constraints.
- Charter changes must not be inferred from ordinary implementation, documentation, refactoring, or roadmap-progress requests.
- Architecture decision records may clarify implementation choices but cannot override this charter.
- [`PROJECT_STATUS.md`](PROJECT_STATUS.md) and [`ARCHITECTURE.md`](ARCHITECTURE.md) may evolve as behavior changes, provided they continue to distinguish verified reality from intended direction.
