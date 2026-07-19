import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.validate_dictionary_source import validate_archive, validate_frequency


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


if __name__ == "__main__":
    unittest.main()
