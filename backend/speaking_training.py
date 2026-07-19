from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone


TASK_LABELS = {"retell": "脱稿复述", "opinion": "观点表达", "chunk": "词块口头造句"}
SELF_REVIEW_FIELDS = ("content", "coherence", "fluency", "chunk_use", "grammar_impact")
ENGLISH_WORD = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for", "from",
    "has", "have", "in", "is", "it", "of", "on", "or", "that", "the", "their", "this",
    "to", "was", "were", "will", "with",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _load_json(value: str, fallback: object) -> object:
    try:
        return json.loads(value or "")
    except (TypeError, ValueError):
        return fallback


def _words(text: str) -> list[str]:
    return [word.lower() for word in ENGLISH_WORD.findall(text or "")]


def _paragraphs(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", part).strip() for part in re.split(r"\n\s*\n", text or "") if part.strip()]


def _source_excerpt(body: str, limit: int = 240) -> str:
    selected = []
    count = 0
    for paragraph in _paragraphs(body):
        words = len(_words(paragraph))
        if selected and count + words > limit:
            break
        selected.append(paragraph)
        count += words
        if len(selected) >= 3:
            break
    return "\n\n".join(selected) or str(body or "").strip()


def _chunks(body: str, candidates: list[str]) -> list[str]:
    source = str(body or "").casefold()
    values = []
    for candidate in candidates:
        clean = re.sub(r"\s+", " ", str(candidate or "")).strip()
        if clean and clean.casefold() in source and clean.casefold() not in {item.casefold() for item in values}:
            values.append(clean)
        if len(values) >= 4:
            break
    if not values:
        terms = {word for word in _words(body) if len(word) > 5 and word not in STOP_WORDS}
        values = sorted(terms, key=lambda word: (-len(word), word))[:4]
    return values


def _task_payload(row: sqlite3.Row | dict) -> dict:
    item = dict(row)
    item["target_chunks"] = _load_json(item.pop("target_chunks_json", "[]"), [])
    item["label"] = TASK_LABELS.get(item["task_type"], item["task_type"])
    item["evidence_eligible"] = bool(item.get("evidence_eligible"))
    return item


def create_speaking_task_set(
    conn: sqlite3.Connection,
    article: sqlite3.Row | dict,
    chunk_candidates: list[str] | None = None,
    duration_target: int = 60,
    prep_seconds: int = 15,
    force_new: bool = False,
) -> dict:
    duration = int(duration_target)
    if duration not in {30, 60, 90}:
        raise ValueError("Speaking duration must be 30, 60, or 90 seconds")
    prep = max(0, min(60, int(prep_seconds or 0)))
    article_id = int(article["id"])
    if not force_new:
        existing = conn.execute(
            """SELECT id FROM speaking_task_sets
               WHERE article_id = ? AND duration_target = ? AND status = 'active'
               ORDER BY id DESC LIMIT 1""",
            (article_id, duration),
        ).fetchone()
        if existing:
            return speaking_task_set_payload(conn, int(existing["id"]))
    body = str(article["body"] or "").strip()
    if len(_words(body)) < 40:
        raise ValueError("The article is too short for speaking practice")
    excerpt = _source_excerpt(body)
    chunks = _chunks(body, chunk_candidates or [])
    target = chunks[0] if chunks else "the main idea"
    now = utc_now()
    cursor = conn.execute(
        """INSERT INTO speaking_task_sets
           (article_id, source_hash, duration_target, prep_seconds, status, created_at)
           VALUES (?, ?, ?, ?, 'active', ?)""",
        (article_id, hashlib.sha256(body.encode("utf-8")).hexdigest(), duration, prep, now),
    )
    set_id = int(cursor.lastrowid)
    title = str(article["title"] or "this article")
    tasks = (
        ("retell", f"不看原文，用英语概括《{title}》的核心事实、原因和意义。", excerpt, chunks[:3], 1),
        ("opinion", f"结合文章表达你的观点：其中最值得讨论的影响是什么，为什么？", excerpt, chunks[:3], 1),
        ("chunk", f"使用“{target}”说一段与你的学习、生活或兴趣有关的话。", excerpt, [target], 0),
    )
    for position, (task_type, prompt, source, target_chunks, eligible) in enumerate(tasks, start=1):
        conn.execute(
            """INSERT INTO speaking_tasks
               (set_id, article_id, position, task_type, prompt_text, source_text,
                target_chunks_json, evidence_eligible, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (set_id, article_id, position, task_type, prompt, source, _json(target_chunks), eligible, now),
        )
    return speaking_task_set_payload(conn, set_id)


def speaking_task_set_payload(conn: sqlite3.Connection, set_id: int) -> dict | None:
    task_set = conn.execute(
        """SELECT s.*, a.title AS article_title, a.source, a.body AS article_body
           FROM speaking_task_sets s JOIN articles a ON a.id = s.article_id WHERE s.id = ?""",
        (set_id,),
    ).fetchone()
    if not task_set:
        return None
    rows = conn.execute(
        """SELECT t.*, COUNT(a.id) AS attempt_count, MAX(a.created_at) AS last_attempt_at
           FROM speaking_tasks t LEFT JOIN speaking_attempts a ON a.task_id = t.id AND a.status != 'deleted'
           WHERE t.set_id = ? GROUP BY t.id ORDER BY t.position""",
        (set_id,),
    ).fetchall()
    tasks = [_task_payload(row) for row in rows]
    return {"set": dict(task_set), "tasks": tasks, "summary": {"total": len(tasks), "attempted": sum(bool(task["attempt_count"]) for task in tasks)}}


def latest_speaking_task_set(conn: sqlite3.Connection, article_id: int, duration_target: int | None = None) -> dict | None:
    params: list[object] = [article_id]
    where = "article_id = ? AND status = 'active'"
    if duration_target in {30, 60, 90}:
        where += " AND duration_target = ?"
        params.append(duration_target)
    row = conn.execute(f"SELECT id FROM speaking_task_sets WHERE {where} ORDER BY id DESC LIMIT 1", params).fetchone()
    return speaking_task_set_payload(conn, int(row["id"])) if row else None


def transcript_analysis(task: sqlite3.Row | dict, transcript: str, duration_seconds: int) -> dict:
    words = _words(transcript)
    source_terms = {word for word in _words(task["source_text"]) if len(word) > 3 and word not in STOP_WORDS}
    transcript_terms = set(words)
    source_coverage = len(source_terms & transcript_terms) / max(1, min(20, len(source_terms)))
    filler_pattern = re.compile(r"\b(?:um+|uh+|erm+|you know|I mean)\b", re.I)
    filler_count = len(filler_pattern.findall(transcript or ""))
    repeated = sum(1 for left, right in zip(words, words[1:]) if left == right)
    chunks = _load_json(task.get("target_chunks_json", "[]") if isinstance(task, dict) else task["target_chunks_json"], [])
    used_chunks = [chunk for chunk in chunks if str(chunk).casefold() in transcript.casefold()]
    return {
        "version": "speaking-transcript-rules-v1",
        "word_count": len(words),
        "words_per_minute": round(len(words) / max(1, duration_seconds) * 60),
        "source_coverage": round(min(1, source_coverage), 2),
        "filler_count": filler_count,
        "immediate_repetitions": repeated,
        "target_chunks_used": used_chunks,
        "grammar_note": "规则分析不能可靠判断语法是否影响理解，请结合自评或后续 AI 反馈。",
    }


def create_speaking_attempt(conn: sqlite3.Connection, task_id: int, prep_seconds: int = 0, repeat_of_id: int | None = None) -> dict:
    task = conn.execute("SELECT * FROM speaking_tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        raise ValueError("Speaking task not found")
    if repeat_of_id:
        parent = conn.execute("SELECT task_id FROM speaking_attempts WHERE id = ?", (repeat_of_id,)).fetchone()
        if not parent or int(parent["task_id"]) != task_id:
            raise ValueError("Repeat attempt must use the same speaking task")
    now = utc_now()
    cursor = conn.execute(
        """INSERT INTO speaking_attempts
           (task_id, prep_seconds, repeat_of_id, status, created_at, updated_at)
           VALUES (?, ?, ?, 'draft', ?, ?)""",
        (task_id, max(0, min(300, int(prep_seconds or 0))), repeat_of_id, now, now),
    )
    return speaking_attempt_payload(conn, int(cursor.lastrowid))


def speaking_attempt_payload(conn: sqlite3.Connection, attempt_id: int) -> dict | None:
    row = conn.execute(
        """SELECT a.*, t.set_id, t.article_id, t.task_type, t.prompt_text, t.source_text,
                  t.target_chunks_json, t.evidence_eligible, ar.title AS article_title
           FROM speaking_attempts a JOIN speaking_tasks t ON t.id = a.task_id
           JOIN articles ar ON ar.id = t.article_id WHERE a.id = ?""",
        (attempt_id,),
    ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["target_chunks"] = _load_json(item.pop("target_chunks_json", "[]"), [])
    item["transcript_analysis"] = _load_json(item.pop("transcript_analysis_json", "{}"), {})
    item["self_review"] = _load_json(item.pop("self_review_json", "{}"), {})
    item["label"] = TASK_LABELS.get(item["task_type"], item["task_type"])
    item["evidence_eligible"] = bool(item["evidence_eligible"])
    item["audio_url"] = f"/api/speaking/audio/{attempt_id}" if item["audio_filename"] and item["status"] != "deleted" else ""
    links = conn.execute(
        """SELECT l.*, c.term, c.context FROM speaking_review_links l
           JOIN cards c ON c.id = l.card_id WHERE l.attempt_id = ? ORDER BY l.id""",
        (attempt_id,),
    ).fetchall()
    item["review_links"] = [dict(link) for link in links]
    return item


def attach_audio(conn: sqlite3.Connection, attempt_id: int, filename: str, mime_type: str, size_bytes: int, duration_seconds: int) -> dict:
    if not conn.execute("SELECT 1 FROM speaking_attempts WHERE id = ? AND status != 'deleted'", (attempt_id,)).fetchone():
        raise ValueError("Speaking attempt not found")
    conn.execute(
        """UPDATE speaking_attempts SET audio_filename = ?, audio_mime = ?, audio_bytes = ?,
           duration_seconds = ?, status = 'recorded', updated_at = ? WHERE id = ?""",
        (filename, mime_type, size_bytes, max(1, min(600, int(duration_seconds or 1))), utc_now(), attempt_id),
    )
    return speaking_attempt_payload(conn, attempt_id)


def save_transcript(conn: sqlite3.Connection, attempt_id: int, text: str, source: str, provider: str = "", model: str = "") -> dict:
    attempt = speaking_attempt_payload(conn, attempt_id)
    if not attempt or attempt["status"] == "deleted":
        raise ValueError("Speaking attempt not found")
    transcript = re.sub(r"\r\n?", "\n", str(text or "")).strip()
    if len(transcript) < 2 or len(transcript) > 10000:
        raise ValueError("Transcript must contain 2-10000 characters")
    task = conn.execute("SELECT * FROM speaking_tasks WHERE id = ?", (attempt["task_id"],)).fetchone()
    analysis = transcript_analysis(task, transcript, int(attempt["duration_seconds"] or 1))
    conn.execute(
        """UPDATE speaking_attempts SET transcript_text = ?, transcript_source = ?,
           transcript_provider = ?, transcript_model = ?, transcript_analysis_json = ?, updated_at = ?
           WHERE id = ?""",
        (transcript, source, provider, model, _json(analysis), utc_now(), attempt_id),
    )
    return speaking_attempt_payload(conn, attempt_id)


def save_speaking_self_review(conn: sqlite3.Connection, attempt_id: int, values: dict, note: str = "", stuck_expression: str = "") -> dict:
    if not conn.execute("SELECT 1 FROM speaking_attempts WHERE id = ? AND status != 'deleted'", (attempt_id,)).fetchone():
        raise ValueError("Speaking attempt not found")
    review = {}
    for field in SELF_REVIEW_FIELDS:
        value = int(values.get(field) or 0)
        if value not in {1, 2, 3}:
            raise ValueError("Speaking self-review values must be 1, 2, or 3")
        review[field] = value
    review.update({
        "note": str(note or "").strip()[:500],
        "stuck_expression": str(stuck_expression or "").strip()[:500],
        "version": "speaking-self-review-v1",
    })
    conn.execute(
        "UPDATE speaking_attempts SET self_review_json = ?, updated_at = ? WHERE id = ?",
        (_json(review), utc_now(), attempt_id),
    )
    return speaking_attempt_payload(conn, attempt_id)


def mark_speaking_attempt_deleted(conn: sqlite3.Connection, attempt_id: int) -> dict:
    attempt = speaking_attempt_payload(conn, attempt_id)
    if not attempt:
        raise ValueError("Speaking attempt not found")
    now = utc_now()
    conn.execute(
        """UPDATE speaking_attempts SET audio_filename = '', audio_bytes = 0,
           status = 'deleted', deleted_at = ?, updated_at = ? WHERE id = ?""",
        (now, now, attempt_id),
    )
    return attempt


def speaking_history(conn: sqlite3.Connection, limit: int = 50) -> dict:
    safe_limit = max(1, min(100, int(limit or 50)))
    rows = conn.execute(
        "SELECT id FROM speaking_attempts WHERE status != 'deleted' ORDER BY created_at DESC, id DESC LIMIT ?",
        (safe_limit,),
    ).fetchall()
    attempts = [speaking_attempt_payload(conn, int(row["id"])) for row in rows]
    totals = conn.execute(
        """SELECT COUNT(*) AS attempts, COALESCE(SUM(duration_seconds), 0) AS seconds,
                  COUNT(DISTINCT t.article_id) AS articles,
                  COALESCE(SUM(CASE WHEN t.evidence_eligible = 1 THEN 1 ELSE 0 END), 0) AS evidence_candidates
           FROM speaking_attempts a JOIN speaking_tasks t ON t.id = a.task_id WHERE a.status != 'deleted'"""
    ).fetchone()
    return {"attempts": attempts, "summary": dict(totals)}
