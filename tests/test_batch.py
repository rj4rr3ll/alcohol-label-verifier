import unittest

import pandas as pd

from src.batch import (
    clean_cell,
    normalize_batch_dataframe,
    validate_batch_dataframe,
    parse_warning_required,
    build_batch_failure_result,
    verify_batch_label,
)


class TestBatchLogic(unittest.TestCase):

    def test_clean_cell_converts_nan_to_empty_string(self):
        self.assertEqual(clean_cell(float("nan")), "")
        self.assertEqual(clean_cell(pd.NA), "")
        self.assertEqual(clean_cell("  OLD TOM  "), "OLD TOM")

    def test_normalize_batch_dataframe_column_names(self):
        df = pd.DataFrame(
            columns=[
                "File Name",
                "Brand Name",
                "Class-Type",
                "Alcohol Content",
                "Net Contents",
                "Name Address",
                "Country of Origin",
            ]
        )
        normalized = normalize_batch_dataframe(df)

        self.assertIn("file_name", normalized.columns)
        self.assertIn("brand_name", normalized.columns)
        self.assertIn("class_type", normalized.columns)
        self.assertIn("alcohol_content", normalized.columns)
        self.assertIn("net_contents", normalized.columns)
        self.assertIn("name_address", normalized.columns)
        self.assertIn("country_of_origin", normalized.columns)

    def test_validate_batch_dataframe_reports_missing_columns(self):
        df = pd.DataFrame(columns=["file_name", "brand_name"])
        missing = validate_batch_dataframe(df)

        self.assertIn("class_type", missing)
        self.assertIn("alcohol_content", missing)
        self.assertIn("net_contents", missing)

    def test_parse_warning_required_false_values(self):
        self.assertFalse(parse_warning_required("false"))
        self.assertFalse(parse_warning_required("No"))
        self.assertFalse(parse_warning_required("0"))
        self.assertTrue(parse_warning_required("true"))
        self.assertTrue(parse_warning_required(""))
        self.assertTrue(parse_warning_required(pd.NA))

    def test_build_batch_failure_result_does_not_show_nan(self):
        row = pd.Series(
            {
                "file_name": "missing_label.png",
                "brand_name": float("nan"),
                "class_type": "Kentucky Straight Bourbon Whiskey",
                "alcohol_content": pd.NA,
                "net_contents": "750 mL",
                "name_address": pd.NA,
                "country_of_origin": float("nan"),
            }
        )

        result = build_batch_failure_result(row, "Matching image file was not uploaded.")

        self.assertEqual(result["Brand Name"], "")
        self.assertEqual(result["Alcohol Content"], "")
        self.assertEqual(result["Country of Origin"], "")
        self.assertEqual(result["Overall Result"], "FAIL")

    def test_verify_batch_label_does_not_show_nan_expected_fields(self):
        row = pd.Series(
            {
                "file_name": "old_tom.png",
                "brand_name": "OLD TOM DISTILLERY",
                "class_type": float("nan"),
                "alcohol_content": "45%",
                "net_contents": "750 mL",
                "name_address": "OLD TOM DISTILLERY - LOUISVILLE KY",
                "country_of_origin": "United States",
                "warning_required": "true",
            }
        )
        detected = (
            "OLD TOM DISTILLERY\n"
            "45% Alc./Vol.\n"
            "750 mL\n"
            "BOTTLED BY OLD TOM DISTILLERY - LOUISVILLE KY\n"
            "Product of United States\n"
            "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
            "drink alcoholic beverages during pregnancy because of the risk of birth defects. "
            "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
            "operate machinery, and may cause health problems."
        )

        result = verify_batch_label(row, detected)

        self.assertEqual(result["Class/Type"], "")
        self.assertEqual(result["Name/Address"], "OLD TOM DISTILLERY - LOUISVILLE KY")
        self.assertEqual(result["Country of Origin"], "United States")
        self.assertNotIn("nan", result["Issues"].lower())


if __name__ == "__main__":
    unittest.main()