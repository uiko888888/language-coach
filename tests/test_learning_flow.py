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
        self.assertEqual(article["content_status"], "full")

    def test_exam_question_type_filters_engine_output(self):
        items = server.generate_quiz_items(server.SAMPLE_ARTICLE, "mixed", "IELTS", "heading")
        self.assertTrue(items)
        self.assertTrue(all(item["type"] == "main-idea" for item in items))
        self.assertTrue(all("段落标题匹配" in item["note"] for item in items))

    def test_domestic_exam_styles_have_independent_types_and_profiles(self):
        expected = {
            "CET4": ("banked-cloze", "选词填空", "四级"),
            "CET6": ("matching", "长篇阅读", "六级"),
            "KAOYAN": ("sentence-meaning", "长难句语义", "考研"),
        }
        for style, (question_type, question_label, coaching_label) in expected.items():
            configured = {item[0] for item in server.EXAM_QUESTION_TYPES[style]}
            self.assertIn(question_type, configured)
            items = server.generate_quiz_items(server.SAMPLE_ARTICLE, "mixed", style, question_type)
            self.assertTrue(items)
            self.assertTrue(all(question_label in item["note"] for item in items))
            self.assertTrue(all(coaching_label in note for note in server.style_profile(style)["notes"]))

    def test_domestic_exam_source_matching(self):
        self.assertEqual(server.source_profile("Guardian Science", "CET4")["exam_fit"], 100)
        self.assertEqual(server.source_profile("The Conversation", "KAOYAN")["exam_fit"], 100)
        self.assertIn("CET6", server.source_profile("manual")["source_exams"])

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
        topic_items = server.list_articles({"exam": ["IELTS"], "topic": ["科技创新"]})
        self.assertTrue(topic_items)
        self.assertTrue(all("科技创新" in item["theme_tags"] for item in topic_items))
        recommended = server.list_articles({"exam": ["IELTS"], "recommended": ["1"]})
        self.assertLessEqual(len(recommended), 3)
        self.assertTrue(all(item["recommended_today"] for item in recommended))

    def test_article_themes_support_future_collections(self):
        article = {"title": "Protecting forests from climate pollution", "body": "New conservation policy could reduce carbon emissions."}
        profile = server.article_theme_profile(article)
        self.assertIn("环境保护", profile["theme_tags"])
        self.assertIn("环境保护", server.ARTICLE_THEMES)
        generic = server.article_theme_profile({"title": "A changing political environment", "body": "The government changed its media policy."})
        self.assertNotIn("环境保护", generic["theme_tags"])

    def test_article_normalization_removes_duplicate_title_and_builds_paragraphs(self):
        title = "A climate story"
        body = "A climate story. First sentence. Second sentence. Third sentence. Fourth sentence."
        normalized = server.normalize_article_text(title, body)
        self.assertFalse(normalized.lower().startswith(title.lower()))
        self.assertIn("\n\n", normalized)

    def test_article_completeness_is_explicit(self):
        item = server.enrich_article({
            "id": 99, "title": "Short feed item", "body": "A short RSS summary.",
            "source": "Guardian Science", "content_status": "summary", "created_at": server.utc_now(), "level": "B2",
        }, "IELTS")
        self.assertEqual(item["content_status"], "summary")
        self.assertEqual(item["content_word_count"], 4)

    def test_current_affairs_sources_have_explicit_classification(self):
        names = {feed["name"] for feed in server.DEFAULT_FEEDS}
        self.assertTrue({"BBC World", "Guardian Opinion", "NPR World", "UN News"}.issubset(names))
        opinion = server.source_profile("Guardian Opinion", "KAOYAN")
        self.assertEqual(opinion["source_kind"], "新闻媒体")
        self.assertEqual(opinion["default_content_type"], "opinion")
        institution = server.source_profile("UN News", "IELTS")
        self.assertEqual(institution["default_content_type_label"], "机构公告")

    def test_content_type_inference_and_filtering(self):
        self.assertEqual(server.infer_content_type({"source": "Guardian Opinion", "title": "A measured view"}), "opinion")
        self.assertEqual(server.infer_content_type({"source": "BBC World", "title": "New study finds a change"}), "research")
        now = server.utc_now()
        with server.db() as conn:
            conn.execute(
                """INSERT INTO articles
                   (title, language, level, topic, source, source_url, content_status, content_type, body, created_at, updated_at)
                   VALUES (?, 'en', 'B2', 'policy', 'manual', '', 'full', 'opinion', ?, ?, ?)""",
                ("A local policy opinion", "The writer presents a qualified argument about public policy.", now, now),
            )
        items = server.list_articles({"content_type": ["opinion"]})
        self.assertTrue(items)
        self.assertTrue(all(item["content_type"] == "opinion" for item in items))
        self.assertTrue(all(item["content_type_label"] == "观点评论" for item in items))

    def test_database_migrates_content_type_column(self):
        with server.db() as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(articles)")}
            seed = conn.execute("SELECT content_type FROM articles WHERE source = 'seed'").fetchone()
        self.assertIn("content_type", columns)
        self.assertEqual(seed["content_type"], "explainer")


if __name__ == "__main__":
    unittest.main()
