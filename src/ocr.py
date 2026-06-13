import os
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass

from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import pytesseract


COMMON_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]

COMMON_ML_SIZES = {
    50, 100, 187, 200, 250, 300, 330, 341, 355, 375,
    500, 700, 720, 750, 1000, 1500, 1750,
}

COMMON_L_SIZES = {
    1.0, 1.5, 1.75,
}

FIELD_ABV = "abv"
FIELD_PROOF = "proof"
FIELD_NET_CONTENTS = "net_contents"


@dataclass(frozen=True)
class FieldCandidate:
    """
    Structured value recovered from OCR output.

    These candidates help recover small but important compliance fields such as
    ABV, proof, and net contents without dumping every noisy OCR pass into the
    user-facing text box.
    """

    field: str
    display: str
    value: float
    source: str


@dataclass(frozen=True)
class OcrRegion:
    """
    Defines one image region and OCR configuration.
    """

    title: str
    image: Image.Image
    config: str
    threshold: bool = False
    numeric_only: bool = False


def configure_tesseract() -> tuple[bool, str]:
    """
    Configure Tesseract for local OCR.

    Returns:
        (is_ready, message)
    """
    if shutil.which("tesseract"):
        return True, "Tesseract is available on PATH."

    for path in COMMON_TESSERACT_PATHS:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            return True, f"Tesseract found at {path}."

    return (
        False,
        "Tesseract OCR engine was not found. Install Tesseract or use manual text entry.",
    )


def get_resample_filter():
    """
    Return a high-quality resize filter while preserving compatibility across
    Pillow versions.
    """
    try:
        return Image.Resampling.LANCZOS
    except AttributeError:
        return Image.LANCZOS


def prepare_base_image(image: Image.Image) -> Image.Image:
    """
    Standardize image orientation and color mode.
    """
    image = ImageOps.exif_transpose(image)

    if image.mode != "RGB":
        image = image.convert("RGB")

    return image


def upscale_if_needed(image: Image.Image, min_width: int = 1600) -> Image.Image:
    """
    Upscale smaller images to improve OCR on small label text.
    """
    width, height = image.size

    if width >= min_width:
        return image

    scale = min_width / width
    new_size = (int(width * scale), int(height * scale))

    return image.resize(new_size, get_resample_filter())


def preprocess_image(
    image: Image.Image,
    min_width: int = 1600,
    contrast: float = 2.0,
    sharpen: bool = True,
) -> Image.Image:
    """
    General OCR preprocessing:
    - Fix orientation
    - Convert to RGB
    - Upscale
    - Grayscale
    - Autocontrast
    - Increase contrast
    - Sharpen
    """
    image = prepare_base_image(image)
    image = upscale_if_needed(image, min_width=min_width)
    image = ImageOps.grayscale(image)
    image = ImageOps.autocontrast(image)
    image = ImageEnhance.Contrast(image).enhance(contrast)

    if sharpen:
        image = image.filter(ImageFilter.SHARPEN)

    return image


def preprocess_threshold_image(
    image: Image.Image,
    threshold: int = 175,
    min_width: int = 1600,
    contrast: float = 2.0,
) -> Image.Image:
    """
    Higher-contrast preprocessing for faint or low-contrast text.

    Thresholding can help recover small ABV/net-contents text, but it can also
    introduce false reads. This is why thresholded regions are used carefully.
    """
    image = preprocess_image(
        image,
        min_width=min_width,
        contrast=contrast,
        sharpen=True,
    )
    image = image.point(lambda pixel: 255 if pixel > threshold else 0)

    return image


def crop_percent(
    image: Image.Image,
    left: float,
    top: float,
    right: float,
    bottom: float,
) -> Image.Image:
    """
    Crop a region using percentages of image width and height.
    """
    width, height = image.size

    left_px = max(0, min(width, int(width * left)))
    top_px = max(0, min(height, int(height * top)))
    right_px = max(0, min(width, int(width * right)))
    bottom_px = max(0, min(height, int(height * bottom)))

    if right_px <= left_px:
        right_px = min(width, left_px + 1)

    if bottom_px <= top_px:
        bottom_px = min(height, top_px + 1)

    return image.crop((left_px, top_px, right_px, bottom_px))


