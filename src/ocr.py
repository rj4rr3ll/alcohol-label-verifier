import os
import shutil

from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import pytesseract


COMMON_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


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
        "Tesseract OCR engine was not found. Install Tesseract or use manual text entry."
    )


def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Basic image cleanup before OCR:
    - Fix image orientation
    - Convert to grayscale
    - Increase contrast
    - Sharpen
    - Upscale small images
    """
    image = ImageOps.exif_transpose(image)

    if image.mode != "RGB":
        image = image.convert("RGB")

    width, height = image.size

    if width < 1400:
        scale = 1400 / width
        new_size = (int(width * scale), int(height * scale))
        image = image.resize(new_size)

    image = ImageOps.grayscale(image)
    image = ImageOps.autocontrast(image)
    image = ImageEnhance.Contrast(image).enhance(1.8)
    image = image.filter(ImageFilter.SHARPEN)

    return image


def extract_text_from_uploaded_image(uploaded_file) -> str:
    """
    Extract text from an uploaded image file using Tesseract OCR.
    """
    ready, message = configure_tesseract()

    if not ready:
        raise RuntimeError(message)

    uploaded_file.seek(0)
    image = Image.open(uploaded_file)

    processed_image = preprocess_image(image)

    text = pytesseract.image_to_string(processed_image)

    return text.strip()


def get_ocr_status() -> tuple[bool, str]:
    """
    Return OCR availability status for display in the app.
    """
    return configure_tesseract()