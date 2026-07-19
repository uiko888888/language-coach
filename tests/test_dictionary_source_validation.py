import gzip
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.build_kaikki_target_words import QUALITY_GATE_TERMS, build_target_words
from scripts.validate_dictionary_source import validate_archive, validate_frequency, validate_kaikki


class DictionarySourceValidationTests(unittest.TestCase):
    def test_archive_validation_reads_the_full_member(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "sentences.tsv"
            source.write_text("1\teng\tA complete sentence.\tAlice\n", encoding="utf-8")
            archive = root / "sentences.tar.bz2"
            with tarfile.open(archive, "w:bz2") as bundle:
                bundle.add(source, arcname="sentences.tsv")
            result = validate_archive(archive)
            self.assertEqual(result["files"], 1)
            self.assertGreater(result["uncompressed_bytes"], 1)
            truncated = root / "truncated.tar.bz2"
            content = archive.read_bytes()
            truncated.write_bytes(content[:len(content) // 2])
            with self.assertRaises((EOFError, OSError, tarfile.TarError)):
                validate_archive(truncated)

    def test_frequency_validation_rejects_invalid_or_small_sources(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "frequency.tsv"
            path.write_text("the\t7.73\ninspect\t3.63\n", encoding="utf-8")
            self.assertEqual(validate_frequency(path, minimum_rows=2)["valid_rows"], 2)
            path.write_text("the\tnan\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "rejected rows"):
                validate_frequency(path, minimum_rows=1)

    def test_kaikki_validation_reads_complete_gzip_jsonl(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "kaikki.jsonl.gz"
            with gzip.open(path, "wt", encoding="utf-8") as stream:
                for word in ("set", "run"):
                    stream.write(json.dumps({"word": word, "lang_code": "en"}) + "\n")
            result = validate_kaikki(path, minimum_rows=2)
            self.assertEqual(result["valid_rows"], 2)
            path.write_bytes(path.read_bytes()[:-4])
            with self.assertRaises((EOFError, OSError)):
                validate_kaikki(path, minimum_rows=2)

    def test_target_words_include_frequency_and_quality_probes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            frequency = root / "frequency.tsv"
            output = root / "targets.txt"
            frequency.write_text("the\t7.73\ninspect\t3.63\n", encoding="utf-8")
            result = build_target_words(frequency, output, limit=2)
            targets = set(output.read_text(encoding="utf-8").splitlines())
            self.assertEqual(result["frequency_limit"], 2)
            self.assertIn("the", targets)
            self.assertTrue(QUALITY_GATE_TERMS.issubset(targets))


if __name__ == "__main__":
    unittest.main()
