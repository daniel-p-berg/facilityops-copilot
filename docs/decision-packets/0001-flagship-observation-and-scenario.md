# PROPOSED—INACTIVE: Flagship Observation, Evidence, and Golden-Scenario Decision Packet

- Status: **PROPOSED—INACTIVE**
- Date: 2026-07-22
- Facility binding: `FACILITY-ADVANCED-MATERIALS-RESEARCH`
- Current topology fixture: `1.0.0`, unchanged
- Normal application loading: **Excluded**
- Executable mappings, requirements, inference, evaluation, or control behavior: **None**

This packet consolidates decisions needed before Milestones 4 and 5. It is a review artifact, not an ADR, requirement, mapping, parameter set, fixture, scenario package, or authorization to implement later inference or evaluation. It is not loaded by normal application behavior and changes no database, topology fixture, alarm behavior, replay behavior, or external-system boundary.

Any future topology change requires a separate proposed ADR and explicit acceptance. Candidate point identifiers, semantics, scenario events, and parameter topics below remain inactive until the appropriate decision and review are complete. FacilityOps remains read-only toward external systems.

## Accepted boundaries carried forward

This packet is subordinate to [ADR 0001](../decisions/0001-minimum-flagship-topology.md), [ADR 0002](../decisions/0002-facility-fixture-identity-and-topology-persistence.md), [ADR 0003](../decisions/0003-epistemic-and-human-authority-boundaries.md), and [ADR 0004](../decisions/0004-flagship-fictional-applicability-profile.md).

- A source-native or canonical observation is a reported indication within its quality, timing, mapping, and transformation limits. It does not independently prove physical state.
- A controller request or controller-reported execution indication is evidence only. FacilityOps does not issue the request or command.
- A recorded human action is not evidence of its physical effect. Recovery requires new post-action observations and a separate evaluation.
- The current Northstar arrival-order projection is a preserved compatibility behavior, not the proposed flagship observation model.
- The ten qualitative flagship requirements remain `ACCEPTED_FOR_SIMULATION`, `INACTIVE`, and non-executable. The two additional requirements remain `DRAFT`, approval status `PROPOSED`, activation status `INACTIVE`, and non-executable.

## Proposed source-native and canonical boundaries

### Source-native observation

A source-native observation should be immutable and retain the source representation needed to reconstruct what FacilityOps received:

- Source artifact or stream identifier and version.
- Source point, address, register, field, or object reference.
- Raw value, raw type, raw quality or status, raw unit where present, and raw timestamp representation.
- Source event identifier or sequence, sequence scope, and source epoch where supplied.
- First `received_at` assigned by FacilityOps.
- Protocol or adapter identity and version.
- Payload hash for conflict detection, not as the sole observation identity.
- Synthetic lineage when the record was generated or replayed.

The source-native record should not silently repair units, timestamps, quality, sign, orientation, or vocabulary. A later mapping may interpret those fields without replacing the original record.

### Canonical observation

A canonical observation should be an immutable, reproducible derivation linked to exactly one source-native observation. It should retain:

- Canonical point identifier.
- Mapping identifier, version, and content hash.
- Normalized value, quantity kind, unit, and explicit quality flags.
- `observed_at`, `received_at`, clock basis, and known time uncertainty.
- Transformation steps and synthetic provenance.
- A direct reference to the source-native record.

Normalization may perform a declared type conversion, unit conversion, quality mapping, or sign/orientation mapping. Computation that combines multiple observations belongs in a later point-condition or inference layer, not canonical normalization.

## Proposed temporal semantics

- `observed_at` is the source's claim for when the indication applied. It may be null or uncertain. FacilityOps should preserve the raw source timestamp, clock identifier, timezone or offset, precision, and uncertainty rather than inventing event time.
- `received_at` is the time FacilityOps first accepts the complete source-native record. FacilityOps assigns it; it must not be copied from `observed_at`.
- `evaluation_at` is a separate deterministic computation time and must not overwrite either observation timestamp.
- Synthetic replay should use a declared deterministic virtual clock and must remain labeled synthetic.
- Serialized timestamps should use timezone-aware RFC 3339 values, normally normalized to UTC while preserving raw source representation.
- Cross-source event-time comparison is unsupported when clock basis, synchronization, precision, or uncertainty is insufficient.

No allowed-lateness, staleness, persistence, or recovery interval is proposed in this packet.

