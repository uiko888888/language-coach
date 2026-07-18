import argparse
import gzip
import hashlib
import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import server
from backend.lexical_data import ensure_lexical_data_schema, normalize_term, register_dictionary_source


SOURCE_KEY = "kaikki-english"
SOURCE_NAME = "Kaikki English Wiktionary extract"
SOURCE_LICENSE = "CC BY-SA 4.0 / GFDL"
SOURCE_ATTRIBUTION = "Wiktionary contributors; machine-readable extract by Kaikki.org"
SOURCE_URL = "https://kaikki.org/dictionary/English/index.html"


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def open_text(path: Path):
    return gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else path.open(encoding="utf-8")


def relation_words(values) -> list[dict]:
    result = []
    for value in values or []:
        if isinstance(value, str):
            result.append({"word": value})
        elif isinstance(value, dict) and value.get("word"):
            result.append({key: value[key] for key in ("word", "sense", "tags", "english") if key in value})
    return result


def parse_record(item: dict, line_number: int) -> tuple | None:
    word = str(item.get("word") or "").strip()
    if not word or item.get("lang_code") not in {None, "en"}:
        return None
    senses = [value for value in item.get("senses") or [] if isinstance(value, dict)]
    glosses = []
    translations_zh = []
    examples = []
    synonyms = relation_words(item.get("synonyms"))
    antonyms = relation_words(item.get("antonyms"))
    tags = list(item.get("tags") or [])
    for sense in senses:
        glosses.extend(value for value in sense.get("glosses") or [] if isinstance(value, str))
        translations_zh.extend(
            value.get("word") for value in sense.get("translations") or []
            if isinstance(value, dict) and value.get("lang_code") in {"zh", "cmn"} and value.get("word")
        )
        examples.extend(
            value.get("text") for value in sense.get("examples") or []
            if isinstance(value, dict) and value.get("text")
        )
        synonyms.extend(relation_words(sense.get("synonyms")))
        antonyms.extend(relation_words(sense.get("antonyms")))
        tags.extend(value for value in sense.get("tags") or [] if isinstance(value, str))
    translations_zh.extend(
        value.get("word") for value in item.get("translations") or []
        if isinstance(value, dict) and value.get("lang_code") in {"zh", "cmn"} and value.get("word")
    )
    forms = [
        {key: value[key] for key in ("form", "tags", "source") if key in value}
        for value in item.get("forms") or [] if isinstance(value, dict) and value.get("form")
    ]
    pronunciations = [
        {key: value[key] for key in ("ipa", "enpr", "tags", "audio") if key in value}
        for value in item.get("sounds") or [] if isinstance(value, dict) and (value.get("ipa") or value.get("enpr"))
    ]
    phrases = [*relation_words(item.get("derived")), *relation_words(item.get("related"))]
    source_record_id = str(item.get("id") or f"{normalize_term(word)}:{item.get('pos') or ''}:{item.get('etymology_number') or 0}:{line_number}")
    unique = lambda values: list(dict.fromkeys(value for value in values if value))
    return (
        normalize_term(word), word, str(item.get("pos") or ""),
        json.dumps(unique(glosses), ensure_ascii=False),
        json.dumps(unique(translations_zh), ensure_ascii=False),
        json.dumps(forms, ensure_ascii=False),
        json.dumps(pronunciations, ensure_ascii=False),
        str(item.get("etymology_text") or ""),
        json.dumps(synonyms, ensure_ascii=False),
        json.dumps(antonyms, ensure_ascii=False),
        json.dumps(phrases, ensure_ascii=False),
        json.dumps(unique(examples), ensure_ascii=False),
        json.dumps(unique(tags), ensure_ascii=False),
        SOURCE_KEY, source_record_id, server.utc_now(),
    )


def import_kaikki(path: Path, database: Path = server.DB_PATH, limit: int = 0, words: set[str] | None = None) -> dict:
    path = Path(path)
    database = Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    wanted = {normalize_term(value) for value in words or set() if normalize_term(value)}
    conn = sqlite3.connect(database)
    try:
        server.ensure_wordnet_schema(conn)
        ensure_lexical_data_schema(conn)
        imported = scanned = 0
        batch = []
        with open_text(path) as stream, conn:
            conn.execute("DELETE FROM open_lexical_entries WHERE source_key = ?", (SOURCE_KEY,))
            for line_number, line in enumerate(stream, 1):
                scanned += 1
                item = json.loads(line)
                if wanted and normalize_term(item.get("word", "")) not in wanted:
                    continue
                row = parse_record(item, line_number)
                if not row:
                    continue
                batch.append(row)
                imported += 1
                if len(batch) >= 1000:
                    conn.executemany(
                        """INSERT OR REPLACE INTO open_lexical_entries
                           (normalized, headword, pos, glosses_json, translations_zh_json, forms_json,
                            pronunciations_json, etymology_text, synonyms_json, antonyms_json, phrases_json,
                            examples_json, tags_json, source_key, source_record_id, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        batch,
                    )
                    batch.clear()
                if limit and imported >= limit:
                    break
            if batch:
                conn.executemany(
                    """INSERT OR REPLACE INTO open_lexical_entries
                       (normalized, headword, pos, glosses_json, translations_zh_json, forms_json,
                        pronunciations_json, etymology_text, synonyms_json, antonyms_json, phrases_json,
                        examples_json, tags_json, source_key, source_record_id, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    batch,
                )
            register_dictionary_source(
                conn, source_key=SOURCE_KEY, name=SOURCE_NAME, version="rolling",
                license_name=SOURCE_LICENSE, attribution=SOURCE_ATTRIBUTION, source_url=SOURCE_URL,
                checksum=checksum(path), imported_at=server.utc_now(),
            )
        return {"source": SOURCE_NAME, "scanned": scanned, "imported": imported, "database": str(database)}
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import selected Kaikki/Wiktionary English JSONL records")
    parser.add_argument("--jsonl", type=Path, required=True)
    parser.add_argument("--database", type=Path, default=server.DB_PATH)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--words", type=Path, help="Optional UTF-8 file with one target word per line")
    args = parser.parse_args()
    words = set(args.words.read_text(encoding="utf-8").splitlines()) if args.words else None
    print(json.dumps(import_kaikki(args.jsonl, args.database, args.limit, words), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
