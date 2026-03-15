# 📈 Signalview

A lightweight Streamlit app for visualizing trading signals stored in a PostgreSQL database and comparing them to latest market prices.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)]()

## Features

- Load trading signal records from PostgreSQL (table `signal`).
- Pages: **Overview**, **Top score**, **Market** — switch between views using the sidebar.
- Normalize signal timestamps to Asia/Shanghai (UTC+8) for display and charting.
- Compare latest market prices (via `akshare`) against the recorded signal price and export CSV of rankings.
- Safe error handling when DB or market data is unavailable.

## Requirements

- Python 3.10+
- Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

- The PostgreSQL connection string is defined in `streamlit_app.py` at the `conn_str` variable. Edit it to point to your database or replace this with a secure configuration method (environment variable or config file) before deploying.
- Market data (Market page) uses `akshare`. If `akshare` is not available, the app will show an informative error and continue to work for non-market pages.

## Run locally

```bash
streamlit run streamlit_app.py
```

## Contributing

Contributions and issues are welcome. Please open a GitHub issue or PR.

## License

See the `LICENSE` file for details.