def dark_pixel_density(image: Image.Image, threshold: int = 225) -> float:
    """
    Estimate how much visible content exists in an image region.

    This helps distinguish a true side-by-side label sheet from a single
    wide document that has blank space on the right.
    """
    if image.width == 0 or image.height == 0:
        return 0.0

    image = prepare_base_image(image)
    image = ImageOps.grayscale(image)
    image = image.resize((120, 120), get_resample_filter())

    pixels = list(image.getdata())

    if not pixels:
        return 0.0

    dark_pixels = sum(1 for pixel in pixels if pixel < threshold)

    return dark_pixels / len(pixels)


def should_use_side_by_side_region_ocr(image: Image.Image) -> bool:
    """
    Detect likely side-by-side front/back label sheets.

    Whole-image OCR performs poorly on true side-by-side sheets because
    Tesseract reads across columns. But some single-label documents are also
    wide, so aspect ratio alone is not enough.

    This checks that both the left and right label areas contain meaningful
    visual content before using side-by-side OCR.
    """
    width, height = image.size

    if height == 0:
        return False

    aspect_ratio = width / height

    if width < 500 or aspect_ratio < 1.05:
        return False

    left_region = crop_percent(image, 0.03, 0.05, 0.50, 0.92)
    right_region = crop_percent(image, 0.52, 0.05, 0.98, 0.92)

    left_density = dark_pixel_density(left_region)
    right_density = dark_pixel_density(right_region)

    # A true side-by-side label sheet should have meaningful content on both
    # sides. A single wide document often has text on the left and blank space
    # on the right.
    if left_density < 0.06 or right_density < 0.06:
        return False

    return True


def get_side_by_side_regions(image: Image.Image) -> list[OcrRegion]:
    """
    Define visible OCR regions for side-by-side front/back label sheets.

    These regions are shown to the reviewer. Do not include noisy candidate-only
    regions here because they can create false visible text such as 43% ALC/VOL.
    """
    front_title = "Front / Brand Label OCR"
    back_title = "Back Label OCR"

    return [
        OcrRegion(
            title=front_title,
            image=crop_percent(image, 0.03, 0.04, 0.49, 0.27),
            config="--oem 3 --psm 6",
        ),
        OcrRegion(
            title=front_title,
            image=crop_percent(image, 0.06, 0.22, 0.48, 0.51),
            config="--oem 3 --psm 6",
        ),
        OcrRegion(
            title=front_title,
            image=crop_percent(image, 0.03, 0.58, 0.50, 0.90),
            config="--oem 3 --psm 6",
        ),
        OcrRegion(
            title=back_title,
            image=crop_percent(image, 0.55, 0.04, 0.98, 0.31),
            config="--oem 3 --psm 6",
        ),
        OcrRegion(
            title=back_title,
            image=crop_percent(image, 0.55, 0.22, 0.98, 0.44),
            config="--oem 3 --psm 6",
        ),
        OcrRegion(
            title=back_title,
            image=crop_percent(image, 0.55, 0.34, 0.98, 0.86),
            config="--oem 3 --psm 6",
            threshold=True,
        ),
    ]


def get_side_by_side_candidate_regions(image: Image.Image) -> list[OcrRegion]:
    """
    Define candidate-only OCR regions for side-by-side label sheets.

    These regions are not displayed directly. They are used only to recover
    structured fields such as ABV and net contents.
    """
    return [
        OcrRegion(
            title="",
            image=crop_percent(image, 0.02, 0.58, 0.50, 0.90),
            config="--oem 3 --psm 6",
            threshold=False,
        ),
        OcrRegion(
            title="",
            image=crop_percent(image, 0.08, 0.66, 0.48, 0.91),
            config="--oem 3 --psm 11",
            threshold=True,
            numeric_only=True,
        ),
    ]


