import hashlib
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
