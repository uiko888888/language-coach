from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone

try:
    from .review_scheduler import ensure_review_item, parse_time, review_choices, review_undo_status
except ImportError:
    from review_scheduler import ensure_review_item, parse_time, review_choices, review_undo_status


def _json_list(raw: str | None) -> list:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return value if isinstance(value, list) else []


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def materialize_complete_word_cards(conn: sqlite3.Connection, now: str | None = None) -> int:
    created_at = now or _iso_now()
    rows = conn.execute(
        """SELECT q.id, q.answer, q.evidence, q.article_id
           FROM quizzes q
           WHERE q.question_type = 'complete-words'
             AND EXISTS (SELECT 1 FROM attempts a WHERE a.quiz_id = q.id)
           ORDER BY q.id"""
    ).fetchall()
    created = 0
    for row in rows:
        card = conn.execute("SELECT id FROM cards WHERE source_quiz_id = ?", (row["id"],)).fetchone()
        if not card:
            cursor = conn.execute(
                """INSERT INTO cards
                   (term, kind, context, source_article_id, source_quiz_id, status, note, created_at, updated_at)
                   VALUES (?, 'complete-word', ?, ?, ?, 'new', 'TOEFL Complete the Words 原题回顾', ?, ?)""",
                (row["answer"], row["evidence"] or "", row["article_id"], row["id"], created_at, created_at),
            )
            card_id = int(cursor.lastrowid)
            created += 1
        else:
            card_id = int(card["id"])
        ensure_review_item(conn, "card", card_id, created_at)
    return created


def _lexical_hint(conn: sqlite3.Connection, word: str) -> dict:
    normalized = word.casefold()
    row = conn.execute(
        "SELECT pos, meaning_zh FROM dictionary_entries WHERE lower(headword) = ? ORDER BY id LIMIT 1",
        (normalized,),
    ).fetchone()
    if row:
        return {"pos": row["pos"] or "", "meaning_zh": row["meaning_zh"] or ""}
    row = conn.execute(
        """SELECT pos, translations_zh_json FROM open_lexical_entries
           WHERE normalized = ? ORDER BY CASE WHEN translations_zh_json = '[]' THEN 1 ELSE 0 END, id LIMIT 1""",
        (normalized,),
    ).fetchone()
    if row:
        translations = _json_list(row["translations_zh_json"])
        values = []
        for item in translations:
            value = item.get("word") if isinstance(item, dict) else item
            if value and value not in values:
                values.append(str(value))
        return {"pos": row["pos"] or "", "meaning_zh": "；".join(values[:4])}
    return {"pos": "", "meaning_zh": ""}