def get_general_regions(image: Image.Image) -> list[OcrRegion]:
    """
    Define visible OCR regions for ordinary single-label images.

    A single wide document can still need multiple OCR passes. For example,
    a large title may be skipped by one full-page OCR mode, while the warning
    paragraph may be better captured by a lower-region crop.
    """
    general_title = "Label OCR"

    return [
        # Page segmentation mode 4 often works better for single-column label
        # documents with large title text.
        OcrRegion(
            title=general_title,
            image=image,
            config="--oem 3 --psm 4",
        ),

        # Sparse-text mode helps recover large standalone text such as brand
        # names that psm 6 sometimes skips.
        OcrRegion(
            title=general_title,
            image=image,
            config="--oem 3 --psm 11",
        ),

        # Top crop helps recover large brand names such as OLD TOM DISTILLERY.
        OcrRegion(
            title=general_title,
            image=crop_percent(image, 0.00, 0.00, 1.00, 0.28),
            config="--oem 3 --psm 6",
        ),

        # Middle crop helps recover class/type, alcohol content, and net contents.
        OcrRegion(
            title=general_title,
            image=crop_percent(image, 0.00, 0.12, 1.00, 0.45),
            config="--oem 3 --psm 6",
        ),

        # Warning crop helps recover full government warning paragraph.
        OcrRegion(
            title=general_title,
            image=crop_percent(image, 0.00, 0.30, 1.00, 0.96),
            config="--oem 3 --psm 6",
        ),
    ]


def get_general_candidate_regions(image: Image.Image) -> list[OcrRegion]:
    """
    Define candidate-only regions for ordinary single-label uploads.
    """
    return [
        OcrRegion(
            title="",
            image=crop_percent(image, 0.00, 0.50, 1.00, 1.00),
            config="--oem 3 --psm 6",
            threshold=True,
        ),
        OcrRegion(
            title="",
            image=crop_percent(image, 0.00, 0.50, 1.00, 1.00),
            config="--oem 3 --psm 11",
            threshold=True,
            numeric_only=True,
        ),
    ]


def run_tesseract(image: Image.Image, config: str) -> str:
    """
    Run Tesseract safely with the provided configuration.
    """
    try:
        return pytesseract.image_to_string(image, config=config)
    except Exception:
        return ""


def run_region_ocr(region: OcrRegion) -> str:
    """
    Run OCR for one prepared region.
    """
    if region.threshold:
        processed = preprocess_threshold_image(region.image)
    else:
        processed = preprocess_image(region.image)

    config = region.config

    if region.numeric_only:
        config += (
            " -c tessedit_char_whitelist=0123456789.%"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz/"
        )

    return run_tesseract(processed, config=config)


def is_caption_line(line: str) -> bool:
    """
    Remove captions from sample images, such as 'Brand Label' and 'Back Label'.
    These are not part of the actual alcohol label.
    """
    key = re.sub(r"[^A-Z]+", "", line.upper())

    return key in {
        "BRANDLABEL",
        "BACKLABEL",
        "BRANDLABELBACKLABEL",
    }


def has_useful_numeric_pattern(line: str) -> bool:
    """
    Preserve lines that contain common structured label values without relying
    on brand-specific or product-specific vocabulary.

    Examples preserved:
    - 12345
    - 18% ALC/VOL
    - 200 ML
    - 750 ML
    - 90 PROOF
    - (1) According to...
    """
    if not line:
        return False

    text = line.upper()

    patterns = [
        r"\b\d{1,5}\b",                                  # standalone numbers
        r"\b\d{1,3}(?:\.\d+)?\s*%",                      # ABV percent
        r"\b\d{1,4}(?:\.\d+)?\s*(ML|L)\b",               # net contents
        r"\b\d{1,3}(?:\.\d+)?\s*PROOF\b",                # proof
        r"\(\s*\d+\s*\)",                                # warning numbering
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",    # email-like text
    ]

    return any(re.search(pattern, text) for pattern in patterns)


