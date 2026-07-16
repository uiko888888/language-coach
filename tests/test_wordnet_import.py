import json
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from backend import server
from scripts.import_wordnet import import_wordnet


class WordNetImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.previous_db = server.DB_PATH
        cls.database = Path(cls.temp_dir.name) / "wordnet.sqlite"
        cls.archive = Path(cls.temp_dir.name) / "wordnet.zip"
        server.DB_PATH = cls.database
        server.init_db()
        with zipfile.ZipFile(cls.archive, "w") as archive:
            archive.writestr(
                "noun.test.json",
                json.dumps({
                    "00000001-n": {
                        "definition": ["a small test concept"],
                        "example": ["This is a test."],
                        "members": ["test"],
                        "partOfSpeech": "n",
                        "hypernym": ["00000002-n"],
                    },
                    "00000002-n": {
                        "definition": ["a broader concept"],
                        "members": ["concept"],
                        "partOfSpeech": "n",
                    },
                })
            )
            archive.writestr(
                "entries-t.json",
                json.dumps({
                    "test": {
                        "n": {
                            "pronunciation": [{"value": "/test/"}],
                            "sense": [{"id": "test%1:00:00::", "synset": "00000001-n"}],
                        }
                    }
                })
            )
        cls.result = import_wordnet(cls.archive, cls.database)

    @classmethod
    def tearDownClass(cls):
        server.DB_PATH = cls.previous_db
        cls.temp_dir.cleanup()

    def test_import_records_source_and_counts(self):
        self.assertEqual(self.result["synsets"], 2)
        self.assertEqual(self.result["lemmas"], 1)
        with server.db() as conn:
            source = conn.execute("SELECT * FROM dictionary_sources").fetchone()
        self.assertEqual(source["license"], "CC BY 4.0")
        self.assertEqual(source["version"], "2025")

    def test_cached_definition_translation_appears_in_lookup(self):
        definition = "a small test concept"
        digest = hashlib.sha256(definition.encode("utf-8")).hexdigest()
        with server.db() as conn:
            conn.execute(
                """INSERT INTO translation_cache
                   (text_hash, source_lang, target_lang, provider, source_text, translated_text, created_at)
                   VALUES (?, 'EN', 'ZH-HANS', 'deepl', ?, ?, ?)""",
                (digest, definition, "一个小型测试概念", server.utc_now()),
            )
        result = server.lexical_search("test")["results"][0]
        self.assertEqual(result["meaning_zh"], "一个小型测试概念")
        self.assertEqual(result["senses"][0]["definition_translations"][0], "一个小型测试概念")

    def test_wordnet_lookup_exposes_definition_and_relation(self):
        result = server.lexical_search("test")["results"][0]
        self.assertEqual(result["type"], "wordnet")
        self.assertEqual(result["core_meaning"], "a small test concept")
        relation = next(item for item in result["semantic_relations"] if item["type"] == "hypernym")
        self.assertIn("concept", relation["terms"])


if __name__ == "__main__":
    unittest.main()
