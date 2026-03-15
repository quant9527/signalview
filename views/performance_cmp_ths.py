import streamlit as st

st.session_state.main_signal = "cmp"
st.session_state.exchange = "ths"

exec(open("performance.py").read())
