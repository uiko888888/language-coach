import sqlite3
import unittest

from backend.academic_phrase_recommendation import recommend_academic_phrases


class AcademicPhraseRecommendationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE academic_phrase_attempts (sense_key TEXT, correct INTEGER, created_at TEXT);
            CREATE TABLE cards (id INTEGER, kind TEXT, sense_key TEXT);
            CREATE TABLE review_items (item_type TEXT, item_id INTEGER, due_at TEXT, state TEXT);
        """)

    def tearDown(self):
        self.conn.close()

    def test_unpractised_items_are_explained_and_wrong_items_rank_higher(self):
        self.conn.execute("INSERT INTO academic_phrase_attempts VALUES (?, 0, ?)", ("academic-phrase:provide evidence for", "2026-07-22T00:00:00+00:00"))
        items = recommend_academic_phrases(self.conn, task_type="cloze", limit=50)
        target = next(item for item in items if item["term"] == "provide evidence for")
        self.assertEqual(target["wrong_attempts"], 1)
        self.assertIn("答错", target["recommendation_reason"])
        self.assertTrue(any(item["recommendation_reason"] == "尚未练习" for item in items))


if __name__ == "__main__":
    unittest.main()
