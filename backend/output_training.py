from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone


GENERATION_VERSION = "context-output-rule-v1"
TASK_TYPES = ("en_to_zh", "zh_to_en", "summary", "personal")
TASK_LABELS = {
    "en_to_zh": "理解翻译",
    "zh_to_en": "重构翻译",
    "summary": "三句摘要",
    "personal": "个人表达",
}
SELF_REVIEW_FIELDS = ("information", "naturalness", "chunk_use")
ENGLISH_WORD = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for", "from",
    "has", "have", "he", "her", "his", "in", "is", "it", "its", "of", "on", "or",
    "she", "that", "the", "their", "they", "this", "to", "was", "were", "will", "with",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def paragraphs(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", value).strip() for value in re.split(r"\n\s*\n", text or "") if value.strip()]


def sentences(text: str) -> list[str]:
    values = re.findall(r"[^.!?。！？]+[.!?。！？]?", text or "")
    return [re.sub(r"\s+", " ", value).strip() for value in values if value.strip()]


def english_words(text: str) -> list[str]:
    return [value.lower() for value in ENGLISH_WORD.findall(text or "")]


def sentence_count(text: str) -> int:
    return len(sentences(text))


def _content_terms(text: str) -> set[str]:
    return {word for word in english_words(text) if len(word) > 3 and word not in STOP_WORDS}


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _load_json(value: str, fallback: object) -> object:
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError):
        return fallback
    return parsed


def _aligned_translation_pair(article: sqlite3.Row | dict) -> tuple[str, str] | None:
    source_paragraphs = paragraphs(article["body"])
    translated_paragraphs = paragraphs(article.get("translation_zh", "") if isinstance(article, dict) else article["translation_zh"])
    if not translated_paragraphs or len(source_paragraphs) != len(translated_paragraphs):
        return None
    candidates = []
    for source, translated in zip(source_paragraphs, translated_paragraphs):
        count = len(english_words(source))
        if 12 <= count <= 90 and translated.strip():
            candidates.append((abs(count - 35), source, translated))
    if not candidates:
        return None
    _, source, translated = min(candidates, key=lambda item: item[0])
    return source, translated


def _summary_source(body: str) -> str:
    selected = []
    count = 0
    for paragraph in paragraphs(body):
        paragraph_count = len(english_words(paragraph))
        if selected and count + paragraph_count > 420:
            break
        selected.append(paragraph)
        count += paragraph_count
        if len(selected) >= 3:
            break
    return "\n\n".join(selected) or body.strip()


def _summary_points(source: str) -> str:
    points = []
    for paragraph in paragraphs(source):
        values = sentences(paragraph)
        if values:
            points.append(values[0])
        if len(points) >= 3:
            break
    if len(points) < 3:
        for value in sentences(source):
            if value not in points:
                points.append(value)
            if len(points) >= 3:
                break
    return "\n".join(points)


def _target_chunks(body: str, candidates: list[str]) -> list[str]:
    source = body.casefold()
    values = []
    for candidate in candidates:
        clean = re.sub(r"\s+", " ", str(candidate or "")).strip()
        if len(clean) < 3 or clean.casefold() not in source:
            continue
        if clean.casefold() not in {item.casefold() for item in values}:
            values.append(clean)
        if len(values) >= 5:
            break
    if not values:
        ranked = sorted(_content_terms(body), key=lambda value: (-len(value), value))
        values = ranked[:5]
    return values


def _task_payload(row: sqlite3.Row | dict) -> dict:
    item = dict(row)
    item["target_chunks"] = _load_json(item.pop("target_chunks_json", "[]"), [])
    item["guidance"] = _load_json(item.pop("guidance_json", "{}"), {})
    item["label"] = TASK_LABELS.get(item["task_type"], item["task_type"])
    return item


