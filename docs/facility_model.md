# Northstar Data Hall Facility Model

Northstar Data Hall is the fictional legacy regression fixture and secondary data-center demonstration used for FacilityOps Copilot sample data. It represents a small environment where BMS and EPMS indications can be reviewed together to study cooling, power, and operational risk. It is not the standards-grounded flagship environment.

## Facility Purpose

Northstar Data Hall supports high-availability compute racks for internal business systems. The facility model focuses on alarm review, equipment context, and operator follow-up rather than live controls integration.

## Major Areas

- Data Hall A: Primary white space with IT racks and environmental sensors.
- Electrical Room A: UPS, ATS, PDU, and power monitoring equipment.
- Generator Yard: Standby generation equipment.
- Mechanical Room 1: Air handling equipment supporting facility airflow.
- Central Plant: Chilled water pumping equipment.
- Utility Service Entrance: Incoming electrical service and utility metering.

## BMS Scope

The BMS monitors and reports alarms for cooling and environmental systems, including:

- CRAC units
- AHUs
- Chilled water pumps
- Temperature sensors
- Humidity sensors

## EPMS Scope

The EPMS monitors and reports alarms for electrical infrastructure, including:

- UPS systems
- Generators
- ATS equipment
- PDUs
- Electrical meters

## Criticality Levels

- Critical: Equipment or sensors directly tied to continuity of data hall power or cooling.
- High: Important support equipment where failure can affect data hall operation.
- Medium: Monitoring points or equipment that provide early warning or environmental visibility.
- Low: Non-critical supporting points not currently represented in the sample inventory.

## Operating Assumptions

- All data is simulated and does not represent a live customer system.
- Northstar alarm rules and seeded operational context are local demonstration records, not controlled standards requirements, code-compliance evaluations, or qualified human dispositions.
- Alarm records may include both Active and Cleared states.
- Operators should review active Critical alarms first.
- Cooling and power alarms occurring near the same time should be reviewed together.
- Equipment context is used to help prioritize alarm response and explain operational impact.
