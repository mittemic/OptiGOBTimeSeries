import streamlit as st

st.title("Optigob Interface")

st.markdown(
    "This is a beta version of time series-focussed Optigob in its validation stage. "
    "For the currently released version, please visit "
    "[https://goblin.cs.universityofgalway.ie/](https://goblin.cs.universityofgalway.ie/)."
)

if st.button("Configure Optigob Scenario"):
    st.switch_page("pages/01_Configuration.py")
