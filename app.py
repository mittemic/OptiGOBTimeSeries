import streamlit as st

st.set_page_config(page_title="Optigob Interface", layout="wide")

st.title("Optigob Interface")

if st.button("Configure Optigob Scenario"):
    st.switch_page("pages/01_Configuration.py")