import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import server
from backend.dictionary_quality import audit_dictionary_data
from scripts.import_kaikki import import_kaikki


def clone_database(source: Path, destination: Path) -> None:
    source = Path(source)
    destination = Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError("Candidate database must differ from the production database")
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(source)
    destination_conn = sqlite3.connect(destination)
    try:
        source_conn.backup(destination_conn)
    finally:
        destination_conn.close()
        source_conn.close()


def stage_kaikki_candidate(
    source: Path,
    words_path: Path,
    production_database: Path,
    candidate_database: Path,
    report_path: Path,
    source_version: str,
) -> dict:
    source = Path(source)
    words_path = Path(words_path)
    production_database = Path(production_database)
    candidate_database = Path(candidate_database)
    report_path = Path(report_path)
    if not source.is_file() or not words_path.is_file() or not production_database.is_file():
        raise FileNotFoundError("Kaikki source, target words and production database must all exist")
    if production_database.resolve() == candidate_database.resolve():
        raise ValueError("Candidate database must differ from the production database")

    building = candidate_database.with_name(candidate_database.name + ".building")
    building.unlink(missing_ok=True)
    clone_database(production_database, building)
    words = set(words_path.read_text(encoding="utf-8").splitlines())
    import_result = import_kaikki(
        source,
        database=building,
        words=words,
        source_version=source_version,
    )
    conn = sqlite3.connect(building)
    conn.row_factory = sqlite3.Row
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        audit = audit_dictionary_data(conn)
    finally:
        conn.close()
    result = {
        "ready": integrity == "ok" and audit["ready"],
        "production_unchanged": True,
        "candidate_database": str(candidate_database),
        "integrity": integrity,
        "import": import_result,
        "audit": audit,
    }
    os.replace(building, candidate_database)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Kaikki into an isolated candidate and run production gates")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--words", type=Path, required=True)
    parser.add_argument("--production-database", type=Path, default=server.DB_PATH)
    parser.add_argument("--candidate-database", type=Path, default=ROOT / "artifacts" / "kaikki-candidate.sqlite3")
    parser.add_argument("--report", type=Path, default=ROOT / "artifacts" / "kaikki-candidate-audit.json")
    parser.add_argument("--source-version", required=True)
    args = parser.parse_args()
    result = stage_kaikki_candidate(
        args.source,
        args.words,
        args.production_database,
        args.candidate_database,
        args.report,
        args.source_version,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ready"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
