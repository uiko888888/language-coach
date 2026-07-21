from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.migrations import run_migrations
from backend.private_dictionaries import register_private_stardict


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a user-owned StarDict dictionary for private local lookup.")
    parser.add_argument("--ifo", required=True, type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--kind", choices=("bilingual_dictionary", "monolingual_dictionary", "encyclopedia"), default="bilingual_dictionary")
    parser.add_argument("--priority", type=int, default=20)
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "language_coach.sqlite")
    args = parser.parse_args()
    if not args.ifo.is_file():
        parser.error(f"StarDict .ifo file not found: {args.ifo}")
    args.database.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with sqlite3.connect(args.database) as conn:
            conn.row_factory = sqlite3.Row
            run_migrations(conn)
            result = register_private_stardict(
                conn, args.ifo, name=args.name, kind=args.kind,
                priority=max(0, min(999, args.priority)), now=now,
            )
    except (OSError, ValueError, sqlite3.DatabaseError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
