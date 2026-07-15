import gc
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


if __name__ == "__main__":
    unittest.main()
