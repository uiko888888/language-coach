from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.academic_phrases import CATEGORY_META, SOURCE, academic_phrase_catalog, validate_academic_phrases
from backend.chinese_text import to_simplified_chinese


def main() -> int:
    validate_academic_phrases()
    items = academic_phrase_catalog()
    categories = Counter(item["category"] for item in items)
    exams = Counter(tag for item in items for tag in item["exam_tags"])
    non_simplified = []
    for item in items:
        for field in ("meaning_zh", "example_zh", "usage_note_zh"):
            if to_simplified_chinese(item[field]) != item[field]:
                non_simplified.append(f"{item['term']}:{field}")
    result = {
        "entries": len(items),
        "categories": dict(sorted(categories.items())),
        "category_gate": categories == Counter({key: 10 for key in CATEGORY_META}),
        "exam_coverage": dict(sorted(exams.items())),
        "complete_entries": sum(all(item.get(field) for field in (
            "meaning_zh", "concept_en", "grammar_frame", "example", "example_zh",
            "usage_note_zh", "source_key", "sense_key",
        )) for item in items),
        "unique_phrases": len({item["term"].casefold() for item in items}),
        "non_simplified_fields": non_simplified,
        "source": SOURCE,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["category_gate"] and result["complete_entries"] == 100 and result["unique_phrases"] == 100 and not non_simplified else 1


if __name__ == "__main__":
    raise SystemExit(main())
