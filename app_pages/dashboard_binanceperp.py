"""Binance Perp dashboard page (url_path=dashboard_binanceperp)."""
from __future__ import annotations

import streamlit as st

from app_pages.dashboard import render_dashboard
from constants import EXCHANGE_BINANCE_PERP


def page_dashboard_binanceperp() -> None:
    """Render the Binance perpetual dashboard."""
    st.set_page_config(layout="wide", page_title="Binance Perp Dashboard")
    render_dashboard(EXCHANGE_BINANCE_PERP)
