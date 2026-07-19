from __future__ import annotations

import json
import sqlite3
from typing import Any


DEFAULT_MINIMUM_COUNTS = {
    "kaikki-english": 25_000,
    "tatoeba-en-zh": 25_000,
    "wordfreq": 25_000,
}

DEFAULT_PROBES = {
    "polysemy": ["set", "run", "cast", "charge", "issue"],
    "phrases": ["carry out", "look up", "in terms of", "as a result"],
    "chinese": ["检查", "影响", "支持", "处理", "提升"],
    "examples": ["set", "run", "cast", "charge", "issue"],
    "frequency_pairs": [["the", "inspect"], ["make", "spectroscopy"], ["work", "photosynthesis"]],
}
MISSING_ATTRIBUTION_VALUES = {"", r"\N"}


def _json_list(raw: str) -> list:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return value if isinstance(value, list) else []


def _coverage(items: list[dict[str, Any]]) -> dict:
    total = len(items)
    passed = sum(1 for item in items if item["passed"])
    return {
        "passed": passed,
        "total": total,
        "ratio": round(passed / total, 3) if total else 1.0,
        "items": items,
    }


def _has_attribution(value: Any) -> bool:
    return str(value or "").strip() not in MISSING_ATTRIBUTION_VALUES


def _source_count(conn: sqlite3.Connection, source_key: str) -> int:
    if source_key == "kaikki-english":
        query = "SELECT COUNT(*) FROM open_lexical_entries WHERE source_key = ?"
    elif source_key == "tatoeba-en-zh":
        query = "SELECT COUNT(*) FROM open_bilingual_examples WHERE source_key = ?"
    else:
        query = "SELECT COUNT(*) FROM lexical_frequencies WHERE source_key = ?"
    return int(conn.execute(query, (source_key,)).fetchone()[0])


def _attributed_example(conn: sqlite3.Connection, term: str):
    query = '"' + str(term).casefold().replace('"', '""') + '"'
    try:
        return conn.execute(
            """SELECT e.source_author, e.target_author, e.license
               FROM open_bilingual_examples_fts f
               JOIN open_bilingual_examples e ON e.id = f.rowid
               WHERE open_bilingual_examples_fts MATCH ? AND e.source_key = 'tatoeba-en-zh'
               ORDER BY e.quality_score DESC LIMIT 1""",
            (query,),
        ).fetchone()
    except sqlite3.OperationalError:
        return conn.execute(
            """SELECT source_author, target_author, license FROM open_bilingual_examples
               WHERE source_key = 'tatoeba-en-zh' AND lower(source_text) LIKE ?
               ORDER BY quality_score DESC LIMIT 1""",
            (f"%{str(term).casefold()}%",),
        ).fetchone()


def audit_dictionary_data(
    conn: sqlite3.Connection,
    probes: dict[str, list] | None = None,
    minimum_counts: dict[str, int] | None = None,
) -> dict:
    probes = {**DEFAULT_PROBES, **(probes or {})}
    minimum_counts = {**DEFAULT_MINIMUM_COUNTS, **(minimum_counts or {})}
    source_rows = {
        row["source_key"] if isinstance(row, sqlite3.Row) else row[0]: dict(row) if isinstance(row, sqlite3.Row) else {
            "source_key": row[0], "name": row[1], "version": row[2], "license": row[3],
            "attribution": row[4], "source_url": row[5], "checksum": row[6], "imported_at": row[7],
        }
        for row in conn.execute(
            """SELECT source_key, name, version, license, attribution, source_url, checksum, imported_at
               FROM dictionary_sources"""
        ).fetchall()
    }
    sources = []
    for source_key, minimum in minimum_counts.items():
        metadata = source_rows.get(source_key) or {}
        count = _source_count(conn, source_key)
        metadata_complete = all(metadata.get(field) for field in ("version", "license", "attribution", "source_url", "checksum"))
        sources.append({
            "source_key": source_key,
            "count": count,
            "minimum": int(minimum),
            "metadata_complete": metadata_complete,
            "passed": count >= int(minimum) and metadata_complete,
        })

    polysemy = []
    for term in probes["polysemy"]:
        rows = conn.execute(
            "SELECT pos, glosses_json FROM open_lexical_entries WHERE normalized = ?", (str(term).casefold(),)
        ).fetchall()
        parts = {row[0] for row in rows if row[0]}
        glosses = {gloss for row in rows for gloss in _json_list(row[1]) if gloss}
        polysemy.append({"probe": term, "parts_of_speech": len(parts), "glosses": len(glosses), "passed": len(parts) >= 2 or len(glosses) >= 3})

    phrases = []
    for phrase in probes["phrases"]:
        normalized = str(phrase).casefold()
        found = conn.execute(
            """SELECT 1 FROM open_lexical_entries
               WHERE normalized = ? OR lower(phrases_json) LIKE ? LIMIT 1""",
            (normalized, f'%"word": "{normalized}"%'),
        ).fetchone()
        phrases.append({"probe": phrase, "passed": bool(found)})

    chinese = []
    for query in probes["chinese"]:
        found = conn.execute(
            "SELECT 1 FROM open_lexical_entries WHERE translations_zh_json LIKE ? LIMIT 1", (f"%{query}%",)
        ).fetchone()
        chinese.append({"probe": query, "passed": bool(found)})

    examples = []
    for term in probes["examples"]:
        row = _attributed_example(conn, term)
        attributed = bool(row and all(_has_attribution(value) for value in row))
        examples.append({
            "probe": term,
            "attributed": attributed,
            "passed": attributed,
        })

    frequency_pairs = []
    for common, uncommon in probes["frequency_pairs"]:
        rows = dict(conn.execute(
            """SELECT normalized, zipf_frequency FROM lexical_frequencies
               WHERE source_key = 'wordfreq' AND normalized IN (?, ?)""",
            (str(common).casefold(), str(uncommon).casefold()),
        ).fetchall())
        passed = common.casefold() in rows and uncommon.casefold() in rows and rows[common.casefold()] > rows[uncommon.casefold()]
        frequency_pairs.append({
            "probe": f"{common}>{uncommon}", "common": rows.get(common.casefold()),
            "uncommon": rows.get(uncommon.casefold()), "passed": passed,
        })

    groups = {
        "polysemy": _coverage(polysemy),
        "phrases": _coverage(phrases),
        "chinese_reverse": _coverage(chinese),
        "attributed_examples": _coverage(examples),
        "frequency_order": _coverage(frequency_pairs),
    }
    source_ready = all(item["passed"] for item in sources)
    probe_ready = all(group["ratio"] >= 0.6 for group in groups.values())
    passed = sum(group["passed"] for group in groups.values())
    total = sum(group["total"] for group in groups.values())
    return {
        "ready": source_ready and probe_ready,
        "source_ready": source_ready,
        "probe_ready": probe_ready,
        "passed": passed,
        "total": total,
        "sources": sources,
        "groups": groups,
        "policy": {"minimum_group_ratio": 0.6, "minimum_counts": minimum_counts},
    }
