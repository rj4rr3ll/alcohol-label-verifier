import re
import string
from rapidfuzz import fuzz


PASS = "PASS"
REVIEW = "REVIEW"
FAIL = "FAIL"


def normalize_text(value: str) -> str:
    """
    Normalize text for comparison:
    - Uppercase
    - Replace curly punctuation
    - Remove most punctuation
    - Collapse whitespace
    """
    if not value:
        return ""

    text = value.upper()
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("&", " AND ")

    punctuation_to_remove = string.punctuation.replace("%", "")
    text = text.translate(str.maketrans("", "", punctuation_to_remove))

    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_best_matching_line(expected: str, detected_text: str) -> tuple[str, int]:
    """
    Compare expected text against each OCR/detected text line.
    Return the best matching line and score.
    """
    if not expected or not detected_text:
        return "", 0

    lines = [line.strip() for line in detected_text.splitlines() if line.strip()]
    if not lines:
        return "", 0

    normalized_expected = normalize_text(expected)

    best_line = ""
    best_score = 0

    for line in lines:
        score = fuzz.token_set_ratio(normalized_expected, normalize_text(line))
        if score > best_score:
            best_score = score
            best_line = line

    return best_line, int(best_score)


def verify_text_field(
    check_name: str,
    expected: str,
    detected_text: str,
    pass_threshold: int = 92,
    review_threshold: int = 75,
) -> dict:
    """
    Generic field verification using normalized exact match and fuzzy matching.
    """
    expected = expected.strip() if expected else ""

    if not expected:
        return {
            "Check": check_name,
            "Expected": "",
            "Detected": "",
            "Result": REVIEW,
            "Notes": "No expected value was provided."
        }

    if not detected_text or not detected_text.strip():
        return {
            "Check": check_name,
            "Expected": expected,
            "Detected": "",
            "Result": FAIL,
            "Notes": "No label text was provided for comparison."
        }

    normalized_expected = normalize_text(expected)
    normalized_detected = normalize_text(detected_text)

    if normalized_expected in normalized_detected:
        return {
            "Check": check_name,
            "Expected": expected,
            "Detected": expected,
            "Result": PASS,
            "Notes": "Expected value found on label."
        }

    best_line, score = get_best_matching_line(expected, detected_text)

    if score >= pass_threshold:
        result = PASS
        notes = "Close normalized match found on label."
    elif score >= review_threshold:
        result = REVIEW
        notes = "Similar text found; manual review recommended."
    else:
        result = FAIL
        notes = "Expected value was not found on label."

    return {
        "Check": check_name,
        "Expected": expected,
        "Detected": best_line,
        "Result": result,
        "Notes": f"{notes} Match score: {score}."
    }


def extract_percent_values(text: str) -> list[float]:
    """
    Extract percentage values such as 45%, 45.0%, or 45 percent.
    """
    if not text:
        return []

    pattern = r"(\d+(?:\.\d+)?)\s*(?:%|PERCENT)"
    matches = re.findall(pattern, text.upper())

    return [float(match) for match in matches]


def extract_proof_values(text: str) -> list[float]:
    """
    Extract proof values such as 90 Proof.
    """
    if not text:
        return []

    pattern = r"(\d+(?:\.\d+)?)\s*PROOF"
    matches = re.findall(pattern, text.upper())

    return [float(match) for match in matches]


