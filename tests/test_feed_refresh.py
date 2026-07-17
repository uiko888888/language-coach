import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from backend import server


RSS = b"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel><title>Test Feed</title><item>
  <title>Evidence in public policy</title>
  <link>https://example.test/evidence</link>
  <guid>entry-001</guid>
  <pubDate>Fri, 17 Jul 2026 08:30:00 GMT</pubDate>
  <description>A public report explains how careful evidence can improve policy decisions for communities.</description>
</item></channel></rss>"""


class MockResponse:
    def __init__(self, body=b"", status=200, headers=None):
        self.body = body
        self.status = status
        self.headers = headers or {}

    def read(self, limit=-1):
        return self.body if limit < 0 else self.body[:limit]

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FeedRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        server.DB_PATH = Path(cls.temp_dir.name) / "feeds.sqlite"
        server.init_db()

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def setUp(self):
        with server.db() as conn:
            conn.execute("DELETE FROM feed_refresh_sources")
            conn.execute("DELETE FROM feed_refresh_runs")
            conn.execute("DELETE FROM articles WHERE source = 'Test Feed'")
            conn.execute("UPDATE feeds SET active = 0")
            conn.execute(
                """INSERT INTO feeds (name, url, language, level_hint, active, created_at)
                   VALUES ('Test Feed', 'https://example.test/feed.xml', 'en', 'B2', 1, ?)
                   ON CONFLICT(url) DO UPDATE SET active = 1, etag = '', last_modified = '',
                     last_attempt_at = '', last_success_at = '', consecutive_failures = 0, last_error = ''""",
                (server.utc_now(),),
            )

    def test_refresh_imports_publication_metadata_and_records_health(self):
        response = MockResponse(RSS, headers={"ETag": '"feed-v1"', "Last-Modified": "Fri, 17 Jul 2026 09:00:00 GMT"})
        with patch("backend.server.urllib.request.urlopen", return_value=response):
            result = server.fetch_feed_items(trigger_type="test")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["imported"], 1)
        with server.db() as conn:
            article = conn.execute("SELECT * FROM articles WHERE source = 'Test Feed'").fetchone()
            feed = conn.execute("SELECT * FROM feeds WHERE name = 'Test Feed'").fetchone()
            source_run = conn.execute("SELECT * FROM feed_refresh_sources ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(article["source_guid"], "entry-001")
        self.assertTrue(article["content_hash"])
        self.assertTrue(article["published_at"].startswith("2026-07-17T08:30:00"))
        self.assertEqual(feed["etag"], '"feed-v1"')
        self.assertEqual(feed["consecutive_failures"], 0)
        self.assertEqual(source_run["imported_count"], 1)
        self.assertFalse(server.feed_refresh_due())

    def test_conditional_refresh_handles_not_modified(self):
        with server.db() as conn:
            conn.execute("UPDATE feeds SET etag = '\"feed-v1\"', last_modified = 'yesterday' WHERE name = 'Test Feed'")
        captured = {}

        def respond(request, timeout=0):
            captured.update(dict(request.header_items()))
            return MockResponse(status=304)

        with patch("backend.server.urllib.request.urlopen", side_effect=respond):
            result = server.fetch_feed_items(trigger_type="test")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["imported"], 0)
        self.assertEqual(captured.get("If-none-match"), '"feed-v1"')
        self.assertEqual(captured.get("If-modified-since"), "yesterday")

    def test_guid_and_hash_fallbacks_are_idempotent(self):
        feed = {"name": "Test Feed", "language": "en", "level_hint": "B2"}
        base = {
            "title": "No stable URL", "link": "", "guid": "entry-guid", "body": "A stable body for identity.",
            "content_hash": "hash-one", "content_status": "summary", "content_type": "report", "published_at": "",
        }
        with server.db() as conn:
            self.assertEqual(server.upsert_feed_article(conn, feed, base, server.utc_now()), "imported")
            self.assertEqual(server.upsert_feed_article(conn, feed, {**base, "content_hash": "hash-two"}, server.utc_now()), "unchanged")
            hash_only = {**base, "guid": "", "content_hash": "hash-only", "body": "Another stable body."}
            self.assertEqual(server.upsert_feed_article(conn, feed, hash_only, server.utc_now()), "imported")
            self.assertEqual(server.upsert_feed_article(conn, feed, hash_only, server.utc_now()), "unchanged")
            count = conn.execute("SELECT COUNT(*) FROM articles WHERE source = 'Test Feed'").fetchone()[0]
        self.assertEqual(count, 2)

    def test_failure_updates_source_health_without_crashing_run(self):
        with patch("backend.server.urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            result = server.fetch_feed_items(trigger_type="test")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["errors"]), 1)
        status = server.feed_refresh_status()
        source = next(item for item in status["sources"] if item["name"] == "Test Feed")
        self.assertEqual(source["consecutive_failures"], 1)
        self.assertIn("offline", source["last_error"])
        self.assertFalse(server.feed_retry_ready(source, datetime.now(timezone.utc)))
        source["last_attempt_at"] = (datetime.now(timezone.utc) - timedelta(minutes=16)).isoformat()
        self.assertTrue(server.feed_retry_ready(source, datetime.now(timezone.utc)))


if __name__ == "__main__":
    unittest.main()
