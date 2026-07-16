from __future__ import annotations

import argparse
import hashlib
import io
import json
import sqlite3
import sys
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import server


SOURCE_KEY = "open-english-wordnet"
SOURCE_NAME = "Open English WordNet"
SOURCE_VERSION = "2025"
SOURCE_LICENSE = "CC BY 4.0"
SOURCE_ATTRIBUTION = "Open English WordNet, Global WordNet Association"
SOURCE_URL = "https://en-word.net/static/english-wordnet-2025-json.zip"
SKIP_SYNSET_FIELDS = {"definition", "example", "ili", "members", "partOfSpeech", "lexfile", "source"}


def download_release(url: str, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "Language-Coach-WordNet-Importer"})
    with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    return target


def file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(archive: zipfile.ZipFile, name: str) -> dict:
    with archive.open(name) as raw, io.TextIOWrapper(raw, encoding="utf-8") as stream:
        return json.load(stream)


def import_wordnet(zip_path: Path, database_path: Path = server.DB_PATH) -> dict:
    zip_path = Path(zip_path)
    database_path = Path(database_path)
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    checksum = file_checksum(zip_path)
    conn = sqlite3.connect(database_path)
    try:
        server.ensure_wordnet_schema(conn)
        with zipfile.ZipFile(zip_path) as archive, conn:
            names = set(archive.namelist())
            synset_files = sorted(
                name for name in names
                if name.endswith(".json") and not name.startswith("entries-") and name != "frames.json"
            )
            entry_files = sorted(name for name in names if name.startswith("entries-") and name.endswith(".json"))
            if not synset_files or not entry_files:
                raise ValueError("Archive does not contain Open English WordNet JSON files")

            conn.execute("DELETE FROM wordnet_relations WHERE source_key = ?", (SOURCE_KEY,))
            conn.execute("DELETE FROM wordnet_lemmas WHERE source_key = ?", (SOURCE_KEY,))
            conn.execute("DELETE FROM wordnet_synsets WHERE source_key = ?", (SOURCE_KEY,))

            synset_count = 0
            relation_count = 0
            for name in synset_files:
                payload = read_json(archive, name)
                synsets = []
                relations = []
                for synset_id, item in payload.items():
                    synsets.append(
                        (
                            synset_id,
                            item.get("partOfSpeech") or "",
                            json.dumps(item.get("definition") or [], ensure_ascii=False),
                            json.dumps(item.get("example") or [], ensure_ascii=False),
                            json.dumps(item.get("members") or [], ensure_ascii=False),
                            item.get("ili") or "",
                            SOURCE_KEY,
                        )
                    )
                    for relation_type, targets in item.items():
                        if relation_type in SKIP_SYNSET_FIELDS or not isinstance(targets, list):
                            continue
                        relations.extend(
                            (synset_id, relation_type, target, SOURCE_KEY)
                            for target in targets
                            if isinstance(target, str)
                        )
                conn.executemany(
                    """INSERT OR REPLACE INTO wordnet_synsets
                       (synset_id, pos, definitions_json, examples_json, members_json, ili, source_key)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    synsets,
                )
                conn.executemany(
                    """INSERT OR IGNORE INTO wordnet_relations
                       (synset_id, relation_type, target_synset_id, source_key)
                       VALUES (?, ?, ?, ?)""",
                    relations,
                )
                synset_count += len(synsets)
                relation_count += len(relations)

            lemma_count = 0
            for name in entry_files:
                payload = read_json(archive, name)
                lemmas = []
                for lemma, pos_items in payload.items():
                    normalized = " ".join(lemma.split()).casefold()
                    for pos, item in pos_items.items():
                        pronunciations = [
                            value.get("value") for value in item.get("pronunciation") or []
                            if isinstance(value, dict) and value.get("value")
                        ]
                        pronunciation_json = json.dumps(list(dict.fromkeys(pronunciations)), ensure_ascii=False)
                        for sense in item.get("sense") or []:
                            synset_id = sense.get("synset")
                            if not synset_id:
                                continue
                            lemmas.append(
                                (
                                    lemma,
                                    normalized,
                                    pos,
                                    synset_id,
                                    sense.get("id") or f"{normalized}:{pos}:{synset_id}",
                                    pronunciation_json,
                                    SOURCE_KEY,
                                )
                            )
                conn.executemany(
                    """INSERT OR REPLACE INTO wordnet_lemmas
                       (lemma, normalized, pos, synset_id, sense_id, pronunciations_json, source_key)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    lemmas,
                )
                lemma_count += len(lemmas)

            conn.execute(
                """INSERT OR REPLACE INTO dictionary_sources
                   (source_key, name, version, license, attribution, source_url, checksum, imported_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    SOURCE_KEY,
                    SOURCE_NAME,
                    SOURCE_VERSION,
                    SOURCE_LICENSE,
                    SOURCE_ATTRIBUTION,
                    SOURCE_URL,
                    checksum,
                    server.utc_now(),
                ),
            )
        return {
            "source": SOURCE_NAME,
            "version": SOURCE_VERSION,
            "checksum": checksum,
            "synsets": synset_count,
            "relations": relation_count,
            "lemmas": lemma_count,
            "database": str(database_path),
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Open English WordNet into Language Coach")
    parser.add_argument("--zip", type=Path, default=ROOT / "artifacts" / "english-wordnet-2025-json.zip")
    parser.add_argument("--database", type=Path, default=server.DB_PATH)
    parser.add_argument("--download", action="store_true", help="Download the official 2025 JSON release first")
    args = parser.parse_args()
    if args.download:
        download_release(SOURCE_URL, args.zip)
    result = import_wordnet(args.zip, args.database)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
