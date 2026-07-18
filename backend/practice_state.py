from __future__ import annotations

import json
import sqlite3
from collections import defaultdict


JSON_FIELDS = {
    "quiz_ids_json": "quiz_ids",
    "answers_json": "answers",
    "confidence_json": "confidence",
    "flagged_json": "flagged",
    "answer_changes_json": "answer_changes",
    "hint_used_json": "hint_used",
    "feedback_json": "feedback",
}


def practice_run_payload(row: sqlite3.Row | dict) -> dict:
    item = dict(row)
    for source, target in JSON_FIELDS.items():
        item[target] = json.loads(item.pop(source, "{}" if target != "quiz_ids" else "[]") or ("{}" if target != "quiz_ids" else "[]"))
    return item


def active_practice_run(conn: sqlite3.Connection, learner_key: str = "local") -> dict | None:
    row = conn.execute(
        """SELECT * FROM practice_runs
           WHERE learner_key = ? AND status = 'in_progress'
           ORDER BY updated_at DESC, id DESC LIMIT 1""",
        (learner_key,),
    ).fetchone()
    return practice_run_payload(row) if row else None


def save_practice_run(conn: sqlite3.Connection, payload: dict, now: str, learner_key: str = "local") -> dict:
    raw_ids = payload.get("quiz_ids") or []
    if not isinstance(raw_ids, list):
        raise ValueError("quiz_ids must be a list")
    quiz_ids = list(dict.fromkeys(int(value) for value in raw_ids if int(value) > 0))
    if not quiz_ids or len(quiz_ids) > 50:
        raise ValueError("A practice run requires between 1 and 50 unique quizzes")
    placeholders = ",".join("?" for _ in quiz_ids)
    quizzes = conn.execute(
        f"SELECT id, article_id, style, question_type FROM quizzes WHERE id IN ({placeholders})",
        quiz_ids,
    ).fetchall()
    if len(quizzes) != len(quiz_ids):
        raise ValueError("One or more quizzes were not found")
    by_id = {row["id"]: row for row in quizzes}
    ordered = [by_id[quiz_id] for quiz_id in quiz_ids]
    run_id = int(payload.get("id") or 0)
    status = str(payload.get("status") or "in_progress")
    if status not in {"in_progress", "completed", "abandoned"}:
        raise ValueError("Invalid practice run status")
    state = {
        "article_id": int(payload.get("article_id") or ordered[0]["article_id"] or 0) or None,
        "style": str(payload.get("style") or ordered[0]["style"] or "IELTS"),
        "question_type": str(payload.get("question_type") or ordered[0]["question_type"] or "mixed"),
        "scope": str(payload.get("scope") or "specialty")[:32],
        "session_mode": "mock" if payload.get("session_mode") == "mock" else "practice",
        "status": status,
        "quiz_ids_json": json.dumps(quiz_ids),
        "answers_json": json.dumps(payload.get("answers") or {}, ensure_ascii=False),
        "confidence_json": json.dumps(payload.get("confidence") or {}, ensure_ascii=False),
        "flagged_json": json.dumps(payload.get("flagged") or {}, ensure_ascii=False),
        "answer_changes_json": json.dumps(payload.get("answer_changes") or {}, ensure_ascii=False),
        "hint_used_json": json.dumps(payload.get("hint_used") or {}, ensure_ascii=False),
        "feedback_json": json.dumps(payload.get("feedback") or {}, ensure_ascii=False),
        "active_index": max(0, min(len(quiz_ids) - 1, int(payload.get("active_index") or 0))),
        "display_mode": "all" if payload.get("display_mode") == "all" else "single",
        "elapsed_seconds": max(0, min(21600, int(payload.get("elapsed_seconds") or 0))),
    }
    if run_id:
        current = conn.execute(
            "SELECT id FROM practice_runs WHERE id = ? AND learner_key = ? AND status = 'in_progress'",
            (run_id, learner_key),
        ).fetchone()
        if not current:
            raise ValueError("Active practice run not found")
        assignments = ", ".join(f"{key} = ?" for key in state)
        completed_at = now if status == "completed" else ""
        conn.execute(
            f"UPDATE practice_runs SET {assignments}, updated_at = ?, completed_at = ? WHERE id = ?",
            (*state.values(), now, completed_at, run_id),
        )
    else:
        conn.execute(
            "UPDATE practice_runs SET status = 'abandoned', updated_at = ?, completed_at = ? WHERE learner_key = ? AND status = 'in_progress'",
            (now, now, learner_key),
        )
        columns = ", ".join(state)
        placeholders = ", ".join("?" for _ in state)
        cursor = conn.execute(
            f"""INSERT INTO practice_runs
                (learner_key, {columns}, started_at, updated_at, completed_at)
                VALUES (?, {placeholders}, ?, ?, ?)""",
            (learner_key, *state.values(), now, now, now if status == "completed" else ""),
        )
        run_id = int(cursor.lastrowid)
    row = conn.execute("SELECT * FROM practice_runs WHERE id = ?", (run_id,)).fetchone()
    return practice_run_payload(row)