def has_natural_word_shape(line: str) -> bool:
    """
    Return True if a line looks like human-readable label text rather than a
    decorative border, barcode artifact, or OCR noise.

    This is intentionally general and does not depend on specific label words.
    """
    if not line:
        return False

    stripped = line.strip()

    # Short all-caps brand marks like ABC should be preserved.
    compact_letters = re.sub(r"[^A-Z]", "", stripped.upper())

    if (
        2 <= len(compact_letters) <= 5
        and stripped.upper() == stripped
        and re.fullmatch(r"[A-Z0-9 .,%/:-]+", stripped)
    ):
        return True

    words = re.findall(r"[A-Za-z]{2,}", stripped)

    if not words:
        return False

    quality_words = []

    for word in words:
        word_upper = word.upper()

        # Ignore tiny OCR fragments like "if", "iy", "v", etc.
        if len(word_upper) < 3:
            continue

        # Repeated letters are common in border/barcode OCR artifacts.
        if re.search(r"(.)\1{3,}", word_upper):
            continue

        # Long words with very few unique letters are usually OCR noise.
        if len(word_upper) >= 8:
            unique_ratio = len(set(word_upper)) / len(word_upper)

            if unique_ratio < 0.35:
                continue

        # Normal words usually contain at least one vowel.
        if re.search(r"[AEIOU]", word_upper):
            quality_words.append(word_upper)

    if len(quality_words) >= 2:
        return True

    if len(quality_words) == 1:
        # One strong word can be valid, especially short label lines like
        # IMPORTED, WHISKY, LIQUEUR, CHILLED, CANADA, etc.
        return len(quality_words[0]) >= 4

    return False


def is_likely_border_or_decoration_artifact(line: str) -> bool:
    """
    Detect OCR lines that are probably decorative borders, separators, barcodes,
    or image artifacts rather than real label text.

    This avoids using a label-specific word whitelist.
    """
    if not line:
        return True

    stripped = line.strip()

    if not stripped:
        return True

    # Preserve structured numeric fields before applying artifact filters.
    if has_useful_numeric_pattern(stripped):
        return False

    symbol_count = sum(
        1 for character in stripped
        if not character.isalnum() and not character.isspace()
    )

    symbol_ratio = symbol_count / max(len(stripped), 1)

    compact_letters = re.sub(r"[^A-Z]", "", stripped.upper())
    has_digit = any(character.isdigit() for character in stripped)

    # Very short letter fragments with symbols are usually OCR garbage.
    # This removes lines like: i \y
    if len(compact_letters) <= 2 and not has_digit:
        return True

    # Border/separator artifacts often have many non-alphanumeric symbols.
    # This removes lines like: if —T|/"'’v—wnnnnaanaaannwv—
    if len(stripped) >= 8 and symbol_ratio >= 0.18:
        return True

    # Long repeated-letter artifacts are common from borders/barcodes.
    if len(compact_letters) >= 8:
        repeated_noise = re.search(r"(.)\1{3,}", compact_letters)

        if repeated_noise:
            return True

        unique_ratio = len(set(compact_letters)) / len(compact_letters)

        if unique_ratio < 0.35:
            return True

    # If it has no useful numeric pattern and no natural word shape, it is
    # probably not useful label text.
    if not has_natural_word_shape(stripped):
        return True

    return False


def is_mostly_garbage_line(line: str) -> bool:
    """
    Filter obvious OCR artifacts while preserving useful label text.

    This uses structural signals rather than a hardcoded list of product,
    brand, country, or warning terms.
    """
    if not line:
        return True

    stripped = line.strip()

    if not stripped:
        return True

    if is_caption_line(stripped):
        return True

    if is_likely_border_or_decoration_artifact(stripped):
        return True

    compact_letters = re.sub(r"[^A-Z]", "", stripped.upper())
    has_digit = any(character.isdigit() for character in stripped)

    if len(compact_letters) <= 1 and not has_digit:
        return True

    alnum_count = sum(character.isalnum() for character in stripped)

    if alnum_count == 0:
        return True

    if len(stripped) > 8 and (alnum_count / len(stripped)) < 0.32:
        return True

    return False


