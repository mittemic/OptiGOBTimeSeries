import streamlit as st
import json

st.set_page_config(page_title="Scenario Configuration Builder", layout="wide")

st.title("Scenario Configuration Builder")

# -------------------------
# Helper functions
# -------------------------

def waypoint_agriculture(idx, key_prefix):
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        year = st.number_input(
            "Year",
            min_value=2021,
            max_value=2120,
            value=2020 + (idx+1)*10,
            step=1,
            key=f"{key_prefix}_year_{idx}",
        )
    with col2:
        abatement = st.selectbox(
            "Abatement",
            ["2020 BL", "MACC", "Frontier"],
            key=f"{key_prefix}_abatement_{idx}",
        )
    with col3:
        scaler = st.number_input(
            "Scaler",
            min_value=0.0,
            max_value=999999.9,
            step=0.1,
            value=1.0,
            key=f"{key_prefix}_scaler_{idx}",
        )
    with col4:
        scale_type = st.selectbox(
            "Scaler Type",
            ["Percentage Value", "Absolute Value"],
            key=f"{key_prefix}_scale_type_{idx}",
        )
    with col5:
        parameter = st.selectbox(
            "Parameter",
            ["co2e", "area", "protein"],
            key=f"{key_prefix}_parameter_{idx}",
        )

    return {
        "year": year,
        "abatement": abatement,
        "productivity": "2020 Prod",
        "scaler": scaler,
        "scale_parameter": parameter,
        "scale_absolute_or_percentage": scale_type == "Absolute Value",
    }

def waypoint_cattle(idx, key_prefix):
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        year = st.number_input(
            "Year",
            min_value=2021,
            max_value=2120,
            value=2020 + (idx+1)*10,
            step=1,
            key=f"{key_prefix}_year_{idx}",
        )
    with col2:
        abatement = st.selectbox(
            "Abatement",
            ["2020 BL", "MACC", "Frontier"],
            key=f"{key_prefix}_abatement_{idx}",
        )
    with col3:
        scaler = st.number_input(
            "Scaler",
            min_value=0.0,
            max_value=999999.9,
            value=1.0,
            step=0.1,
            key=f"{key_prefix}_scaler_{idx}",
        )
    with col4:
        scale_type = st.selectbox(
            "Scaler Type",
            ["Percentage Value", "Absolute Value"],
            key=f"{key_prefix}_scale_type_{idx}",
        )
    with col5:
        parameter = st.selectbox(
            "Parameter",
            ["co2e", "area", "protein"],
            key=f"{key_prefix}_parameter_{idx}",
        )

    col6, col7 = st.columns(2)
    with col6:
        dairy_prod = st.selectbox(
            "Dairy Productivity",
            ["2020 Prod", "Medium increase", "Strong increase"],
            key=f"{key_prefix}_dairy_{idx}",
        )
    with col7:
        beef_prod = st.selectbox(
            "Beef Productivity",
            ["2020 Prod", "Medium increase", "Strong increase"],
            key=f"{key_prefix}_beef_{idx}",
        )

    return {
        "year": year,
        "abatement": abatement,
        "scaler": scaler,
        "scale_parameter": parameter,
        "scale_absolute_or_percentage": scale_type == "Absolute Value",
        "dairy_productivity": dairy_prod,
        "beef_productivity": beef_prod,
    }


def waypoint_organic(idx, key_prefix):
    col1, col2 = st.columns(2)
    with col1:
        year = st.number_input(
            "Year",
            min_value=2021,
            max_value=2120,
            value=2020 + (idx+1)*10,
            step=1,
            key=f"{key_prefix}_year_{idx}",
        )
    with col2:
        ratio = st.number_input(
            "Rewetting ratio",
            min_value=0.0,
            max_value=1.0,
            value=0.0,
            step=0.05,
            key=f"{key_prefix}_ratio_{idx}",
        )

    return {
        "year": year,
        "rewetting_ratio": ratio,
    }


# -------------------------
# Global options
# -------------------------

st.header("Global Configuration")

target_year = st.number_input(
    "Target Year",
    min_value=2030,
    max_value=2120,
    step=1,
    value=2100,
)

# -------------------------
# Forestry
# -------------------------

st.header("Forestry")

with st.expander("Existing Forest", expanded=False):
    ef_harvest = st.selectbox("Harvest", ["low", "high"], key="ef_harvest")
    ef_ccs = st.checkbox("CCS", value=False, key="ef_ccs")

