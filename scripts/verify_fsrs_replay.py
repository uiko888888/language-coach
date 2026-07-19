from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay FSRS against a disposable database copy")
    parser.add_argument("--database", default="data/language_coach.sqlite")
    args = parser.parse_args()
    source = Path(args.database).resolve()
    if not source.exists():
        raise SystemExit(f"Database not found: {source}")

    with tempfile.TemporaryDirectory(prefix="language-coach-fsrs-") as temp_dir:
        replay_db = Path(temp_dir) / source.name
        shutil.copy2(source, replay_db)
        os.environ["LANGUAGE_COACH_DB_PATH"] = str(replay_db)
        os.environ["LANGUAGE_COACH_FSRS"] = "1"
        os.environ.setdefault("FSRS_DESIRED_RETENTION", "0.90")

        from backend import fsrs_adapter, server
        from backend.review_scheduler import rate_review_item, review_queue, undo_last_review

        if not fsrs_adapter.available():
            raise SystemExit("fsrs package is not available in this Python environment")
        server.init_db()
        now = datetime.now(timezone.utc)
        with server.db() as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            before_count = conn.execute("SELECT COUNT(*) FROM review_items").fetchone()[0]
            before_logs = conn.execute("SELECT COUNT(*) FROM review_logs").fetchone()[0]
            queue = review_queue(conn, now=now)
            result = None
            if queue["items"]:
                result = rate_review_item(conn, queue["items"][0]["id"], "good", now)
                undo_last_review(conn, now)
            after_count = conn.execute("SELECT COUNT(*) FROM review_items").fetchone()[0]
            after_logs = conn.execute("SELECT COUNT(*) FROM review_logs").fetchone()[0]

        if integrity != "ok" or before_count != after_count or before_logs != after_logs:
            raise SystemExit("FSRS replay changed counts or failed SQLite integrity validation")
        print({
            "database_copy": str(replay_db),
            "integrity": integrity,
            "review_items": before_count,
            "review_logs": before_logs,
            "due_items": queue["summary"]["due"],
            "fsrs": True,
            "sample_rating": result["rating"] if result else None,
            "sample_scheduler": result["item"]["scheduler"] if result else fsrs_adapter.FSRS_ID,
            "rollback_verified": True,
        })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
