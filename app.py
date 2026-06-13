import streamlit as st
import pandas as pd

from src.matching import verify_core_fields, determine_overall_result
from src.warning_check import verify_government_warning
from src.ocr import extract_text_from_uploaded_image, get_ocr_status


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
    "Phase 4: OCR is enabled. Uploaded label images can be processed, and extracted text can be reviewed before verification."
)

if "detected_text" not in st.session_state:
    st.session_state.detected_text = ""

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
    help="Upload a clear image of the alcohol label."
)

if uploaded_file is not None:
    st.image(uploaded_file, caption="Uploaded Label Preview", use_container_width=True)

    ocr_ready, ocr_message = get_ocr_status()

    if ocr_ready:
        st.caption(f"OCR status: {ocr_message}")

        if st.button("Run OCR on Uploaded Label"):
            with st.spinner("Extracting text from label image..."):
                try:
                    extracted_text = extract_text_from_uploaded_image(uploaded_file)
                    st.session_state.detected_text = extracted_text

                    if extracted_text:
                        st.success("OCR complete. Review and edit the extracted text below if needed.")
                    else:
                        st.warning(
                            "OCR completed but did not detect readable text. "
                            "You can still paste label text manually below."
                        )

                except Exception as error:
                    st.error(f"OCR failed: {error}")
                    st.info("You can still paste label text manually below.")
    else:
        st.warning(ocr_message)
        st.info("Manual text entry remains available below.")
else:
    st.caption("No label image uploaded yet.")

st.divider()

# -----------------------------
# Manual Label Text Section
# -----------------------------
st.header("2. Enter Detected Label Text")

detected_text = st.text_area(
    "Review, edit, paste, or type the text visible on the label",
    height=220,
    key="detected_text",
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

        warning_result = verify_government_warning(
            detected_text=detected_text,
            warning_required=warning_required,
        )

        results.append(warning_result)

        overall_result = determine_overall_result(results)

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
            "Note: This prototype checks warning text and capitalization. It does not verify font size, bold formatting, or label placement."
        )