import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from backend import server
from backend.backups import create_backup, list_backups, restore_backup
from backend.migrations import (
    _article_semantic_blocks,
    _embedded_article_captions,
    _sanitize_feed_articles,
    _source_adapter_backfill,
    run_migrations,
)
from backend.versioning import API_VERSION, SCHEMA_VERSION


class MaintenanceTests(unittest.TestCase):
    def test_migration_registry_upgrades_legacy_columns_once(self):
        with sqlite3.connect(":memory:") as conn:
            conn.executescript(
                """
                CREATE TABLE articles (id INTEGER PRIMARY KEY, source TEXT, source_guid TEXT DEFAULT '', content_hash TEXT DEFAULT '');
                CREATE TABLE feeds (id INTEGER PRIMARY KEY);
                CREATE TABLE mistakes (id INTEGER PRIMARY KEY);
                CREATE TABLE quizzes (id INTEGER PRIMARY KEY);
                CREATE TABLE attempts (id INTEGER PRIMARY KEY);
                CREATE TABLE practice_sessions (id INTEGER PRIMARY KEY);
                CREATE TABLE cards (id INTEGER PRIMARY KEY);
                """
            )
            self.assertEqual(run_migrations(conn), SCHEMA_VERSION)
            self.assertEqual(run_migrations(conn), SCHEMA_VERSION)
            migrations = conn.execute("SELECT version, name FROM schema_migrations").fetchall()
            article_columns = {row[1] for row in conn.execute("PRAGMA table_info(articles)")}
            attempt_columns = {row[1] for row in conn.execute("PRAGMA table_info(attempts)")}
            mistake_columns = {row[1] for row in conn.execute("PRAGMA table_info(mistakes)")}
            practice_run_columns = {row[1] for row in conn.execute("PRAGMA table_info(practice_runs)")}
        self.assertEqual(len(migrations), 23)
        self.assertIn("translation_zh", article_columns)
        self.assertIn("content_status", article_columns)
        self.assertTrue({"elapsed_seconds", "answer_changes", "hint_used"}.issubset(attempt_columns))
        self.assertTrue({"remedial_attempts", "remedial_correct_streak", "mastery_source"}.issubset(mistake_columns))
        self.assertIn("visibility", article_columns)
        self.assertIn((21, "add private local dictionary index"), migrations)
        self.assertIn((22, "add lexical comparison review workflow"), migrations)
        self.assertEqual(migrations[-1][1], "add comparison boundary training")
        self.assertTrue({"author", "image_caption", "disclosure", "extraction_version"}.issubset(article_columns))
        self.assertTrue({"quiz_ids_json", "feedback_json", "elapsed_seconds", "status"}.issubset(practice_run_columns))

    def test_script_noise_repair_is_audited_and_clears_misaligned_translation(self):
        with sqlite3.connect(":memory:") as conn:
            conn.execute(
                """CREATE TABLE articles (
                     id INTEGER PRIMARY KEY, body TEXT NOT NULL, translation_zh TEXT NOT NULL,
                     content_hash TEXT NOT NULL, updated_at TEXT NOT NULL
                   )"""
            )
            clean = "A readable report explains policy evidence for local communities. " * 8
            dirty = clean + " GF_AJAX_POSTBACK = []; jQuery('#gform_wrapper_17').html(contents);"
            conn.execute("INSERT INTO articles VALUES (1, ?, '旧译文', 'old', '')", (dirty,))
            _sanitize_feed_articles(conn)
            article = conn.execute("SELECT * FROM articles WHERE id = 1").fetchone()
            repair = conn.execute("SELECT * FROM article_content_repairs WHERE article_id = 1").fetchone()
        self.assertNotIn("GF_AJAX_POSTBACK", article[1])
        self.assertEqual(article[2], "")
        self.assertIn("GF_AJAX_POSTBACK", repair[2])

    def test_conversation_migration_preserves_original_and_repairs_semantic_blocks(self):
        caption = (
            "Republican Rep. Ralph Norman discusses the Save America Act. "
            "The act is stuck between the U.\n\nS. House and Senate. J.\n\nScott Applewhite/AP Photo"
        )
        opening = "President Donald Trump’s obsession with election rules has returned to Congress."
        disclosure = (
            "SoRelle Wyckoff Gaynor does not work for, consult, own shares in or receive funding from "
            "any company or organization that would benefit from this article."
        )
        original = f"{caption} {opening}\n\nA second paragraph explains the proposal.\n\n{disclosure}"
        with sqlite3.connect(":memory:") as conn:
            conn.row_factory = sqlite3.Row
            conn.execute(
                """CREATE TABLE articles (
                     id INTEGER PRIMARY KEY, source TEXT NOT NULL, body TEXT NOT NULL,
                     translation_zh TEXT NOT NULL DEFAULT '', content_hash TEXT NOT NULL DEFAULT '',
                     updated_at TEXT NOT NULL DEFAULT ''
                   )"""
            )
            conn.execute(
                "INSERT INTO articles (id, source, body, translation_zh) VALUES (235, 'The Conversation Politics', ?, 'old')",
                (original,),
            )
            _article_semantic_blocks(conn)
            article = conn.execute("SELECT * FROM articles WHERE id = 235").fetchone()
            audit = conn.execute("SELECT * FROM article_extraction_audits WHERE article_id = 235").fetchone()
        self.assertTrue(article["body"].startswith(opening))
        self.assertNotIn("AP Photo", article["body"])
        self.assertNotIn("does not work for, consult", article["body"])
        self.assertEqual(article["author"], "SoRelle Wyckoff Gaynor")
        self.assertIn("U.S. House and Senate", article["image_caption"])
        self.assertEqual(article["translation_zh"], "")
        self.assertEqual(audit["original_body"], original)
        self.assertEqual(audit["extracted_body"], article["body"])

    def test_embedded_caption_migration_keeps_following_heading_and_body(self):
        caption = "House Majority Leader Steve Scalise speaks to reporters. Tom Brenner/AP Photo"
        paragraph = f"{caption} Legal and logistical hurdles The proposal would be expensive to implement."
        with sqlite3.connect(":memory:") as conn:
            conn.row_factory = sqlite3.Row
            conn.executescript(
                """CREATE TABLE articles (
                     id INTEGER PRIMARY KEY, source TEXT NOT NULL, body TEXT NOT NULL,
                     image_caption TEXT NOT NULL DEFAULT '', extraction_version TEXT NOT NULL DEFAULT '',
                     extraction_confidence REAL NOT NULL DEFAULT 0, extraction_notes_json TEXT NOT NULL DEFAULT '{}',
                     translation_zh TEXT NOT NULL DEFAULT '', content_hash TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT ''
                   );
                   CREATE TABLE article_extraction_audits (
                     id INTEGER PRIMARY KEY AUTOINCREMENT, article_id INTEGER NOT NULL, extraction_version TEXT NOT NULL,
                     original_body TEXT NOT NULL, extracted_body TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}',
                     created_at TEXT NOT NULL, UNIQUE(article_id, extraction_version)
                   );"""
            )
            conn.execute(
                "INSERT INTO articles (id, source, body, image_caption) VALUES (235, 'The Conversation Politics', ?, 'Opening caption')",
                (paragraph,),
            )
            _embedded_article_captions(conn)
            article = conn.execute("SELECT * FROM articles WHERE id = 235").fetchone()
            audit = conn.execute("SELECT * FROM article_extraction_audits WHERE article_id = 235").fetchone()
        self.assertEqual(article["body"], "Legal and logistical hurdles The proposal would be expensive to implement.")
        self.assertNotIn("AP Photo", article["body"])
        self.assertIn("Opening caption", article["image_caption"])
        self.assertIn("Tom Brenner/AP Photo", article["image_caption"])
        self.assertEqual(article["extraction_version"], "conversation-rules-v2")
        self.assertEqual(audit["original_body"], paragraph)

    def test_source_adapter_backfill_audits_jstor_cleanup(self):
        with sqlite3.connect(":memory:") as conn:
            conn.row_factory = sqlite3.Row
            conn.executescript(
                """
                CREATE TABLE articles (
                  id INTEGER PRIMARY KEY, title TEXT DEFAULT '', source TEXT, body TEXT DEFAULT '',
                  language TEXT DEFAULT 'en', level TEXT DEFAULT 'B2', topic TEXT DEFAULT '',
                  source_guid TEXT DEFAULT '', content_hash TEXT DEFAULT '', created_at TEXT DEFAULT '', updated_at TEXT DEFAULT ''
                );
                CREATE TABLE feeds (id INTEGER PRIMARY KEY);
                CREATE TABLE mistakes (id INTEGER PRIMARY KEY);
                CREATE TABLE quizzes (id INTEGER PRIMARY KEY);
                CREATE TABLE attempts (id INTEGER PRIMARY KEY);
                CREATE TABLE practice_sessions (id INTEGER PRIMARY KEY);
                CREATE TABLE cards (id INTEGER PRIMARY KEY);
                """
            )
            run_migrations(conn)
            body = "A complete article closes with a clear finding.\n\nWeekly Newsletter var gform;"
            cursor = conn.execute(
                """INSERT INTO articles
                   (title, source, body, language, level, topic, created_at, updated_at)
                   VALUES ('JSTOR sample', 'JSTOR Daily', ?, 'en', 'B2', 'history', '', '')""",
                (body,),
            )
            article_id = cursor.lastrowid
            _source_adapter_backfill(conn)
            article = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
            audit = conn.execute(
                "SELECT * FROM article_extraction_audits WHERE article_id = ? AND extraction_version = 'jstor-rss-v1'",
                (article_id,),
            ).fetchone()
        self.assertEqual(article["body"], "A complete article closes with a clear finding.")
        self.assertEqual(article["extraction_version"], "jstor-rss-v1")
        self.assertEqual(audit["original_body"], body)

    def test_backup_round_trip_restores_database_and_creates_safety_copy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "coach.sqlite"
            backup_dir = root / "backups"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE sample (value TEXT NOT NULL)")
                conn.execute("INSERT INTO sample VALUES ('before')")
                conn.commit()
            backup = create_backup(db_path, backup_dir, "test")
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("UPDATE sample SET value = 'after'")
                conn.commit()
            result = restore_backup(db_path, backup_dir, backup["filename"], "test")
            with closing(sqlite3.connect(db_path)) as conn:
                value = conn.execute("SELECT value FROM sample").fetchone()[0]
            self.assertEqual(value, "before")
            self.assertEqual(result["restored"], backup["filename"])
            self.assertEqual(len(list_backups(backup_dir)), 2)

    def test_restore_rejects_paths_outside_backup_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "coach.sqlite"
            sqlite3.connect(db_path).close()
            with self.assertRaisesRegex(ValueError, "Invalid backup filename"):
                restore_backup(db_path, root / "backups", "../coach.sqlite", "test")

    def test_runtime_metadata_reports_compatible_versions(self):
        original_db = server.DB_PATH
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                server.DB_PATH = Path(temp_dir) / "coach.sqlite"
                server.init_db()
                metadata = server.runtime_metadata()
            self.assertEqual(metadata["api_version"], API_VERSION)
            self.assertEqual(metadata["schema_version"], SCHEMA_VERSION)
            self.assertEqual(metadata["database_schema_version"], SCHEMA_VERSION)
            self.assertTrue(metadata["compatible"])
        finally:
            server.DB_PATH = original_db

    def test_runtime_metadata_keeps_the_process_start_version(self):
        original_db = server.DB_PATH
        original_version = server.PROCESS_APP_VERSION
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                server.DB_PATH = Path(temp_dir) / "coach.sqlite"
                server.PROCESS_APP_VERSION = "process-start-version"
                server.init_db()
                with patch.object(server, "version_payload", return_value={
                    "app_version": "changed-on-disk",
                    "api_version": API_VERSION,
                    "schema_version": SCHEMA_VERSION,
                }):
                    metadata = server.runtime_metadata()
            self.assertEqual(metadata["app_version"], "process-start-version")
            self.assertTrue(metadata["compatible"])
        finally:
            server.DB_PATH = original_db
            server.PROCESS_APP_VERSION = original_version


if __name__ == "__main__":
    unittest.main()
