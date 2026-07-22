import unittest
import tempfile
from pathlib import Path

from backend.dictionary_ocr import (
    annotation_template,
    evaluate_sample,
    extract_paddle_lines,
    infer_page_prediction,
    validate_sample_manifest,
)
from scripts.prepare_private_pdf_ocr_sample import ensure_annotation_file


def manifest():
    layouts = [
        "standard_three_column",
        "illustration_wrap",
        "cross_column_panel",
        "usage_and_reference_box",
    ]
    return {
        "schema_version": 1,
        "sample_id": "test-sample",
        "source_page_count": 100,
        "thresholds": {
            "headword_accuracy": 0.98,
            "reading_order_accuracy": 0.99,
            "chinese_alignment_error_rate": 0.01,
        },
        "pages": [
            {"page": index + 1, "layout": layouts[index % len(layouts)]}
            for index in range(20)
        ],
    }


class DictionaryOcrTests(unittest.TestCase):
    def test_environment_setup_fails_closed_on_external_command_errors(self):
        script = (Path(__file__).resolve().parents[1] / "scripts" / "prepare_private_ocr_env.ps1").read_text(
            encoding="utf-8"
        )
        self.assertGreaterEqual(script.count("$LASTEXITCODE -ne 0"), 3)
        self.assertIn("Failed to install the pinned Paddle OCR dependencies", script)

    def test_manifest_requires_twenty_unique_pages_and_all_layouts(self):
        checked = validate_sample_manifest(manifest())
        self.assertEqual(sum(checked["layout_counts"].values()), 20)
        invalid = manifest()
        invalid["pages"] = invalid["pages"][:-1]
        with self.assertRaisesRegex(ValueError, "exactly 20"):
            validate_sample_manifest(invalid)

    def test_annotation_template_starts_pending_and_cannot_pass(self):
        sample = manifest()
        gold = annotation_template(sample, "a" * 64)
        prediction = {"sample_id": sample["sample_id"], "source_sha256": "a" * 64, "pages": []}
        report = evaluate_sample(sample, gold, prediction)
        self.assertEqual(report["reviewed_pages"], 0)
        self.assertFalse(report["passed"])
        self.assertFalse(report["promotion_allowed"])

    def test_pending_gold_is_refreshed_when_sample_pages_change(self):
        sample = manifest()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "gold.json"
            ensure_annotation_file(path, sample, "a" * 64)
            changed = manifest()
            changed["pages"][0]["page"] = 99
            ensure_annotation_file(path, changed, "a" * 64)
            self.assertEqual(path.read_text(encoding="utf-8").count('"status": "pending"'), 20)

    def test_perfect_reviewed_sample_passes_all_gates(self):
        sample = manifest()
        gold = annotation_template(sample, "a" * 64)
        predictions = []
        for page in gold["pages"]:
            page.update({
                "status": "reviewed",
                "headwords": [f"word{page['page']}", f"term{page['page']}"],
                "reading_order": [f"word{page['page']}", f"term{page['page']}"],
                "alignments": [{"headword": f"word{page['page']}", "meaning_zh": "释义"}],
            })
            predictions.append({
                "page": page["page"],
                "headwords": page["headwords"],
                "reading_order": page["reading_order"],
                "alignments": page["alignments"],
            })
        report = evaluate_sample(sample, gold, {
            "sample_id": sample["sample_id"], "source_sha256": "a" * 64, "pages": predictions,
        })
        self.assertTrue(report["passed"])
        self.assertEqual(report["metrics"]["headword_accuracy"], 1.0)
        self.assertEqual(report["metrics"]["reading_order_accuracy"], 1.0)
        self.assertEqual(report["metrics"]["chinese_alignment_error_rate"], 0.0)

    def test_wrong_column_order_fails_strict_gate(self):
        sample = manifest()
        gold = annotation_template(sample, "a" * 64)
        predictions = []
        for page in gold["pages"]:
            page.update({
                "status": "reviewed",
                "headwords": ["alpha", "beta", "gamma"],
                "reading_order": ["alpha", "beta", "gamma"],
                "alignments": [{"headword": "alpha", "meaning_zh": "释义"}],
            })
            predictions.append({
                "page": page["page"],
                "headwords": page["headwords"],
                "reading_order": ["beta", "alpha", "gamma"],
                "alignments": page["alignments"],
            })
        report = evaluate_sample(sample, gold, {
            "sample_id": sample["sample_id"], "source_sha256": "a" * 64, "pages": predictions,
        })
        self.assertFalse(report["passed"])
        self.assertIn("reading-order gate failed", report["failure_reasons"])

    def test_prediction_from_another_source_is_rejected(self):
        sample = manifest()
        gold = annotation_template(sample, "a" * 64)
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            evaluate_sample(sample, gold, {
                "sample_id": sample["sample_id"], "source_sha256": "b" * 64, "pages": [],
            })

    def test_paddle_lines_are_normalized_and_ordered_by_column(self):
        raw = {"res": {
            "rec_texts": ["alpha n. 阿尔法", "beta n. 贝塔"],
            "rec_scores": [0.99, 0.98],
            "rec_boxes": [[10, 20, 90, 40], [220, 10, 300, 30]],
        }}
        lines = extract_paddle_lines(raw)
        prediction = infer_page_prediction(7, 300, lines)
        self.assertEqual(len(lines), 2)
        self.assertEqual(prediction["reading_order"], ["alpha n", "beta n"])
        self.assertEqual(prediction["lines"][0]["column"], 0)
        self.assertEqual(prediction["lines"][1]["column"], 2)


if __name__ == "__main__":
    unittest.main()
