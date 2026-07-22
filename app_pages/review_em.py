"""EM Review: redirect to Search Signals with a preset (signals=NESTED_2BC_*)."""
from __future__ import annotations

import streamlit as st

from app_pages.search_signals import page_search_signals
from signal_constants import NESTED_2BC_SIGNAL_NAMES

_SEARCH_PAGE = st.Page(
    page_search_signals, title="Search Signals", icon="🔍",
    url_path="search_signals",
)


def build_review_em_params() -> dict[str, str]:
    return {"signals": ",".join(NESTED_2BC_SIGNAL_NAMES)}


def page_review_em() -> None:
    st.set_page_config(layout="wide", page_title="EM Review")
    st.header("📋 EM Review")
    st.caption("跳转到 Search Signals，preset：NESTED_2BC 系列信号。")
    st.page_link(
        _SEARCH_PAGE,
        label="打开 EM Review",
        icon=":material/arrow_forward:",
        query_params=build_review_em_params(),
    )