def create_output_task_set(
    conn: sqlite3.Connection,
    article: sqlite3.Row | dict,
    chunk_candidates: list[str] | None = None,
    force_new: bool = False,
) -> dict:
    article_id = int(article["id"])
    if not force_new:
        existing = conn.execute(
            "SELECT id FROM output_task_sets WHERE article_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
            (article_id,),
        ).fetchone()
        if existing:
            return output_task_set_payload(conn, int(existing["id"]))

    body = str(article["body"] or "").strip()
    if len(english_words(body)) < 40:
        raise ValueError("The article is too short for contextual output training")
    now = utc_now()
    source_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    cursor = conn.execute(
        """INSERT INTO output_task_sets
           (article_id, source_hash, generation_version, status, created_at)
           VALUES (?, ?, ?, 'active', ?)""",
        (article_id, source_hash, GENERATION_VERSION, now),
    )
    set_id = int(cursor.lastrowid)
    chunks = _target_chunks(body, chunk_candidates or [])
    tasks: list[dict] = []
    pair = _aligned_translation_pair(article)
    if pair:
        source, translated = pair
        tasks.extend([
            {
                "task_type": "en_to_zh", "prompt_text": source, "source_text": source,
                "reference_text": translated, "target_chunks": chunks[:3],
                "guidance": {"instruction": "先独立翻译，再与参考译文核对信息、否定、程度和指代。", "reference_label": "参考译文（非唯一答案）"},
            },
            {
                "task_type": "zh_to_en", "prompt_text": translated, "source_text": source,
                "reference_text": source, "target_chunks": [chunk for chunk in chunks if chunk.casefold() in source.casefold()][:3],
                "guidance": {"instruction": "隐藏原文后重新表达，提交后检查遗漏信息与词块。", "reference_label": "原文表达（非唯一答案）"},
            },
        ])
    summary_source = _summary_source(body)
    tasks.append({
        "task_type": "summary", "prompt_text": "用三句英语概括这段材料的核心事实、原因和意义。",
        "source_text": summary_source, "reference_text": _summary_points(summary_source),
        "target_chunks": chunks[:4],
        "guidance": {"instruction": "不要复制整段原文；优先保留事实关系，再考虑表达变化。", "reference_label": "参考要点（不是参考答案）"},
    })
    target = chunks[0] if chunks else "the main idea"
    context = next((value for value in sentences(body) if target.casefold() in value.casefold()), sentences(body)[0] if sentences(body) else body)
    tasks.append({
        "task_type": "personal", "prompt_text": f"使用“{target}”写一句与你的经历、兴趣或观点有关的英语。",
        "source_text": context, "reference_text": context, "target_chunks": [target],
        "guidance": {"instruction": "保留目标词块的自然搭配，但内容必须与你自己有关。", "reference_label": "原文中的用法"},
    })
    for position, task in enumerate(tasks, start=1):
        conn.execute(
            """INSERT INTO output_tasks
               (set_id, article_id, position, task_type, prompt_text, source_text, reference_text,
                target_chunks_json, guidance_json, generation_source, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                set_id, article_id, position, task["task_type"], task["prompt_text"], task["source_text"],
                task["reference_text"], _json(task["target_chunks"]), _json(task["guidance"]),
                GENERATION_VERSION, now,
            ),
        )
    return output_task_set_payload(conn, set_id)


def output_task_set_payload(conn: sqlite3.Connection, set_id: int) -> dict | None:
    task_set = conn.execute(
        """SELECT s.*, a.title AS article_title, a.source, a.body AS article_body,
                  a.translation_zh AS article_translation
           FROM output_task_sets s JOIN articles a ON a.id = s.article_id WHERE s.id = ?""",
        (set_id,),
    ).fetchone()
    if not task_set:
        return None
    rows = conn.execute(
        """SELECT t.*, COUNT(a.id) AS attempt_count, MAX(a.created_at) AS last_attempt_at
           FROM output_tasks t LEFT JOIN output_attempts a ON a.task_id = t.id
           WHERE t.set_id = ? GROUP BY t.id ORDER BY t.position""",
        (set_id,),
    ).fetchall()
    tasks = [_task_payload(row) for row in rows]
    completed = sum(bool(task["attempt_count"]) for task in tasks)
    return {
        "set": dict(task_set), "tasks": tasks,
        "summary": {"total": len(tasks), "completed": completed, "remaining": len(tasks) - completed},
    }


def latest_output_task_set(conn: sqlite3.Connection, article_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id FROM output_task_sets WHERE article_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
        (article_id,),
    ).fetchone()
    return output_task_set_payload(conn, int(row["id"])) if row else None


def deterministic_feedback(task: sqlite3.Row | dict, response: str) -> dict:
    source = dict(task)
    task_type = source["task_type"]
    reference = source.get("reference_text") or ""
    chunks = _load_json(source.get("target_chunks_json") or "[]", [])
    response_words = english_words(response)
    checks = []

    if task_type == "en_to_zh":
        checks.append({"id": "response", "label": "已经独立完成译文", "passed": len(response.strip()) >= 8})
        checks.append({"id": "review", "label": "提交后核对主语、否定、程度与指代", "passed": None})
    elif task_type == "zh_to_en":
        reference_terms = _content_terms(reference)
        response_terms = _content_terms(response)
        overlap = len(reference_terms & response_terms) / max(1, len(reference_terms))
        checks.append({"id": "coverage", "label": "核心信息词覆盖", "passed": overlap >= 0.45, "score": round(overlap, 2)})
        source_numbers = set(re.findall(r"\d+(?:\.\d+)?", reference))
        response_numbers = set(re.findall(r"\d+(?:\.\d+)?", response))
        checks.append({"id": "numbers", "label": "数字信息保持", "passed": not source_numbers or source_numbers <= response_numbers})
        reference_negative = bool(re.search(r"\b(?:not|never|no|without|hardly|cannot|can't|don't|doesn't|didn't)\b", reference, re.I))
        response_negative = bool(re.search(r"\b(?:not|never|no|without|hardly|cannot|can't|don't|doesn't|didn't)\b", response, re.I))
        checks.append({"id": "negation", "label": "否定关系保持", "passed": not reference_negative or response_negative})
    elif task_type == "summary":
        count = len(response_words)
        checks.append({"id": "length", "label": "摘要长度 25-120 词", "passed": 25 <= count <= 120, "value": count})
        checks.append({"id": "sentences", "label": "至少形成三句表达", "passed": sentence_count(response) >= 3, "value": sentence_count(response)})
        source_terms = _content_terms(source.get("source_text") or "")
        overlap = len(source_terms & set(response_words)) / max(1, min(12, len(source_terms)))
        checks.append({"id": "concepts", "label": "覆盖多个原文核心概念", "passed": overlap >= 0.25, "score": round(overlap, 2)})
        normalized_source = re.sub(r"\W+", " ", source.get("source_text") or "").casefold()
        normalized_response = re.sub(r"\W+", " ", response).casefold().strip()
        checks.append({"id": "copy", "label": "没有整段复制原文", "passed": not normalized_response or normalized_response not in normalized_source})
    else:
        target = str(chunks[0] if chunks else "").strip()
        checks.append({"id": "chunk", "label": f"使用目标词块 {target}", "passed": bool(target) and target.casefold() in response.casefold()})
        checks.append({"id": "sentence", "label": "形成完整个人表达", "passed": len(response_words) >= 5 and sentence_count(response) >= 1})

    passed = sum(check["passed"] is True for check in checks)
    applicable = sum(check["passed"] is not None for check in checks)
    return {
        "version": GENERATION_VERSION,
        "checks": checks,
        "passed": passed,
        "applicable": applicable,
        "note": "规则检查只处理可确定的形式与信息信号；自然度和开放语义需要自评或后续 AI 反馈。",
    }


def submit_output_attempt(
    conn: sqlite3.Connection,
    task_id: int,
    response: str,
    elapsed_seconds: int = 0,
    hint_used: bool = False,
    confidence: int | None = None,
) -> dict:
    task = conn.execute("SELECT * FROM output_tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        raise ValueError("Output task not found")
    answer = re.sub(r"\r\n?", "\n", str(response or "")).strip()
    if len(answer) < 3:
        raise ValueError("Write an answer before submitting")
    if len(answer) > 5000:
        raise ValueError("The output answer is too long")
    safe_confidence = None if confidence in (None, "") else max(1, min(3, int(confidence)))
    feedback = deterministic_feedback(task, answer)
    now = utc_now()
    cursor = conn.execute(
        """INSERT INTO output_attempts
           (task_id, response_text, elapsed_seconds, hint_used, confidence, sentence_count,
            deterministic_feedback_json, self_review_json, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, '{}', ?, ?)""",
        (
            task_id, answer, max(0, min(7200, int(elapsed_seconds or 0))), int(bool(hint_used)),
            safe_confidence, max(1, sentence_count(answer)), _json(feedback), now, now,
        ),
    )
    return output_attempt_payload(conn, int(cursor.lastrowid))


def output_attempt_payload(conn: sqlite3.Connection, attempt_id: int) -> dict | None:
    row = conn.execute(
        """SELECT a.*, t.set_id, t.article_id, t.position, t.task_type, t.prompt_text,
                  t.source_text, t.reference_text, t.target_chunks_json, t.guidance_json,
                  ar.title AS article_title, ar.source AS article_source
           FROM output_attempts a JOIN output_tasks t ON t.id = a.task_id
           JOIN articles ar ON ar.id = t.article_id WHERE a.id = ?""",
        (attempt_id,),
    ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["feedback"] = _load_json(item.pop("deterministic_feedback_json", "{}"), {})
    item["self_review"] = _load_json(item.pop("self_review_json", "{}"), {})
    item["target_chunks"] = _load_json(item.pop("target_chunks_json", "[]"), [])
    item["guidance"] = _load_json(item.pop("guidance_json", "{}"), {})
    item["task_label"] = TASK_LABELS.get(item["task_type"], item["task_type"])
    links = conn.execute(
        """SELECT l.*, c.term, c.context FROM output_review_links l
           JOIN cards c ON c.id = l.card_id WHERE l.attempt_id = ? ORDER BY l.id""",
        (attempt_id,),
    ).fetchall()
    item["review_links"] = [dict(link) for link in links]
    return item


def save_self_review(conn: sqlite3.Connection, attempt_id: int, values: dict, note: str = "") -> dict:
    if not conn.execute("SELECT 1 FROM output_attempts WHERE id = ?", (attempt_id,)).fetchone():
        raise ValueError("Output attempt not found")
    review = {}
    for field in SELF_REVIEW_FIELDS:
        value = int(values.get(field) or 0)
        if value not in {1, 2, 3}:
            raise ValueError("Self-review values must be 1, 2, or 3")
        review[field] = value
    review["note"] = str(note or "").strip()[:500]
    review["version"] = "output-self-review-v1"
    conn.execute(
        "UPDATE output_attempts SET self_review_json = ?, updated_at = ? WHERE id = ?",
        (_json(review), utc_now(), attempt_id),
    )
    return output_attempt_payload(conn, attempt_id)


def output_history(conn: sqlite3.Connection, limit: int = 50) -> dict:
    safe_limit = max(1, min(100, int(limit or 50)))
    rows = conn.execute(
        "SELECT id FROM output_attempts ORDER BY created_at DESC, id DESC LIMIT ?",
        (safe_limit,),
    ).fetchall()
    attempts = [output_attempt_payload(conn, int(row["id"])) for row in rows]
    totals = conn.execute(
        """SELECT COUNT(*) AS attempts, COALESCE(SUM(sentence_count), 0) AS sentences,
                  COUNT(DISTINCT t.article_id) AS articles
           FROM output_attempts a JOIN output_tasks t ON t.id = a.task_id"""
    ).fetchone()
    return {"attempts": attempts, "summary": dict(totals)}
