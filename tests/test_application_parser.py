import unittest
from io import BytesIO

from src.application_parser import parse_application_file


class UploadedFileStub(BytesIO):
    def __init__(self, name: str, data: bytes):
        super().__init__(data)
        self.name = name

    def getvalue(self):
        return super().getvalue()


class TestApplicationParser(unittest.TestCase):

    def test_csv_first_row_imports_expected_fields(self):
        uploaded = UploadedFileStub(
            "application.csv",
            (
                "brand_name,class_type,alcohol_content,net_contents,name_address,country_of_origin,warning_required\n"
                "OLD TOM DISTILLERY,Kentucky Straight Bourbon Whiskey,45% Alc./Vol. (90 Proof),750 mL,OLD TOM DISTILLERY - LOUISVILLE KY,United States,true\n"
            ).encode("utf-8"),
        )

        parsed = parse_application_file(uploaded)

        self.assertEqual(parsed.brand_name, "OLD TOM DISTILLERY")
        self.assertEqual(parsed.class_type, "Kentucky Straight Bourbon Whiskey")
        self.assertEqual(parsed.alcohol_content, "45% Alc./Vol. (90 Proof)")
        self.assertEqual(parsed.net_contents, "750 mL")
        self.assertEqual(parsed.name_address, "OLD TOM DISTILLERY - LOUISVILLE KY")
        self.assertEqual(parsed.country_of_origin, "United States")
        self.assertTrue(parsed.warning_required)

    def test_txt_key_value_imports_expected_fields(self):
        uploaded = UploadedFileStub(
            "application.txt",
            (
                "Brand Name: OLD TOM DISTILLERY\n"
                "Class/Type: Kentucky Straight Bourbon Whiskey\n"
                "Alcohol Content: 45% Alc./Vol. (90 Proof)\n"
                "Net Contents: 750 mL\n"
                "Name and Address: OLD TOM DISTILLERY - LOUISVILLE KY\n"
                "Country of Origin: United States\n"
                "Government Warning Required: yes\n"
            ).encode("utf-8"),
        )

        parsed = parse_application_file(uploaded)

        self.assertEqual(parsed.brand_name, "OLD TOM DISTILLERY")
        self.assertEqual(parsed.class_type, "Kentucky Straight Bourbon Whiskey")
        self.assertEqual(parsed.alcohol_content, "45% Alc./Vol. (90 Proof)")
        self.assertEqual(parsed.net_contents, "750 mL")
        self.assertEqual(parsed.name_address, "OLD TOM DISTILLERY - LOUISVILLE KY")
        self.assertEqual(parsed.country_of_origin, "United States")
        self.assertTrue(parsed.warning_required)

    def test_json_nested_imports_expected_fields(self):
        uploaded = UploadedFileStub(
            "application.json",
            b'''{
                "application": {
                    "Brand Name": "OLD TOM DISTILLERY",
                    "Class Type": "Kentucky Straight Bourbon Whiskey",
                    "Alcohol Content": "45% Alc./Vol. (90 Proof)",
                    "Net Contents": "750 mL",
                    "Name and Address": "OLD TOM DISTILLERY - LOUISVILLE KY",
                    "Country of Origin": "United States",
                    "Government Warning Required": "true"
                }
            }''',
        )

        parsed = parse_application_file(uploaded)

        self.assertEqual(parsed.brand_name, "OLD TOM DISTILLERY")
        self.assertEqual(parsed.class_type, "Kentucky Straight Bourbon Whiskey")
        self.assertEqual(parsed.alcohol_content, "45% Alc./Vol. (90 Proof)")
        self.assertEqual(parsed.net_contents, "750 mL")
        self.assertEqual(parsed.name_address, "OLD TOM DISTILLERY - LOUISVILLE KY")
        self.assertEqual(parsed.country_of_origin, "United States")
        self.assertTrue(parsed.warning_required)

    def test_blank_csv_cells_do_not_import_nan_text(self):
        uploaded = UploadedFileStub(
            "application.csv",
            (
                "brand_name,class_type,alcohol_content,net_contents\n"
                "OLD TOM DISTILLERY,,,750 mL\n"
            ).encode("utf-8"),
        )

        parsed = parse_application_file(uploaded)

        self.assertEqual(parsed.brand_name, "OLD TOM DISTILLERY")
        self.assertEqual(parsed.class_type, "")
        self.assertEqual(parsed.alcohol_content, "")
        self.assertEqual(parsed.net_contents, "750 mL")

    def test_expected_field_dict_includes_optional_checks(self):
        uploaded = UploadedFileStub(
            "application.txt",
            (
                "Brand Name: OLD TOM DISTILLERY\n"
                "Name and Address: OLD TOM DISTILLERY - LOUISVILLE KY\n"
                "Country of Origin: United States\n"
            ).encode("utf-8"),
        )

        parsed = parse_application_file(uploaded)
        fields = parsed.expected_field_dict()

        self.assertEqual(fields["name_address"], "OLD TOM DISTILLERY - LOUISVILLE KY")
        self.assertEqual(fields["country_of_origin"], "United States")


if __name__ == "__main__":
    unittest.main()