## Proposed identity, duplicate, late, and out-of-order handling

### Idempotency identity

The preferred identity order is:

1. A source event identifier when the source contract guarantees its uniqueness and scope.
2. `(source_stream_id, source_epoch, source_sequence)` when the stream defines epoch and sequence semantics.
3. `(scenario_package_id, replay_run_id, event_id)` for deterministic synthetic replay.

If a source provides no stable identity, FacilityOps should retain separate deliveries. Identical content alone must not be treated as proof that two deliveries represent one source event.

### Duplicate and identity conflict

- Same idempotency key and identical source payload: retain duplicate-delivery metadata, do not create another canonical observation, and do not update the current-value projection.
- Same idempotency key and different payload: quarantine as an identity conflict, preserve both deliveries for review, expose the conflict on any current projection that references that identity, and make source selection and evidentiary support unresolved until the conflict is dispositioned. Do not project either conflicting replacement automatically.
- A payload hash may detect equality or conflict but does not replace the scoped idempotency identity.

### Sequence, lateness, and ordering

- Preserve source sequence exactly and compare it only within its declared stream and epoch.
- Retain an observation received after a newer sequence or trusted event time; label the ordering relationship rather than discarding the record.
- A late classification requires an approved lateness budget and time basis. Until then, lateness remains unresolved.
- Sequence gaps, source restarts, epoch changes, and incomparable streams remain explicit.
- Do not reuse Northstar's current staleness behavior as a flagship lateness or ordering rule.

## Proposed mapping version and synthetic provenance

- Mapping changes apply prospectively and never rewrite source-native history.
- Re-normalization under a new mapping creates a new canonical derivation linked to the same source-native observation.
- A mapping record should identify source schema or profile version, source field, target point, transformation version, source and target units, sign/orientation, quality mapping, effective interval, review status, and content hash.
- Synthetic records should identify generator ID and version, scenario ID and version, event ID, replay-run ID, source fixture version, mapping version, and random seed if randomness is later permitted.
- Synthetic evidence must never be presented as received field evidence.
- An AI-drafted mapping remains proposed and inactive until a qualified person and the project owner complete the required review and approval.

## Proposed current-value projection rules

The current-value projection should be rebuildable convenience state, not durable evidence.

- The projection references the selected canonical observation; it does not copy away provenance.
- Each mapping declares one ordering mode: `SOURCE_SEQUENCE`, `OBSERVED_AT`, or `RECEIVED_AT`.
- There is no implicit fallback between incomparable time or sequence bases.
- Duplicate, conflicting, or older out-of-order observations do not replace the selected current observation. A selected observation whose identity becomes conflicted cannot silently remain eligible to support a conclusion.
- Quality, suspect, override, out-of-service, late, stale, duplicate, and identity-conflict conditions remain visible on the selected indication. An older good-quality value must not silently replace a newer insufficient indication.
- Staleness is computed at evaluation time from an approved category-specific limit and declared time basis.
- Multiple sources mapped to one point require an explicit selection or precedence rule. Without one, projection is unresolved.
- These rules must not retrofit or change preserved Northstar behavior without a separate compatibility decision.

## Proposed evidence-independence rules

- Different point IDs, API fields, protocols, or displays do not establish independent evidence.
- Evidence counts as independent only when the requirement calls for distinct categories and provenance identifies distinct immediate source or measurement chains.
- Controller request and controller-reported execution from the same controller are not independent.
- A BAS run-status field derived from a VFD register is not independent of that VFD indication.
- VFD state and VFD-reported motor current are not independent.
- Independently measured motor current can supply a distinct motor/electrical evidence category for a later fan-operation inference. It does not validate the truth of a VFD-state indication.
- Delivered airflow can supply a distinct delivered-response category for a later fan-operation or system-response inference when the airflow instrument, source chain, and transformation lineage are distinct. It does not validate the truth of a fan indication.
- Derived copies inherit all upstream provenance and independence groups.
- Unknown provenance makes independence unresolved and cannot satisfy an independence requirement.
- Synthetic independence is a declared scenario assumption, not proof of real-world independence.

Candidate provenance fields are `source_device_id`, `measurement_chain_id`, `controller_logic_origin_id`, `mapping_id`, `lineage_root_ids`, and `independence_group_ids`. These fields and their vocabularies remain proposed and inactive.

## Exact flagship point and evidence gaps

