import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend import server
from backend.review_scheduler import (
    ensure_review_item,
    rate_review_item,
    review_queue,
    schedule_review,
    undo_last_review,
)


class ReviewSchedulerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        server.DB_PATH = Path(cls.temp_dir.name) / "reviews.sqlite"
        server.init_db()

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def setUp(self):
        with server.db() as conn:
            conn.execute("DELETE FROM review_logs")
            conn.execute("DELETE FROM review_items")
            conn.execute("DELETE FROM cards")
            conn.execute("DELETE FROM mistakes")
            conn.execute("DELETE FROM daily_plan_progress")

    def test_four_ratings_produce_monotonic_initial_intervals(self):
        now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
        item = {
            "state": "new", "interval_days": 0, "ease_factor": 2.5,
            "repetitions": 0, "lapses": 0,
        }
        schedules = {rating: schedule_review(item, rating, now) for rating in ("again", "hard", "good", "easy")}
        due = [datetime.fromisoformat(schedules[rating]["due_at"]) for rating in ("again", "hard", "good", "easy")]
        self.assertEqual(due, sorted(due))
        self.assertEqual(schedules["again"]["state"], "learning")
        self.assertEqual(schedules["good"]["interval_days"], 3)
        self.assertEqual(schedules["easy"]["interval_days"], 7)

    def test_forgetting_review_item_enters_relearning_and_counts_lapse(self):
        now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
        item = {
            "state": "review", "interval_days": 12, "ease_factor": 2.5,
            "repetitions": 4, "lapses": 1,
        }
        scheduled = schedule_review(item, "again", now)
        self.assertEqual(scheduled["state"], "relearning")
        self.assertEqual(scheduled["lapses"], 2)
        self.assertEqual(datetime.fromisoformat(scheduled["due_at"]), now + timedelta(minutes=10))

    def test_queue_unifies_words_phrases_and_solved_mistakes(self):
        now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
        now_text = now.isoformat()
        with server.db() as conn:
            article_id = conn.execute("SELECT id FROM articles ORDER BY id LIMIT 1").fetchone()[0]
            word_id = conn.execute(
                """INSERT INTO cards (term, kind, context, status, created_at, updated_at)
                   VALUES ('inspect', 'word', 'Inspect the bridge.', 'new', ?, ?)""", (now_text, now_text),
            ).lastrowid
            phrase_id = conn.execute(
                """INSERT INTO cards (term, kind, context, status, created_at, updated_at)
                   VALUES ('inspect for damage', 'phrase', 'Inspect for damage.', 'new', ?, ?)""", (now_text, now_text),
            ).lastrowid
            quiz_id = conn.execute(
                """INSERT INTO quizzes
                   (article_id, style, mode, type, prompt, answer, created_at)
                   VALUES (?, 'IELTS', 'reading', 'reading', 'Which claim is supported?', 'Claim A', ?)""",
                (article_id, now_text),
            ).lastrowid
            mistake_id = conn.execute(
                """INSERT INTO mistakes
                   (quiz_id, prompt, answer, user_answer, evidence, solved, created_at, mastered_at)
                   VALUES (?, 'Which claim is supported?', 'Claim A', 'Claim B', 'Evidence A', 1, ?, ?)""",
                (quiz_id, now_text, now_text),
            ).lastrowid
            conn.execute(
                """INSERT INTO mistakes
                   (prompt, answer, user_answer, solved, created_at)
                   VALUES ('Unsolved', 'A', 'B', 0, ?)""", (now_text,),
            )
            ensure_review_item(conn, "card", word_id, now_text)
            ensure_review_item(conn, "card", phrase_id, now_text)
            ensure_review_item(conn, "mistake", mistake_id, now_text)
            queue = review_queue(conn, now=now)
        self.assertEqual({item["kind"] for item in queue["items"]}, {"word", "phrase", "mistake"})
        self.assertEqual(queue["summary"]["due"], 3)
        self.assertFalse(queue["scheduler"]["fsrs"])

    def test_rating_and_undo_restore_exact_schedule_snapshot(self):
        now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
        now_text = now.isoformat()
        with server.db() as conn:
            card_id = conn.execute(
                """INSERT INTO cards (term, kind, context, status, created_at, updated_at)
                   VALUES ('evidence', 'word', 'Use evidence.', 'new', ?, ?)""", (now_text, now_text),
            ).lastrowid
            review_id = ensure_review_item(conn, "card", card_id, now_text)
            before = dict(conn.execute("SELECT * FROM review_items WHERE id = ?", (review_id,)).fetchone())
            rated = rate_review_item(conn, review_id, "good", now)
            self.assertEqual(rated["interval"], "3 天")
            undo_last_review(conn, now + timedelta(seconds=30))
            restored = dict(conn.execute("SELECT * FROM review_items WHERE id = ?", (review_id,)).fetchone())
            log = conn.execute("SELECT * FROM review_logs WHERE id = ?", (rated["log_id"],)).fetchone()
        for field in ("state", "due_at", "interval_days", "ease_factor", "repetitions", "lapses", "last_review_at"):
            self.assertEqual(restored[field], before[field])
        self.assertTrue(log["reverted_at"])

    def test_invalid_rating_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "rating"):
            schedule_review({"state": "new"}, "perfect", datetime.now(timezone.utc))

    def test_future_item_cannot_be_rated_twice(self):
        now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
        now_text = now.isoformat()
        with server.db() as conn:
            card_id = conn.execute(
                """INSERT INTO cards (term, kind, context, status, created_at, updated_at)
                   VALUES ('idempotent', 'word', 'An idempotent action.', 'new', ?, ?)""", (now_text, now_text),
            ).lastrowid
            review_id = ensure_review_item(conn, "card", card_id, now_text)
            rate_review_item(conn, review_id, "good", now)
            with self.assertRaisesRegex(ValueError, "not due"):
                rate_review_item(conn, review_id, "good", now + timedelta(seconds=1))

    def test_undo_expires_after_ten_minutes(self):
        now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
        now_text = now.isoformat()
        with server.db() as conn:
            card_id = conn.execute(
                """INSERT INTO cards (term, kind, context, status, created_at, updated_at)
                   VALUES ('expiry', 'word', 'An expiry window.', 'new', ?, ?)""", (now_text, now_text),
            ).lastrowid
            review_id = ensure_review_item(conn, "card", card_id, now_text)
            rate_review_item(conn, review_id, "hard", now)
            with self.assertRaisesRegex(ValueError, "expired"):
                undo_last_review(conn, now + timedelta(minutes=11))


if __name__ == "__main__":
    unittest.main()
