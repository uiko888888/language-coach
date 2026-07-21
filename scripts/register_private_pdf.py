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
from backend.private_dictionaries import register_private_pdf_source


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Register an image-only user-owned PDF dictionary for a later validated OCR import."
    )
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--pages", required=True, type=int)
    parser.add_argument("--priority", type=int, default=30)
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "language_coach.sqlite")
    args = parser.parse_args()
    if not args.pdf.is_file():
        parser.error(f"PDF file not found: {args.pdf}")
    if args.pages < 1:
        parser.error("--pages must be positive")
    args.database.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with sqlite3.connect(args.database) as conn:
        conn.row_factory = sqlite3.Row
        run_migrations(conn)
        result = register_private_pdf_source(
            conn, args.pdf, name=args.name, pages=args.pages,
            priority=max(0, min(999, args.priority)), now=now,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
