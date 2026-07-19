import unittest
from datetime import datetime, timezone

from backend import fsrs_adapter


@unittest.skipUnless(fsrs_adapter.available(), "optional fsrs package is not available in this Python environment")
class FsrsAdapterTests(unittest.TestCase):
    def test_four_ratings_return_persistable_state(self):
        now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
        item = {"item_id": 1, "state": "new", "fsrs_state_json": ""}
        results = {rating: fsrs_adapter.schedule_review(item, rating, now) for rating in fsrs_adapter.RATING_NAMES}
        self.assertEqual(set(results), {"again", "hard", "good", "easy"})
        for result in results.values():
            self.assertEqual(result["scheduler"], fsrs_adapter.FSRS_ID)
            self.assertTrue(result["fsrs_state_json"])
            self.assertGreaterEqual(result["interval_days"], 0)

    def test_review_state_can_be_replayed(self):
        now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
        item = {"item_id": 1, "state": "new", "fsrs_state_json": ""}
        first = fsrs_adapter.schedule_review(item, "good", now)
        second = fsrs_adapter.schedule_review(first, "good", now.replace(hour=13))
        self.assertEqual(second["scheduler"], fsrs_adapter.FSRS_ID)
        self.assertNotEqual(first["fsrs_state_json"], second["fsrs_state_json"])
