# FacilityOps Copilot

## Applicable Standards Baseline and Stage Review

**Baseline date:** 2026-07-22
**Status:** Research baseline for project review; not yet an approved project requirement set
**Facility assumption:** Fictional advanced-materials research and precision-environment facility in New York State, outside New York City
**Product stage:** Canonical observations, temporal semantics, provenance, deterministic replay, and the first process-exhaust failure scenario

## Executive determination

FacilityOps does not need a universal compliance catalog at this stage. It needs a controlled reference set and a disciplined method for deciding which source governs each fictional requirement.

The standards that should materially influence the product now are those that establish:

- Jurisdiction and applicability.
- A defensible process-exhaust reference scenario.
- Requirements traceability and versioning.
- Separation of computed findings from human acceptance.
- Deterministic replay and the limits of controller-conformance testing.
- Observation time, units, provenance, quality, and uncertainty.
- Read-only OT and protocol boundaries.

No reviewed source supplies a universal numerical room-pressure band, standby-start time, airflow threshold, or recovery time that can be applied to the current fictional facility without further assumptions. Those values must come from an approved project basis such as an Owner's Project Requirements document, Basis of Design, sequence of operation, Chemical Hygiene Plan, permit, equipment requirement, or test procedure. Until a qualified review occurs, FacilityOps should label them `SYNTHETIC` and `ACCEPTED_FOR_SIMULATION`.

The standards baseline should therefore have three conceptual layers:

1. **Source reference registry** — what a source is, its status, edition, authority, access, and applicability trigger.
2. **Applicable requirements baseline** — which requirements have been selected for a particular facility, system, mode, and effective interval.
3. **Executable requirements and tests** — deterministic abstractions that state their parameters, evidence needs, scope, limitations, and review status.

This report establishes the first layer and recommends which sources should shape the second and third layers. It does not encode them.

## Applicability rules

A publication is not automatically applicable merely because it is current or technically relevant.

| Authority class | When it becomes applicable | FacilityOps treatment |
|---|---|---|
| Law or regulation | The facility, employer, activity, material, or emission falls within its legal scope | Record jurisdiction, applicability decision, effective date, and enforcement status |
| Adopted code | The jurisdiction adopts the edition and the project or existing condition falls within its scope | Record adopted edition separately from publisher-current edition |
| Referenced standard | An applicable code incorporates it to a stated extent | Store the incorporating source and exact extent of reference |
| Permit, consent order, or license condition | Issued for the actual facility or activity | Treat as site-specific authority; do not generalize it |
| Contract, OPR, BOD, SOO, CHP, SOP, or owner standard | Approved through the applicable project or operating process | Treat as project/site control intent with approval and effective intervals |
| Consensus standard | Adopted, incorporated, contracted, or voluntarily selected | Do not describe it as legally mandatory without the adoption path |
| Guideline or recommended practice | Selected as a design or process reference | Preserve its advisory status |
| Protocol or data specification | Selected for an interface or representation | It governs interoperability, not physical truth or regulatory compliance |
| Proposed standard or research specification | Used for comparison or monitored for future change | Never use as a compliance claim |

At minimum, a future source record must distinguish:

- `publisher_current_edition`
- `jurisdiction_adopted_edition`
- `project_effective_edition`
- `publication_status`
- `adoption_status`
- `enforcement_status`
- `applicability_status`
- `applicability_basis`
- `effective_from` and `effective_to`
- addenda, errata, interpretations, amendments, and court or agency actions

