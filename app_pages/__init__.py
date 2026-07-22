"""Streamlit page modules for signalview.

This package is registered with `st.navigation` in `streamlit_app.py`.

Internal helpers (NOT registered in nav, do not call `st.Page` on them):
- `app_pages.dashboard`      — shared `render_dashboard(exchange)` for the three market pages.
- `app_pages.kline_charts`   — ECharts option builders used by the K-line pages.
- `app_pages._kline_common`  — query-params parsing and data assembly shared by K-line and fullscreen.
"""
