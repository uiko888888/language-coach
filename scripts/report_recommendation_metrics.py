from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


EVENTS = ("impression", "click", "start", "submit")


def report(database: Path, days: int = 7, now: datetime | None = None) -> dict:
    current = now or datetime.now(timezone.utc)
    since = current - timedelta(days=max(1, days))
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    try:
        table = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'academic_phrase_recommendation_events'").fetchone()
        if not table:
            return {"database": str(database), "ready": False, "reason": "schema 25 not applied", "days": days}
        rows = conn.execute(
            """SELECT event_type, COUNT(*) AS count FROM academic_phrase_recommendation_events
               WHERE created_at >= ? GROUP BY event_type""",
            (since.isoformat(timespec="seconds"),),
        ).fetchall()
        counts = {event: 0 for event in EVENTS}
        counts.update({row["event_type"]: row["count"] for row in rows})
        correct = conn.execute(
            """SELECT COUNT(*) AS submissions, COALESCE(SUM(correct), 0) AS correct
               FROM academic_phrase_recommendation_events
               WHERE event_type = 'submit' AND created_at >= ?""",
            (since.isoformat(timespec="seconds"),),
        ).fetchone()
        denominator = lambda key: max(1, counts[key])
        return {
            "database": str(database),
            "ready": True,
            "since": since.isoformat(timespec="seconds"),
            "days": days,
            "events": counts,
            "funnel_rates": {
                "click_per_impression": round(counts["click"] / denominator("impression"), 3),
                "start_per_click": round(counts["start"] / denominator("click"), 3),
                "submit_per_start": round(counts["submit"] / denominator("start"), 3),
                "correct_per_submit": round(int(correct["correct"]) / max(1, int(correct["submissions"])), 3),
            },
            "sample": {"submissions": int(correct["submissions"]), "correct": int(correct["correct"])},
            "interpretation": "描述性观测，不代表学习迁移收益。" if int(correct["submissions"]) else "样本不足，继续使用后再解释。",
        }
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Report local academic phrase recommendation funnel metrics.")
    parser.add_argument("--database", type=Path, default=Path(os.environ.get("LANGUAGE_COACH_DB_PATH", "data/language_coach.sqlite")))
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    print(json.dumps(report(args.database, args.days), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
