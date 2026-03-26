"""Unified Performance：通过「功能」选择预设的 main_signal 与默认 exchange。"""
from pathlib import Path

import streamlit as st

from constants import EXCHANGE_AS, EXCHANGE_THS

_PRESETS = [
    (
        EXCHANGE_AS,
        ("nested_2bc", "pair_seg", "cl3b_macd", "cmp"),
        EXCHANGE_AS,
    ),
    (
        EXCHANGE_THS,
        ("cmp","cl3b_macd",),
        EXCHANGE_THS,
    ),
]
_LABELS = [p[0] for p in _PRESETS]

st.header("Signal Performance vs Current Prices — Ranking")

choice = st.selectbox("功能", options=_LABELS, key="performance_preset")
for label, main_signal, exchange in _PRESETS:
    if label == choice:
        st.session_state.main_signal = main_signal
        st.session_state.exchange = exchange
        break

_root = Path(__file__).resolve().parent.parent
exec((_root / "performance.py").read_text(encoding="utf-8"))
