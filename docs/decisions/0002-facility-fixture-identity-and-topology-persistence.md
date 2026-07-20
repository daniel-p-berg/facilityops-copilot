# ADR 0002: Facility fixture identity and minimum topology persistence

- Status: Accepted
- Date: 2026-07-20
- Approver: Daniel Berg
- Supersedes: None
- Superseded by: None

## Context

[ADR 0001](0001-minimum-flagship-topology.md) defines the minimum fictional flagship topology for the pressure-cascade golden scenario. It deliberately does not prescribe persistence, fixture identity, loader behavior, reset selection, migration, API representation, or point bindings. Milestone 2 cannot safely store, load, and query that topology until those concerns have a consistent boundary.

The implemented repository has one Northstar Data Hall catalog in one SQLite database. Equipment and point identifiers are globally keyed within that database, every point has an equipment owner, the sample loader uses fixed Northstar CSV paths, and operational reset reloads the fixed Northstar current-value fixture. SQLite table definitions contain foreign-key clauses, but connections do not globally enable foreign-key enforcement. Schema creation and compatibility changes are implemented inline, and the database has no migration framework or facility identity record.

Adding flagship rows directly to the existing tables would silently decide whether facilities coexist, how identifiers are scoped, how reset selects baseline data, and how APIs distinguish environments. A generic graph or polymorphic reference model would create a framework broader than the accepted topology. This decision establishes the smallest persistence and fixture contract needed by Milestone 2 while preserving Northstar behavior and leaving later roadmap decisions open.

## Decision

If accepted, Milestone 2 will use the following facility-fixture, persistence, loading, reset, and query boundaries.

### Environment isolation

One explicitly selected facility environment will be stored in each SQLite database. The database is the isolation boundary for catalog, topology, and local runtime state.

Northstar Data Hall remains the default facility for the normal local database and remains the legacy regression fixture. The flagship fixture may be loaded only through explicit fixture selection into an explicitly selected target database. Milestone 2 will not implicitly replace the normal Northstar database when loading or testing the flagship.

Multiple facilities in one database, cross-facility joins, and concurrent multi-facility querying are deferred. This does not limit the number of playgrounds a user may create: users and tests may create many separate SQLite databases, each loaded from an explicitly selected facility package.

### Facility identity and versioning

Each facility package will declare:

- A stable, fixture-owned `facility_id`.
- A human-readable facility name.
- An explicit `fixture_version`.
- The package files and their expected roles.

The selected `facility_id` and `fixture_version` will be recorded in an additive facility-environment metadata table as part of a successful load transaction. Exactly one active facility identity is permitted per database.

Database schema version and facility fixture version are separate concepts. A fixture version identifies the content contract for a particular fictional facility package. A database schema version identifies the application's storage shape. Incrementing one does not implicitly increment, migrate, or validate the other.

All catalog and topology identifiers are owned by the selected fixture and must remain stable within its version lineage. Cross-facility relationships are prohibited. Because a database contains only one facility, existing Northstar equipment and point identifiers do not require facility prefixes or composite primary keys.

### Versioned fixture package

A facility package will have one explicit manifest entry point and a small set of versioned catalog/topology files. The manifest will identify the facility and fixture version and enumerate the package files; loaders must not infer environment identity from filenames, directory names, identifier prefixes, or record contents.

The preferred Milestone 2 representation is a standard-library-readable manifest, such as JSON, plus CSV files for tabular facility identity, equipment, points, zones, systems, pressure boundaries, shared paths, monitored dependencies, and typed relationship rows. This preserves the current Python standard-library and CSV approach and does not introduce YAML or another parsing dependency.

Northstar and flagship packages will remain logically separate and explicitly selectable. Existing Northstar identifiers and behavior must be preserved. Packaging Northstar does not authorize rewriting its fixture contents, identifiers, current values, alarm rules, scenarios, or regression expectations.

### Typed relational topology

Milestone 2 will use explicit relational tables and constrained relationship tables. It will not use a graph database, EAV model, arbitrary user-defined relationship vocabulary, or unconstrained source-type/source-ID polymorphism.

The persistence model will distinguish these entity families:

- Facility environment metadata.
- Zones.
- Systems.
- Directed pressure boundaries.
- Shared system paths.
- Monitored dependencies.
- Existing equipment and points.

It will distinguish these relationship families:

- Equipment-to-system membership with a constrained equipment role.
- System-to-zone service.
- Equipment-to-shared-path membership.
- Shared-path-to-monitored-dependency.
- Pressure-boundary-to-system dependency.
- Pressure-boundary-to-monitored-dependency.
- Pressure-boundary cascade ordering.
- Typed point bindings described below.

Direction will be stored in explicit upstream-zone and downstream-zone columns on each pressure boundary. Direction must not be inferred from names or row order. Equipment roles for this slice are fixture data constrained to the roles required by ADR 0001, including `duty` and `standby`; they do not define executable control behavior.

Relationship endpoints must use real keys to their typed tables. No relationship may name an endpoint through an arbitrary entity-type/entity-ID pair.

### ADR 0001-to-persistence mapping

| ADR 0001 concept | Fixture representation | Persistence representation | Required validation |
|---|---|---|---|
| Advanced Materials Research and Precision-Environment Facility | Manifest facility identity | Facility-environment metadata row | Exactly one selected facility and fixture version per database. |
| `ZONE-REFERENCE-CORRIDOR` | Zone row | Zone table | Stable ID belongs to active fixture. |
| `ZONE-TRANSITION-AIRLOCK` | Zone row | Zone table | Stable ID belongs to active fixture. |
| `ZONE-PROCESS-LAB` | Zone row | Zone table | Stable ID belongs to active fixture. |
| `BOUNDARY-CORRIDOR-TRANSITION` | Pressure-boundary row | Pressure-boundary table with explicit upstream and downstream zone keys | Upstream is corridor; downstream is transition; endpoints differ. |
| `BOUNDARY-TRANSITION-LAB` | Pressure-boundary row | Pressure-boundary table with explicit upstream and downstream zone keys | Upstream is transition; downstream is laboratory; endpoints differ. |
| `SYSTEM-PROCESS-EXHAUST` | System row | System table | System belongs to active fixture. |
| `FAN-EXHAUST-DUTY` | Equipment row plus membership row | Existing equipment table plus equipment-system membership table | Equipment exists; system exists; role is `duty`; membership is unique. |
| `FAN-EXHAUST-STANDBY` | Equipment row plus membership row | Existing equipment table plus equipment-system membership table | Equipment exists; system exists; role is `standby`; membership is unique. |
| `PATH-EXHAUST-SHARED` | Shared-path row | Shared-path table | Path belongs to active fixture. |
| `PERMISSIVE-TREATMENT` | Monitored-dependency row | Monitored-dependency table | Dependency belongs to active fixture and is marked monitored, not commanded. |
| `DEPENDENCY-SUPPLY-MAKEUP` | Monitored-dependency row | Monitored-dependency table | Dependency belongs to active fixture and is marked monitored, not commanded. |
| Corridor is upstream of first boundary | Boundary endpoint columns | `BOUNDARY-CORRIDOR-TRANSITION.upstream_zone_id` | Endpoint matches the accepted direction. |
| Transition is downstream of first boundary | Boundary endpoint columns | `BOUNDARY-CORRIDOR-TRANSITION.downstream_zone_id` | Endpoint matches the accepted direction. |
| Transition is upstream of second boundary | Boundary endpoint columns | `BOUNDARY-TRANSITION-LAB.upstream_zone_id` | Endpoint matches the accepted direction. |
| Laboratory is downstream of second boundary | Boundary endpoint columns | `BOUNDARY-TRANSITION-LAB.downstream_zone_id` | Endpoint matches the accepted direction. |
| Duty fan is a duty member of process exhaust | Equipment-system membership row | Equipment-system membership table | One duty membership for the accepted system. |
| Standby fan is a standby member of process exhaust | Equipment-system membership row | Equipment-system membership table | One standby membership for the accepted system. |
| Both fans use the shared path | Two equipment-shared-path rows | Equipment-shared-path membership table | Both equipment and path endpoints exist; rows are unique. |
| Shared path has treatment dependency | Shared-path-dependency row | Shared-path-to-monitored-dependency table | Path and treatment dependency exist. |
| Process-exhaust system serves laboratory | System-zone service row | System-to-zone service table | System and laboratory zone exist. |
| Laboratory boundary depends on process exhaust | Boundary-system dependency row | Pressure-boundary-to-system dependency table | Boundary and system exist. |
| Both boundaries depend on supply/makeup air | Two boundary-dependency rows | Pressure-boundary-to-monitored-dependency table | Both boundaries and supply dependency exist. |
| First boundary is cascade-upstream of second | Cascade-order row | Pressure-boundary cascade-order table | Boundaries exist; no self-reference, duplicate, or cycle in the selected chain. |

