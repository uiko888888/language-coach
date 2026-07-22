import unittest
from collections import Counter

from backend.academic_phrases import (
    CATEGORY_META,
    academic_phrase_catalog,
    search_academic_phrases,
    validate_academic_phrases,
)


class AcademicPhraseTests(unittest.TestCase):
    def test_catalog_has_ten_complete_categories_and_unique_entries(self):
        validate_academic_phrases()
        items = academic_phrase_catalog()
        self.assertEqual(len(items), 100)
        self.assertEqual(Counter(item["category"] for item in items), Counter({key: 10 for key in CATEGORY_META}))
        self.assertEqual(len({item["term"].casefold() for item in items}), 100)
        self.assertTrue(all(item["meaning_zh"] and item["concept_en"] and item["grammar_frame"] for item in items))
        self.assertTrue(all(item["example"] and item["example_zh"] and item["sense_key"] for item in items))

    def test_search_filters_by_phrase_chinese_category_and_exam(self):
        exact = search_academic_phrases("provide evidence for")
        chinese = search_academic_phrases("提供证据")
        evidence = search_academic_phrases(category="evidence", exam="IELTS")
        self.assertEqual(exact[0]["term"], "provide evidence for")
        self.assertEqual(chinese[0]["term"], "provide evidence for")
        self.assertEqual(len(evidence), 10)
        self.assertTrue(all(item["category"] == "evidence" and "IELTS" in item["exam_tags"] for item in evidence))
        with self.assertRaisesRegex(ValueError, "category"):
            search_academic_phrases(category="unknown")


if __name__ == "__main__":
    unittest.main()
