import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend import server
from backend.backups import create_backup, list_backups, restore_backup
from backend.migrations import run_migrations
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
        self.assertEqual(len(migrations), 1)
        self.assertIn("translation_zh", article_columns)
        self.assertIn("content_status", article_columns)

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


if __name__ == "__main__":
    unittest.main()
