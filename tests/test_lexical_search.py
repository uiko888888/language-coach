import gc
import hashlib
import tempfile
import unittest
from pathlib import Path

from backend import server


class LexicalSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        server.DB_PATH = Path(cls.temp_dir.name) / "test.sqlite"
        server.init_db()

    @classmethod
    def tearDownClass(cls):
        gc.collect()
        cls.temp_dir.cleanup()

    def first_label(self, query):
        first = server.lexical_search(query)["results"][0]
        return first.get("headword") or first.get("form")

    def test_exact_headword_and_word_form(self):
        self.assertEqual(self.first_label("inspect"), "inspect")
        self.assertEqual(self.first_label("inspection"), "inspection")
        self.assertEqual(self.first_label("inspected"), "inspect")

    def test_chinese_root_and_etymon_queries(self):
        self.assertIn(self.first_label("观察"), {"inspect", "spect"})
        self.assertEqual(self.first_label("spect"), "spect")
        self.assertEqual(self.first_label("specere"), "spect")

    def test_affix_queries(self):
        self.assertEqual(self.first_label("re-"), "re-")
        self.assertEqual(self.first_label("-tion"), "-tion")

    def test_empty_query_returns_browsable_catalog(self):
        payload = server.lexical_search("")
        self.assertGreaterEqual(payload["count"], 10)
        self.assertTrue(any(item["type"] == "entry" for item in payload["results"]))
        self.assertTrue(any(item["type"] == "morpheme" for item in payload["results"]))

    def test_collocations_include_bilingual_relations(self):
        entry = server.lexical_search("inspect")["results"][0]
        collocation = entry["collocations"][0]
        self.assertEqual(collocation["phrase"], "inspect the premises")
        self.assertEqual(collocation["meaning_zh"], "检查场所")
        self.assertTrue(collocation["synonyms"][0]["meaning_zh"])
        self.assertTrue(collocation["antonyms"][0]["meaning_zh"])

    def test_examples_include_chinese_translations(self):
        entry = server.lexical_search("inspected")["results"][0]
        self.assertEqual(entry["headword"], "inspect")
        self.assertIn("inspected", entry["examples"][1]["text"].lower())
        self.assertEqual(entry["examples"][1]["translation"], "这些文件在批准之前必须经过审查。")

    def test_phrase_relations_are_searchable(self):
        results = server.lexical_search("check for damage")["results"]
        self.assertEqual(results[0]["type"], "query")
        self.assertEqual(results[0]["kind"], "phrase")
        self.assertEqual(results[0]["translation_zh"], "查看有无损坏")
        self.assertTrue(any(item.get("headword") == "inspect" for item in results))

    def test_unknown_term_keeps_translation_learning_state_and_context(self):
        term = "meaningful control"
        now = server.utc_now()
        digest = hashlib.sha256(term.encode("utf-8")).hexdigest()
        with server.db() as conn:
            article = conn.execute("SELECT id FROM articles WHERE source = 'seed'").fetchone()
            conn.execute(
                """INSERT INTO cards (term, kind, context, source_article_id, status, created_at, updated_at)
                   VALUES (?, 'phrase', ?, ?, 'new', ?, ?)""",
                (term, "People need meaningful control over their data.", article["id"], now, now),
            )
            conn.execute(
                """INSERT INTO translation_cache
                   (text_hash, source_lang, target_lang, provider, source_text, translated_text, created_at)
                   VALUES (?, 'EN', 'ZH-HANS', 'deepl', ?, ?, ?)""",
                (digest, term, "真正的掌控权", now),
            )
        item = server.lexical_search(term)["results"][0]
        self.assertEqual(item["type"], "query")
        self.assertTrue(item["saved"])
        self.assertEqual(item["translation_zh"], "真正的掌控权")
        self.assertTrue(item["contexts"])

    def test_unknown_single_word_returns_actionable_query(self):
        item = server.lexical_search("ubiquitous")["results"][0]
        self.assertEqual(item["type"], "query")
        self.assertEqual(item["term"], "ubiquitous")
        self.assertEqual(item["kind"], "word")


if __name__ == "__main__":
    unittest.main()
