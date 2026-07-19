from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

try:
    from .fsrs_adapter import FSRS_ID, enabled as fsrs_enabled, schedule_review as schedule_review_fsrs
except ImportError:
    from fsrs_adapter import FSRS_ID, enabled as fsrs_enabled, schedule_review as schedule_review_fsrs


SCHEDULER_ID = "adaptive-interval-v1"
UNDO_WINDOW_MINUTES = 10
RATINGS = ("again", "hard", "good", "easy")
RATING_LABELS = {"again": "忘记", "hard": "困难", "good": "记得", "easy": "轻松"}
SCHEDULE_FIELDS = (
    "state", "due_at", "interval_days", "ease_factor", "repetitions", "lapses",
    "last_review_at", "scheduler", "updated_at", "fsrs_state_json",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_time(value: str | None, fallback: datetime | None = None) -> datetime:
    if value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    return fallback or utc_now()


def ensure_review_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS review_items (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             learner_key TEXT NOT NULL DEFAULT 'local',
             item_type TEXT NOT NULL CHECK(item_type IN ('card', 'mistake')),
             item_id INTEGER NOT NULL,
             state TEXT NOT NULL DEFAULT 'new',
             due_at TEXT NOT NULL,
             interval_days REAL NOT NULL DEFAULT 0,
             ease_factor REAL NOT NULL DEFAULT 2.5,
             repetitions INTEGER NOT NULL DEFAULT 0,
             lapses INTEGER NOT NULL DEFAULT 0,
             last_review_at TEXT NOT NULL DEFAULT '',
           scheduler TEXT NOT NULL DEFAULT 'adaptive-interval-v1',
             fsrs_state_json TEXT NOT NULL DEFAULT '',
             created_at TEXT NOT NULL,
             updated_at TEXT NOT NULL,
             UNIQUE(learner_key, item_type, item_id)
           );
           CREATE INDEX IF NOT EXISTS idx_review_items_due
           ON review_items(learner_key, due_at, state);

           CREATE TABLE IF NOT EXISTS review_logs (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             review_item_id INTEGER NOT NULL,
             rating TEXT NOT NULL,
             before_json TEXT NOT NULL,
             after_json TEXT NOT NULL,
             reviewed_at TEXT NOT NULL,
             scheduler TEXT NOT NULL,
             reverted_at TEXT NOT NULL DEFAULT '',
             FOREIGN KEY(review_item_id) REFERENCES review_items(id)
           );
           CREATE INDEX IF NOT EXISTS idx_review_logs_recent
           ON review_logs(reviewed_at DESC, id DESC);"""
    )


def backfill_review_items(conn: sqlite3.Connection, now: str) -> None:
    ensure_review_schema(conn)
    card_columns = {row[1] for row in conn.execute("PRAGMA table_info(cards)")}
    if {"id", "created_at"}.issubset(card_columns):
        conn.execute(
            """INSERT OR IGNORE INTO review_items
               (learner_key, item_type, item_id, state, due_at, scheduler, created_at, updated_at)
               SELECT 'local', 'card', id, 'new', created_at, ?, created_at, ? FROM cards""",
            (SCHEDULER_ID, now),
        )
    mistake_columns = {row[1] for row in conn.execute("PRAGMA table_info(mistakes)")}
    if {"id", "solved", "created_at"}.issubset(mistake_columns):
        due_expression = "COALESCE(NULLIF(mastered_at, ''), created_at)" if "mastered_at" in mistake_columns else "created_at"
        conn.execute(
            f"""INSERT OR IGNORE INTO review_items
                (learner_key, item_type, item_id, state, due_at, scheduler, created_at, updated_at)
                SELECT 'local', 'mistake', id, 'new', {due_expression}, ?, created_at, ?
                FROM mistakes WHERE solved = 1""",
            (SCHEDULER_ID, now),
        )


def ensure_review_item(
    conn: sqlite3.Connection, item_type: str, item_id: int, now: str, learner_key: str = "local",
) -> int:
    if item_type not in {"card", "mistake"} or item_id <= 0:
        raise ValueError("A review item requires a card or mistake id")
    conn.execute(
        """INSERT OR IGNORE INTO review_items
           (learner_key, item_type, item_id, state, due_at, scheduler, created_at, updated_at)
           VALUES (?, ?, ?, 'new', ?, ?, ?, ?)""",
        (learner_key, item_type, item_id, now, SCHEDULER_ID, now, now),
    )
    row = conn.execute(
        "SELECT id FROM review_items WHERE learner_key = ? AND item_type = ? AND item_id = ?",
        (learner_key, item_type, item_id),
    ).fetchone()
    return int(row[0])


def schedule_snapshot(item: sqlite3.Row | dict) -> dict:
    source = dict(item)
    return {field: source.get(field) for field in SCHEDULE_FIELDS}


def schedule_review(item: sqlite3.Row | dict, rating: str, reviewed_at: datetime) -> dict:
    if rating not in RATINGS:
        raise ValueError("rating must be again, hard, good, or easy")
    source = dict(item)
    state = source.get("state") or "new"
    previous_interval = max(0.0, float(source.get("interval_days") or 0))
    ease = max(1.3, min(3.2, float(source.get("ease_factor") or 2.5)))
    repetitions = max(0, int(source.get("repetitions") or 0))
    lapses = max(0, int(source.get("lapses") or 0))

    if rating == "again":
        next_state = "learning" if state == "new" else "relearning"
        interval = 0.0
        due = reviewed_at + timedelta(minutes=10)
        ease = max(1.3, ease - 0.20)
        repetitions = 0
        if state != "new":
            lapses += 1
    elif rating == "hard":
        next_state = "learning" if state in {"new", "learning", "relearning"} else "review"
        interval = 1.0 if previous_interval < 1 else max(1.0, round(previous_interval * 1.2, 2))
        due = reviewed_at + timedelta(days=interval)
        ease = max(1.3, ease - 0.15)
        repetitions += 1
    elif rating == "good":
        next_state = "review"
        interval = 3.0 if previous_interval < 1 else max(3.0, round(previous_interval * ease, 2))
        due = reviewed_at + timedelta(days=interval)
        repetitions += 1
    else:
        next_state = "review"
        interval = 7.0 if previous_interval < 1 else max(7.0, round(previous_interval * ease * 1.3, 2))
        due = reviewed_at + timedelta(days=interval)
        ease = min(3.2, ease + 0.15)
        repetitions += 1

    return {
        "state": next_state,
        "due_at": iso(due),
        "interval_days": interval,
        "ease_factor": round(ease, 2),
        "repetitions": repetitions,
        "lapses": lapses,
        "last_review_at": iso(reviewed_at),
        "scheduler": SCHEDULER_ID,
        "updated_at": iso(reviewed_at),
        "fsrs_state_json": source.get("fsrs_state_json") or "",
    }


def schedule_for_item(item: sqlite3.Row | dict, rating: str, reviewed_at: datetime) -> dict:
    if fsrs_enabled():
        try:
            return schedule_review_fsrs(dict(item), rating, reviewed_at)
        except (RuntimeError, TypeError, ValueError, KeyError):
            pass
    return schedule_review(item, rating, reviewed_at)


def interval_label(after: dict, reviewed_at: datetime) -> str:
    due = parse_time(after["due_at"], reviewed_at)
    seconds = max(0, int((due - reviewed_at).total_seconds()))
    if seconds < 3600:
        return f"{max(1, round(seconds / 60))} 分钟"
    if seconds < 86400:
        return f"{max(1, round(seconds / 3600))} 小时"
    days = seconds / 86400
    return f"{round(days)} 天" if days < 30 else f"{round(days / 30, 1)} 个月"


def review_choices(item: sqlite3.Row | dict, now: datetime) -> list[dict]:
    return [
        {"rating": rating, "label": RATING_LABELS[rating], "interval": interval_label(schedule_for_item(item, rating, now), now)}
        for rating in RATINGS
    ]


def _kind_clause(kind: str) -> tuple[str, tuple]:
    if kind == "word":
        return "ri.item_type = 'card' AND c.kind = 'word'", ()
    if kind == "phrase":
        return "ri.item_type = 'card' AND c.kind = 'phrase'", ()
    if kind == "mistake":
        return "ri.item_type = 'mistake'", ()
    return "1 = 1", ()


def review_item_payload(row: sqlite3.Row | dict, now: datetime) -> dict:
    item = dict(row)
    is_card = item["item_type"] == "card"
    if is_card:
        front = item.get("term") or ""
        answer = item.get("context") or item.get("note") or "请回想这个表达在原语境中的含义与搭配。"
        kind = item.get("card_kind") or "word"
        source_id = item.get("source_article_id")
        context = item.get("context") or ""
    else:
        front = item.get("prompt") or ""
        answer = item.get("answer") or ""
        kind = "mistake"
        source_id = item.get("article_id")
        context = item.get("evidence") or ""
    return {
        "id": item["id"], "item_type": item["item_type"], "item_id": item["item_id"],
        "kind": kind, "front": front, "answer": answer, "context": context,
        "note": item.get("note") or item.get("error_type") or "", "source_article_id": source_id,
        "state": item["state"], "due_at": item["due_at"], "interval_days": item["interval_days"],
        "ease_factor": item["ease_factor"], "repetitions": item["repetitions"], "lapses": item["lapses"],
        "last_review_at": item["last_review_at"], "scheduler": item["scheduler"],
        "choices": review_choices(item, now),
    }


def review_queue(
    conn: sqlite3.Connection, kind: str = "all", limit: int = 20,
    now: datetime | None = None, learner_key: str = "local",
) -> dict:
    current = now or utc_now()
    now_text = iso(current)
    backfill_review_items(conn, now_text)
    kind_clause, kind_params = _kind_clause(kind)
    active_clause = "((ri.item_type = 'card' AND c.id IS NOT NULL) OR (ri.item_type = 'mistake' AND m.solved = 1))"
    safe_limit = max(1, min(100, int(limit or 20)))
    rows = conn.execute(
        f"""SELECT ri.*, c.term, c.kind AS card_kind, c.context, c.note, c.source_article_id,
                   m.prompt, m.answer, m.evidence, m.error_type, q.article_id
            FROM review_items ri
            LEFT JOIN cards c ON ri.item_type = 'card' AND c.id = ri.item_id
            LEFT JOIN mistakes m ON ri.item_type = 'mistake' AND m.id = ri.item_id
            LEFT JOIN quizzes q ON m.quiz_id = q.id
            WHERE ri.learner_key = ? AND ri.state != 'suspended' AND ri.due_at <= ?
              AND {active_clause} AND ({kind_clause})
            ORDER BY CASE ri.state WHEN 'relearning' THEN 0 WHEN 'learning' THEN 1 WHEN 'review' THEN 2 ELSE 3 END,
                     ri.due_at, ri.id LIMIT ?""",
        (learner_key, now_text, *kind_params, safe_limit),
    ).fetchall()
    summary_rows = conn.execute(
        f"""SELECT ri.state, COUNT(*) AS count
            FROM review_items ri
            LEFT JOIN cards c ON ri.item_type = 'card' AND c.id = ri.item_id
            LEFT JOIN mistakes m ON ri.item_type = 'mistake' AND m.id = ri.item_id
            WHERE ri.learner_key = ? AND ri.state != 'suspended' AND ri.due_at <= ?
              AND {active_clause} AND ({kind_clause}) GROUP BY ri.state""",
        (learner_key, now_text, *kind_params),
    ).fetchall()
    counts = {"new": 0, "learning": 0, "review": 0, "relearning": 0}
    counts.update({row["state"]: row["count"] for row in summary_rows})
    next_due = conn.execute(
        f"""SELECT MIN(ri.due_at) FROM review_items ri
            LEFT JOIN cards c ON ri.item_type = 'card' AND c.id = ri.item_id
            LEFT JOIN mistakes m ON ri.item_type = 'mistake' AND m.id = ri.item_id
            WHERE ri.learner_key = ? AND ri.state != 'suspended' AND ri.due_at > ?
              AND {active_clause} AND ({kind_clause})""",
        (learner_key, now_text, *kind_params),
    ).fetchone()[0]
    return {
        "items": [review_item_payload(row, current) for row in rows],
        "summary": {**counts, "due": sum(counts.values()), "next_due": next_due, "kind": kind},
        "scheduler": {"id": FSRS_ID if fsrs_enabled() else SCHEDULER_ID, "fsrs": fsrs_enabled(), "description": "FSRS 6.3.1" if fsrs_enabled() else "可替换的保守间隔调度；当前不是 FSRS。"},
        "undo": review_undo_status(conn, current, learner_key),
    }


def review_undo_status(
    conn: sqlite3.Connection, now: datetime | None = None, learner_key: str = "local",
) -> dict:
    current = now or utc_now()
    row = conn.execute(
        """SELECT l.id, l.review_item_id, l.rating, l.reviewed_at FROM review_logs l
           JOIN review_items ri ON ri.id = l.review_item_id
           WHERE ri.learner_key = ? AND l.reverted_at = ''
           ORDER BY l.reviewed_at DESC, l.id DESC LIMIT 1""",
        (learner_key,),
    ).fetchone()
    available = bool(row) and current - parse_time(row["reviewed_at"], current) <= timedelta(minutes=UNDO_WINDOW_MINUTES)
    return {
        "available": available,
        "log_id": row["id"] if available else None,
        "review_item_id": row["review_item_id"] if available else None,
        "reviewed_at": row["reviewed_at"] if available else "",
        "window_minutes": UNDO_WINDOW_MINUTES,
    }


def rate_review_item(
    conn: sqlite3.Connection, review_item_id: int, rating: str,
    now: datetime | None = None, learner_key: str = "local",
) -> dict:
    current = now or utc_now()
    row = conn.execute(
        "SELECT * FROM review_items WHERE id = ? AND learner_key = ? AND state != 'suspended'",
        (review_item_id, learner_key),
    ).fetchone()
    if not row:
        raise ValueError("Review item not found")
    if parse_time(row["due_at"], current) > current:
        raise ValueError("Review item is not due yet")
    before = schedule_snapshot(row)
    after = schedule_for_item(row, rating, current)
    assignments = ", ".join(f"{field} = ?" for field in SCHEDULE_FIELDS)
    conn.execute(
        f"UPDATE review_items SET {assignments} WHERE id = ?",
        (*[after[field] for field in SCHEDULE_FIELDS], review_item_id),
    )
    cursor = conn.execute(
        """INSERT INTO review_logs
           (review_item_id, rating, before_json, after_json, reviewed_at, scheduler)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (review_item_id, rating, json.dumps(before), json.dumps(after), iso(current), SCHEDULER_ID),
    )
    updated = conn.execute("SELECT * FROM review_items WHERE id = ?", (review_item_id,)).fetchone()
    return {"log_id": cursor.lastrowid, "item": dict(updated), "rating": rating, "interval": interval_label(after, current)}


