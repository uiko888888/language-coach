from __future__ import annotations

import sqlite3
import hashlib
import json
import re
from collections.abc import Callable
from datetime import datetime, timezone

try:
    from .content_extraction import extract_source_content
    from .lexical_data import ensure_lexical_data_schema
    from .review_scheduler import backfill_review_items
except ImportError:
    from content_extraction import extract_source_content
    from lexical_data import ensure_lexical_data_schema
    from review_scheduler import backfill_review_items


Migration = tuple[int, str, Callable[[sqlite3.Connection], None]]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    if column not in _columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _legacy_schema(conn: sqlite3.Connection) -> None:
    for column, definition in {
        "translation_zh": "TEXT NOT NULL DEFAULT ''",
        "content_status": "TEXT NOT NULL DEFAULT 'summary'",
        "content_type": "TEXT NOT NULL DEFAULT 'auto'",
        "published_at": "TEXT NOT NULL DEFAULT ''",
        "source_guid": "TEXT NOT NULL DEFAULT ''",
        "content_hash": "TEXT NOT NULL DEFAULT ''",
    }.items():
        _ensure_column(conn, "articles", column, definition)

    for column, definition in {
        "etag": "TEXT NOT NULL DEFAULT ''",
        "last_modified": "TEXT NOT NULL DEFAULT ''",
        "last_attempt_at": "TEXT NOT NULL DEFAULT ''",
        "last_success_at": "TEXT NOT NULL DEFAULT ''",
        "consecutive_failures": "INTEGER NOT NULL DEFAULT 0",
        "last_error": "TEXT NOT NULL DEFAULT ''",
    }.items():
        _ensure_column(conn, "feeds", column, definition)

    for column, definition in {
        "reward_claimed": "INTEGER NOT NULL DEFAULT 0",
        "skill": "TEXT NOT NULL DEFAULT ''",
        "error_type": "TEXT NOT NULL DEFAULT ''",
        "explanation_json": "TEXT NOT NULL DEFAULT '{}'",
    }.items():
        _ensure_column(conn, "mistakes", column, definition)

    for column, definition in {
        "question_type": "TEXT NOT NULL DEFAULT ''",
        "skill": "TEXT NOT NULL DEFAULT ''",
        "difficulty": "TEXT NOT NULL DEFAULT 'B2'",
        "validation_json": "TEXT NOT NULL DEFAULT '{}'",
        "generation_source": "TEXT NOT NULL DEFAULT 'legacy'",
        "metadata_json": "TEXT NOT NULL DEFAULT '{}'",
    }.items():
        _ensure_column(conn, "quizzes", column, definition)

    for column, definition in {
        "error_type": "TEXT NOT NULL DEFAULT ''",
        "session_id": "INTEGER",
        "confidence": "INTEGER",
    }.items():
        _ensure_column(conn, "attempts", column, definition)

    _ensure_column(conn, "practice_sessions", "confidence_summary_json", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(conn, "cards", "kind", "TEXT NOT NULL DEFAULT 'word'")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_source_guid "
        "ON articles(source, source_guid) WHERE source_guid != ''"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_content_hash "
        "ON articles(source, content_hash) WHERE content_hash != ''"
    )


def _training_loop_metrics(conn: sqlite3.Connection) -> None:
    for column, definition in {
        "elapsed_seconds": "INTEGER NOT NULL DEFAULT 0",
        "answer_changes": "INTEGER NOT NULL DEFAULT 0",
        "hint_used": "INTEGER NOT NULL DEFAULT 0",
    }.items():
        _ensure_column(conn, "attempts", column, definition)
    for column, definition in {
        "remedial_attempts": "INTEGER NOT NULL DEFAULT 0",
        "remedial_correct_streak": "INTEGER NOT NULL DEFAULT 0",
        "mastered_at": "TEXT NOT NULL DEFAULT ''",
        "mastery_source": "TEXT NOT NULL DEFAULT ''",
    }.items():
        _ensure_column(conn, "mistakes", column, definition)


