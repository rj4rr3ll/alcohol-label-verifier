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

    Percent signs are preserved because they are meaningful for alcohol-content
    checks.
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


def tokenize_normalized_text(value: str) -> list[str]:
    """
    Return normalized alphanumeric tokens.

    Token-level checks prevent unsafe substring matches such as OLD TOM matching
    OLD TOMATO, while still allowing punctuation/case differences such as
    Stone's Throw versus STONE'S THROW.
    """
    normalized = normalize_text(value)
    return re.findall(r"[A-Z0-9%]+", normalized)


def contains_normalized_phrase(expected: str, detected_text: str) -> bool:
    """
    Return True when the expected value appears as a full token sequence inside
    the detected text.

    This is stricter than a raw substring check. It allows:
    - OLD TOM DISTILLERY inside OLD TOM DISTILLERY / 750 ML
    - Stone's Throw matching STONE'S THROW

    It does not allow:
    - OLD TOM matching OLD TOMATO
    - RYE WHISKY passing when only WHISKY appears
    """
    normalized_expected = normalize_text(expected)
    normalized_detected = normalize_text(detected_text)

    if not normalized_expected or not normalized_detected:
        return False

    escaped = re.escape(normalized_expected).replace(r"\ ", r"\s+")
    pattern = rf"(?<![A-Z0-9]){escaped}(?![A-Z0-9])"
    return re.search(pattern, normalized_detected) is not None


def token_coverage(expected: str, candidate: str) -> float:
    """
    Measure how many expected tokens are present in the candidate line.

    Duplicate words are not important for these label fields, so set coverage is
    sufficient and keeps the behavior easy to explain.
    """
    expected_tokens = set(tokenize_normalized_text(expected))
    candidate_tokens = set(tokenize_normalized_text(candidate))

    if not expected_tokens:
        return 0.0

    return len(expected_tokens.intersection(candidate_tokens)) / len(expected_tokens)


def calculate_line_match_score(expected: str, candidate: str) -> int:
    """
    Score a candidate OCR line without allowing subset matches to pass.

    The previous implementation used token_set_ratio, which can return 100 when
    the candidate contains only a subset of the expected phrase. For compliance
    review, that is too permissive: "Whisky" should not pass for
    "Straight Rye Whisky".

    This score favors full-string similarity and token order similarity, then
    caps the result when too many expected tokens are missing.
    """
    normalized_expected = normalize_text(expected)
    normalized_candidate = normalize_text(candidate)

    if not normalized_expected or not normalized_candidate:
        return 0

    if normalized_expected == normalized_candidate:
        return 100

    if contains_normalized_phrase(expected, candidate):
        return 100

    ratio_score = fuzz.ratio(normalized_expected, normalized_candidate)
    token_sort_score = fuzz.token_sort_ratio(normalized_expected, normalized_candidate)
    score = max(ratio_score, token_sort_score)

    coverage = token_coverage(expected, candidate)

    # If the candidate is missing a meaningful share of the expected words,
    # never let it pass solely because the remaining word is highly similar.
    if coverage < 0.50:
        score = min(score, 60)
    elif coverage < 0.75:
        score = min(score, 82)

    return int(round(score))


def get_best_matching_line(expected: str, detected_text: str) -> tuple[str, int]:
    """
    Compare expected text against each detected/OCR text line.
    Return the best matching line and score.
    """
    if not expected or not detected_text:
        return "", 0

    lines = [line.strip() for line in detected_text.splitlines() if line.strip()]

    if not lines:
        return "", 0

    best_line = ""
    best_score = 0

    for line in lines:
        score = calculate_line_match_score(expected, line)

        if score > best_score:
            best_score = score
            best_line = line

    return best_line, best_score


def verify_text_field(
    check_name: str,
    expected: str,
    detected_text: str,
    pass_threshold: int = 92,
    review_threshold: int = 75,
) -> dict:
    """
    Generic field verification using normalized full-token matching and fuzzy
    matching.

    The function is intentionally conservative. Clear normalized matches pass,
    close OCR/case/punctuation differences can pass, partial or uncertain
    matches are routed to manual review, and missing values fail.
    """
    expected = expected.strip() if expected else ""

    if not expected:
        return {
            "Check": check_name,
            "Expected": "",
            "Detected": "",
            "Result": REVIEW,
            "Notes": "No expected value was provided.",
        }

    if not detected_text or not detected_text.strip():
        return {
            "Check": check_name,
            "Expected": expected,
            "Detected": "",
            "Result": FAIL,
            "Notes": "No label text was provided for comparison.",
        }

    if contains_normalized_phrase(expected, detected_text):
        return {
            "Check": check_name,
            "Expected": expected,
            "Detected": expected,
            "Result": PASS,
            "Notes": "Expected value found on label.",
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
        "Notes": f"{notes} Match score: {score}.",
    }