The loader must validate that the complete corridor to transition/airlock to process-laboratory chain exists and is connected through the accepted entity and relationship inventory. The schema remains limited to these relationship families until a later accepted decision expands it.

### Point binding

Existing point-to-equipment ownership is preserved. Northstar's `points.equipment_id` values and behavior will not be rewritten. A point continues to have exactly one real equipment owner. The flagship fixture may include real sensing or controls equipment when needed to own observations, but it must not create fictional placeholder equipment solely to stand in for a zone, system, shared path, dependency, or pressure boundary.

Additional topology meaning will be represented by separate typed binding tables where required:

- Point to zone.
- Point to system.
- Point to pressure boundary.
- Point to shared path.
- Point to monitored dependency.

Each typed binding has concrete foreign-key-shaped columns for its point and target. There is no generic `entity_type` plus `entity_id` binding. For Milestone 2, a point may have zero or one additional primary topology binding across these binding families. The fixture validator must reject duplicate bindings, multiple primary topology targets, missing targets, or a binding to another fixture.

Point-binding examples for the accepted topology are:

| Point category | Equipment ownership | Additional typed topology binding |
|---|---|---|
| Duty-fan run or fault status | Real duty-fan equipment | None required; equipment-system membership supplies system context. |
| Standby availability, run, or fault status | Real standby-fan equipment | None required; equipment-system membership supplies system context. |
| Exhaust airflow or system-capacity evidence | Real instrument or controls equipment | Process-exhaust system or shared exhaust path, according to what is directly observed. |
| Duct-static or relevant damper-position evidence | Real instrument or damper equipment | Shared exhaust path. |
| Treatment permissive | Real monitoring or treatment equipment | Treatment monitored dependency. |
| Supply or makeup-air status | Real monitoring or supply equipment | Supply/makeup-air monitored dependency. |
| Process-laboratory zone pressure | Real pressure instrument | Process-laboratory zone. |
| Corridor-to-transition differential pressure | Real differential-pressure instrument | Corridor-to-transition pressure boundary. |
| Transition-to-laboratory differential pressure | Real differential-pressure instrument | Transition-to-laboratory pressure boundary. |

These bindings describe observation context only. They do not define point condition, quality precedence, sufficiency, thresholds, persistence, timing, or state determination.

### Loader validation and transaction boundary

The loader will resolve one explicitly supplied manifest, read all referenced package files, normalize them, and validate the complete in-memory fixture before opening a write transaction.

Pre-load validation will reject at least:

- Missing, blank, duplicate, or unstable identifiers.
- Manifest/file facility or version mismatches.
- Unknown or invalid equipment roles.
- Invalid or self-referential pressure directions.
- Missing relationship endpoints.
- Duplicate relationships.
- Missing required ADR 0001 entities or relationships.
- An incomplete or disconnected cascade chain.
- Invalid point-binding cardinality or target type.
- Cross-fixture references.

After successful pre-load validation, catalog, topology, typed bindings, and active facility metadata will be written through one SQLite connection in one explicit transaction. The active facility identity and fixture version will be recorded only within that transaction. Any write failure or post-load validation failure must roll back the entire transaction and preserve the prior database contents.

Post-load validation will re-query stored identifiers, relationship endpoints, directions, roles, binding cardinality, and the complete accepted chain. It will also run SQLite foreign-key consistency inspection for declared constraints even though global enforcement remains disabled in this milestone.

No loader may fall back from an unknown or invalid requested fixture to Northstar.

### Reset-selection behavior

Facility catalogs, topology, relationship rows, point bindings, active facility identity, and fixture version are configuration and survive operational reset.

Operational reset will read the active facility identity and fixture version from the target database and resolve only the matching explicitly registered package context. If the exact package or declared baseline is unavailable, reset must fail without modifying the database. It must never silently use the Northstar current-value CSV for a flagship or other playground database.

The Milestone 2 flagship fixture does not need golden-scenario observations. It may declare no current-value baseline. In that case operational reset clears the otherwise approved volatile state and reloads zero baseline observations while preserving the flagship catalog and topology. Exact golden-scenario observations belong to Milestone 4.

