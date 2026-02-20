import pandas as pd
import streamlit as st
import json

from matplotlib import pyplot as plt

from optigob.optigob import Optigob

st.set_page_config(
    page_title="Configuration Evaluation",
    layout="wide"
)

st.title("Configuration Review & Evaluation")

# -------------------------
# Load configuration
# -------------------------

config = st.session_state.get("generated_config")

if config is None:
    st.warning("No configuration found. Please generate one first.")
    if st.button("Back to configuration builder"):
        st.switch_page("app.py")
    st.stop()
else:
    optigob = Optigob(json_config=config, db_file_path="data/database.db")
    optigob.run()

# -------------------------
# Display configuration
# -------------------------


with st.expander("Generated Configuration", expanded=False):
    st.json(config)

    st.download_button(
        label="Download JSON configuration",
        data=json.dumps(config, indent=2),
        file_name="scenario_config.json",
        mime="application/json",
    )

# -------------------------
# evaluation
# -------------------------

def render_timeseries_tab(
    *,
    metric_key: str,
    title: str,
    y_label: str,
    time_line,
    optigob,
):
    series = optigob.get_evaluation(metric_key)

    # Helper to generate guaranteed-unique keys
    def make_key(index: int) -> str:
        return f"{metric_key}_{index}"

    st.subheader(title)

    # ---- initialize session state safely ----
    for i, (label, _) in enumerate(series):
        key = make_key(i)
        if key not in st.session_state:
            st.session_state[key] = False

    # ---- checkboxes ----
    st.markdown("### Show / hide series")

    num_columns = 5
    cols = st.columns(num_columns)

    for i, (label, _) in enumerate(series):
        key = make_key(i)
        col = cols[i % num_columns]
        with col:
            st.checkbox(label, key=key)

    # ---- prepare dataframe for selected series ----
    data = {"Year": list(time_line)}

    for i, (label, y) in enumerate(series):
        key = make_key(i)
        if st.session_state[key]:
            data[label] = y

    df = pd.DataFrame(data)

    # ---- plot ----
    if len(df.columns) > 1:
        df_chart = df.set_index("Year")

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.subheader(f"{title} ({y_label})")
            st.line_chart(df_chart, use_container_width=True)

    else:
        st.info("No series selected")

    # ---- table ----
    st.divider()
    st.header("Data Table")
    st.dataframe(df, use_container_width=True)

    # ---- CSV download ----
    st.download_button(
        label="Download data as CSV",
        data=df.to_csv(index=False),
        file_name=f"{metric_key}.csv",
        mime="text/csv",
    )


tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🌍 Emissions",
    "🗺️ Area",
    "🥩 Protein",
    "⚡ Bio-Energy",
    "🪵 HWP",
    "🔄 Substitution",
    "🦋 Biodiversity"
])

time_line = range(optigob.baseline_year, optigob.target_year + 1)

with tab1:
    render_timeseries_tab(
        metric_key="co2e",
        title="CO₂e emissions",
        y_label="CO₂e",
        time_line=time_line,
        optigob=optigob,
    )

with tab2:
    render_timeseries_tab(
        metric_key="area",
        title="Land area",
        y_label="ha",
        time_line=time_line,
        optigob=optigob,
    )

with tab3:
    render_timeseries_tab(
        metric_key="protein",
        title="Protein production",
        y_label="t",
        time_line=time_line,
        optigob=optigob,
    )

with tab4:
    render_timeseries_tab(
        metric_key="bio_energy",
        title="Bio-energy",
        y_label="MWh",
        time_line=time_line,
        optigob=optigob,
    )

with tab5:
    render_timeseries_tab(
        metric_key="hwp",
        title="Harvested Wood Products",
        y_label="m³",
        time_line=time_line,
        optigob=optigob,
    )

with tab6:
    render_timeseries_tab(
        metric_key="substitution",
        title="Substitution effects",
        y_label="CO₂e",
        time_line=time_line,
        optigob=optigob,
    )

with tab7:
    render_timeseries_tab(
        metric_key="biodiversity",
        title="Biodiversity indicators",
        y_label="HNV area (ha)",
        time_line=time_line,
        optigob=optigob,
    )


