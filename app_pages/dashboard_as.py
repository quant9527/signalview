"""AS dashboard page (url_path=dashboard_as)."""
from __future__ import annotations

import streamlit as st

from app_pages.dashboard import render_dashboard


def page_dashboard_as() -> None:
    """Render the A-share market dashboard."""
    st.set_page_config(layout="wide", page_title="AS Dashboard")
    render_dashboard("as")