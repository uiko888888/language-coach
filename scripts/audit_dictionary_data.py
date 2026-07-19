import argparse
import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import server
from backend.dictionary_quality import audit_dictionary_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit installed open dictionary layers")
    parser.add_argument("--database", type=Path, default=server.DB_PATH)
    parser.add_argument("--report", type=Path, help="Optional JSON report destination")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero until production gates pass")
    args = parser.parse_args()
    conn = sqlite3.connect(args.database)
    conn.row_factory = sqlite3.Row
    try:
        report = audit_dictionary_data(conn)
    finally:
        conn.close()
    output = json.dumps(report, ensure_ascii=False, indent=2)
    print(output)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output + "\n", encoding="utf-8")
    if args.strict and not report["ready"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
