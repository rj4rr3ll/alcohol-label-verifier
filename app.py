import streamlit as st
import pandas as pd

from src.matching import verify_core_fields, determine_overall_result


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
    "Phase 2: Core field matching is enabled. OCR and government warning validation will be added later."
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
    st.caption(
        "Current phase: Manual text entry with automated core field matching."
    )

# -----------------------------
# Label Upload Section
# -----------------------------
st.header("1. Upload Label Artwork")

uploaded_file = st.file_uploader(
    "Upload a label image",
    type=["png", "jpg", "jpeg"],
    help="OCR is not active yet. Upload preview only in Phase 2."
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
# Verification Results
# -----------------------------
st.header("4. Verification Results")

verify_button = st.button("Verify Label", type="primary")

if verify_button:
    if not detected_text.strip():
        st.error("Please enter detected label text before verifying.")
    else:
        results = verify_core_fields(
            detected_text=detected_text,
            brand_name=brand_name,
            class_type=class_type,
            alcohol_content=alcohol_content,
            net_contents=net_contents,
        )

        results.append(
            {
                "Check": "Government Warning",
                "Expected": "Required" if warning_required else "Not required",
                "Detected": "Not checked yet",
                "Result": "Not implemented",
                "Notes": "Warning validation will be added in Phase 3."
            }
        )

        core_results = results[:-1]
        overall_result = determine_overall_result(core_results)

        st.subheader("Overall Result")

        if overall_result == "PASS":
            st.success("PASS — Core application fields appear to match the label.")
        elif overall_result == "MANUAL REVIEW RECOMMENDED":
            st.warning("MANUAL REVIEW RECOMMENDED — One or more fields need human review.")
        else:
            st.error("FAIL — One or more expected fields were not found or did not match.")

        results_df = pd.DataFrame(results)
        st.dataframe(results_df, use_container_width=True)

        st.caption(
            "Note: Government warning validation is intentionally deferred to Phase 3."
        )