def normalize_common_ocr_text(line: str) -> str:
    """
    Normalize common OCR formatting errors without inventing label text.
    """
    line = line.strip()
    line = line.strip('"`“”')
    line = re.sub(r"\s+", " ", line)

    line = line.replace("ALC/ VOL", "ALC/VOL")
    line = line.replace("ALC /VOL", "ALC/VOL")
    line = line.replace("ALC / VOL", "ALC/VOL")
    line = line.replace("ALC./VOL.", "ALC/VOL")
    line = line.replace("ALC./VOL", "ALC/VOL")
    line = line.replace("ALC/VOL.", "ALC/VOL")

    # Common OCR punctuation error inside the government warning phrase.
    # Example: "According to. the Surgeon General" -> "According to the Surgeon General"
    line = re.sub(
        r"\bAccording\s+to\.\s+the\b",
        "According to the",
        line,
        flags=re.IGNORECASE,
    )

    line = re.sub(
        r"\bAccording\s+to,\s+the\b",
        "According to the",
        line,
        flags=re.IGNORECASE,
    )

    # Remove obvious trailing border artifacts without removing useful text.
    line = re.sub(r"\s*\|+$", "", line).strip()
    line = re.sub(r"^[|\\/\-–—_]+\s*", "", line).strip()

    line = re.sub(
        r"\bFREDERICK,\s*MD\b",
        "FREDERICK, MD",
        line,
        flags=re.IGNORECASE,
    )

    # Preserve or restore the required warning heading colon.
    if re.fullmatch(r"GOVERNMENT\s+WARNING:?", line, flags=re.IGNORECASE):
        return "GOVERNMENT WARNING:"

    # Common warning-statement OCR cleanups.
    line = re.sub(
        r"^\(?[3I|l]\)\s+According\b",
        "(1) According",
        line,
        flags=re.IGNORECASE,
    )
    line = re.sub(
        r"\bbevorages\b",
        "beverages",
        line,
        flags=re.IGNORECASE,
    )
    line = re.sub(
        r"\bmachinery\.\s+and\b",
        "machinery, and",
        line,
        flags=re.IGNORECASE,
    )

    line = re.sub(r"\s+([,.;:])", r"\1", line)
    line = re.sub(r"[,.;]+$", "", line).strip()

    return line


def clean_ocr_output(text: str) -> str:
    """
    Clean OCR output while preserving useful line structure.
    """
    if not text:
        return ""

    cleaned_lines = []

    for line in text.splitlines():
        cleaned = normalize_common_ocr_text(line)

        if cleaned and not is_mostly_garbage_line(cleaned):
            cleaned_lines.append(cleaned)

    return "\n".join(cleaned_lines)


def line_key(line: str) -> str:
    """
    Normalize a line for deduplication.
    """
    return re.sub(r"[^A-Z0-9]+", "", line.upper())


def is_near_duplicate(new_line: str, existing_lines: list[str]) -> bool:
    """
    Avoid duplicate lines across OCR regions.
    """
    new_key = line_key(new_line)

    if not new_key:
        return True

    for existing_line in existing_lines:
        existing_key = line_key(existing_line)

        if new_key == existing_key:
            return True

        if len(new_key) >= 5 and new_key in existing_key:
            return True

    return False


def combine_region_outputs(region_results: list[tuple[str, str]]) -> str:
    """
    Combine cleaned OCR text from multiple visible regions while removing
    duplicates. Section headers make the OCR text easier for the reviewer to
    inspect and edit.
    """
    output_lines = []
    current_section_has_lines = False
    seen_section_titles = set()

    for title, raw_text in region_results:
        cleaned_text = clean_ocr_output(raw_text)

        if not cleaned_text:
            continue

        section_lines = []

        for line in cleaned_text.splitlines():
            if not is_near_duplicate(line, output_lines + section_lines):
                section_lines.append(line)

        if not section_lines:
            continue

        if title:
            if output_lines and current_section_has_lines:
                output_lines.append("")

            title_key = title.lower()

            if title_key not in seen_section_titles:
                output_lines.append(f"{title}:")
                seen_section_titles.add(title_key)

            current_section_has_lines = True

        output_lines.extend(section_lines)

    return "\n".join(output_lines).strip()


