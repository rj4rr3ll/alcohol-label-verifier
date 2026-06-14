import unittest

from src.matching import (
    PASS,
    REVIEW,
    FAIL,
    normalize_text,
    contains_normalized_phrase,
    verify_text_field,
    verify_alcohol_content,
    verify_net_contents,
    verify_core_fields,
)
from src.warning_check import verify_government_warning


class TestMatchingLogic(unittest.TestCase):

    def test_normalize_text_case_and_punctuation(self):
        self.assertEqual(
            normalize_text("Stone's Throw"),
            normalize_text("STONE'S THROW")
        )

    def test_contains_normalized_phrase_allows_case_and_punctuation(self):
        self.assertTrue(
            contains_normalized_phrase("Stone's Throw", "STONE'S THROW")
        )

    def test_contains_normalized_phrase_blocks_embedded_word_match(self):
        self.assertFalse(
            contains_normalized_phrase("OLD TOM", "OLD TOMATO")
        )

    def test_exact_brand_match(self):
        detected = "OLD TOM DISTILLERY\nKentucky Straight Bourbon Whiskey"
        result = verify_text_field("Brand Name", "OLD TOM DISTILLERY", detected)
        self.assertEqual(result["Result"], PASS)

    def test_case_difference_brand_match(self):
        detected = "STONE'S THROW"
        result = verify_text_field("Brand Name", "Stone's Throw", detected)
        self.assertEqual(result["Result"], PASS)

    def test_near_brand_match_requires_review(self):
        detected = "Old Town Distillery"
        result = verify_text_field("Brand Name", "Old Tom Distillery", detected)
        self.assertIn(result["Result"], [REVIEW, PASS])

    def test_missing_brand_fails(self):
        detected = "Completely Different Label"
        result = verify_text_field("Brand Name", "OLD TOM DISTILLERY", detected)
        self.assertEqual(result["Result"], FAIL)

    def test_partial_class_type_subset_does_not_pass(self):
        detected = "WHISKY"
        result = verify_text_field("Class/Type", "Straight Rye Whisky", detected)
        self.assertNotEqual(result["Result"], PASS)

    def test_embedded_word_brand_does_not_pass(self):
        detected = "OLD TOMATO SPIRITS"
        result = verify_text_field("Brand Name", "OLD TOM", detected)
        self.assertNotEqual(result["Result"], PASS)

    def test_full_class_type_still_passes(self):
        detected = "Kentucky Straight Bourbon Whiskey"
        result = verify_text_field(
            "Class/Type",
            "Kentucky Straight Bourbon Whiskey",
            detected,
        )
        self.assertEqual(result["Result"], PASS)

    def test_abv_match(self):
        detected = "45% Alc./Vol. (90 Proof)"
        result = verify_alcohol_content("45%", detected)
        self.assertEqual(result["Result"], PASS)

    def test_abv_matches_proof(self):
        detected = "90 Proof"
        result = verify_alcohol_content("45%", detected)
        self.assertEqual(result["Result"], PASS)

    def test_net_contents_match(self):
        detected = "750 mL"
        result = verify_net_contents("750 mL", detected)
        self.assertEqual(result["Result"], PASS)

    def test_government_warning_correct(self):
        detected = (
            "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
            "drink alcoholic beverages during pregnancy because of the risk of birth defects. "
            "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
            "operate machinery, and may cause health problems."
        )
        result = verify_government_warning(detected, warning_required=True)
        self.assertEqual(result["Result"], PASS)

    def test_government_warning_title_case_fails(self):
        detected = (
            "Government Warning: (1) According to the Surgeon General, women should not "
            "drink alcoholic beverages during pregnancy because of the risk of birth defects. "
            "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
            "operate machinery, and may cause health problems."
        )
        result = verify_government_warning(detected, warning_required=True)
        self.assertEqual(result["Result"], FAIL)

    def test_government_warning_missing_fails(self):
        detected = "OLD TOM DISTILLERY\nKentucky Straight Bourbon Whiskey\n45% Alc./Vol.\n750 mL"
        result = verify_government_warning(detected, warning_required=True)
        self.assertEqual(result["Result"], FAIL)

    def test_government_warning_partial_requires_review(self):
        detected = (
            "GOVERNMENT WARNING: According to the Surgeon General, women should not "
            "drink alcoholic beverages during pregnancy."
        )
        result = verify_government_warning(detected, warning_required=True)
        self.assertEqual(result["Result"], REVIEW)

    def test_alcohol_marker_without_number_requires_review(self):
        detected = "% ALC/VOL"
        result = verify_alcohol_content("45%", detected)
        self.assertEqual(result["Result"], REVIEW)

    def test_abv_ocr_confuses_s_for_five(self):
        detected = "4S% ALC/VOL"
        result = verify_alcohol_content("45%", detected)
        self.assertEqual(result["Result"], PASS)

    def test_abv_ocr_confuses_o_for_zero_in_proof(self):
        detected = "9O Proof"
        result = verify_alcohol_content("45%", detected)
        self.assertEqual(result["Result"], PASS)

    def test_optional_name_address_check_runs_when_expected_value_provided(self):
        detected = "OLD TOM DISTILLERY\nBOTTLED BY OLD TOM DISTILLERY - LOUISVILLE KY"
        results = verify_core_fields(
            detected_text=detected,
            brand_name="OLD TOM DISTILLERY",
            class_type="",
            alcohol_content="",
            net_contents="",
            name_address="OLD TOM DISTILLERY - LOUISVILLE KY",
        )

        checks = [result["Check"] for result in results]
        self.assertIn("Name/Address", checks)

    def test_optional_country_check_is_omitted_when_blank(self):
        results = verify_core_fields(
            detected_text="OLD TOM DISTILLERY",
            brand_name="OLD TOM DISTILLERY",
            class_type="",
            alcohol_content="",
            net_contents="",
            country_of_origin="",
        )

        checks = [result["Check"] for result in results]
        self.assertNotIn("Country of Origin", checks)

    def test_optional_country_check_passes_when_present(self):
        detected = "Imported from Canada"
        results = verify_core_fields(
            detected_text=detected,
            brand_name="",
            class_type="",
            alcohol_content="",
            net_contents="",
            country_of_origin="Canada",
        )

        country_results = [result for result in results if result["Check"] == "Country of Origin"]
        self.assertEqual(country_results[0]["Result"], PASS)


if __name__ == "__main__":
    unittest.main()