def undo_last_review(
    conn: sqlite3.Connection, now: datetime | None = None, learner_key: str = "local",
) -> dict:
    current = now or utc_now()
    row = conn.execute(
        """SELECT l.*, ri.learner_key FROM review_logs l
           JOIN review_items ri ON ri.id = l.review_item_id
           WHERE ri.learner_key = ? AND l.reverted_at = ''
           ORDER BY l.reviewed_at DESC, l.id DESC LIMIT 1""",
        (learner_key,),
    ).fetchone()
    if not row:
        raise ValueError("No review can be undone")
    if current - parse_time(row["reviewed_at"], current) > timedelta(minutes=UNDO_WINDOW_MINUTES):
        raise ValueError("The review undo window has expired")
    before = json.loads(row["before_json"])
    assignments = ", ".join(f"{field} = ?" for field in SCHEDULE_FIELDS)
    conn.execute(
        f"UPDATE review_items SET {assignments} WHERE id = ?",
        (*[before[field] for field in SCHEDULE_FIELDS], row["review_item_id"]),
    )
    conn.execute("UPDATE review_logs SET reverted_at = ? WHERE id = ?", (iso(current), row["id"]))
    return {
        "log_id": row["id"], "review_item_id": row["review_item_id"], "rating": row["rating"],
        "reviewed_at": row["reviewed_at"], "reverted_at": iso(current),
    }