with st.expander("Afforestation", expanded=False):
    af_harvest = st.selectbox("Harvest", ["low", "high"], key="af_harvest")
    af_ccs = st.checkbox("CCS", value=False, key="af_ccs")
    af_rate = st.number_input(
        "Afforestation rate (x1,000 ha/y)",
        min_value=0.0,
        max_value=10.0,
        step=0.1,
        value=1.0,
    )
    bl_ratio = st.selectbox(
        "Broadleaf / Conifer ratio",
        ["50/50", "30/70"],
    )
    soil_ratio = st.selectbox(
        "Organic / Mineral soil ratio",
        ["15/85", "0/100"],
    )

broadleaf_frac = 0.5 if bl_ratio == "50/50" else 0.3
organic_soil_frac = 0.15 if soil_ratio == "15/85" else 0.0

# -------------------------
# Agriculture
# -------------------------

st.header("Agriculture")

def agriculture_block(name):
    st.subheader(name)
    n_wp = st.number_input(
        f"Number of waypoints ({name})",
        min_value=0,
        max_value=10,
        step=1,
        key=f"{name}_nwp",
    )

    waypoints = []
    for i in range(n_wp):
        st.markdown(f"**Waypoint {i + 1}**")
        waypoints.append(waypoint_agriculture(i, f"{name}_wp"))

    return {
        "name": name,
        "abatement": "2020 BL",
        "productivity": "2020 Prod",
        "waypoints": waypoints,
    }

non_cattle = []
for system in ["Pigs", "Poultry", "Sheep", "Crops"]:
    with st.expander(system, expanded=False):
        non_cattle.append(agriculture_block(system))



with st.expander("Cattle", expanded=False):
    cattle_nwp = st.number_input(
        "Number of waypoints (Cattle)",
        min_value=0,
        max_value=10,
        step=1,
    )

    cattle_waypoints = []
    for i in range(cattle_nwp):
        st.markdown(f"**Waypoint {i + 1}**")
        cattle_waypoints.append(waypoint_cattle(i, "cattle_wp"))

# -------------------------
# Organic Soils
# -------------------------

st.header("Organic Soils")

def organic_block(name):
    st.subheader(name)
    n_wp = st.number_input(
        f"Number of waypoints ({name})",
        min_value=0,
        max_value=10,
        step=1,
        key=f"{name}_nwp",
    )

    waypoints = []
    for i in range(n_wp):
        st.markdown(f"**Waypoint {i + 1}**")
        waypoints.append(waypoint_organic(i, f"{name}_wp"))

    return {
        "name": name,
        "drainage_status": ["Drained", "Rewetted"],
        "waypoints": waypoints if waypoints else None,
    }

organic_soils = []

with st.expander("Organic soil under grass", expanded=False):
    organic_soils.append(organic_block("Organic soil under grass"))

organic_soils.append(
    {
        "name": "Near natural wetlands",
        "drainage_status": ["Natural"],
    }
)

with st.expander("Industrial peat", expanded=False):
    organic_soils.append(organic_block("Industrial peat"))

with st.expander("Domestic peat", expanded=False):
    organic_soils.append(organic_block("Domestic peat"))

# Remove None waypoints
for o in organic_soils:
    if o.get("waypoints") is None:
        o.pop("waypoints", None)

# -------------------------
# Build JSON
# -------------------------

config = {
    "baseline_year": 2020,
    "target_year": target_year,
    "forestry": [
        {
            "name": "existing_forest",
            "harvest": ef_harvest,
            "ccs": ef_ccs,
        },
        {
            "name": "afforestation",
            "afforestation_rate": af_rate,
            "broadleaf_frac": broadleaf_frac,
            "organic_soil": organic_soil_frac,
            "harvest": af_harvest,
            "ccs": af_ccs,
        },
    ],
    "organic_soils": organic_soils,
    "non_cattle_agriculture": non_cattle,
    "cattle_systems": {
        "abatement": "2020 BL",
        "productivity": "2020 Prod",
        "waypoints": cattle_waypoints,
    },
}

# -------------------------
# Output
# -------------------------
st.header("Generated Configuration")

with st.expander("Generated Configuration", expanded=False):
    st.json(config)

    st.download_button(
        label="Download JSON configuration",
        data=json.dumps(config, indent=2),
        file_name="scenario_config.json",
        mime="application/json",
    )

st.session_state["generated_config"] = config
st.divider()

if st.button("Run Optigob ➜"):
    st.switch_page("pages/02_Evaluation.py")
