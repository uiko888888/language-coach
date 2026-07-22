import hashlib
import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from backend import fsrs_adapter, server
from tests.test_private_dictionaries import build_stardict


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

    def test_private_stardict_api_imports_manages_and_removes_only_the_index(self):
        source_dir = Path(self.temp_dir.name) / "stardict-api"
        source_dir.mkdir(exist_ok=True)
        ifo = build_stardict(source_dir, [("keen", "adj. eager; 热切的"), ("zeal", "n. enthusiasm; 热忱")])
        payload = {"path": str(ifo), "name": "API StarDict", "priority": 12, "kind": "bilingual_dictionary"}
        with self.assertRaises(urllib.error.HTTPError) as unauthorized:
            self.request("/api/private-dictionaries/stardict", "POST", payload)
        self.assertEqual(unauthorized.exception.code, 401)
        unauthorized.exception.close()
        imported, _ = self.request("/api/private-dictionaries/stardict", "POST", payload, token=self.token)
        source = imported["source"]
        self.assertEqual(source["status"], "ready")
        lookup, _ = self.request("/api/lexicon/search?q=keen")
        self.assertTrue(any(item.get("source_name") == "API StarDict" for item in lookup["results"]))
        updated, _ = self.request(
            f"/api/private-dictionaries/{source['id']}", "POST",
            {"enabled": False, "priority": 42}, token=self.token,
        )
        self.assertFalse(updated["source"]["enabled"])
        self.assertEqual(updated["source"]["priority"], 42)
        removed, _ = self.request(f"/api/private-dictionaries/{source['id']}", "DELETE", token=self.token)
        self.assertTrue(removed["removed"])
        self.assertTrue(ifo.exists())

    def test_lexicon_history_tracks_full_queries_and_can_be_cleared(self):
        self.request("/api/lexicon/history/clear", "POST", {})
        self.request("/api/lexicon/search?q=inspect")
        empty, _ = self.request("/api/lexicon/history")
        self.assertEqual(empty["recent"], [])
        result, _ = self.request("/api/lexicon/search?q=inspeckt&track=1")
        self.assertIn("inspect", result["suggestions"])
        history, _ = self.request("/api/lexicon/history")
        self.assertEqual(history["recent"][0]["query"], "inspeckt")
        cleared, _ = self.request("/api/lexicon/history/clear", "POST", {})
        self.assertTrue(cleared["cleared"])
        self.assertEqual(cleared["recent"], [])

    def test_lexicon_compare_returns_reviewed_boundaries_and_evidence_fallback(self):
        single, _ = self.request("/api/lexicon/search?q=cordial")
        self.assertEqual(single["results"][0]["learning_profile"]["meaning_zh"], "热情友好的；诚恳而有礼的")
        curated, _ = self.request("/api/lexicon/compare?q=cordial%2C%20keen%2C%20zeal")
        self.assertTrue(curated["reviewed"])
        self.assertEqual([item["term"] for item in curated["items"]], ["cordial", "keen", "zeal"])
        self.assertEqual(curated["items"][2]["pos"], "noun")
        fallback, _ = self.request("/api/lexicon/compare?q=happy%2C%20glad")
        self.assertFalse(fallback["reviewed"])
        with self.assertRaises(urllib.error.HTTPError) as invalid:
            self.request("/api/lexicon/compare?q=keen")
        self.assertEqual(invalid.exception.code, 400)
        invalid.exception.close()

        catalog, _ = self.request("/api/lexicon/comparisons")
        self.assertEqual(len(catalog["groups"]), 45)
        self.assertTrue(any(group["query"].startswith("compose, comprise") for group in catalog["groups"]))
        self.assertTrue(any(group["confusion_type"] == "lookalike" for group in catalog["groups"]))

    def test_review_api_rates_and_undoes_with_daily_progress(self):
        created, _ = self.request("/api/cards", "POST", {
            "term": "review contract phrase", "kind": "phrase", "context": "A review contract should be reversible.",
        })
        with server.db() as conn:
            review_item = conn.execute(
                "SELECT * FROM review_items WHERE item_type = 'card' AND item_id = ?", (created["card"]["id"],)
            ).fetchone()
            baseline = conn.execute(
                "SELECT completed_count FROM daily_plan_progress WHERE day = ? AND task = 'review'",
                (server.current_plan_day(),),
            ).fetchone()
            baseline_count = baseline[0] if baseline else 0
        queue, _ = self.request("/api/reviews?kind=phrase&limit=100")
        self.assertTrue(any(item["id"] == review_item["id"] for item in queue["items"]))
        self.assertEqual(queue["scheduler"]["fsrs"], fsrs_adapter.enabled())

        rated, _ = self.request(f"/api/reviews/{review_item['id']}/rate", "POST", {
            "rating": "good", "kind": "phrase",
        })
        self.assertTrue(rated["interval"])
        with server.db() as conn:
            scheduled = conn.execute("SELECT * FROM review_items WHERE id = ?", (review_item["id"],)).fetchone()
            progress = conn.execute(
                "SELECT completed_count FROM daily_plan_progress WHERE day = ? AND task = 'review'",
                (server.current_plan_day(),),
            ).fetchone()[0]
        self.assertIn(scheduled["state"], {"learning", "review", "relearning"})
        self.assertEqual(progress, baseline_count + 1)
        cards, _ = self.request("/api/cards")
        scheduled_card = next(item for item in cards["cards"] if item["id"] == created["card"]["id"])
        self.assertEqual(scheduled_card["review_state"], scheduled["state"])

        undone, _ = self.request("/api/reviews/undo", "POST", {"kind": "phrase"})
        self.assertEqual(undone["review_item_id"], review_item["id"])
        with server.db() as conn:
            restored = conn.execute("SELECT * FROM review_items WHERE id = ?", (review_item["id"],)).fetchone()
            progress = conn.execute(
                "SELECT completed_count FROM daily_plan_progress WHERE day = ? AND task = 'review'",
                (server.current_plan_day(),),
            ).fetchone()[0]
        self.assertEqual(restored["state"], "new")
        self.assertEqual(progress, baseline_count)

    def test_cards_preserve_two_senses_of_the_same_word_in_review(self):
        common = {
            "term": "cast", "kind": "word", "part_of_speech": "verb",
            "grammar_frame": "cast a vote", "lexical_source": "Open English WordNet",
        }
        first, _ = self.request("/api/cards", "POST", {
            **common, "sense_key": "wordnet:cast:throw", "meaning_zh": "投；掷",
            "concept_en": "throw something with force", "confusion_note": "不是演员阵容。",
        })
        second, _ = self.request("/api/cards", "POST", {
            **common, "sense_key": "wordnet:cast:actors", "part_of_speech": "noun",
            "meaning_zh": "演员阵容", "concept_en": "the actors in a production",
        })
        self.assertTrue(first["created"])
        self.assertTrue(second["created"])
        self.assertNotEqual(first["card"]["id"], second["card"]["id"])
        queue, _ = self.request("/api/reviews?kind=word&limit=100")
        senses = {item["sense_key"]: item for item in queue["items"] if item["front"] == "cast"}
        self.assertIn("wordnet:cast:throw", senses)
        self.assertIn("wordnet:cast:actors", senses)
        self.assertIn("throw something with force", senses["wordnet:cast:throw"]["answer"])
        self.assertEqual(senses["wordnet:cast:throw"]["confusion_note"], "不是演员阵容。")

    def test_complete_word_review_keeps_exam_attempts_separate_and_uses_fsrs_card(self):
        now = server.utc_now()
        with server.db() as conn:
            article_id = conn.execute("SELECT id FROM articles ORDER BY id LIMIT 1").fetchone()[0]
            wrong_quiz = conn.execute(
                """INSERT INTO quizzes
                   (article_id, style, mode, type, question_type, skill, difficulty, prompt, answer,
                    evidence, metadata_json, generation_source, created_at)
                   VALUES (?, 'TOEFL', 'reading', 'complete-words', 'complete-words', '语境拼写', 'B2',
                           'Complete: aggr____', 'aggregate', 'Solid particles are called aggregate.',
                           ?, 'toefl-2026-sim-v1', ?)""",
                (article_id, json.dumps({"masked_text": "Solid particles are called aggr____.", "visible_prefix": "aggr", "missing_count": 5}), now),
            ).lastrowid
            correct_quiz = conn.execute(
                """INSERT INTO quizzes
                   (article_id, style, mode, type, question_type, skill, difficulty, prompt, answer,
                    evidence, metadata_json, generation_source, created_at)
                   VALUES (?, 'TOEFL', 'reading', 'complete-words', 'complete-words', '语境拼写', 'B2',
                           'Complete: trans____', 'transport', 'Railways transport goods efficiently.',
                           ?, 'toefl-2026-sim-v1', ?)""",
                (article_id, json.dumps({"masked_text": "Railways trans____ goods efficiently.", "visible_prefix": "trans", "missing_count": 4}), now),
            ).lastrowid
            conn.execute(
                """INSERT INTO attempts (quiz_id, user_answer, correct, error_type, created_at)
                   VALUES (?, 'aggregat', 0, '拼写或词形错误', ?)""", (wrong_quiz, now),
            )
            conn.execute(
                """INSERT INTO attempts (quiz_id, user_answer, correct, error_type, created_at)
                   VALUES (?, 'transport', 1, '', ?)""", (correct_quiz, now),
            )

        wrong, _ = self.request("/api/complete-word-reviews?scope=wrong")
        self.assertEqual([item["quiz_id"] for item in wrong["items"]], [wrong_quiz])
        self.assertEqual(wrong["items"][0]["visible_prefix"], "aggr")
        self.assertTrue(wrong["items"][0]["due"])
        all_items, _ = self.request("/api/complete-word-reviews?scope=all")
        self.assertEqual({item["quiz_id"] for item in all_items["items"]}, {wrong_quiz, correct_quiz})
        searched, _ = self.request("/api/complete-word-reviews?scope=all&q=goods")
        self.assertEqual([item["quiz_id"] for item in searched["items"]], [correct_quiz])
        missing, _ = self.request("/api/complete-word-reviews?scope=all&q=not-present-anywhere")
        self.assertEqual(missing["items"], [])

        reviewed, _ = self.request(f"/api/complete-word-reviews/{wrong_quiz}/answer", "POST", {
            "answer": "aggregate", "elapsed_seconds": 8,
        })
        self.assertTrue(reviewed["correct"])
        with server.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM attempts WHERE quiz_id = ?", (wrong_quiz,)).fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM complete_word_review_attempts WHERE quiz_id = ?", (wrong_quiz,)).fetchone()[0], 1)
            card = conn.execute("SELECT * FROM cards WHERE source_quiz_id = ?", (wrong_quiz,)).fetchone()
            review_item = conn.execute("SELECT * FROM review_items WHERE item_type = 'card' AND item_id = ?", (card["id"],)).fetchone()
        rated, _ = self.request(f"/api/reviews/{review_item['id']}/rate", "POST", {
            "rating": "good", "kind": "complete-word",
        })
        self.assertTrue(rated["interval"])
        self.assertTrue(rated["queue"]["undo"]["available"])
        reviewed_catalog, _ = self.request("/api/complete-word-reviews?scope=all")
        self.assertTrue(reviewed_catalog["undo"]["available"])
        memory, _ = self.request("/api/reviews?kind=all&limit=100")
        self.assertFalse(any(item["kind"] == "complete-word" for item in memory["items"]))
        self.assertFalse(memory["undo"]["available"])
        undone, _ = self.request("/api/reviews/undo", "POST", {"kind": "complete-word"})
        self.assertEqual(undone["review_item_id"], review_item["id"])

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

    def test_single_paragraph_translation_persists_and_expires_when_source_changes(self):
        now = server.utc_now()
        with server.db() as conn:
            cursor = conn.execute(
                """INSERT INTO articles
                   (title, language, level, topic, source, content_status, content_type, body, created_at, updated_at)
                   VALUES ('Paragraph translation', 'en', 'B2', 'study', 'manual', 'full', 'explainer', ?, ?, ?)""",
                ("First paragraph.\n\nSecond paragraph.", now, now),
            )
            article_id = cursor.lastrowid
        translated_result = {
            "source_segments": ["Second paragraph."], "translated_segments": ["第二段。"],
            "provider": "test", "cached": False,
        }
        with patch("backend.server.translate_segments", return_value=translated_result):
            data, _ = self.request(
                f"/api/articles/{article_id}/paragraphs/1/translate", "POST", {"exam": "IELTS"}
            )
        self.assertEqual(data["paragraph_index"], 1)
        self.assertEqual(data["article"]["paragraph_translations"], ["", "第二段。"])
        self.assertFalse(data["article"]["translation_aligned"])
        loaded, _ = self.request(f"/api/articles/{article_id}?exam=IELTS")
        self.assertEqual(loaded["article"]["paragraph_translations"], ["", "第二段。"])
        with server.db() as conn:
            conn.execute(
                "UPDATE articles SET body = ?, updated_at = ? WHERE id = ?",
                ("First paragraph.\n\nChanged second paragraph.", server.utc_now(), article_id),
            )
        changed, _ = self.request(f"/api/articles/{article_id}?exam=IELTS")
        self.assertEqual(changed["article"]["paragraph_translations"], ["", ""])
        refreshed_result = {
            "source_segments": ["First paragraph.", "Changed second paragraph."],
            "translated_segments": ["第一段。", "更新后的第二段。"],
            "provider": "test", "cached": False,
        }
        with patch("backend.server.translate_segments", return_value=refreshed_result) as translate:
            refreshed, _ = self.request(f"/api/articles/{article_id}/translate", "POST", {"exam": "IELTS"})
        translate.assert_called_once_with(["First paragraph.", "Changed second paragraph."])
        self.assertEqual(refreshed["article"]["paragraph_translations"], ["第一段。", "更新后的第二段。"])

    def test_summary_article_is_rejected_by_server_training_gate(self):
        now = server.utc_now()
        with server.db() as conn:
            cursor = conn.execute(
                """INSERT INTO articles
                   (title, language, level, topic, source, source_url, content_status, content_type, body, created_at, updated_at)
                   VALUES ('Feed summary', 'en', 'B2', 'news', 'BBC World', 'https://example.test/summary',
                           'summary', 'report', 'A short source summary.', ?, ?)""",
                (now, now),
            )
            article_id = cursor.lastrowid
        try:
            self.request(
                f"/api/articles/{article_id}/quizzes",
                "POST",
                {"style": "IELTS", "mode": "mixed", "question_type": "tfng"},
            )
        except urllib.error.HTTPError as error:
            payload = json.load(error)
            self.assertEqual(error.code, 422)
            self.assertIn("RSS 摘要", payload["error"])
            self.assertFalse(payload["quality"]["training_eligible"])
            error.close()
        else:
            self.fail("Summary article bypassed the server training gate")

    def test_article_extraction_feedback_records_verdict_and_extractor_version(self):
        now = server.utc_now()
        with server.db() as conn:
            cursor = conn.execute(
                """INSERT INTO articles
                   (title, language, level, topic, source, content_status, content_type, body,
                    extraction_version, extraction_confidence, created_at, updated_at)
                   VALUES ('Reviewed article', 'en', 'B2', 'politics', 'The Conversation Politics',
                           'full', 'report', 'A clean article body.', 'conversation-rules-v1', 0.98, ?, ?)""",
                (now, now),
            )
            article_id = cursor.lastrowid
        payload, _ = self.request(
            f"/api/articles/{article_id}/extraction-feedback",
            "POST",
            {"verdict": "caption_in_body", "note": "Opening photo credit remains."},
        )
        self.assertEqual(payload["feedback"]["article_id"], article_id)
        self.assertEqual(payload["feedback"]["verdict"], "caption_in_body")
        self.assertEqual(payload["feedback"]["extraction_version"], "conversation-rules-v1")
        with server.db() as conn:
            stored = conn.execute(
                "SELECT * FROM article_extraction_feedback WHERE id = ?", (payload["feedback"]["id"],)
            ).fetchone()
        self.assertEqual(stored["note"], "Opening photo credit remains.")
        quality, _ = self.request("/api/extraction/quality")
        self.assertTrue(any(item["key"] == "jstor" for item in quality["adapters"]))
        self.assertGreaterEqual(quality["feedback_count"], 1)
        self.assertFalse(quality["classifier_readiness"]["ready"])
        self.assertIn("block_labels", quality["classifier_readiness"]["unmet"])

        annotation, _ = self.request(f"/api/articles/{article_id}/extraction-blocks")
        body_block = next(item for item in annotation["blocks"] if item["suggested_label"] == "body")
        self.assertEqual(annotation["summary"]["labeled"], 0)
        saved, _ = self.request(
            f"/api/articles/{article_id}/extraction-block-labels",
            "POST",
            {"block_hash": body_block["block_hash"], "label": "body"},
        )
        self.assertEqual(saved["summary"]["labeled"], 1)
        self.assertEqual(saved["summary"]["usable"], 1)
        quality, _ = self.request("/api/extraction/quality")
        self.assertGreaterEqual(quality["classifier_readiness"]["observed"]["block_labels"], 1)

    def test_representative_review_batch_tracks_time_and_confusion(self):
        source_versions = [
            ("The Conversation Politics", "conversation-rules-v2"),
            ("BBC World", "bbc-rss-v1"),
            ("Guardian World", "guardian-rss-v1"),
            ("JSTOR Daily", "jstor-rss-v1"),
        ]
        now = server.utc_now()
        with server.db() as conn:
            for index, (source, version) in enumerate(source_versions):
                conn.execute(
                    """INSERT INTO articles
                       (title, language, level, topic, source, content_status, content_type, body,
                        extraction_version, extraction_confidence, created_at, updated_at)
                       VALUES (?, 'en', 'B2', 'review', ?, 'full', 'report', ?, ?, 0.95, ?, ?)""",
                    (
                        f"Representative source {index}", source,
                        "A representative paragraph provides enough evidence for source extraction review.",
                        version, now, now,
                    ),
                )
        batch, _ = self.request(
            "/api/extraction/review-batches", "POST", {"target_size": 4, "force_new": True}
        )
        self.assertEqual(batch["summary"]["total"], 4)
        self.assertEqual({item["adapter"] for item in batch["items"]}, {"conversation", "bbc", "guardian", "jstor"})
        item = batch["items"][0]
        active, _ = self.request(
            f"/api/extraction/review-items/{item['id']}/activity", "POST", {"elapsed_seconds": 7}
        )
        active_item = next(value for value in active["items"] if value["id"] == item["id"])
        self.assertEqual(active_item["active_seconds"], 7)
        annotation, _ = self.request(f"/api/articles/{item['article_id']}/extraction-blocks")
        block = next(value for value in annotation["blocks"] if value["suggested_label"] == "body")
        saved, _ = self.request(
            f"/api/articles/{item['article_id']}/extraction-block-labels",
            "POST",
            {
                "block_hash": block["block_hash"], "label": "boilerplate",
                "batch_item_id": item["id"], "elapsed_seconds": 5,
            },
        )
        self.assertEqual(saved["summary"]["labeled"], 1)
        refreshed, _ = self.request(f"/api/extraction/review-batches/{batch['batch']['id']}")
        refreshed_item = next(value for value in refreshed["items"] if value["id"] == item["id"])
        self.assertEqual(refreshed_item["active_seconds"], 12)
        self.assertEqual(refreshed["analytics"]["corrected_suggestions"], 1)
        self.assertEqual(refreshed["analytics"]["confusion"][0]["suggested_label"], "body")
        self.assertEqual(refreshed["analytics"]["confusion"][0]["label"], "boilerplate")

    def test_contextual_output_loop_tracks_metrics_and_review(self):
        with server.db() as conn:
            article = conn.execute("SELECT * FROM articles WHERE source = 'seed'").fetchone()
            article_id = article["id"]
            conn.execute("DELETE FROM output_review_links")
            conn.execute("DELETE FROM output_attempts")
            conn.execute("DELETE FROM output_tasks")
            conn.execute("DELETE FROM output_task_sets")
            conn.execute("DELETE FROM article_reading_events WHERE article_id = ?", (article_id,))
            conn.execute("DELETE FROM daily_learning_metrics")

        generated, _ = self.request(f"/api/articles/{article_id}/output-tasks", "POST", {})
        self.assertEqual([task["task_type"] for task in generated["tasks"]], ["en_to_zh", "zh_to_en", "summary", "personal"])
        reconstruction = next(task for task in generated["tasks"] if task["task_type"] == "zh_to_en")
        submitted, _ = self.request(
            "/api/output-attempts", "POST",
            {
                "task_id": reconstruction["id"],
                "response": reconstruction["reference_text"],
                "elapsed_seconds": 42,
                "confidence": 2,
            },
        )
        attempt = submitted["attempt"]
        self.assertEqual(attempt["elapsed_seconds"], 42)
        self.assertTrue(all(check["passed"] for check in attempt["feedback"]["checks"]))
        self.assertGreaterEqual(next(item for item in submitted["plan"]["metrics"] if item["metric"] == "output_sentences")["value"], 1)

        reviewed, _ = self.request(
            f"/api/output-attempts/{attempt['id']}/self-review", "POST",
            {"ratings": {"information": 3, "naturalness": 2, "chunk_use": 2}, "note": "Check collocations."},
        )
        self.assertEqual(reviewed["attempt"]["self_review"]["information"], 3)
        saved, _ = self.request(f"/api/output-attempts/{attempt['id']}/save-review-item", "POST", {})
        self.assertEqual(saved["card"]["kind"], "phrase")
        self.assertEqual(saved["card"]["term"], reconstruction["target_chunks"][0])
        self.assertEqual(saved["card"]["context"], reconstruction["reference_text"])
        queue, _ = self.request("/api/reviews?kind=phrase&limit=100")
        self.assertTrue(any(item["item_id"] == saved["card"]["id"] for item in queue["items"]))

        first_read, _ = self.request(f"/api/articles/{article_id}/read", "POST", {})
        repeated_read, _ = self.request(f"/api/articles/{article_id}/read", "POST", {})
        self.assertTrue(first_read["recorded"])
        self.assertFalse(repeated_read["recorded"])
        reading_metric = next(item for item in repeated_read["plan"]["metrics"] if item["metric"] == "reading_words")
        self.assertEqual(reading_metric["value"], first_read["word_count"])

        history, _ = self.request("/api/output/history")
        self.assertGreaterEqual(history["summary"]["attempts"], 1)
        self.assertEqual(history["attempts"][0]["article_title"], article["title"])

    def test_semantic_feedback_contrast_and_custom_review_loop(self):
        with server.db() as conn:
            article = conn.execute("SELECT * FROM articles WHERE source = 'seed'").fetchone()
        generated, _ = self.request(f"/api/articles/{article['id']}/output-tasks", "POST", {})
        task = next(item for item in generated["tasks"] if item["task_type"] == "personal")
        submitted, _ = self.request("/api/output-attempts", "POST", {
            "task_id": task["id"],
            "response": f"I use {task['target_chunks'][0]} when I discuss research with classmates.",
            "confidence": 2,
        })
        attempt = submitted["attempt"]
        provider_result = {
            "provider": "openai-compatible",
            "model": "test-model",
            "prompt_version": "output-feedback-v1",
            "feedback": {
                "summary": "The idea is clear.",
                "dimensions": [
                    {"id": key, "label": key, "score": 4, "finding": "Clear", "suggestion": "Keep it concise", "evidence_quote": "", "evidence_origin": "none"}
                    for key in ("information", "collocation", "register", "coherence", "naturalness")
                ],
                "revised_response": "I use this expression when discussing research with classmates.",
                "boundary": "The suggestion is not a unique answer.",
            },
        }
        with patch.object(server, "request_semantic_feedback", return_value=provider_result):
            feedback_response, _ = self.request(
                f"/api/output-attempts/{attempt['id']}/semantic-feedback", "POST", {}
            )
        feedback = feedback_response["semantic_feedback"]
        self.assertEqual(len(feedback["feedback"]["dimensions"]), 5)
        reused, _ = self.request(f"/api/output-attempts/{attempt['id']}/semantic-feedback", "POST", {})
        self.assertTrue(reused["reused"])
        self.assertEqual(reused["semantic_feedback"]["id"], feedback["id"])
        decided, _ = self.request(f"/api/output-feedback/{feedback['id']}/decision", "POST", {
            "decision": "modify",
            "revised_response": "I use this expression when discussing research with classmates.",
        })
        self.assertEqual(decided["semantic_feedback"]["decision"]["decision"], "modify")

        custom, _ = self.request(f"/api/output-attempts/{attempt['id']}/review-items", "POST", {
            "term": "discuss research with classmates",
            "context": attempt["response_text"],
            "note": "My corrected output sentence",
        })
        self.assertEqual(custom["card"]["term"], "discuss research with classmates")
        self.assertEqual(custom["card"]["source_article_id"], article["id"])

        contrasts, _ = self.request("/api/output/contrasts?query=career")
        contrast = contrasts["contrasts"][0]
        self.assertEqual(contrast["slug"], "job-work-career")
        self.assertNotIn("answer_index", contrast)
        answer, _ = self.request(f"/api/output/contrasts/{contrast['slug']}/attempt", "POST", {"selected_index": 2})
        self.assertTrue(answer["correct"])
        self.assertEqual(answer["history"]["attempts"], 1)

        with server.db() as conn:
            persisted = conn.execute("SELECT response_text FROM output_attempts WHERE id = ?", (attempt["id"],)).fetchone()
        self.assertEqual(persisted["response_text"], attempt["response_text"])

    def test_local_speaking_recording_transcript_review_and_delete_loop(self):
        with server.db() as conn:
            article = conn.execute("SELECT * FROM articles WHERE source = 'seed'").fetchone()
        generated, _ = self.request(f"/api/articles/{article['id']}/speaking-tasks", "POST", {
            "duration_target": 30,
            "prep_seconds": 10,
        })
        self.assertEqual([task["task_type"] for task in generated["tasks"]], ["retell", "opinion", "chunk"])
        self.assertTrue(generated["tasks"][0]["evidence_eligible"])
        self.assertFalse(generated["tasks"][2]["evidence_eligible"])
        task = generated["tasks"][0]
        created, _ = self.request("/api/speaking-attempts", "POST", {
            "task_id": task["id"], "prep_seconds": 8,
        })
        attempt_id = created["attempt"]["id"]
        audio = b"test-webm-audio-payload"
        upload = urllib.request.Request(
            self.base + f"/api/speaking-attempts/{attempt_id}/audio",
            data=audio,
            method="POST",
            headers={"Content-Type": "audio/webm", "X-Audio-Duration": "31"},
        )
        with urllib.request.urlopen(upload) as response:
            uploaded = json.load(response)["attempt"]
        self.assertEqual(uploaded["duration_seconds"], 31)
        self.assertTrue(Path(server.speaking_audio_dir(), uploaded["audio_filename"]).is_file())
        with urllib.request.urlopen(self.base + uploaded["audio_url"]) as response:
            self.assertEqual(response.read(), audio)

        transcript_text = "The article explains privacy choices. Um I think clear consent matters matters for users."
        transcript, _ = self.request(f"/api/speaking-attempts/{attempt_id}/transcript", "POST", {"text": transcript_text})
        analysis = transcript["attempt"]["transcript_analysis"]
        self.assertGreater(analysis["words_per_minute"], 0)
        self.assertEqual(analysis["filler_count"], 1)
        self.assertEqual(analysis["immediate_repetitions"], 1)
        reviewed, _ = self.request(f"/api/speaking-attempts/{attempt_id}/self-review", "POST", {
            "ratings": {"content": 2, "coherence": 2, "fluency": 2, "chunk_use": 1, "grammar_impact": 2},
            "note": "Pause before the conclusion.",
            "stuck_expression": "give people meaningful control",
        })
        self.assertEqual(reviewed["attempt"]["self_review"]["stuck_expression"], "give people meaningful control")
        saved, _ = self.request(f"/api/speaking-attempts/{attempt_id}/review-items", "POST", {
            "term": "give people meaningful control", "context": transcript_text,
        })
        self.assertEqual(saved["card"]["kind"], "phrase")
        history, _ = self.request("/api/speaking/history")
        self.assertEqual(history["attempts"][0]["id"], attempt_id)
        plan, _ = self.request("/api/daily-plan")
        speaking_metric = next(item for item in plan["plan"]["metrics"] if item["metric"] == "speaking_seconds")
        self.assertGreaterEqual(speaking_metric["value"], 31)

        delete = urllib.request.Request(self.base + f"/api/speaking-attempts/{attempt_id}", method="DELETE")
        with urllib.request.urlopen(delete) as response:
            self.assertTrue(json.load(response)["deleted"])
        self.assertFalse(Path(server.speaking_audio_dir(), uploaded["audio_filename"]).exists())
        with self.assertRaises(urllib.error.HTTPError) as missing:
            urllib.request.urlopen(self.base + uploaded["audio_url"])
        self.assertEqual(missing.exception.code, 404)
        missing.exception.close()

    def test_representative_review_batch_does_not_persist_empty_batch(self):
        with sqlite3.connect(":memory:") as conn:
            conn.row_factory = sqlite3.Row
            conn.executescript(
                """CREATE TABLE articles (
                     id INTEGER PRIMARY KEY, source TEXT NOT NULL, extraction_version TEXT NOT NULL,
                     body TEXT NOT NULL, content_status TEXT NOT NULL, published_at TEXT NOT NULL
                   );
                   CREATE TABLE article_extraction_block_labels (
                     id INTEGER PRIMARY KEY, article_id INTEGER NOT NULL
                   );
                   CREATE TABLE article_extraction_feedback (
                     id INTEGER PRIMARY KEY, article_id INTEGER NOT NULL, verdict TEXT
                   );
                   CREATE TABLE article_extraction_review_batches (
                     id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                     target_size INTEGER NOT NULL, status TEXT NOT NULL,
                     created_at TEXT NOT NULL, completed_at TEXT NOT NULL DEFAULT ''
                   );"""
            )
            with self.assertRaisesRegex(ValueError, "No eligible"):
                server.create_extraction_review_batch(conn, 20)
            count = conn.execute("SELECT COUNT(*) FROM article_extraction_review_batches").fetchone()[0]
        self.assertEqual(count, 0)

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

    def test_deepl_verification_distinguishes_network_failure_from_rejected_key(self):
        unavailable = urllib.error.URLError(OSError("connection unavailable"))
        with patch.dict(server.os.environ, {"DEEPL_API_KEY": "test-key", "DEEPL_API_URL": "https://api-free.deepl.com/v2/translate"}), \
                patch("backend.server.urllib.request.urlopen", side_effect=[unavailable, unavailable]):
            status = server.verify_deepl_configuration()
        self.assertFalse(status["verified"])
        self.assertIn("当前网络无法连接", status["last_error"])
        self.assertIn("尚未验证 API Key", status["last_error"])
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
        with server.db() as conn:
            review_item = conn.execute(
                "SELECT * FROM review_items WHERE item_type = 'mistake' AND item_id = ?", (mistake["id"],)
            ).fetchone()
        self.assertIsNotNone(review_item)
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

    def test_active_practice_run_round_trip_and_explainable_prescription(self):
        created, _ = self.request(
            "/api/articles", "POST",
            {"title": "Persistent TEM8 run", "body": server.SAMPLE_ARTICLE, "source": "manual"},
        )
        generated, _ = self.request(
            f"/api/articles/{created['article']['id']}/quizzes", "POST",
            {"mode": "reading", "style": "TEM8", "question_type": "inference"},
        )
        quiz = generated["quizzes"][0]
        run_data, _ = self.request("/api/practice-runs", "POST", {
            "article_id": created["article"]["id"], "style": "TEM8", "question_type": "inference",
            "scope": "specialty", "session_mode": "practice", "quiz_ids": [quiz["id"]],
            "answers": {str(quiz["id"]): "draft"}, "confidence": {str(quiz["id"]): 2},
            "flagged": {str(quiz["id"]): True}, "answer_changes": {str(quiz["id"]): 1},
            "hint_used": {str(quiz["id"]): True}, "feedback": {}, "active_index": 0,
            "display_mode": "single", "elapsed_seconds": 37,
        })
        run = run_data["run"]
        active, _ = self.request("/api/practice-runs/active")
        self.assertEqual(active["run"]["id"], run["id"])
        self.assertEqual(active["run"]["elapsed_seconds"], 37)
        self.assertEqual(active["quizzes"][0]["id"], quiz["id"])
        run["answers"] = {str(quiz["id"]): quiz["answer"]}
        run["feedback"] = {str(quiz["id"]): {"correct": True}}
        run["quiz_ids"] = [quiz["id"]]
        updated, _ = self.request("/api/practice-runs", "POST", run)
        self.assertTrue(updated["run"]["feedback"][str(quiz["id"])]["correct"])

        wrong_answer = next(option for option in quiz["options"] if option != quiz["answer"])
        attempt_ids = []
        for answer, confidence, elapsed, changes, hint in (
            (wrong_answer, 3, 130, 2, True),
            (wrong_answer, 2, 110, 1, True),
            (quiz["answer"], 2, 95, 1, False),
        ):
            attempt, _ = self.request("/api/attempts", "POST", {
                "quiz_id": quiz["id"], "answer": answer, "confidence": confidence,
                "elapsed_seconds": elapsed, "answer_changes": changes, "hint_used": hint,
            })
            attempt_ids.append(attempt["attempt_id"])
        prescribed, _ = self.request("/api/practice/prescription?style=TEM8")
        prescription = prescribed["prescription"]
        self.assertEqual(prescription["status"], "ready")
        self.assertEqual(prescription["question_type"], "inference")
        self.assertEqual(prescription["sample_count"], 3)
        self.assertEqual(prescription["metrics"]["accuracy"], 33)
        self.assertEqual(prescription["unique_quiz_count"], 1)
        self.assertEqual(prescription["evidence_confidence"], "low")
        self.assertTrue(any("正确率" in reason for reason in prescription["reasons"]))

        archived, _ = self.request("/api/practice-sessions/record", "POST", {
            "attempt_ids": attempt_ids, "question_count": 3, "elapsed_seconds": 335,
        })
        completed, _ = self.request(f"/api/practice-runs/{run['id']}/complete", "POST", {
            "practice_session_id": archived["session"]["id"],
        })
        self.assertEqual(completed["run"]["status"], "completed")
        self.assertEqual(completed["run"]["practice_session_id"], archived["session"]["id"])
        active_after, _ = self.request("/api/practice-runs/active")
        self.assertIsNone(active_after["run"])

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
