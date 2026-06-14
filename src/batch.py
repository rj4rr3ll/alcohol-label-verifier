import re

import pandas as pd

from src.matching import verify_core_fields, determine_overall_result
from src.warning_check import verify_government_warning


REQUIRED_BATCH_COLUMNS = [
    "file_name",
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
]


FALSE_WARNING_VALUES = {"false", "no", "n", "0", "not required", "unchecked"}
TRUE_WARNING_VALUES = {"true", "yes", "y", "1", "required", "checked"}


def clean_cell(value) -> str:
    """
    Convert a CSV cell into safe display/comparison text.

    Pandas represents blank CSV cells as NaN. Calling str() on those cells turns
    them into the literal text "nan", which can leak into the UI and verification
    results. This helper keeps missing cells empty and trims real values.
    """
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    return str(value).strip()


def normalize_column_name(column_name: str) -> str:
    """
    Normalize CSV column names so small formatting differences do not break import.

    Examples:
    - Brand Name -> brand_name
    - Class-Type -> class_type
    - Name/Address -> name_address
    - Country of Origin -> country_of_origin
    """
    cleaned_name = clean_cell(column_name).lower()
    cleaned_name = re.sub(r"[^a-z0-9]+", "_", cleaned_name)
    cleaned_name = re.sub(r"_+", "_", cleaned_name)
    cleaned_name = cleaned_name.strip("_")

    return cleaned_name


def normalize_batch_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize batch CSV column names.
    """
    renamed_columns = {
        column: normalize_column_name(column)
        for column in df.columns
    }

    return df.rename(columns=renamed_columns)


def validate_batch_dataframe(df: pd.DataFrame) -> list[str]:
    """
    Return a list of missing required columns.
    """
    normalized_columns = set(df.columns)

    return [
        column for column in REQUIRED_BATCH_COLUMNS
        if column not in normalized_columns
    ]


def parse_warning_required(value) -> bool:
    """
    Parse warning_required values from CSV.

    Defaults to True because the government warning is mandatory for the expected
    alcohol label workflow in this prototype.
    """
    text = clean_cell(value).lower()

    if not text:
        return True

    if text in FALSE_WARNING_VALUES:
        return False

    if text in TRUE_WARNING_VALUES:
        return True

    return True


def build_batch_failure_result(row: pd.Series, issue: str, file_name: str | None = None) -> dict:
    """
    Build a consistent batch result row for missing-image and processing errors.
    """
    resolved_file_name = clean_cell(file_name) if file_name is not None else clean_cell(row.get("file_name", ""))

    return {
        "File Name": resolved_file_name,
        "Overall Result": "FAIL",
        "Passed Checks": 0,
        "Manual Review Checks": 0,
        "Failed Checks": 1,
        "Brand Name": clean_cell(row.get("brand_name", "")),
        "Class/Type": clean_cell(row.get("class_type", "")),
        "Alcohol Content": clean_cell(row.get("alcohol_content", "")),
        "Net Contents": clean_cell(row.get("net_contents", "")),
        "Name/Address": clean_cell(row.get("name_address", "")),
        "Country of Origin": clean_cell(row.get("country_of_origin", "")),
        "Issues": issue,
        "OCR Text Preview": "",
    }


def verify_batch_label(row: pd.Series, detected_text: str) -> dict:
    """
    Verify one batch label using expected CSV fields and OCR text.
    """
    warning_required = True

    if "warning_required" in row.index:
        warning_required = parse_warning_required(row["warning_required"])

    file_name = clean_cell(row.get("file_name", ""))
    brand_name = clean_cell(row.get("brand_name", ""))
    class_type = clean_cell(row.get("class_type", ""))
    alcohol_content = clean_cell(row.get("alcohol_content", ""))
    net_contents = clean_cell(row.get("net_contents", ""))
    name_address = clean_cell(row.get("name_address", ""))
    country_of_origin = clean_cell(row.get("country_of_origin", ""))

    detailed_results = verify_core_fields(
        detected_text=detected_text,
        brand_name=brand_name,
        class_type=class_type,
        alcohol_content=alcohol_content,
        net_contents=net_contents,
        name_address=name_address,
        country_of_origin=country_of_origin,
    )

    detailed_results.append(
        verify_government_warning(
            detected_text=detected_text,
            warning_required=warning_required,
        )
    )

    overall_result = determine_overall_result(detailed_results)

    passed_checks = sum(1 for item in detailed_results if item["Result"] == "PASS")
    review_checks = sum(1 for item in detailed_results if item["Result"] == "REVIEW")
    failed_checks = sum(1 for item in detailed_results if item["Result"] == "FAIL")

    issues = [
        f"{item['Check']}: {item['Notes']}"
        for item in detailed_results
        if item["Result"] in ["REVIEW", "FAIL"]
    ]

    return {
        "File Name": file_name,
        "Overall Result": overall_result,
        "Passed Checks": passed_checks,
        "Manual Review Checks": review_checks,
        "Failed Checks": failed_checks,
        "Brand Name": brand_name,
        "Class/Type": class_type,
        "Alcohol Content": alcohol_content,
        "Net Contents": net_contents,
        "Name/Address": name_address,
        "Country of Origin": country_of_origin,
        "Issues": "; ".join(issues) if issues else "No review or failure items found.",
        "OCR Text Preview": clean_cell(detected_text)[:250].replace("\n", " "),
    }