def normalize_ocr_numeric_token(token: str) -> str:
    """
    Normalize common OCR mistakes in numeric contexts only.

    Examples:
    - 4S -> 45
    - 9O -> 90
    - 7S0 -> 750
    """
    if not token:
        return ""

    normalized = str(token).upper()
    normalized = normalized.replace("O", "0")
    normalized = normalized.replace("I", "1")
    normalized = normalized.replace("L", "1")
    normalized = normalized.replace("|", "1")
    normalized = normalized.replace("S", "5")
    normalized = normalized.replace(",", ".")
    normalized = re.sub(r"[^0-9.]", "", normalized)

    return normalized


def parse_ocr_number(token: str) -> float | None:
    """
    Convert an OCR numeric token into a float after normalization.
    """
    normalized = normalize_ocr_numeric_token(token)

    if not normalized:
        return None

    try:
        return float(normalized)
    except ValueError:
        return None


def format_number(value: float) -> str:
    """
    Format a numeric value without unnecessary trailing decimals.
    """
    if float(value).is_integer():
        return str(int(value))

    return str(value)


def coerce_likely_common_ml_size(value: float) -> int | None:
    """
    Recover likely common bottle sizes from OCR-confused net contents.

    This does not change the visible OCR line. It only adds a recovered
    structured candidate for human review and downstream matching.

    Example:
    - OCR may read 750 ML as 730 ML on stylized labels.
    - 730 ML is not a common alcohol container size, but 750 ML is.
    """
    rounded_value = int(round(value))

    if rounded_value in COMMON_ML_SIZES:
        return rounded_value

    # Common OCR confusion for 750 ML on stylized labels.
    if 725 <= rounded_value <= 775:
        return 750

    # Common OCR confusion for 1750 ML.
    if 1725 <= rounded_value <= 1775:
        return 1750

    return None


def extract_field_candidate_records(text: str, source: str) -> list[FieldCandidate]:
    """
    Extract likely structured field candidates from OCR output:
    - Alcohol by volume
    - Proof
    - Net contents
    """
    if not text:
        return []

    text_upper = text.upper()
    candidates = []

    abv_patterns = [
        r"\b([0-9OILS|]{1,3}(?:[.,][0-9OILS|]{1,2})?)\s*%?\s*(?:ALC\.?\s*/?\s*VOL\.?|ABV)\b",
        r"\b([0-9OILS|]{1,3}(?:[.,][0-9OILS|]{1,2})?)\s*(?:%|PERCENT)\b",
    ]

    for pattern in abv_patterns:
        for match in re.findall(pattern, text_upper):
            value = parse_ocr_number(match)

            if value is not None and 0.5 <= value <= 95:
                candidates.append(
                    FieldCandidate(
                        field=FIELD_ABV,
                        display=f"{format_number(value)}% ALC/VOL",
                        value=value,
                        source=source,
                    )
                )

    proof_pattern = r"\b([0-9OILS|]{1,3}(?:[.,][0-9OILS|]{1,2})?)\s*PROOF\b"

    for match in re.findall(proof_pattern, text_upper):
        value = parse_ocr_number(match)

        if value is not None and 1 <= value <= 200:
            candidates.append(
                FieldCandidate(
                    field=FIELD_PROOF,
                    display=f"{format_number(value)} PROOF",
                    value=value,
                    source=source,
                )
            )

    net_content_pattern = (
        r"\b([0-9OILS|]{1,4}(?:[.,][0-9OILS|]{1,2})?)\s*(ML|M[L1I]|L)\b"
    )

    for number_match, unit_match in re.findall(net_content_pattern, text_upper):
        value = parse_ocr_number(number_match)

        if value is None:
            continue

        unit = "ML" if unit_match.startswith("M") else "L"

        if unit == "ML":
            recovered_ml_value = coerce_likely_common_ml_size(value)

            if recovered_ml_value is not None:
                candidates.append(
                    FieldCandidate(
                        field=FIELD_NET_CONTENTS,
                        display=f"{recovered_ml_value} ML",
                        value=float(recovered_ml_value),
                        source=source,
                    )
                )

        if unit == "L":
            rounded_value = round(value, 2)

            if rounded_value in COMMON_L_SIZES:
                candidates.append(
                    FieldCandidate(
                        field=FIELD_NET_CONTENTS,
                        display=f"{format_number(rounded_value)} L",
                        value=rounded_value,
                        source=source,
                    )
                )

    return deduplicate_candidates(candidates)