All candidate points below are proposed and inactive. Adding them requires a later accepted topology ADR and a new prospective fixture version. Existing points remain unchanged.

| Evidence category | Current fixture evidence | Proposed exact missing point ID or record | Candidate type / unit | Boundary and unresolved work |
| --- | --- | --- | --- | --- |
| Process permissive | None | `PROCESS_PERMISSIVE_STATUS` | Boolean controller-reported indication | Requires a future owner/binding and source mapping. FacilityOps does not control the permissive. |
| Process-enabled operating context | None | `PROCESS_ENABLED_STATUS` | Boolean controller-reported indication | Permission and enabled context are separate. This indication does not prove process operation and need not be independent of the controller request. |
| Controller request | None | `FAN-EXHAUST-DUTY_REQUEST`; `FAN-EXHAUST-STANDBY_REQUEST` | Boolean controller-request indications | Provenance must identify the external controller and request semantics. |
| Controller-reported execution | None | `FAN-EXHAUST-DUTY_CONTROLLER_EXECUTION_STATUS`; `FAN-EXHAUST-STANDBY_CONTROLLER_EXECUTION_STATUS` | Status indication; vocabulary TBD | Request and execution remain separate; no state vocabulary is approved. |
| VFD state | Duty and standby speed-feedback points only | `FAN-EXHAUST-DUTY_VFD_STATE`; `FAN-EXHAUST-STANDBY_VFD_STATE` | Status indication; vocabulary TBD | Speed feedback is separate evidence and does not establish fan operation. |
| Motor/electrical response | None | `FAN-EXHAUST-DUTY_MOTOR_CURRENT`; `FAN-EXHAUST-STANDBY_MOTOR_CURRENT` | Analog, `A` | Current is a candidate measurement only. Source design determines whether it is independent of VFD telemetry. |
| Delivered airflow | `PROCESS-EXHAUST_AIRFLOW` | No additional point proposed | Existing analog, `m3/s` | Source identity, sensor location, calibration, uncertainty, and sufficiency criterion are missing. |
| Treatment availability | `TREATMENT_PERMISSIVE_STATUS` only | `TREATMENT_AVAILABILITY_STATUS` | Boolean or status indication; vocabulary TBD | Availability is a reported indication and does not prove treatment performance or efficiency. |
| Makeup-air response | `SUPPLY-MAKEUP_STATUS` only | `SUPPLY-MAKEUP_AIRFLOW` | Analog, `m3/s` | Status and delivered response are separate categories; measurement basis is missing. |
| Zone differential pressure | `CORRIDOR-TRANSITION_DIFFERENTIAL_PRESSURE`, `TRANSITION-LAB_DIFFERENTIAL_PRESSURE`, and `PROCESS-LAB_ZONE_PRESSURE` | No additional point proposed | Existing analog, `Pa` | Sign/orientation mapping, sensor metadata, uncertainty, and criteria are missing. A candidate upstream-minus-downstream sign convention remains inactive. |
| Post-action recovery | Existing category `EVIDENCE-POST-ACTION-OBSERVATIONS`; no observation-set instance | Proposed `POST-ACTION-OBSERVATION-SET` record type with `post_action_observation_set_id`; no recovery point | Time-bounded evidence-set record | The existing identifier is an evidence-category definition, not an observation-set instance. A recovered flag would collapse observations and evaluation. Recovery must reuse new post-action observations. |

## Proposed golden-scenario event sequence

Event IDs are stable scenario ordinals, not timestamps or evaluation criteria. Each event records an indication; none assigns a physical-state conclusion.

