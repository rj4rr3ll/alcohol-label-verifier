import re
import time
from difflib import SequenceMatcher

import streamlit as st
import pandas as pd

from src.matching import verify_core_fields, determine_overall_result
from src.warning_check import verify_government_warning
from src.ocr import extract_text_from_uploaded_image, get_ocr_status
from src.batch import (
    normalize_batch_dataframe,
    validate_batch_dataframe,
    verify_batch_label,
    clean_cell,
    build_batch_failure_result,
)
from src.application_parser import (
    SUPPORTED_APPLICATION_EXTENSIONS,
    ParsedApplication,
    parse_application_file,
)


st.set_page_config(
    page_title="AI-Powered Alcohol Label Verification App",
    page_icon="🏷️",
    layout="wide"
)


BATCH_GENERATED_COLUMNS = [
    "file_name",
    "application_file",
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "name_address",
    "country_of_origin",
    "warning_required",
]


FILENAME_STOP_WORDS = {
    "application",
    "applications",
    "app",
    "label",
    "labels",
    "ttb",
    "cola",
    "f510031",
    "form",
    "test",
    "sample",
    "official",
    "filled",
    "pdf",
    "csv",
    "json",
    "txt",
    "distillery",
    "imports",
    "import",
    "importer",
    "company",
    "inc",
    "llc",
}


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
    Display the verification results table and provide a clean CSV export.
    The UI uses icon-enhanced status labels, but the CSV uses plain text
    to avoid encoding issues in Excel.
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

    csv_columns = [
        "Check",
        "Expected",
        "Detected",
        "Result",
        "Notes",
    ]

    csv_data = results_df[csv_columns].to_csv(index=False).encode("utf-8-sig")

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

    column_config = {
        "File Name": st.column_config.TextColumn("File Name", width="medium"),
        "Overall Result": st.column_config.TextColumn("Overall Result", width="medium"),
        "Passed Checks": st.column_config.NumberColumn("Passed Checks", width="small"),
        "Manual Review Checks": st.column_config.NumberColumn("Manual Review Checks", width="small"),
        "Failed Checks": st.column_config.NumberColumn("Failed Checks", width="small"),
        "Processing Time (s)": st.column_config.NumberColumn(
            "Processing Time (s)",
            width="small",
            format="%.2f",
        ),
        "Name/Address": st.column_config.TextColumn("Name/Address", width="large"),
        "Country of Origin": st.column_config.TextColumn("Country of Origin", width="medium"),
        "Issues": st.column_config.TextColumn("Issues", width="large"),
        "OCR Text Preview": st.column_config.TextColumn("OCR Text Preview", width="large"),
    }

    st.dataframe(
        batch_results_df,
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
    )

    csv_data = batch_results_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Download Batch Results CSV",
        data=csv_data,
        file_name="batch_label_verification_results.csv",
        mime="text/csv"
    )


def format_elapsed_time(seconds: float) -> str:
    """
    Format elapsed processing time for reviewer-facing messages.
    """
    if seconds < 1:
        return f"{seconds:.2f} seconds"

    return f"{seconds:.1f} seconds"


def add_processing_time(result: dict, elapsed_seconds: float | None) -> dict:
    """
    Add processing-time telemetry to a batch result row.
    """
    result_with_time = result.copy()
    result_with_time["Processing Time (s)"] = (
        round(elapsed_seconds, 2) if elapsed_seconds is not None else None
    )
    return result_with_time