def deduplicate_candidates(candidates: list[FieldCandidate]) -> list[FieldCandidate]:
    """
    Deduplicate candidates while preserving order.
    """
    unique_candidates = []
    seen = set()

    for candidate in candidates:
        key = (candidate.field, candidate.display.lower())

        if key not in seen:
            seen.add(key)
            unique_candidates.append(candidate)

    return unique_candidates


def select_best_candidates(candidates: list[FieldCandidate]) -> list[FieldCandidate]:
    """
    Select one best candidate for each structured field to reduce noisy output.
    """
    if not candidates:
        return []

    selected = []

    for field_name in [FIELD_ABV, FIELD_PROOF, FIELD_NET_CONTENTS]:
        field_candidates = [
            candidate for candidate in candidates
            if candidate.field == field_name
        ]

        if not field_candidates:
            continue

        grouped = defaultdict(lambda: {"candidate": None, "score": 0})

        for candidate in field_candidates:
            key = (
                candidate.field,
                round(candidate.value, 2),
                candidate.display.lower(),
            )

            grouped[key]["candidate"] = candidate

            if candidate.source == "region":
                grouped[key]["score"] += 3
            elif candidate.source == "candidate":
                grouped[key]["score"] += 2
            elif candidate.source == "primary":
                grouped[key]["score"] += 2
            else:
                grouped[key]["score"] += 1

        ranked = sorted(
            grouped.values(),
            key=lambda item: item["score"],
            reverse=True,
        )

        best = ranked[0]["candidate"]

        if best:
            selected.append(best)

    return deduplicate_candidates(selected)


def candidate_presence_key(text: str) -> str:
    """
    Normalize text for checking whether a recovered candidate already appears.
    """
    if not text:
        return ""

    text = text.upper()
    text = text.replace("ALC./VOL.", "ALC/VOL")
    text = text.replace("ALC. / VOL.", "ALC/VOL")
    text = text.replace("ALC VOL", "ALC/VOL")
    text = text.replace("ALC/VOL.", "ALC/VOL")
    text = re.sub(r"[^A-Z0-9]", "", text)

    return text


def candidate_already_present(candidate: str, text: str) -> bool:
    """
    Return True if a structured candidate already appears in the OCR text.
    """
    candidate_key = candidate_presence_key(candidate)
    text_key = candidate_presence_key(text)

    return bool(candidate_key and candidate_key in text_key)


def visible_text_has_alcohol_content(visible_text: str) -> bool:
    """
    Return True if the visible OCR text already contains an alcohol-content
    value. This prevents candidate-only OCR from adding noisy alternatives like
    43% ALC/VOL when the visible OCR already has 45% ALC/VOL.
    """
    if not visible_text:
        return False

    text_upper = visible_text.upper()

    patterns = [
        r"\b[0-9OILS|]{1,3}(?:[.,][0-9OILS|]{1,2})?\s*%?\s*(?:ALC\.?\s*/?\s*VOL\.?|ABV)\b",
        r"\b[0-9OILS|]{1,3}(?:[.,][0-9OILS|]{1,2})?\s*(?:%|PERCENT)\b",
        r"\b[0-9OILS|]{1,3}(?:[.,][0-9OILS|]{1,2})?\s*PROOF\b",
    ]

    return any(re.search(pattern, text_upper) for pattern in patterns)