def normalize_ocr_number(value: str) -> float | None:
    """
    Normalize numeric OCR mistakes in alcohol-content contexts.

    Examples:
    - 4S -> 45
    - 9O -> 90
    - 7S0 -> 750
    """
    if not value:
        return None

    normalized = str(value).upper()
    normalized = normalized.replace("O", "0")
    normalized = normalized.replace("I", "1")
    normalized = normalized.replace("L", "1")
    normalized = normalized.replace("|", "1")
    normalized = normalized.replace("S", "5")
    normalized = normalized.replace(",", ".")
    normalized = re.sub(r"[^0-9.]", "", normalized)

    if not normalized:
        return None

    try:
        return float(normalized)
    except ValueError:
        return None


def extract_percent_values(text: str) -> list[float]:
    """
    Extract percentage values such as:
    - 45%
    - 45.0%
    - 45 percent
    - 45% ABV
    - 45% Alc./Vol.
    - 4S% ALC/VOL
    """
    if not text:
        return []

    text_upper = text.upper()

    patterns = [
        r"\b([0-9OILS|]{1,3}(?:[.,][0-9OILS|]+)?)\s*%",
        r"\b([0-9OILS|]{1,3}(?:[.,][0-9OILS|]+)?)\s*PERCENT\b",
        r"\b([0-9OILS|]{1,3}(?:[.,][0-9OILS|]+)?)\s*%?\s*(?:ALC\.?\s*/?\s*VOL\.?|ABV)\b",
    ]

    values = []

    for pattern in patterns:
        matches = re.findall(pattern, text_upper)

        for match in matches:
            number = normalize_ocr_number(match)

            if number is not None and 0 < number <= 100:
                values.append(number)

    unique_values = []

    for value in values:
        if value not in unique_values:
            unique_values.append(value)

    return unique_values


def extract_proof_values(text: str) -> list[float]:
    """
    Extract proof values such as:
    - 90 Proof
    - 9O Proof
    """
    if not text:
        return []

    text_upper = text.upper()

    pattern = r"\b([0-9OILS|]{1,3}(?:[.,][0-9OILS|]+)?)\s*PROOF\b"
    matches = re.findall(pattern, text_upper)

    values = []

    for match in matches:
        number = normalize_ocr_number(match)

        if number is not None and 0 < number <= 200:
            values.append(number)

    unique_values = []

    for value in values:
        if value not in unique_values:
            unique_values.append(value)

    return unique_values


