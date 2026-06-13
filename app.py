import streamlit as st
import pandas as pd

from src.matching import verify_core_fields, determine_overall_result
from src.warning_check import verify_government_warning
from src.ocr import extract_text_from_uploaded_image, get_ocr_status
from src.batch import (
    normalize_batch_dataframe,
    validate_batch_dataframe,
    verify_batch_label,
)


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


def display_batch_summary(batch_results_df: pd.DataFrame):
    """
    Display batch-level summary metrics.
    """
    total = len(batch_results_df)
    passed = int((batch_results_df["Overall Result"] == "PASS").sum())
    review = int((batch_results_df["Overall Result"] == "MANUAL REVIEW RECOMMENDED").sum())
    failed = int((batch_results_df["Overall Result"] == "FAIL").sum())

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Labels", total)

    with col2:
        st.metric("Passed", passed)

    with col3:
        st.metric("Manual Review", review)

    with col4:
        st.metric("Failed", failed)


def display_batch_results(batch_results: list[dict]):
    """
    Display batch results and CSV download.
    """
    if not batch_results:
        st.warning("No batch results to display.")
        return

    batch_results_df = pd.DataFrame(batch_results)

    display_batch_summary(batch_results_df)

    st.subheader("Batch Verification Results")

    st.dataframe(
        batch_results_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "File Name": st.column_config.TextColumn("File Name", width="medium"),
            "Overall Result": st.column_config.TextColumn("Overall Result", width="medium"),
            "Passed Checks": st.column_config.NumberColumn("Passed Checks", width="small"),
            "Manual Review Checks": st.column_config.NumberColumn("Manual Review Checks", width="small"),
            "Failed Checks": st.column_config.NumberColumn("Failed Checks", width="small"),
            "Issues": st.column_config.TextColumn("Issues", width="large"),
            "OCR Text Preview": st.column_config.TextColumn("OCR Text Preview", width="large"),
        }
    )

    csv_data = batch_results_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Download Batch Results CSV",
        data=csv_data,
        file_name="batch_label_verification_results.csv",
        mime="text/csv"
    )


st.title("AI-Powered Alcohol Label Verification App")

st.write(
    "Prototype tool for verifying alcohol label information against expected application fields."
)

