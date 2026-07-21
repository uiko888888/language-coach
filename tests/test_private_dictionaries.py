import gzip
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
    register_private_stardict,
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


def build_stardict(root: Path, entries, *, sequence="m", compressed=False, synonyms=()):
    base = root / "sample"
    dictionary = bytearray()
    index = bytearray()
    for headword, definition in entries:
        payload = definition.encode("utf-8")
        offset = len(dictionary)
        dictionary.extend(payload)
        index.extend(headword.encode("utf-8") + b"\0")
        index.extend(struct.pack(">II", offset, len(payload)))
    ifo = base.with_suffix(".ifo")
    ifo.write_text(
        "\n".join((
            "StarDict's dict ifo file", "version=3.0.0", f"wordcount={len(entries)}",
            f"idxfilesize={len(index)}", "bookname=Sample", f"sametypesequence={sequence}",
        )) + "\n",
        encoding="utf-8",
    )
    if compressed:
        with gzip.open(str(base) + ".idx.gz", "wb") as target:
            target.write(index)
        with gzip.open(str(base) + ".dict.dz", "wb") as target:
            target.write(dictionary)
    else:
        Path(str(base) + ".idx").write_bytes(index)
        Path(str(base) + ".dict").write_bytes(dictionary)
    if synonyms:
        data = b"".join(word.encode("utf-8") + b"\0" + struct.pack(">I", target) for word, target in synonyms)
        Path(str(base) + ".syn").write_bytes(data)
    return ifo


class PrivateDictionaryTests(unittest.TestCase):
    def test_imports_stardict_html_and_synonyms(self):
        with tempfile.TemporaryDirectory() as root:
            ifo = build_stardict(
                Path(root),
                [("keen", "<b>adj.</b> eager; 热切的<br/>be keen on 喜爱"), ("zeal", "<b>n.</b> enthusiasm; 热忱")],
                sequence="h", synonyms=(("enthusiasm", 1),),
            )
            conn = sqlite3.connect(":memory:")
            try:
                conn.row_factory = sqlite3.Row
                ensure_private_dictionary_schema(conn)
                result = register_private_stardict(
                    conn, ifo, name="Sample StarDict", kind="bilingual_dictionary",
                    priority=5, now="2026-07-21T00:00:00+00:00",
                )
                keen = search_private_entries(conn, "keen")
                synonym = search_private_entries(conn, "enthusiasm")
            finally:
                conn.close()
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["entry_count"], 3)
            self.assertIn("be keen on 喜爱", keen[0]["entry_text"])
            self.assertIn("enthusiasm; 热忱", synonym[0]["entry_text"])

    def test_imports_compressed_stardict_without_full_dictionary_buffer(self):
        with tempfile.TemporaryDirectory() as root:
            ifo = build_stardict(Path(root), [("cast", "v. throw; 投掷"), ("cordial", "adj. warm and friendly; 热情友好的")], compressed=True)
            conn = sqlite3.connect(":memory:")
            try:
                conn.row_factory = sqlite3.Row
                ensure_private_dictionary_schema(conn)
                result = register_private_stardict(
                    conn, ifo, name="Compressed StarDict", kind="bilingual_dictionary",
                    priority=5, now="2026-07-21T00:00:00+00:00",
                )
                lookup = search_private_entries(conn, "cast")
            finally:
                conn.close()
            self.assertEqual(result["entry_count"], 2)
            self.assertEqual(lookup[0]["headword"], "cast")

    def test_failed_stardict_refresh_rolls_back_existing_index(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            ifo = build_stardict(root_path, [("cast", "v. throw; 投掷"), ("keen", "adj. eager; 热切的")])
            database = root_path / "private.sqlite"
            conn = sqlite3.connect(database)
            try:
                conn.row_factory = sqlite3.Row
                ensure_private_dictionary_schema(conn)
                register_private_stardict(
                    conn, ifo, name="Rollback StarDict", kind="bilingual_dictionary",
                    priority=5, now="2026-07-21T00:00:00+00:00",
                )
                conn.commit()
            finally:
                conn.close()
            Path(str(ifo.with_suffix("")) + ".dict").write_bytes(b"broken")
            with self.assertRaisesRegex(ValueError, "offset or size"):
                conn = sqlite3.connect(database)
                try:
                    conn.row_factory = sqlite3.Row
                    register_private_stardict(
                        conn, ifo, name="Rollback StarDict", kind="bilingual_dictionary",
                        priority=5, now="2026-07-21T01:00:00+00:00",
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
                finally:
                    conn.close()
            conn = sqlite3.connect(database)
            try:
                source = conn.execute("SELECT status, entry_count FROM private_dictionaries").fetchone()
                count = conn.execute("SELECT COUNT(*) FROM private_dictionary_entries").fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(source, ("ready", 2))
            self.assertEqual(count, 2)

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
