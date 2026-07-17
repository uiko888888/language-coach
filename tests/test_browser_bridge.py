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

    def test_today_api_accepts_learning_mode(self):
        today, _ = self.request("/api/today?exam=IELTS&mode=interest")
        self.assertEqual(today["mode"], "interest")
        self.assertTrue(any(lane["label"] == "15 分钟沉浸" for lane in today["lanes"]))

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
            "/api/attempts", "POST", {"quiz_id": quiz["id"], "answer": "NOT GIVEN"}
        )
        self.assertFalse(attempt["correct"])
        self.assertEqual(attempt["error_type"], "一致与未提及混淆")
        mistakes, _ = self.request("/api/mistakes")
        saved = next(item for item in mistakes["mistakes"] if item["quiz_id"] == quiz["id"])
        self.assertEqual(saved["skill"], quiz["skill"])
        self.assertEqual(saved["error_type"], attempt["error_type"])

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
                    {"quiz_id": quizzes[0]["id"], "answer": quizzes[0]["answer"]},
                    {"quiz_id": quizzes[1]["id"], "answer": ""},
                    {"quiz_id": quizzes[2]["id"], "answer": "TRUE" if quizzes[2]["answer"] != "TRUE" else "FALSE"},
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
        self.assertEqual(len(submitted["results"]), 3)
        self.assertTrue(all("explanation" in result for result in submitted["results"]))
        history, _ = self.request("/api/practice-sessions")
        self.assertEqual(history["sessions"][0]["id"], session["id"])
        with server.db() as conn:
            linked = conn.execute(
                "SELECT COUNT(*) FROM attempts WHERE session_id = ?", (session["id"],)
            ).fetchone()[0]
        self.assertEqual(linked, 3)

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
