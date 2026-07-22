"""Shared helpers for the K-line pages.

Internal module — do not register with st.navigation.

Currently exports query-params primitives used by both the
settings page (app_pages.kline) and the fullscreen page
(app_pages.kline_fullscreen). The flight-fetching and
chart-assembly helpers are fullscreen-only and stay there.
"""
from __future__ import annotations

from datetime import date


def qp_str(key: str) -> str:
    """Read a query-param string, trimmed; empty string if absent."""
    from streamlit import query_params
    return str(query_params.get(key, "") or "").strip()


def qp_bool(key: str) -> bool:
    """Read a query-param boolean: 1/true/yes are truthy."""
    from streamlit import query_params
    return str(query_params.get(key, "") or "").strip() in ("1", "true", "yes")


def parse_iso_date(s: str) -> date | None:
    """Parse YYYY-MM-DD (or any ISO prefix); None on empty/garbage."""
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None