def _cached_translation(conn: sqlite3.Connection, text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    row = conn.execute(
        """SELECT translated_text FROM translation_cache
           WHERE text_hash = ? AND source_lang = 'EN' AND target_lang = 'ZH-HANS'
           ORDER BY created_at DESC, id DESC LIMIT 1""",
        (digest,),
    ).fetchone()
    return row["translated_text"] if row else ""


def _error_type(answer: str, selected: str) -> str:
    target = answer.casefold()
    attempt = selected.casefold()
    if attempt and target.startswith(attempt):
        return "只填写了已知部分或单词未补完整"
    if attempt and abs(len(attempt) - len(target)) <= 2:
        return "拼写或词形错误"
    return "语境词义判断错误"


def complete_word_catalog(
    conn: sqlite3.Connection,
    scope: str = "wrong",
    search: str = "",
    limit: int = 200,
    now: datetime | None = None,
) -> dict:
    current = now or datetime.now(timezone.utc)
    current_text = current.isoformat(timespec="seconds")
    materialize_complete_word_cards(conn, current_text)
    safe_scope = "all" if scope == "all" else "wrong"
    safe_limit = max(1, min(500, int(limit or 200)))
    conditions = ["q.question_type = 'complete-words'"]
    params: list[object] = []
    if safe_scope == "wrong":
        conditions.append("s.wrong_count > 0")
    query = re.sub(r"\s+", " ", str(search or "")).strip()
    if query:
        pattern = f"%{query}%"
        conditions.append("(q.answer LIKE ? OR q.evidence LIKE ? OR ar.title LIKE ?)")
        params.extend((pattern, pattern, pattern))
    params.append(safe_limit)
    rows = conn.execute(
        f"""WITH s AS (
                 SELECT quiz_id, COUNT(*) AS attempt_count, SUM(CASE WHEN correct = 0 THEN 1 ELSE 0 END) AS wrong_count,
                        MAX(created_at) AS last_attempt_at
                 FROM attempts GROUP BY quiz_id
               )
               SELECT q.*, ar.title AS article_title, ar.source AS article_source,
                      s.attempt_count, s.wrong_count, s.last_attempt_at,
                      la.user_answer AS latest_answer, la.correct AS latest_correct, la.error_type AS latest_error_type,
                      c.id AS card_id, ri.id AS review_item_id, ri.state, ri.due_at, ri.interval_days,
                      ri.ease_factor, ri.repetitions, ri.lapses, ri.last_review_at, ri.scheduler,
                      ri.updated_at, ri.fsrs_state_json,
                      cra.user_answer AS review_answer, cra.correct AS review_correct,
                      cra.error_type AS review_error_type, cra.created_at AS review_attempt_at
               FROM quizzes q
               JOIN s ON s.quiz_id = q.id
               JOIN attempts la ON la.id = (SELECT a2.id FROM attempts a2 WHERE a2.quiz_id = q.id ORDER BY a2.id DESC LIMIT 1)
               LEFT JOIN articles ar ON ar.id = q.article_id
               JOIN cards c ON c.source_quiz_id = q.id
               JOIN review_items ri ON ri.item_type = 'card' AND ri.item_id = c.id AND ri.learner_key = 'local'
               LEFT JOIN complete_word_review_attempts cra ON cra.id = (
                 SELECT c2.id FROM complete_word_review_attempts c2 WHERE c2.quiz_id = q.id ORDER BY c2.id DESC LIMIT 1
               )
               WHERE {' AND '.join(conditions)}
               ORDER BY CASE WHEN ri.due_at <= ? THEN 0 ELSE 1 END, s.wrong_count DESC, s.last_attempt_at DESC, q.id DESC
               LIMIT ?""",
        (*params[:-1], current_text, params[-1]),
    ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        metadata = json.loads(item.get("metadata_json") or "{}")
        due = parse_time(item["due_at"], current) <= current
        lexical = _lexical_hint(conn, item["answer"])
        items.append({
            "quiz_id": item["id"], "review_item_id": item["review_item_id"], "card_id": item["card_id"],
            "masked_text": metadata.get("masked_text") or item["prompt"],
            "visible_prefix": metadata.get("visible_prefix") or "",
            "missing_count": int(metadata.get("missing_count") or 0),
            "answer": item["answer"], "evidence": item["evidence"] or "",
            "evidence_translation_zh": _cached_translation(conn, item["evidence"] or "") if item["evidence"] else "",
            "pos": lexical["pos"], "meaning_zh": lexical["meaning_zh"],
            "article_id": item["article_id"], "article_title": item["article_title"] or "",
            "article_source": item["article_source"] or "", "generation_source": item["generation_source"],
            "official_equivalence": bool(metadata.get("official_equivalence", False)),
            "attempt_count": item["attempt_count"], "wrong_count": item["wrong_count"],
            "latest_answer": item["latest_answer"] or "", "latest_correct": bool(item["latest_correct"]),
            "latest_error_type": item["latest_error_type"] or "", "last_attempt_at": item["last_attempt_at"],
            "review_answer": item["review_answer"] or "", "review_correct": None if item["review_correct"] is None else bool(item["review_correct"]),
            "review_error_type": item["review_error_type"] or "", "review_attempt_at": item["review_attempt_at"] or "",
            "state": item["state"], "due_at": item["due_at"], "due": due,
            "repetitions": item["repetitions"], "lapses": item["lapses"],
            "choices": review_choices(item, current) if due else [],
        })
    total = len(items)
    return {
        "items": items,
        "summary": {
            "scope": safe_scope, "total": total,
            "due": sum(1 for item in items if item["due"]),
            "wrong": sum(1 for item in items if item["wrong_count"]),
            "reviewed": sum(1 for item in items if item["review_attempt_at"]),
        },
        "undo": review_undo_status(conn, current, kind="complete-word"),
    }


def submit_complete_word_review(
    conn: sqlite3.Connection,
    quiz_id: int,
    answer: str,
    elapsed_seconds: int = 0,
) -> dict:
    row = conn.execute(
        "SELECT id, answer, evidence FROM quizzes WHERE id = ? AND question_type = 'complete-words'",
        (quiz_id,),
    ).fetchone()
    if not row:
        raise ValueError("Complete the Words item not found")
    selected = re.sub(r"\s+", " ", str(answer or "")).strip()
    if not selected or len(selected) > 80:
        raise ValueError("Enter the complete word")
    correct = selected.casefold() == row["answer"].strip().casefold()
    error = "" if correct else _error_type(row["answer"], selected)
    try:
        elapsed = max(0, min(1800, int(elapsed_seconds or 0)))
    except (TypeError, ValueError):
        elapsed = 0
    now = _iso_now()
    cursor = conn.execute(
        """INSERT INTO complete_word_review_attempts
           (quiz_id, user_answer, correct, error_type, elapsed_seconds, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (quiz_id, selected, int(correct), error, elapsed, now),
    )
    lexical = _lexical_hint(conn, row["answer"])
    return {
        "attempt_id": cursor.lastrowid, "quiz_id": quiz_id, "user_answer": selected,
        "correct": correct, "answer": row["answer"], "evidence": row["evidence"] or "",
        "evidence_translation_zh": _cached_translation(conn, row["evidence"] or "") if row["evidence"] else "",
        "pos": lexical["pos"], "meaning_zh": lexical["meaning_zh"],
        "error_type": error, "elapsed_seconds": elapsed, "created_at": now,
    }