def _practice_run_state(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS practice_runs (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             learner_key TEXT NOT NULL DEFAULT 'local',
             practice_session_id INTEGER,
             article_id INTEGER,
             style TEXT NOT NULL DEFAULT 'IELTS',
             question_type TEXT NOT NULL DEFAULT '',
             scope TEXT NOT NULL DEFAULT 'specialty',
             session_mode TEXT NOT NULL DEFAULT 'practice',
             status TEXT NOT NULL DEFAULT 'in_progress',
             quiz_ids_json TEXT NOT NULL DEFAULT '[]',
             answers_json TEXT NOT NULL DEFAULT '{}',
             confidence_json TEXT NOT NULL DEFAULT '{}',
             flagged_json TEXT NOT NULL DEFAULT '{}',
             answer_changes_json TEXT NOT NULL DEFAULT '{}',
             hint_used_json TEXT NOT NULL DEFAULT '{}',
             feedback_json TEXT NOT NULL DEFAULT '{}',
             active_index INTEGER NOT NULL DEFAULT 0,
             display_mode TEXT NOT NULL DEFAULT 'single',
             elapsed_seconds INTEGER NOT NULL DEFAULT 0,
             started_at TEXT NOT NULL,
             updated_at TEXT NOT NULL,
             completed_at TEXT NOT NULL DEFAULT '',
             FOREIGN KEY(article_id) REFERENCES articles(id),
             FOREIGN KEY(practice_session_id) REFERENCES practice_sessions(id)
           );
           CREATE INDEX IF NOT EXISTS idx_practice_runs_active
           ON practice_runs(learner_key, status, updated_at DESC);"""
    )


def _article_visibility(conn: sqlite3.Connection) -> None:
    _ensure_column(conn, "articles", "visibility", "TEXT NOT NULL DEFAULT 'public'")
    private_conditions = ["source IN ('manual', 'browser', 'private EPUB')"]
    if "source_url" in _columns(conn, "articles"):
        private_conditions.append("source_url LIKE 'private-epub://%'")
    conn.execute(f"UPDATE articles SET visibility = 'private' WHERE {' OR '.join(private_conditions)}")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_articles_visibility ON articles(visibility)"
    )


def _open_lexical_layers(conn: sqlite3.Connection) -> None:
    ensure_lexical_data_schema(conn)


def _lexical_query_history(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS lexical_queries (
             normalized TEXT PRIMARY KEY,
             query TEXT NOT NULL,
             query_kind TEXT NOT NULL,
             lookup_count INTEGER NOT NULL DEFAULT 1,
             first_searched_at TEXT NOT NULL,
             last_searched_at TEXT NOT NULL
           );
           CREATE INDEX IF NOT EXISTS idx_lexical_queries_recent
           ON lexical_queries(last_searched_at DESC);
           CREATE INDEX IF NOT EXISTS idx_lexical_queries_frequent
           ON lexical_queries(lookup_count DESC, last_searched_at DESC);"""
    )


def _review_schedule(conn: sqlite3.Connection) -> None:
    backfill_review_items(conn, _utc_now())


def _fsrs_review_state(conn: sqlite3.Connection) -> None:
    _ensure_column(conn, "review_items", "fsrs_state_json", "TEXT NOT NULL DEFAULT ''")


