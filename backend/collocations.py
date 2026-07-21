from __future__ import annotations

import re
import sqlite3
from collections import defaultdict


TOKEN = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")
BOUNDARY_WORDS = {
    "a", "an", "the", "this", "that", "these", "those", "my", "your", "his", "her", "its", "our", "their",
    "i", "you", "he", "she", "we", "they", "me", "him", "us", "them",
    "and", "or", "but", "if", "because", "while", "when", "who", "which", "what", "there", "here", "to",
}
USEFUL_PARTICLES = {"about", "against", "as", "at", "by", "for", "from", "in", "into", "of", "on", "over", "to", "with"}


def _sentences(text: str) -> list[str]:
    return [value.strip() for value in re.split(r"(?<=[.!?])\s+|\n+", text or "") if value.strip()]


def _open_examples(conn: sqlite3.Connection, term: str, limit: int) -> list[dict]:
    query = '"' + term.replace('"', '""') + '"'
    try:
        rows = conn.execute(
            """SELECT e.source_text, e.target_text, e.source_record_id, d.name AS source_name
               FROM open_bilingual_examples_fts f
               JOIN open_bilingual_examples e ON e.id = f.rowid
               JOIN dictionary_sources d ON d.source_key = e.source_key
               WHERE open_bilingual_examples_fts MATCH ?
               ORDER BY e.quality_score DESC, e.id LIMIT ?""",
            (query, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = conn.execute(
            """SELECT e.source_text, e.target_text, e.source_record_id, d.name AS source_name
               FROM open_bilingual_examples e
               JOIN dictionary_sources d ON d.source_key = e.source_key
               WHERE lower(e.source_text) LIKE ? ORDER BY e.quality_score DESC, e.id LIMIT ?""",
            (f"%{term.casefold()}%", limit),
        ).fetchall()
    return [
        {
            "text": row["source_text"], "translation_zh": row["target_text"],
            "source": row["source_name"], "source_key": f"example:{row['source_record_id']}",
        }
        for row in rows
    ]


def _public_article_examples(conn: sqlite3.Connection, term: str, limit: int) -> list[dict]:
    rows = conn.execute(
        """SELECT id, title, source, body FROM articles
           WHERE visibility = 'public' AND lower(body) LIKE ?
           ORDER BY updated_at DESC, id DESC LIMIT 100""",
        (f"%{term.casefold()}%",),
    ).fetchall()
    pattern = re.compile(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", re.IGNORECASE)
    examples = []
    for row in rows:
        for sentence in _sentences(row["body"]):
            if not pattern.search(sentence):
                continue
            examples.append({
                "text": sentence, "translation_zh": "", "source": row["source"],
                "source_key": f"article:{row['id']}", "article_id": row["id"], "article_title": row["title"],
            })
            if len(examples) >= limit:
                return examples
    return examples


def open_corpus_examples(conn: sqlite3.Connection, term: str, limit: int = 240) -> list[dict]:
    clean = re.sub(r"\s+", " ", term).strip().casefold()
    if not clean or len(clean.split()) > 3:
        return []
    values = [*_open_examples(conn, clean, limit), *_public_article_examples(conn, clean, limit)]
    unique = []
    seen = set()
    for item in values:
        key = re.sub(r"\s+", " ", item["text"]).strip().casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:limit]


def _phrase_candidates(term: str, sentence: str) -> set[str]:
    tokens = TOKEN.findall(sentence)
    lowered = [value.casefold() for value in tokens]
    result = set()
    for index, value in enumerate(lowered):
        if value != term:
            continue
        if index and lowered[index - 1] not in BOUNDARY_WORDS:
            result.add(f"{lowered[index - 1]} {term}")
        if index + 1 < len(tokens) and lowered[index + 1] not in BOUNDARY_WORDS:
            result.add(f"{term} {lowered[index + 1]}")
        if index + 1 < len(tokens) and lowered[index + 1] in USEFUL_PARTICLES:
            result.add(f"{term} {lowered[index + 1]}")
        for start, end in ((index - 1, index + 2), (index, index + 3)):
            if start < 0 or end > len(tokens):
                continue
            phrase_tokens = lowered[start:end]
            if phrase_tokens[0] in BOUNDARY_WORDS or phrase_tokens[-1] in BOUNDARY_WORDS:
                continue
            result.add(" ".join(phrase_tokens))
    return result


def corpus_collocations(
    conn: sqlite3.Connection,
    term: str,
    registered_phrases: list[str] | None = None,
    curated_patterns: list[str] | None = None,
    limit: int = 10,
) -> dict:
    clean = re.sub(r"\s+", " ", term).strip().casefold()
    if not clean or " " in clean:
        return {"items": [], "examples_scanned": 0, "sources": []}
    examples = open_corpus_examples(conn, clean)
    phrase_evidence: dict[str, list[dict]] = defaultdict(list)
    registered = {
        re.sub(r"\s+", " ", str(value.get("word") if isinstance(value, dict) else value)).strip().casefold()
        for value in (registered_phrases or [])
    }
    registered = {
        value for value in registered
        if " " in value
        and re.search(rf"(?<![A-Za-z]){re.escape(clean)}(?![A-Za-z])", value)
        and value.split()[0] not in BOUNDARY_WORDS
        and value.split()[-1] not in BOUNDARY_WORDS
    }
    curated = [re.sub(r"\s+", " ", value).strip() for value in (curated_patterns or []) if value.strip()]
    for example in examples:
        normalized_sentence = re.sub(r"\s+", " ", example["text"]).strip().casefold()
        candidates = _phrase_candidates(clean, example["text"])
        candidates.update(value for value in registered if re.search(rf"(?<![A-Za-z]){re.escape(value)}(?![A-Za-z])", normalized_sentence))
        for phrase in candidates:
            phrase_evidence[phrase].append(example)
    items = []
    for phrase, evidence in phrase_evidence.items():
        source_names = {item["source"] for item in evidence}
        word_count = len(phrase.split())
        repeated = len(evidence) >= (2 if word_count == 2 else 3)
        accepted = repeated or (phrase in registered and bool(evidence))
        if not accepted:
            continue
        items.append({
            "phrase": phrase, "meaning_zh": "", "source": "开放语料",
            "observed_count": len(evidence), "source_count": len(source_names),
            "confidence": "重复观察" if repeated else "词典收录并有语料例证",
            "contexts": evidence[:2], "synonyms": [], "antonyms": [],
        })
    for pattern in curated:
        key = pattern.casefold()
        evidence = phrase_evidence.get(key, [])
        items.append({
            "phrase": pattern, "meaning_zh": "", "source": "本地整理",
            "observed_count": len(evidence), "source_count": len({item["source"] for item in evidence}),
            "confidence": "人工整理基础组", "contexts": evidence[:2], "synonyms": [], "antonyms": [],
        })
    deduplicated = {}
    for item in items:
        key = item["phrase"].casefold()
        current = deduplicated.get(key)
        if not current or item["source"] == "本地整理" or item["observed_count"] > current["observed_count"]:
            deduplicated[key] = item
    ranked = sorted(
        deduplicated.values(),
        key=lambda item: (item["source"] != "本地整理", -item["observed_count"], len(item["phrase"]), item["phrase"]),
    )
    return {
        "items": ranked[:limit], "examples_scanned": len(examples),
        "sources": sorted({item["source"] for item in examples}),
    }
