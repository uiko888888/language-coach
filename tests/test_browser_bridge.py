import hashlib
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from backend import server


class BrowserBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        server.DB_PATH = Path(cls.temp_dir.name) / "browser.sqlite"
        server.init_db()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.App)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        cls.token = server.browser_bridge_token()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.temp_dir.cleanup()

    def request(self, path, method="GET", payload=None, token=None, origin=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["X-Language-Coach-Token"] = token
        if origin:
            headers["Origin"] = origin
        request = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        with urllib.request.urlopen(request) as response:
            return json.load(response), response.headers

    def setUp(self):
        server.TRANSLATION_RUNTIME.update({"verified": None, "last_error": "", "deepl_url": ""})

    def test_bridge_token_is_persistent_and_required(self):
        self.assertGreater(len(self.token), 20)
        try:
            self.request("/api/browser/clips")
        except urllib.error.HTTPError as error:
            self.assertEqual(error.code, 401)
            error.close()
        else:
            self.fail("Browser clips endpoint accepted a request without a token")

    def test_profile_api_supports_score_and_quick_test_paths(self):
        original = server.learner_settings()
        try:
            quick, _ = self.request("/api/profile/quick-test")
            self.assertEqual(len(quick["items"]), 6)
            self.assertTrue(all("answer" not in item for item in quick["items"]))
            score, _ = self.request("/api/learner-profile", "POST", {
                "profile_source": "score", "assessment_type": "TOEFL", "overall_score": 86,
                "target_exam": "TOEFL", "target_score": 100, "weak_areas": ["listening"],
                "interest_topics": ["影视娱乐"], "interest_content_types": ["subtitles"],
            })
            self.assertEqual(score["profile"]["cefr"], "B2")
            responses = {item["id"]: source["answer"] for item, source in zip(quick["items"], server.QUICK_TEST_ITEMS)}
            baseline, _ = self.request("/api/profile/quick-test", "POST", {
                "responses": responses, "target_exam": "IELTS", "target_score": 7,
                "weak_areas": ["paraphrase"], "interest_topics": ["明星访谈"],
                "interest_content_types": ["interview"],
            })
            self.assertEqual(baseline["profile"]["source"], "quick_test")
            self.assertEqual(baseline["profile"]["cefr"], "C1")
        finally:
            server.save_learner_settings(original)

    def test_interest_and_exam_modes_return_distinct_workflows(self):
        original = server.learner_settings()
        try:
            server.update_learner_profile({
                "profile_source": "self_assessment", "self_levels": {"reading": "B1"},
                "target_exam": "IELTS", "target_score": 7,
                "interest_topics": ["影视娱乐"], "interest_content_types": ["culture"],
            })
            interest, _ = self.request("/api/today?exam=IELTS&mode=interest")
            exam, _ = self.request("/api/today?exam=IELTS&mode=exam")
            self.assertEqual(interest["mode_focus"]["next_action"], "reading")
            self.assertEqual(exam["mode_focus"]["next_action"], "practice")
            self.assertNotEqual(interest["mode_focus"]["title"], exam["mode_focus"]["title"])
            self.assertIn("calibration", exam)
            self.assertTrue(any("目标" in value for value in exam["mode_focus"]["signals"]))
        finally:
            server.save_learner_settings(original)

    def test_selection_saves_context_and_source_to_wordbook(self):
        payload = {
            "kind": "selection",
            "text": "meaningful control over their own data",
            "translation": "真正掌控自己的数据",
            "context": "Companies should give people meaningful control over their own data.",
            "page_title": "Privacy article",
            "page_url": "https://example.test/privacy",
        }
        data, _ = self.request("/api/browser/clips", "POST", payload, self.token)
        self.assertEqual(data["clip"]["page_url"], payload["page_url"])
        self.assertEqual(data["clip"]["translated_text"], payload["translation"])
        self.assertEqual(data["card"]["context"], payload["context"])

    def test_repeated_browser_selection_updates_one_card(self):
        payload = {
            "kind": "selection",
            "text": "evidence-based practice",
            "context": "The first evidence-based practice example.",
            "page_title": "First page",
            "page_url": "https://example.test/first",
        }
        first, _ = self.request("/api/browser/clips", "POST", payload, self.token)
        payload.update({
            "context": "A newer evidence-based practice example.",
            "page_title": "Second page",
            "page_url": "https://example.test/second",
        })
        second, _ = self.request("/api/browser/clips", "POST", payload, self.token)
        self.assertEqual(first["card"]["id"], second["card"]["id"])
        self.assertEqual(second["card"]["context"], payload["context"])
        with server.db() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM cards WHERE lower(term) = lower('evidence-based practice')"
            ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_extracted_article_enters_full_content_pool(self):
        text = "First paragraph about climate policy. Second paragraph explains the evidence. " * 8
        payload = {
            "kind": "article",
            "text": text,
            "page_title": "Extracted climate article",
            "page_url": "https://example.test/full-article",
            "save_to": "articles",
        }
        data, _ = self.request("/api/browser/clips", "POST", payload, self.token)
        self.assertEqual(data["article"]["content_status"], "full")
        self.assertEqual(data["article"]["source_url"], payload["page_url"])
        self.assertIn("环境保护", data["article"]["theme_tags"])
        self.assertEqual(data["article"]["content_type"], "explainer")
        self.assertEqual(data["article"]["source_kind"], "网页导入")

    def test_translation_cache_works_without_network(self):
        text = "A cached translation"
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        with server.db() as conn:
            conn.execute(
                """INSERT INTO translation_cache
                   (text_hash, source_lang, target_lang, provider, source_text, translated_text, created_at)
                   VALUES (?, 'EN', 'ZH-HANS', 'deepl', ?, ?, ?)""",
                (digest, text, "缓存译文", server.utc_now()),
            )
        result = server.translate_text(text)
        self.assertTrue(result["cached"])
        self.assertEqual(result["translated_text"], "缓存译文")

    def test_segment_translation_endpoint_preserves_alignment_from_cache(self):
        segments = ["first open definition", "second open example"]
        translations = ["第一个开放释义", "第二个开放例句"]
        with server.db() as conn:
            for source, translated in zip(segments, translations):
                digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
                conn.execute(
                    """INSERT OR REPLACE INTO translation_cache
                       (text_hash, source_lang, target_lang, provider, source_text, translated_text, created_at)
                       VALUES (?, 'EN', 'ZH-HANS', 'deepl', ?, ?, ?)""",
                    (digest, source, translated, server.utc_now()),
                )
        result, _ = self.request(
            "/api/browser/translate-segments",
            "POST",
            {"segments": segments, "source_lang": "EN", "target_lang": "ZH-HANS"},
            self.token,
        )
        self.assertTrue(result["cached"])
        self.assertEqual(result["translated_segments"], translations)

    def test_deepl_verification_reports_rejected_key(self):
        rejected = urllib.error.HTTPError("https://api-free.deepl.com/v2/usage", 403, "Forbidden", {}, None)
        with patch.dict(server.os.environ, {"DEEPL_API_KEY": "test-key", "DEEPL_API_URL": "https://api-free.deepl.com/v2/translate"}), \
                patch("backend.server.urllib.request.urlopen", side_effect=[rejected, rejected]):
            status = server.verify_deepl_configuration()
        self.assertFalse(status["verified"])
        self.assertIn("403", status["last_error"])
        self.assertNotIn("test-key", status["last_error"])

    def test_extension_origin_receives_cors_headers(self):
        request = urllib.request.Request(
            self.base + "/api/browser/status",
            method="OPTIONS",
            headers={"Origin": "chrome-extension://test-extension"},
        )
        with urllib.request.urlopen(request) as response:
            self.assertEqual(response.status, 204)
            self.assertEqual(response.headers["Access-Control-Allow-Origin"], "chrome-extension://test-extension")

    def test_source_subscription_api_updates_catalog_and_today(self):
        catalog, _ = self.request("/api/source-catalog")
        self.assertTrue(any(item["name"] == "BBC World" for item in catalog["sources"]))
        result, _ = self.request(
            "/api/subscriptions",
            "POST",
            {"target_type": "source", "target_value": "BBC World", "active": True},
        )
        self.assertTrue(result["active"])
        updated, _ = self.request("/api/source-catalog")
        bbc = next(item for item in updated["sources"] if item["name"] == "BBC World")
        self.assertTrue(bbc["subscribed"])
        today, _ = self.request("/api/today?exam=IELTS")
        self.assertIn("lanes", today)
        self.assertGreaterEqual(today["subscription_count"], 1)

    def test_content_hub_api_exposes_simple_product_categories(self):
        payload, _ = self.request("/api/content-hubs")
        self.assertEqual([item["label"] for item in payload["hubs"]], [
            "新闻", "观点", "研究", "科学与自然", "文化与生活", "影视与听力", "小说与图书",
        ])
        catalog, _ = self.request("/api/source-catalog")
        reuters = next(item for item in catalog["sources"] if item["name"] == "Reuters")
        self.assertFalse(reuters["automatic"])
        self.assertEqual(reuters["hub"], "news")
        self.assertEqual(reuters["access_method"], "摘要与原站")
        self.assertIn("rights_status", reuters)

    def test_today_api_accepts_learning_mode(self):
        today, _ = self.request("/api/today?exam=IELTS&mode=interest")
        self.assertEqual(today["mode"], "interest")
        self.assertTrue(any(lane["label"] == "15 分钟沉浸" for lane in today["lanes"]))

    def test_feed_status_api_exposes_scheduler_and_source_health(self):
        status, _ = self.request("/api/feeds/status")
        self.assertIn("refreshing", status)
        self.assertIn("due", status)
        self.assertGreaterEqual(status["interval_hours"], 1)
        self.assertTrue(status["sources"])
        self.assertTrue(all("consecutive_failures" in source for source in status["sources"]))

    def test_learner_settings_shape_daily_plan_and_goal_context(self):
        saved, _ = self.request(
            "/api/learner-settings",
            "POST",
            {
                "daily_minutes": 30,
                "daily_tasks": ["reading", "practice", "vocabulary"],
                "short_goal": "Improve IELTS matching information",
                "short_goal_date": "2026-08-01",
                "long_goal": "IELTS reading 7.0",
                "long_goal_date": "2026-10-01",
                "recommendations_enabled": True,
            },
        )
        self.assertEqual(saved["settings"]["daily_minutes"], 30)
        loaded, _ = self.request("/api/learner-settings")
        self.assertEqual(loaded["settings"], saved["settings"])
        today, _ = self.request("/api/today?exam=IELTS&mode=exam")
        self.assertEqual(today["plan"]["minutes"], 30)
        self.assertEqual(today["goals"]["short"], "Improve IELTS matching information")
        self.assertTrue(all("对应当前目标" in lane["reason"] for lane in today["lanes"]))
        disabled, _ = self.request(
            "/api/learner-settings",
            "POST",
            {**saved["settings"], "recommendations_enabled": False},
        )
        self.assertFalse(disabled["settings"]["recommendations_enabled"])
        generic, _ = self.request("/api/today?exam=IELTS&mode=exam")
        self.assertTrue(all(lane["reason"] == "通用内容安排" for lane in generic["lanes"]))

    def test_daily_plan_executes_manual_queue_and_automatic_progress(self):
        with server.db() as conn:
            conn.execute("DELETE FROM daily_plan_items")
            conn.execute("DELETE FROM daily_plan_progress")

        saved, _ = self.request(
            "/api/learner-settings",
            "POST",
            {
                "daily_minutes": 30,
                "daily_tasks": ["reading", "practice", "review", "vocabulary"],
                "daily_targets": {"reading": 2, "practice": 2, "review": 1, "vocabulary": 1},
            },
        )
        self.assertEqual(saved["settings"]["daily_targets"]["reading"], 2)

        manual, _ = self.request(
            "/api/daily-plan/progress", "POST", {"task": "reading", "completed_count": 1}
        )
        reading = next(item for item in manual["plan"]["tasks"] if item["task"] == "reading")
        self.assertEqual(reading["completed"], 1)

        with server.db() as conn:
            article_id = conn.execute("SELECT id FROM articles ORDER BY id LIMIT 1").fetchone()[0]
        payload = {
            "task": "reading",
            "item_type": "article",
            "item_id": article_id,
            "title": "Daily reading",
        }
        self.request("/api/daily-plan/items", "POST", payload)
        duplicate, _ = self.request("/api/daily-plan/items", "POST", payload)
        self.assertEqual(len(duplicate["plan"]["items"]), 1)
        item_id = duplicate["plan"]["items"][0]["id"]
        completed, _ = self.request(f"/api/daily-plan/items/{item_id}/complete", "POST", {})
        repeated, _ = self.request(f"/api/daily-plan/items/{item_id}/complete", "POST", {})
        reading = next(item for item in repeated["plan"]["tasks"] if item["task"] == "reading")
        self.assertEqual(reading["completed"], 2)
        self.assertTrue(completed["plan"]["items"][0]["completed"])

        card, _ = self.request(
            "/api/cards", "POST", {"term": "daily-loop-lexeme", "kind": "word", "context": "A test context."}
        )
        self.assertTrue(card["created"])

        article, _ = self.request(
            "/api/articles",
            "POST",
            {"title": "Daily plan practice", "body": server.SAMPLE_ARTICLE, "source": "manual"},
        )
        generated, _ = self.request(
            f"/api/articles/{article['article']['id']}/quizzes",
            "POST",
            {"mode": "reading", "style": "IELTS", "question_type": "tfng"},
        )
        quiz = generated["quizzes"][0]
        wrong_answer = next(option for option in quiz["options"] if option != quiz["answer"])
        self.request("/api/attempts", "POST", {"quiz_id": quiz["id"], "answer": wrong_answer})
        mistakes, _ = self.request("/api/mistakes")
        mistake = next(item for item in mistakes["mistakes"] if item["quiz_id"] == quiz["id"])
        first_solve, _ = self.request(f"/api/mistakes/{mistake['id']}/solve", "POST", {})
        second_solve, _ = self.request(f"/api/mistakes/{mistake['id']}/solve", "POST", {})
        self.assertEqual(first_solve["points"], 5)
        self.assertEqual(second_solve["points"], 0)

        session, _ = self.request(
            "/api/practice-sessions",
            "POST",
            {
                "session_mode": "mock",
                "elapsed_seconds": 30,
                "answers": [{"quiz_id": quiz["id"], "answer": quiz["answer"], "confidence": 3}],
            },
        )
        self.assertEqual(session["session"]["answered_count"], 1)
        plan, _ = self.request("/api/daily-plan")
        counts = {item["task"]: item["completed"] for item in plan["plan"]["tasks"]}
        self.assertEqual(counts, {"reading": 2, "practice": 1, "review": 1, "vocabulary": 1})
        self.assertGreater(plan["plan"]["remaining_minutes"], 0)

        finished, _ = self.request(
            "/api/daily-plan/progress", "POST", {"task": "practice", "completed_count": 2}
        )
        self.assertTrue(finished["plan"]["completed"])
        self.assertEqual(finished["plan"]["remaining_minutes"], 0)
        self.assertEqual(finished["plan"]["summary"], "今日计划已完成")

    def test_ielts_generation_and_wrong_answer_record_skill_and_error(self):
        created, _ = self.request(
            "/api/articles",
            "POST",
            {"title": "IELTS evidence test", "body": server.SAMPLE_ARTICLE, "source": "manual"},
        )
        generated, _ = self.request(
            f"/api/articles/{created['article']['id']}/quizzes",
            "POST",
            {"mode": "reading", "style": "IELTS", "question_type": "tfng"},
        )
        quiz = generated["quizzes"][0]
        self.assertEqual(quiz["question_type"], "tfng")
        self.assertTrue(quiz["skill"])
        self.assertTrue(quiz["validation"]["valid"])
        attempt, _ = self.request(
            "/api/attempts", "POST", {"quiz_id": quiz["id"], "answer": "NOT GIVEN", "confidence": 3}
        )
        self.assertFalse(attempt["correct"])
        self.assertEqual(attempt["confidence"], 3)
        self.assertEqual(attempt["error_type"], "一致与未提及混淆")
        mistakes, _ = self.request("/api/mistakes")
        saved = next(item for item in mistakes["mistakes"] if item["quiz_id"] == quiz["id"])
        self.assertEqual(saved["skill"], quiz["skill"])
        self.assertEqual(saved["error_type"], attempt["error_type"])
        next_set, _ = self.request("/api/practice/next-set", "POST", {"style": "IELTS", "limit": 5})
        self.assertTrue(next_set["quizzes"])
        self.assertLessEqual(len(next_set["quizzes"]), 5)
        self.assertIn(attempt["error_type"], next_set["focus"])
        focused, _ = self.request(
            "/api/practice/next-set",
            "POST",
            {"style": "IELTS", "limit": 5, "question_type": "tfng", "error_type": attempt["error_type"]},
        )
        self.assertEqual(focused["filters"], {"question_type": "tfng", "error_type": attempt["error_type"]})
        self.assertTrue(all(item["question_type"] == "tfng" for item in focused["quizzes"]))

    def test_toefl_generation_attempt_and_remedial_items_stay_exam_specific(self):
        created, _ = self.request(
            "/api/articles",
            "POST",
            {"title": "TOEFL evidence test", "body": server.SAMPLE_ARTICLE, "source": "manual"},
        )
        generated, _ = self.request(
            f"/api/articles/{created['article']['id']}/quizzes",
            "POST",
            {"mode": "reading", "style": "TOEFL", "question_type": "simplification"},
        )
        quiz = generated["quizzes"][0]
        self.assertEqual(quiz["generation_source"], "toefl-rule-v2")
        wrong_answer = next(option for option in quiz["options"] if option != quiz["answer"])
        attempt, _ = self.request(
            "/api/attempts",
            "POST",
            {"quiz_id": quiz["id"], "answer": wrong_answer, "confidence": 2},
        )
        self.assertEqual(attempt["error_type"], "关键信息遗漏或逻辑关系改变")
        mistakes, _ = self.request("/api/mistakes")
        mistake = next(item for item in mistakes["mistakes"] if item["quiz_id"] == quiz["id"])
        similar, _ = self.request(f"/api/mistakes/{mistake['id']}/similar", "POST", {"count": 3})
        self.assertTrue(similar["quizzes"])
        self.assertTrue(all(item["style"] == "TOEFL" for item in similar["quizzes"]))
        self.assertTrue(all(item["question_type"] == "simplification" for item in similar["quizzes"]))
        self.assertTrue(all(item["parent_mistake_id"] == mistake["id"] for item in similar["quizzes"]))
        self.assertTrue(all(item["remedial_level"] >= 1 for item in similar["quizzes"]))

    def test_toefl_advanced_types_are_exposed_and_support_remedial_flow(self):
        catalog, _ = self.request("/api/exam-types?style=TOEFL")
        ids = {item["id"] for item in catalog["types"]}
        self.assertTrue({"complete-words", "negative-factual", "rhetorical-purpose", "insertion", "prose-summary"}.issubset(ids))

        created, _ = self.request(
            "/api/articles",
            "POST",
            {"title": "TOEFL insertion flow", "body": server.SAMPLE_ARTICLE, "source": "manual"},
        )
        generated, _ = self.request(
            f"/api/articles/{created['article']['id']}/quizzes",
            "POST",
            {"mode": "reading", "style": "TOEFL", "question_type": "insertion"},
        )
        quiz = generated["quizzes"][0]
        wrong_answer = next(option for option in quiz["options"] if option != quiz["answer"])
        attempt, _ = self.request(
            "/api/attempts", "POST", {"quiz_id": quiz["id"], "answer": wrong_answer, "confidence": 2}
        )
        self.assertEqual(attempt["error_type"], "指代或篇章衔接判断错误")
        mistakes, _ = self.request("/api/mistakes")
        mistake = next(item for item in mistakes["mistakes"] if item["quiz_id"] == quiz["id"])
        similar, _ = self.request(f"/api/mistakes/{mistake['id']}/similar", "POST", {"count": 3})
        self.assertTrue(similar["quizzes"])
        self.assertTrue(all(item["question_type"] == "insertion" for item in similar["quizzes"]))

    def test_complete_words_persists_metadata_and_saves_wrong_word_for_review(self):
        created, _ = self.request(
            "/api/articles",
            "POST",
            {"title": "TOEFL complete words", "body": server.SAMPLE_ARTICLE, "source": "manual"},
        )
        generated, _ = self.request(
            f"/api/articles/{created['article']['id']}/quizzes",
            "POST",
            {"mode": "cloze", "style": "TOEFL", "question_type": "complete-words"},
        )
        quiz = generated["quizzes"][0]
        loaded, _ = self.request(
            f"/api/quizzes?article_id={created['article']['id']}&style=TOEFL&question_type=complete-words"
        )
        persisted = next(item for item in loaded["quizzes"] if item["id"] == quiz["id"])
        self.assertEqual(persisted["target_word"], quiz["target_word"])
        self.assertEqual(persisted["masked_text"], quiz["masked_text"])
        self.assertFalse(persisted["official_equivalence"])

        partial = quiz["answer"][: max(2, (len(quiz["answer"]) + 1) // 2)]
        attempt, _ = self.request(
            "/api/attempts", "POST", {"quiz_id": quiz["id"], "answer": partial, "confidence": 2}
        )
        self.assertEqual(attempt["error_type"], "只填写了已知部分或单词未补完整")
        self.request("/api/attempts", "POST", {"quiz_id": quiz["id"], "answer": partial, "confidence": 1})
        cards, _ = self.request("/api/cards")
        matching_cards = [item for item in cards["cards"] if item["term"].casefold() == quiz["answer"].casefold()]
        self.assertEqual(len(matching_cards), 1)
        saved = matching_cards[0]
        self.assertEqual(saved["context"], quiz["evidence"])
        self.assertIn("Complete the Words", saved["note"])

    def test_mock_session_scores_unanswered_items_and_persists_diagnosis(self):
        created, _ = self.request(
            "/api/articles",
            "POST",
            {"title": "IELTS mock session", "body": server.SAMPLE_ARTICLE, "source": "manual"},
        )
        generated, _ = self.request(
            f"/api/articles/{created['article']['id']}/quizzes",
            "POST",
            {"mode": "reading", "style": "IELTS", "question_type": "tfng"},
        )
        quizzes = generated["quizzes"]
        submitted, _ = self.request(
            "/api/practice-sessions",
            "POST",
            {
                "session_mode": "mock",
                "elapsed_seconds": 95,
                "answers": [
                    {"quiz_id": quizzes[0]["id"], "answer": quizzes[0]["answer"], "confidence": 3},
                    {"quiz_id": quizzes[1]["id"], "answer": "", "confidence": 1},
                    {"quiz_id": quizzes[2]["id"], "answer": "TRUE" if quizzes[2]["answer"] != "TRUE" else "FALSE", "confidence": 2},
                ],
            },
        )
        session = submitted["session"]
        self.assertEqual(session["session_mode"], "mock")
        self.assertEqual(session["question_count"], 3)
        self.assertEqual(session["answered_count"], 2)
        self.assertEqual(session["correct_count"], 1)
        self.assertEqual(session["elapsed_seconds"], 95)
        self.assertEqual(session["score"], 33)
        self.assertEqual(session["error_summary"]["未作答"], 1)
        self.assertEqual(session["confidence_summary"]["确定"], {"total": 1, "correct": 1})
        self.assertEqual(submitted["results"][0]["confidence"], 3)
        self.assertEqual(len(submitted["results"]), 3)
        self.assertTrue(all("explanation" in result for result in submitted["results"]))
        history, _ = self.request("/api/practice-sessions")
        self.assertEqual(history["sessions"][0]["id"], session["id"])
        with server.db() as conn:
            linked = conn.execute(
                "SELECT COUNT(*) FROM attempts WHERE session_id = ?", (session["id"],)
            ).fetchone()[0]
        self.assertEqual(linked, 3)

    def test_practice_attempts_are_archived_with_detail_and_analytics(self):
        baseline, _ = self.request("/api/practice/analytics?style=TOEFL")
        created, _ = self.request(
            "/api/articles",
            "POST",
            {"title": "TOEFL history", "body": server.SAMPLE_ARTICLE, "source": "manual"},
        )
        generated, _ = self.request(
            f"/api/articles/{created['article']['id']}/quizzes",
            "POST",
            {"mode": "reading", "style": "TOEFL", "question_type": "factual"},
        )
        first, second = generated["quizzes"][:2]
        correct, _ = self.request(
            "/api/attempts",
            "POST",
            {"quiz_id": first["id"], "answer": first["answer"], "confidence": 3},
        )
        wrong_answer = next(option for option in second["options"] if option != second["answer"])
        wrong, _ = self.request(
            "/api/attempts",
            "POST",
            {"quiz_id": second["id"], "answer": wrong_answer, "confidence": 2},
        )
        archived, _ = self.request(
            "/api/practice-sessions/record",
            "POST",
            {
                "attempt_ids": [correct["attempt_id"], wrong["attempt_id"]],
                "question_count": 3,
                "elapsed_seconds": 120,
            },
        )
        session = archived["session"]
        self.assertEqual(session["session_mode"], "practice")
        self.assertEqual(session["question_count"], 3)
        self.assertEqual(session["answered_count"], 2)
        self.assertEqual(session["correct_count"], 1)
        self.assertEqual(session["error_summary"]["未作答"], 1)
        self.assertEqual(len(archived["attempts"]), 2)
        listed, _ = self.request("/api/practice-sessions?style=TOEFL")
        self.assertEqual(listed["sessions"][0]["id"], session["id"])
        detail, _ = self.request(f"/api/practice-sessions/{session['id']}")
        self.assertEqual(detail["session"]["article_title"], "TOEFL history")
        analytics, _ = self.request("/api/practice/analytics?style=TOEFL")
        self.assertEqual(analytics["summary"]["attempts"], baseline["summary"]["attempts"] + 2)
        self.assertEqual(analytics["summary"]["correct"], baseline["summary"]["correct"] + 1)
        self.assertTrue(analytics["skills"])
        self.assertTrue(analytics["recommendation"]["question_type"])

    def test_exam_resources_expose_rights_and_user_import_is_labeled(self):
        resources, _ = self.request("/api/exam-resources?exam=IELTS")
        self.assertTrue(resources["resources"])
        self.assertTrue(all(item["rights_status"] == "link_only" for item in resources["resources"]))
        imported, _ = self.request(
            "/api/exam-resources",
            "POST",
            {
                "title": "My licensed IELTS paper",
                "exam": "IELTS",
                "year": 2022,
                "provider": "Personal archive",
                "description": "User supplied for private practice",
            },
        )
        self.assertEqual(imported["resource"]["resource_type"], "user_import")
        self.assertEqual(imported["resource"]["rights_status"], "user_provided")
        kaoyan, _ = self.request("/api/exam-resources?exam=KAOYAN")
        self.assertTrue(any(item["provider"] == "CHSI / 研招网" for item in kaoyan["resources"]))

    def test_ielts_full_mock_paper_has_three_sections_and_forty_questions(self):
        paragraph = (
            "Researchers examine how public policy changes communities and how evidence shapes practical decisions. "
            "The study compares local responses, records measurable outcomes, and identifies limits that future work must address."
        )
        body = "\n\n".join(f"{paragraph} Paragraph {index} adds a different example about education, health, and technology." for index in range(1, 6))
        for index in range(3):
            self.request(
                "/api/articles",
                "POST",
                {"title": f"Full paper passage {index + 1}", "body": body, "source": "manual"},
            )
        generated, _ = self.request("/api/exam-papers/generate", "POST", {"exam": "IELTS"})
        paper = generated["paper"]
        self.assertEqual(paper["paper_type"], "full_mock")
        self.assertEqual(paper["source_class"], "system_simulation")
        self.assertEqual(paper["question_count"], 40)
        self.assertEqual([len(section["quizzes"]) for section in paper["sections"]], [13, 13, 14])
        self.assertTrue(all(quiz["validation"]["valid"] for section in paper["sections"] for quiz in section["quizzes"]))

    def test_article_one_click_translation_uses_aligned_cached_paragraphs(self):
        body = "First paragraph explains the evidence.\n\nSecond paragraph states the conclusion."
        created, _ = self.request(
            "/api/articles",
            "POST",
            {"title": "Bilingual test", "body": body, "source": "manual"},
        )
        source_segments = ["First paragraph explains the evidence.", "Second paragraph states the conclusion."]
        translated_segments = ["第一段解释证据。", "第二段陈述结论。"]
        with server.db() as conn:
            for source, translated in zip(source_segments, translated_segments):
                digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
                conn.execute(
                    """INSERT OR REPLACE INTO translation_cache
                       (text_hash, source_lang, target_lang, provider, source_text, translated_text, created_at)
                       VALUES (?, 'EN', 'ZH-HANS', 'deepl', ?, ?, ?)""",
                    (digest, source, translated, server.utc_now()),
                )
        result, _ = self.request(
            f"/api/articles/{created['article']['id']}/translate",
            "POST",
            {"exam": "IELTS"},
        )
        self.assertTrue(result["cached"])
        self.assertEqual(result["translated_segments"], translated_segments)
        self.assertEqual(result["article"]["translation_zh"], "\n\n".join(translated_segments))
        reused, _ = self.request(
            f"/api/articles/{created['article']['id']}/translate",
            "POST",
            {"exam": "IELTS"},
        )
        self.assertEqual(reused["provider"], "saved")
        self.assertTrue(reused["cached"])

    def test_card_api_marks_multiword_terms_as_phrases(self):
        result, _ = self.request(
            "/api/cards",
            "POST",
            {"term": "meaningful control", "context": "People need meaningful control over their data."},
        )
        self.assertEqual(result["card"]["kind"], "phrase")

    def test_saving_same_term_updates_existing_card(self):
        term = "contextual vocabulary"
        first, _ = self.request(
            "/api/cards", "POST", {"term": term, "context": "The first context."}
        )
        second, _ = self.request(
            "/api/cards", "POST", {"term": term.upper(), "context": "A better context from the article."}
        )
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["card"]["id"], second["card"]["id"])
        self.assertEqual(second["card"]["context"], "A better context from the article.")
        with server.db() as conn:
            count = conn.execute("SELECT COUNT(*) FROM cards WHERE lower(term) = lower(?)", (term,)).fetchone()[0]
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
