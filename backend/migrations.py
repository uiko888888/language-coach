from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone


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


MIGRATIONS: tuple[Migration, ...] = (
    (1, "consolidate legacy schema", _legacy_schema),
    (2, "add training loop metrics", _training_loop_metrics),
    (3, "add server-side practice run state", _practice_run_state),
    (4, "classify public and private article material", _article_visibility),
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
