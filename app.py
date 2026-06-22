import streamlit as st

pg = st.navigation(
    [
        st.Page("pages/00_Home.py", title="Home", icon="🏠", default=True),
        st.Page("pages/01_Configuration.py", title="Manual Configuration", icon="⚙️"),
        st.Page("pages/02_Evaluation.py", title="Configuration Analysis", icon="📊"),
        st.Page("pages/03_Scenario_Discovery.py", title="Scenario Discovery", icon="🔍"),
        st.Page("pages/04_Scenario_Discovery_Evaluation.py", title="Scenario Discovery Evaluation", icon="📈"),
        st.Page("pages/05_Data_Management.py", title="Data Management", icon="🗄️"),
    ]
)
pg.run()
