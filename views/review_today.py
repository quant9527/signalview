import pandas as pd
import streamlit as st

st.session_state['_is_review_mode'] = True
st.session_state['_auto_select_recent_2_days'] = True

exec(open('search_signals.py').read())