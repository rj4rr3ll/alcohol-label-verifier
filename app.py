import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="AI-Powered Alcohol Label Verification App",
    page_icon="🏷️",
    layout="wide"
)

st.title("AI-Powered Alcohol Label Verification App")

st.write(
    "Prototype tool for verifying alcohol label information against expected application fields."
)

st.info(
    "Phase 1: Manual label text entry is enabled. OCR will be added in a later phase."
)

st.divider()

# -----------------------------
# Sidebar / Prototype Notes
# -----------------------------
with st.sidebar:
    st.header("Prototype Notes")
    st.write(
        "This tool assists compliance review by identifying potential mismatches "
        "between application data and label artwork."
    )
    st.warning(
        "Prototype only: Human compliance review remains required."
    )

# -----------------------------
# Label Upload Section
# -----------------------------
st.header("1. Upload Label Artwork")

uploaded_file = st.file_uploader(
    "Upload a label image",
    type=["png", "jpg", "jpeg"],
    help="OCR is not active yet. Upload preview only in Phase 1."
)

if uploaded_file is not None:
    st.image(uploaded_file, caption="Uploaded Label Preview", use_container_width=True)
else:
    st.caption("No label image uploaded yet.")

st.divider()

# -----------------------------
# Manual Label Text Section
# -----------------------------
st.header("2. Enter Detected Label Text")

detected_text = st.text_area(
    "Paste or type the text visible on the label",
    height=220,
    placeholder=(
        "Example:\n"
        "OLD TOM DISTILLERY\n"
        "Kentucky Straight Bourbon Whiskey\n"
        "45% Alc./Vol. (90 Proof)\n"
        "750 mL\n"
        "GOVERNMENT WARNING: ..."
    )
)

st.divider()

# -----------------------------
# Expected Application Fields
# -----------------------------
st.header("3. Enter Expected Application Fields")

col1, col2 = st.columns(2)

with col1:
    brand_name = st.text_input("Brand Name", placeholder="OLD TOM DISTILLERY")
    class_type = st.text_input(
        "Class/Type",
        placeholder="Kentucky Straight Bourbon Whiskey"
    )
    alcohol_content = st.text_input(
        "Alcohol Content",
        placeholder="45% Alc./Vol. or 90 Proof"
    )

with col2:
    net_contents = st.text_input("Net Contents", placeholder="750 mL")
    warning_required = st.checkbox(
        "Government Health Warning Required",
        value=True
    )

st.divider()

# -----------------------------
# Verification Placeholder
# -----------------------------
st.header("4. Verification Results")

verify_button = st.button("Verify Label", type="primary")

if verify_button:
    if not detected_text.strip():
        st.error("Please enter detected label text before verifying.")
    else:
        results = [
            {
                "Check": "Brand Name",
                "Expected": brand_name,
                "Detected": "Not checked yet",
                "Result": "Not implemented",
                "Notes": "Matching logic will be added in Phase 2."
            },
            {
                "Check": "Class/Type",
                "Expected": class_type,
                "Detected": "Not checked yet",
                "Result": "Not implemented",
                "Notes": "Matching logic will be added in Phase 2."
            },
            {
                "Check": "Alcohol Content",
                "Expected": alcohol_content,
                "Detected": "Not checked yet",
                "Result": "Not implemented",
                "Notes": "Matching logic will be added in Phase 2."
            },
            {
                "Check": "Net Contents",
                "Expected": net_contents,
                "Detected": "Not checked yet",
                "Result": "Not implemented",
                "Notes": "Matching logic will be added in Phase 2."
            },
            {
                "Check": "Government Warning",
                "Expected": "Required" if warning_required else "Not required",
                "Detected": "Not checked yet",
                "Result": "Not implemented",
                "Notes": "Warning validation will be added in Phase 3."
            },
        ]

        results_df = pd.DataFrame(results)

        st.subheader("Overall Result")
        st.warning("Verification logic not implemented yet.")

        st.dataframe(results_df, use_container_width=True)

        st.success("Phase 1 check complete: the form and results table are working.")