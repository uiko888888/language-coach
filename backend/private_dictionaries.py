from __future__ import annotations

import hashlib
import html
import re
import sqlite3
import struct
from html.parser import HTMLParser
from pathlib import Path


PAGE_ENTRY_RE = re.compile(
    rb"<mbp:pagebreak\s*/?>\s*<h2>(.*?)</h2>(.*?)(?=<mbp:pagebreak\s*/?>\s*<h2>|\Z)",
    re.IGNORECASE | re.DOTALL,
)


def normalize_headword(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"br", "p", "li", "div", "hr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"p", "li", "div"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        value = "".join(self.parts)
        value = "".join(char for char in value if char in "\n\t" or ord(char) >= 32)
        value = re.sub(r"[ \t]+", " ", value)
        value = re.sub(r" *\n *", "\n", value)
        return re.sub(r"\n{3,}", "\n\n", value).strip()


def html_to_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    return parser.text()


def _record_offsets(data: bytes) -> list[int]:
    count = struct.unpack(">H", data[76:78])[0]
    return [struct.unpack(">I", data[78 + index * 8:82 + index * 8])[0] for index in range(count)]


def inspect_mobi(path: Path) -> dict:
    data = path.read_bytes()
    offsets = _record_offsets(data)
    record = data[offsets[0]:offsets[1]]
    if record[16:20] != b"MOBI":
        raise ValueError("The file is not a supported MOBI container")
    compression, _, text_length, text_records, record_size, encryption = struct.unpack(">HHIHHH", record[:14])
    encoding_code = struct.unpack(">I", record[28:32])[0]
    return {
        "compression": compression,
        "compression_name": {1: "none", 2: "PalmDOC", 17480: "HUFF/CDIC"}.get(compression, f"unknown-{compression}"),
        "text_length": text_length,
        "text_records": text_records,
        "record_size": record_size,
        "encryption": encryption,
        "encoding": {65001: "utf-8", 1252: "cp1252"}.get(encoding_code, "utf-8"),
    }


def _palmdoc_decompress(data: bytes) -> bytes:
    output = bytearray()
    index = 0
    while index < len(data):
        value = data[index]
        index += 1
        if value == 0:
            output.append(0)
        elif value <= 8:
            output.extend(data[index:index + value])
            index += value
        elif value <= 0x7F:
            output.append(value)
        elif value <= 0xBF:
            if index >= len(data):
                break
            pair = (value << 8) | data[index]
            index += 1
            distance = (pair >> 3) & 0x7FF
            length = (pair & 7) + 3
            if not distance or distance > len(output):
                break
            for _ in range(length):
                output.append(output[-distance])
        else:
            output.extend((32, value ^ 0x80))
    return bytes(output)


def extract_mobi_html(path: Path) -> tuple[str, dict]:
    metadata = inspect_mobi(path)
    if metadata["encryption"]:
        raise ValueError("Encrypted/DRM-protected MOBI files are not supported")
    if metadata["compression"] == 17480:
        raise ValueError("HUFF/CDIC MOBI requires conversion to HTML or EPUB before import")
    if metadata["compression"] not in {1, 2}:
        raise ValueError(f"Unsupported MOBI compression: {metadata['compression_name']}")
    data = path.read_bytes()
    offsets = _record_offsets(data)
    chunks = []
    for index in range(1, metadata["text_records"] + 1):
        end = offsets[index + 1] if index + 1 < len(offsets) else len(data)
        chunk = data[offsets[index]:end]
        chunks.append(_palmdoc_decompress(chunk) if metadata["compression"] == 2 else chunk)
    raw = b"".join(chunks)[:metadata["text_length"]]
    return raw.decode(metadata["encoding"], errors="replace"), metadata


def _fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_dictionary_html(document: str) -> list[tuple[str, str, str]]:
    encoded = document.encode("utf-8")
    entries: list[tuple[str, str, str]] = []
    for position, match in enumerate(PAGE_ENTRY_RE.finditer(encoded), start=1):
        headword_html = match.group(1).decode("utf-8", errors="replace")
        body_html = match.group(2).decode("utf-8", errors="replace")
        headword = html_to_text(headword_html).strip(" .,:;*-_")
        normalized = normalize_headword(headword)
        if not normalized or len(headword) > 180 or "\ufffd" in headword:
            continue
        if not re.search(r"[A-Za-z]", headword) or len(headword.split()) > 16:
            continue
        body_text = html_to_text(body_html)
        if len(body_text) < 2:
            continue
        entries.append((headword, body_text, f"entry:{position}"))
    return entries


def ensure_private_dictionary_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS private_dictionaries (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             name TEXT NOT NULL,
             kind TEXT NOT NULL DEFAULT 'bilingual_dictionary',
             format TEXT NOT NULL DEFAULT 'mobi',
             source_path TEXT NOT NULL,
             fingerprint TEXT NOT NULL UNIQUE,
             rights_status TEXT NOT NULL DEFAULT 'private_user_owned',
             priority INTEGER NOT NULL DEFAULT 50,
             enabled INTEGER NOT NULL DEFAULT 1,
             status TEXT NOT NULL DEFAULT 'pending',
             status_detail TEXT NOT NULL DEFAULT '',
             entry_count INTEGER NOT NULL DEFAULT 0,
             imported_at TEXT NOT NULL DEFAULT '',
             updated_at TEXT NOT NULL
           );
           CREATE TABLE IF NOT EXISTS private_dictionary_entries (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             dictionary_id INTEGER NOT NULL,
             normalized TEXT NOT NULL,
             headword TEXT NOT NULL,
             entry_text TEXT NOT NULL,
             source_locator TEXT NOT NULL DEFAULT '',
             created_at TEXT NOT NULL,
             UNIQUE(dictionary_id, normalized, source_locator),
             FOREIGN KEY(dictionary_id) REFERENCES private_dictionaries(id) ON DELETE CASCADE
           );
           CREATE INDEX IF NOT EXISTS idx_private_dictionary_entries_lookup
           ON private_dictionary_entries(normalized, dictionary_id);"""
    )


def register_private_dictionary(
    conn: sqlite3.Connection,
    path: Path,
    *,
    name: str,
    kind: str,
    priority: int,
    now: str,
) -> dict:
    resolved = path.resolve()
    fingerprint = _fingerprint(resolved)
    metadata = inspect_mobi(resolved)
    existing = conn.execute("SELECT id FROM private_dictionaries WHERE fingerprint = ?", (fingerprint,)).fetchone()
    if existing:
        dictionary_id = existing[0]
        conn.execute(
            """UPDATE private_dictionaries SET name = ?, kind = ?, source_path = ?, priority = ?,
                      enabled = 1, updated_at = ? WHERE id = ?""",
            (name, kind, str(resolved), priority, now, dictionary_id),
        )
    else:
        dictionary_id = conn.execute(
            """INSERT INTO private_dictionaries
               (name, kind, format, source_path, fingerprint, priority, status, status_detail, updated_at)
               VALUES (?, ?, 'mobi', ?, ?, ?, 'pending', '', ?)""",
            (name, kind, str(resolved), fingerprint, priority, now),
        ).lastrowid
    try:
        document, metadata = extract_mobi_html(resolved)
        entries = parse_dictionary_html(document)
        if len(entries) < 100:
            raise ValueError(f"Only {len(entries)} valid entries were detected")
        conn.execute("DELETE FROM private_dictionary_entries WHERE dictionary_id = ?", (dictionary_id,))
        conn.executemany(
            """INSERT INTO private_dictionary_entries
               (dictionary_id, normalized, headword, entry_text, source_locator, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ((dictionary_id, normalize_headword(headword), headword, text, locator, now)
             for headword, text, locator in entries),
        )
        conn.execute(
            """UPDATE private_dictionaries SET status = 'ready', status_detail = ?, entry_count = ?,
                      imported_at = ?, updated_at = ? WHERE id = ?""",
            (metadata["compression_name"], len(entries), now, now, dictionary_id),
        )
    except ValueError as exc:
        status = "conversion_required" if "HUFF/CDIC" in str(exc) else "failed"
        conn.execute(
            """UPDATE private_dictionaries SET status = ?, status_detail = ?, entry_count = 0,
                      updated_at = ? WHERE id = ?""",
            (status, str(exc), now, dictionary_id),
        )
    row = conn.execute("SELECT * FROM private_dictionaries WHERE id = ?", (dictionary_id,)).fetchone()
    return dict(row)


def register_private_pdf_source(
    conn: sqlite3.Connection,
    path: Path,
    *,
    name: str,
    pages: int,
    priority: int,
    now: str,
) -> dict:
    resolved = path.resolve()
    with resolved.open("rb") as source:
        if source.read(5) != b"%PDF-":
            raise ValueError("The file is not a PDF document")
    fingerprint = _fingerprint(resolved)
    detail = (
        f"{max(0, int(pages))} pages; image-only scan; OCR and column-order validation required"
    )
    existing = conn.execute("SELECT id FROM private_dictionaries WHERE fingerprint = ?", (fingerprint,)).fetchone()
    if existing:
        dictionary_id = existing[0]
        conn.execute(
            """UPDATE private_dictionaries SET name = ?, kind = 'illustrated_dictionary',
                      format = 'pdf', source_path = ?, priority = ?, enabled = 1,
                      status = 'ocr_required', status_detail = ?, entry_count = 0, updated_at = ?
               WHERE id = ?""",
            (name, str(resolved), priority, detail, now, dictionary_id),
        )
    else:
        dictionary_id = conn.execute(
            """INSERT INTO private_dictionaries
               (name, kind, format, source_path, fingerprint, priority, enabled, status,
                status_detail, entry_count, updated_at)
               VALUES (?, 'illustrated_dictionary', 'pdf', ?, ?, ?, 1, 'ocr_required', ?, 0, ?)""",
            (name, str(resolved), fingerprint, priority, detail, now),
        ).lastrowid
    return dict(conn.execute("SELECT * FROM private_dictionaries WHERE id = ?", (dictionary_id,)).fetchone())


def search_private_entries(conn: sqlite3.Connection, query: str, limit: int = 8) -> list[dict]:
    normalized = normalize_headword(query)
    if not normalized:
        return []
    rows = conn.execute(
        """SELECT e.*, d.name AS source_name, d.kind AS source_kind, d.priority
           FROM private_dictionary_entries e
           JOIN private_dictionaries d ON d.id = e.dictionary_id
           WHERE d.enabled = 1 AND d.status = 'ready'
             AND (e.normalized = ? OR e.normalized LIKE ?)
           ORDER BY CASE WHEN e.normalized = ? THEN 0 ELSE 1 END, d.priority, length(e.headword), e.id
           LIMIT ?""",
        (normalized, f"{normalized}%", normalized, limit),
    ).fetchall()
    if any(row["normalized"] == normalized for row in rows):
        rows = [row for row in rows if row["normalized"] == normalized]
    return [{
        "type": "private",
        "id": row["id"],
        "score": (106 if row["source_kind"] == "bilingual_dictionary" else 74)
                 if row["normalized"] == normalized else 67,
        "matched_by": f"私人词典 · {row['source_name']}",
        "headword": row["headword"],
        "entry_text": row["entry_text"],
        "source_name": row["source_name"],
        "source_kind": row["source_kind"],
        "meaning_zh": _first_chinese_gloss(row["entry_text"]),
        "visibility": "private_local",
    } for row in rows]


def _first_chinese_gloss(entry_text: str) -> str:
    ignored = {"口语", "书面语", "正式", "非正式", "美式", "英式", "作定语", "作表语"}
    for match in re.finditer(r"[\u3400-\u9fff][\u3400-\u9fff、，；：·（）\s]{1,60}", entry_text or ""):
        value = re.sub(r"\s+", "", match.group(0)).strip("，；：")
        if len(re.findall(r"[\u3400-\u9fff]", value)) >= 2 and value not in ignored:
            return value
    return ""


def private_phrase_meanings(conn: sqlite3.Connection, phrases: list[str]) -> dict[str, dict]:
    normalized_phrases = [normalize_headword(value) for value in phrases if value]
    normalized_phrases = list(dict.fromkeys(value for value in normalized_phrases if value))
    if not normalized_phrases:
        return {}
    placeholders = ",".join("?" for _ in normalized_phrases)
    rows = conn.execute(
        f"""SELECT e.normalized, e.entry_text, d.name AS source_name
             FROM private_dictionary_entries e
             JOIN private_dictionaries d ON d.id = e.dictionary_id
             WHERE d.enabled = 1 AND d.status = 'ready' AND d.kind = 'bilingual_dictionary'
               AND e.normalized IN ({placeholders})
             ORDER BY d.priority, e.id""",
        normalized_phrases,
    ).fetchall()
    result = {}
    for row in rows:
        gloss = _first_chinese_gloss(row["entry_text"])
        if gloss and row["normalized"] not in result:
            result[row["normalized"]] = {"meaning_zh": gloss, "source": row["source_name"]}
    return result


def private_dictionary_status(conn: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in conn.execute(
        """SELECT id, name, kind, format, priority, enabled, status, status_detail,
                  entry_count, imported_at, updated_at
           FROM private_dictionaries ORDER BY priority, name"""
    ).fetchall()]
