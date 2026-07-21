import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path

from backend.private_dictionaries import (
    ensure_private_dictionary_schema,
    extract_mobi_html,
    parse_dictionary_html,
    private_phrase_meanings,
    register_private_dictionary,
    register_private_pdf_source,
    search_private_entries,
)


def build_uncompressed_mobi(path: Path, document: str) -> None:
    text = document.encode("cp1252", errors="xmlcharrefreplace")
    record_zero = bytearray(248)
    struct.pack_into(">HHIHHH", record_zero, 0, 1, 0, len(text), 1, 4096, 0)
    record_zero[16:20] = b"MOBI"
    struct.pack_into(">I", record_zero, 20, 232)
    struct.pack_into(">I", record_zero, 28, 1252)
    header = bytearray(96)
    header[60:68] = b"BOOKMOBI"
    struct.pack_into(">H", header, 76, 2)
    struct.pack_into(">I", header, 78, len(header))
    struct.pack_into(">I", header, 86, len(header) + len(record_zero))
    path.write_bytes(bytes(header) + bytes(record_zero) + text)


class PrivateDictionaryTests(unittest.TestCase):
    def test_registers_image_pdf_without_promoting_unverified_entries(self):
        with tempfile.TemporaryDirectory() as root:
            pdf = Path(root) / "illustrated.pdf"
            pdf.write_bytes(b"%PDF-1.7\nimage-only-placeholder")
            conn = sqlite3.connect(":memory:")
            try:
                conn.row_factory = sqlite3.Row
                ensure_private_dictionary_schema(conn)
                result = register_private_pdf_source(
                    conn, pdf, name="Illustrated dictionary", pages=1263,
                    priority=30, now="2026-07-21T00:00:00+00:00",
                )
                entries = conn.execute("SELECT COUNT(*) FROM private_dictionary_entries").fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(result["status"], "ocr_required")
            self.assertEqual(result["format"], "pdf")
            self.assertEqual(result["entry_count"], 0)
            self.assertEqual(entries, 0)

    def test_parses_headwords_and_keeps_bilingual_entry_order(self):
        document = (
            "<html><body><mbp:pagebreak/><h2> keen </h2>"
            "adj eager 热切的<br/>be keen to do 热切想做<br/>She is keen to learn. 她渴望学习。"
            "<mbp:pagebreak/><h2> zeal </h2>n enthusiasm 热忱</body></html>"
        )
        entries = parse_dictionary_html(document)
        self.assertEqual([entry[0] for entry in entries], ["keen", "zeal"])
        self.assertIn("be keen to do 热切想做", entries[0][1])
        self.assertIn("She is keen to learn. 她渴望学习。", entries[0][1])

    def test_imports_private_mobi_and_returns_local_only_result(self):
        with tempfile.TemporaryDirectory() as root:
            mobi = Path(root) / "private.mobi"
            database = Path(root) / "private.sqlite"
            entries = "<mbp:pagebreak/><h2> be keen on </h2>fond of 喜爱；热衷于" + "".join(
                f"<mbp:pagebreak/><h2> word{index} </h2>n definition {index} 中文释义"
                for index in range(119)
            )
            build_uncompressed_mobi(mobi, f"<html><body>{entries}</body></html>")
            document, metadata = extract_mobi_html(mobi)
            self.assertEqual(metadata["compression_name"], "none")
            self.assertIn("word42", document)
            conn = sqlite3.connect(database)
            try:
                conn.row_factory = sqlite3.Row
                ensure_private_dictionary_schema(conn)
                result = register_private_dictionary(
                    conn, mobi, name="My dictionary", kind="bilingual_dictionary",
                    priority=10, now="2026-07-21T00:00:00+00:00",
                )
                lookup = search_private_entries(conn, "word42")
                phrase = private_phrase_meanings(conn, ["be keen on"])
            finally:
                conn.close()
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["entry_count"], 120)
            self.assertEqual(lookup[0]["visibility"], "private_local")
            self.assertEqual(lookup[0]["source_name"], "My dictionary")
            self.assertEqual(phrase["be keen on"]["meaning_zh"], "喜爱；热衷于")


if __name__ == "__main__":
    unittest.main()