def format_number_for_display(value: float) -> str:
    """
    Format numbers cleanly for display.
    Example: 45.0 -> 45
    """
    if float(value).is_integer():
        return str(int(value))

    return str(value)


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
            "Notes": "No expected alcohol content was provided.",
        }

    expected_percentages = extract_percent_values(expected)
    expected_proofs = extract_proof_values(expected)

    detected_percentages = extract_percent_values(detected_text)
    detected_proofs = extract_proof_values(detected_text)

    detected_summary_parts = []

    if detected_percentages:
        detected_summary_parts.append(
            "Percent values: "
            + ", ".join(
                f"{format_number_for_display(value)}%"
                for value in detected_percentages
            )
        )

    if detected_proofs:
        detected_summary_parts.append(
            "Proof values: "
            + ", ".join(
                format_number_for_display(value)
                for value in detected_proofs
            )
        )

    detected_summary = "; ".join(detected_summary_parts)

    for expected_abv in expected_percentages:
        for detected_abv in detected_percentages:
            if abs(expected_abv - detected_abv) <= 0.2:
                return {
                    "Check": "Alcohol Content",
                    "Expected": expected,
                    "Detected": detected_summary,
                    "Result": PASS,
                    "Notes": "Expected ABV found on label.",
                }

        for detected_proof in detected_proofs:
            if abs((expected_abv * 2) - detected_proof) <= 0.5:
                return {
                    "Check": "Alcohol Content",
                    "Expected": expected,
                    "Detected": detected_summary,
                    "Result": PASS,
                    "Notes": "Expected ABV matches detected proof.",
                }

    for expected_proof in expected_proofs:
        for detected_proof in detected_proofs:
            if abs(expected_proof - detected_proof) <= 0.5:
                return {
                    "Check": "Alcohol Content",
                    "Expected": expected,
                    "Detected": detected_summary,
                    "Result": PASS,
                    "Notes": "Expected proof found on label.",
                }

        for detected_abv in detected_percentages:
            if abs((detected_abv * 2) - expected_proof) <= 0.5:
                return {
                    "Check": "Alcohol Content",
                    "Expected": expected,
                    "Detected": detected_summary,
                    "Result": PASS,
                    "Notes": "Expected proof matches detected ABV.",
                }

    if detected_percentages or detected_proofs:
        return {
            "Check": "Alcohol Content",
            "Expected": expected,
            "Detected": detected_summary,
            "Result": REVIEW,
            "Notes": "Alcohol content found, but it does not clearly match the expected value.",
        }

    alcohol_marker_pattern = r"(%|ALC\.?\s*/?\s*VOL\.?|ABV|PROOF)"

    if detected_text and re.search(alcohol_marker_pattern, detected_text.upper()):
        return {
            "Check": "Alcohol Content",
            "Expected": expected,
            "Detected": "Alcohol content marker found, but numeric value was not clearly captured",
            "Result": REVIEW,
            "Notes": (
                "OCR detected an alcohol-content marker such as '%', 'ALC/VOL', "
                "or 'PROOF', but did not capture a clear numeric value. "
                "Manual review or text correction is recommended."
            ),
        }

    return {
        "Check": "Alcohol Content",
        "Expected": expected,
        "Detected": "",
        "Result": FAIL,
        "Notes": "Alcohol content was not found on the label.",
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
            "Notes": "No expected net contents value was provided.",
        }

    normalized_expected = normalize_net_contents(expected)
    normalized_detected = normalize_net_contents(detected_text)

    if contains_normalized_phrase(normalized_expected, normalized_detected):
        return {
            "Check": "Net Contents",
            "Expected": expected,
            "Detected": expected,
            "Result": PASS,
            "Notes": "Expected net contents found on label.",
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
        "Notes": f"{notes} Match score: {score}.",
    }


def verify_optional_text_field(
    check_name: str,
    expected: str,
    detected_text: str,
    pass_threshold: int = 92,
    review_threshold: int = 75,
) -> dict | None:
    """
    Verify an optional expected field only when the reviewer/application provided
    a value.

    Optional fields improve label coverage without penalizing applications that do
    not include a value in the prototype workflow.
    """
    expected = expected.strip() if expected else ""

    if not expected:
        return None

    return verify_text_field(
        check_name=check_name,
        expected=expected,
        detected_text=detected_text,
        pass_threshold=pass_threshold,
        review_threshold=review_threshold,
    )


def verify_name_address(expected: str, detected_text: str) -> dict | None:
    """
    Verify the expected bottler/producer/importer name and address when provided.

    This prototype treats the value as an optional text-matching check. It does
    not decide which address statement is legally required for a given beverage
    or business role.
    """
    return verify_optional_text_field(
        "Name/Address",
        expected,
        detected_text,
        pass_threshold=88,
        review_threshold=72,
    )


def verify_country_of_origin(expected: str, detected_text: str) -> dict | None:
    """
    Verify country of origin text when provided.

    Country of origin is most relevant for imported products. The check is kept
    optional because domestic products may not have an expected country-of-origin
    value in the application data.
    """
    return verify_optional_text_field(
        "Country of Origin",
        expected,
        detected_text,
        pass_threshold=90,
        review_threshold=75,
    )


def verify_core_fields(
    detected_text: str,
    brand_name: str,
    class_type: str,
    alcohol_content: str,
    net_contents: str,
    name_address: str = "",
    country_of_origin: str = "",
) -> list[dict]:
    """
    Run core field checks plus optional label checks when expected values are
    provided.
    """
    results = [
        verify_text_field("Brand Name", brand_name, detected_text),
        verify_text_field("Class/Type", class_type, detected_text),
        verify_alcohol_content(alcohol_content, detected_text),
        verify_net_contents(net_contents, detected_text),
    ]

    optional_results = [
        verify_name_address(name_address, detected_text),
        verify_country_of_origin(country_of_origin, detected_text),
    ]

    results.extend(
        result for result in optional_results
        if result is not None
    )

    return results


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