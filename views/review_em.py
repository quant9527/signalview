import pandas as pd
import streamlit as st

st.session_state['_is_review_mode'] = True
st.session_state['_preset_exchange'] = 'em'

exec(open('search_signals.py').read())
