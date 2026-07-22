# Facility Fixture and Standards-Basis Data

The root-level sample CSV files remain the fictional Northstar Data Hall regression fixture. `analysis/load_alarm_db.py` is its default compatibility loader and records Northstar facility identity/version metadata after a successful load.

Versioned facility packages are under `facilities/`:

- `facilities/northstar/1.0.0/manifest.json` registers the existing Northstar files and 17-value reset baseline without copying or rewriting them.
- `facilities/flagship/1.0.0/manifest.json` is the minimum Advanced Materials Research and Precision-Environment Facility package. Its CSV files contain 10 equipment records, 16 owned points, 3 zones, 1 system, 2 directed pressure boundaries, 1 shared path, 2 monitored dependencies, 10 topology relationship rows, and 8 typed point bindings. It intentionally contains no current-value observations.

The facility package at `facilities/flagship/1.0.0/` is a synthetic topology and observation-context catalog only. It is not a controlled-source catalog, applicability baseline, executable requirement pack, evidence-sufficiency definition, conformance dataset, commissioning record, or determination of physical safety. Its duty/standby roles, pressure directions, dependencies, and point categories represent accepted fictional topology for simulation planning; FacilityOps does not represent them as directly code-required or as physical-operation requirements.

The current facility package has no process-enabled operating-context or controller command/request observation and no dedicated VFD or motor electrical corroboration point. Those are required future evidence categories, but exact fixture or topology changes require a later accepted ADR and approved roadmap slice.

The separate [standards-basis package](standards/flagship/1.0.0/manifest.json) is repository-versioned reviewer data bound to flagship facility and fixture version `1.0.0`. It contains 18 fictional profile facts, 27 controlled-source records, 23 applicability bases, 18 evidence categories, and 12 project-authored synthetic requirements. Ten requirements have the project-owner decision recorded; two remain proposed drafts. All 12 are inactive, non-executable, and contain no numerical criteria.

`backend/services/standards_basis_service.py` validates the entire JSON package before atomically exposing an in-memory snapshot. It rejects duplicate identifiers, invalid statuses, missing provenance, unresolved or cross-facility references, point references outside the bound flagship catalog, malformed files, numerical criteria, and executable requirements. It does not create or modify SQLite data.

Controlled-source records contain metadata, official links, access status, uncertainty, and short project-authored summaries. They do not reproduce protected standards clauses, tables, or figures. The provisional applicability matrix and traceability do not establish code compliance, commissioning acceptance, physical safety, operability, or authorization for operation.

Process-enabled operating context, controller request, controller-reported execution, dedicated VFD state, independently sourced motor/electrical response, treatment-availability response, makeup-air response, complete timing/provenance, and post-action evidence remain missing or partial. The proposed exact additions are documentation only in the [inactive next-review packet](../docs/decision-packets/0001-flagship-observation-and-scenario.md).

Every flagship CSV row repeats the owning `facility_id` and `fixture_version`. The manifest-driven loader checks those fields, identifiers, references, roles, pressure direction, cascade connectivity, relationship uniqueness, and primary binding cardinality before it opens the target database.

`replay_samples.csv` is an ordered fictional CSV replay fixture used by the local read-only replay adapter and replay-runner workflows. `imports/modbus_register_map_sample.csv` is a static fictional Modbus register-map fixture used for preview and local catalog import only; it is not a device connection or polling configuration.

All data is fictional. The repository contains no credentials, customer exports, real facility network information, or live system configuration. Do not add sensitive or proprietary data or protected standards clauses to this folder.