def normalize_filename_stem(file_name: str) -> str:
    """
    Normalize a file name stem for matching applications to label images.
    """
    if not file_name:
        return ""

    stem = file_name.rsplit(".", 1)[0].lower()
    stem = re.sub(r"[^a-z0-9]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem


def filename_tokens(file_name: str) -> set[str]:
    """
    Convert a file name into useful matching tokens.
    """
    stem = normalize_filename_stem(file_name)

    tokens = {
        token for token in stem.split()
        if token and token not in FILENAME_STOP_WORDS
    }

    return tokens


def infer_label_file_name(application_file_name: str, image_file_names: list[str]) -> str:
    """
    Best-effort filename matching from an application file to a label image.

    This is intentionally conservative. If it cannot find a unique likely match,
    it returns a blank file_name so the reviewer can edit the generated table.
    """
    if not application_file_name or not image_file_names:
        return ""

    app_stem = normalize_filename_stem(application_file_name)
    app_tokens = filename_tokens(application_file_name)

    if not app_tokens:
        return ""

    scored_matches = []

    for image_file_name in image_file_names:
        image_stem = normalize_filename_stem(image_file_name)
        image_tokens = filename_tokens(image_file_name)

        token_overlap = len(app_tokens.intersection(image_tokens))
        sequence_score = SequenceMatcher(None, app_stem, image_stem).ratio()

        score = (token_overlap * 10) + sequence_score

        scored_matches.append(
            {
                "file_name": image_file_name,
                "score": score,
                "token_overlap": token_overlap,
            }
        )

    scored_matches.sort(key=lambda item: item["score"], reverse=True)

    if not scored_matches:
        return ""

    best_match = scored_matches[0]

    if best_match["token_overlap"] == 0:
        return ""

    if len(scored_matches) > 1:
        second_match = scored_matches[1]

        if best_match["score"] == second_match["score"]:
            return ""

    return best_match["file_name"]


def parsed_application_to_batch_row(
    parsed_application: ParsedApplication,
    application_file_name: str,
    image_file_names: list[str],
) -> dict:
    """
    Convert a parsed single application into one batch CSV row.
    """
    fields = parsed_application.expected_field_dict()

    return {
        "file_name": infer_label_file_name(application_file_name, image_file_names),
        "application_file": application_file_name,
        "brand_name": fields.get("brand_name", ""),
        "class_type": fields.get("class_type", ""),
        "alcohol_content": fields.get("alcohol_content", ""),
        "net_contents": fields.get("net_contents", ""),
        "name_address": fields.get("name_address", ""),
        "country_of_origin": fields.get("country_of_origin", ""),
        "warning_required": bool(fields.get("warning_required", True)),
    }


def build_batch_dataframe_from_application_files(
    application_files,
    image_file_names: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    """
    Parse multiple raw application files into an editable batch dataframe.

    Each application file becomes one generated batch row. Reviewers can edit
    the generated table before processing.
    """
    rows = []
    messages = []

    for application_file in application_files:
        application_file_name = getattr(application_file, "name", "uploaded_application")

        try:
            parsed_application = parse_application_file(application_file)
            row = parsed_application_to_batch_row(
                parsed_application=parsed_application,
                application_file_name=application_file_name,
                image_file_names=image_file_names,
            )
            rows.append(row)

            for message in parsed_application.messages:
                messages.append(f"{application_file_name}: {message}")

            if not row["file_name"]:
                messages.append(
                    f"{application_file_name}: Could not confidently match this application "
                    "to a label image filename. Review and fill in file_name before processing."
                )

        except Exception as error:
            messages.append(f"{application_file_name}: Application parsing failed: {error}")

            rows.append(
                {
                    "file_name": "",
                    "application_file": application_file_name,
                    "brand_name": "",
                    "class_type": "",
                    "alcohol_content": "",
                    "net_contents": "",
                    "name_address": "",
                    "country_of_origin": "",
                    "warning_required": True,
                }
            )

    generated_df = pd.DataFrame(rows, columns=BATCH_GENERATED_COLUMNS)

    return generated_df, messages


def initialize_expected_field_state():
    """
    Initialize expected application fields in session state so imported
    application data can pre-fill the editable inputs.
    """
    defaults = {
        "expected_brand_name": "",
        "expected_class_type": "",
        "expected_alcohol_content": "",
        "expected_net_contents": "",
        "expected_name_address": "",
        "expected_country_of_origin": "",
        "expected_warning_required": True,
        "application_import_messages": [],
        "application_import_metadata": {},
        "last_single_ocr_seconds": None,
        "generated_batch_df": None,
        "generated_batch_messages": [],
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def apply_parsed_application(parsed_application: ParsedApplication):
    """
    Apply imported application fields to Streamlit session state.
    Empty imported values do not overwrite fields the reviewer already entered.
    """
    imported_fields = parsed_application.expected_field_dict()

    field_to_state_key = {
        "brand_name": "expected_brand_name",
        "class_type": "expected_class_type",
        "alcohol_content": "expected_alcohol_content",
        "net_contents": "expected_net_contents",
        "name_address": "expected_name_address",
        "country_of_origin": "expected_country_of_origin",
        "warning_required": "expected_warning_required",
    }

    for field_name, state_key in field_to_state_key.items():
        value = imported_fields.get(field_name)

        if field_name == "warning_required":
            st.session_state[state_key] = bool(value)
        elif value:
            st.session_state[state_key] = value

    st.session_state.application_import_messages = parsed_application.messages
    st.session_state.application_import_metadata = {
        key: value
        for key, value in parsed_application.metadata_dict().items()
        if value
    }


def display_application_import_messages():
    """
    Display messages and optional metadata from the most recent application import.
    """
    messages = st.session_state.get("application_import_messages", [])
    metadata = st.session_state.get("application_import_metadata", {})

    for message in messages:
        st.info(message)

    if metadata:
        with st.expander("View imported application metadata"):
            metadata_df = pd.DataFrame(
                [
                    {"Field": key, "Imported Value": value}
                    for key, value in metadata.items()
                ]
            )
            st.dataframe(metadata_df, use_container_width=True, hide_index=True)


st.title("AI-Powered Alcohol Label Verification App")

st.write(
    "Prototype tool for verifying alcohol label information against expected application fields."
)


if "detected_text" not in st.session_state:
    st.session_state.detected_text = ""

initialize_expected_field_state()

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
        "Current phase: Application import, single-label OCR, and batch verification workflow."
    )

    with st.expander("How to use single-label review"):
        st.write(
            "1. Upload a clear label image.\n\n"
            "2. Extract label text with OCR or paste label text manually.\n\n"
            "3. Upload application data or enter expected fields manually.\n\n"
            "4. Verify the label.\n\n"
            "5. Review any warnings or failures."
        )

    with st.expander("How to use batch review"):
        st.write(
            "1. Choose whether to upload a batch CSV or generate one from application files.\n\n"
            "2. Upload matching label images.\n\n"
            "3. Review the CSV or generated batch table.\n\n"
            "4. Make sure each file_name value matches an uploaded image name.\n\n"
            "5. Process the batch and download the results."
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

            if st.button(
                "Extract Label Text",
                key="single_ocr_button",
                type="primary",
                help="Use OCR to pull readable label text into the editable review box below."
            ):
                with st.spinner("Extracting text from label image..."):
                    try:
                        start_time = time.perf_counter()
                        extracted_text = extract_text_from_uploaded_image(uploaded_file)
                        elapsed_seconds = time.perf_counter() - start_time
                        st.session_state.last_single_ocr_seconds = elapsed_seconds
                        st.session_state.detected_text = extracted_text

                        if extracted_text:
                            st.success(
                                "OCR complete in "
                                f"{format_elapsed_time(elapsed_seconds)}. "
                                "Review and edit the extracted text below if needed."
                            )
                        else:
                            st.warning(
                                "OCR completed in "
                                f"{format_elapsed_time(elapsed_seconds)}, "
                                "but did not detect readable text. "
                                "You can still paste label text manually below."
                            )

                    except Exception as error:
                        st.session_state.last_single_ocr_seconds = None
                        st.error(f"OCR failed: {error}")
                        st.info("You can still paste label text manually below.")

            if st.session_state.last_single_ocr_seconds is not None:
                elapsed = st.session_state.last_single_ocr_seconds
                if elapsed <= 5:
                    st.caption(
                        f"Last OCR run: {format_elapsed_time(elapsed)}. "
                        "This is within the 5-second target from stakeholder feedback."
                    )
                else:
                    st.warning(
                        f"Last OCR run: {format_elapsed_time(elapsed)}. "
                        "This is above the 5-second stakeholder target; use smaller or clearer images for the prototype."
                    )
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

    st.header("3. Upload or Enter Expected Application Fields")

    st.write(
        "Upload a structured application file to pre-fill the expected fields, "
        "or enter the fields manually. CSV, JSON, TXT, and PDF uploads are supported."
    )

    st.caption(
        "Official reference: TTB F 5100.31 is the paper Application for and "
        "Certification/Exemption of Label/Bottle Approval. The paper form includes "
        "Brand Name and application metadata, but class/type, alcohol content, and "
        "net contents may not be available as dedicated paper-form fields."
    )

    application_file = st.file_uploader(
        "Optional: upload application data to auto-fill expected fields",
        type=SUPPORTED_APPLICATION_EXTENSIONS,
        key="single_application_upload",
        help=(
            "Use CSV/JSON/TXT for structured prototype data, or upload a filled PDF "
            "such as TTB F 5100.31 for best-effort extraction."
        ),
    )

    if application_file is not None:
        if st.button(
            "Populate Expected Fields",
            key="populate_application_fields_button",
            type="primary",
            help="Extract supported application fields and pre-fill the editable inputs below.",
        ):
            try:
                parsed_application = parse_application_file(application_file)
                apply_parsed_application(parsed_application)
                st.success("Application import complete. Review and edit the fields below before verifying.")
            except Exception as error:
                st.error(f"Application import failed: {error}")
                st.info("You can still enter the expected fields manually below.")

    display_application_import_messages()

    with st.expander("Accepted application upload formats"):
        st.write(
            "For the most reliable prototype workflow, use CSV or JSON with columns/keys such as "
            "`brand_name`, `class_type`, `alcohol_content`, `net_contents`, "
            "`name_address`, `country_of_origin`, and `warning_required`."
        )
        st.code(
            "brand_name,class_type,alcohol_content,net_contents,name_address,country_of_origin,warning_required\n"
            "OLD TOM DISTILLERY,Kentucky Straight Bourbon Whiskey,45% Alc./Vol. (90 Proof),750 mL,OLD TOM DISTILLERY - LOUISVILLE KY,United States,true",
            language="csv",
        )
        st.write(
            "TXT files can use simple key/value lines such as `Brand Name: OLD TOM DISTILLERY`. "
            "PDF import is best-effort and works best with filled form fields or exported application summaries."
        )

    col1, col2 = st.columns(2)

    with col1:
        brand_name = st.text_input(
            "Brand Name",
            key="expected_brand_name",
            placeholder="OLD TOM DISTILLERY",
        )
        class_type = st.text_input(
            "Class/Type",
            key="expected_class_type",
            placeholder="Kentucky Straight Bourbon Whiskey",
        )
        alcohol_content = st.text_input(
            "Alcohol Content",
            key="expected_alcohol_content",
            placeholder="45% Alc./Vol. or 90 Proof",
        )

    with col2:
        net_contents = st.text_input(
            "Net Contents",
            key="expected_net_contents",
            placeholder="750 mL",
        )
        name_address = st.text_input(
            "Name/Address Optional",
            key="expected_name_address",
            placeholder="OLD TOM DISTILLERY - LOUISVILLE KY",
            help="Optional text check for bottler, producer, importer, or applicant name/address statements.",
        )
        country_of_origin = st.text_input(
            "Country of Origin Optional",
            key="expected_country_of_origin",
            placeholder="United States",
            help="Optional text check, most useful for imported products.",
        )
        warning_required = st.checkbox(
            "Government Health Warning Required",
            key="expected_warning_required",
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
                name_address=name_address,
                country_of_origin=country_of_origin,
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
        "Upload expected application data first, then upload the matching label images. "
        "You can either use a ready-made batch CSV or generate one from raw application files."
    )

    st.subheader("1. Choose Expected-Field Source")

    batch_source = st.radio(
        "How do you want to provide expected application fields?",
        ["Upload Batch CSV", "Generate from Application Files"],
        horizontal=True,
        help=(
            "Use a batch CSV if the expected fields are already structured. "
            "Use application files to generate an editable batch table from CSV, JSON, TXT, or best-effort PDF uploads."
        ),
    )

    batch_df_for_processing = None
    batch_df_valid = False
    application_files = None

    st.divider()

    # -----------------------------
    # Step 2: Expected Application Data
    # -----------------------------
    st.subheader("2. Upload Expected Application Data")

    if batch_source == "Upload Batch CSV":
        st.write(
            "Use this option when expected application fields are already structured in one CSV."
        )

        with st.expander("Required CSV format"):
            st.code(
                "file_name,brand_name,class_type,alcohol_content,net_contents,name_address,country_of_origin,warning_required\n"
                "old_tom_test_label.png,OLD TOM DISTILLERY,Kentucky Straight Bourbon Whiskey,45% Alc./Vol. (90 Proof),750 mL,OLD TOM DISTILLERY - LOUISVILLE KY,United States,true",
                language="csv"
            )

        batch_csv = st.file_uploader(
            "Upload batch application CSV",
            type=["csv"],
            key="batch_csv_upload",
            help="Upload the CSV that contains expected fields and matching label image filenames."
        )

        if batch_csv is not None:
            try:
                uploaded_batch_df = pd.read_csv(batch_csv)
                uploaded_batch_df = normalize_batch_dataframe(uploaded_batch_df)

                st.subheader("CSV Preview")
                st.dataframe(uploaded_batch_df, use_container_width=True, hide_index=True)

                missing_columns = validate_batch_dataframe(uploaded_batch_df)

                if missing_columns:
                    st.error(
                        "The batch CSV is missing required columns: "
                        + ", ".join(missing_columns)
                    )
                elif uploaded_batch_df.empty:
                    st.error("The batch CSV contains the required columns but no application rows.")
                else:
                    batch_df_valid = True
                    batch_df_for_processing = uploaded_batch_df
                    st.success("CSV format looks valid. Now upload the matching label images below.")

                    if len(uploaded_batch_df) > 25:
                        st.warning(
                            "Prototype performance note: This CSV contains more than 25 rows. "
                            "For production use, large batches should be processed asynchronously."
                        )

            except Exception as error:
                st.error(f"Could not read CSV: {error}")
                batch_df_for_processing = None
                batch_df_valid = False

    else:
        st.write(
            "Use this option to upload multiple raw application files. "
            "The app will generate an editable batch table so the reviewer does not have to build the CSV manually."
        )

        application_files = st.file_uploader(
            "Upload application files",
            type=SUPPORTED_APPLICATION_EXTENSIONS,
            accept_multiple_files=True,
            key="batch_application_files_upload",
            help="Supports CSV, JSON, TXT, and best-effort PDF application files."
        )

        if application_files:
            st.caption(f"{len(application_files)} application file(s) uploaded.")
            st.info(
                "Next, upload the matching label images. Image filenames help the app auto-fill the file_name column."
            )

    st.divider()

    # -----------------------------
    # Step 3: Label Images
    # -----------------------------
    st.subheader("3. Upload Matching Label Images")

    st.write(
        "Upload the label image files that correspond to the expected application data. "
        "For batch CSVs, each `file_name` value must match one uploaded image filename."
    )

    batch_images = st.file_uploader(
        "Upload batch label images",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="batch_image_upload",
        help="Upload PNG or JPG label images only."
    )

    if batch_images:
        st.caption(f"{len(batch_images)} image file(s) uploaded.")

        uploaded_image_names = [image_file.name for image_file in batch_images]
        duplicate_image_names = sorted(
            {name for name in uploaded_image_names if uploaded_image_names.count(name) > 1}
        )

        if duplicate_image_names:
            st.warning(
                "Duplicate uploaded image filenames were found. Batch matching uses filenames, "
                "so each uploaded image should have a unique name. Duplicates: "
                + ", ".join(duplicate_image_names)
            )

        if len(batch_images) > 25:
            st.warning(
                "Prototype performance note: More than 25 images were uploaded. "
                "Large production batches would require background processing, queueing, "
                "and monitoring."
            )

    st.divider()

    # -----------------------------
    # Step 4: Generated Batch Table
    # -----------------------------
    if batch_source == "Generate from Application Files":
        st.subheader("4. Generate and Review Batch Table")

        generate_button = st.button(
            "Generate Batch Table",
            type="primary",
            disabled=not application_files,
            help="Parse application files and generate an editable batch table for review.",
        )

        if generate_button:
            image_file_names = [image_file.name for image_file in batch_images] if batch_images else []

            generated_df, generated_messages = build_batch_dataframe_from_application_files(
                application_files=application_files,
                image_file_names=image_file_names,
            )

            st.session_state.generated_batch_df = generated_df
            st.session_state.generated_batch_messages = generated_messages

            st.success(
                "Generated batch table from application files. "
                "Review and edit the table before processing."
            )

        generated_batch_df = st.session_state.get("generated_batch_df")

        if generated_batch_df is not None and not generated_batch_df.empty:
            st.info(
                "Check the generated file_name values carefully. Each file_name must match one uploaded label image. "
                "You can edit cells directly before processing."
            )

            edited_generated_df = st.data_editor(
                generated_batch_df,
                use_container_width=True,
                hide_index=True,
                num_rows="dynamic",
                key="generated_batch_editor",
                column_config={
                    "file_name": st.column_config.TextColumn(
                        "file_name",
                        help="Must match one uploaded label image filename.",
                    ),
                    "application_file": st.column_config.TextColumn(
                        "application_file",
                        help="Source application file used to generate this row.",
                        disabled=True,
                    ),
                    "brand_name": st.column_config.TextColumn("brand_name"),
                    "class_type": st.column_config.TextColumn("class_type"),
                    "alcohol_content": st.column_config.TextColumn("alcohol_content"),
                    "net_contents": st.column_config.TextColumn("net_contents"),
                    "name_address": st.column_config.TextColumn("name_address"),
                    "country_of_origin": st.column_config.TextColumn("country_of_origin"),
                    "warning_required": st.column_config.CheckboxColumn("warning_required"),
                },
            )

            normalized_generated_df = normalize_batch_dataframe(edited_generated_df)

            generated_csv_data = normalized_generated_df.to_csv(index=False).encode("utf-8-sig")

            st.download_button(
                label="Download Generated Batch CSV",
                data=generated_csv_data,
                file_name="generated_batch_application.csv",
                mime="text/csv",
            )

            missing_columns = validate_batch_dataframe(normalized_generated_df)

            if missing_columns:
                st.error(
                    "The generated batch table is missing required columns: "
                    + ", ".join(missing_columns)
                )
            elif normalized_generated_df.empty:
                st.error("The generated batch table does not contain any application rows.")
            else:
                batch_df_for_processing = normalized_generated_df
                batch_df_valid = True

                blank_file_names = int(
                    (
                        normalized_generated_df["file_name"]
                        .fillna("")
                        .astype(str)
                        .str.strip()
                        == ""
                    ).sum()
                )

                if blank_file_names:
                    st.warning(
                        f"{blank_file_names} generated row(s) have a blank file_name. "
                        "Those rows will fail unless you enter a matching uploaded label image filename."
                    )
                else:
                    st.success("Generated batch table looks ready to process.")

            generated_messages = st.session_state.get("generated_batch_messages", [])

            if generated_messages:
                with st.expander("View application import notes"):
                    for message in generated_messages:
                        st.write(f"- {message}")
        else:
            st.caption("No generated batch table yet.")
    else:
        st.subheader("4. Process Batch")

    # -----------------------------
    # Step 5: Process Batch
    # -----------------------------
    if batch_source == "Generate from Application Files":
        st.subheader("5. Process Batch")

    process_batch_button = st.button(
        "Process Batch",
        type="primary",
        disabled=not batch_df_valid or not batch_images
    )

    if not batch_df_valid:
        if batch_source == "Upload Batch CSV":
            st.caption("Upload a valid batch CSV before processing.")
        else:
            st.caption("Generate and review a valid batch table before processing.")

    if not batch_images:
        st.caption("Upload matching label images before processing.")

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
            batch_start_time = time.perf_counter()

            for row_number, (_, row) in enumerate(batch_df_for_processing.iterrows(), start=1):
                file_name = clean_cell(row.get("file_name", ""))
                display_file_name = file_name if file_name else f"row {row_number}"
                status_text.write(f"Processing {display_file_name}...")

                if not file_name:
                    batch_results.append(
                        add_processing_time(
                            build_batch_failure_result(
                                row,
                                "CSV row is missing a file_name value.",
                                file_name="",
                            ),
                            None,
                        )
                    )
                elif file_name not in uploaded_images_by_name:
                    batch_results.append(
                        add_processing_time(
                            build_batch_failure_result(
                                row,
                                "Matching image file was not uploaded.",
                                file_name=file_name,
                            ),
                            None,
                        )
                    )
                else:
                    image_file = uploaded_images_by_name[file_name]
                    item_start_time = time.perf_counter()

                    try:
                        detected_batch_text = extract_text_from_uploaded_image(image_file)
                        item_elapsed_seconds = time.perf_counter() - item_start_time
                        batch_result = verify_batch_label(row, detected_batch_text)
                        batch_results.append(
                            add_processing_time(batch_result, item_elapsed_seconds)
                        )

                    except Exception as error:
                        item_elapsed_seconds = time.perf_counter() - item_start_time
                        batch_results.append(
                            add_processing_time(
                                build_batch_failure_result(
                                    row,
                                    f"OCR or verification failed: {error}",
                                    file_name=file_name,
                                ),
                                item_elapsed_seconds,
                            )
                        )

                progress_bar.progress(row_number / len(batch_df_for_processing))

            batch_elapsed_seconds = time.perf_counter() - batch_start_time
            status_text.write(
                f"Batch processing complete in {format_elapsed_time(batch_elapsed_seconds)}."
            )

            completed_timings = [
                row.get("Processing Time (s)")
                for row in batch_results
                if row.get("Processing Time (s)") is not None
            ]

            if completed_timings:
                average_seconds = sum(completed_timings) / len(completed_timings)
                metric_col1, metric_col2 = st.columns(2)

                with metric_col1:
                    st.metric("Total Batch Time", format_elapsed_time(batch_elapsed_seconds))

                with metric_col2:
                    st.metric("Average OCR Time", format_elapsed_time(average_seconds))

                if average_seconds <= 5:
                    st.caption(
                        "Average OCR time is within the 5-second target from stakeholder feedback."
                    )
                else:
                    st.warning(
                        "Average OCR time is above the 5-second stakeholder target. "
                        "Production deployment would need stronger optimization, queueing, or worker scaling."
                    )

            display_batch_results(batch_results)

            st.caption(
                "Prototype limitation: Batch mode is designed for proof-of-concept testing. "
                "Large production batches would require queueing, monitoring, and stronger error handling."
            )