1. `E000-CONTEXT-DECLARED` — Pin facility profile, topology fixture, requirement set, mapping, generator, and scenario versions.
2. `E010-BASELINE-DEPENDENCIES-RECEIVED` — Receive treatment, makeup-air, shared-damper, and shared-path indications.
3. `E020-BASELINE-PERMISSIVE-RECEIVED` — Receive the external controller's process-permissive indication.
4. `E025-PROCESS-ENABLED-RECEIVED` — Receive a controller-reported process-enabled operating-context indication separately from the permissive; it does not prove process operation.
5. `E030-DUTY-REQUEST-RECEIVED` — Receive the external controller's duty-fan request indication.
6. `E040-DUTY-EXECUTION-RECEIVED` — Receive controller-reported execution separately from request.
7. `E050-DUTY-DEVICE-EVIDENCE-RECEIVED` — Receive duty availability, run, fault, dedicated VFD state, speed feedback, and motor-current indications as separate fields.
8. `E060-BASELINE-PROCESS-EVIDENCE-RECEIVED` — Receive delivered airflow, duct static, zone pressure, and both boundary differential indications.
9. `E100-DUTY-LOSS-EVIDENCE-RECEIVED` — Receive new fault, availability, run, VFD, and electrical indications that may later support a bounded duty-loss inference.
10. `E110-AIRFLOW-CHANGE-RECEIVED` — Receive new delivered-airflow and shared-path indications without assigning an inference.
11. `E120-PROCESS-PERMISSIVE-WITHHELD-RECEIVED` — Receive the external controller's indication that the process permissive is removed or withheld.
12. `E130-STANDBY-REQUEST-RECEIVED` — Receive the external controller's standby-fan request indication.
13. `E140-STANDBY-EXECUTION-RECEIVED` — Receive controller-reported standby execution separately from request.
14. `E150-STANDBY-DEVICE-EVIDENCE-RECEIVED` — Receive standby availability, run, fault, dedicated VFD state, speed feedback, and motor-current indications as separate fields.
15. `E160-STANDBY-PROCESS-RESPONSE-RECEIVED` — Receive new shared airflow, duct-static, and damper indications. A standby request alone cannot satisfy this step.
16. `E170-PRESSURE-RESPONSE-RECEIVED` — Receive new process-laboratory pressure and both boundary differential indications.
17. `E180-HUMAN-ACTION-RECORDED` — Record a fictional authorized review or action outside FacilityOps. The record supplies no evidence of physical effect.
18. `E190-POST-ACTION-DEPENDENCY-EVIDENCE-RECEIVED` — Receive new treatment and makeup-air observations whose source event times are after the recorded action where time semantics support that comparison.
19. `E200-POST-ACTION-FAN-EVIDENCE-RECEIVED` — Receive new request, execution, run, VFD, electrical, fault, and availability indications.
20. `E210-POST-ACTION-PROCESS-EVIDENCE-RECEIVED` — Receive new airflow, duct-static, zone-pressure, and both boundary observations.
21. `E220-RETURN-INDICATION-RECEIVED` — Optionally receive a permissive or return-to-normal indication; explicitly insufficient by itself.
22. `E230-RECOVERY-EVALUATION-REQUESTED` — Reserve a future evaluator input containing the controlled post-action evidence set, its non-evidentiary link to the recorded action and cutoff, the declared baseline and operating context, mappings, requirements, parameters, and evidence-health context. The action record is context, not proof of effect.
23. `E240-RECOVERY-FINDING-COMPUTED` — Reserve a later milestone event. No expected outcome is assigned until the evaluation rule and parameters are approved.

The primary sequence does not assume automatic process re-enable or exact safe-mode fan behavior. Future inactive companion variants should cover failed standby response, request/execution discrepancy, non-independent VFD/electrical evidence, status/airflow conflict, treatment loss, makeup-air loss, duplicate or conflicting identity, late or out-of-order evidence, and incomplete recovery.

## Candidate parameter register

No numerical evaluation criterion for this observation and scenario packet is defensible from the current controlled package. Every candidate below is `TBD—NO VALUE RECOMMENDED`, `PROPOSED`, and `INACTIVE`. Existing Northstar thresholds or staleness behavior must not be reused. Selection requires the stated source category, applicability decision, instrument basis, qualified domain review, and project-owner approval.

Unless a future approved basis states otherwise, candidate time-based quantities would use seconds; pressure tolerance and hysteresis would use `Pa`; airflow tolerance and hysteresis would use `m3/s` or the approved design-relative unit; and electrical hysteresis would use the selected `A`, `kW`, or controlled-status basis. These unit conventions are themselves proposed and inactive.

