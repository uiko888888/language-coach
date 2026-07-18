import argparse
import csv
import hashlib
import json
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


def import_frequency_tsv(path: Path, database: Path = server.DB_PATH) -> dict:
    path = Path(path)
    database = Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database)
    try:
        server.ensure_wordnet_schema(conn)
        ensure_lexical_data_schema(conn)
        rows = []
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.reader(stream, delimiter="\t"):
                if len(row) < 2 or not normalize_term(row[0]):
                    continue
                try:
                    score = float(row[1])
                except ValueError:
                    continue
                rows.append((normalize_term(row[0]), score, frequency_band(score), SOURCE_KEY, server.utc_now()))
        with conn:
            conn.execute("DELETE FROM lexical_frequencies WHERE source_key = ?", (SOURCE_KEY,))
            conn.executemany(
                """INSERT OR REPLACE INTO lexical_frequencies
                   (normalized, zipf_frequency, frequency_band, source_key, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                rows,
            )
            register_dictionary_source(
                conn, source_key=SOURCE_KEY, name=SOURCE_NAME, version="TSV import",
                license_name=SOURCE_LICENSE, attribution=SOURCE_ATTRIBUTION, source_url=SOURCE_URL,
                checksum=checksum(path), imported_at=server.utc_now(),
            )
        return {"source": SOURCE_NAME, "frequencies": len(rows), "database": str(database)}
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import wordfreq-compatible term and Zipf-frequency TSV")
    parser.add_argument("--tsv", type=Path, required=True, help="Two columns: term and Zipf frequency")
    parser.add_argument("--database", type=Path, default=server.DB_PATH)
    args = parser.parse_args()
    print(json.dumps(import_frequency_tsv(args.tsv, args.database), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
