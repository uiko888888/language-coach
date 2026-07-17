import hashlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
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
        enriched = server.enrich_article(dict(article))
        self.assertEqual(enriched["paragraph_count"], enriched["translation_paragraph_count"])
        self.assertTrue(enriched["translation_aligned"])

    def test_score_profile_validates_and_stays_separate_from_xp(self):
        original = server.learner_settings()
        try:
            result = server.update_learner_profile({
                "profile_source": "score",
                "assessment_type": "IELTS",
                "assessment_date": "2026-07-01",
                "overall_score": 6.5,
                "section_scores": {"reading": 7, "listening": 5.5},
                "target_exam": "IELTS",
                "target_score": 7.5,
                "target_date": "2026-12-01",
                "weak_areas": ["listening", "paraphrase"],
                "interest_topics": ["影视娱乐", "科学技术"],
                "interest_content_types": ["subtitles", "interview"],
            })
            self.assertEqual(result["profile"]["cefr"], "B2")
            self.assertEqual(result["profile"]["confidence"], "high")
            self.assertNotIn("xp", result["profile"])
            self.assertEqual(result["settings"]["target_score"], 7.5)
        finally:
            server.save_learner_settings(original)

    def test_score_profile_requires_at_least_one_valid_score(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            server.update_learner_profile({
                "profile_source": "score", "assessment_type": "TOEFL", "target_exam": "TOEFL",
            })

    def test_quick_test_builds_reading_vocabulary_baseline_without_exposing_answers(self):
        original = server.learner_settings()
        try:
            public_items = server.quick_test_payload()
            self.assertTrue(public_items)
            self.assertTrue(all("answer" not in item for item in public_items))
            responses = {item["id"]: item["answer"] for item in server.QUICK_TEST_ITEMS[:5]}
            result = server.submit_quick_test({"responses": responses})
            self.assertEqual(result["profile"]["source"], "quick_test")
            self.assertEqual(result["profile"]["cefr"], "B2")
            self.assertEqual(result["result"]["domains"]["reading"]["answered"], 3)
        finally:
            server.save_learner_settings(original)

    def test_profile_shapes_today_difficulty_and_explains_recommendation(self):
        original = server.learner_settings()
        try:
            server.update_learner_profile({
                "profile_source": "self_assessment",
                "self_levels": {"reading": "B2", "vocabulary": "B2"},
                "target_exam": "IELTS",
                "interest_topics": ["科学技术"],
                "interest_content_types": ["explainer"],
            })
            today = server.today_content("IELTS", "interest")
            self.assertEqual(today["profile"]["cefr"], "B2")
            self.assertTrue(today["lanes"])
            self.assertTrue(any("难度接近你的 B2" in lane["reason"] for lane in today["lanes"]))
        finally:
            server.save_learner_settings(original)

    def test_daily_plan_update_preserves_profile(self):
        original = server.learner_settings()
        try:
            server.update_learner_profile({
                "profile_source": "self_assessment", "self_levels": {"reading": "B1"},
                "target_exam": "TOEFL", "interest_topics": ["影视娱乐"],
            })
            updated = server.update_learner_settings({
                "daily_minutes": 30, "daily_tasks": ["reading", "vocabulary"],
                "daily_targets": {"reading": 1, "vocabulary": 5},
            })
            self.assertEqual(updated["profile_source"], "self_assessment")
            self.assertEqual(updated["target_exam"], "TOEFL")
            self.assertEqual(updated["interest_topics"], ["影视娱乐"])
        finally:
            server.save_learner_settings(original)

    def test_weekly_calibration_updates_only_eligible_reading_domain(self):
        original = server.learner_settings()
        now = datetime(2026, 7, 18, 2, 0, tzinfo=timezone.utc)
        created_ids = {"sessions": [], "quizzes": [], "attempts": []}
        try:
            profile = server.update_learner_profile({
                "profile_source": "self_assessment",
                "self_levels": {"reading": "B1", "listening": "A2", "writing": "A2", "speaking": "A2"},
                "target_exam": "IELTS",
            })
            settings = profile["settings"]
            settings["profile_started_at"] = (now - timedelta(days=8)).isoformat()
            server.save_learner_settings(settings)
            with server.db() as conn:
                article_id = conn.execute("SELECT id FROM articles ORDER BY id LIMIT 1").fetchone()[0]
                for session_index, day_offset in enumerate((6, 1)):
                    session_id = conn.execute(
                        """INSERT INTO practice_sessions
                           (article_id, style, question_type, session_mode, question_count, answered_count,
                            correct_count, elapsed_seconds, score, completed_at)
                           VALUES (?, 'IELTS', 'tfng', 'practice', 4, 4, 4, 240, 100, ?)""",
                        (article_id, (now - timedelta(days=day_offset)).isoformat()),
                    ).lastrowid
                    created_ids["sessions"].append(session_id)
                    for item_index in range(4):
                        quiz_id = conn.execute(
                            """INSERT INTO quizzes
                               (article_id, style, mode, type, question_type, skill, difficulty,
                                prompt, answer, options_json, evidence, note, created_at)
                               VALUES (?, 'IELTS', 'reading', 'tfng', 'tfng', '证据定位', 'B2', ?, 'TRUE',
                                       '[\"TRUE\",\"FALSE\",\"NOT GIVEN\"]', 'Evidence', 'test', ?)""",
                            (article_id, f"Calibration reading {session_index}-{item_index}", now.isoformat()),
                        ).lastrowid
                        created_ids["quizzes"].append(quiz_id)
                        attempt_id = conn.execute(
                            """INSERT INTO attempts
                               (quiz_id, session_id, user_answer, confidence, correct, error_type, created_at)
                               VALUES (?, ?, 'TRUE', 3, 1, '', ?)""",
                            (quiz_id, session_id, (now - timedelta(days=day_offset)).isoformat()),
                        ).lastrowid
                        created_ids["attempts"].append(attempt_id)
            result = server.run_profile_calibration(force=False, now=now)
            self.assertTrue(result["ran"])
            self.assertTrue(result["domains"]["reading"]["adjusted"])
            self.assertGreater(result["domains"]["reading"]["after"]["score"], result["domains"]["reading"]["before"]["score"])
            self.assertFalse(result["domains"]["listening"]["adjusted"])
            self.assertFalse(result["overall"]["adjusted"])
            self.assertIn("3 个分项", result["overall"]["reason"])
        finally:
            with server.db() as conn:
                if created_ids["attempts"]:
                    conn.execute(f"DELETE FROM attempts WHERE id IN ({','.join('?' for _ in created_ids['attempts'])})", created_ids["attempts"])
                if created_ids["quizzes"]:
                    conn.execute(f"DELETE FROM quizzes WHERE id IN ({','.join('?' for _ in created_ids['quizzes'])})", created_ids["quizzes"])
                if created_ids["sessions"]:
                    conn.execute(f"DELETE FROM practice_sessions WHERE id IN ({','.join('?' for _ in created_ids['sessions'])})", created_ids["sessions"])
                conn.execute("DELETE FROM profile_calibrations")
            server.save_learner_settings(original)

    def test_profile_calibration_waits_seven_days(self):
        original = server.learner_settings()
        now = datetime(2026, 7, 18, 2, 0, tzinfo=timezone.utc)
        try:
            settings = server.update_learner_profile({
                "profile_source": "self_assessment", "self_levels": {"reading": "B1"}, "target_exam": "IELTS",
            })["settings"]
            settings["profile_started_at"] = (now - timedelta(days=6)).isoformat()
            server.save_learner_settings(settings)
            result = server.run_profile_calibration(now=now)
            self.assertFalse(result["ran"])
            self.assertFalse(result["due"])
            self.assertEqual(result["days_remaining"], 1)
        finally:
            server.save_learner_settings(original)

    def test_changing_baseline_resets_calibration_but_changing_preferences_does_not(self):
        original = server.learner_settings()
        try:
            first = server.update_learner_profile({
                "profile_source": "self_assessment", "self_levels": {"reading": "B1"}, "target_exam": "IELTS",
            })["settings"]
            first["ability_domains"] = {"reading": {"cefr": "B2", "score": 62, "confidence": "medium", "evidence_count": 12, "updated_at": server.utc_now()}}
            first["last_calibration_at"] = server.utc_now()
            server.save_learner_settings(first)
            preferences = server.update_learner_profile({
                "profile_source": "self_assessment", "self_levels": {"reading": "B1"},
                "target_exam": "IELTS", "interest_topics": ["影视娱乐"],
            })["settings"]
            self.assertTrue(preferences["ability_domains"])
            changed = server.update_learner_profile({
                "profile_source": "self_assessment", "self_levels": {"reading": "B2"}, "target_exam": "IELTS",
            })["settings"]
            self.assertEqual(changed["ability_domains"], {})
            self.assertEqual(changed["last_calibration_at"], "")
        finally:
            server.save_learner_settings(original)

    def test_exam_question_type_filters_engine_output(self):
        items = server.generate_quiz_items(server.SAMPLE_ARTICLE, "mixed", "IELTS", "heading")
        self.assertTrue(items)
        self.assertTrue(all(item["type"] == "heading" for item in items))
        self.assertTrue(all("段落标题匹配" in item["note"] for item in items))

    def test_mixed_generation_no_longer_creates_initial_letter_items(self):
        items = server.generate_quiz_items(server.SAMPLE_ARTICLE, "mixed", "general")
        self.assertTrue(items)
        self.assertFalse(any(item["type"] == "initial" for item in items))

    def test_ielts_tfng_uses_official_answer_format(self):
        items = server.generate_quiz_items(server.SAMPLE_ARTICLE, "mixed", "IELTS", "tfng")
        self.assertEqual(len(items), 3)
        self.assertEqual({item["answer"] for item in items}, {"TRUE", "FALSE", "NOT GIVEN"})
        self.assertTrue(all(item["options"] == ["TRUE", "FALSE", "NOT GIVEN"] for item in items))
        self.assertTrue(all(item["validation"]["valid"] for item in items))

    def test_ielts_single_passage_combination_contains_multiple_specialties(self):
        items = server.generate_quiz_items(server.SAMPLE_ARTICLE, "reading", "IELTS", "mixed")
        self.assertGreaterEqual(len({item["question_type"] for item in items}), 2)
        self.assertTrue(all(item["validation"]["valid"] for item in items))

    def test_every_ielts_template_has_metadata_and_passes_validation(self):
        for question_type in ("tfng", "heading", "matching-info", "gap-fill"):
            items = server.generate_quiz_items(server.SAMPLE_ARTICLE, "mixed", "IELTS", question_type)
            self.assertTrue(items, question_type)
            self.assertTrue(all(item["question_type"] == question_type for item in items))
            self.assertTrue(all(item["skill"] and item["difficulty"] for item in items))
            self.assertTrue(all(item["validation"]["valid"] for item in items))

    def test_toefl_templates_are_independent_validated_and_mixed(self):
        for question_type in server.TOEFL_TASK_META:
            items = server.generate_quiz_items(server.SAMPLE_ARTICLE, "reading", "TOEFL", question_type)
            self.assertTrue(items, question_type)
            self.assertTrue(all(item["question_type"] == question_type for item in items))
            expected_source = "toefl-2026-sim-v1" if question_type == "complete-words" else "toefl-rule-v2"
            self.assertTrue(all(item["generation_source"] == expected_source for item in items))
            self.assertTrue(all(item["validation"]["valid"] for item in items))
            expected_option_count = 0 if question_type == "complete-words" else 4
            self.assertTrue(all(len(item["options"]) == expected_option_count for item in items))
            self.assertTrue(all(item["skill"] and item["difficulty"] for item in items))
        mixed = server.generate_quiz_items(server.SAMPLE_ARTICLE, "reading", "TOEFL", "mixed")
        self.assertEqual({item["question_type"] for item in mixed}, set(server.TOEFL_TASK_META))

    def test_toefl_error_types_are_specific(self):
        expected = {
            "complete-words": "拼写或词形错误",
            "factual": "事实定位或限定范围错误",
            "negative-factual": "EXCEPT 方向或多项证据核对错误",
            "inference": "推断距离过远或证据范围扩大",
            "rhetorical-purpose": "句子内容与修辞功能混淆",
            "main-idea": "主旨与细节混淆",
            "simplification": "关键信息遗漏或逻辑关系改变",
            "insertion": "指代或篇章衔接判断错误",
            "prose-summary": "主旨覆盖不足或细节权重错误",
            "vocabulary": "语境词义判断错误",
        }
        for question_type, error_type in expected.items():
            self.assertEqual(
                server.classify_answer_error({"question_type": question_type, "answer": "A"}, "B"),
                error_type,
            )

    def test_toefl_complete_words_masks_and_validates_a_traceable_word(self):
        items = server.toefl_quiz_items(server.SAMPLE_ARTICLE, "complete-words")
        self.assertTrue(items)
        item = items[0]
        self.assertEqual(item["generation_source"], "toefl-2026-sim-v1")
        self.assertFalse(item["options"])
        self.assertIn(item["target_word"], item["evidence"])
        self.assertNotIn(item["target_word"], item["masked_text"])
        self.assertIn("_" * item["missing_count"], item["masked_text"])
        self.assertTrue(item["validation"]["valid"])
        self.assertFalse(item["official_equivalence"])
        with server.db() as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(quizzes)")}
        self.assertIn("metadata_json", columns)

        broken = {**item, "missing_count": item["missing_count"] + 1}
        result = server.validate_quiz_item(broken, server.SAMPLE_ARTICLE, "TOEFL", "complete-words")
        self.assertFalse(result["valid"])
        self.assertIn("complete_word_mask", result["errors"])

    def test_toefl_advanced_templates_enforce_exam_specific_evidence_contracts(self):
        negative = server.toefl_negative_factual_items(server.SAMPLE_ARTICLE)[0]
        self.assertEqual(len(negative["supported_options"]), 3)
        self.assertTrue(all(value in negative["evidence"] for value in negative["supported_options"]))
        self.assertNotIn(negative["answer"], negative["evidence"])

        insertion = server.toefl_insertion_items(server.SAMPLE_ARTICLE)[0]
        rebuilt = list(insertion["base_sentences"])
        rebuilt.insert(insertion["insertion_position"], insertion["target_sentence"])
        self.assertEqual(rebuilt, server.sentences(insertion["evidence"]))

        summary = server.toefl_prose_summary_items(server.SAMPLE_ARTICLE)[0]
        self.assertGreaterEqual(len(summary["covered_paragraphs"]), 2)
        self.assertTrue(all(idea in summary["answer"] for idea in summary["key_ideas"]))

        broken = {**insertion, "insertion_position": 0}
        result = server.validate_quiz_item(broken, server.SAMPLE_ARTICLE, "TOEFL", "insertion")
        self.assertFalse(result["valid"])
        self.assertIn("insertion_reconstructs_paragraph", result["errors"])

    def test_validator_rejects_untraceable_evidence(self):
        item = {
            "prompt": "Choose the answer.", "answer": "TRUE",
            "options": ["TRUE", "FALSE", "NOT GIVEN"],
            "evidence": "This sentence does not occur.",
            "skill": "证据判断", "difficulty": "B2",
        }
        result = server.validate_quiz_item(item, server.SAMPLE_ARTICLE, "IELTS", "tfng")
        self.assertFalse(result["valid"])
        self.assertIn("evidence_not_in_source", result["errors"])

    def test_tfng_validator_rejects_uncontrolled_false_statement(self):
        evidence = "A speaker can learn when a family is at home."
        item = {
            "prompt": "Statement: A speaker is expensive.", "statement": "A speaker is expensive.",
            "answer": "FALSE", "evidence_relation": "contradicts",
            "options": ["TRUE", "FALSE", "NOT GIVEN"], "evidence": evidence,
            "skill": "证据判断", "difficulty": "B2",
        }
        result = server.validate_quiz_item(item, server.SAMPLE_ARTICLE, "IELTS", "tfng")
        self.assertFalse(result["valid"])
        self.assertIn("controlled_contradiction", result["errors"])

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

    def test_kaoyan_templates_are_independent_validated_and_mixed(self):
        for question_type in ("detail-inference", "main-attitude", "sentence-meaning", "cloze-logic"):
            items = server.generate_quiz_items(server.SAMPLE_ARTICLE, "reading", "KAOYAN", question_type)
            self.assertTrue(items, question_type)
            self.assertTrue(all(item["question_type"] == question_type for item in items))
            self.assertTrue(all(item["generation_source"] == "kaoyan-rule-v1" for item in items))
            self.assertTrue(all(item["validation"]["valid"] for item in items))
            self.assertTrue(all(item["skill"] and item["difficulty"] for item in items))
        mixed = server.generate_quiz_items(server.SAMPLE_ARTICLE, "reading", "KAOYAN", "mixed")
        self.assertEqual({item["question_type"] for item in mixed}, set(server.KAOYAN_TASK_META))

    def test_kaoyan_error_types_are_specific(self):
        expected = {
            "detail-inference": "证据范围扩大或推断过度",
            "main-attitude": "主旨、观点转述与作者态度混淆",
            "sentence-meaning": "长难句主干或逻辑关系判断错误",
            "cloze-logic": "词义、搭配或篇章逻辑错误",
        }
        for question_type, error_type in expected.items():
            self.assertEqual(
                server.classify_answer_error({"question_type": question_type, "answer": "A"}, "B"),
                error_type,
            )

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

    def test_source_catalog_distinguishes_automatic_and_authorized_access(self):
        catalog = {item["name"]: item for item in server.source_catalog()}
        self.assertTrue(catalog["BBC World"]["automatic"])
        self.assertEqual(catalog["BBC World"]["access_mode"], "RSS 自动更新")
        self.assertFalse(catalog["HBO Max"]["automatic"])
        self.assertIn("不抓取视频", catalog["HBO Max"]["rights_mode"])
        self.assertEqual(catalog["Project Gutenberg"]["access_mode"], "开放全文")

    def test_source_registry_covers_graduate_information_channels(self):
        catalog = {item["name"]: item for item in server.source_catalog()}
        expected = {
            "Reuters", "Associated Press", "Financial Times", "Bloomberg", "The Atlantic",
            "Foreign Affairs", "Nature News", "Science", "NASA", "NOAA", "TED", "NPR Podcasts",
            "Google Scholar", "arXiv", "PubMed", "SSRN", "Project MUSE", "Open Library",
            "University public lectures", "Local life services",
        }
        self.assertTrue(expected.issubset(catalog))
        self.assertEqual(set(server.CONTENT_HUBS.values()), {
            "新闻", "观点", "研究", "科学与自然", "文化与生活", "影视与听力", "小说与图书",
        })
        for item in catalog.values():
            self.assertIn(item["hub"], server.CONTENT_HUBS)
            self.assertTrue(item["access_mode"])
            self.assertTrue(item["rights_mode"])
            self.assertTrue(item["formats"])
            self.assertTrue(item["cadence"])
            self.assertTrue(item["difficulty"])
            self.assertIn("transcript_available", item)

    def test_article_hub_and_subscription_filters_are_real(self):
        now = server.utc_now()
        with server.db() as conn:
            conn.execute(
                """INSERT INTO articles
                   (title, language, level, topic, source, source_url, content_status, content_type, body, created_at, updated_at)
                   VALUES ('A world policy briefing', 'en', 'B2', 'policy', 'BBC World', '', 'full', 'report', ?, ?, ?)""",
                ("The report explains a policy change and its effects on communities.", now, now),
            )
        news = server.list_articles({"hub": ["news"]})
        self.assertTrue(news)
        self.assertTrue(all(item["content_hub"] == "news" for item in news))
        with server.db() as conn:
            conn.execute(
                """INSERT INTO subscriptions (target_type, target_value, active, created_at, updated_at)
                   VALUES ('category', '新闻', 1, ?, ?)
                   ON CONFLICT(target_type, target_value) DO UPDATE SET active = 1, updated_at = excluded.updated_at""",
                (now, now),
            )
        subscribed = server.list_articles({"hub": ["subscribed"]})
        self.assertTrue(subscribed)
        self.assertTrue(all(item["subscribed"] for item in subscribed))

    def test_subscriptions_shape_unique_today_content(self):
        now = server.utc_now()
        fixtures = [
            ("World briefing", "BBC World", "report", "A concise world report explains a significant policy change and its public effects."),
            ("A measured policy argument", "Guardian Opinion", "opinion", "The writer develops a qualified argument about evidence, institutions, and public trust. " * 8),
            ("Institutional health update", "UN News", "institution", "The institution reports a health programme and explains the evidence behind the international response."),
        ]
        with server.db() as conn:
            for title, source, content_type, body in fixtures:
                conn.execute(
                    """INSERT INTO articles
                       (title, language, level, topic, source, source_url, content_status, content_type, body, created_at, updated_at)
                       VALUES (?, 'en', 'B2', 'policy', ?, '', 'full', ?, ?, ?, ?)""",
                    (title, source, content_type, body, now, now),
                )
            conn.execute(
                """INSERT INTO subscriptions (target_type, target_value, active, created_at, updated_at)
                   VALUES ('source', 'Guardian Opinion', 1, ?, ?)
                   ON CONFLICT(target_type, target_value) DO UPDATE SET active = 1, updated_at = excluded.updated_at""",
                (now, now),
            )
        payload = server.today_content("KAOYAN")
        ids = [lane["article"]["id"] for lane in payload["lanes"]]
        sources = [lane["article"]["source"] for lane in payload["lanes"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(sources), len(set(sources)))
        self.assertGreaterEqual(payload["subscription_count"], 1)
        self.assertTrue(any(lane["article"]["subscribed"] for lane in payload["lanes"]))
        catalog = {item["name"]: item for item in server.source_catalog_payload()}
        self.assertTrue(catalog["Guardian Opinion"]["subscribed"])

    def test_today_content_has_distinct_persistent_mode_contract(self):
        interest = server.today_content("IELTS", "interest")
        exam = server.today_content("IELTS", "exam")
        self.assertEqual(interest["mode"], "interest")
        self.assertEqual(exam["mode"], "exam")
        self.assertTrue(any(lane["label"] == "15 分钟沉浸" for lane in interest["lanes"]))
        self.assertTrue(any(lane["label"] == "15 分钟精读" for lane in exam["lanes"]))
        self.assertEqual(server.today_content("IELTS", "unknown")["mode"], "exam")

    def test_translation_status_supports_private_provider_configuration(self):
        keys = ("TRANSLATION_PROVIDER", "DEEPL_API_KEY", "LIBRETRANSLATE_URL")
        previous = {key: os.environ.get(key) for key in keys}
        try:
            os.environ["TRANSLATION_PROVIDER"] = "libretranslate"
            os.environ.pop("DEEPL_API_KEY", None)
            os.environ["LIBRETRANSLATE_URL"] = "http://127.0.0.1:5000"
            status = server.translation_status()
            self.assertTrue(status["configured"])
            self.assertEqual(status["provider_id"], "libretranslate")
            self.assertEqual(len(status["options"]), 3)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_cached_segment_translation_preserves_paragraph_order(self):
        segments = ["First paragraph.", "Second paragraph."]
        translations = ["第一段。", "第二段。"]
        with server.db() as conn:
            for source, translated in zip(segments, translations):
                digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
                conn.execute(
                    """INSERT OR REPLACE INTO translation_cache
                       (text_hash, source_lang, target_lang, provider, source_text, translated_text, created_at)
                       VALUES (?, 'EN', 'ZH-HANS', 'deepl', ?, ?, ?)""",
                    (digest, source, translated, server.utc_now()),
                )
        result = server.translate_segments(segments)
        self.assertTrue(result["cached"])
        self.assertEqual(result["translated_segments"], translations)

    def test_vocabulary_candidates_prioritize_saved_phrases(self):
        now = server.utc_now()
        with server.db() as conn:
            conn.execute(
                """INSERT INTO cards (term, kind, context, status, created_at, updated_at)
                   VALUES ('meaningful control', 'phrase', '', 'new', ?, ?)""",
                (now, now),
            )
        candidates = server.vocabulary_candidates(
            "People need meaningful control over extraordinarily complicated privacy arrangements."
        )
        saved = next(item for item in candidates if item["term"] == "meaningful control")
        self.assertEqual(saved["kind"], "phrase")
        self.assertEqual(saved["reason"], "已在生词本")
        self.assertTrue(saved["saved"])


if __name__ == "__main__":
    unittest.main()
