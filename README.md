# AI-Powered Alcohol Label Verification App

## Overview

This is a standalone proof-of-concept application for verifying alcohol beverage label artwork against expected application fields.

The prototype is designed around a compliance review workflow where reviewers compare label text against application data. It supports both single-label review and small batch review.

This application does not integrate with COLA or any Treasury production system. It is intended as a working prototype to demonstrate approach, usability, verification logic, OCR tradeoffs, and human-in-the-loop review.

## Live Demo

Deployment URL: https://alcohol-label-verifier-vrrps9ziiy96hyapfkk7vd.streamlit.app/

## Features

* Upload alcohol label artwork.
* Run OCR on uploaded label images.
* Review and edit extracted text before verification.
* Compare label text against expected application fields.
* Validate government health warning text and heading capitalization.
* Flag results as pass, manual review, or fail.
* Display detailed verification results and attention items.
* Download single-label verification results as CSV.
* Process small batches using a CSV plus matching image files.
* Download batch verification results as CSV.

## TTB Labeling Coverage and Core Checks

This prototype focuses on high-volume text-matching checks that are well suited for an AI-assisted alcohol label review workflow. It is not intended to implement the full set of TTB beverage-specific labeling rules or make final regulatory determinations.

TTB distilled spirits labeling guidance identifies several mandatory label information categories, including brand name, class/type designation, alcohol content, health warning statement, name and address, net contents, and country of origin for imports. Some requirements are conditional, such as age statements, color ingredient disclosures, and commodity statements.

This prototype currently verifies:

* Brand name
* Class/type designation
* Alcohol content and proof equivalency
* Net contents
* Government health warning text and heading capitalization

This prototype does not currently verify:

* Same-field-of-vision placement for brand name, class/type designation, and alcohol content
* Font size, bold formatting, continuous paragraph layout, contrast, or exact label placement
* Name and address
* Country of origin for imports
* Age statements
* Color ingredient disclosures
* Commodity statements
* Full beverage-type-specific TTB rule coverage

These limitations are documented intentionally. The app is designed to assist human review by identifying likely mismatches and cases requiring manual review.

## Technical Approach

The application uses:

* Streamlit for the web interface
* Tesseract OCR through pytesseract for text extraction
* Pillow for image preprocessing and region-based OCR cropping
* rapidfuzz for tolerant text matching
* pandas for CSV and batch processing
* Python unit tests for core verification logic

The verification logic uses a combination of OCR, deterministic rules, regular expressions, fuzzy matching, and structured field candidate recovery.

The app is intentionally designed to flag uncertain cases for human review rather than make final regulatory determinations.

## OCR Approach

The OCR workflow uses Tesseract and image preprocessing to extract label text. For side-by-side label images, the app uses region-based OCR so front-label and back-label text are processed separately. This reduces OCR errors caused by reading across two labels at once.

The app also uses structured field candidate recovery for high-value fields such as alcohol content and net contents. For example, if OCR misreads a common container size, the app may add a recovered candidate while still keeping the original OCR text visible for reviewer validation.

OCR output is editable before verification. This is intentional because image quality, stylized typography, curved text, low contrast, glare, or small text can affect OCR accuracy.

## How to Run Locally

Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run the app:

```powershell
streamlit run app.py
```

## OCR Setup

This prototype uses Tesseract OCR.

On Windows, install Tesseract OCR and confirm the executable exists at:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

The app checks common Tesseract installation paths and also supports Tesseract if it is available on PATH.

For Streamlit deployment, the repository includes a `packages.txt` file with:

```text
tesseract-ocr
```

## Single-Label Review Workflow

1. Upload a label image.
2. Run OCR on the uploaded label or paste label text manually.
3. Review and edit the extracted label text if needed.
4. Enter the expected application fields.
5. Click Verify Label.
6. Review the overall result, detailed checks, and any items requiring attention.
7. Download the results CSV if needed.

## Batch Review Workflow

Batch review uses one CSV file and one or more matching label images.

The CSV must include a `file_name` column. Each `file_name` value must match one uploaded image filename.

Required CSV columns:

```text
file_name
brand_name
class_type
alcohol_content
net_contents
warning_required
```

Example batch CSV format:

