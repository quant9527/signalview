import streamlit as st

st.session_state.main_signal = "pair_seg"
st.session_state.exchange = "as"

exec(open("performance.py").read())