This reset decision only prevents cross-environment contamination and preserves configuration. It does not decide durable incident-evidence retention, which remains deferred to its roadmap milestone and future ADR.

### Foreign keys and additive schema evolution

Milestone 2 will add topology and facility metadata storage without rewriting existing Northstar equipment or point identifiers. Existing local Northstar databases will be handled by creating the additive tables and recording Northstar facility metadata only when the Northstar package is explicitly selected and successfully validated. Facility identity must not be guessed from current rows.

New topology and typed-binding table definitions will declare concrete foreign-key relationships and uniqueness constraints compatible with later enforcement. Milestone 2 will also require deterministic pre-load and post-load referential validation.

Milestone 2 will not globally enable SQLite foreign keys. Current loader ordering, deletion behavior, and connection creation have not been verified under global enforcement, so enabling it would be a separate compatibility change. Milestone 2 will not introduce a migration framework. The additive table-creation and compatibility behavior needed for this slice may use the existing straightforward schema-creation approach.

Fixture-version changes are not database migrations. This ADR does not select future migration tooling, define general upgrade paths, or claim that existing databases are production-upgradeable.

### Query contract

Topology query results will identify the active `facility_id` and `fixture_version`. A query of the minimum flagship topology must expose the complete ordered corridor to transition/airlock to process-laboratory chain, including:

- Both directed pressure boundaries and their upstream/downstream zones.
- The process-exhaust system serving the laboratory.
- Duty and standby fan memberships and roles.
- Both fans' shared-path memberships.
- The treatment dependency.
- The minimum supply/makeup-air dependencies for both boundaries.
- Cascade ordering.
- Relevant typed point bindings.

The query result must be deterministic and inspectable without inferring direction or relationships from names. Exact endpoint paths, response nesting, and frontend presentation remain implementation details for a later approved slice.

### Explicitly deferred decisions

This ADR does not decide:

- Numerical pressure, airflow, duct-static, speed, current, or other thresholds and tolerances.
- Point-condition, equipment-state, system-state, pressure-cascade-state, facility-state, consequence, alarm-priority, operational-risk, advisory, or incident-severity vocabularies.
- Event time, receive time, ordering, late data, staleness, persistence, delays, replay clocks, or recovery holds.
- Golden-scenario observation values, sequencing, replay packaging, or expected states.
- Operational consequence logic, affected scope, escalation, or advisory text.
- Durable evidence identifiers, retention, reset survival, manifests, hashes, or export architecture.
- Sequence-of-operations simulation, controller behavior, automatic duty/standby transfer, control language, or external commands.
- Global SQLite foreign-key enforcement.
- Migration-framework selection or general production database upgrades.
- Frontend facility selection or presentation.
- Multiple concurrently active facilities or multi-facility queries.
- Milestone 3 point-condition semantics or any higher-level authoritative determination.

## Consequences

The one-facility-per-database boundary preserves simple, unscoped catalog queries and avoids invasive Northstar primary-key migration during Milestone 2. Facility identity and fixture version become explicit, and users can still create any number of isolated playground databases.

Typed tables and bindings make accepted topology direction, roles, dependencies, and observation context inspectable and deterministically validatable. They cost more tables and fixture files than a generic edge model, but their allowed meanings and endpoints are reviewable and compatible with later foreign-key enforcement.

An atomic environment load prevents a partially replaced catalog or topology after invalid input. It requires refactoring the current multi-connection, per-table replacement flow for the new explicitly selected package path. The legacy Northstar entry point may remain as a compatibility wrapper, but its observable catalog, alarm, replay, and reset behavior must remain unchanged.

Reset becomes facility-aware and fails closed when fixture context is unavailable. This removes the unsafe possibility of inserting Northstar baseline rows into a flagship database, but it requires active facility metadata and an explicit fixture resolver.

The design intentionally cannot query two facilities together. If a later approved use case requires concurrent facilities, facility-scoped keys and pervasive query filters may require a new ADR and schema evolution. The typed vocabulary may also need deliberate expansion for future topology concepts; arbitrary relationships cannot be added without schema and validation changes.

Acceptance of this ADR would authorize these persistence boundaries only. It would not claim that any facility package, schema, loader, reset behavior, topology query, or validation is implemented.

## Alternatives considered

### Multiple facilities in one SQLite database

