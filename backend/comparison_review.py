from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone


WORKFLOW_STATUSES = {"candidate", "evidence_ready", "reviewing", "published", "rejected"}
REQUIRED_ITEM_FIELDS = {
    "term", "pos", "meaning_zh", "focus_en", "focus", "patterns",
    "register", "avoid", "example", "example_zh", "example_source",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _loads(value: str, fallback):
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback


def validate_editorial_payload(payload: dict, expected_terms: list[str]) -> list[str]:
    errors: list[str] = []
    if not str(payload.get("summary") or "").strip():
        errors.append("summary is required")
    if not str(payload.get("memory_rule") or "").strip():
        errors.append("memory_rule is required")
    if len(payload.get("dimensions") or []) < 3:
        errors.append("at least three comparison dimensions are required")
    items = payload.get("items") or []
    if {str(item.get("term") or "").casefold() for item in items} != {term.casefold() for term in expected_terms}:
        errors.append("editorial items must match every group term")
    for item in items:
        term = str(item.get("term") or "")
        missing = sorted(field for field in REQUIRED_ITEM_FIELDS if not item.get(field))
        if missing:
            errors.append(f"{term or 'item'} missing: {', '.join(missing)}")
        if len(item.get("patterns") or []) < 2:
            errors.append(f"{term or 'item'} requires at least two patterns")
    return errors


def sync_comparison_registry(conn: sqlite3.Connection, catalog: list[dict]) -> None:
    now = _now()
    for group in catalog:
        initial_status = "published" if group.get("reviewed") else "candidate"
        priority = 80 if "IELTS" in group.get("exam_tags", []) else 50
        conn.execute(
            """INSERT INTO lexical_comparison_reviews
               (slug, terms_json, confusion_type, topic, exam_tags_json, workflow_status,
                priority, created_at, updated_at, reviewed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(slug) DO UPDATE SET
                 terms_json = excluded.terms_json,
                 confusion_type = excluded.confusion_type,
                 topic = excluded.topic,
                 exam_tags_json = excluded.exam_tags_json""",
            (
                group["slug"], json.dumps(group["terms"], ensure_ascii=False),
                group.get("confusion_type", "semantic"), group.get("topic", "general"),
                json.dumps(group.get("exam_tags", []), ensure_ascii=False), initial_status,
                priority, now, now, now if initial_status == "published" else "",
            ),
        )


def comparison_review_payload(row: sqlite3.Row) -> dict:
    evidence = _loads(row["evidence_json"], {})
    editorial = _loads(row["editorial_json"], {})
    return {
        "slug": row["slug"], "terms": _loads(row["terms_json"], []),
        "confusion_type": row["confusion_type"], "topic": row["topic"],
        "exam_tags": _loads(row["exam_tags_json"], []),
        "workflow_status": row["workflow_status"], "priority": row["priority"],
        "evidence": evidence, "editorial": editorial,
        "editor_notes": row["editor_notes"], "decision_reason": row["decision_reason"],
        "quality": {
            "bilingual_examples": int(evidence.get("bilingual_examples") or 0),
            "verified_patterns": int(evidence.get("verified_patterns") or 0),
            "editorial_errors": validate_editorial_payload(editorial, _loads(row["terms_json"], [])) if editorial else [],
        },
        "updated_at": row["updated_at"], "reviewed_at": row["reviewed_at"],
    }


def catalog_with_review_status(conn: sqlite3.Connection, catalog: list[dict]) -> list[dict]:
    rows = {row["slug"]: row for row in conn.execute("SELECT * FROM lexical_comparison_reviews")}
    result = []
    for group in catalog:
        item = dict(group)
        row = rows.get(group["slug"])
        if row:
            editorial = _loads(row["editorial_json"], {})
            item["workflow_status"] = row["workflow_status"]
            item["priority"] = row["priority"]
            if row["workflow_status"] == "published":
                item["reviewed"] = True
                item["catalog_status"] = "reviewed"
                for key in ("summary", "shared_translation", "memory_rule"):
                    if editorial.get(key):
                        item[key] = editorial[key]
        result.append(item)
    return sorted(result, key=lambda item: (-int(item.get("priority") or 0), item["title"]))


def published_editorial(conn: sqlite3.Connection, slug: str) -> dict | None:
    row = conn.execute(
        "SELECT terms_json, workflow_status, editorial_json FROM lexical_comparison_reviews WHERE slug = ?",
        (slug,),
    ).fetchone()
    if not row or row["workflow_status"] != "published":
        return None
    editorial = _loads(row["editorial_json"], {})
    return editorial if not validate_editorial_payload(editorial, _loads(row["terms_json"], [])) else None


def comparison_review_queue(conn: sqlite3.Connection, status: str = "", exam: str = "", limit: int = 200) -> dict:
    clauses, params = [], []
    if status:
        if status not in WORKFLOW_STATUSES:
            raise ValueError("Invalid comparison review status")
        clauses.append("workflow_status = ?")
        params.append(status)
    if exam:
        clauses.append("exam_tags_json LIKE ?")
        params.append(f'%"{exam.upper()}"%')
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"""SELECT * FROM lexical_comparison_reviews {where}
            ORDER BY CASE workflow_status WHEN 'reviewing' THEN 0 WHEN 'evidence_ready' THEN 1
                     WHEN 'candidate' THEN 2 WHEN 'rejected' THEN 3 ELSE 4 END,
                     priority DESC, slug LIMIT ?""",
        (*params, max(1, min(int(limit), 500))),
    ).fetchall()
    counts = {row["workflow_status"]: row["count"] for row in conn.execute(
        "SELECT workflow_status, COUNT(*) AS count FROM lexical_comparison_reviews GROUP BY workflow_status"
    )}
    return {"items": [comparison_review_payload(row) for row in rows], "counts": counts, "total": sum(counts.values())}


