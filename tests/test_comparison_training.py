import tempfile
import unittest
from pathlib import Path

from backend import server
from backend.comparison_training import (
    comparison_training_catalog,
    comparison_training_queue,
    submit_comparison_training_answer,
)
from backend.review_scheduler import review_queue


class ComparisonTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        server.DB_PATH = Path(cls.temp_dir.name) / "comparison-training.sqlite"
        server.init_db()

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def setUp(self):
        with server.db() as conn:
            conn.execute("DELETE FROM review_logs")
            conn.execute("DELETE FROM review_items")
            conn.execute("DELETE FROM comparison_training_attempts")
            conn.execute("DELETE FROM cards")

    def test_catalog_derives_choice_and_safe_correction_tasks_from_reviewed_content(self):
        tasks = comparison_training_catalog()
        choices = [task for task in tasks if task["task_type"] == "choice"]
        corrections = [task for task in tasks if task["task_type"] == "correction"]
        self.assertEqual(len(tasks), 393)
        self.assertEqual(len(choices), 236)
        self.assertEqual(len(corrections), 157)
        self.assertEqual(len({task["task_id"] for task in tasks}), len(tasks))
        self.assertTrue(all(task["answer"] in task["options"] for task in tasks))
        self.assertTrue(all(task["corrected_text"] for task in corrections))

    def test_wrong_answer_creates_one_due_boundary_card_and_persists_behavior(self):
        task = next(task for task in comparison_training_catalog() if task["task_type"] == "choice")
        wrong = next(option for option in task["options"] if option != task["answer"])
        with server.db() as conn:
            first = submit_comparison_training_answer(
                conn, task["task_id"], wrong, elapsed_seconds=18, answer_changes=2, hint_used=True,
            )
            second = submit_comparison_training_answer(conn, task["task_id"], wrong)
            cards = conn.execute("SELECT * FROM cards WHERE kind = 'comparison-boundary'").fetchall()
            attempts = conn.execute(
                "SELECT * FROM comparison_training_attempts WHERE task_id = ? ORDER BY id", (task["task_id"],)
            ).fetchall()
            queue = review_queue(conn, kind="comparison")
        self.assertFalse(first["correct"])
        self.assertTrue(first["review"]["created"])
        self.assertFalse(second["review"]["created"])
        self.assertEqual(first["review"]["card_id"], second["review"]["card_id"])
        self.assertEqual(len(cards), 1)
        self.assertEqual(len(attempts), 2)
        self.assertEqual((attempts[0]["elapsed_seconds"], attempts[0]["answer_changes"], attempts[0]["hint_used"]), (18, 2, 1))
        self.assertEqual(queue["summary"]["due"], 1)
        self.assertEqual(queue["items"][0]["kind"], "comparison-boundary")

    def test_correct_answer_records_progress_without_creating_review_card(self):
        task = next(task for task in comparison_training_catalog() if task["task_type"] == "choice")
        with server.db() as conn:
            result = submit_comparison_training_answer(conn, task["task_id"], task["answer"])
            queue = comparison_training_queue(conn, task_type="choice")
            card_count = conn.execute("SELECT COUNT(*) FROM cards WHERE kind = 'comparison-boundary'").fetchone()[0]
        self.assertTrue(result["correct"])
        self.assertFalse(result["review"]["due"])
        self.assertEqual(card_count, 0)
        self.assertEqual(queue["summary"]["attempted"], 1)
        self.assertEqual(queue["summary"]["correct"], 1)
        self.assertTrue(all("answer" not in item and "avoid" not in item for item in queue["items"]))

    def test_queue_prioritizes_latest_wrong_and_validates_filters(self):
        tasks = [task for task in comparison_training_catalog() if task["task_type"] == "choice" and task["topic"] == "charts"]
        with server.db() as conn:
            submit_comparison_training_answer(conn, tasks[0]["task_id"], tasks[0]["answer"])
            wrong = next(option for option in tasks[1]["options"] if option != tasks[1]["answer"])
            submit_comparison_training_answer(conn, tasks[1]["task_id"], wrong)
            queue = comparison_training_queue(conn, topic="charts", task_type="choice")
            with self.assertRaisesRegex(ValueError, "topic"):
                comparison_training_queue(conn, topic="unknown")
        self.assertEqual(queue["items"][0]["task_id"], tasks[1]["task_id"])
        self.assertEqual(queue["summary"]["wrong"], 1)


if __name__ == "__main__":
    unittest.main()