| Candidate criterion | Value / status | Source category and applicability basis required | Units, variability, and instrument assumptions | Persistence, delay, or hysteresis | Credible false positives and limitations | Required evidence and review |
| --- | --- | --- | --- | --- | --- | --- |
| Corridor-to-transition directional criterion | TBD—no value recommended; inactive | Project requirement based on qualified ventilation design, hazard/exposure basis, and verified source applicability | `Pa`; normal door/traffic/wind variability and instrument range, accuracy, resolution, calibration, port location, orientation, and clock basis TBD | Persistence and hysteresis TBD | Door movement, traffic, wind, stack effect, port reversal/blockage, drift | Boundary pressure evidence; mechanical, controls, industrial-hygiene, commissioning, and project-owner review |
| Transition-to-laboratory directional criterion | TBD—no value recommended; inactive | Same basis as the upstream boundary, confirmed for the laboratory use and enclosure | `Pa`; same instrument and variability metadata required independently | Persistence and hysteresis TBD | Door movement, traffic, wind, stack effect, port reversal/blockage, drift | Boundary pressure evidence; same qualified reviews |
| Differential-pressure tolerance | TBD—no value recommended; inactive | Project measurement and evaluation basis after directional criteria exist | `Pa`; combined instrument uncertainty and expected operating variability TBD | Tolerance and hysteresis TBD | Noise, resolution, drift, calibration, common reference error | Both boundary observations and calibration metadata; controls and commissioning review |
| Supported process-exhaust airflow | TBD—no value recommended; inactive | Project design and industrial-hygiene basis; applicable exhaust and test-method sources must be verified | `m3/s` or an approved design-relative basis; sensor location, density conversion, range, accuracy, and calibration TBD | Persistence and airflow hysteresis TBD | System effect, density conversion, turbulence, fouling, sensor placement, damper state | Delivered-airflow and shared-path evidence; mechanical, industrial-hygiene, controls, and commissioning review |
| Airflow tolerance and hysteresis | TBD—no value recommended; inactive | Project measurement and evaluation basis after supported airflow is defined | `m3/s` or approved design-relative basis; combined measurement uncertainty and expected operating variability TBD | Tolerance and hysteresis TBD | Turbulence, sensor noise, density conversion, VFD ramp, damper motion | Delivered-airflow and shared-path evidence; mechanical, controls, industrial-hygiene, and commissioning review |
| Motor/electrical response magnitude or status | TBD—no value recommended; inactive | Selected motor/VFD documentation, electrical measurement design, and project inference basis | `A`, `kW`, or a controlled status basis; selection, range, accuracy, sampling, and calibration TBD | Persistence and hysteresis TBD | Inrush, unloaded current, VFD-derived values, sensor noise, other connected load | Independently sourced motor/electrical evidence; electrical and controls review |
| Supported-duty-loss persistence | TBD—no value recommended; inactive | Project fan-operation inference and failure definition after evidence independence is approved | `s` or controlled multi-observation state basis; update rates and uncertainty TBD | Persistence, reset, and contradiction handling TBD | Transient fault, update skew, communications loss, sensor disagreement | Request, execution, VFD, electrical, run, fault, airflow, and health evidence; controls, electrical, mechanical, and commissioning review |
| Duty-loss-to-process-permissive-withhold timing | TBD—no value recommended; inactive | Project controls sequence and controller execution basis; not a FacilityOps command criterion | `s`; controller scan, update, transport, and timestamp uncertainty TBD | Delay and persistence TBD | Update-on-change, batching, latched status, source-clock mismatch | Supported-duty-loss evidence and process-permissive indication; controls and process review |
| Duty-loss-to-standby-request timing | TBD—no value recommended; inactive | Project controls sequence and standby-selection basis; not a FacilityOps command criterion | `s`; controller scan, update, transport, and timestamp uncertainty TBD | Delay, retry, and persistence TBD | Update-on-change, batching, permissive interlocks, source-clock mismatch | Supported-duty-loss evidence and standby-request indication; controls and mechanical review |
| Request-to-controller-execution delay | TBD—no value recommended; inactive | Project controls sequence and controller scan/communications basis | `s`; source scan, timestamp, network, and batching uncertainty TBD | Delay and retry treatment TBD; no hysteresis expected | Update-on-change, communications batching, stale controller state | Request and execution observations; controls review and project-owner approval |
| Execution-to-VFD-response delay | TBD—no value recommended; inactive | Project controls/VFD behavior and selected drive documentation | `s`; VFD ramp, scan, timestamp, and mapping assumptions TBD | Delay/persistence TBD | Ramp behavior, status derivation, network batching, permissive interlocks | Controller execution and VFD evidence; controls and electrical review |
| Execution-to-electrical-response delay | TBD—no value recommended; inactive | Project electrical measurement and motor/VFD behavior basis | `s`; current sensor range, accuracy, sampling, calibration, and clock assumptions TBD | Delay/persistence TBD | Inrush, unloaded current, VFD-derived current, sensor noise, scan time | Execution plus independently sourced motor/electrical evidence; electrical and controls review |
| Standby delivered-airflow response delay | TBD—no value recommended; inactive | Project sequence, installed system response, and verified test basis | `s`; airflow sensor dynamics and system-volume response assumptions TBD | Delay, persistence, and airflow hysteresis TBD | VFD ramp, duct storage, damper motion, sensor lag, common-path fault | Standby request/execution, device, airflow, shared-path, and pressure evidence; multidisciplinary review |
| Treatment-availability persistence | TBD—no value recommended; inactive | Project treatment definition, selected equipment documentation, and verified applicability basis | Status semantics and supporting measurements TBD | Persistence and on/off delay TBD | Latched permissive, controller-derived status, bypass, fouling, sensor or switch fault | Treatment availability, health, and source provenance; process, industrial-hygiene, controls, and commissioning review |
| Makeup-air response threshold | TBD—no value recommended; inactive | Project air-balance and pressure-control design basis | `m3/s` or approved response quantity; measurement location, accuracy, calibration, and variability TBD | Threshold, delay, persistence, and hysteresis TBD | Command versus flow, damper leakage, wind, door state, sensor lag | Makeup status/airflow and pressure evidence; mechanical, controls, and commissioning review |
| Controller evidence staleness | TBD—no value recommended; inactive | Source contract, scan/update behavior, communications SLA, and scenario timing basis | `s`; clock synchronization, precision, and receive-time uncertainty TBD | Category-specific limit TBD | Update-on-change, batching, repeated values, communications outage | Controller request/execution plus health/timing evidence; controls and data review |
| VFD/electrical evidence staleness | TBD—no value recommended; inactive | Source and instrument update behavior plus intended inference timing | `s`; sampling, scan, timestamp, and calibration assumptions TBD | Category-specific limits TBD | Cached registers, derived fields, slow polling, clock mismatch | VFD and electrical evidence with provenance; electrical, controls, and data review |
| Airflow/pressure evidence staleness | TBD—no value recommended; inactive | Instrument response, acquisition contract, physical transient, and evaluation basis | `s`; response time, sampling, filtering, precision, and clock uncertainty TBD | Separate category limits and persistence TBD | Filter lag, communications batching, transient doors/wind, cached values | Airflow, pressure, health, and timing evidence; mechanical, controls, and commissioning review |
| Dependency evidence staleness | TBD—no value recommended; inactive | Treatment and makeup source contracts and dependency semantics | `s`; update behavior and clock assumptions TBD | Separate limits/persistence TBD | Latched permissive, status-only reporting, cached pre-action value | Treatment, makeup, health, and timing evidence; responsible domain reviews |
| Allowed lateness or watermark | TBD—no value recommended; inactive | Source sequence/time contract and replay design basis | `s`; clock basis, maximum transport behavior, and uncertainty TBD | Watermark and reprocessing behavior TBD | Network interruption, batch replay, source restart, clock correction | Source-native timing and sequence metadata; data/controls review |
| Recovery persistence or hold | TBD—no value recommended; inactive | Project recovery requirement after evidence categories and safe-mode behavior are resolved | `s`; observation update rate, instrument response, and uncertainty TBD | Hold interval and reset behavior TBD | Cached pre-action values, transient return, acknowledgment/reset, controller normal flag | Complete post-action observation set; mechanical, electrical, controls, commissioning, safety, and project-owner review |

## Items requiring the next project-owner approval

1. Source-native and canonical observation boundaries, including timestamp semantics.
2. Identity, duplicate, conflict, ordering, lateness, and current-projection rules.
3. Mapping/provenance fields and the candidate upstream-minus-downstream pressure sign convention.
4. Evidence-independence rules.
5. Authorization to draft and review a new topology ADR containing the exact candidate point additions, owners, relationships, and prospective fixture version.
6. The proposed golden sequence and its inactive companion variants.
7. Each physical criterion, timing value, staleness limit, tolerance, instrument assumption, and recovery hold after a defensible basis and qualified domain review are supplied.
8. Separate authorization for Milestone 4 implementation and, later, Milestone 5 implementation.

Until those decisions are accepted, this packet remains documentation only and must not be loaded, interpreted as executable configuration, or used to evaluate the fictional facility.
