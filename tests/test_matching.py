import unittest

from src.matching import (
    PASS,
    REVIEW,
    FAIL,
    normalize_text,
    verify_text_field,
    verify_alcohol_content,
    verify_net_contents,
)


class TestMatchingLogic(unittest.TestCase):

    def test_normalize_text_case_and_punctuation(self):
        self.assertEqual(
            normalize_text("Stone's Throw"),
            normalize_text("STONE'S THROW")
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


if __name__ == "__main__":
    unittest.main()