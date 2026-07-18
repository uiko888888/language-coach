import unittest

from backend.content_extraction import adapter_catalog, extract_source_content, suggest_annotation_blocks


class ContentExtractionTests(unittest.TestCase):
    def test_bbc_adapter_registers_clean_summary_without_promoting_or_rewriting_it(self):
        text = "The broadcaster reports a policy change and links readers to the full report."
        result = extract_source_content(text, "BBC World")
        self.assertEqual(result["body"], text)
        self.assertEqual(result["extraction_version"], "bbc-rss-v1")
        self.assertEqual(result["removed_blocks"], [])

    def test_guardian_adapter_removes_only_known_feed_prompts(self):
        text = (
            "A report explains why the policy matters. "
            "Sign up for the Breaking News US newsletter email "
            "The final reported sentence remains useful. Continue reading..."
        )
        result = extract_source_content(text, "Guardian World")
        self.assertIn("A report explains why the policy matters.", result["body"])
        self.assertIn("The final reported sentence remains useful.", result["body"])
        self.assertNotIn("newsletter email", result["body"])
        self.assertNotIn("Continue reading", result["body"])
        self.assertEqual(result["removed_blocks"], ["newsletter_prompt", "continue_reading"])

    def test_jstor_adapter_stops_before_newsletter_and_form_script(self):
        article = "The final paragraph completes the historical argument."
        noise = "Weekly Newsletter var gform; gform.initializeOnLoaded(function() { return true; });"
        result = extract_source_content(f"{article}\n\n{noise}", "JSTOR Daily")
        self.assertEqual(result["body"], article)
        self.assertNotIn("gform", result["body"])
        self.assertEqual(result["extraction_version"], "jstor-rss-v1")
        self.assertEqual(result["removed_blocks"], ["newsletter_or_form"])

    def test_catalog_exposes_versioned_source_coverage(self):
        catalog = {item["key"]: item for item in adapter_catalog()}
        self.assertTrue({"conversation", "bbc", "guardian", "jstor"}.issubset(catalog))
        self.assertIn("BBC World", catalog["bbc"]["sources"])
        self.assertIn("JSTOR Daily", catalog["jstor"]["sources"])

    def test_annotation_candidates_separate_body_and_guardian_boilerplate(self):
        text = "A useful report remains available. Continue reading..."
        blocks = suggest_annotation_blocks(text, "Guardian World")
        self.assertEqual([item["suggested_label"] for item in blocks], ["body", "boilerplate"])
        self.assertEqual(blocks[0]["text"], "A useful report remains available.")
        self.assertEqual(blocks[1]["text"], "Continue reading...")
        self.assertTrue(all(len(item["block_hash"]) == 64 for item in blocks))

    def test_annotation_candidates_bound_long_jstor_noise_blocks(self):
        text = "A complete article.\n\nWeekly Newsletter " + ("var gform; " * 500)
        blocks = suggest_annotation_blocks(text, "JSTOR Daily")
        noise = [item for item in blocks if item["suggested_label"] == "boilerplate"]
        self.assertGreater(len(noise), 1)
        self.assertTrue(all(len(item["text"]) <= 1200 for item in noise))


if __name__ == "__main__":
    unittest.main()