def finish_practice_run(
    conn: sqlite3.Connection,
    run_id: int,
    now: str,
    status: str = "completed",
    practice_session_id: int | None = None,
) -> dict:
    if status not in {"completed", "abandoned"}:
        raise ValueError("A practice run can only be completed or abandoned")
    current = conn.execute("SELECT * FROM practice_runs WHERE id = ?", (run_id,)).fetchone()
    if not current:
        raise ValueError("Practice run not found")
    if practice_session_id is not None and not conn.execute(
        "SELECT 1 FROM practice_sessions WHERE id = ?", (practice_session_id,)
    ).fetchone():
        raise ValueError("Practice session not found")
    conn.execute(
        """UPDATE practice_runs SET status = ?, practice_session_id = ?,
           updated_at = ?, completed_at = ? WHERE id = ?""",
        (status, practice_session_id, now, now, run_id),
    )
    return practice_run_payload(conn.execute("SELECT * FROM practice_runs WHERE id = ?", (run_id,)).fetchone())


def training_prescription(conn: sqlite3.Connection, style: str, default_question_type: str = "") -> dict:
    rows = conn.execute(
        """SELECT at.correct, at.confidence, at.elapsed_seconds, at.answer_changes, at.hint_used,
                  at.created_at, q.id AS quiz_id, q.question_type, q.skill
           FROM attempts at
           JOIN quizzes q ON q.id = at.quiz_id
           WHERE q.style = ?
           ORDER BY at.created_at DESC, at.id DESC LIMIT 120""",
        (style,),
    ).fetchall()
    if not rows:
        return {
            "style": style, "status": "bootstrap", "sample_count": 0,
            "question_type": default_question_type, "skill": "待建立基线", "priority_score": 0,
            "recommended_count": 5,
            "reasons": ["尚无有效作答证据，先完成 5 道专项题建立基线。"],
            "metrics": {"accuracy": None, "average_seconds": None, "average_changes": 0, "hint_rate": 0, "certain_wrong_rate": 0},
            "evidence_note": "处方会在作答后根据正确率、用时、改答、提示和信心更新。",
        }
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        item = dict(row)
        buckets[item.get("question_type") or "mixed"].append(item)
    candidates = []
    for question_type, values in buckets.items():
        total = len(values)
        unique_quiz_count = len({item["quiz_id"] for item in values})
        correct = sum(1 for item in values if item["correct"])
        timed = [int(item["elapsed_seconds"] or 0) for item in values if int(item["elapsed_seconds"] or 0) > 0]
        average_seconds = round(sum(timed) / len(timed)) if timed else None
        average_changes = round(sum(int(item["answer_changes"] or 0) for item in values) / total, 1)
        hint_rate = round(sum(1 for item in values if item["hint_used"]) / total, 2)
        certain_wrong_rate = round(sum(1 for item in values if item["confidence"] == 3 and not item["correct"]) / total, 2)
        accuracy = round(correct / total * 100)
        target_seconds = 45 if any(token in question_type for token in ("gap", "cloze", "word", "vocabulary")) else 75
        speed_penalty = 0 if average_seconds is None else min(20, max(0, round((average_seconds / target_seconds - 1) * 20)))
        priority = round((100 - accuracy) * 0.45 + speed_penalty + min(15, average_changes * 5) + hint_rate * 10 + certain_wrong_rate * 15)
        reasons = []
        if accuracy < 70:
            reasons.append(f"近 {total} 题正确率 {accuracy}%，低于当前稳固线 70%。")
        if average_seconds and average_seconds > target_seconds:
            reasons.append(f"平均用时 {average_seconds} 秒，高于当前参考值 {target_seconds} 秒。")
        if average_changes >= 0.5:
            reasons.append(f"平均改答 {average_changes} 次，说明选项排除仍不稳定。")
        if hint_rate >= 0.25:
            reasons.append(f"提示使用率 {round(hint_rate * 100)}%，需要强化独立定位。")
        if certain_wrong_rate:
            reasons.append(f"确定但答错占 {round(certain_wrong_rate * 100)}%，优先修正判断规则。")
        if not reasons:
            reasons.append(f"近 {total} 题表现相对稳定，用一组短训练确认是否真正掌握。")
        if unique_quiz_count < 3:
            reasons.append(f"当前只覆盖 {unique_quiz_count} 道独立题，处方置信度较低，需要更多不同证据。")
        candidates.append({
            "question_type": question_type,
            "skill": next((item.get("skill") for item in values if item.get("skill")), "阅读理解"),
            "priority_score": priority,
            "sample_count": total,
            "unique_quiz_count": unique_quiz_count,
            "evidence_confidence": "high" if unique_quiz_count >= 8 else "medium" if unique_quiz_count >= 3 else "low",
            "recommended_count": 10 if priority >= 35 else 5,
            "reasons": reasons,
            "metrics": {
                "accuracy": accuracy, "average_seconds": average_seconds,
                "average_changes": average_changes, "hint_rate": hint_rate,
                "certain_wrong_rate": certain_wrong_rate,
            },
        })
    focus = max(candidates, key=lambda item: (item["priority_score"], item["sample_count"]))
    return {
        "style": style, "status": "ready", **focus,
        "alternatives": sorted(candidates, key=lambda item: item["priority_score"], reverse=True)[1:4],
        "evidence_note": "规则处方使用最近 120 次作答，并同时报告独立题目覆盖；它是可解释建议，不是考试分数预测。",
    }
