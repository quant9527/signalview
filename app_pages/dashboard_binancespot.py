"""Binance Spot dashboard page (url_path=dashboard_binancespot)."""
from __future__ import annotations

import streamlit as st

from app_pages.dashboard import render_dashboard
from constants import EXCHANGE_BINANCE_SPOT


def page_dashboard_binancespot() -> None:
    """Render the Binance spot dashboard."""
    st.set_page_config(layout="wide", page_title="Binance Spot Dashboard")
    render_dashboard(EXCHANGE_BINANCE_SPOT)
