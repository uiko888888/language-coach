from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.comparison_training import comparison_training_candidates, comparison_training_catalog
from backend.comparison_training_audit import CORRECTION_AUDIT_REVIEWS, CORRECTION_TASK_REVISIONS, correction_audit_summary


def main() -> int:
    candidates = [task for task in comparison_training_candidates() if task["task_type"] == "correction"]
    candidate_map = {task["task_id"]: task for task in candidates}
    reviewed_ids = [review["task_id"] for review in CORRECTION_AUDIT_REVIEWS]
    missing = sorted(set(reviewed_ids) - set(candidate_map))
    duplicate_reviews = len(reviewed_ids) - len(set(reviewed_ids))
    invalid_decisions = sorted({review["decision"] for review in CORRECTION_AUDIT_REVIEWS} - {"approved", "revise", "rejected"})
    published = [task for task in comparison_training_catalog() if task["task_type"] == "correction"]
    published_ids = {task["task_id"] for task in published}
    approved_ids = {
        review["task_id"] for review in CORRECTION_AUDIT_REVIEWS if review["decision"] == "approved"
    }
    strata = Counter(
        (candidate_map[task_id]["topic"], candidate_map[task_id]["confusion_type"])
        for task_id in reviewed_ids if task_id in candidate_map
    )
    batches = Counter(review.get("batch", 1) for review in CORRECTION_AUDIT_REVIEWS)
    revision_errors = []
    for task_id, revision in CORRECTION_TASK_REVISIONS.items():
        task = candidate_map.get(task_id)
        if not task:
            revision_errors.append(f"{task_id}: missing candidate")
            continue
        if revision["decision"] != "approved":
            continue
        prompt = revision.get("prompt", "")
        corrected = revision.get("corrected_text", "")
        contains_answer = re.search(rf"(?<![A-Za-z]){re.escape(task['answer'])}(?![A-Za-z])", corrected, re.IGNORECASE)
        contains_distractor = any(
            option != task["answer"] and re.search(rf"(?<![A-Za-z]){re.escape(option)}(?![A-Za-z])", prompt, re.IGNORECASE)
            for option in task["options"]
        )
        if not prompt or not corrected or prompt.casefold() == corrected.casefold() or not contains_answer or not contains_distractor:
            revision_errors.append(f"{task_id}: invalid approved revision structure")
    summary = {
        "candidates": len(candidates),
        **correction_audit_summary(set(candidate_map)),
        "unreviewed": len(candidates) - len(set(reviewed_ids)),
        "published": len(published),
        "approval_rate": round(len(approved_ids) / len(reviewed_ids), 3) if reviewed_ids else 0,
        "revision_records": len({task_id for task_id in reviewed_ids if task_id in CORRECTION_TASK_REVISIONS}),
        "strata": {f"{topic}:{kind}": count for (topic, kind), count in sorted(strata.items())},
        "batches": {str(batch): count for batch, count in sorted(batches.items())},
        "missing_review_tasks": missing,
        "duplicate_reviews": duplicate_reviews,
        "invalid_decisions": invalid_decisions,
        "revision_errors": revision_errors,
        "publication_matches_approval": published_ids == approved_ids,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    valid_batches = batches == Counter({1: 50, 2: 50})
    return 0 if not missing and not duplicate_reviews and not invalid_decisions and not revision_errors and valid_batches and published_ids == approved_ids else 1


if __name__ == "__main__":
    raise SystemExit(main())
