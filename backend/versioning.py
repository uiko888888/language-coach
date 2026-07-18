from __future__ import annotations

from pathlib import Path


API_VERSION = "1"
SCHEMA_VERSION = 13


def app_version(root: Path) -> str:
    version_file = root / "VERSION"
    return version_file.read_text(encoding="utf-8").strip() if version_file.exists() else "development"


def version_payload(root: Path) -> dict:
    return {
        "app_version": app_version(root),
        "api_version": API_VERSION,
        "schema_version": SCHEMA_VERSION,
    }
