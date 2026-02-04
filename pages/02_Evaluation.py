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
    optigob.apply_scalers()
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

    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        fig, ax = plt.subplots()
        any_visible = False

        # ---- initialize session state ----
        for label, _ in series:
            key = f"{metric_key}_{label}"
            if key not in st.session_state:
                st.session_state[key] = False

        # ---- plot ----
        for label, y in series:
            if st.session_state[f"{metric_key}_{label}"]:
                ax.plot(time_line, y, marker=None, label=label)
                any_visible = True

        ax.set_xlabel("Year")
        ax.set_ylabel(y_label)
        ax.set_title(title)
        ax.grid(True)

        if any_visible:
            ax.legend(loc="center left", bbox_to_anchor=(1, 0.5))
        else:
            ax.text(
                0.5,
                0.5,
                "No series selected",
                ha="center",
                va="center",
                transform=ax.transAxes,
                fontsize=12,
                alpha=0.6,
            )

        st.pyplot(fig)

    # ---- checkboxes ----
    st.markdown("### Show / hide series")

    cols = st.columns(len(series))
    for col, (label, _) in zip(cols, series):
        with col:
            st.checkbox(
                label,
                key=f"{metric_key}_{label}",
            )

    # ---- table ----
    st.divider()
    st.header("Data Table")

    data = {"year": time_line}
    for label, y in series:
        if st.session_state[f"{metric_key}_{label}"]:
            data[label] = y

    df = pd.DataFrame(data)
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
        y_label="Area (ha)",
        time_line=time_line,
        optigob=optigob,
    )

with tab3:
    render_timeseries_tab(
        metric_key="protein",
        title="Protein production",
        y_label="Protein (t)",
        time_line=time_line,
        optigob=optigob,
    )

with tab4:
    render_timeseries_tab(
        metric_key="bio_energy",
        title="Bio-energy",
        y_label="Energy (PJ)",
        time_line=time_line,
        optigob=optigob,
    )

with tab5:
    render_timeseries_tab(
        metric_key="hwp",
        title="Harvested Wood Products",
        y_label="HWP",
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
        y_label="Index",
        time_line=time_line,
        optigob=optigob,
    )


