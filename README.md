# AI-Powered Alcohol Label Verification App

## Overview

This is a standalone proof-of-concept application for verifying alcohol beverage label artwork against expected application fields.

The prototype is designed around a compliance review workflow where agents compare label text against application data. It supports both single-label review and small batch review.

This application does not integrate with COLA or any Treasury production system. It is intended as a working prototype to demonstrate approach, usability, verification logic, and tradeoffs.

## Live Demo

Deployment URL: https://alcohol-label-verifier-vrrps9ziiy96hyapfkk7vd.streamlit.app/

## Features

* Upload alcohol label artwork.
* Run OCR on uploaded label images.
* Review and edit extracted text before verification.
* Compare label text against expected application fields.
* Validate government health warning text and capitalization.
* Flag results as pass, manual review, or fail.
* Download single-label verification results as CSV.
* Process small batches using a CSV plus matching image files.
* Download batch verification results as CSV.

## Core Checks

The prototype checks the following label elements:

* Brand name
* Class/type designation
* Alcohol content
* Net contents
* Government health warning statement

## Technical Approach

The application uses:

* Streamlit for the web interface
* Tesseract OCR through pytesseract for text extraction
* Pillow for basic image preprocessing
* rapidfuzz for tolerant text matching
* pandas for CSV and batch processing

The verification logic uses a combination of OCR, deterministic rules, regular expressions, and fuzzy matching.

The app is intentionally designed to flag uncertain cases for human review rather than make final regulatory determinations.

## How to Run Locally

Create and activate a virtual environment:

```
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install dependencies:

```
pip install -r requirements.txt
```

Run the app:

```
streamlit run app.py
```

## OCR Setup

This prototype uses Tesseract OCR.

On Windows, install Tesseract OCR and confirm the executable exists at:

```
C:\Program Files\Tesseract-OCR\tesseract.exe
```

The app checks common Tesseract installation paths and also supports Tesseract if it is available on PATH.

For Streamlit deployment, the repository includes a packages.txt file with:

```
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

The CSV must include a file_name column. Each file_name value must match one uploaded image filename.

Example batch CSV format:

```
file_name,brand_name,class_type,alcohol_content,net_contents,warning_required
old_tom_test_label.png,OLD TOM DISTILLERY,Kentucky Straight Bourbon Whiskey,45% Alc./Vol. (90 Proof),750 mL,true
```

A sample CSV is included at:

```
sample_data/sample_application.csv
```

A sample label image is included at:

```
sample_data/labels/old_tom_test_label.png
```

## Result Categories

The app uses three result categories:

### PASS

The expected value appears to match the detected label text.

### MANUAL REVIEW RECOMMENDED

The app found a similar or partial match, but the result requires human judgment.

### FAIL

The expected value was not found, did not match, or a required label element was missing or incorrectly formatted.

## Government Warning Validation

The prototype checks whether the government health warning is present and whether the heading appears as:

```
GOVERNMENT WARNING:
```

The prototype also checks for required warning phrases.

The app flags incorrect capitalization, such as:

```
Government Warning:
```

as a failure because the warning heading must appear in all caps.

## Security and Privacy Notes

* This is a standalone prototype and does not integrate with COLA.
* Uploaded files are processed during the active session and are not intentionally persisted by the application.
* The prototype does not require API keys, external AI services, or persistent document storage.
* No secrets or credentials should be committed to the repository.
* Human compliance review remains required.

## Assumptions

* The prototype focuses on common label verification checks rather than the full universe of alcohol labeling rules.
* The expected application fields are provided manually or through a batch CSV.
* The image file name in batch mode matches the file_name value in the CSV.
* OCR output can be reviewed and corrected by the user before final verification.
* Batch mode is intended for proof-of-concept testing rather than high-volume production processing.

## Known Limitations

* OCR accuracy depends on image quality.
* Small, curved, angled, low-contrast, or blurry text may be misread.
* The app does not verify font size, bold formatting, or exact label placement.
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

```
alcohol-label-verifier/
├── app.py
├── requirements.txt
├── packages.txt
├── README.md
├── sample_data/
│   ├── sample_application.csv
│   └── labels/
│       └── old_tom_test_label.png
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

```
python -m unittest discover -s tests
```

The tests cover:

* Text normalization
* Brand matching
* Alcohol content matching
* Net contents matching
* Government warning validation

## Prototype Disclaimer

This prototype assists label review by identifying potential mismatches between application data and label artwork. It is not a substitute for human compliance review and does not make final regulatory determinations.
