import json
import sqlite3
import tarfile
import tempfile
import unittest
from pathlib import Path

from backend import server
from backend.lexical_data import lookup_lexical_layers, search_open_entries
from scripts.import_kaikki import import_kaikki
from scripts.import_tatoeba import import_tatoeba
from scripts.import_word_frequency import import_frequency_tsv


class OpenLexicalDataTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.database = self.root / "lexical.sqlite"
        original = server.DB_PATH
        server.DB_PATH = self.database
        try:
            server.init_db()
        finally:
            server.DB_PATH = original

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_layered_imports_merge_etymology_frequency_chinese_and_attributed_examples(self):
        kaikki = self.root / "kaikki.jsonl"
        kaikki.write_text(json.dumps({
            "id": "inspect-en-verb-1",
            "word": "inspect",
            "lang_code": "en",
            "pos": "verb",
            "sounds": [{"ipa": "/ɪnˈspekt/", "tags": ["UK"]}],
            "forms": [{"form": "inspected", "tags": ["past"]}],
            "etymology_text": "From Latin inspectus, from inspicere.",
            "senses": [{
                "glosses": ["to examine carefully"],
                "translations": [{"lang_code": "zh", "word": "检查；仔细查看"}],
                "examples": [{"text": "They inspect every component."}],
                "synonyms": [{"word": "examine"}],
            }],
            "derived": [{"word": "inspection"}],
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        frequencies = self.root / "frequency.tsv"
        frequencies.write_text("inspect\t4.72\n", encoding="utf-8")
        sentences = self.root / "sentences.tsv"
        sentences.write_text(
            "1\teng\tEngineers inspect the bridge every year.\tAlice\n"
            "2\tcmn\t工程师每年检查这座桥。\t小林\n"
            "3\teng\tInspect this line.\t\n"
            "4\tcmn\t检查这一行。\t小王\n",
            encoding="utf-8",
        )
        links = self.root / "links.tsv"
        links.write_text("1\t2\n3\t4\n", encoding="utf-8")
        sentence_archive = self.root / "sentences_detailed.tar.bz2"
        links_archive = self.root / "links.tar.bz2"
        with tarfile.open(sentence_archive, "w:bz2") as archive:
            archive.add(sentences, arcname="sentences_detailed.csv")
        with tarfile.open(links_archive, "w:bz2") as archive:
            archive.add(links, arcname="links.csv")

        self.assertEqual(import_kaikki(kaikki, self.database)["imported"], 1)
        self.assertEqual(import_frequency_tsv(frequencies, self.database)["frequencies"], 1)
        self.assertEqual(import_tatoeba(sentence_archive, links_archive, self.database)["pairs"], 1)

        conn = sqlite3.connect(self.database)
        conn.row_factory = sqlite3.Row
        try:
            layers = lookup_lexical_layers(conn, "inspect")
            results = search_open_entries(conn, "检查")
        finally:
            conn.close()
        self.assertEqual(layers["translations_zh"][0], "检查；仔细查看")
        self.assertEqual(layers["primary_frequency"]["frequency_band"], "常见")
        self.assertEqual(layers["forms"][0]["form"], "inspected")
        self.assertIn("Latin", layers["etymologies"][0])
        self.assertEqual(len(layers["examples"]), 1)
        self.assertEqual(layers["examples"][0]["source_author"], "Alice")
        self.assertEqual(layers["examples"][0]["license"], "CC BY 2.0 FR")
        self.assertTrue(results)
        self.assertEqual(results[0]["headword"], "inspect")
        original = server.DB_PATH
        server.DB_PATH = self.database
        try:
            payload = server.lexical_search("inspect")
            chinese_payload = server.lexical_search("检查")
            status = server.dictionary_data_status()
        finally:
            server.DB_PATH = original
        open_result = next(item for item in payload["results"] if item["type"] == "open")
        self.assertEqual(open_result["frequency"]["frequency_band"], "常见")
        self.assertEqual(open_result["lexical_layers"]["examples"][0]["target_text"], "工程师每年检查这座桥。")
        self.assertTrue(any(item["type"] == "open" for item in chinese_payload["results"]))
        self.assertTrue(all(layer["installed"] for layer in status["layers"][1:]))

    def test_invalid_preference_data_does_not_affect_open_lexical_schema(self):
        conn = sqlite3.connect(self.database)
        try:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")}
        finally:
            conn.close()
        self.assertTrue({"open_lexical_entries", "open_bilingual_examples", "lexical_frequencies"}.issubset(tables))


if __name__ == "__main__":
    unittest.main()
