import pandas as pd
import streamlit as st

st.session_state['_is_review_mode'] = True
st.session_state['_preset_signals'] = ['nested_2bc_macd_1b', 'nested_2bc_ma5ma10_1b']

exec(open('search_signals.py').read())
