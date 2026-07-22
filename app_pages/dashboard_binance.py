"""Binance dashboard page (url_path=dashboard_binance)."""
from __future__ import annotations

import streamlit as st

from app_pages.dashboard import render_dashboard


def page_dashboard_binance() -> None:
    """Render the Binance market dashboard."""
    st.set_page_config(layout="wide", page_title="Binance Dashboard")
    render_dashboard("binance")