def build_recovered_candidate_block(
    visible_text: str,
    candidates: list[FieldCandidate],
) -> str:
    """
    Build a readable block of recovered structured field candidates.

    Rules:
    - Do not repeat candidates already present in visible OCR.
    - Do not add noisy ABV/proof candidates if visible OCR already contains
      alcohol content.
    - Do allow net-content recovery because OCR often confuses 750 ML as 730 ML.
    """
    candidate_lines = []
    seen = set()
    alcohol_already_visible = visible_text_has_alcohol_content(visible_text)

    for candidate in candidates:
        if candidate.field in {FIELD_ABV, FIELD_PROOF} and alcohol_already_visible:
            continue

        if candidate_already_present(candidate.display, visible_text):
            continue

        key = candidate.display.lower()

        if key not in seen:
            seen.add(key)
            candidate_lines.append(candidate.display)

    if not candidate_lines:
        return ""

    return "Recovered structured field candidates:\n" + "\n".join(candidate_lines)


def build_final_text(
    visible_text: str,
    candidates: list[FieldCandidate],
) -> str:
    """
    Combine readable OCR text with a short structured-candidate block.
    """
    visible_text = clean_ocr_output(visible_text)
    candidate_block = build_recovered_candidate_block(visible_text, candidates)

    if visible_text and candidate_block:
        return f"{visible_text}\n\n{candidate_block}"

    if candidate_block:
        return candidate_block

    return visible_text


def ocr_regions(regions: list[OcrRegion]) -> list[tuple[str, str]]:
    """
    Run OCR for all defined regions.
    """
    results = []

    for region in regions:
        results.append((region.title, run_region_ocr(region)))

    return results


def extract_side_by_side_label_sheet_text(original_image: Image.Image) -> str:
    """
    OCR strategy for front/back label sheets shown side by side.

    Visible regions are shown to the reviewer. Candidate-only regions are used
    only to recover structured fields and are not displayed directly.
    """
    visible_regions = get_side_by_side_regions(original_image)
    visible_region_results = ocr_regions(visible_regions)
    visible_text = combine_region_outputs(visible_region_results)

    candidate_regions = get_side_by_side_candidate_regions(original_image)
    candidate_region_results = ocr_regions(candidate_regions)

    visible_region_text = "\n".join(text for _, text in visible_region_results)
    candidate_region_text = "\n".join(text for _, text in candidate_region_results)

    candidates = select_best_candidates(
        extract_field_candidate_records(
            visible_region_text,
            source="region",
        )
        + extract_field_candidate_records(
            candidate_region_text,
            source="candidate",
        )
    )

    return build_final_text(visible_text, candidates)


def extract_general_label_text(original_image: Image.Image) -> str:
    """
    OCR strategy for ordinary single-label uploads.
    """
    visible_regions = get_general_regions(original_image)
    visible_region_results = ocr_regions(visible_regions)
    visible_text = combine_region_outputs(visible_region_results)

    candidate_regions = get_general_candidate_regions(original_image)
    candidate_region_results = ocr_regions(candidate_regions)

    visible_region_text = "\n".join(text for _, text in visible_region_results)
    candidate_region_text = "\n".join(text for _, text in candidate_region_results)

    candidates = select_best_candidates(
        extract_field_candidate_records(
            visible_region_text,
            source="primary",
        )
        + extract_field_candidate_records(
            candidate_region_text,
            source="candidate",
        )
    )

    return build_final_text(visible_text, candidates)


def extract_text_from_uploaded_image(uploaded_file) -> str:
    """
    Extract text from an uploaded image file.

    Design:
    - Use region OCR for wide side-by-side label sheets.
    - Use general OCR for ordinary single-label uploads.
    - Recover structured candidates such as ABV and net contents.
    - Keep output readable and editable for human review.
    """
    ready, message = configure_tesseract()

    if not ready:
        raise RuntimeError(message)

    uploaded_file.seek(0)
    original_image = Image.open(uploaded_file)
    original_image = prepare_base_image(original_image)

    if should_use_side_by_side_region_ocr(original_image):
        final_text = extract_side_by_side_label_sheet_text(original_image)
    else:
        final_text = extract_general_label_text(original_image)

    return final_text.strip()


def get_ocr_status() -> tuple[bool, str]:
    """
    Return OCR availability status for display in the app.
    """
    return configure_tesseract()