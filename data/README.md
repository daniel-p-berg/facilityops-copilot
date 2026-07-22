# Facility Fixture Data

The root-level sample CSV files remain the fictional Northstar Data Hall regression fixture. `analysis/load_alarm_db.py` is its default compatibility loader and records Northstar facility identity/version metadata after a successful load.

Versioned facility packages are under `facilities/`:

- `facilities/northstar/1.0.0/manifest.json` registers the existing Northstar files and 17-value reset baseline without copying or rewriting them.
- `facilities/flagship/1.0.0/manifest.json` is the minimum Advanced Materials Research and Precision-Environment Facility package. Its CSV files contain 10 equipment records, 16 owned points, 3 zones, 1 system, 2 directed pressure boundaries, 1 shared path, 2 monitored dependencies, 10 topology relationship rows, and 8 typed point bindings. It intentionally contains no current-value observations.

The flagship package is a synthetic topology and observation-context catalog only. It is not a Standards Reference Registry, Applicable Requirements Baseline, executable requirement pack, evidence-sufficiency definition, conformance dataset, commissioning record, or determination of physical safety. Its duty/standby roles, pressure directions, dependencies, and point categories represent accepted fictional topology for simulation planning, not directly applicable code or owner requirements.

The current package has no controller command/request observation and no dedicated VFD or motor electrical corroboration point. Those are required future evidence categories, but exact fixture or topology changes require a later accepted ADR and approved roadmap slice.

Every flagship CSV row repeats the owning `facility_id` and `fixture_version`. The manifest-driven loader checks those fields, identifiers, references, roles, pressure direction, cascade connectivity, relationship uniqueness, and primary binding cardinality before it opens the target database.

`replay_samples.csv` is an ordered fictional CSV replay fixture used by the local read-only replay adapter and replay-runner workflows. `imports/modbus_register_map_sample.csv` is a static fictional Modbus register-map fixture used for preview and local catalog import only; it is not a device connection or polling configuration.

All data is fictional. The repository contains no credentials, customer exports, real facility network information, or live system configuration. Do not add sensitive or proprietary data or protected standards clauses to this folder.
