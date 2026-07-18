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
                    "00000003-v": {
                        "definition": ["to examine something as a test"],
                        "example": ["They test the system twice."],
                        "members": ["test", "try out"],
                        "partOfSpeech": "v",
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
                        },
                        "v": {
                            "pronunciation": [{"value": "/test/"}],
                            "sense": [{"id": "test%2:00:00::", "synset": "00000003-v"}],
                        },
                    }
                })
            )
        cls.result = import_wordnet(cls.archive, cls.database)

    @classmethod
    def tearDownClass(cls):
        server.DB_PATH = cls.previous_db
        cls.temp_dir.cleanup()

    def test_import_records_source_and_counts(self):
        self.assertEqual(self.result["synsets"], 3)
        self.assertEqual(self.result["lemmas"], 2)
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

    def test_same_headword_parts_of_speech_are_grouped(self):
        results = [item for item in server.lexical_search("test")["results"] if item["type"] == "wordnet"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["parts_of_speech"], ["noun", "verb"])
        self.assertEqual({sense["pos"] for sense in results[0]["senses"]}, {"noun", "verb"})
        self.assertEqual(len(results[0]["examples"]), 2)

    def test_generic_pronunciation_is_labeled_without_inventing_dialects(self):
        result = server.lexical_search("test")["results"][0]
        self.assertEqual(result["ipa_uk"], "/test/")
        self.assertEqual(result["ipa_us"], "/test/")
        self.assertEqual(result["pronunciation_scope"], "generic")

    def test_tagged_open_pronunciations_keep_uk_and_us_distinct(self):
        resolved = server.resolve_pronunciations([
            {"ipa": "/kɑːst/", "tags": ["UK"]},
            {"ipa": "/kæst/", "tags": ["US", "General American"]},
        ], ["/kast/"])
        self.assertEqual(resolved["ipa_uk"], "/kɑːst/")
        self.assertEqual(resolved["ipa_us"], "/kæst/")
        self.assertEqual(resolved["pronunciation_scope"], "dialect-specific")
        australian = server.resolve_pronunciations([{"ipa": "/test/", "tags": ["Australian"]}])
        self.assertEqual(australian["pronunciation_scope"], "generic")

    def test_cached_word_and_relation_translations_are_exposed(self):
        values = {"test": "测试", "concept": "概念"}
        with server.db() as conn:
            for source, translated in values.items():
                digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
                conn.execute(
                    """INSERT INTO translation_cache
                       (text_hash, source_lang, target_lang, provider, source_text, translated_text, created_at)
                       VALUES (?, 'EN', 'ZH-HANS', 'deepl', ?, ?, ?)""",
                    (digest, source, translated, server.utc_now()),
                )
        result = server.lexical_search("test")["results"][0]
        self.assertEqual(result["headword_translation_zh"], "测试")
        relation = next(item for item in result["semantic_relations"] if item["type"] == "hypernym")
        self.assertEqual(relation["term_details"][0]["meaning_zh"], "概念")


if __name__ == "__main__":
    unittest.main()
