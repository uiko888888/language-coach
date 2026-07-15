import tempfile
import unittest
from pathlib import Path

from backend import server


class LearningFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        server.DB_PATH = Path(cls.temp_dir.name) / "learning.sqlite"
        server.init_db()

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_seed_article_has_reliable_translation(self):
        with server.db() as conn:
            article = conn.execute("SELECT * FROM articles WHERE source = 'seed'").fetchone()
        self.assertIn("智能设备", article["translation_zh"])
        self.assertIn("Smart devices", article["body"])

    def test_exam_question_type_filters_engine_output(self):
        items = server.generate_quiz_items(server.SAMPLE_ARTICLE, "mixed", "IELTS", "heading")
        self.assertTrue(items)
        self.assertTrue(all(item["type"] == "main-idea" for item in items))
        self.assertTrue(all("段落标题匹配" in item["note"] for item in items))

    def test_progress_awards_points_and_level(self):
        with server.db() as conn:
            progress = server.award_progress(conn, 110, correct=True)
        self.assertEqual(progress["level"], 2)
        self.assertEqual(progress["level_xp"], 10)
        self.assertEqual(progress["correct_count"], 1)
        self.assertEqual(progress["streak"], 1)

    def test_articles_receive_daily_recommendation_metadata(self):
        articles = server.list_articles({"exam": ["IELTS"]})
        self.assertTrue(articles)
        self.assertIn("recommendation_score", articles[0])
        self.assertTrue(articles[0]["recommended_today"])
        self.assertTrue(articles[0]["recommendation_reasons"])

    def test_article_topic_and_recommended_filters(self):
        topic_items = server.list_articles({"exam": ["IELTS"], "topic": ["科技"]})
        self.assertTrue(topic_items)
        self.assertTrue(all("科技" in item["source_topics"] for item in topic_items))
        recommended = server.list_articles({"exam": ["IELTS"], "recommended": ["1"]})
        self.assertLessEqual(len(recommended), 3)
        self.assertTrue(all(item["recommended_today"] for item in recommended))


if __name__ == "__main__":
    unittest.main()
