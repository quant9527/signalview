<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-08 | Updated: 2026-05-08 -->

# scripts

## Purpose
Utility scripts for signal processing and database queries, supporting the SignalView Streamlit app.

## Key Files
| File | Description |
|------|-------------|
| `query_signals.py` | Query and filter signals from PostgreSQL for batch analysis |

## Subdirectories
None.

## For AI Agents

### Working In This Directory
- Scripts are standalone utilities, not part of the main Streamlit app
- `query_signals.py` can be run independently to export signal data

### Testing Requirements
- Manual verification — no formal test suite

## Dependencies

### Internal
- `data.py` — PostgreSQL connection logic (from parent)

### External
- psycopg2 — PostgreSQL client
- pandas — data processing

<!-- MANUAL: -->
