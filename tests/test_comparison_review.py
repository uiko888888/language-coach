import sqlite3
import unittest

from backend.comparison_review import (
    catalog_with_review_status,
    comparison_review_queue,
    published_editorial,
    sync_comparison_registry,
    update_comparison_review,
)
from backend.lexical_compare import curated_comparison_catalog
from backend.migrations import _lexical_comparison_review_workflow


class ComparisonReviewTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _lexical_comparison_review_workflow(self.conn)
        sync_comparison_registry(self.conn, curated_comparison_catalog())

    def tearDown(self):
        self.conn.close()

    def test_registry_sync_preserves_reviewed_and_candidate_boundaries(self):
        queue = comparison_review_queue(self.conn)
        self.assertEqual(queue["total"], 200)
        self.assertEqual(queue["counts"]["published"], 85)
        self.assertEqual(queue["counts"]["candidate"], 115)
        self.assertEqual(len(comparison_review_queue(self.conn, exam="IELTS")["items"]), 95)

    def test_versioned_chart_review_promotes_existing_candidate_without_erasing_notes(self):
        chart = next(group for group in curated_comparison_catalog() if group["topic"] == "charts")
        candidate = {**chart, "reviewed": False, "catalog_status": "candidate"}
        sync_comparison_registry(self.conn, [candidate])
        self.conn.execute(
            "UPDATE lexical_comparison_reviews SET workflow_status = 'reviewing', editor_notes = '核对过原始图表' WHERE slug = ?",
            (chart["slug"],),
        )
        sync_comparison_registry(self.conn, [chart])
        promoted = next(item for item in comparison_review_queue(self.conn, "published")["items"] if item["slug"] == chart["slug"])
        self.assertEqual(promoted["editor_notes"], "核对过原始图表")

    def test_repeated_sync_does_not_overwrite_manual_progress(self):
        update_comparison_review(self.conn, "accept-except", {
            "workflow_status": "reviewing", "priority": 99, "editor_notes": "检查同音误写",
        })
        sync_comparison_registry(self.conn, curated_comparison_catalog())
        item = next(item for item in comparison_review_queue(self.conn, "reviewing")["items"] if item["slug"] == "accept-except")
        self.assertEqual(item["priority"], 99)
        self.assertEqual(item["editor_notes"], "检查同音误写")

    def test_evidence_ready_and_rejection_are_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Evidence-ready"):
            update_comparison_review(self.conn, "accept-except", {"workflow_status": "evidence_ready"})
        with self.assertRaisesRegex(ValueError, "rejection reason"):
            update_comparison_review(self.conn, "accept-except", {"workflow_status": "rejected"})

    def test_candidate_cannot_publish_without_complete_editorial_content(self):
        with self.assertRaisesRegex(ValueError, "Publication blocked"):
            update_comparison_review(self.conn, "accept-except", {
                "workflow_status": "published", "editorial": {"summary": "incomplete"},
            })
        with self.assertRaisesRegex(TypeError, "must be objects"):
            update_comparison_review(self.conn, "accept-except", {"editorial": []})

    def test_static_reviewed_priority_remains_editable_without_database_editorial(self):
        reviewed = next(item for item in comparison_review_queue(self.conn, "published")["items"])
        saved = update_comparison_review(self.conn, reviewed["slug"], {"priority": 91})
        self.assertEqual(saved["priority"], 91)
        self.assertEqual(saved["workflow_status"], "published")

    def test_complete_editorial_content_publishes_and_updates_catalog(self):
        def item(term, meaning, example, example_zh):
            return {
                "term": term, "pos": "verb" if term == "accept" else "preposition/conjunction",
                "meaning_zh": meaning, "focus_en": f"reviewed concept for {term}",
                "focus": f"核对 {term} 的句法角色。", "patterns": [f"{term} the result", f"use {term} correctly"],
                "register": "中性高频。", "avoid": "不能只凭读音互换。",
                "example": example, "example_zh": example_zh,
                "example_source": "项目原创审核例句",
            }
        editorial = {
            "shared_translation": "两词形近但句法和含义不同。",
            "summary": "accept 表示接受；except 表示排除。",
            "memory_rule": "accept 接受，except 排除。",
            "dimensions": [
                {"label": "词义", "value": "接受与排除"},
                {"label": "词性", "value": "动词与介词/连词"},
                {"label": "拼写", "value": "ac- 与 ex-"},
            ],
            "items": [
                item("accept", "接受", "They accepted the revised plan.", "他们接受了修改后的计划。"),
                item("except", "除……之外", "Everyone attended except Lee.", "除李以外，所有人都参加了。"),
            ],
        }
        result = update_comparison_review(self.conn, "accept-except", {
            "workflow_status": "published", "editorial": editorial,
            "evidence": {"bilingual_examples": 2, "verified_patterns": 4},
        })
        self.assertEqual(result["workflow_status"], "published")
        with self.assertRaisesRegex(ValueError, "Publication blocked"):
            update_comparison_review(self.conn, "accept-except", {
                "workflow_status": "published", "editorial": {},
            })
        self.assertEqual(published_editorial(self.conn, "accept-except")["summary"], editorial["summary"])
        catalog = catalog_with_review_status(self.conn, curated_comparison_catalog())
        promoted = next(item for item in catalog if item["slug"] == "accept-except")
        self.assertTrue(promoted["reviewed"])
        self.assertEqual(promoted["catalog_status"], "reviewed")


if __name__ == "__main__":
    unittest.main()