This would make side-by-side facility selection and cross-facility queries easier. It would require facility-scoped keys or globally unique identifiers, updates to existing Northstar tables and APIs, pervasive filtering, environment-aware local writes, and broader migration work. It is deferred because Milestone 2 needs one flagship proof while preserving the current single-database architecture.

### One database per facility with explicit selection

This is the selected approach. It matches the implemented single-database query model, gives strong isolation, avoids rewriting Northstar identifiers, and permits many independent playgrounds. Its limitation is the absence of concurrent multi-facility queries.

### Generic graph or EAV topology

A generic node/edge or EAV model could represent future relationships without adding tables. It would weaken endpoint enforcement, permit arbitrary vocabulary, obscure cardinality, and create a general topology framework before more than one scenario proves the need. It is rejected for Milestone 2.

### Typed relational topology

This is the selected approach. It uses more explicit tables but makes direction, membership, service, dependencies, cascade order, and point context readable and deterministically testable.

### Facility identity inferred from filenames or identifier prefixes

Inference would require less manifest data but could misclassify user-created fixtures and silently choose the wrong reset baseline. It is rejected in favor of explicit manifest selection and recorded identity.

### Fake equipment or polymorphic point targets

Creating equipment rows to stand in for zones or boundaries would corrupt domain meaning. A generic entity-type/entity-ID pair would not have a concrete relational target and would rely entirely on application convention. Both are rejected in favor of real equipment ownership plus typed topology bindings.

### Global foreign-key enforcement and migration framework in Milestone 2

This could improve database-wide integrity but would broaden the slice into existing loader, reset, connection, and upgrade behavior. It is deferred. New tables remain shaped for later enforcement, and explicit validation provides the Milestone 2 acceptance boundary.

## Verification and implementation impact

This proposed ADR changes documentation only. It does not implement schemas, fixture packages, loaders, queries, reset behavior, migrations, or tests.

If accepted and followed by a separately approved implementation slice, likely affected areas include:

- `analysis/load_alarm_db.py` or a focused facility-package loader for explicit manifest selection, validation, and one-transaction loading.
- Separate Northstar and flagship package directories under `data/`, using standard-library-readable manifests and CSV catalogs.
- Additive SQLite table creation for facility metadata, topology entities, typed relationships, and point bindings.
- `backend/services/operational_reset_service.py` for facility-aware baseline resolution without Northstar fallback.
- A focused topology query service and `backend/main.py` route integration.
- `data/README.md`, `docs/ARCHITECTURE.md`, and `docs/PROJECT_STATUS.md` after implementation is verified.
- Catalog, topology, loader-rollback, reset-isolation, API, and Northstar regression tests.

Implementation tests must cover at least:

- Explicit Northstar and flagship selection into separate temporary SQLite databases.
- Stable facility ID and fixture-version recording.
- Deterministic loads and repeated loads.
- Every ADR 0001 entity and relationship mapping.
- Exact pressure direction, fan roles, system service, shared-path membership, dependencies, and cascade order.
- Point-binding cardinality and typed target validation.
- Missing files, invalid identifiers, duplicate identifiers, invalid roles, missing endpoints, invalid directions, incomplete chains, cycles, cross-fixture references, and invalid manifests.
- Complete rollback after pre-load, write, or post-load failure.
- Query output containing facility identity, fixture version, and the complete accepted topology chain.
- Operational reset preserving both Northstar and flagship catalogs/topology and never crossing fixture baselines.
- Existing Northstar identifiers, counts, behavior, and the full regression suite remaining unchanged.

Implementation evidence must distinguish the approved decision from verified behavior. `PROJECT_STATUS.md` may describe the topology as implemented only after the approved code slice and its deterministic tests pass.

## References

- [FacilityOps Copilot Product Charter](../PRODUCT_CHARTER.md)
- [FacilityOps Copilot Project Status](../PROJECT_STATUS.md)
- [FacilityOps Copilot Roadmap, Milestone 2](../ROADMAP.md#milestone-2--minimum-viable-flagship-catalog-and-topology)
- [FacilityOps Copilot Architecture](../ARCHITECTURE.md)
- [Planned Flagship Facility](../FLAGSHIP_FACILITY.md)
- [ADR 0001: Minimum flagship topology](0001-minimum-flagship-topology.md)
- [Architecture Decision Records](README.md)
