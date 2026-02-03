import streamlit as st

st.session_state.main_signal = "cmp"
st.session_state.exchange = "em"

exec(open("performance.py").read())
