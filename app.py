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


def add_result_icons(results: list[dict]) -> list[dict]:
    """
    Add a human-friendly status label for display.
    """
    icon_map = {
        "PASS": "✅ PASS",
        "REVIEW": "⚠️ REVIEW",
        "FAIL": "❌ FAIL",
        "Not implemented": "⏳ Not implemented",
    }

    enhanced_results = []

    for row in results:
        enhanced_row = row.copy()
        enhanced_row["Status"] = icon_map.get(row.get("Result", ""), row.get("Result", ""))
        enhanced_results.append(enhanced_row)

    return enhanced_results


def summarize_results(results: list[dict]) -> dict:
    """
    Count pass, review, and fail results.
    """
    return {
        "pass": sum(1 for row in results if row["Result"] == "PASS"),
        "review": sum(1 for row in results if row["Result"] == "REVIEW"),
        "fail": sum(1 for row in results if row["Result"] == "FAIL"),
    }


def display_overall_result(overall_result: str):
    """
    Display overall result in plain language.
    """
    st.subheader("Overall Result")

    if overall_result == "PASS":
        st.success("PASS — The checked label fields appear to match the application data.")
    elif overall_result == "MANUAL REVIEW RECOMMENDED":
        st.warning("MANUAL REVIEW RECOMMENDED — One or more fields need human review.")
    else:
        st.error("FAIL — One or more required fields were not found or did not match.")


def display_attention_items(results: list[dict]):
    """
    Display only review/fail items so agents can quickly see what needs attention.
    """
    attention_items = [
        row for row in results
        if row["Result"] in ["REVIEW", "FAIL"]
    ]

    if not attention_items:
        st.success("No review or failure items were found.")
        return

    st.subheader("Items Requiring Attention")

    for item in attention_items:
        if item["Result"] == "FAIL":
            st.error(f"{item['Check']}: {item['Notes']}")
        else:
            st.warning(f"{item['Check']}: {item['Notes']}")


def display_results_table(results: list[dict]):
    """
    Display the verification results table.
    """
    enhanced_results = add_result_icons(results)
    results_df = pd.DataFrame(enhanced_results)

    display_columns = [
        "Check",
        "Expected",
        "Detected",
        "Status",
        "Notes",
    ]

    st.subheader("Detailed Verification Results")

    st.dataframe(
        results_df[display_columns],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Check": st.column_config.TextColumn("Check", width="small"),
            "Expected": st.column_config.TextColumn("Expected", width="medium"),
            "Detected": st.column_config.TextColumn("Detected", width="medium"),
            "Status": st.column_config.TextColumn("Status", width="small"),
            "Notes": st.column_config.TextColumn("Notes", width="large"),
        }
    )

    csv_data = results_df[display_columns].to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Download Results CSV",
        data=csv_data,
        file_name="label_verification_results.csv",
        mime="text/csv"
    )


st.title("AI-Powered Alcohol Label Verification App")

st.write(
    "Prototype tool for verifying alcohol label information against expected application fields."
)

st.info(
    "Phase 5: OCR, core field matching, government warning validation, and improved review workflow are enabled."
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
        "Current phase: Single-label OCR and verification workflow."
    )

    with st.expander("How to use this prototype"):
        st.write(
            "1. Upload a clear label image.\n\n"
            "2. Run OCR or paste label text manually.\n\n"
            "3. Enter expected application fields.\n\n"
            "4. Click Verify Label.\n\n"
            "5. Review any warnings or failures."
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
st.header("2. Review or Enter Detected Label Text")

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

with st.expander("View detected label text guidance"):
    st.write(
        "OCR may misread small, curved, low-contrast, or angled text. "
        "Agents can edit the extracted text before running verification. "
        "This keeps the workflow usable even when image quality is poor."
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
        summary = summarize_results(results)

        display_overall_result(overall_result)

        metric_col1, metric_col2, metric_col3 = st.columns(3)

        with metric_col1:
            st.metric("Passed Checks", summary["pass"])

        with metric_col2:
            st.metric("Manual Review Checks", summary["review"])

        with metric_col3:
            st.metric("Failed Checks", summary["fail"])

        display_attention_items(results)

        display_results_table(results)

        st.caption(
            "Prototype limitation: This tool checks extracted text and capitalization. "
            "It does not verify font size, bold formatting, exact label placement, or make final regulatory determinations."
        )