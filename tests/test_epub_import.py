import tempfile
import unittest
import zipfile
from pathlib import Path

from backend import server


CONTAINER_XML = """<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="EPUB/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""

PACKAGE_XML = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Open Test Reader</dc:title><dc:creator>Test Author</dc:creator><dc:language>en</dc:language>
  </metadata>
  <manifest>
    <item id="c1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
    <item id="c2" href="chapter2.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="c1"/><itemref idref="c2"/></spine>
</package>"""


def chapter(title: str, topic: str) -> str:
    return f"""<html><head><title>{title}</title></head><body><h1>{title}</h1>
    <p>This openly generated chapter explains {topic} through a clear example for language learners.</p>
    <p>Readers can inspect the paragraph structure, save useful phrases, and create private practice questions safely.</p>
    </body></html>"""


class EpubImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp_dir.name)
        server.DB_PATH = cls.root / "epub.sqlite"
        server.init_db()
        cls.epub = cls.root / "open-test.epub"
        with zipfile.ZipFile(cls.epub, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr("META-INF/container.xml", CONTAINER_XML)
            archive.writestr("EPUB/content.opf", PACKAGE_XML)
            archive.writestr("EPUB/chapter1.xhtml", chapter("Chapter One", "evidence"))
            archive.writestr("EPUB/chapter2.xhtml", chapter("Chapter Two", "context"))

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def setUp(self):
        with server.db() as conn:
            conn.execute("DELETE FROM book_chapters")
            conn.execute("DELETE FROM books")
            conn.execute("DELETE FROM articles WHERE source = 'private EPUB'")

    def test_parser_follows_container_manifest_and_spine(self):
        parsed = server.parse_epub(str(self.epub))
        self.assertEqual(parsed["title"], "Open Test Reader")
        self.assertEqual(parsed["author"], "Test Author")
        self.assertEqual([item["title"] for item in parsed["chapters"]], ["Chapter One", "Chapter Two"])
        self.assertTrue(all(item["word_count"] >= 20 for item in parsed["chapters"]))

    def test_import_is_idempotent_and_listing_hides_body_and_path(self):
        first, created = server.import_epub(str(self.epub))
        second, created_again = server.import_epub(str(self.epub))
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["source_path"], self.epub.name)
        self.assertNotIn("body", first["chapters"][0])
        with server.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM books").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM book_chapters").fetchone()[0], 2)

    def test_chapter_materializes_once_as_private_article(self):
        book, _ = server.import_epub(str(self.epub))
        chapter_id = book["chapters"][0]["id"]
        with server.db() as conn:
            first = server.materialize_book_chapter(conn, chapter_id)
            second = server.materialize_book_chapter(conn, chapter_id)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["source"], "private EPUB")
        self.assertEqual(first["content_status"], "full")
        self.assertTrue(first["source_url"].startswith("private-epub://"))

    def test_invalid_epub_is_rejected(self):
        invalid = self.root / "invalid.epub"
        invalid.write_text("not a zip", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "ZIP"):
            server.parse_epub(str(invalid))


if __name__ == "__main__":
    unittest.main()
