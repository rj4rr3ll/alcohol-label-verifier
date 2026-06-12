import re

from src.matching import PASS, REVIEW, FAIL


STANDARD_GOVERNMENT_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)


REQUIRED_WARNING_PHRASES = [
    "according to the surgeon general",
    "women should not drink alcoholic beverages during pregnancy",
    "risk of birth defects",
    "consumption of alcoholic beverages impairs your ability to drive a car or operate machinery",
    "may cause health problems",
]


def normalize_spaces(text: str) -> str:
    """
    Collapse repeated whitespace while preserving case.
    """
    if not text:
        return ""

    return re.sub(r"\s+", " ", text).strip()


def normalize_for_phrase_check(text: str) -> str:
    """
    Normalize text for checking required warning phrases.
    """
    if not text:
        return ""

    text = text.lower()
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = re.sub(r"\s+", " ", text).strip()
    return text


def has_correct_warning_heading(detected_text: str) -> bool:
    """
    Check for the exact all-caps warning heading.
    """
    if not detected_text:
        return False

    return "GOVERNMENT WARNING:" in detected_text


def has_incorrect_case_warning_heading(detected_text: str) -> bool:
    """
    Detect warning headings that exist but are not correctly capitalized.
    Example: Government Warning:
    """
    if not detected_text:
        return False

    pattern = r"government\s+warning\s*:"
    matches = re.findall(pattern, detected_text, flags=re.IGNORECASE)

    if not matches:
        return False

    return not has_correct_warning_heading(detected_text)


def count_required_warning_phrases(detected_text: str) -> tuple[int, list[str]]:
    """
    Count required warning phrases present in detected label text.
    """
    normalized_text = normalize_for_phrase_check(detected_text)

    found_phrases = []
    missing_phrases = []

    for phrase in REQUIRED_WARNING_PHRASES:
        if phrase in normalized_text:
            found_phrases.append(phrase)
        else:
            missing_phrases.append(phrase)

    return len(found_phrases), missing_phrases


def verify_government_warning(
    detected_text: str,
    warning_required: bool = True,
) -> dict:
    """
    Validate the alcohol government health warning statement.

    Prototype limitation:
    This function checks text and capitalization. It does not verify font size,
    bold formatting, or label placement from image pixels.
    """
    expected = "Required" if warning_required else "Not required"

    if not warning_required:
        return {
            "Check": "Government Warning",
            "Expected": expected,
            "Detected": "Not checked",
            "Result": PASS,
            "Notes": "Government warning check was not required for this review."
        }

    if not detected_text or not detected_text.strip():
        return {
            "Check": "Government Warning",
            "Expected": expected,
            "Detected": "",
            "Result": FAIL,
            "Notes": "No label text was provided for warning validation."
        }

    cleaned_text = normalize_spaces(detected_text)

    correct_heading = has_correct_warning_heading(cleaned_text)
    incorrect_case_heading = has_incorrect_case_warning_heading(cleaned_text)
    phrase_count, missing_phrases = count_required_warning_phrases(cleaned_text)

    if incorrect_case_heading:
        return {
            "Check": "Government Warning",
            "Expected": "GOVERNMENT WARNING:",
            "Detected": "Incorrect warning heading capitalization",
            "Result": FAIL,
            "Notes": "Warning heading must appear as 'GOVERNMENT WARNING:' in all caps."
        }

    if correct_heading and phrase_count == len(REQUIRED_WARNING_PHRASES):
        return {
            "Check": "Government Warning",
            "Expected": "Standard government warning statement",
            "Detected": "Warning heading and required phrases found",
            "Result": PASS,
            "Notes": "Government warning text appears to be present with correct heading capitalization."
        }

    if correct_heading and phrase_count > 0:
        return {
            "Check": "Government Warning",
            "Expected": "Standard government warning statement",
            "Detected": f"Found {phrase_count} of {len(REQUIRED_WARNING_PHRASES)} required phrases",
            "Result": REVIEW,
            "Notes": (
                "Warning heading was found, but the warning text appears incomplete. "
                f"Missing phrase examples: {', '.join(missing_phrases[:2])}."
            )
        }

    if phrase_count >= 2:
        return {
            "Check": "Government Warning",
            "Expected": "Standard government warning statement",
            "Detected": f"Found {phrase_count} warning-related phrases but no correct heading",
            "Result": REVIEW,
            "Notes": "Warning-like text was found, but the required 'GOVERNMENT WARNING:' heading was missing."
        }

    return {
        "Check": "Government Warning",
        "Expected": "Standard government warning statement",
        "Detected": "",
        "Result": FAIL,
        "Notes": "Required government warning statement was not found on the label."
    }