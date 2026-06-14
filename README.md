# AI-Powered Alcohol Label Verification App

## Overview

This is a standalone proof-of-concept application for verifying alcohol beverage label artwork against expected application fields.

The prototype is designed around a compliance review workflow where reviewers compare label text against application data. It supports single-label review, structured application upload, OCR-assisted text extraction, manual correction, small batch review, and batch table generation from raw application files.

This application does not integrate with COLAs Online or any Treasury production system. It is intended as a working prototype to demonstrate approach, usability, verification logic, OCR tradeoffs, batch review support, and human-in-the-loop review.

## Live Demo

Deployment URL:

```text
https://alcohol-label-verifier-vrrps9ziiy96hyapfkk7vd.streamlit.app/
```

## Demo Script

A reviewer can test the app with this workflow:

1. Open the deployed Streamlit app.
2. Go to **Single Label Review**.
3. Upload a label image.
4. Click **Extract Label Text**.
5. Review or edit the detected label text.
6. Upload a structured application file or manually enter expected fields.
7. Click **Populate Expected Fields** if using an application upload.
8. Click **Verify Label**.
9. Review the overall result, attention items, and detailed results table.
10. Download the CSV result if needed.

For batch testing with a ready-made CSV:

1. Go to **Batch Review**.
2. Select **Upload Batch CSV**.
3. Upload a CSV with expected application fields.
4. Upload matching label images.
5. Confirm each CSV `file_name` value matches an uploaded image filename.
6. Click **Process Batch**.
7. Review the batch summary, per-label results, processing time, and downloadable CSV.

For batch testing with raw application files:

1. Go to **Batch Review**.
2. Select **Generate from Application Files**.
3. Upload one or more application files.
4. Upload matching label images.
5. Click **Generate Batch Table**.
6. Review and edit the generated batch table.
7. Confirm each generated `file_name` value matches an uploaded image filename.
8. Download the generated batch CSV if needed.
9. Click **Process Batch**.
10. Review the batch summary, per-label results, processing time, and downloadable CSV.

## Features

* Upload alcohol label artwork.
* Run OCR on uploaded label images.
* Review and edit extracted text before verification.
* Upload structured application data to auto-fill expected fields.
* Supports CSV, JSON, TXT, and best-effort PDF application uploads.
* Compare label text against expected application fields.
* Validate government health warning text and heading capitalization.
* Flag results as pass, manual review, or fail.
* Display detailed verification results and attention items.
* Download single-label verification results as CSV.
* Process small batches using a CSV plus matching image files.
* Generate an editable batch table from multiple raw application files.
* Download generated batch tables as reusable CSV files.
* Validate batch CSV structure before processing.
* Handle blank CSV cells safely without displaying `nan` values.
* Display OCR processing time for single-label and batch workflows.
* Download batch verification results as CSV.
* Uses a dark Streamlit theme for a cleaner reviewer-facing interface.

## Official Application Reference

The official paper COLA application is **TTB F 5100.31, Application for and Certification/Exemption of Label/Bottle Approval**.

Official form:

```text
https://www.ttb.gov/system/files/images/pdfs/forms/f510031.pdf
```

TTB COLA information page:

```text
https://www.ttb.gov/alfd/certificate-of-label-aproval-cola
```

For this prototype, official PDF import is best-effort. A blank or scanned PDF form may not contain filled form-field data that can be reliably extracted. Structured CSV, JSON, or TXT application data is the most reliable prototype path for auto-filling expected fields.

## Application Upload / Auto-Fill

Single-label review supports an optional application upload step. The upload can populate expected review fields before verification.

Supported single-label application formats:

* CSV
* JSON
* TXT
* PDF, best-effort

Recommended CSV format:

```csv
brand_name,class_type,alcohol_content,net_contents,name_address,country_of_origin,warning_required
OLD TOM DISTILLERY,Kentucky Straight Bourbon Whiskey,45% Alc./Vol. (90 Proof),750 mL,OLD TOM DISTILLERY - LOUISVILLE KY,United States,true
```

