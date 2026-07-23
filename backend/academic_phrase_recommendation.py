from __future__ import annotations

from datetime import datetime, timezone

try:
    from .academic_phrases import search_academic_phrases
    from .academic_phrase_training import training_items
except ImportError:
    from academic_phrases import search_academic_phrases
    from academic_phrase_training import training_items


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def recommend_academic_phrases(conn, category: str = "", exam: str = "", task_type: str = "cloze", limit: int = 10) -> list[dict]:
    candidates = search_academic_phrases(category=category, exam=exam, limit=100)
    task_by_sense = {
        item["sense_key"]: item
        for item in training_items(category=category, exam=exam, task_type=task_type, limit=100)
    }
    now = _now()
    ranked = []
    for item in candidates:
        stats = conn.execute(
            """SELECT COUNT(*) AS attempts, COALESCE(SUM(correct = 0), 0) AS wrong,
                      MAX(created_at) AS last_attempt
               FROM academic_phrase_attempts WHERE sense_key = ?""",
            (item["sense_key"],),
        ).fetchone()
        due = conn.execute(
            """SELECT COUNT(*) FROM review_items ri JOIN cards c
               ON ri.item_type = 'card' AND ri.item_id = c.id
               WHERE c.kind = 'phrase' AND c.sense_key = ? AND ri.due_at <= ? AND ri.state != 'suspended'""",
            (item["sense_key"], now),
        ).fetchone()[0]
        attempts = int(stats["attempts"] or 0)
        wrong = int(stats["wrong"] or 0)
        reasons = []
        score = 0
        if due:
            score += 100
            reasons.append("今天到期")
        if wrong:
            score += min(90, wrong * 60)
            reasons.append(f"已答错 {wrong} 次")
        if not attempts:
            score += 40
            reasons.append("尚未练习")
        if not reasons:
            score += max(1, 20 - attempts)
            reasons.append("保持间隔复习")
        task = task_by_sense.get(item["sense_key"])
        if task:
            ranked.append({**task, "recommendation_score": score, "recommendation_reason": "；".join(reasons), "attempts": attempts, "wrong_attempts": wrong, "due": bool(due), "last_attempt": stats["last_attempt"]})
    ranked.sort(key=lambda value: (-value["recommendation_score"], value["last_attempt"] or "", value["term"]))
    return ranked[: max(1, min(50, int(limit or 10)))]
