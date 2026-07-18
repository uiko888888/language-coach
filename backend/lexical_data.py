from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterable


def normalize_term(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def ensure_lexical_data_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS open_lexical_entries (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          normalized TEXT NOT NULL,
          headword TEXT NOT NULL,
          pos TEXT NOT NULL DEFAULT '',
          glosses_json TEXT NOT NULL DEFAULT '[]',
          translations_zh_json TEXT NOT NULL DEFAULT '[]',
          forms_json TEXT NOT NULL DEFAULT '[]',
          pronunciations_json TEXT NOT NULL DEFAULT '[]',
          etymology_text TEXT NOT NULL DEFAULT '',
          synonyms_json TEXT NOT NULL DEFAULT '[]',
          antonyms_json TEXT NOT NULL DEFAULT '[]',
          phrases_json TEXT NOT NULL DEFAULT '[]',
          examples_json TEXT NOT NULL DEFAULT '[]',
          tags_json TEXT NOT NULL DEFAULT '[]',
          source_key TEXT NOT NULL,
          source_record_id TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(source_key, source_record_id, pos)
        );

        CREATE INDEX IF NOT EXISTS idx_open_lexical_entries_normalized
        ON open_lexical_entries(normalized);

        CREATE TABLE IF NOT EXISTS open_bilingual_examples (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_text TEXT NOT NULL,
          target_text TEXT NOT NULL,
          source_lang TEXT NOT NULL DEFAULT 'en',
          target_lang TEXT NOT NULL DEFAULT 'zh',
          source_author TEXT NOT NULL DEFAULT '',
          target_author TEXT NOT NULL DEFAULT '',
          license TEXT NOT NULL,
          source_key TEXT NOT NULL,
          source_record_id TEXT NOT NULL,
          quality_score INTEGER NOT NULL DEFAULT 50,
          created_at TEXT NOT NULL,
          UNIQUE(source_key, source_record_id)
        );

        CREATE INDEX IF NOT EXISTS idx_open_examples_quality
        ON open_bilingual_examples(quality_score DESC, id);

        CREATE VIRTUAL TABLE IF NOT EXISTS open_bilingual_examples_fts USING fts5(
          source_text,
          target_text,
          content='open_bilingual_examples',
          content_rowid='id',
          tokenize='unicode61 remove_diacritics 2'
        );

        CREATE TRIGGER IF NOT EXISTS open_examples_ai AFTER INSERT ON open_bilingual_examples BEGIN
          INSERT INTO open_bilingual_examples_fts(rowid, source_text, target_text)
          VALUES (new.id, new.source_text, new.target_text);
        END;
        CREATE TRIGGER IF NOT EXISTS open_examples_ad AFTER DELETE ON open_bilingual_examples BEGIN
          INSERT INTO open_bilingual_examples_fts(open_bilingual_examples_fts, rowid, source_text, target_text)
          VALUES ('delete', old.id, old.source_text, old.target_text);
        END;
        CREATE TRIGGER IF NOT EXISTS open_examples_au AFTER UPDATE ON open_bilingual_examples BEGIN
          INSERT INTO open_bilingual_examples_fts(open_bilingual_examples_fts, rowid, source_text, target_text)
          VALUES ('delete', old.id, old.source_text, old.target_text);
          INSERT INTO open_bilingual_examples_fts(rowid, source_text, target_text)
          VALUES (new.id, new.source_text, new.target_text);
        END;

        CREATE TABLE IF NOT EXISTS lexical_frequencies (
          normalized TEXT NOT NULL,
          zipf_frequency REAL NOT NULL,
          frequency_band TEXT NOT NULL,
          source_key TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(normalized, source_key)
        );

        CREATE INDEX IF NOT EXISTS idx_lexical_frequencies_rank
        ON lexical_frequencies(zipf_frequency DESC);
        """
    )


def register_dictionary_source(
    conn: sqlite3.Connection,
    *,
    source_key: str,
    name: str,
    version: str,
    license_name: str,
    attribution: str,
    source_url: str,
    checksum: str,
    imported_at: str,
) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO dictionary_sources
           (source_key, name, version, license, attribution, source_url, checksum, imported_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (source_key, name, version, license_name, attribution, source_url, checksum, imported_at),
    )


def _json_values(raw: str) -> list:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return value if isinstance(value, list) else []


def _unique(values: Iterable) -> list:
    result = []
    seen = set()
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, dict) else str(value).casefold()
        if not value or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def frequency_band(zipf: float) -> str:
    if zipf >= 6:
        return "核心高频"
    if zipf >= 5:
        return "日常高频"
    if zipf >= 4:
        return "常见"
    if zipf >= 3:
        return "较少见"
    return "低频/专业"


def _example_rows(conn: sqlite3.Connection, term: str, limit: int) -> list[sqlite3.Row]:
    normalized = normalize_term(term)
    if not normalized:
        return []
    fts_query = '"' + normalized.replace('"', '""') + '"'
    try:
        return conn.execute(
            """SELECT e.*, d.name AS source_name, d.version AS source_version,
                      d.attribution, d.source_url
               FROM open_bilingual_examples_fts f
               JOIN open_bilingual_examples e ON e.id = f.rowid
               JOIN dictionary_sources d ON d.source_key = e.source_key
               WHERE open_bilingual_examples_fts MATCH ?
               ORDER BY e.quality_score DESC, length(e.source_text), e.id
               LIMIT ?""",
            (fts_query, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        return conn.execute(
            """SELECT e.*, d.name AS source_name, d.version AS source_version,
                      d.attribution, d.source_url
               FROM open_bilingual_examples e
               JOIN dictionary_sources d ON d.source_key = e.source_key
               WHERE lower(e.source_text) LIKE ?
               ORDER BY e.quality_score DESC, length(e.source_text), e.id
               LIMIT ?""",
            (f"%{normalized}%", limit),
        ).fetchall()


def lookup_lexical_layers(conn: sqlite3.Connection, term: str, example_limit: int = 8) -> dict:
    normalized = normalize_term(term)
    rows = conn.execute(
        """SELECT e.*, d.name AS source_name, d.version AS source_version,
                  d.license, d.attribution, d.source_url
           FROM open_lexical_entries e
           JOIN dictionary_sources d ON d.source_key = e.source_key
           WHERE e.normalized = ?
           ORDER BY e.id""",
        (normalized,),
    ).fetchall()
    frequency_rows = conn.execute(
        """SELECT f.*, d.name AS source_name, d.version AS source_version,
                  d.license, d.attribution, d.source_url
           FROM lexical_frequencies f
           JOIN dictionary_sources d ON d.source_key = f.source_key
           WHERE f.normalized = ?
           ORDER BY f.zipf_frequency DESC""",
        (normalized,),
    ).fetchall()
    examples = _example_rows(conn, normalized, example_limit)
    entries = []
    for row in rows:
        item = dict(row)
        for field in (
            "glosses", "translations_zh", "forms", "pronunciations", "synonyms",
            "antonyms", "phrases", "examples", "tags",
        ):
            item[field] = _json_values(item.pop(f"{field}_json"))
        entries.append(item)
    return {
        "entries": entries,
        "forms": _unique(value for item in entries for value in item["forms"]),
        "pronunciations": _unique(value for item in entries for value in item["pronunciations"]),
        "glosses": _unique(value for item in entries for value in item["glosses"]),
        "translations_zh": _unique(value for item in entries for value in item["translations_zh"]),
        "synonyms": _unique(value for item in entries for value in item["synonyms"]),
        "antonyms": _unique(value for item in entries for value in item["antonyms"]),
        "phrases": _unique(value for item in entries for value in item["phrases"]),
        "etymologies": _unique(item["etymology_text"] for item in entries),
        "examples": [dict(row) for row in examples],
        "frequencies": [dict(row) for row in frequency_rows],
        "primary_frequency": dict(frequency_rows[0]) if frequency_rows else None,
        "sources": _unique({
            "name": row["source_name"], "version": row["source_version"],
            "license": row["license"], "attribution": row["attribution"], "url": row["source_url"],
        } for row in [*rows, *frequency_rows, *examples]),
    }


def search_open_entries(conn: sqlite3.Connection, query: str, limit: int = 10) -> list[dict]:
    normalized = normalize_term(query)
    if not normalized:
        return []
    rows = conn.execute(
        """SELECT e.*, d.name AS source_name, d.version AS source_version,
                  d.license, d.attribution, d.source_url
           FROM open_lexical_entries e
           JOIN dictionary_sources d ON d.source_key = e.source_key
           WHERE e.normalized = ? OR lower(e.headword) LIKE ? OR e.translations_zh_json LIKE ?
           ORDER BY CASE WHEN e.normalized = ? THEN 0 ELSE 1 END, e.headword, e.pos
           LIMIT ?""",
        (normalized, f"%{normalized}%", f"%{query.strip()}%", normalized, limit),
    ).fetchall()
    results = []
    for row in rows:
        layers = lookup_lexical_layers(conn, row["headword"], example_limit=6)
        results.append({
            "type": "open",
            "id": row["id"],
            "score": 96 if row["normalized"] == normalized else 76,
            "matched_by": row["source_name"],
            "headword": row["headword"],
            "pos": row["pos"],
            "meaning_zh": "；".join(layers["translations_zh"][:4]),
            "core_meaning": layers["glosses"][0] if layers["glosses"] else "",
            "lexical_layers": layers,
            "source_name": row["source_name"],
            "source_version": row["source_version"],
            "license": row["license"],
            "attribution": row["attribution"],
            "source_url": row["source_url"],
        })
    return results