def _complete_word_review(conn: sqlite3.Connection) -> None:
    _ensure_column(conn, "cards", "source_quiz_id", "INTEGER")
    conn.executescript(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_cards_source_quiz
           ON cards(source_quiz_id) WHERE source_quiz_id IS NOT NULL;
           CREATE TABLE IF NOT EXISTS complete_word_review_attempts (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             quiz_id INTEGER NOT NULL,
             user_answer TEXT NOT NULL,
             correct INTEGER NOT NULL,
             error_type TEXT NOT NULL DEFAULT '',
             elapsed_seconds INTEGER NOT NULL DEFAULT 0,
             created_at TEXT NOT NULL,
             FOREIGN KEY(quiz_id) REFERENCES quizzes(id)
           );
           CREATE INDEX IF NOT EXISTS idx_complete_word_review_quiz
           ON complete_word_review_attempts(quiz_id, created_at DESC, id DESC);"""
    )


def _article_paragraph_translations(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS article_paragraph_translations (
             article_id INTEGER NOT NULL,
             paragraph_index INTEGER NOT NULL,
             source_hash TEXT NOT NULL,
             source_text TEXT NOT NULL,
             translation_zh TEXT NOT NULL,
             provider TEXT NOT NULL DEFAULT 'manual',
             updated_at TEXT NOT NULL,
             PRIMARY KEY(article_id, paragraph_index),
             FOREIGN KEY(article_id) REFERENCES articles(id)
           );
           CREATE INDEX IF NOT EXISTS idx_article_paragraph_translations_hash
           ON article_paragraph_translations(article_id, source_hash);"""
    )
    if not {"id", "body", "translation_zh", "updated_at"}.issubset(_columns(conn, "articles")):
        return
    rows = conn.execute("SELECT id, body, translation_zh, updated_at FROM articles WHERE translation_zh != ''").fetchall()
    for row in rows:
        originals = [value.strip() for value in re.split(r"\n\s*\n", row[1] or "") if value.strip()]
        translations = [value.strip() for value in re.split(r"\n\s*\n", row[2] or "") if value.strip()]
        if not originals or len(originals) != len(translations):
            continue
        conn.executemany(
            """INSERT OR IGNORE INTO article_paragraph_translations
               (article_id, paragraph_index, source_hash, source_text, translation_zh, provider, updated_at)
               VALUES (?, ?, ?, ?, ?, 'legacy', ?)""",
            [
                (row[0], index, hashlib.sha256(source.encode("utf-8")).hexdigest(), source, translated, row[3])
                for index, (source, translated) in enumerate(zip(originals, translations))
            ],
        )


SCRIPT_NOISE_PATTERN = re.compile(
    r"(?i)(?:\bGF_AJAX_POSTBACK\b|\bgform_confirmation_loaded\b|\bgform_pre_post_render\b|"
    r"\bgformRedirect\b|\bgform_wrapper_\d+\b|\bconfirmation_content\b|window\[['\"]gf_|jQuery\(['\"]#gform)"
)


