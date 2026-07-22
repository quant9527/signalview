"""Unified Performance entry (url_path=performance).

Thin wrapper around root performance.py::render_performance(). The
preset picker sets main_signal + exchange + df in session_state;
render_performance() reads them.
"""
from __future__ import annotations

import streamlit as st

from constants import EXCHANGE_AS, EXCHANGE_THS
from performance import render_performance
from signal_constants import (
    PERFORMANCE_PRESET_AS_PREFIXES,
    PERFORMANCE_PRESET_THS_PREFIXES,
)
from utils import get_cached_data

_PRESETS = [
    (EXCHANGE_AS, PERFORMANCE_PRESET_AS_PREFIXES, EXCHANGE_AS),
    (EXCHANGE_THS, PERFORMANCE_PRESET_THS_PREFIXES, EXCHANGE_THS),
]
_LABELS = [p[0] for p in _PRESETS]


def page_performance() -> None:
    """Performance ranking (url_path=performance)."""
    st.set_page_config(layout="wide", page_title="Performance")
    st.header("Signal Performance vs Current Prices — Ranking")

    choice = st.selectbox("功能", options=_LABELS, key="performance_preset")
    for label, main_signal, exchange in _PRESETS:
        if label == choice:
            st.session_state.main_signal = main_signal
            st.session_state.exchange = exchange
            break

    # Legacy session_state fallbacks (no writer in this design beyond
    # the line above; downstream code in render_performance() reads these).
    st.session_state.setdefault("df", None)
    st.session_state.setdefault("exchange", EXCHANGE_AS)

    st.session_state.df = get_cached_data(45)
    render_performance()