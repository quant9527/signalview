"""Key Review: redirect to Search Signals with a preset (exchange=em)."""
from __future__ import annotations

import streamlit as st

from app_pages.search_signals import page_search_signals

_SEARCH_PAGE = st.Page(
    page_search_signals, title="Search Signals", icon="🔍",
    url_path="search_signals",
)


def build_review_key_params() -> dict[str, str]:
    return {"exchange": "em"}


def page_review_key() -> None:
    st.set_page_config(layout="wide", page_title="Key Review")
    st.header("📋 Key Review")
    st.caption("跳转到 Search Signals，preset：EM 行情。")
    st.page_link(
        _SEARCH_PAGE,
        label="打开 Key Review",
        icon=":material/arrow_forward:",
        query_params=build_review_key_params(),
    )