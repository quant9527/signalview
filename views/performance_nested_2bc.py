import streamlit as st

st.session_state.main_signal = "nested_2bc"
st.session_state.exchange = "as"

exec(open("performance.py").read())