def update_comparison_review(conn: sqlite3.Connection, slug: str, payload: dict) -> dict:
    row = conn.execute("SELECT * FROM lexical_comparison_reviews WHERE slug = ?", (slug,)).fetchone()
    if not row:
        raise ValueError("Comparison review group not found")
    status = str(payload.get("workflow_status") or row["workflow_status"])
    if status not in WORKFLOW_STATUSES:
        raise ValueError("Invalid comparison review status")
    priority = max(0, min(int(payload.get("priority", row["priority"])), 100))
    editorial = payload.get("editorial") if "editorial" in payload else _loads(row["editorial_json"], {})
    evidence = payload.get("evidence", _loads(row["evidence_json"], {}))
    if not isinstance(editorial, dict) or not isinstance(evidence, dict):
        raise TypeError("Editorial and evidence payloads must be objects")
    term_count = len(_loads(row["terms_json"], []))
    if status == "evidence_ready" and (
        int(evidence.get("bilingual_examples") or 0) < term_count
        or int(evidence.get("verified_patterns") or 0) < term_count * 2
    ):
        raise ValueError("Evidence-ready requires one bilingual example and two verified patterns per term")
    if status == "published":
        errors = validate_editorial_payload(editorial, _loads(row["terms_json"], []))
        static_reviewed_group = row["workflow_status"] == "published" and not row["editorial_json"].strip(" {}")
        if errors and (not static_reviewed_group or "editorial" in payload):
            raise ValueError("Publication blocked: " + "; ".join(errors))
    if status == "rejected" and not str(payload.get("decision_reason") or row["decision_reason"]).strip():
        raise ValueError("A rejection reason is required")
    now = _now()
    conn.execute(
        """UPDATE lexical_comparison_reviews SET workflow_status = ?, priority = ?,
           evidence_json = ?, editorial_json = ?, editor_notes = ?, decision_reason = ?,
           updated_at = ?, reviewed_at = CASE WHEN ? = 'published' THEN ? ELSE reviewed_at END
           WHERE slug = ?""",
        (
            status, priority, json.dumps(evidence, ensure_ascii=False),
            json.dumps(editorial, ensure_ascii=False), str(payload.get("editor_notes", row["editor_notes"])),
            str(payload.get("decision_reason", row["decision_reason"])), now, status, now, slug,
        ),
    )
    return comparison_review_payload(conn.execute(
        "SELECT * FROM lexical_comparison_reviews WHERE slug = ?", (slug,)
    ).fetchone())
