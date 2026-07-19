import argparse
import csv
import hashlib
import json
import math
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import server
from backend.lexical_data import ensure_lexical_data_schema, frequency_band, normalize_term, register_dictionary_source


SOURCE_KEY = "wordfreq"
SOURCE_NAME = "wordfreq"
SOURCE_LICENSE = "Apache-2.0 code; mixed licensed frequency data"
SOURCE_ATTRIBUTION = "wordfreq by Luminoso Technologies; see upstream NOTICE and data-source licenses"
SOURCE_URL = "https://github.com/rspeer/wordfreq"


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def import_frequency_tsv(path: Path, database: Path = server.DB_PATH, source_version: str = "") -> dict:
    path = Path(path)
    database = Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database)
    try:
        server.ensure_wordnet_schema(conn)
        ensure_lexical_data_schema(conn)
        imported = rejected = 0
        batch = []
        source_checksum = checksum(path)
        conn.executescript(
            """DROP TABLE IF EXISTS temp.frequency_import_stage;
               CREATE TEMP TABLE frequency_import_stage (
                 normalized TEXT PRIMARY KEY,
                 zipf_frequency REAL NOT NULL,
                 frequency_band TEXT NOT NULL,
                 source_key TEXT NOT NULL,
                 updated_at TEXT NOT NULL
               );"""
        )
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.reader(stream, delimiter="\t"):
                normalized = normalize_term(row[0]) if row else ""
                if len(row) < 2 or not normalized:
                    rejected += 1
                    continue
                try:
                    score = float(row[1])
                except ValueError:
                    rejected += 1
                    continue
                if not math.isfinite(score) or not 0 <= score <= 8:
                    rejected += 1
                    continue
                batch.append((normalized, score, frequency_band(score), SOURCE_KEY, server.utc_now()))
                if len(batch) >= 2000:
                    conn.executemany(
                        """INSERT OR REPLACE INTO frequency_import_stage
                           (normalized, zipf_frequency, frequency_band, source_key, updated_at)
                           VALUES (?, ?, ?, ?, ?)""",
                        batch,
                    )
                    batch.clear()
            if batch:
                conn.executemany(
                    """INSERT OR REPLACE INTO frequency_import_stage
                       (normalized, zipf_frequency, frequency_band, source_key, updated_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    batch,
                )
            imported = conn.execute(
                "SELECT COUNT(*) FROM frequency_import_stage"
            ).fetchone()[0]
            if imported < 1:
                raise ValueError("Frequency source contains no valid Zipf rows")
        conn.commit()
        with conn:
            conn.execute("DELETE FROM lexical_frequencies WHERE source_key = ?", (SOURCE_KEY,))
            conn.execute(
                """INSERT INTO lexical_frequencies
                   (normalized, zipf_frequency, frequency_band, source_key, updated_at)
                   SELECT normalized, zipf_frequency, frequency_band, source_key, updated_at
                   FROM frequency_import_stage"""
            )
            register_dictionary_source(
                conn, source_key=SOURCE_KEY, name=SOURCE_NAME,
                version=source_version.strip() or f"sha256:{source_checksum[:12]}",
                license_name=SOURCE_LICENSE, attribution=SOURCE_ATTRIBUTION, source_url=SOURCE_URL,
                checksum=source_checksum, imported_at=server.utc_now(),
            )
        return {"source": SOURCE_NAME, "frequencies": imported, "rejected": rejected, "database": str(database)}
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import wordfreq-compatible term and Zipf-frequency TSV")
    parser.add_argument("--tsv", type=Path, required=True, help="Two columns: term and Zipf frequency")
    parser.add_argument("--database", type=Path, default=server.DB_PATH)
    parser.add_argument("--source-version", default="", help="Upstream dataset/package version")
    args = parser.parse_args()
    print(json.dumps(import_frequency_tsv(args.tsv, args.database, args.source_version), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
