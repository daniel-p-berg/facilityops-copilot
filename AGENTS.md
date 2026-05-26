# AGENTS.md

This repository is for FacilityOps Copilot, a simulated BMS/EPMS monitoring stack for mission-critical facility operations.

## Project Purpose

The goal is to demonstrate how a building controls technician can use AI-assisted development to understand and work across the full stack: sample facility data, database storage, backend APIs, dashboards, and AI-generated operational analysis.

## Domain Context

BMS means building management system, such as Niagara, Schneider EcoStruxure, or similar platforms.

EPMS means electrical power monitoring system.

The project uses simulated data only. Do not use real customer data, real IP addresses, real credentials, proprietary exports, or vendor-specific confidential information.

## Equipment Types

Use realistic mission-critical facility equipment, including:

- UPS
- Generator
- ATS
- PDU
- CRAC
- AHU
- Chilled water pump
- Temperature sensor
- Humidity sensor
- Electrical meter

## Alarm Severity

Use these alarm severity levels:

- Critical
- High
- Medium
- Low

Critical alarms should be highlighted in summaries and reports.

## Coding Preferences

- Keep the code readable.
- Prefer simple Python before clever abstractions.
- Use SQLite for local database work.
- Use FastAPI for the backend.
- Use plain HTML or a minimal frontend at first.
- Add tests for analysis logic.
- Update documentation when behavior changes.

## Reporting Style

Reports should be written for facilities operations personnel, not software engineers.

The system should explain what happened, what equipment was affected, what the likely operational concern is, and what follow-up action an operator or technician should consider.