def verify_alcohol_content(expected: str, detected_text: str) -> dict:
    """
    Verify alcohol content using ABV percentages and proof.
    For distilled spirits, proof is approximately 2x ABV.
    Example: 45% ABV = 90 proof.
    """
    expected = expected.strip() if expected else ""

    if not expected:
        return {
            "Check": "Alcohol Content",
            "Expected": "",
            "Detected": "",
            "Result": REVIEW,
            "Notes": "No expected alcohol content was provided."
        }

    expected_percentages = extract_percent_values(expected)
    expected_proofs = extract_proof_values(expected)

    detected_percentages = extract_percent_values(detected_text)
    detected_proofs = extract_proof_values(detected_text)

    detected_summary_parts = []
    if detected_percentages:
        detected_summary_parts.append(
            "Percent values: " + ", ".join(str(x).rstrip("0").rstrip(".") + "%" for x in detected_percentages)
        )
    if detected_proofs:
        detected_summary_parts.append(
            "Proof values: " + ", ".join(str(x).rstrip("0").rstrip(".") for x in detected_proofs)
        )

    detected_summary = "; ".join(detected_summary_parts) if detected_summary_parts else ""

    for expected_abv in expected_percentages:
        for detected_abv in detected_percentages:
            if abs(expected_abv - detected_abv) <= 0.2:
                return {
                    "Check": "Alcohol Content",
                    "Expected": expected,
                    "Detected": detected_summary,
                    "Result": PASS,
                    "Notes": "Expected ABV found on label."
                }

        for detected_proof in detected_proofs:
            if abs((expected_abv * 2) - detected_proof) <= 0.5:
                return {
                    "Check": "Alcohol Content",
                    "Expected": expected,
                    "Detected": detected_summary,
                    "Result": PASS,
                    "Notes": "Expected ABV matches detected proof."
                }

    for expected_proof in expected_proofs:
        for detected_proof in detected_proofs:
            if abs(expected_proof - detected_proof) <= 0.5:
                return {
                    "Check": "Alcohol Content",
                    "Expected": expected,
                    "Detected": detected_summary,
                    "Result": PASS,
                    "Notes": "Expected proof found on label."
                }

        for detected_abv in detected_percentages:
            if abs((detected_abv * 2) - expected_proof) <= 0.5:
                return {
                    "Check": "Alcohol Content",
                    "Expected": expected,
                    "Detected": detected_summary,
                    "Result": PASS,
                    "Notes": "Expected proof matches detected ABV."
                }

    if detected_percentages or detected_proofs:
        return {
            "Check": "Alcohol Content",
            "Expected": expected,
            "Detected": detected_summary,
            "Result": REVIEW,
            "Notes": "Alcohol content found, but it does not clearly match the expected value."
        }

    return {
        "Check": "Alcohol Content",
        "Expected": expected,
        "Detected": "",
        "Result": FAIL,
        "Notes": "Alcohol content was not found on the label."
    }


def normalize_net_contents(value: str) -> str:
    """
    Normalize common net contents formats.
    Example: 750 mL, 750ml, 750 ML -> 750 ML
    """
    if not value:
        return ""

    text = value.upper()
    text = text.replace("MILLILITERS", "ML")
    text = text.replace("MILLILITRES", "ML")
    text = text.replace("LITERS", "L")
    text = text.replace("LITRES", "L")

    text = re.sub(r"(\d+)\s*ML", r"\1 ML", text)
    text = re.sub(r"(\d+)\s*L\b", r"\1 L", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def verify_net_contents(expected: str, detected_text: str) -> dict:
    """
    Verify net contents such as 750 mL or 1 L.
    """
    expected = expected.strip() if expected else ""

    if not expected:
        return {
            "Check": "Net Contents",
            "Expected": "",
            "Detected": "",
            "Result": REVIEW,
            "Notes": "No expected net contents value was provided."
        }

    normalized_expected = normalize_net_contents(expected)
    normalized_detected = normalize_net_contents(detected_text)

    if normalized_expected and normalized_expected in normalized_detected:
        return {
            "Check": "Net Contents",
            "Expected": expected,
            "Detected": expected,
            "Result": PASS,
            "Notes": "Expected net contents found on label."
        }

    best_line, score = get_best_matching_line(expected, detected_text)

    if score >= 90:
        result = PASS
        notes = "Close normalized net contents match found."
    elif score >= 75:
        result = REVIEW
        notes = "Similar net contents text found; manual review recommended."
    else:
        result = FAIL
        notes = "Expected net contents were not found on label."

    return {
        "Check": "Net Contents",
        "Expected": expected,
        "Detected": best_line,
        "Result": result,
        "Notes": f"{notes} Match score: {score}."
    }


def verify_core_fields(
    detected_text: str,
    brand_name: str,
    class_type: str,
    alcohol_content: str,
    net_contents: str,
) -> list[dict]:
    """
    Run all Phase 2 core field checks.
    """
    return [
        verify_text_field("Brand Name", brand_name, detected_text),
        verify_text_field("Class/Type", class_type, detected_text),
        verify_alcohol_content(alcohol_content, detected_text),
        verify_net_contents(net_contents, detected_text),
    ]


def determine_overall_result(results: list[dict]) -> str:
    """
    Determine overall result from field-level results.
    """
    result_values = [row["Result"] for row in results]

    if FAIL in result_values:
        return "FAIL"
    if REVIEW in result_values:
        return "MANUAL REVIEW RECOMMENDED"
    return "PASS"