st.info(
    "Phase 6: Single-label review and batch label review are enabled."
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
    st.info(
        "Privacy note: Uploaded files are processed during the active session "
        "and are not intentionally stored by this prototype."
    )
    st.info(
        "Security note: This prototype does not require API keys, external AI services, "
        "or persistent document storage."
    )
    st.caption(
        "Current phase: Single-label OCR and batch verification workflow."
    )

    with st.expander("How to use single-label review"):
        st.write(
            "1. Upload a clear label image.\n\n"
            "2. Run OCR or paste label text manually.\n\n"
            "3. Enter expected application fields.\n\n"
            "4. Click Verify Label.\n\n"
            "5. Review any warnings or failures."
        )

    with st.expander("How to use batch review"):
        st.write(
            "1. Upload a CSV with expected application fields.\n\n"
            "2. Upload matching label images.\n\n"
            "3. Make sure the CSV file_name values match the uploaded image names.\n\n"
            "4. Click Process Batch.\n\n"
            "5. Download the results CSV."
        )

single_tab, batch_tab = st.tabs(["Single Label Review", "Batch Review"])

# -----------------------------
# Single Label Review Tab
# -----------------------------
with single_tab:
    st.header("1. Upload Label Artwork")

    uploaded_file = st.file_uploader(
        "Upload a label image",
        type=["png", "jpg", "jpeg"],
        help="Upload a clear image of the alcohol label.",
        key="single_label_upload"
    )

    if uploaded_file is not None:
        st.image(uploaded_file, caption="Uploaded Label Preview", use_container_width=True)

        ocr_ready, ocr_message = get_ocr_status()

        if ocr_ready:
            st.caption(f"OCR status: {ocr_message}")

            if st.button("Run OCR on Uploaded Label", key="single_ocr_button"):
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

# -----------------------------
# Batch Review Tab
# -----------------------------
with batch_tab:
    st.header("Batch Label Review")

    st.write(
        "Upload a CSV of expected application fields and matching label images. "
        "Each CSV row should include a `file_name` value that matches one uploaded image filename."
    )

    with st.expander("Required CSV format"):
        st.code(
            "file_name,brand_name,class_type,alcohol_content,net_contents,warning_required\n"
            "old_tom_test_label.png,OLD TOM DISTILLERY,Kentucky Straight Bourbon Whiskey,45% Alc./Vol. (90 Proof),750 mL,true",
            language="csv"
        )

    batch_csv = st.file_uploader(
        "Upload batch application CSV",
        type=["csv"],
        key="batch_csv_upload"
    )

    batch_images = st.file_uploader(
        "Upload batch label images",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="batch_image_upload"
    )

    if batch_csv is not None:
        try:
            batch_df = pd.read_csv(batch_csv)
            batch_df = normalize_batch_dataframe(batch_df)

            st.subheader("CSV Preview")
            st.dataframe(batch_df, use_container_width=True, hide_index=True)
            
            if len(batch_df) > 25:
                st.warning(
                    "Prototype performance note: This CSV contains more than 25 rows. "
                    "For production use, large batches should be processed asynchronously."
                )

            missing_columns = validate_batch_dataframe(batch_df)

            if missing_columns:
                st.error(
                    "The batch CSV is missing required columns: "
                    + ", ".join(missing_columns)
                )
            else:
                st.success("CSV format looks valid.")

        except Exception as error:
            st.error(f"Could not read CSV: {error}")
            batch_df = None
    else:
        batch_df = None

    if batch_images:
        st.caption(f"{len(batch_images)} image file(s) uploaded.")

        if len(batch_images) > 25:
            st.warning(
                "Prototype performance note: More than 25 images were uploaded. "
                "Large production batches would require background processing, queueing, "
                "and monitoring."
            )

    process_batch_button = st.button(
        "Process Batch",
        type="primary",
        disabled=batch_df is None or not batch_images
    )

    if process_batch_button:
        ocr_ready, ocr_message = get_ocr_status()

        if not ocr_ready:
            st.error(ocr_message)
            st.info("Batch OCR requires Tesseract to be available.")
        else:
            uploaded_images_by_name = {
                image_file.name: image_file
                for image_file in batch_images
            }

            batch_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            for index, row in batch_df.iterrows():
                file_name = str(row.get("file_name", "")).strip()
                status_text.write(f"Processing {file_name}...")

                if file_name not in uploaded_images_by_name:
                    batch_results.append(
                        {
                            "File Name": file_name,
                            "Overall Result": "FAIL",
                            "Passed Checks": 0,
                            "Manual Review Checks": 0,
                            "Failed Checks": 1,
                            "Brand Name": str(row.get("brand_name", "")),
                            "Class/Type": str(row.get("class_type", "")),
                            "Alcohol Content": str(row.get("alcohol_content", "")),
                            "Net Contents": str(row.get("net_contents", "")),
                            "Issues": "Matching image file was not uploaded.",
                            "OCR Text Preview": "",
                        }
                    )
                else:
                    image_file = uploaded_images_by_name[file_name]

                    try:
                        detected_batch_text = extract_text_from_uploaded_image(image_file)
                        batch_result = verify_batch_label(row, detected_batch_text)
                        batch_results.append(batch_result)

                    except Exception as error:
                        batch_results.append(
                            {
                                "File Name": file_name,
                                "Overall Result": "FAIL",
                                "Passed Checks": 0,
                                "Manual Review Checks": 0,
                                "Failed Checks": 1,
                                "Brand Name": str(row.get("brand_name", "")),
                                "Class/Type": str(row.get("class_type", "")),
                                "Alcohol Content": str(row.get("alcohol_content", "")),
                                "Net Contents": str(row.get("net_contents", "")),
                                "Issues": f"OCR or verification failed: {error}",
                                "OCR Text Preview": "",
                            }
                        )

                progress_bar.progress((index + 1) / len(batch_df))

            status_text.write("Batch processing complete.")

            display_batch_results(batch_results)

            st.caption(
                "Prototype limitation: Batch mode is designed for proof-of-concept testing. "
                "Large production batches would require queueing, monitoring, and stronger error handling."
            )