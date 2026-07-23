import sqlite3
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone

from scripts.report_recommendation_metrics import report


class RecommendationMetricsTests(unittest.TestCase):
    def test_report_returns_funnel_rates_and_closes_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.sqlite"
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE academic_phrase_recommendation_events (event_type TEXT, correct INTEGER, created_at TEXT)")
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            conn.executemany("INSERT INTO academic_phrase_recommendation_events VALUES (?, ?, ?)", [
                ("impression", None, now), ("click", None, now), ("start", None, now),
                ("submit", 1, now), ("submit", 0, now),
            ])
            conn.commit()
            conn.close()
            result = report(path, 7)
            self.assertTrue(result["ready"])
            self.assertEqual(result["events"]["submit"], 2)
            self.assertEqual(result["funnel_rates"]["correct_per_submit"], 0.5)

    def test_report_is_explicit_when_schema_is_not_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            result = report(Path(directory) / "missing.sqlite", 7)
            self.assertFalse(result["ready"])
            self.assertEqual(result["reason"], "schema 25 not applied")


if __name__ == "__main__":
    unittest.main()
