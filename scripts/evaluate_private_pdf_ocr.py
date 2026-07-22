from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.dictionary_ocr import evaluate_sample, load_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate private dictionary OCR against manual gold annotations.")
    parser.add_argument("--manifest", type=Path, default=ROOT / "config/private_ocr/dk_oxford_20_pages.json")
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--prediction", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = evaluate_sample(load_json(args.manifest), load_json(args.gold), load_json(args.prediction))
    if args.report:
        write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
