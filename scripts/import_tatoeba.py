import argparse
import bz2
import hashlib
import io
import json
import sqlite3
import sys
import tarfile
import tempfile
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import server
from backend.lexical_data import ensure_lexical_data_schema, register_dictionary_source


SOURCE_KEY = "tatoeba-en-zh"
SOURCE_NAME = "Tatoeba English-Chinese sentence pairs"
SOURCE_LICENSE = "CC BY 2.0 FR"
SOURCE_ATTRIBUTION = "Tatoeba contributors; sentence-level authors retained"
SOURCE_URL = "https://tatoeba.org/en/downloads"


@contextmanager
def open_text(path: Path):
    if path.name.endswith((".tar.bz2", ".tbz2")):
        with tarfile.open(path, "r:bz2") as archive:
            member = next((value for value in archive.getmembers() if value.isfile()), None)
            if not member:
                raise ValueError(f"Archive contains no data file: {path}")
            raw = archive.extractfile(member)
            if raw is None:
                raise ValueError(f"Cannot read archive member: {member.name}")
            with raw, io.TextIOWrapper(raw, encoding="utf-8") as stream:
                yield stream
    elif path.suffix == ".bz2":
        with bz2.open(path, "rt", encoding="utf-8") as stream:
            yield stream
    else:
        with path.open(encoding="utf-8") as stream:
            yield stream


def files_checksum(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest()


def sentence_quality(english: str, chinese: str) -> int:
    score = 50
    english_words = english.split()
    if 5 <= len(english_words) <= 24:
        score += 20
    if 8 <= len(chinese) <= 70:
        score += 15
    if english[-1:] in ".!?" and chinese[-1:] in "。！？.!?":
        score += 5
    if any(char.isdigit() for char in english + chinese):
        score -= 5
    return max(0, min(100, score))


def import_tatoeba(
    sentences_path: Path,
    links_path: Path,
    database: Path = server.DB_PATH,
    limit: int = 0,
) -> dict:
    sentences_path, links_path, database = Path(sentences_path), Path(links_path), Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp_dir:
        staging = sqlite3.connect(Path(temp_dir) / "tatoeba-staging.sqlite")
        staging.executescript(
            """CREATE TABLE sentences (id INTEGER PRIMARY KEY, lang TEXT, text TEXT, author TEXT);
               CREATE TABLE links (english_id INTEGER, chinese_id INTEGER, PRIMARY KEY(english_id, chinese_id));"""
        )
        sentence_batch = []
        with open_text(sentences_path) as stream, staging:
            for line in stream:
                fields = line.rstrip("\n").split("\t")
                if len(fields) < 4 or fields[1] not in {"eng", "cmn", "zho"}:
                    continue
                sentence_batch.append((int(fields[0]), fields[1], fields[2].strip(), fields[3].strip()))
                if len(sentence_batch) >= 5000:
                    staging.executemany("INSERT OR IGNORE INTO sentences VALUES (?, ?, ?, ?)", sentence_batch)
                    sentence_batch.clear()
            if sentence_batch:
                staging.executemany("INSERT OR IGNORE INTO sentences VALUES (?, ?, ?, ?)", sentence_batch)
        english_ids = {row[0] for row in staging.execute("SELECT id FROM sentences WHERE lang = 'eng'")}
        chinese_ids = {row[0] for row in staging.execute("SELECT id FROM sentences WHERE lang IN ('cmn', 'zho')")}
        link_batch = []
        with open_text(links_path) as stream, staging:
            for line in stream:
                fields = line.rstrip("\n").split("\t")
                if len(fields) < 2:
                    continue
                left, right = int(fields[0]), int(fields[1])
                pair = (left, right) if left in english_ids and right in chinese_ids else (right, left) if right in english_ids and left in chinese_ids else None
                if pair:
                    link_batch.append(pair)
                if len(link_batch) >= 5000:
                    staging.executemany("INSERT OR IGNORE INTO links VALUES (?, ?)", link_batch)
                    link_batch.clear()
            if link_batch:
                staging.executemany("INSERT OR IGNORE INTO links VALUES (?, ?)", link_batch)

        target = sqlite3.connect(database)
        try:
            server.ensure_wordnet_schema(target)
            ensure_lexical_data_schema(target)
            imported = 0
            batch = []
            pairs = staging.execute(
                """SELECT e.id, e.text, e.author, z.id, z.text, z.author
                   FROM links l JOIN sentences e ON e.id = l.english_id
                   JOIN sentences z ON z.id = l.chinese_id
                   ORDER BY e.id, z.id"""
            )
            with target:
                target.execute("DELETE FROM open_bilingual_examples WHERE source_key = ?", (SOURCE_KEY,))
                for english_id, english, english_author, chinese_id, chinese, chinese_author in pairs:
                    if not english_author or not chinese_author or not (4 <= len(english) <= 280 and 2 <= len(chinese) <= 180):
                        continue
                    batch.append((
                        english, chinese, "en", "zh", english_author, chinese_author,
                        SOURCE_LICENSE, SOURCE_KEY, f"{english_id}:{chinese_id}",
                        sentence_quality(english, chinese), server.utc_now(),
                    ))
                    imported += 1
                    if len(batch) >= 1000:
                        target.executemany(
                            """INSERT OR REPLACE INTO open_bilingual_examples
                               (source_text, target_text, source_lang, target_lang, source_author,
                                target_author, license, source_key, source_record_id, quality_score, created_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            batch,
                        )
                        batch.clear()
                    if limit and imported >= limit:
                        break
                if batch:
                    target.executemany(
                        """INSERT OR REPLACE INTO open_bilingual_examples
                           (source_text, target_text, source_lang, target_lang, source_author,
                            target_author, license, source_key, source_record_id, quality_score, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        batch,
                    )
                register_dictionary_source(
                    target, source_key=SOURCE_KEY, name=SOURCE_NAME, version="download export",
                    license_name=SOURCE_LICENSE, attribution=SOURCE_ATTRIBUTION, source_url=SOURCE_URL,
                    checksum=files_checksum([sentences_path, links_path]), imported_at=server.utc_now(),
                )
            return {"source": SOURCE_NAME, "pairs": imported, "database": str(database)}
        finally:
            target.close()
            staging.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import attributable Tatoeba English-Chinese sentence pairs")
    parser.add_argument("--sentences", type=Path, required=True, help="Tatoeba detailed sentences TSV/BZ2 with author column")
    parser.add_argument("--links", type=Path, required=True, help="Tatoeba links TSV/BZ2")
    parser.add_argument("--database", type=Path, default=server.DB_PATH)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    print(json.dumps(import_tatoeba(args.sentences, args.links, args.database, args.limit), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
