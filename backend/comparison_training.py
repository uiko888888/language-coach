from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone

try:
    from .lexical_compare import CURATED_COMPARISONS
    from .review_scheduler import ensure_review_item
except ImportError:
    from lexical_compare import CURATED_COMPARISONS
    from review_scheduler import ensure_review_item


TASK_TYPES = {"choice", "correction"}
TOPICS = {"", "general", "charts", "argument"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _replace_term(text: str, term: str, replacement: str) -> str | None:
    pattern = re.compile(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return None
    value = replacement.capitalize() if match.group(0)[:1].isupper() else replacement
    return pattern.sub(value, text, count=1)


def comparison_training_catalog() -> list[dict]:
    tasks: list[dict] = []
    for group in CURATED_COMPARISONS:
        terms = list(group["terms"])
        topic = group.get("topic", "general")
        for position, term in enumerate(terms):
            lexical_item = group["items"][term]
            base = {
                "slug": group["slug"], "term": term, "terms": terms,
                "title": group["title"], "topic": topic,
                "confusion_type": group.get("confusion_type", "semantic"),
                "options": terms, "answer": term,
                "meaning_zh": lexical_item["meaning_zh"],
                "focus_en": lexical_item["focus_en"],
                "focus": lexical_item["focus"],
                "patterns": list(lexical_item["patterns"]),
                "avoid": lexical_item["avoid"],
                "memory_rule": group["memory_rule"],
                "summary": group["summary"],
                "example": lexical_item["example"],
                "example_zh": lexical_item["example_zh"],
                "example_source": lexical_item.get("example_source", "本地人工整理基础组"),
            }
            tasks.append({
                **base, "task_id": f"{group['slug']}:choice:{term}", "task_type": "choice",
                "instruction": "选择最符合英文概念和句法框架的表达。",
                "prompt": lexical_item["focus_en"],
                "support": " · ".join(lexical_item["patterns"][:2]),
                "corrected_text": "",
            })
            distractor = terms[(position + 1) % len(terms)]
            incorrect = _replace_term(lexical_item["example"], term, distractor)
            if incorrect and _normalize(incorrect) != _normalize(lexical_item["example"]):
                tasks.append({
                    **base, "task_id": f"{group['slug']}:correction:{term}", "task_type": "correction",
                    "instruction": "根据目标含义，选择能修正句中用词边界的表达。",
                    "prompt": incorrect,
                    "support": f"目标含义：{lexical_item['focus']}",
                    "corrected_text": lexical_item["example"],
                })
    return tasks


def _task_map() -> dict[str, dict]:
    return {task["task_id"]: task for task in comparison_training_catalog()}


def comparison_training_queue(
    conn: sqlite3.Connection, topic: str = "", task_type: str = "choice", limit: int = 80,
) -> dict:
    if topic not in TOPICS:
        raise ValueError("Invalid comparison training topic")
    if task_type not in TASK_TYPES:
        raise ValueError("Invalid comparison training task type")
    safe_limit = max(1, min(int(limit), 200))
    latest_rows = conn.execute(
        """SELECT a.* FROM comparison_training_attempts a
           JOIN (SELECT task_id, MAX(id) AS id FROM comparison_training_attempts GROUP BY task_id) latest
             ON latest.id = a.id"""
    ).fetchall()
    latest = {row["task_id"]: dict(row) for row in latest_rows}
    attempt_counts = {
        row["task_id"]: row["count"] for row in conn.execute(
            "SELECT task_id, COUNT(*) AS count FROM comparison_training_attempts GROUP BY task_id"
        )
    }
    catalog = [
        task for task in comparison_training_catalog()
        if task["task_type"] == task_type and (not topic or task["topic"] == topic)
    ]
    catalog.sort(key=lambda task: (
        0 if task["task_id"] in latest and not latest[task["task_id"]]["correct"] else
        1 if task["task_id"] not in latest else 2,
        task["topic"], task["slug"], task["term"],
    ))
    items = []
    for task in catalog[:safe_limit]:
        attempt = latest.get(task["task_id"])
        items.append({
            **{key: task[key] for key in (
                "task_id", "slug", "terms", "title", "topic", "confusion_type", "options",
                "task_type", "instruction", "prompt", "support", "patterns",
            )},
            "attempted": bool(attempt),
            "last_correct": bool(attempt and attempt["correct"]),
            "last_answer": attempt["user_answer"] if attempt else "",
            "attempt_count": attempt_counts.get(task["task_id"], 0),
        })
    total = len(catalog)
    attempted = sum(task["task_id"] in latest for task in catalog)
    correct = sum(bool(latest.get(task["task_id"], {}).get("correct")) for task in catalog)
    wrong = sum(task["task_id"] in latest and not latest[task["task_id"]]["correct"] for task in catalog)
    due_reviews = conn.execute(
        """SELECT COUNT(*) FROM review_items ri JOIN cards c ON c.id = ri.item_id
           WHERE ri.item_type = 'card' AND c.kind = 'comparison-boundary'
             AND ri.state != 'suspended' AND ri.due_at <= ?""", (_now(),)
    ).fetchone()[0]
    return {
        "items": items,
        "summary": {"total": total, "attempted": attempted, "correct": correct, "wrong": wrong, "due_reviews": due_reviews},
        "filters": {"topic": topic, "task_type": task_type},
    }


def _ensure_boundary_card(
    conn: sqlite3.Connection, task: dict, user_answer: str, created_at: str,
) -> tuple[int, int, bool, bool]:
    sense_key = f"comparison:{task['task_id']}"
    existing = conn.execute(
        "SELECT id FROM cards WHERE kind = 'comparison-boundary' AND sense_key = ? ORDER BY id LIMIT 1",
        (sense_key,),
    ).fetchone()
    context = "\n".join(value for value in (task["instruction"], task["prompt"], task["support"]) if value)
    note = f"辨析错答：{user_answer} → {task['answer']}"
    if not existing:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO cards
               (term, kind, context, status, note, sense_key, part_of_speech, meaning_zh,
                concept_en, grammar_frame, confusion_note, lexical_source, created_at, updated_at)
               VALUES (?, 'comparison-boundary', ?, 'new', ?, ?, '', ?, ?, ?, ?, ?, ?, ?)""",
            (
                task["prompt"], context, note, sense_key, task["meaning_zh"], task["focus_en"],
                "；".join(task["patterns"]), f"{task['avoid']} 记忆：{task['memory_rule']}",
                task["example_source"], created_at, created_at,
            ),
        )
        created = cursor.rowcount > 0
    else:
        created = False
    row = conn.execute(
        "SELECT id FROM cards WHERE kind = 'comparison-boundary' AND sense_key = ? ORDER BY id LIMIT 1",
        (sense_key,),
    ).fetchone()
    if not row:
        raise RuntimeError("Comparison boundary card could not be created")
    card_id = int(row["id"])
    conn.execute(
        """UPDATE cards SET context = ?, note = ?, meaning_zh = ?, concept_en = ?, grammar_frame = ?,
           confusion_note = ?, lexical_source = ?, updated_at = ? WHERE id = ?""",
        (
            context, note, task["meaning_zh"], task["focus_en"], "；".join(task["patterns"]),
            f"{task['avoid']} 记忆：{task['memory_rule']}", task["example_source"], created_at, card_id,
        ),
    )
    review_id = ensure_review_item(conn, "card", card_id, created_at)
    review = conn.execute("SELECT due_at FROM review_items WHERE id = ?", (review_id,)).fetchone()
    return card_id, review_id, created, bool(review and review["due_at"] <= created_at)


def submit_comparison_training_answer(
    conn: sqlite3.Connection, task_id: str, user_answer: str, *, elapsed_seconds: int = 0,
    answer_changes: int = 0, hint_used: bool = False,
) -> dict:
    task = _task_map().get(str(task_id or ""))
    if not task:
        raise ValueError("Comparison training task not found")
    selected = re.sub(r"\s+", " ", str(user_answer or "")).strip()
    if _normalize(selected) not in {_normalize(option) for option in task["options"]}:
        raise ValueError("Answer must be one of the task options")
    correct = _normalize(selected) == _normalize(task["answer"])
    created_at = _now()
    card_id = review_id = None
    card_created = False
    review_due = False
    if not correct:
        card_id, review_id, card_created, review_due = _ensure_boundary_card(conn, task, selected, created_at)
    explanation = {
        "answer": task["answer"], "meaning_zh": task["meaning_zh"],
        "focus": task["focus"], "focus_en": task["focus_en"],
        "patterns": task["patterns"], "avoid": task["avoid"],
        "memory_rule": task["memory_rule"], "summary": task["summary"],
        "corrected_text": task["corrected_text"], "example": task["example"],
        "example_zh": task["example_zh"], "example_source": task["example_source"],
    }
    cursor = conn.execute(
        """INSERT INTO comparison_training_attempts
           (task_id, slug, term, task_type, prompt, options_json, correct_answer, user_answer,
            correct, explanation_json, elapsed_seconds, answer_changes, hint_used, review_card_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            task["task_id"], task["slug"], task["term"], task["task_type"], task["prompt"],
            json.dumps(task["options"], ensure_ascii=False), task["answer"], selected, int(correct),
            json.dumps(explanation, ensure_ascii=False), max(0, min(int(elapsed_seconds), 86400)),
            max(0, min(int(answer_changes), 100)), int(bool(hint_used)), card_id, created_at,
        ),
    )
    return {
        "attempt_id": int(cursor.lastrowid), "task_id": task["task_id"],
        "correct": correct, "user_answer": selected, "answer": task["answer"],
        "explanation": explanation,
        "review": {
            "scheduled": not correct, "created": card_created, "card_id": card_id,
            "review_item_id": review_id, "due": review_due,
        },
    }
