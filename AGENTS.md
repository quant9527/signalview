<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-25 | Updated: 2026-04-25 -->

# signalview

## Purpose
Streamlit web app for visualizing trading signals stored in a PostgreSQL database. Displays signal overviews, top-score rankings, and compares latest market prices (via akshare) against recorded signal prices. Exports ranked signals to CSV.

## Key Files
| File | Description |
|------|-------------|
| `streamlit_app.py` | Main Streamlit app entry point |
| `data.py` | PostgreSQL data fetching and signal loading |
| `performance.py` | Performance metrics calculation |
| `performance_table.py` | Performance table rendering |
| `constants.py` | Application constants |
| `signal_constants.py` | Signal-specific constants |
| `utils.py` | Utility functions |
| `flight_kline_client.py` | Flight K-line data client |
| `Dockerfile` | Docker deployment |
| `pyproject.toml` | Project dependencies (uv) |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `signalml/` | ML model artifacts and cached signal data (`.cache/signalml/`) |
| `sql/` | SQL schema definitions (`schema/`) and seed data (`data/`) |
| `scripts/` | Utility scripts for signal processing |
| `views/` | Page/view modules for Streamlit |
| `graphify-out/` | Code analysis output |
| `artifacts/` | Run artifacts and output |

## For AI Agents

### Working In This Directory
- Install: `uv sync` or `pip install -e .`
- Run: `streamlit run streamlit_app.py`
- PostgreSQL `conn_str` is defined in `streamlit_app.py` — edit before deploying
- Market data page uses akshare — graceful fallback if unavailable

### Testing Requirements
- No formal test suite — manual verification via Streamlit UI
- SQL schema in `sql/schema/` must match the PostgreSQL schema expected by `data.py`

### Architecture
- 3 main pages: **Overview**, **Top score**, **Market** (sidebar navigation)
- All timestamps normalized to Asia/Shanghai (UTC+8)
- Signals sourced from PostgreSQL `signal` table
- Market prices fetched via akshare for comparison

## Dependencies

### External
- streamlit — web UI framework
- psycopg2 — PostgreSQL client
- akshare — A-share market data (optional, for Market page)
- pandas — data processing

<!-- MANUAL: -->
