from __future__ import annotations

import re
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


_BACKUP_LOCK = threading.Lock()
_SAFE_NAME = re.compile(r"^language-coach-[0-9TZ-]+-[A-Za-z0-9._-]+\.sqlite3$")


def _integrity_check(path: Path) -> None:
    with closing(sqlite3.connect(path)) as conn:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise ValueError(f"Backup integrity check failed: {result}")


def list_backups(backup_dir: Path) -> list[dict]:
    if not backup_dir.exists():
        return []
    items = []
    for path in sorted(backup_dir.glob("language-coach-*.sqlite3"), reverse=True):
        stat = path.stat()
        items.append({
            "filename": path.name,
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
        })
    return items


def create_backup(db_path: Path, backup_dir: Path, app_version: str) -> dict:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    safe_version = re.sub(r"[^A-Za-z0-9._-]", "-", app_version)
    target = backup_dir / f"language-coach-{stamp}-{safe_version}.sqlite3"
    with _BACKUP_LOCK:
        with closing(sqlite3.connect(db_path)) as source, closing(sqlite3.connect(target)) as destination:
            source.backup(destination)
    _integrity_check(target)
    return next(item for item in list_backups(backup_dir) if item["filename"] == target.name)


def restore_backup(db_path: Path, backup_dir: Path, filename: str, app_version: str) -> dict:
    if not _SAFE_NAME.fullmatch(filename):
        raise ValueError("Invalid backup filename")
    source_path = (backup_dir / filename).resolve()
    if source_path.parent != backup_dir.resolve() or not source_path.is_file():
        raise ValueError("Backup not found")
    _integrity_check(source_path)
    safety_backup = create_backup(db_path, backup_dir, f"pre-restore-{app_version}")
    with _BACKUP_LOCK:
        with closing(sqlite3.connect(source_path)) as source, closing(sqlite3.connect(db_path)) as destination:
            source.backup(destination)
    _integrity_check(db_path)
    return {"restored": filename, "safety_backup": safety_backup}
