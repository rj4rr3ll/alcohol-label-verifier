"""
Utilities for importing expected application fields into the Streamlit UI.

The take-home prompt describes agents comparing application data to label
artwork. This module keeps that step deterministic and prototype-friendly by
supporting structured uploads instead of requiring a live COLAs Online
integration.

Supported inputs:
- CSV: first row is used for single-label review
- JSON: object or first object in a list
- TXT: simple key/value text such as "Brand Name: OLD TOM DISTILLERY"
- PDF: best-effort extraction from fillable PDF form fields and text

The official TTB paper COLA application is TTB F 5100.31. That form includes
Brand Name and other application metadata, but it does not expose every
prototype verification field as a dedicated paper-form field. When the uploaded
application does not contain class/type, alcohol content, or net contents, the
UI leaves those fields editable for the reviewer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
import json
import re
from typing import Any

import pandas as pd

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - handled at runtime for deployments
    PdfReader = None


SUPPORTED_APPLICATION_EXTENSIONS = ["csv", "json", "txt", "pdf"]


@dataclass
class ParsedApplication:
    """
    Normalized application fields used by the single-label review UI.
    """

    brand_name: str = ""
    class_type: str = ""
    alcohol_content: str = ""
    net_contents: str = ""
    warning_required: bool = True

    # Optional metadata extracted when present. These fields are not all used by
    # the current verification workflow, but they make the import transparent and
    # leave room for the next iteration.
    product_type: str = ""
    fanciful_name: str = ""
    name_address: str = ""
    country_of_origin: str = ""
    source_format: str = ""
    source_name: str = ""
    messages: list[str] = field(default_factory=list)

    def expected_field_dict(self) -> dict[str, Any]:
        """
        Return only fields currently used to pre-fill the verification UI.
        """
        return {
            "brand_name": self.brand_name,
            "class_type": self.class_type,
            "alcohol_content": self.alcohol_content,
            "net_contents": self.net_contents,
            "name_address": self.name_address,
            "country_of_origin": self.country_of_origin,
            "warning_required": self.warning_required,
        }

    def metadata_dict(self) -> dict[str, str]:
        """
        Return optional extracted metadata for display.
        """
        return {
            "Product Type": self.product_type,
            "Fanciful Name": self.fanciful_name,
            "Name / Address": self.name_address,
            "Country of Origin": self.country_of_origin,
        }


FIELD_ALIASES = {
    "brand_name": [
        "brand name",
        "brand",
        "item 6",
        "item 6 brand name",
        "6 brand name",
        "6. brand name",
    ],
    "class_type": [
        "class/type",
        "class type",
        "class and type",
        "class/type designation",
        "class designation",
        "type designation",
        "class",
        "type",
        "product designation",
    ],
    "alcohol_content": [
        "alcohol content",
        "alcohol by volume",
        "alc/vol",
        "alc./vol.",
        "abv",
        "proof",
        "percent alcohol",
    ],
    "net_contents": [
        "net contents",
        "net content",
        "bottle size",
        "container size",
        "volume",
        "contents",
    ],
    "warning_required": [
        "warning required",
        "government warning required",
        "health warning required",
        "government health warning required",
        "requires warning",
    ],
    "product_type": [
        "type of product",
        "product type",
        "item 5",
        "item 5 type of product",
        "5 type of product",
        "5. type of product",
    ],
    "fanciful_name": [
        "fanciful name",
        "item 7",
        "item 7 fanciful name",
        "7 fanciful name",
        "7. fanciful name",
    ],
    "name_address": [
        "name_address",
        "name address",
        "name and address",
        "name and address of applicant",
        "applicant name and address",
        "applicant address",
        "bottler address",
        "producer address",
        "importer address",
        "item 8",
        "item 8 name and address",
        "8 name and address",
        "8. name and address",
    ],
    "country_of_origin": [
        "country_of_origin",
        "country of origin",
        "origin country",
        "import country",
        "country",
    ],
}


BOOLEAN_TRUE_VALUES = {"true", "t", "yes", "y", "1", "required", "checked"}
BOOLEAN_FALSE_VALUES = {"false", "f", "no", "n", "0", "not required", "unchecked"}


def normalize_key(value: str) -> str:
    """
    Normalize field names for alias matching.
    """
    if value is None:
        return ""

    text = str(value).strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_value(value: Any) -> str:
    """
    Convert a cell/form value into clean display text.
    """
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    if isinstance(value, (list, tuple, set)):
        return ", ".join(normalize_value(item) for item in value if normalize_value(item))

    text = str(value).strip()

    # pypdf may expose checkbox/export values with leading slash names.
    if text.startswith("/"):
        text = text[1:]

    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_bool(value: Any, default: bool = True) -> bool:
    """
    Parse warning_required values from CSV/JSON/TXT/PDF inputs.
    """
    text = normalize_value(value).lower()

    if not text:
        return default

    if text in BOOLEAN_TRUE_VALUES:
        return True

    if text in BOOLEAN_FALSE_VALUES:
        return False

    return default


def alias_lookup(record: dict[str, Any], canonical_field: str) -> str:
    """
    Pull the first non-empty value matching a canonical field alias.
    """
    normalized_record = {
        normalize_key(key): value
        for key, value in record.items()
    }

    for alias in FIELD_ALIASES.get(canonical_field, []):
        normalized_alias = normalize_key(alias)
        if normalized_alias in normalized_record:
            value = normalize_value(normalized_record[normalized_alias])
            if value:
                return value

    # Secondary matching: useful for PDF field names such as
    # "form1[0].Page1[0].brandName[0]" or similar variants.
    alias_keys = [normalize_key(alias) for alias in FIELD_ALIASES.get(canonical_field, [])]
    alias_tokens = [set(alias.split()) for alias in alias_keys]

    for key, value in normalized_record.items():
        if not key:
            continue

        key_tokens = set(key.split())
        for token_set in alias_tokens:
            if token_set and token_set.issubset(key_tokens):
                cleaned_value = normalize_value(value)
                if cleaned_value:
                    return cleaned_value

    return ""


def build_parsed_application(
    record: dict[str, Any],
    source_format: str,
    source_name: str,
    messages: list[str] | None = None,
) -> ParsedApplication:
    """
    Convert an arbitrary field/value record into the app's normalized schema.
    """
    messages = messages or []

    parsed = ParsedApplication(
        brand_name=alias_lookup(record, "brand_name"),
        class_type=alias_lookup(record, "class_type"),
        alcohol_content=alias_lookup(record, "alcohol_content"),
        net_contents=alias_lookup(record, "net_contents"),
        warning_required=parse_bool(alias_lookup(record, "warning_required"), default=True),
        product_type=alias_lookup(record, "product_type"),
        fanciful_name=alias_lookup(record, "fanciful_name"),
        name_address=alias_lookup(record, "name_address"),
        country_of_origin=alias_lookup(record, "country_of_origin"),
        source_format=source_format,
        source_name=source_name,
        messages=messages,
    )

    populated = [
        label for label, value in {
            "Brand Name": parsed.brand_name,
            "Class/Type": parsed.class_type,
            "Alcohol Content": parsed.alcohol_content,
            "Net Contents": parsed.net_contents,
            "Product Type": parsed.product_type,
            "Fanciful Name": parsed.fanciful_name,
            "Name / Address": parsed.name_address,
            "Country of Origin": parsed.country_of_origin,
        }.items()
        if value
    ]

    if populated:
        parsed.messages.append("Imported fields: " + ", ".join(populated) + ".")
    else:
        parsed.messages.append(
            "No supported expected-field values were found. You can still enter the fields manually."
        )

    return parsed


def flatten_json(data: Any, prefix: str = "") -> dict[str, Any]:
    """
    Flatten nested JSON into a simple record for alias matching.
    """
    flattened: dict[str, Any] = {}

    if isinstance(data, list):
        if not data:
            return flattened
        return flatten_json(data[0], prefix=prefix)

    if not isinstance(data, dict):
        return flattened

    for key, value in data.items():
        full_key = f"{prefix} {key}".strip()

        if isinstance(value, dict):
            flattened.update(flatten_json(value, prefix=full_key))
        elif isinstance(value, list):
            if value and isinstance(value[0], dict):
                flattened.update(flatten_json(value[0], prefix=full_key))
            else:
                flattened[full_key] = value
        else:
            flattened[full_key] = value

    return flattened


def parse_csv_application(raw_bytes: bytes, source_name: str) -> ParsedApplication:
    """
    Parse the first row of a CSV upload as single-label application data.
    """
    df = pd.read_csv(BytesIO(raw_bytes))

    if df.empty:
        return ParsedApplication(
            source_format="CSV",
            source_name=source_name,
            messages=["The uploaded CSV did not contain any rows."],
        )

    record = df.iloc[0].to_dict()
    messages = []

    if len(df) > 1:
        messages.append(
            "The CSV contains multiple rows. Single-label review imported the first row only. "
            "Use Batch Applications for multi-row review."
        )

    return build_parsed_application(record, "CSV", source_name, messages)


def parse_json_application(raw_bytes: bytes, source_name: str) -> ParsedApplication:
    """
    Parse JSON upload as single-label application data.
    """
    text = raw_bytes.decode("utf-8-sig")
    data = json.loads(text)
    record = flatten_json(data)

    messages = []
    if isinstance(data, list) and len(data) > 1:
        messages.append(
            "The JSON contains multiple records. Single-label review imported the first record only."
        )

    return build_parsed_application(record, "JSON", source_name, messages)


def parse_key_value_text(text: str) -> dict[str, str]:
    """
    Parse simple key/value text. Supports lines such as:
    Brand Name: OLD TOM DISTILLERY
    Alcohol Content - 45% Alc./Vol.
    """
    record: dict[str, str] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = re.match(r"^(.{2,80}?)(?:\s*[:=]\s*|\s+-\s+)(.+)$", line)
        if not match:
            continue

        key = match.group(1).strip()
        value = match.group(2).strip()

        if key and value:
            record[key] = value

    return record


def parse_txt_application(raw_bytes: bytes, source_name: str) -> ParsedApplication:
    """
    Parse plain text application notes as key/value data.
    """
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    record = parse_key_value_text(text)
    return build_parsed_application(record, "TXT", source_name)


def clean_pdf_field_value(value: Any) -> str:
    """
    Convert PDF form-field values into readable text.
    """
    if isinstance(value, dict):
        for key in ("/V", "/DV", "V", "DV"):
            if key in value:
                return normalize_value(value[key])
        return ""

    return normalize_value(value)


def extract_pdf_form_record(raw_bytes: bytes) -> tuple[dict[str, str], str]:
    """
    Extract form fields and text from a PDF application.
    """
    if PdfReader is None:
        raise RuntimeError("PDF parsing requires the pypdf package.")

    reader = PdfReader(BytesIO(raw_bytes))
    record: dict[str, str] = {}

    fields = reader.get_fields() or {}
    for field_name, field_data in fields.items():
        value = clean_pdf_field_value(field_data.get("/V") if isinstance(field_data, dict) else field_data)
        if value:
            record[str(field_name)] = value

            # Include alternate/user-facing labels when available.
            if isinstance(field_data, dict):
                for label_key in ("/TU", "/TM"):
                    label = normalize_value(field_data.get(label_key))
                    if label:
                        record[label] = value

    extracted_pages = []
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        if page_text:
            extracted_pages.append(page_text)

    extracted_text = "\n".join(extracted_pages)

    # If the PDF text layer contains key/value notes, use them too. This helps
    # with exported application summaries and non-fillable PDFs.
    text_record = parse_key_value_text(extracted_text)
    for key, value in text_record.items():
        record.setdefault(key, value)

    return record, extracted_text


def parse_pdf_application(raw_bytes: bytes, source_name: str) -> ParsedApplication:
    """
    Best-effort parsing for PDF uploads, including official TTB F 5100.31.
    """
    record, extracted_text = extract_pdf_form_record(raw_bytes)

    messages = [
        "PDF import is best-effort. It works best with filled PDF form fields or exported application summaries."
    ]

    lower_text = extracted_text.lower()
    if "ttb f 5100.31" in lower_text or "label/bottle approval" in lower_text:
        messages.append(
            "Detected text consistent with TTB F 5100.31, Application for and Certification/Exemption of Label/Bottle Approval."
        )
        messages.append(
            "TTB F 5100.31 includes Brand Name and applicant/product metadata, but class/type, alcohol content, and net contents may not be available as dedicated paper-form fields."
        )

    if not record:
        messages.append(
            "No filled PDF form-field values were found. If this is a blank official form, enter expected fields manually or upload CSV/JSON/TXT data."
        )

    return build_parsed_application(record, "PDF", source_name, messages)


def get_file_extension(file_name: str) -> str:
    """
    Return the lowercase extension without a dot.
    """
    if not file_name or "." not in file_name:
        return ""
    return file_name.rsplit(".", 1)[-1].lower().strip()


def parse_application_file(uploaded_file) -> ParsedApplication:
    """
    Parse a Streamlit uploaded application file into normalized fields.
    """
    source_name = getattr(uploaded_file, "name", "uploaded_application")
    extension = get_file_extension(source_name)

    if hasattr(uploaded_file, "getvalue"):
        raw_bytes = uploaded_file.getvalue()
    else:
        raw_bytes = uploaded_file.read()

    if extension == "csv":
        return parse_csv_application(raw_bytes, source_name)

    if extension == "json":
        return parse_json_application(raw_bytes, source_name)

    if extension == "txt":
        return parse_txt_application(raw_bytes, source_name)

    if extension == "pdf":
        return parse_pdf_application(raw_bytes, source_name)

    return ParsedApplication(
        source_format=extension.upper() if extension else "UNKNOWN",
        source_name=source_name,
        messages=[
            "Unsupported application upload type. Supported formats are CSV, JSON, TXT, and PDF."
        ],
    )