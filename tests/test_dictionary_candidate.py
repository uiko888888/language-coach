import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend import server
from scripts.stage_kaikki_candidate import clone_database, stage_kaikki_candidate


class DictionaryCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.production = self.root / "production.sqlite3"
        original = server.DB_PATH
        server.DB_PATH = self.production
        try:
            server.init_db()
        finally:
            server.DB_PATH = original

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_failed_gate_keeps_production_unchanged_and_preserves_candidate(self):
        source = self.root / "kaikki.jsonl"
        source.write_text(json.dumps({
            "id": "inspect-verb",
            "word": "inspect",
            "lang_code": "en",
            "pos": "verb",
            "senses": [{"glosses": ["to examine carefully"]}],
        }) + "\n", encoding="utf-8")
        words = self.root / "words.txt"
        words.write_text("inspect\n", encoding="utf-8")
        candidate = self.root / "candidate.sqlite3"
        report = self.root / "candidate.json"

        result = stage_kaikki_candidate(
            source,
            words,
            self.production,
            candidate,
            report,
            "test-version",
        )

        self.assertFalse(result["ready"])
        self.assertTrue(result["production_unchanged"])
        self.assertEqual(result["integrity"], "ok")
        self.assertTrue(candidate.is_file())
        self.assertTrue(report.is_file())
        production_conn = sqlite3.connect(self.production)
        candidate_conn = sqlite3.connect(candidate)
        try:
            production_count = production_conn.execute("SELECT COUNT(*) FROM open_lexical_entries").fetchone()[0]
            candidate_count = candidate_conn.execute("SELECT COUNT(*) FROM open_lexical_entries").fetchone()[0]
        finally:
            candidate_conn.close()
            production_conn.close()
        self.assertEqual(production_count, 0)
        self.assertEqual(candidate_count, 1)

    def test_clone_rejects_production_as_candidate(self):
        with self.assertRaisesRegex(ValueError, "must differ"):
            clone_database(self.production, self.production)


if __name__ == "__main__":
    unittest.main()