```csv
file_name,brand_name,class_type,alcohol_content,net_contents,warning_required
abc_rye_whisky_label.jpg,ABC DISTILLERY,STRAIGHT RYE WHISKY,45% ALC/VOL,750 ML,true
12345_rum_liqueur_label.jpg,12345 IMPORTS,RUM,18% ALC/VOL,200 ML,true
```

A sample CSV is included at:

```text
sample_data/sample_application.csv
```

Sample label images are included at:

```text
sample_data/labels/abc_rye_whisky_label.jpg
sample_data/labels/12345_rum_liqueur_label.jpg
```

## Result Categories

The app uses three result categories.

### PASS

The expected value appears to match the detected label text.

### MANUAL REVIEW RECOMMENDED

The app found a similar or partial match, or OCR output appears incomplete or uncertain. Human judgment is recommended.

### FAIL

The expected value was not found, did not match, or a required label element was missing or incorrectly formatted.

## Government Warning Validation

The prototype checks whether the government health warning is present and whether the heading appears as:

```text
GOVERNMENT WARNING:
```

The prototype also checks for required warning phrases.

The app flags incorrect capitalization, such as:

```text
Government Warning:
```

as a failure because the warning heading must appear in all caps.

The prototype checks warning text and capitalization only. It does not verify bold formatting, font size, contrast, continuous paragraph layout, or physical label placement.

## Security and Privacy Notes

* This is a standalone prototype and does not integrate with COLA.
* Uploaded files are processed during the active session and are not intentionally persisted by the application.
* The prototype does not require API keys, external AI services, or persistent document storage.
* No secrets or credentials should be committed to the repository.
* Human compliance review remains required.

## Assumptions

* The prototype focuses on common label verification checks rather than the full universe of alcohol labeling rules.
* The expected application fields are provided manually or through a batch CSV.
* The image filename in batch mode matches the `file_name` value in the CSV.
* OCR output can be reviewed and corrected by the user before final verification.
* Batch mode is intended for proof-of-concept testing rather than high-volume production processing.
* Manual review is appropriate when OCR output is incomplete, uncertain, or partially inconsistent with expected application data.

## Known Limitations

* OCR accuracy depends on image quality.
* Small, curved, angled, low-contrast, stylized, or blurry text may be misread.
* OCR may require human correction before verification.
* The app does not verify font size, bold formatting, continuous paragraph layout, contrast, or exact label placement.
* The app does not implement the full set of beverage-specific TTB labeling rules.
* The app does not make final regulatory determinations.
* Batch mode is intended for small proof-of-concept batches.
* Production deployment would require stronger access controls, audit logging, monitoring, queueing, retention controls, and compliance review.

## Future Improvements

Potential future improvements include:

* Add PDF support.
* Add OCR confidence scoring.
* Add visual detection for warning placement and formatting.
* Add beverage-type-specific rule sets for beer, wine, and distilled spirits.
* Add asynchronous processing for large batches.
* Add queueing and progress monitoring for high-volume submissions.
* Add role-based access control.
* Add audit logging.
* Add integration pathways for future COLA modernization efforts.

## Project Structure

```text
alcohol-label-verifier/
├── app.py
├── requirements.txt
├── packages.txt
├── README.md
├── sample_data/
│   ├── sample_application.csv
│   └── labels/
│       ├── abc_rye_whisky_label.jpg
│       └── 12345_rum_liqueur_label.jpg
├── src/
│   ├── __init__.py
│   ├── batch.py
│   ├── matching.py
│   ├── ocr.py
│   └── warning_check.py
└── tests/
    └── test_matching.py
```

## Testing

Run the included unit tests with:

```powershell
python -m unittest discover -s tests
```

The tests cover:

* Text normalization
* Brand matching
* Alcohol content matching
* Alcohol proof equivalency
* OCR-confused alcohol content values
* Net contents matching
* Government warning validation

## References

* TTB Distilled Spirits Labeling guidance: https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/labeling
* TTB Distilled Spirits Mandatory Label Information guidance: https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/ds-labeling-home/ds-brand-label
* TTB Distilled Spirits Health Warning Statement guidance: https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/ds-labeling-home/ds-health-warning

## Prototype Disclaimer

This prototype assists label review by identifying potential mismatches between application data and label artwork. It is not a substitute for human compliance review and does not make final regulatory determinations.

