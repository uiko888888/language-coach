from __future__ import annotations

import hashlib
import html
import gzip
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


def _source_set_fingerprint(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.casefold().encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _stardict_metadata(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines or lines[0].strip() != "StarDict's dict ifo file":
        raise ValueError("Invalid StarDict .ifo header")
    metadata = {}
    for line in lines[1:]:
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        metadata[key.strip().casefold()] = value.strip()
    if metadata.get("version") not in {"2.4.2", "3.0.0"}:
        raise ValueError("Unsupported StarDict version")
    try:
        word_count = int(metadata["wordcount"])
        index_size = int(metadata["idxfilesize"])
    except (KeyError, ValueError) as exc:
        raise ValueError("StarDict .ifo is missing valid wordcount/idxfilesize") from exc
    if word_count < 1 or index_size < 1:
        raise ValueError("StarDict wordcount and idxfilesize must be positive")
    metadata["wordcount"] = str(word_count)
    metadata["idxfilesize"] = str(index_size)
    return metadata


def _stardict_companion(ifo_path: Path, suffixes: tuple[str, ...], required: bool = True) -> Path | None:
    stem = ifo_path.with_suffix("")
    for suffix in suffixes:
        candidate = Path(str(stem) + suffix)
        if candidate.is_file():
            return candidate
    if required:
        raise ValueError(f"Missing StarDict companion file: {' or '.join(suffixes)}")
    return None


def _read_stardict_index(path: Path, offset_bits: int) -> tuple[list[tuple[str, int, int]], int]:
    opener = gzip.open if path.suffix.casefold() == ".gz" else open
    with opener(path, "rb") as source:
        data = source.read()
    records = []
    cursor = 0
    offset_bytes = 8 if offset_bits == 64 else 4
    trailer_size = offset_bytes + 4
    while cursor < len(data):
        separator = data.find(b"\0", cursor)
        if separator < 0 or separator + 1 + trailer_size > len(data):
            raise ValueError("Malformed StarDict index record")
        try:
            headword = data[cursor:separator].decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise ValueError("StarDict index headword is not valid UTF-8") from exc
        cursor = separator + 1
        offset = int.from_bytes(data[cursor:cursor + offset_bytes], "big")
        size = int.from_bytes(data[cursor + offset_bytes:cursor + trailer_size], "big")
        cursor += trailer_size
        if not headword or size < 1 or size > 4 * 1024 * 1024:
            raise ValueError("StarDict index contains an invalid headword or entry size")
        records.append((headword, offset, size))
    return records, len(data)


def _decode_stardict_field(field_type: str, data: bytes) -> str:
    if field_type.isupper():
        return ""
    try:
        decoded = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("StarDict entry is not valid UTF-8") from exc
    if field_type.casefold() in {"g", "h", "x"}:
        return html_to_text(decoded)
    return "".join(char for char in decoded if char in "\n\t" or ord(char) >= 32).strip()


def _decode_stardict_entry(data: bytes, sequence: str) -> str:
    fields: list[str] = []
    cursor = 0
    types = list(sequence)
    if not types:
        while cursor < len(data):
            field_type = chr(data[cursor])
            cursor += 1
            if field_type.isupper():
                if cursor + 4 > len(data):
                    raise ValueError("Malformed StarDict typed field length")
                size = int.from_bytes(data[cursor:cursor + 4], "big")
                cursor += 4
                payload = data[cursor:cursor + size]
                cursor += size
            else:
                end = data.find(b"\0", cursor)
                if end < 0:
                    end = len(data)
                payload = data[cursor:end]
                cursor = min(len(data), end + 1)
            fields.append(_decode_stardict_field(field_type, payload))
    else:
        for index, field_type in enumerate(types):
            if field_type.isupper():
                if cursor + 4 > len(data):
                    raise ValueError("Malformed StarDict field length")
                size = int.from_bytes(data[cursor:cursor + 4], "big")
                cursor += 4
                payload = data[cursor:cursor + size]
                cursor += size
            elif index == len(types) - 1:
                payload = data[cursor:]
                cursor = len(data)
            else:
                end = data.find(b"\0", cursor)
                if end < 0:
                    raise ValueError("Malformed StarDict null-terminated field")
                payload = data[cursor:end]
                cursor = end + 1
            fields.append(_decode_stardict_field(field_type, payload))
    return "\n\n".join(value for value in fields if value).strip()


def _read_stardict_synonyms(path: Path | None, word_count: int) -> list[tuple[str, int]]:
    if not path:
        return []
    data = path.read_bytes()
    synonyms = []
    cursor = 0
    while cursor < len(data):
        separator = data.find(b"\0", cursor)
        if separator < 0 or separator + 5 > len(data):
            raise ValueError("Malformed StarDict synonym record")
        try:
            synonym = data[cursor:separator].decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise ValueError("StarDict synonym is not valid UTF-8") from exc
        target = int.from_bytes(data[separator + 1:separator + 5], "big")
        if not synonym or target >= word_count:
            raise ValueError("StarDict synonym target is out of range")
        synonyms.append((synonym, target))
        cursor = separator + 5
    return synonyms


def register_private_stardict(
    conn: sqlite3.Connection,
    ifo_path: Path,
    *,
    name: str,
    kind: str,
    priority: int,
    now: str,
) -> dict:
    resolved_ifo = ifo_path.resolve()
    metadata = _stardict_metadata(resolved_ifo)
    idx_path = _stardict_companion(resolved_ifo, (".idx", ".idx.gz"))
    dict_path = _stardict_companion(resolved_ifo, (".dict", ".dict.dz"))
    syn_path = _stardict_companion(resolved_ifo, (".syn",), required=False)
    source_paths = [resolved_ifo, idx_path, dict_path, *([syn_path] if syn_path else [])]
    fingerprint = _source_set_fingerprint(source_paths)
    offset_bits = int(metadata.get("idxoffsetbits", "32"))
    if offset_bits not in {32, 64}:
        raise ValueError("StarDict idxoffsetbits must be 32 or 64")
    records, decoded_index_size = _read_stardict_index(idx_path, offset_bits)
    if len(records) != int(metadata["wordcount"]):
        raise ValueError(f"StarDict wordcount mismatch: expected {metadata['wordcount']}, found {len(records)}")
    if decoded_index_size != int(metadata["idxfilesize"]):
        raise ValueError("StarDict idxfilesize does not match the .idx file")
    synonyms = _read_stardict_synonyms(syn_path, len(records))
    if "synwordcount" in metadata and int(metadata["synwordcount"]) != len(synonyms):
        raise ValueError("StarDict synwordcount does not match the .syn file")
    if dict_path.name.casefold().endswith(".dict.dz") and any(
        records[index][1] < records[index - 1][1] for index in range(1, len(records))
    ):
        raise ValueError("Compressed StarDict entries must use nondecreasing offsets for low-memory import")
    sequence = metadata.get("sametypesequence", "")
    existing = conn.execute(
        """SELECT id FROM private_dictionaries
           WHERE fingerprint = ? OR (format = 'stardict' AND source_path = ?)
           ORDER BY CASE WHEN fingerprint = ? THEN 0 ELSE 1 END LIMIT 1""",
        (fingerprint, str(resolved_ifo), fingerprint),
    ).fetchone()
    if existing:
        dictionary_id = existing[0]
        conn.execute(
            """UPDATE private_dictionaries SET name = ?, kind = ?, format = 'stardict', source_path = ?,
                      fingerprint = ?, priority = ?, enabled = 1, status = 'pending', status_detail = '', updated_at = ?
               WHERE id = ?""",
            (name, kind, str(resolved_ifo), fingerprint, priority, now, dictionary_id),
        )
    else:
        dictionary_id = conn.execute(
            """INSERT INTO private_dictionaries
               (name, kind, format, source_path, fingerprint, priority, enabled, status, updated_at)
               VALUES (?, ?, 'stardict', ?, ?, ?, 1, 'pending', ?)""",
            (name, kind, str(resolved_ifo), fingerprint, priority, now),
        ).lastrowid
    conn.execute("DELETE FROM private_dictionary_entries WHERE dictionary_id = ?", (dictionary_id,))
    opener = gzip.open if dict_path.name.casefold().endswith(".dict.dz") else open
    with opener(dict_path, "rb") as dictionary:
        for index, (headword, offset, size) in enumerate(records):
            dictionary.seek(offset)
            payload = dictionary.read(size)
            if len(payload) != size:
                raise ValueError("StarDict entry offset or size exceeds dictionary data")
            entry_text = _decode_stardict_entry(payload, sequence)
            if not entry_text:
                raise ValueError("StarDict contains an empty decoded entry")
            conn.execute(
                """INSERT INTO private_dictionary_entries
                   (dictionary_id, normalized, headword, entry_text, source_locator, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (dictionary_id, normalize_headword(headword), headword, entry_text, f"entry:{index}", now),
            )
    for synonym, target in synonyms:
        target_row = conn.execute(
            """SELECT entry_text FROM private_dictionary_entries
               WHERE dictionary_id = ? AND source_locator = ?""",
            (dictionary_id, f"entry:{target}"),
        ).fetchone()
        if not target_row:
            raise ValueError("StarDict synonym target entry is unavailable")
        conn.execute(
            """INSERT OR IGNORE INTO private_dictionary_entries
               (dictionary_id, normalized, headword, entry_text, source_locator, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (dictionary_id, normalize_headword(synonym), synonym, target_row[0], f"syn:{target}:{synonym}", now),
        )
    count = len(records) + len(synonyms)
    details = f"StarDict {metadata['version']}; {len(records)} entries; {len(synonyms)} synonyms; {sequence or 'typed fields'}"
    conn.execute(
        """UPDATE private_dictionaries SET status = 'ready', status_detail = ?, entry_count = ?,
                  imported_at = ?, updated_at = ? WHERE id = ?""",
        (details, count, now, now, dictionary_id),
    )
    return dict(conn.execute("SELECT * FROM private_dictionaries WHERE id = ?", (dictionary_id,)).fetchone())


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


def update_private_dictionary(
    conn: sqlite3.Connection,
    dictionary_id: int,
    *,
    enabled: bool | None = None,
    priority: int | None = None,
    now: str,
) -> dict | None:
    row = conn.execute("SELECT * FROM private_dictionaries WHERE id = ?", (dictionary_id,)).fetchone()
    if not row:
        return None
    next_enabled = int(bool(enabled)) if enabled is not None else row["enabled"]
    next_priority = max(0, min(999, int(priority))) if priority is not None else row["priority"]
    conn.execute(
        "UPDATE private_dictionaries SET enabled = ?, priority = ?, updated_at = ? WHERE id = ?",
        (next_enabled, next_priority, now, dictionary_id),
    )
    return dict(conn.execute("SELECT * FROM private_dictionaries WHERE id = ?", (dictionary_id,)).fetchone())


def remove_private_dictionary_index(conn: sqlite3.Connection, dictionary_id: int) -> bool:
    if not conn.execute("SELECT 1 FROM private_dictionaries WHERE id = ?", (dictionary_id,)).fetchone():
        return False
    conn.execute("DELETE FROM private_dictionary_entries WHERE dictionary_id = ?", (dictionary_id,))
    conn.execute("DELETE FROM private_dictionaries WHERE id = ?", (dictionary_id,))
    return True
