# Facility Fixture, Standards-Basis, Mapping, and Replay Data

The root-level sample CSV files remain the fictional Northstar Data Hall regression fixture. `analysis/load_alarm_db.py` is its default compatibility loader and records Northstar facility identity/version metadata after a successful load.

Versioned facility packages are under `facilities/`:

- `facilities/northstar/1.0.0/manifest.json` registers the existing Northstar files and 17-value reset baseline without copying or rewriting them.
- `facilities/flagship/1.0.0/manifest.json` is the preserved minimum Advanced Materials Research and Precision-Environment Facility package. It contains 10 equipment records, 16 owned point definitions, 3 zones, 1 system, 2 directed pressure boundaries, 1 shared path, 2 monitored dependencies, 10 topology relationship rows, and 8 typed point bindings.
- `facilities/flagship/1.1.0/manifest.json` is the additive observation-topology package identified as `TOPOLOGY-FLAGSHIP-PROCESS-EXHAUST` version `1.1.0`. It preserves the `1.0.0` inventory and adds 2 real point-owning equipment records, 12 reported-indication point definitions, and 4 typed bindings. The resulting package contains 12 equipment records, 28 point definitions, and 12 typed point bindings.

Both flagship facility packages are synthetic topology and point-definition catalogs. Their point rows and typed bindings define possible reported-indication channels; they are not source-native records or canonical observations, and neither package declares a current-value baseline. They are not controlled-source catalogs, executable requirement packs, evidence-sufficiency definitions, conformance datasets, commissioning records, or determinations of physical safety.

Topology `1.1.0` adds only the approved representation gaps: process-enabled and process-permissive indications; duty- and standby-fan controller request, controller-reported execution, VFD-state, and motor-current indications; treatment availability; and delivered supply/makeup airflow. Existing shared process-exhaust airflow, makeup-air controller status, fan run/fault/availability/speed, pressure, and shared-path point definitions remain reused. The package adds no inferred fan-failed, recovered, containment, equipment-state, system-state, or facility-state point.

The topology crosswalk treats `PROCESS-EXHAUST_AIRFLOW` as one shared downstream delivered-airflow indication owned by `SENSOR-EXHAUST-AIRFLOW` and bound to `SYSTEM-PROCESS-EXHAUST`. It must not be attributed independently to the duty fan or the standby fan, and it is not proof that either fan delivered airflow.

Standards-basis packages are under `standards/flagship/`:

- [Version 1.0.0](standards/flagship/1.0.0/manifest.json) remains the preserved Milestone 3 package bound to topology `1.0.0`.
- [Version 1.1.0](standards/flagship/1.1.0/manifest.json) is additive reviewer data bound to the exact topology `1.1.0` identity and digest. It preserves the same 18 fictional profile facts, 35 controlled sources, 29 applicability bases, 19 evidence categories, and 12 project-authored synthetic requirements while updating only the approved point-definition representations and corresponding explanatory text.

All 12 standards-basis requirements remain inactive, non-executable, and without numerical criteria. Every evidence category continues to state `NO_FLAGSHIP_OBSERVATION_BASELINE`. A synthetic replay execution is a separate, explicitly selected source of fictional observations; it does not become the standards view's default observation baseline.

`backend/services/standards_basis_service.py` validates an entire selected standards package before exposing an in-memory snapshot. It rejects invalid identity, provenance, references, lifecycle state, requirement content, facility/topology bindings, and unapproved changes between versions. It does not create or modify SQLite data.

Repository-versioned source bindings and mappings are under [observation_mappings/flagship-synthetic-indications/1.0.0](observation_mappings/flagship-synthetic-indications/1.0.0/manifest.json). The package is bound to the exact flagship facility and topology `1.1.0` digest and pins canonicalizer `facilityops-canonicalizer/1.0.0`. Its transformations are limited to field selection, strict type or enum normalization, decimal scaling, same-dimension unit conversion, partial decode, and declared signed register-pair decoding. Mapping content digests and exact source-field lineage make each derivation reproducible. Dependency metadata records declared or unknown origins only; it does not establish evidence independence, corroboration count, weight, or sufficiency.

The allowlisted [flagship process-exhaust evidence sequence](observation_replays/flagship-process-exhaust-evidence-sequence/1.0.0/manifest.json) is a repository-only synthetic observation replay. Its manifest pins facility, topology, mapping, canonicalizer, source-event, source timestamp, virtual receipt-time, payload, and synthetic-generator facts. The package includes a 20-entry narrative containing received-indication groups and one non-authoritative recorded-action annotation, plus a structural oracle. It exercises exact and conflicting redelivery, distinct source-event identities, missing or invalid source time, out-of-order arrival, source-order conflicts, declared and ambiguous sequence reset, mapping transition, one-to-many decode, many-to-one decode, and partial decode without asserting equipment, system, facility, conformance, consequence, safety, authorization, or recovery outcomes. Recovery evaluation, findings, and human disposition are not implemented.

`replay_samples.csv` remains the separate ordered Northstar CSV fixture used by the legacy local replay adapter and alarm-evaluating replay runner. It does not use the canonical observation store. `imports/modbus_register_map_sample.csv` remains a static fictional Modbus register-map fixture used for preview and local catalog import only; it is not a device connection or polling configuration.

All data is fictional. The repository contains no credentials, customer exports, real facility network information, or live system configuration. Do not add sensitive or proprietary data or protected standards clauses to this folder.
