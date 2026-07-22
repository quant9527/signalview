"""EM dashboard page (url_path=dashboard_em)."""
from __future__ import annotations

import streamlit as st

from app_pages.dashboard import render_dashboard


def page_dashboard_em() -> None:
    """Render the EM (emerging-market) dashboard."""
    st.set_page_config(layout="wide", page_title="EM Dashboard")
    render_dashboard("em")