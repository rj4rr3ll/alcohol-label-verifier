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


def normalize_column_name(column_name: str) -> str:
    """
    Normalize CSV column names so small formatting differences do not break import.
    Example: Brand Name -> brand_name
    """
    return (
        column_name.strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


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

    Defaults to True because government warning is mandatory for the expected
    alcohol label workflow in this prototype.
    """
    if pd.isna(value):
        return True

    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()

    if text in ["false", "no", "n", "0", "not required"]:
        return False

    return True


def verify_batch_label(row: pd.Series, detected_text: str) -> dict:
    """
    Verify one batch label using expected CSV fields and OCR text.
    """
    warning_required = True

    if "warning_required" in row.index:
        warning_required = parse_warning_required(row["warning_required"])

    detailed_results = verify_core_fields(
        detected_text=detected_text,
        brand_name=str(row.get("brand_name", "")),
        class_type=str(row.get("class_type", "")),
        alcohol_content=str(row.get("alcohol_content", "")),
        net_contents=str(row.get("net_contents", "")),
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
        "File Name": str(row.get("file_name", "")),
        "Overall Result": overall_result,
        "Passed Checks": passed_checks,
        "Manual Review Checks": review_checks,
        "Failed Checks": failed_checks,
        "Brand Name": str(row.get("brand_name", "")),
        "Class/Type": str(row.get("class_type", "")),
        "Alcohol Content": str(row.get("alcohol_content", "")),
        "Net Contents": str(row.get("net_contents", "")),
        "Issues": "; ".join(issues) if issues else "No review or failure items found.",
        "OCR Text Preview": detected_text[:250].replace("\n", " "),
    }