This distinction is already necessary in New York. The 2025 Uniform and Energy Codes became effective on December 31, 2025, but a July 2, 2026 court-order update says specified fossil-fuel prohibitions remain suspended and unenforceable. A static edition field would miss that state. See the [New York Department of State Notice of Adoption](https://dos.ny.gov/notice-adoption).

## Most important sources for the present product stage

### Priority review and disposition

| Priority | Source | Status on 2026-07-22 | Decision for this stage | Principal influence | Critical limitation |
|---:|---|---|---|---|---|
| 1 | 2025 New York State Uniform Code books, especially the Mechanical, Building, and Fire Codes | Adopted; generally effective 2025-12-31 outside NYC | **APPLY AS THE JURISDICTIONAL REFERENCE** | Forces explicit jurisdiction, use, occupancy, hazard, construction-status, and enforcement decisions | The current fictional profile is not detailed enough to establish every applicable section |
| 2 | 2025 Mechanical Code of New York State, Chapter 5 and Section 509 | Adopted code | **USE TO SHAPE THE FLAGSHIP PROFILE; DO NOT YET CLAIM COMPLIANCE** | Provides the strongest public basis for a hazardous/laboratory exhaust topology with redundancy, branch controls, negative-pressure ducts, discharge, and makeup-air relationships | Applicability depends on the actual use, material, quantities, hazard, and related Building/Fire Code provisions |
| 3 | OSHA 29 CFR 1910.1450 | Federal regulation | **APPLY IF THE FICTIONAL USE IS LABORATORY USE OF HAZARDOUS CHEMICALS** | Requires a Chemical Hygiene Plan and functioning protective equipment; makes site program documents important requirement sources | It does not provide a universal fan-transition or room-pressure threshold |
| 4 | ANSI/ASHRAE/IES Standard 202-2024 and ASHRAE Guideline 0-2019 | Published standard and guideline | **APPLY AS PROCESS ARCHITECTURE** | Separates approved requirements, verification, issues, disposition, records, and human acceptance | A synthetic replay is not an actual commissioning project or certification |
| 5 | ANSI/ASHRAE Standard 230-2022 and ASHRAE Guideline 1.1-2025 | Published standard and guideline | **APPLY SELECTED CONCEPTS** | Informs investigation, corrective action, retest, Current Facility Requirements, systems documentation, operability, and retained recovery evidence | They do not establish the process-exhaust design basis or authorize FacilityOps findings as acceptance |
| 6 | ISO/IEC/IEEE 29148:2018 | Current; confirmed in 2024 | **USE AS A LIGHT TRACEABILITY REFERENCE** | Encourages unique, versioned, testable requirements with source, rationale, scope, assumptions, and verification links | Implement a small compatible pattern, not the entire lifecycle standard |
| 7 | ANSI/ASHRAE Standard 231-2026 (CDL) | Published standard | **STUDY; OPTIONAL ONE-SEQUENCE COMPARISON** | Supplies deterministic, human- and machine-readable control-sequence concepts with explicit inputs, outputs, parameters, and state | Controller logic does not prove correct wiring, sensing, airflow, pressure response, or equipment performance |
| 8 | LBNL OpenBuildingControl verification | Evolving research specification and prototype; July 8, 2026 working report | **STUDY AND REUSE CONCEPTS** | Archived replay, pinned parameters, mappings, units, value/time tolerances, and reproducible comparison | It explicitly excludes correct field I/O, sensor/actuator installation, mechanical performance, and envelope performance |
| 9 | BSR/ASHRAE Standard 236P | Proposed standard; no published edition | **MONITOR/STUDY ONLY** | Proposed bounded controller-program test scripts provide a useful comparison boundary | It is bench-scale, BACnet-based, pass/fail testing without physical sensors or devices; final content is unknown |
| 10 | ASHRAE Guideline 36-2024 with published addenda | Published guideline on continuous maintenance | **USE AS A DESIGN SPECIMEN** | Demonstrates structured modes, transitions, timers, deadbands, resets, fault conditions, point requirements, and functional tests | It is not the approved source for the flagship process-exhaust sequence |
| 11 | RFC 3339, W3C PROV-DM, and the BIPM SI Brochure | Stable public specifications/reference | **APPLY SMALL, COMPATIBLE CONVENTIONS NOW** | Supports interoperable timestamps, transformation lineage, responsible activities/agents, and unambiguous quantities and units | Timestamp syntax does not establish clock accuracy; provenance does not establish data validity |
| 12 | ANSI/ASHRAE Standard 135-2024 (BACnet) | Published, continuous-maintenance standard | **PRESERVE COMPATIBILITY; DEFER ADAPTER** | Preserve device/object/property identity, engineering units, flags, reliability, out-of-service, priority/override, and source timestamps when available | Protocol interoperability is not semantic equivalence, mapping correctness, clock quality, or physical proof |
| 13 | NIST SP 800-82 Rev. 3 and ISA/IEC 62443 series | Published guidance/standards; SP 800-82 Rev. 4 is only pre-draft work | **APPLY BOUNDARIES NOW; FULL PROGRAM LATER** | Supports passive collection, least privilege, segmentation, asset ownership, configuration control, logging, and separation from control authority | They do not validate the process model or authorize a live connection |
| 14 | ANSI/ISA-18.2-2016 | Published alarm-management standard | **USE TERMINOLOGY NOW; IMPLEMENT ALARMS LATER** | Keeps observations, events, findings, notifications, and operator alarms distinct | A FacilityOps finding is not automatically an alarm and should not create an unmanaged parallel alarm system |

### 1. New York jurisdiction and process-exhaust applicability

The fictional facility should be explicitly located in New York State outside New York City for this baseline. New York's 2025 Uniform and Energy Codes are generally effective for regulated work from December 31, 2025. The code set includes the Building, Mechanical, Fire, Existing Building, Property Maintenance, and Energy codes. The [New York notice](https://dos.ny.gov/notice-adoption) also demonstrates why amendment and enforcement state must be versioned independently.

The [2025 Mechanical Code of New York State](https://codes.iccsafe.org/content/NYSMC2025P1/chapter-5-exhaust-systems) is the most relevant adopted-code reference for the first scenario. Its Chapter 5 governs exhaust systems, and Section 509 addresses hazardous exhaust. Its laboratory-exhaust manifold provisions are particularly relevant to the chosen topology: under specified conditions they address negative-pressure ducts, branch flow regulation, common fire-area limitations, restricted mixing, and redundant fans. The redundancy alternatives include parallel fans sized for the required exhaust rate or control that operates one fan when the other fails or is shut down. Section 509 also links mechanically supplied makeup air to exhaust operation.

Those provisions support the technical credibility of a duty/standby fan and makeup-air dependency scenario. They do **not** prove that Section 509 applies to the fictional facility as currently documented. In particular, the redundant-fan language is part of a laboratory-manifolding exception with multiple simultaneous conditions; it is not a blanket rule that every laboratory must use duty/standby fans. Before an applicable requirement is created, the project must declare at least:

- Whether the scenario is a laboratory, production process, hazardous production material area, or another use.
- The fictional materials and hazard classifications at a non-sensitive category level.
- Whether the exhaust is hazardous under the adopted code.
- Whether fans share a manifold and fire area.
- Whether the modeled building is new, existing, or altered.
- The relevant Building and Fire Code triggers.
- The AHJ assumption and any local amendments.

Until that profile is approved, the code should be stored as a **candidate source** and the sequence should remain an `ACCEPTED_FOR_SIMULATION` project abstraction.

The 2025 Building and Fire Codes are the applicability gates for occupancy, hazardous-material inventory, maximum allowable quantities, fire areas, control areas, higher-education laboratory provisions, gas rooms/cabinets, detection, treatment, and emergency or standby power. Their requirements are conditional. Treatment failure should be modeled as a bounded life-safety consequence only when the declared material/use/permit basis makes treatment required. Likewise, emergency-power telemetry should enter the evidence model only when an applicable code or owner requirement makes that dependency part of the scenario.

The makeup-air relationship must not be simplified into exact numerical equality. The Mechanical Code uses an approximate relationship and also requires the makeup arrangement not to reduce exhaust effectiveness. A future synthetic requirement should therefore state the intended pressure relationship, capture objective, normal variability, measurement uncertainty, and evidence needed to judge whether the relationship was preserved.

### 2. Laboratory safety and ventilation sources

[OSHA 29 CFR 1910.1450](https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.1450) applies when hazardous chemicals are used on a laboratory scale under the regulation's conditions. It requires a written Chemical Hygiene Plan and measures ensuring that fume hoods and other protective equipment function properly. This matters architecturally: the approved CHP, local SOPs, inspection criteria, and equipment-specific test procedures may be more direct sources of operational intent than a generic national standard.

The consensus sources most likely to inform a realistic laboratory package are:

- [ANSI/ASSP Z9.5-2022](https://webstore.ansi.org/standards/asse/ansiasspz92022), Laboratory Ventilation.
- [NFPA 45-2024](https://www.nfpa.org/product/nfpa-45-standard-on-fire-protection-for-laboratories-using-chemicals/p0045code), fire protection for laboratories using chemicals.
- [NFPA 91-2026](https://www.nfpa.org/codes-and-standards/nfpa-91-standard-development/91), exhaust systems conveying vapors, gases, mists, and particulate solids.
- [ANSI/ASHRAE Standard 110-2016 (RA 2025)](https://www.ashrae.org/technical-resources/technical-faqs), with its [June 24, 2026 erratum](https://www.ashrae.org/file%20library/technical%20resources/standards%20and%20guidelines/standards%20errata/standards/110-2016-ra-2025--errata--06-24-2026-.pdf), for laboratory fume-hood performance testing.
- ANSI/ASHRAE Standards 41.2-2026 and 41.3-2025 for air-velocity and pressure measurement methods.
- ANSI/ASHRAE Standard 111-2024 for field measurement, testing, adjusting, and balancing.

These should be treated as a **review pack**, not as interchangeable sources. NFPA 45 focuses on fire protection in chemical laboratories; Z9.5 addresses laboratory ventilation practice; NFPA 91 addresses exhaust-system fire and explosion concerns; ASHRAE 110 is a hood test method; the ASHRAE 41-series and Standard 111 address measurement and field procedures. None, by title or scope alone, creates the complete duty/standby and pressure-cascade requirement now needed.

Environmental permits may also control discharge, monitoring, and recordkeeping. New York air-permitting and process-source rules, including 6 NYCRR Parts 200, 201, 211, and 212, are conditional on the fictional emission source. They should enter the applicable baseline only after the material and emission profile is declared. See the [New York air-resources regulations index](https://dec.ny.gov/regulatory/regulations/chapter-iii). The [EPA overview of the Clean Air Act](https://www.epa.gov/laws-regulations/summary-clean-air-act) similarly shows that federal requirements are source- and pollutant-dependent.

### 3. Commissioning authority and evidence

[ANSI/ASHRAE/IES Standard 202-2024](https://www.ashrae.org/technical-resources/bookstore/commissioning) and [ASHRAE Guideline 0-2019](https://www.ashrae.org/technical-resources/bookstore/commissioning) should shape the product's authority model now. FacilityOps should preserve distinct objects or records for:

- The approved or simulation-accepted requirement.
- The verification or replay plan.
- The computed result.
- The supporting and contradictory evidence.
- The issue or deficiency.
- Human review, disposition, waiver, and acceptance.
- Corrective action and retest.

A FacilityOps `CONFORMING` result must never be represented as commissioning acceptance. Likewise, a `NONCONFORMING` result is evidence of a bounded mismatch under stated conditions, not a self-executing deficiency declaration with contractual or safety authority.

[ASHRAE Standard 230-2022](https://www.ashrae.org/technical-resources/standards-and-guidelines/titles-purposes-and-scopes) is useful for the later existing-building and operational lifecycle: investigation of unacceptable performance, corrective action, reverification, and handoff. [ASHRAE Guideline 1.1-2025](https://www.ashrae.org/technical-resources/standards-and-guidelines/titles-purposes-and-scopes) adds current HVAC&R commissioning detail, including operability, maintainability, documentation, issues, systems manuals, and training. These support durable incident and recovery evidence but do not establish the process-exhaust design.

### 4. Requirements and traceability

[ISO/IEC/IEEE 29148:2018](https://www.iso.org/standard/72089.html) remains current after confirmation in 2024. FacilityOps should use a deliberately small subset of its requirements-engineering discipline. Every executable requirement should eventually have:

- A stable identifier and version.
- A source and source status.
- Rationale and technical basis.
- Applicability, scope, mode, and preconditions.
- Assumptions and exclusions.
- Parameter values, units, tolerances, persistence, and effective interval.
- Required evidence and explicit sufficiency rules.
- A deterministic verification method.
- Links to replay cases, findings, and human disposition.

This is a compatibility reference, not a project claim of full 29148 conformance.

### 5. Control intent, CDL, replay, and the FacilityOps boundary

[ANSI/ASHRAE Standard 231-2026](https://data.ashrae.org/standard231/) now publishes the Control Description Language (CDL). It is not merely a proposal. CDL provides a declarative, graphical, human- and machine-readable language for building environmental control sequences and supports specification, implementation/translation, documentation, and simulation.

Current ASHRAE material calls the exchange representation **Control eXchange Format (CXF)**. If the optional comparison is built, the project should use that term, pin the referenced Standard 231 resources and implementation version, and avoid treating an unversioned repository branch or the older `CDL-JSON` label as the normative source.

FacilityOps should study CDL and may express one bounded duty/standby controller transition in both CDL and the future FacilityOps requirement format. It should not build a general CDL engine now. CDL can represent expected controller behavior; it does not establish:

- Correct field wiring or point mapping.
- Sensor or actuator installation and accuracy.
- Fan rotation or delivered airflow.
- Zone or duct pressure response.
- Treatment and makeup-air performance.
- Evidence freshness, conflict, or sufficiency.
- Facility consequence or incomplete recovery.

[OpenBuildingControl verification](https://obc.lbl.gov/specification/verification.html) is the closest public replay precedent. It compares real-controller output time series with a simulated CDL sequence using common inputs, captured parameters, mappings, unit conversions, and explicit value/time tolerances. Its most useful contribution is also its explicit limit: the method does not verify correct I/O connection, correct sensor/actuator installation, mechanical-equipment function, or envelope performance. FacilityOps should reuse the reproducibility patterns and occupy the heterogeneous field-evidence side of that boundary.

[BSR/ASHRAE Standard 236P](https://www.ashrae.org/technical-resources/standards-and-guidelines/titles-purposes-and-scopes) remains proposed. Its public scope describes pass/fail scripts for bench testing controller programming through BACnet without physical sensors or devices. It must be monitored, not treated as a published standard or a FacilityOps compliance basis.

[ASHRAE Guideline 36-2024](https://www.ashrae.org/technical-resources/standards-and-guidelines/titles-purposes-and-scopes) is a strong specimen for how to make control intent testable. FacilityOps should study its modes, state transitions, timers, deadbands, resets, fault handling, point requirements, and functional tests. It should not copy a Guideline 36 HVAC sequence into the process-exhaust scenario unless the sequence and equipment actually match. Published addenda and errata, including [Addendum a approved February 27, 2026](https://www.ashrae.org/file%20library/technical%20resources/standards%20and%20guidelines/standards%20addenda/g36_2024_a_20260227.pdf), must be versioned separately.

### 6. Time, units, and provenance

The immediate observation model needs conventions before it needs a building ontology.

- [RFC 3339](https://www.rfc-editor.org/info/rfc3339/) should govern serialized date-time strings. Store event, receive, and evaluation time separately. An offset or `Z` value does not establish synchronization, clock source, resolution, uncertainty, or trust.
- [W3C PROV-DM](https://www.w3.org/TR/prov-dm/) should be studied as a compatibility model for entities, activities, agents, derivation, responsibility, and versioned bundles. A small native provenance record is sufficient now; RDF/OWL is not required.
- The [BIPM SI Brochure, ninth edition, updated June 2026](https://www.bipm.org/en/si-brochure-9), should guide canonical quantities and units. FacilityOps should preserve raw unit/value, normalized unit/value, transformation identity, rounding, and conversion version.

These sources help make evidence reproducible. They cannot make bad mappings, stale sensors, false indications, or invalid rules correct.

### 7. Protocol, OT security, and alarm boundaries

[ANSI/ASHRAE Standard 135-2024](https://www.ashrae.org/technical-resources/standards-and-guidelines/titles-purposes-and-scopes) is the current published BACnet standard. A future read-only adapter should retain native object and property identity, engineering units, status flags, reliability, out-of-service state, priority/override evidence, source timestamp when available, and FacilityOps receive time. BACnet/SC improves communication security; it does not prove semantic correctness or physical response. BACnet conformance testing under Standard 135.1-2023 is protocol conformance, not facility conformance.

[NIST SP 800-82 Rev. 3](https://csrc.nist.gov/pubs/sp/800/82/r3/final) explicitly includes building automation and physical-environment monitoring within OT. The current published revision is Rev. 3; [Rev. 4 is only in a pre-draft call-for-comments stage](https://csrc.nist.gov/pubs/sp/800/82/r4/iprd). NIST and the [ISA/IEC 62443 series](https://www.isa.org/standards-and-publications/isa-standards/isa-iec-62443-series-of-standards) support a passive architecture with defined ownership, least privilege, segmentation, change control, asset inventory, audit logs, and no route from the analysis layer to physical command.

[ANSI/ISA-18.2-2016](https://www.isa.org/products/ansi-isa-18-2-2016-management-of-alarm-systems-for) should influence terminology but not create an alarm subsystem now. FacilityOps should keep these distinct:

- Source alarm or event.
- Canonical observation and point condition.
- Inferred state.
- Conformance finding.
- Operator notification.
- Managed alarm requiring a defined response.

## Controlled reference register

The register below is intentionally tiered. `NOW` means it affects the present architecture or first requirement pack. `STUDY` means use it for a bounded comparison. `CONDITIONAL` means the applicability trigger must be declared. `LATER` means preserve awareness but do not expand the current scope.

### A. Jurisdiction, laboratory, exhaust, and measurement

| Source | Current or applicable status | Trigger | Timing | FacilityOps boundary |
|---|---|---|---|---|
| [2025 NYS Uniform Code books](https://dos.ny.gov/rule-text-uniform-code-0) | Adopted; generally effective 2025-12-31 | Fictional facility in NYS outside NYC | NOW | Store jurisdiction, adopted edition, amendments, enforcement status, and applicability basis |
| [2025 Mechanical Code of NYS](https://dos.ny.gov/system/files/documents/2025/07/2025mcnys_noa_2025-07-24.pdf) | Adopted | Mechanical/exhaust systems within scope | NOW | Chapter 5 and Section 509 shape the exhaust profile; no compliance claim until use/hazard applicability is reviewed |
| [2025 Building Code of NYS](https://codes.iccsafe.org/content/NYSBC2025P1) | Adopted | Occupancy, construction, fire area, hazardous materials, HPM, special systems | CONDITIONAL | Required to resolve Mechanical Code cross-references and facility classification |
| [2025 Fire Code of NYS](https://codes.iccsafe.org/content/NYSFC2025P1) | Adopted | Hazardous materials, operational permits, detection, treatment, emergency/standby power, fire protection, and emergency planning | CONDITIONAL | Required to resolve material and operational triggers; none is universal without the triggering facts |
| 2025 Existing Building and Property Maintenance Codes of NYS | Adopted | Existing-building work or operational maintenance condition | CONDITIONAL | Track construction/alteration/maintenance context rather than mixing all provisions |
| [2025 ECCCNYS and NYS ASHRAE 90.1-2025](https://dos.ny.gov/rule-text-part-1240-energy-code) | Adopted; NYS document is based on ASHRAE 90.1-2022 | Regulated energy-code work | LATER | Energy compliance is not the first golden proof; record adopted basis separately from publisher-current ASHRAE edition |
| NFPA 70-2023 | Edition incorporated by New York's final 2025 rules; NFPA 70-2026 is publisher-current | Electrical installation within adopted scope | CONDITIONAL | Preserve adopted versus publisher-current editions; do not infer power availability from breaker indication alone |
| [OSHA 29 CFR 1910.1450](https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.1450) | Federal regulation | Laboratory use of hazardous chemicals | NOW-CONDITIONAL | Makes the CHP and local protective-equipment program candidate authoritative sources |
| [OSHA 29 CFR 1910.94](https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.94) | Federal regulation | Specific covered ventilation operations | CONDITIONAL | Not a universal laboratory-ventilation standard |
| [NY air rules, including 6 NYCRR Parts 200, 201, 211, and 212](https://dec.ny.gov/regulatory/regulations/chapter-iii) | State regulation | Emission source, pollutant, process, permit, or registration triggers | CONDITIONAL | Model permit/monitoring requirements only after a fictional emissions profile exists |
| Clean Air Act and applicable 40 CFR source standards | Federal law/regulation | Source category, pollutant, quantity, or permit trigger | CONDITIONAL | Do not infer a NESHAP or emission limit without the source profile |
| [ANSI/ASSP Z9.5-2022](https://webstore.ansi.org/standards/asse/ansiasspz92022) | Published consensus standard | Laboratory ventilation selected or incorporated | NOW-REVIEW | Candidate technical-practice source; exact requirements require licensed review and domain approval |
| [NFPA 45-2024](https://www.nfpa.org/product/nfpa-45-standard-on-fire-protection-for-laboratories-using-chemicals/p0045code) | Publisher-current; referenced by specified 2025 NYS Fire Code provisions, including the qualifying higher-education-laboratory pathway | Laboratory using chemicals plus an incorporation, contract, project, or site trigger | NOW-REVIEW | Fire-protection source, not a complete control sequence; the higher-education pathway does not cover every research laboratory |
| [NFPA 91-2026](https://www.nfpa.org/codes-and-standards/nfpa-91-standard-development/91) | Publisher-current | Covered exhaust conveying vapors, gases, mists, or particulate solids | NOW-REVIEW | Fire/explosion and exhaust-system reference; applicability is process-specific |
| [ASHRAE 110-2016 (RA 2025)](https://www.ashrae.org/technical-resources/technical-faqs) | Current reaffirmed edition; 2026-06-24 erratum | A laboratory fume hood enters the topology or evidence pack | CONDITIONAL | Hood containment test evidence is not whole-system or room-pressure proof |
| ASHRAE 62.1-2022 (NYS referenced edition); ASHRAE 62.1-2025 (publisher-current) | NYS Mechanical Code references the 2022 edition only at specified general-ventilation provisions | General ventilation/IAQ | CONDITIONAL | Not a hazardous-process exhaust or containment-cascade authority |
| [ASHRAE 41.2-2026 and 41.3-2025](https://www.ashrae.org/technical-resources/standards-and-guidelines/titles-purposes-and-scopes) | Published test-method standards | Actual air-velocity or pressure measurement is modeled | LATER | Influence measurement metadata and test evidence, not synthetic thresholds |
| [ASHRAE 111-2024](https://www.ashrae.org/technical-resources/standards-and-guidelines/titles-purposes-and-scopes) | Published field-practice standard | Field measurement, testing, adjusting, and balancing | LATER | A field result requires instrument, setup, uncertainty, and test context |

### B. Commissioning, controls, requirements, data, and interfaces

| Source | Status | Timing | FacilityOps use and limit |
|---|---|---|---|
| [ASHRAE/IES 202-2024](https://www.ashrae.org/technical-resources/bookstore/commissioning) | Published standard | NOW | Separate requirements, verification, issues, documentation, and human acceptance |
| [ASHRAE Guideline 0-2019](https://www.ashrae.org/technical-resources/bookstore/commissioning) | Published guideline | NOW | OPR and commissioning-process concepts; use `ACCEPTED_FOR_SIMULATION` for the fictional owner basis |
| [ASHRAE 230-2022](https://www.ashrae.org/technical-resources/standards-and-guidelines/titles-purposes-and-scopes) | Published standard | NOW/LATER | Existing-system investigation, correction, reverification, handoff, and ongoing commissioning |
| ASHRAE Guidelines 1.1-2025, 1.2-2019, and 1.4-2019 | Published guidelines | NOW/LATER | New/existing HVAC&R commissioning detail and systems-manual concepts |
| [ASHRAE Guideline 36-2024](https://www.ashrae.org/technical-resources/standards-and-guidelines/titles-purposes-and-scopes) | Published guideline with addenda | NOW-STUDY | Testable sequence patterns; not the process-exhaust design source |
| ASHRAE Guideline 11-2021 | Published guideline | LATER | Field-test configuration, component identity, instrumentation, adjustment, measured performance, and documentation; a component test is not system validation |
| ASHRAE Guideline 13-2024 | Published guideline | LATER | BAS specification, I/O, communications, testing, and documentation reference |
| [ASHRAE 231-2026 / CDL](https://data.ashrae.org/standard231/) | Published standard | STUDY | Optional one-sequence comparison; do not build a general CDL engine now |
| [OpenBuildingControl verification](https://obc.lbl.gov/specification/verification.html) | LBNL research specification/prototype | STUDY | Reuse replay, parameter, mapping, unit, and tolerance concepts; it does not validate field performance |
| [BSR/ASHRAE 236P](https://www.ashrae.org/technical-resources/standards-and-guidelines/titles-purposes-and-scopes) | Proposed standard | MONITOR | No compliance claim or dependency until publication and exact scripts are known |
| BSR/ASHRAE 223P | Proposed semantic-model standard | STUDY/LATER | Preserve stable identities and versioned topology; do not claim 223 compliance or implement a full graph now |
| ASHRAE/IBPSA 232-2024 | Published metaschema standard | REFERENCE | Schema-documentation concepts only; it is not a facility ontology or control-intent language |
| [Project Haystack](https://project-haystack.org/) and [Brick Schema](https://brickschema.org/) | Community/open semantic specifications, not adopted regulatory standards | STUDY/LATER | Study mapping and export compatibility; pin the exact project release if used and do not force the first proof into a universal ontology |
| [ASHRAE 135-2024](https://www.ashrae.org/technical-resources/standards-and-guidelines/titles-purposes-and-scopes) | Published BACnet standard | COMPATIBILITY NOW; ADAPTER LATER | Preserve native protocol semantics and quality; keep adapter read-only |
| ASHRAE 135.1-2023 | Published BACnet test standard | LATER | Protocol conformance does not establish semantic, mapping, or physical conformance |
| [ISO/IEC/IEEE 29148:2018](https://www.iso.org/standard/72089.html) | Current; confirmed 2024 | NOW | Light requirements identity, source, scope, rationale, assumptions, and traceability pattern |
| [RFC 3339](https://www.rfc-editor.org/info/rfc3339/) | Internet standards-track specification | NOW | Serialized timestamps; separate clock quality, uncertainty, lateness, and staleness |
| [W3C PROV-DM](https://www.w3.org/TR/prov-dm/) | W3C Recommendation | NOW-COMPATIBILITY | Transformation and evaluation lineage; use a small native subset |
| [BIPM SI Brochure, 9th ed., updated 2026](https://www.bipm.org/en/si-brochure-9) | Current SI reference | NOW | Quantity/unit normalization while preserving the raw source representation |
| [ANSI/ISA-18.2-2016](https://www.isa.org/products/ansi-isa-18-2-2016-management-of-alarm-systems-for) and [IEC 62682:2022](https://webstore.iec.ch/en/publication/65543) | Published standards | TERMINOLOGY NOW; LATER IMPLEMENTATION | Findings are not automatically alarms; rationalize any future operator alarm separately |
| [NIST SP 800-82 Rev. 3](https://csrc.nist.gov/pubs/sp/800/82/r3/final) | Current published revision; Rev. 4 pre-draft underway | NOW-BOUNDARY | Passive/read-only OT architecture, ownership, logging, least privilege, and risk controls |
| [ISA/IEC 62443 series](https://www.isa.org/standards-and-publications/isa-standards/isa-iec-62443-series-of-standards) | Multi-part published series under continuous development | LATER PROGRAM; NOW PRINCIPLES | Asset-owner, system, component, zones/conduits, lifecycle, and supplier security references |
| [IEC 61131-3:2025](https://webstore.iec.ch/en/publication/68533) | Edition 4.0, published | STUDY/LATER | Understand PLC program representations; FacilityOps does not program or validate a PLC merely by reading tags |
| [Modbus Application Protocol V1.1b3](https://www.modbus.org/docs/Modbus_Application_Protocol_V1_1b3.pdf) | Public protocol specification | ADAPTER LATER | Addresses and register interpretations require versioned device mappings; protocol has no self-describing engineering semantics |
| [OPC UA 1.05 online reference](https://reference.opcfoundation.org/) | Maintained OPC specification; parts have independent release versions | ADAPTER LATER | Preserve NodeIds, status codes, source/server timestamps, data types, and namespace/model versions |
| [MQTT Version 5.0](https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html) | OASIS Standard | INTEGRATION LATER | Transport semantics do not by themselves define industrial identity, units, state, or validity |
| [Eclipse Sparkplug 3.0](https://sparkplug.eclipse.org/specification/version/3.0/) | Eclipse Foundation specification | STUDY/LATER | Industrial MQTT topic, payload, birth/death, and state-awareness reference; still requires mapping and evidence validation |

### C. Later equipment and sector reference families

These sources belong in the long-term registry, but not in the first process-exhaust requirement pack unless the named trigger is added.

| Domain | Reference families | Trigger and timing | Boundary |
|---|---|---|---|
| Electrical installation | [NFPA 70-2026](https://www.nfpa.org/product/nfpa-70-national-electrical-code-nec/p0070code/nfpa-70-national-electrical-code-nec-2026/7026sb) publisher-current; New York currently incorporates the 2023 edition | Electrical design/installation; CONDITIONAL | Code compliance cannot be inferred from telemetry |
| Electrical safe work | [NFPA 70E-2027](https://www.nfpa.org/education-and-research/electrical/learn-more-about-nfpa-70e); [OSHA 29 CFR 1910.333](https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.333) | Energized work, boundaries, PPE, and safe work practices; NOW as a boundary, LATER as a record domain | FacilityOps cannot authorize work, establish deenergization, select PPE, or determine an electrically safe work condition |
| Hazardous-energy control | [OSHA 29 CFR 1910.147](https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.147) | Servicing or maintenance with unexpected energization, startup, or stored-energy exposure | NOW as a hard authority boundary; LATER for records | FacilityOps cannot authorize LOTO, declare isolation, or substitute telemetry for an energy-isolating device |
| Electrical maintenance | [NFPA 70B-2026](https://www.nfpa.org/product/nfpa-70b-standard-for-electrical-equipment-maintenance/p0070bcode); [ANSI/NETA MTS-2023](https://www.netaworld.org/standards/ansi-neta-mts); manufacturer and owner programs | Electrical maintenance program and condition assessment; LATER | Test results require asset identity, method, instrument, condition, limits, and human disposition |
| Electrical acceptance/commissioning | [ANSI/NETA ATS-2025](https://www.netaworld.org/standards/ansi-neta-ats); [ANSI/NETA ECS-2024](https://www.netaworld.org/standards/ansi-neta-ecs) | New or modified power-system acceptance/commissioning; LATER | Do not turn EPMS indications into acceptance-test or commissioning-acceptance evidence without the actual controlled record |
| Emergency and stored-energy power | [NFPA 110-2025](https://www.nfpa.org/product/nfpa-110-standard-for-emergency-and-standby-power-systems/p0110code/nfpa-110-standard-for-emergency-and-standby-power-systems-2025/11025) and [NFPA 111-2025](https://www.nfpa.org/product/nfpa-111-standard/p0111code) | Generator, ATS, UPS, or stored-energy emergency/standby systems | Equipment availability must remain an inference supported by independent evidence |
| Power-system studies | [IEEE 1584-2018](https://standards.ieee.org/ieee/1584/5802/) with errata; IEEE 1584.1-2022; IEEE 1584.2-2025; applicable [IEEE 3000-series](https://standards.ieee.org/products-programs/ieee-3000/) parts | Arc-flash, load-flow, short-circuit, grounding, motor-starting, protection, reliability, or maintenance study | Register exact part and project-effective study; never cite “IEEE 3000” as one requirement |
| Fire alarm and suppression | [NFPA 72-2025](https://www.nfpa.org/product/nfpa-72-national-fire-alarm-and-signaling-code/p0072code), [NFPA 13-2025](https://www.nfpa.org/product/nfpa-13-standard-for-the-installation-of-sprinkler-systems/p0013code), [NFPA 20-2025](https://www.nfpa.org/product/nfpa-20-standard-for-the-installation-of-stationary-pumps-for-fire-protection/p0020code/nfpa-20-standard-for-the-installation-of-stationary-pumps-for-fire-protection-2025/2025), and [NFPA 25-2026](https://www.nfpa.org/product/nfpa-25-standard-for-the-inspection-testing-and-maintenance-of-water-based-fire-protection-systems/p0025code) | Fire alarm, sprinkler, fire pump, and inspection/testing scope | Life-safety acceptance and impairment authority remain outside FacilityOps |
| Integrated life-safety testing | [NFPA 4-2027](https://www.nfpa.org/codes-and-standards/nfpa-4-standard-development/4) publisher-current; New York Fire Code references NFPA 4-2024 at specified provisions | Code- or project-required integrated testing | Cross-system plans and evidence do not authorize a generic controls test or FacilityOps acceptance |
| HVAC fire/smoke | [NFPA 90A-2027](https://www.nfpa.org/product/nfpa-90a-standard/p0090acode/nfpa-90a-standard-2027/90a27) publisher-current; [NFPA 92-2024](https://link.nfpa.org/all-publications/92/2024) publisher-current; New York Fire Code references NFPA 92-2021 at specified provisions; ASHRAE Guideline 1.5-2025 | Smoke control or HVAC/fire interfaces | Keep normal process-exhaust state and smoke-control state separate; adopted editions may lag publisher-current editions |
| Refrigeration | ASHRAE 15-2024 and applicable IIAR standards | Refrigerants, machinery rooms, or ammonia systems | Add only after refrigerant/system profile is declared |
| Functional safety | IEC 61508 and applicable ISA/IEC 61511 lifecycle requirements | A declared safety-instrumented function or safety system | No current implementation; FacilityOps cannot become the safety authority or infer SIS validation from ordinary control telemetry |
| Boilers, pressure vessels, and piping | ASME BPVC, NBIC, ASME B31.1/B31.3, adopted state rules | Boiler, pressure vessel, power piping, or process piping | Inspection jurisdiction, edition, owner program, and service conditions control applicability |
| Hazardous materials and process safety | NYS Fire/Building Codes; NFPA 30, 55, and 400; OSHA 1910.119; EPA 40 CFR Part 68 | Material, quantity, process, and threshold triggers | Never infer PSM/RMP or hazardous occupancy from a generic “critical facility” label |
| Cleanrooms and particles | [ISO 14644-1:2015](https://www.iso.org/standard/53394.html), [14644-2:2015](https://www.iso.org/standard/53393.html), [14644-3:2019](https://www.iso.org/standard/60598.html), [14644-4:2022](https://www.iso.org/standard/72379.html), and ISO 14644-5:2025; [ISO 21501-4:2018](https://www.iso.org/standard/58073.html) + [Amd 1:2023](https://www.iso.org/standard/80991.html) | Approved cleanroom class, monitoring plan, testing, operations, or particle-counter evidence | ISO particle classification is not a room-pressure or fan-response requirement; positive product-protection pressure can conflict with hazardous-containment intent |
| Semiconductor fabrication | NFPA 318-2025 and applicable hazardous-production-material provisions | Semiconductor-fabrication/HPM profile | Conditional specialized pack; not implied by “advanced materials” |
| Pharmaceutical/life science | 21 CFR Parts 210/211, applicable GMP guidance, quality-system requirements | Regulated drug manufacturing or laboratory scope | Quality approval and validated-system authority remain with the regulated organization |
| Healthcare | NFPA 99-2024, ASHRAE 170, FGI and CMS-adopted requirements | Healthcare occupancy or patient-care function | Not applicable to the present fictional research facility without an explicit change |
| Data centers | ASHRAE 90.4, ASHRAE TC 9.9 guidance, NFPA 75, owner tier/resilience requirements | Data-center systems and performance objectives | A useful adjacent domain, not a basis for the process-exhaust proof |
| General HVAC maintenance | ASHRAE 180-2018 and owner/manufacturer maintenance programs | Commercial HVAC inspection and maintenance | Maintenance evidence and conformance to control intent are separate determinations |

Edition monitoring matters even in deferred domains. ISO 14644-1:2015 and -2:2015 remain current but entered systematic review on July 15, 2026. ISO 21501-4:2018 with Amendment 1:2023 remains the current published basis while replacement work is underway. Proposed or in-development replacements must not silently become project-effective editions.

## Minimum source basis for the first golden proof

The first requirement pack should use only the sources needed to make one scenario traceable and honest.

### Required declarations before implementation

1. **Jurisdiction profile:** New York State outside New York City; assumed AHJ; applicable 2025 code set and known amendments/enforcement actions.
2. **Facility status:** new, existing, or altered fictional facility.
3. **Use and hazard profile:** laboratory versus production; high-level fictional chemical/process categories; whether hazardous exhaust provisions are assumed applicable.
4. **System profile:** shared manifold, fire-area assumption, duty/standby arrangement, treatment component, makeup-air dependency, and pressure-boundary topology.
5. **Authority profile:** every project-authored requirement is `SYNTHETIC` and may be `ACCEPTED_FOR_SIMULATION`; none is code approved, owner approved, or commissioning accepted.
6. **Source access:** exact licensed or official text used for any clause-level abstraction, with no protected full text copied into the repository.
7. **Domain review:** laboratory-ventilation or commissioning practitioner review before the scenario is represented as typical field practice.

### First requirement pack

| Element | Recommended source basis | Current disposition |
|---|---|---|
| Duty-fan failure and standby response | Project-authored SOO informed by MCNYS applicability review, Z9.5/NFPA 45/NFPA 91 review, and Guideline 36 structure | `SYNTHETIC`, `ACCEPTED_FOR_SIMULATION` only |
| Pressure relationship | Project-authored OPR/SOO with declared basis, units, normal variability, uncertainty, persistence, and recovery condition | No numerical value until separately approved |
| Required observations | Project topology plus measurement/test-method references | Fan command/status, VFD/electrical, airflow, duct pressure, zone differential pressure, treatment, makeup air, and time/quality evidence |
| Conformance process | ASHRAE 202/Guideline 0 concepts plus ISO/IEC/IEEE 29148 traceability | Computed finding separated from human review and acceptance |
| Replay | OpenBuildingControl concepts plus FacilityOps evidence-sufficiency rules | Retain data, mapping, parameters, units, tolerances, versions, and evaluation code identity |
| Time and provenance | RFC 3339, W3C PROV concepts, SI reference | Separate event/receive/evaluation time; preserve raw and normalized values and derivations |

### Golden cases required

- Successful standby response with sufficient, agreeing evidence.
- Failed standby start.
- Command-versus-status discrepancy.
- Status-versus-independent-airflow discrepancy.
- Stale or late evidence.
- Missing required evidence.
- Conflicting pressure or electrical evidence.
- Pressure-cascade degradation.
- Successful recovery with defined evidence.
- Incomplete recovery with an explicit unverified remainder.

The expected result should be one of `CONFORMING`, `NONCONFORMING`, `INDETERMINATE`, or `NOT_APPLICABLE`. A binary pass/fail model is not adequate when the evidence cannot support a valid conclusion.

## What must not be encoded from this report

- No copyrighted clause text or large standard excerpts.
- No universal pressure, airflow, alarm, delay, timer, deadband, or recovery values.
- No code-compliance, safety, commissioning-acceptance, or certification conclusion.
- No assumption that a publisher-current edition is the adopted or project-effective edition.
- No inference that controller command/status proves physical equipment response.
- No inference that a protocol-quality flag proves sensor accuracy or mapping correctness.
- No automatic conversion of an abnormal condition or conformance finding into an operator alarm.
- No general CDL engine, universal sequence language, full RDF ontology, or multi-sector standards platform.
- No live control, write authority, or functional-test actuation against an external system.

## Decisions supported by this baseline

1. **Proceed with the golden proof.** Standards research does not justify a broad implementation pause.
2. **Use a FacilityOps-native minimum requirement and evidence model.** Study CDL, OpenBuildingControl, and 236P; do not make them the first conformance engine.
3. **Declare the fictional applicability profile before writing the first executable requirement.** The present facility description is intentionally incomplete.
4. **Make source status and human authority first-class.** A computed result and an accepted result are different records.
5. **Treat standards as versioned sources, not executable truth.** Clause abstraction, parameter selection, mapping, and rules all require separate review.
6. **Add exact clause research only for the requirement pack being implemented.** Expand the register when a new equipment or sector scenario enters scope.

## Open decisions before encoding

The next project discussion should resolve:

- The minimum fictional use/hazard profile for the flagship facility.
- Whether the first code-linked requirement will cite a code section directly or cite a project-authored SOO informed by the code review.
- The review states and human roles permitted in a fictional laboratory.
- The source, applicability, requirement, parameter, evidence, test, finding, and disposition relationships.
- How addenda, errata, jurisdictional amendments, enforcement actions, and superseded versions are represented.
- How licensed source text is kept out of repository data while retaining a precise citation.
- Which fields are required now versus deferred until the first requirement pack proves their need.

## Primary-source index

- [New York Department of State — Notice of Adoption and current enforcement update](https://dos.ny.gov/notice-adoption)
- [New York final amended Uniform Code rule text](https://dos.ny.gov/rule-text-uniform-code-0)
- [New York final amended Energy Code rule text](https://dos.ny.gov/rule-text-part-1240-energy-code)
- [2025 Mechanical Code of New York State](https://dos.ny.gov/system/files/documents/2025/07/2025mcnys_noa_2025-07-24.pdf)
- [2025 Building Code of New York State](https://codes.iccsafe.org/content/NYSBC2025P1)
- [2025 Fire Code of New York State](https://codes.iccsafe.org/content/NYSFC2025P1)
- [OSHA 29 CFR 1910.1450](https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.1450)
- [ANSI/ASSP Z9.5-2022](https://webstore.ansi.org/standards/asse/ansiasspz92022)
- [NFPA 45-2024](https://www.nfpa.org/codes-and-standards/nfpa-45-standard-development/45)
- [NFPA 91-2026](https://www.nfpa.org/codes-and-standards/nfpa-91-standard-development/91)
- [ASHRAE titles, purposes, and scopes](https://www.ashrae.org/technical-resources/standards-and-guidelines/titles-purposes-and-scopes)
- [ASHRAE commissioning resources](https://www.ashrae.org/technical-resources/bookstore/commissioning)
- [ASHRAE Standard 231 resource files](https://data.ashrae.org/standard231/)
- [LBNL OpenBuildingControl verification specification](https://obc.lbl.gov/specification/verification.html)
- [ISO/IEC/IEEE 29148:2018 status](https://www.iso.org/standard/72089.html)
- [RFC 3339](https://www.rfc-editor.org/info/rfc3339/)
- [W3C PROV-DM](https://www.w3.org/TR/prov-dm/)
- [BIPM SI Brochure](https://www.bipm.org/en/si-brochure-9)
- [NIST SP 800-82 Rev. 3](https://csrc.nist.gov/pubs/sp/800/82/r3/final)
- [ISA/IEC 62443 series overview](https://www.isa.org/standards-and-publications/isa-standards/isa-iec-62443-series-of-standards)
- [OPC UA online reference](https://reference.opcfoundation.org/)
- [OASIS MQTT 5.0](https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html)
- [Eclipse Sparkplug 3.0](https://sparkplug.eclipse.org/specification/version/3.0/)

---

**Use limitation:** This report is an engineering research baseline for a fictional facility and software laboratory. It is not legal advice, a code analysis for a real project, a design document, a commissioning record, or a determination of safety or compliance. A licensed design professional, qualified commissioning authority, responsible owner, employer, and authority having jurisdiction retain their respective real-world authority.
