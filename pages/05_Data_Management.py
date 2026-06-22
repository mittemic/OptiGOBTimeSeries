import os
import streamlit as st

DATA_DIR = "data"
STATIC_FILE = os.path.join(DATA_DIR, "static_systems.xlsx")
DYNAMIC_FILE = os.path.join(DATA_DIR, "dynamic_systems.xlsx")
DB_FILE = os.path.join(DATA_DIR, "database.db")

st.title("Data Management")

# ---------------------------------------------------------------------------
# Downloads — public
# ---------------------------------------------------------------------------

st.header("Download Source Data")
st.caption("Download the current Excel files used to populate the database.")

dl_col1, dl_col2 = st.columns(2)

with dl_col1:
    if os.path.exists(STATIC_FILE):
        with open(STATIC_FILE, "rb") as f:
            st.download_button(
                "Download static_systems.xlsx",
                data=f.read(),
                file_name="static_systems.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    else:
        st.warning("static_systems.xlsx not found.")

with dl_col2:
    if os.path.exists(DYNAMIC_FILE):
        with open(DYNAMIC_FILE, "rb") as f:
            st.download_button(
                "Download dynamic_systems.xlsx",
                data=f.read(),
                file_name="dynamic_systems.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    else:
        st.warning("dynamic_systems.xlsx not found.")

# ---------------------------------------------------------------------------
# Upload & Rebuild — admin only
# ---------------------------------------------------------------------------

st.divider()
st.header("Update Database")

try:
    with open("admin_password", "r") as _f:
        admin_password = _f.read().strip() or None
except FileNotFoundError:
    admin_password = None

if not admin_password:
    st.info(
        "Admin uploads are disabled. "
        "Copy `admin_password.example` to `admin_password` and set your own password to enable this section."
    )
    st.stop()

if "db_admin_unlocked" not in st.session_state:
    st.session_state["db_admin_unlocked"] = False

if not st.session_state["db_admin_unlocked"]:
    st.caption("Enter the admin password to upload replacement data files.")
    pw = st.text_input("Password", type="password", key="db_admin_pw_input")
    if st.button("Unlock", use_container_width=False):
        if pw == admin_password:
            st.session_state["db_admin_unlocked"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()

# --- Authenticated ---

if st.button("🔒 Lock admin section"):
    st.session_state["db_admin_unlocked"] = False
    st.rerun()

st.caption(
    "Upload a replacement file for either or both sources, then click **Rebuild Database**. "
    "The uploaded files will overwrite the existing ones in `data/`."
)

static_upload = st.file_uploader("static_systems.xlsx", type=["xlsx"], key="db_static_upload")
dynamic_upload = st.file_uploader("dynamic_systems.xlsx", type=["xlsx"], key="db_dynamic_upload")

if st.button(
    "Rebuild Database",
    disabled=(static_upload is None and dynamic_upload is None),
    type="primary",
):
    from resource_manager.create_database import read_forestry, read_animals

    errors = []
    with st.spinner("Rebuilding database…"):
        if static_upload is not None:
            try:
                with open(STATIC_FILE, "wb") as f:
                    f.write(static_upload.read())
                read_forestry(STATIC_FILE, DB_FILE)
                st.success("static_systems.xlsx imported successfully.")
            except Exception as exc:
                errors.append(f"static_systems.xlsx: {exc}")

        if dynamic_upload is not None:
            try:
                with open(DYNAMIC_FILE, "wb") as f:
                    f.write(dynamic_upload.read())
                read_animals(DYNAMIC_FILE, DB_FILE)
                st.success("dynamic_systems.xlsx imported successfully.")
            except Exception as exc:
                errors.append(f"dynamic_systems.xlsx: {exc}")

    for err in errors:
        st.error(f"Import failed — {err}")