def _sanitize_feed_articles(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS article_content_repairs (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             article_id INTEGER NOT NULL UNIQUE,
             original_body TEXT NOT NULL,
             original_translation_zh TEXT NOT NULL DEFAULT '',
             reason TEXT NOT NULL,
             repaired_at TEXT NOT NULL,
             FOREIGN KEY(article_id) REFERENCES articles(id)
           );"""
    )
    if "body" not in _columns(conn, "articles"):
        return
    columns = _columns(conn, "articles")
    translation_column = "translation_zh" if "translation_zh" in columns else None
    rows = conn.execute(
        f"SELECT id, body{', translation_zh' if translation_column else ''} FROM articles WHERE body != ''"
    ).fetchall()
    for row in rows:
        body = row[1] or ""
        marker = SCRIPT_NOISE_PATTERN.search(body)
        if not marker:
            continue
        cleaned = body[:marker.start()].rstrip(" \t\r\n,;:{[(")
        if len(re.findall(r"[A-Za-z][A-Za-z'-]*", cleaned)) < 30:
            continue
        original_translation = row[2] or "" if translation_column else ""
        conn.execute(
            """INSERT OR IGNORE INTO article_content_repairs
               (article_id, original_body, original_translation_zh, reason, repaired_at)
               VALUES (?, ?, ?, 'embedded-script-noise', ?)""",
            (row[0], body, original_translation, _utc_now()),
        )
        assignments = ["body = ?"]
        params: list[object] = [cleaned]
        if translation_column:
            assignments.append("translation_zh = ''")
        if "content_hash" in columns:
            assignments.append("content_hash = ?")
            params.append(hashlib.sha256(cleaned.casefold().encode("utf-8")).hexdigest())
        if "updated_at" in columns:
            assignments.append("updated_at = ?")
            params.append(_utc_now())
        params.append(row[0])
        conn.execute(f"UPDATE articles SET {', '.join(assignments)} WHERE id = ?", params)


PHOTO_CREDIT_PATTERN = re.compile(
    r"(?is)^\s*(.{20,1600}?(?:AP\s+Photo|Getty\s+Images?|Reuters|AFP|via\s+Wikimedia\s+Commons))\s+(?=[A-Z][A-Za-z])"
)
PHOTO_CREDIT_BLOCK_PATTERN = re.compile(
    r"(?is)^\s*(.{20,1600}?(?:AP\s+Photo|Getty\s+Images?|Reuters|AFP|via\s+Wikimedia\s+Commons))(?:\s+(.+))?$"
)
DISCLOSURE_PATTERN = re.compile(
    r"(?is)\n\s*\n([A-Z][A-Za-zÀ-ÖØ-öø-ÿ'’ .-]{2,100})\s+does not work for, consult, own shares in or receive funding from\b.*$"
)


def _repair_abbreviation_paragraphs(text: str) -> str:
    text = re.sub(r"\bU\.\s+S\.(?=\s|$)", "U.S.", text)
    text = re.sub(r"\b([A-Z])\.\s*\n\s*\n\s*([A-Z])\.\s*", r"\1.\2. ", text)
    text = re.sub(r"\b(Sen|Rep|Dr|Mr|Mrs|Ms|Prof)\.\s*\n\s*\n\s*", r"\1. ", text)
    text = re.sub(r"\b([A-Z])\.\s*\n\s*\n\s*([A-Z][a-z])", r"\1. \2", text)
    return text.strip()


def _article_semantic_blocks(conn: sqlite3.Connection) -> None:
    for column, definition in {
        "author": "TEXT NOT NULL DEFAULT ''",
        "image_caption": "TEXT NOT NULL DEFAULT ''",
        "disclosure": "TEXT NOT NULL DEFAULT ''",
        "extraction_version": "TEXT NOT NULL DEFAULT ''",
        "extraction_confidence": "REAL NOT NULL DEFAULT 0",
        "extraction_notes_json": "TEXT NOT NULL DEFAULT '{}'",
    }.items():
        _ensure_column(conn, "articles", column, definition)
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS article_extraction_audits (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             article_id INTEGER NOT NULL,
             extraction_version TEXT NOT NULL,
             original_body TEXT NOT NULL,
             extracted_body TEXT NOT NULL,
             metadata_json TEXT NOT NULL DEFAULT '{}',
             created_at TEXT NOT NULL,
             UNIQUE(article_id, extraction_version),
             FOREIGN KEY(article_id) REFERENCES articles(id)
           );
           CREATE TABLE IF NOT EXISTS article_extraction_feedback (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             article_id INTEGER NOT NULL,
             verdict TEXT NOT NULL,
             note TEXT NOT NULL DEFAULT '',
             extraction_version TEXT NOT NULL DEFAULT '',
             created_at TEXT NOT NULL,
             FOREIGN KEY(article_id) REFERENCES articles(id)
           );
           CREATE INDEX IF NOT EXISTS idx_article_extraction_feedback_article
           ON article_extraction_feedback(article_id, created_at DESC);"""
    )
    if "body" not in _columns(conn, "articles"):
        return
    rows = conn.execute(
        """SELECT id, body, author, image_caption, disclosure
           FROM articles WHERE source IN ('The Conversation', 'The Conversation Politics') AND body != ''"""
    ).fetchall()
    version = "conversation-rules-v1"
    for row in rows:
        original = row[1] or ""
        body = original
        author = row[2] or ""
        caption = row[3] or ""
        disclosure = row[4] or ""
        removed = []

        caption_match = PHOTO_CREDIT_PATTERN.match(body)
        if caption_match and not caption:
            caption = re.sub(r"\s+", " ", _repair_abbreviation_paragraphs(caption_match.group(1))).strip()
            body = body[caption_match.end():].lstrip()
            removed.append("image_caption")

        disclosure_match = DISCLOSURE_PATTERN.search(body)
        if disclosure_match:
            author = author or re.sub(r"\s+", " ", disclosure_match.group(1)).strip()
            disclosure = disclosure or re.sub(r"\s+", " ", _repair_abbreviation_paragraphs(disclosure_match.group(0))).strip()
            body = body[:disclosure_match.start()].rstrip()
            removed.append("disclosure")

        body = _repair_abbreviation_paragraphs(body)
        if body == original and not any((author, caption, disclosure)):
            continue
        metadata = {"author": author, "image_caption": caption, "disclosure": disclosure, "removed_blocks": removed}
        conn.execute(
            """INSERT OR IGNORE INTO article_extraction_audits
               (article_id, extraction_version, original_body, extracted_body, metadata_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (row[0], version, original, body, json.dumps(metadata, ensure_ascii=False), _utc_now()),
        )
        conn.execute(
            """UPDATE articles SET body = ?, author = ?, image_caption = ?, disclosure = ?,
               extraction_version = ?, extraction_confidence = ?, extraction_notes_json = ?,
               translation_zh = '', content_hash = ?, updated_at = ? WHERE id = ?""",
            (
                body, author, caption, disclosure, version,
                0.98 if caption and disclosure else 0.85 if caption or disclosure else 0.70,
                json.dumps({"removed_blocks": removed, "review_status": "rule-reviewed"}, ensure_ascii=False),
                hashlib.sha256(body.casefold().encode("utf-8")).hexdigest(), _utc_now(), row[0],
            ),
        )


def _embedded_article_captions(conn: sqlite3.Connection) -> None:
    if not {"body", "source", "image_caption"}.issubset(_columns(conn, "articles")):
        return
    rows = conn.execute(
        """SELECT id, body, image_caption FROM articles
           WHERE source IN ('The Conversation', 'The Conversation Politics') AND body != ''"""
    ).fetchall()
    version = "conversation-rules-v2"
    for row in rows:
        original = row[1] or ""
        kept = []
        captions = []
        for paragraph in re.split(r"\n\s*\n", original):
            match = PHOTO_CREDIT_BLOCK_PATTERN.match(paragraph.strip())
            if not match:
                kept.append(paragraph.strip())
                continue
            captions.append(re.sub(r"\s+", " ", _repair_abbreviation_paragraphs(match.group(1))).strip())
            if match.group(2):
                kept.append(match.group(2).strip())
        if not captions:
            continue
        body = "\n\n".join(value for value in kept if value).strip()
        prior_caption = (row[2] or "").strip()
        all_captions = [prior_caption, *captions] if prior_caption else captions
        image_caption = "\n\n".join(dict.fromkeys(value for value in all_captions if value))
        metadata = {"image_captions": captions, "removed_blocks": ["embedded_image_caption"]}
        conn.execute(
            """INSERT OR IGNORE INTO article_extraction_audits
               (article_id, extraction_version, original_body, extracted_body, metadata_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (row[0], version, original, body, json.dumps(metadata, ensure_ascii=False), _utc_now()),
        )
        conn.execute(
            """UPDATE articles SET body = ?, image_caption = ?, extraction_version = ?,
               extraction_confidence = 0.98, extraction_notes_json = ?, translation_zh = '',
               content_hash = ?, updated_at = ? WHERE id = ?""",
            (
                body, image_caption, version,
                json.dumps({"removed_blocks": ["embedded_image_caption"], "review_status": "rule-reviewed"}, ensure_ascii=False),
                hashlib.sha256(body.casefold().encode("utf-8")).hexdigest(), _utc_now(), row[0],
            ),
        )


def _source_adapter_backfill(conn: sqlite3.Connection) -> None:
    required = {"body", "source", "author", "image_caption", "disclosure", "extraction_version"}
    if not required.issubset(_columns(conn, "articles")):
        return
    sources = (
        "BBC World", "BBC Business", "Guardian World", "Guardian Opinion",
        "Guardian Science", "Guardian Environment", "JSTOR Daily",
    )
    placeholders = ",".join("?" for _ in sources)
    rows = conn.execute(
        f"""SELECT id, body, source, author, image_caption, disclosure, translation_zh
            FROM articles WHERE source IN ({placeholders}) AND body != ''""",
        sources,
    ).fetchall()
    for row in rows:
        original = row[1] or ""
        result = extract_source_content(original, row[2], row[3] or "")
        body = result["body"]
        body_changed = body != original
        metadata = {
            "adapter": result["adapter"],
            "removed_blocks": result["removed_blocks"],
            "review_status": "rule-reviewed" if body_changed else "adapter-registered",
        }
        if body_changed:
            conn.execute(
                """INSERT OR IGNORE INTO article_extraction_audits
                   (article_id, extraction_version, original_body, extracted_body, metadata_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    row[0], result["extraction_version"], original, body,
                    json.dumps(metadata, ensure_ascii=False), _utc_now(),
                ),
            )
        conn.execute(
            """UPDATE articles SET body = ?, author = ?, image_caption = ?, disclosure = ?,
               extraction_version = ?, extraction_confidence = ?, extraction_notes_json = ?,
               translation_zh = CASE WHEN ? THEN '' ELSE translation_zh END,
               content_hash = CASE WHEN ? THEN ? ELSE content_hash END,
               updated_at = CASE WHEN ? THEN ? ELSE updated_at END WHERE id = ?""",
            (
                body, result["author"], row[4] or result["image_caption"], row[5] or result["disclosure"],
                result["extraction_version"], result["extraction_confidence"],
                json.dumps(metadata, ensure_ascii=False), int(body_changed), int(body_changed),
                hashlib.sha256(body.casefold().encode("utf-8")).hexdigest(), int(body_changed), _utc_now(), row[0],
            ),
        )


def _article_extraction_block_labels(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS article_extraction_block_labels (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             article_id INTEGER NOT NULL,
             block_hash TEXT NOT NULL,
             block_index INTEGER NOT NULL,
             block_text TEXT NOT NULL,
             suggested_label TEXT NOT NULL,
             label TEXT NOT NULL,
             source TEXT NOT NULL DEFAULT '',
             extraction_version TEXT NOT NULL DEFAULT '',
             created_at TEXT NOT NULL,
             updated_at TEXT NOT NULL,
             UNIQUE(article_id, block_hash),
             FOREIGN KEY(article_id) REFERENCES articles(id)
           );
           CREATE INDEX IF NOT EXISTS idx_article_block_labels_source
           ON article_extraction_block_labels(source, label, updated_at DESC);
           CREATE INDEX IF NOT EXISTS idx_article_block_labels_article
           ON article_extraction_block_labels(article_id, block_index);"""
    )


def _article_extraction_review_batches(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS article_extraction_review_batches (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             name TEXT NOT NULL,
             target_size INTEGER NOT NULL DEFAULT 20,
             status TEXT NOT NULL DEFAULT 'active',
             created_at TEXT NOT NULL,
             completed_at TEXT NOT NULL DEFAULT ''
           );
           CREATE TABLE IF NOT EXISTS article_extraction_review_items (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             batch_id INTEGER NOT NULL,
             article_id INTEGER NOT NULL,
             position INTEGER NOT NULL,
             source TEXT NOT NULL,
             adapter TEXT NOT NULL,
             extraction_version TEXT NOT NULL DEFAULT '',
             total_blocks INTEGER NOT NULL DEFAULT 0,
             status TEXT NOT NULL DEFAULT 'pending',
             started_at TEXT NOT NULL DEFAULT '',
             last_activity_at TEXT NOT NULL DEFAULT '',
             completed_at TEXT NOT NULL DEFAULT '',
             active_seconds INTEGER NOT NULL DEFAULT 0,
             UNIQUE(batch_id, article_id),
             UNIQUE(batch_id, position),
             FOREIGN KEY(batch_id) REFERENCES article_extraction_review_batches(id),
             FOREIGN KEY(article_id) REFERENCES articles(id)
           );
           CREATE INDEX IF NOT EXISTS idx_extraction_review_items_batch
           ON article_extraction_review_items(batch_id, position);
           CREATE INDEX IF NOT EXISTS idx_extraction_review_items_article
           ON article_extraction_review_items(article_id, status);"""
    )


def _contextual_output_training(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS output_task_sets (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             article_id INTEGER NOT NULL,
             source_hash TEXT NOT NULL,
             generation_version TEXT NOT NULL,
             status TEXT NOT NULL DEFAULT 'active',
             created_at TEXT NOT NULL,
             FOREIGN KEY(article_id) REFERENCES articles(id)
           );
           CREATE INDEX IF NOT EXISTS idx_output_task_sets_article
           ON output_task_sets(article_id, status, id DESC);
           CREATE TABLE IF NOT EXISTS output_tasks (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             set_id INTEGER NOT NULL,
             article_id INTEGER NOT NULL,
             position INTEGER NOT NULL,
             task_type TEXT NOT NULL,
             prompt_text TEXT NOT NULL,
             source_text TEXT NOT NULL,
             reference_text TEXT NOT NULL DEFAULT '',
             target_chunks_json TEXT NOT NULL DEFAULT '[]',
             guidance_json TEXT NOT NULL DEFAULT '{}',
             generation_source TEXT NOT NULL,
             created_at TEXT NOT NULL,
             UNIQUE(set_id, position),
             FOREIGN KEY(set_id) REFERENCES output_task_sets(id),
             FOREIGN KEY(article_id) REFERENCES articles(id)
           );
           CREATE INDEX IF NOT EXISTS idx_output_tasks_article
           ON output_tasks(article_id, task_type, id DESC);
           CREATE TABLE IF NOT EXISTS output_attempts (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             task_id INTEGER NOT NULL,
             response_text TEXT NOT NULL,
             elapsed_seconds INTEGER NOT NULL DEFAULT 0,
             hint_used INTEGER NOT NULL DEFAULT 0,
             confidence INTEGER,
             sentence_count INTEGER NOT NULL DEFAULT 1,
             deterministic_feedback_json TEXT NOT NULL DEFAULT '{}',
             self_review_json TEXT NOT NULL DEFAULT '{}',
             created_at TEXT NOT NULL,
             updated_at TEXT NOT NULL,
             FOREIGN KEY(task_id) REFERENCES output_tasks(id)
           );
           CREATE INDEX IF NOT EXISTS idx_output_attempts_task
           ON output_attempts(task_id, created_at DESC);
           CREATE TABLE IF NOT EXISTS output_review_links (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             attempt_id INTEGER NOT NULL,
             card_id INTEGER NOT NULL,
             link_type TEXT NOT NULL DEFAULT 'reference',
             created_at TEXT NOT NULL,
             UNIQUE(attempt_id, card_id, link_type),
             FOREIGN KEY(attempt_id) REFERENCES output_attempts(id),
             FOREIGN KEY(card_id) REFERENCES cards(id)
           );
           CREATE TABLE IF NOT EXISTS daily_learning_metrics (
             day TEXT NOT NULL,
             metric TEXT NOT NULL,
             value INTEGER NOT NULL DEFAULT 0,
             updated_at TEXT NOT NULL,
             PRIMARY KEY(day, metric)
           );
           CREATE TABLE IF NOT EXISTS article_reading_events (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             day TEXT NOT NULL,
             article_id INTEGER NOT NULL,
             word_count INTEGER NOT NULL DEFAULT 0,
             created_at TEXT NOT NULL,
             UNIQUE(day, article_id),
             FOREIGN KEY(article_id) REFERENCES articles(id)
           );"""
    )


def _semantic_output_feedback(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS output_semantic_feedback (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             attempt_id INTEGER NOT NULL,
             provider TEXT NOT NULL,
             model TEXT NOT NULL,
             prompt_version TEXT NOT NULL,
             status TEXT NOT NULL DEFAULT 'complete',
             feedback_json TEXT NOT NULL DEFAULT '{}',
             created_at TEXT NOT NULL,
             FOREIGN KEY(attempt_id) REFERENCES output_attempts(id)
           );
           CREATE INDEX IF NOT EXISTS idx_output_semantic_feedback_attempt
           ON output_semantic_feedback(attempt_id, id DESC);
           CREATE TABLE IF NOT EXISTS output_feedback_decisions (
             feedback_id INTEGER PRIMARY KEY,
             decision TEXT NOT NULL,
             revised_response TEXT NOT NULL DEFAULT '',
             created_at TEXT NOT NULL,
             updated_at TEXT NOT NULL,
             FOREIGN KEY(feedback_id) REFERENCES output_semantic_feedback(id)
           );
           CREATE TABLE IF NOT EXISTS usage_contrast_attempts (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             contrast_slug TEXT NOT NULL,
             selected_index INTEGER NOT NULL,
             correct INTEGER NOT NULL,
             created_at TEXT NOT NULL
           );
           CREATE INDEX IF NOT EXISTS idx_usage_contrast_attempts_slug
           ON usage_contrast_attempts(contrast_slug, created_at DESC);"""
    )


def _speaking_output_training(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS speaking_task_sets (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             article_id INTEGER NOT NULL,
             source_hash TEXT NOT NULL,
             duration_target INTEGER NOT NULL DEFAULT 60,
             prep_seconds INTEGER NOT NULL DEFAULT 15,
             status TEXT NOT NULL DEFAULT 'active',
             created_at TEXT NOT NULL,
             FOREIGN KEY(article_id) REFERENCES articles(id)
           );
           CREATE INDEX IF NOT EXISTS idx_speaking_task_sets_article
           ON speaking_task_sets(article_id, duration_target, status, id DESC);
           CREATE TABLE IF NOT EXISTS speaking_tasks (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             set_id INTEGER NOT NULL,
             article_id INTEGER NOT NULL,
             position INTEGER NOT NULL,
             task_type TEXT NOT NULL,
             prompt_text TEXT NOT NULL,
             source_text TEXT NOT NULL,
             target_chunks_json TEXT NOT NULL DEFAULT '[]',
             evidence_eligible INTEGER NOT NULL DEFAULT 0,
             created_at TEXT NOT NULL,
             UNIQUE(set_id, position),
             FOREIGN KEY(set_id) REFERENCES speaking_task_sets(id),
             FOREIGN KEY(article_id) REFERENCES articles(id)
           );
           CREATE TABLE IF NOT EXISTS speaking_attempts (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             task_id INTEGER NOT NULL,
             audio_filename TEXT NOT NULL DEFAULT '',
             audio_mime TEXT NOT NULL DEFAULT '',
             audio_bytes INTEGER NOT NULL DEFAULT 0,
             duration_seconds INTEGER NOT NULL DEFAULT 0,
             prep_seconds INTEGER NOT NULL DEFAULT 0,
             transcript_text TEXT NOT NULL DEFAULT '',
             transcript_source TEXT NOT NULL DEFAULT '',
             transcript_provider TEXT NOT NULL DEFAULT '',
             transcript_model TEXT NOT NULL DEFAULT '',
             transcript_analysis_json TEXT NOT NULL DEFAULT '{}',
             self_review_json TEXT NOT NULL DEFAULT '{}',
             status TEXT NOT NULL DEFAULT 'draft',
             repeat_of_id INTEGER,
             created_at TEXT NOT NULL,
             updated_at TEXT NOT NULL,
             deleted_at TEXT NOT NULL DEFAULT '',
             FOREIGN KEY(task_id) REFERENCES speaking_tasks(id),
             FOREIGN KEY(repeat_of_id) REFERENCES speaking_attempts(id)
           );
           CREATE INDEX IF NOT EXISTS idx_speaking_attempts_task
           ON speaking_attempts(task_id, created_at DESC);
           CREATE TABLE IF NOT EXISTS speaking_review_links (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             attempt_id INTEGER NOT NULL,
             card_id INTEGER NOT NULL,
             created_at TEXT NOT NULL,
             UNIQUE(attempt_id, card_id),
             FOREIGN KEY(attempt_id) REFERENCES speaking_attempts(id),
             FOREIGN KEY(card_id) REFERENCES cards(id)
           );"""
    )


MIGRATIONS: tuple[Migration, ...] = (
    (1, "consolidate legacy schema", _legacy_schema),
    (2, "add training loop metrics", _training_loop_metrics),
    (3, "add server-side practice run state", _practice_run_state),
    (4, "classify public and private article material", _article_visibility),
    (5, "add layered open lexical data", _open_lexical_layers),
    (6, "add private lexical query history", _lexical_query_history),
    (7, "add unified review scheduling", _review_schedule),
    (8, "remove embedded script noise from feed articles", _sanitize_feed_articles),
    (9, "separate article body from source metadata", _article_semantic_blocks),
    (10, "remove embedded image captions from article body", _embedded_article_captions),
    (11, "apply registered source extraction adapters", _source_adapter_backfill),
    (12, "add human article block labels", _article_extraction_block_labels),
    (13, "add representative extraction review batches", _article_extraction_review_batches),
    (14, "add contextual output training", _contextual_output_training),
    (15, "add semantic output feedback", _semantic_output_feedback),
    (16, "add local speaking output", _speaking_output_training),
    (17, "add optional FSRS review state", _fsrs_review_state),
    (18, "add Complete the Words card review", _complete_word_review),
    (19, "persist paragraph-aligned article translations", _article_paragraph_translations),
)


def run_migrations(conn: sqlite3.Connection) -> int:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
             version INTEGER PRIMARY KEY,
             name TEXT NOT NULL,
             applied_at TEXT NOT NULL
           )"""
    )
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    for version, name, migrate in MIGRATIONS:
        if version in applied:
            continue
        migrate(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
            (version, name, _utc_now()),
        )
    row = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
    return int(row[0])
