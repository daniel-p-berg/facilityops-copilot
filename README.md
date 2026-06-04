# FacilityOps Copilot

FacilityOps Copilot is a simulated BMS/EPMS monitoring stack for mission-critical facility operations.

The project uses sample building automation and electrical power monitoring data to demonstrate how alarms, equipment records, and trend values can be stored, analyzed, and summarized into an operations briefing.

## Project Goals

- Practice Git and GitHub workflow
- Build a simple full-stack application over time
- Model realistic BMS/EPMS alarm and trend data
- Create a local database for operational records
- Expose summary data through a backend API
- Build a simple dashboard for operations review
- Generate daily facility operations briefings
- Explore how AI-assisted coding can expand the capabilities of controls technicians

## Initial Scope

The first version uses simulated data only. It does not connect to live BMS, EPMS, Niagara, Schneider, BACnet, Modbus, or customer systems.

## Local SQLite Alarm Database

The sample alarm CSV can be loaded into a local SQLite database:

```bash
python3 analysis/load_alarm_db.py
```

The loader reads `data/sample_alarms.csv`, creates `db/facilityops.sqlite3`, and prints a verification summary with total records and alarm counts by severity, source, and equipment.

After loading the database, generate a database-backed daily briefing:

```bash
python3 analysis/generate_db_briefing.py
```

The database-backed briefing is written to `reports/daily_briefing_from_db.md`.

Generated database files are local development artifacts and are ignored by git.

## Running Tests

Run the standard-library unittest suite:

```bash
python3 -m unittest discover -s tests
```

## Planned Stack

- Git and GitHub
- Python
- SQLite
- FastAPI
- Pandas
- HTML dashboard
- Markdown reports
- AI-assisted coding tools

## Long-Term Vision

The long-term goal is to explore how AI agents could assist facilities teams by monitoring alarms, identifying recurring issues, summarizing equipment behavior, and helping operators understand the full context behind BMS and EPMS events.
