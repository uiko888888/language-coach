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
from backend.private_dictionaries import register_private_dictionary


def main() -> int:
    parser = argparse.ArgumentParser(description="Index a user-owned MOBI dictionary for private local lookup.")
    parser.add_argument("--mobi", required=True, type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--kind", choices=("bilingual_dictionary", "encyclopedia"), default="bilingual_dictionary")
    parser.add_argument("--priority", type=int, default=50)
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "language_coach.sqlite")
    args = parser.parse_args()
    if not args.mobi.is_file():
        parser.error(f"MOBI file not found: {args.mobi}")
    args.database.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with sqlite3.connect(args.database) as conn:
        conn.row_factory = sqlite3.Row
        run_migrations(conn)
        result = register_private_dictionary(
            conn, args.mobi, name=args.name, kind=args.kind,
            priority=max(0, min(999, args.priority)), now=now,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"ready", "conversion_required"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