Recommended JSON format:

```json
{
  "brand_name": "OLD TOM DISTILLERY",
  "class_type": "Kentucky Straight Bourbon Whiskey",
  "alcohol_content": "45% Alc./Vol. (90 Proof)",
  "net_contents": "750 mL",
  "name_address": "OLD TOM DISTILLERY - LOUISVILLE KY",
  "country_of_origin": "United States",
  "warning_required": true
}
```

Recommended TXT format:

```text
Brand Name: OLD TOM DISTILLERY
Class/Type: Kentucky Straight Bourbon Whiskey
Alcohol Content: 45% Alc./Vol. (90 Proof)
Net Contents: 750 mL
Name and Address: OLD TOM DISTILLERY - LOUISVILLE KY
Country of Origin: United States
Government Warning Required: yes
```

The imported fields remain editable. This is intentional: reviewers should be able to correct application import errors before running verification.

## Batch Review Options

The Batch Review workflow supports two ways to provide expected application data.

### Option A: Upload Batch CSV

Reviewers can upload a structured CSV containing expected application fields and matching label image filenames.

Required CSV columns:

```text
file_name
brand_name
class_type
alcohol_content
net_contents
```

Optional CSV columns:

```text
name_address
country_of_origin
warning_required
```

Each `file_name` value must match one uploaded label image filename.

### Option B: Generate from Application Files

Reviewers can upload multiple raw application files and the app will generate an editable batch table.

Supported application file formats:

```text
CSV
JSON
TXT
PDF, best-effort
```

Each uploaded application file becomes one generated batch row. The app attempts to match each application to an uploaded label image by filename. Reviewers can edit the generated table before processing and can download the generated table as a reusable batch CSV.

This reduces the need for reviewers to manually build a batch CSV before running label verification.

## TTB Labeling Coverage and Core Checks

This prototype focuses on high-volume text-matching checks that are well suited for an AI-assisted alcohol label review workflow. It is not intended to implement the full set of TTB beverage-specific labeling rules or make final regulatory determinations.

TTB labeling requirements vary by beverage type. Common label elements include brand name, class/type designation, alcohol content, net contents, name and address, country of origin for imports, and the government health warning statement.

This prototype currently verifies:

* Brand name
* Class/type designation
* Alcohol content and proof equivalency
* Net contents
* Government health warning text and heading capitalization
* Optional name/address text when provided
* Optional country-of-origin text when provided

This prototype does not currently verify:

* Same-field-of-vision placement for brand name, class/type designation, and alcohol content
* Font size, bold formatting, continuous paragraph layout, contrast, or exact label placement
* Full name/address legal sufficiency by business role
* Whether country of origin is legally required for a specific product
* Age statements
* Color ingredient disclosures
* Commodity statements
* Full beverage-type-specific TTB rule coverage

These limitations are documented intentionally. The app is designed to assist human review by identifying likely mismatches and cases requiring manual review.

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

as a failure because the warning heading must appear in capital letters. The prototype checks warning text and capitalization only. It does not verify bold formatting, font size, contrast, continuous paragraph layout, or physical label placement.

Official TTB health warning reference:

```text
https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/ds-labeling-home/ds-health-warning
```

## Technical Approach

The application uses:

* Streamlit for the web interface
* Tesseract OCR through pytesseract for text extraction
* Pillow for image preprocessing and region-based OCR cropping
* rapidfuzz for conservative fuzzy matching
* pandas for CSV and batch processing
* pypdf for best-effort PDF application parsing
* Python unit tests for parsing, batch handling, and verification logic

The verification logic uses a combination of OCR, deterministic rules, regular expressions, fuzzy matching, structured field candidate recovery, and human-editable review text.

The app is intentionally designed to flag uncertain cases for human review rather than make final regulatory determinations.

## Matching Approach

The app uses conservative matching behavior:

* Case and punctuation differences are tolerated.
* Clear normalized matches pass.
* Close fuzzy matches may pass or trigger manual review.
* Partial/subset matches are restricted so values like `WHISKY` do not automatically pass for `Straight Rye Whisky`.
* Missing expected values trigger review for required core fields.
* Optional fields are checked only when provided.

This design reflects the stakeholder concern that label review includes nuance. For example, `STONE'S THROW` and `Stone's Throw` should be treated as the same brand, but missing regulatory modifiers should not automatically pass.

## OCR Approach

The OCR workflow uses Tesseract and image preprocessing to extract label text. For side-by-side label images, the app uses region-based OCR so front-label and back-label text are processed separately. This reduces OCR errors caused by reading across two labels at once.

The app also uses structured field candidate recovery for high-value fields such as alcohol content and net contents. For example, if OCR misreads a common container size, the app may add a recovered candidate while still keeping the original OCR text visible for reviewer validation.

OCR output is editable before verification. This is intentional because image quality, stylized typography, curved text, low contrast, glare, or small text can affect OCR accuracy.

## Performance Notes

Stakeholder feedback indicated that an earlier vendor pilot was too slow for practical use. This prototype displays OCR processing time in both single-label and batch workflows.

The UI flags whether OCR timing is within a 5-second target for interactive review. Local performance depends on image size, image quality, Tesseract availability, and deployment resources.

Production deployment would require benchmarking, worker scaling, queueing, monitoring, and reliability controls for large import batches.

## Sample Data

The repository includes sample data for local testing and demo workflows.

Recommended folder structure:

```text
sample_data/
  README_sample_data.md
  sample_application.csv
  applications/
  labels/
```

The `sample_application.csv` file can be used with **Batch Review > Upload Batch CSV**.

The files in `sample_data/applications/` can be used with **Single Label Review** or **Batch Review > Generate from Application Files**.

The files in `sample_data/labels/` can be uploaded as matching label images.

Example batch CSV format:

```csv
file_name,brand_name,class_type,alcohol_content,net_contents,name_address,country_of_origin,warning_required
abc_rye_whisky_label.jpg,ABC DISTILLERY,STRAIGHT RYE WHISKY,45% ALC/VOL,750 ML,"ABC DISTILLERY FREDERICK, MD",,true
12345_rum_liqueur_label.jpg,12345 IMPORTS,RUM WITH COCONUT LIQUEUR,18% ALC/VOL,200 ML,"IMPORTED BY 12345 IMPORTS MIAMI, FL",Canada,true
```

The included sample application PDFs are prototype test packets for demonstrating the app workflow. They are not actual approved COLAs and are not intended for submission.

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

## Running Tests

Run all tests from the project root:

```powershell
python -m unittest discover -s tests -p "test*.py" -v
```

The test suite covers:

* Text normalization
* Conservative fuzzy matching
* Alcohol content and proof equivalency
* Net contents matching
* Government warning text checks
* Optional name/address and country-of-origin checks
* Batch CSV validation
* Blank-cell handling
* Application upload parsing for CSV, JSON, TXT, and PDF where supported by the local environment
* Batch table generation from application files

## Single-Label Review Workflow

1. Upload a label image.
2. Run OCR on the uploaded label or paste label text manually.
3. Review and edit the extracted label text if needed.
4. Upload application data or enter expected fields manually.
5. Click **Populate Expected Fields** if using an application upload.
6. Click **Verify Label**.
7. Review the overall result, detailed checks, and any items requiring attention.
8. Download the results CSV if needed.

## Batch Review Workflow

Batch review supports two workflows.

### Workflow A: Upload Batch CSV

1. Select **Upload Batch CSV**.
2. Upload a structured batch CSV.
3. Upload one or more matching label images.
4. Confirm each CSV `file_name` value matches an uploaded image filename.
5. Click **Process Batch**.
6. Review the batch summary and per-label results.
7. Download the batch results CSV if needed.

Required CSV columns:

```text
file_name
brand_name
class_type
alcohol_content
net_contents
```

Optional CSV columns:

