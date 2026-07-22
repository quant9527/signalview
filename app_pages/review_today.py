"""Today Review: redirect to Search Signals with a preset (auto_recent_2d=1)."""
from __future__ import annotations

import streamlit as st

from app_pages.search_signals import page_search_signals

_SEARCH_PAGE = st.Page(
    page_search_signals, title="Search Signals", icon="🔍",
    url_path="search_signals",
)


def build_review_today_params() -> dict[str, str]:
    return {"auto_recent_2d": "1"}


def page_review_today() -> None:
    st.set_page_config(layout="wide", page_title="Today Review")
    st.header("📋 Today Review")
    st.caption("跳转到 Search Signals，preset：今日自动选近两日信号。")
    st.page_link(
        _SEARCH_PAGE,
        label="打开 Today Review",
        icon=":material/arrow_forward:",
        query_params=build_review_today_params(),
    )