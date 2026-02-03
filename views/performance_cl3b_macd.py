import streamlit as st

st.session_state.main_signal = "cl3b_macd"
st.session_state.exchange = "em"

exec(open("performance.py").read())