```text
name_address
country_of_origin
warning_required
```

Example batch CSV format:

```csv
file_name,brand_name,class_type,alcohol_content,net_contents,name_address,country_of_origin,warning_required
abc_rye_whisky_label.jpg,ABC DISTILLERY,STRAIGHT RYE WHISKY,45% ALC/VOL,750 ML,"ABC DISTILLERY FREDERICK, MD",,true
12345_rum_liqueur_label.jpg,12345 IMPORTS,RUM WITH COCONUT LIQUEUR,18% ALC/VOL,200 ML,"IMPORTED BY 12345 IMPORTS MIAMI, FL",Canada,true
```

Batch mode validates required columns before processing. It also warns about larger prototype batches and duplicate image filenames.

### Workflow B: Generate from Application Files

1. Select **Generate from Application Files**.
2. Upload one or more application files.
3. Upload one or more matching label images.
4. Click **Generate Batch Table**.
5. Review and edit the generated table.
6. Confirm each `file_name` value matches an uploaded label image filename.
7. Download the generated batch CSV if needed.
8. Click **Process Batch**.
9. Review the batch summary and per-label results.
10. Download the batch results CSV if needed.

This workflow is useful when reviewers have raw application files but do not already have a structured batch CSV.

## Result Categories

The app uses three result categories.

### PASS

The expected value appears to match the detected label text.

### MANUAL REVIEW RECOMMENDED

The app found a similar or partial match, OCR output appears incomplete or uncertain, or a required expected field was not provided. Human judgment is recommended.

### FAIL

The expected value was not found, did not match, or a required label element was missing or incorrectly formatted.

## Security and Privacy Notes

* This is a standalone prototype and does not integrate with COLAs Online.
* Uploaded files are processed during the active session and are not intentionally persisted by the application.
* The prototype does not require API keys, external AI services, or persistent document storage.
* No secrets or credentials should be committed to the repository.
* Human compliance review remains required.

## Assumptions

* The prototype focuses on common label verification checks rather than the full universe of alcohol labeling rules.
* The expected application fields may be provided manually, through a structured upload, through a batch CSV, or by generating a batch table from application files.
* The official paper COLA form may not contain all prototype verification fields in extractable form.
* In batch mode, each label image filename should match the `file_name` value in the CSV or generated batch table.
* Application-to-label filename matching is best-effort when generating a batch table from raw application files.
* OCR output can be reviewed and corrected by the user before final verification.
* Batch mode is intended for proof-of-concept testing rather than high-volume production processing.
* Manual review is appropriate when OCR output is incomplete, uncertain, or partially inconsistent with expected application data.

## Known Limitations

* OCR accuracy depends on image quality.
* Small, curved, angled, low-contrast, stylized, or blurry text may be misread.
* OCR may require human correction before verification.
* PDF application upload is best-effort and works best with filled PDF form fields or exported application summaries.
* Scanned PDFs may not contain extractable text unless OCR is added in a future version.
* Filename matching between application files and label images is best-effort and may require reviewer correction.
* The app does not verify font size, bold formatting, continuous paragraph layout, contrast, or exact label placement.
* The app does not implement the full set of beverage-specific TTB labeling rules.
* The app does not make final regulatory determinations.
* Batch mode is intended for small proof-of-concept batches.
* Production deployment would require stronger access controls, audit logging, monitoring, queueing, retention controls, and compliance review.

## Future Improvements

Potential future improvements include:

* Add stronger PDF application extraction for exported COLAs Online records.
* Add OCR support for scanned application PDFs.
* Add OCR confidence scoring.
* Add visual detection for warning placement and formatting.
* Add stronger application-to-label matching controls for batch workflows.
* Add beverage-type-specific rule sets for beer, wine, and distilled spirits.
* Add asynchronous processing for large batches.
* Add queueing and progress monitoring for high-volume submissions.
* Add role-based access control.
* Add audit logging.
* Add secure document-retention controls.
* Add integration hooks for future COLAs Online modernization or procurement evaluation.


