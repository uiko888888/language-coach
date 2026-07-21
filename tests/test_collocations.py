import sqlite3
import unittest

from backend.collocations import corpus_collocations
from backend.lexical_data import ensure_lexical_data_schema


class CollocationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """CREATE TABLE dictionary_sources (
                 source_key TEXT PRIMARY KEY, name TEXT, version TEXT, license TEXT,
                 attribution TEXT, source_url TEXT, checksum TEXT, imported_at TEXT
               )"""
        )
        self.conn.execute(
            """CREATE TABLE articles (
                 id INTEGER PRIMARY KEY, title TEXT, source TEXT, visibility TEXT,
                 body TEXT, updated_at TEXT
               )"""
        )
        ensure_lexical_data_schema(self.conn)
        self.conn.execute(
            "INSERT INTO dictionary_sources VALUES ('tatoeba-en-zh', 'Tatoeba', 'test', 'CC BY', 'authors', '', '', '')"
        )

    def tearDown(self):
        self.conn.close()

    def add_example(self, record_id, source, target="示例。"):
        self.conn.execute(
            """INSERT INTO open_bilingual_examples
               (source_text, target_text, license, source_key, source_record_id, quality_score, created_at)
               VALUES (?, ?, 'CC BY', 'tatoeba-en-zh', ?, 90, '')""",
            (source, target, record_id),
        )

    def test_repeated_open_corpus_phrase_is_common_but_single_neighbor_is_not(self):
        self.add_example("1", "She is keen on modern architecture.")
        self.add_example("2", "Many students are keen on the exchange programme.")
        self.add_example("3", "A keen observer noticed the change.")
        self.add_example("4", "She keenly watched, but she keen is not a useful phrase.")
        result = corpus_collocations(self.conn, "keen", registered_phrases=["keen on"])
        phrases = {item["phrase"]: item for item in result["items"]}
        self.assertIn("keen on", phrases)
        self.assertEqual(phrases["keen on"]["observed_count"], 2)
        self.assertEqual(phrases["keen on"]["source_count"], 1)
        self.assertNotIn("keen observer", phrases)
        self.assertNotIn("she keen", phrases)
        self.assertEqual(result["examples_scanned"], 4)

    def test_curated_pattern_remains_distinct_from_corpus_frequency(self):
        result = corpus_collocations(self.conn, "cordial", curated_patterns=["a cordial welcome"])
        self.assertEqual(result["items"][0]["source"], "本地整理")
        self.assertEqual(result["items"][0]["observed_count"], 0)
        self.assertEqual(result["items"][0]["confidence"], "人工整理基础组")
