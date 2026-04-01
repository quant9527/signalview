"""Unified Performance：通过「功能」选择预设的 main_signal 与默认 exchange。"""
from pathlib import Path

import streamlit as st

from constants import EXCHANGE_AS, EXCHANGE_THS
from signal_constants import PERFORMANCE_PRESET_AS_PREFIXES, PERFORMANCE_PRESET_THS_PREFIXES

_PRESETS = [
    (EXCHANGE_AS, PERFORMANCE_PRESET_AS_PREFIXES, EXCHANGE_AS),
    (EXCHANGE_THS, PERFORMANCE_PRESET_THS_PREFIXES, EXCHANGE_THS),
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
