from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

try:
    from fsrs import Card, Rating, Scheduler, State
except ImportError:  # Optional dependency; the legacy scheduler remains usable.
    Card = Rating = Scheduler = State = None


FSRS_ID = "fsrs-6.3.1"
RATING_NAMES = {"again": "Again", "hard": "Hard", "good": "Good", "easy": "Easy"}


def available() -> bool:
    return all(value is not None for value in (Card, Rating, Scheduler, State))


def enabled() -> bool:
    return available() and os.getenv("LANGUAGE_COACH_FSRS", "0").strip().lower() in {"1", "true", "yes", "on"}


def desired_retention() -> float:
    try:
        value = float(os.getenv("FSRS_DESIRED_RETENTION", "0.9"))
    except ValueError:
        value = 0.9
    return max(0.7, min(0.99, value))


def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    return current if current.tzinfo else current.replace(tzinfo=timezone.utc)


def _enum_state(name: str):
    if name == "review":
        return State.Review
    if name == "relearning":
        return getattr(State, "Relearning", State.Learning)
    return State.Learning


def _new_card(item: dict[str, Any], reviewed_at: datetime):
    raw = item.get("fsrs_state_json") or ""
    if raw:
        try:
            saved = json.loads(raw)
            card = Card(
                card_id=item.get("item_id"),
                state=_enum_state(str(saved.get("state") or item.get("state") or "learning")),
                step=saved.get("step"),
                stability=saved.get("stability"),
                difficulty=saved.get("difficulty"),
                due=datetime.fromisoformat(saved["due"]) if saved.get("due") else reviewed_at,
                last_review=datetime.fromisoformat(saved["last_review"]) if saved.get("last_review") else None,
            )
            return card
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            pass
    return Card(card_id=item.get("item_id"), state=_enum_state(str(item.get("state") or "learning")), due=reviewed_at)


def _card_json(card) -> str:
    return json.dumps(
        {
            "state": card.state.name.lower(),
            "step": card.step,
            "stability": card.stability,
            "difficulty": card.difficulty,
            "due": card.due.isoformat() if card.due else "",
            "last_review": card.last_review.isoformat() if card.last_review else "",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def schedule_review(item: dict[str, Any], rating: str, reviewed_at: datetime) -> dict[str, Any]:
    if not available():
        raise RuntimeError("FSRS dependency is not installed")
    if rating not in RATING_NAMES:
        raise ValueError("rating must be again, hard, good, or easy")
    when = _utc(reviewed_at)
    scheduler = Scheduler(desired_retention=desired_retention(), enable_fuzzing=False)
    card = _new_card(item, when)
    next_card, log = scheduler.review_card(card, getattr(Rating, RATING_NAMES[rating]), when)
    previous_state = str(item.get("state") or "new")
    next_state = next_card.state.name.lower()
    if next_state == "new":
        next_state = "learning"
    previous_lapses = max(0, int(item.get("lapses") or 0))
    lapses = previous_lapses + int(rating == "again" and previous_state in {"review", "relearning"})
    previous_repetitions = max(0, int(item.get("repetitions") or 0))
    repetitions = previous_repetitions + int(rating != "again")
    scheduled_days = float(getattr(log, "scheduled_days", 0) or 0)
    difficulty = float(next_card.difficulty or 5.0)
    ease = max(1.3, min(3.2, round(3.2 - ((difficulty - 1.0) / 9.0) * 1.9, 2)))
    return {
        "state": next_state,
        "due_at": next_card.due.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "interval_days": scheduled_days,
        "ease_factor": ease,
        "repetitions": repetitions,
        "lapses": lapses,
        "last_review_at": when.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "scheduler": FSRS_ID,
        "updated_at": when.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "fsrs_state_json": _card_json(next_card),
    }
