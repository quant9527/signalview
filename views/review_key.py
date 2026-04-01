import pandas as pd
import streamlit as st
from signal_constants import NESTED_2BC_SIGNAL_NAMES

st.session_state['_is_review_mode'] = True
st.session_state['_preset_signals'] = list(NESTED_2BC_SIGNAL_NAMES)

exec(open('search_signals.py').read())
