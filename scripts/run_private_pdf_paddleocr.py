from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.dictionary_ocr import infer_page_prediction, load_json, sha256_file, validate_sample_manifest, write_json


def result_payload(result: object) -> object:
    value = getattr(result, "json", result)
    value = value() if callable(value) else value
    if isinstance(value, str):
        return json.loads(value)
    def json_safe(item: object) -> object:
        if item is None or isinstance(item, (str, int, float, bool)):
            return item
        if isinstance(item, dict):
            return {str(key): json_safe(child) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [json_safe(child) for child in item]
        if hasattr(item, "tolist"):
            return json_safe(item.tolist())
        return str(item)

    return json_safe(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PaddleOCR 3 PP-Structure on the private 20-page sample.")
    parser.add_argument("--manifest", type=Path, default=ROOT / "config/private_ocr/dk_oxford_20_pages.json")
    parser.add_argument("--sample-dir", type=Path, default=ROOT / "artifacts/private-ocr/dk-oxford-20-pages-v1")
    args = parser.parse_args()
    try:
        from paddleocr import PPStructureV3
    except ImportError as exc:
        raise SystemExit(
            "PaddleOCR 3 is not installed. Prepare the isolated OCR environment before running this command."
        ) from exc
    manifest = validate_sample_manifest(load_json(args.manifest))
    sample_run = load_json(args.sample_dir / "sample-run.json")
    if sample_run.get("sample_id") != manifest["sample_id"]:
        raise SystemExit("Rendered sample metadata does not match the configured sample")
    rendered_pages = {int(item["page"]): item for item in sample_run.get("pages", [])}
    pipeline = PPStructureV3()
    pages = []
    raw_dir = args.sample_dir / "paddle-raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for item in manifest["pages"]:
        page = int(item["page"])
        image_path = args.sample_dir / "pages" / f"page-{page:04d}.png"
        if not image_path.is_file():
            raise SystemExit(f"Rendered sample page is missing: {image_path}")
        expected_hash = str(rendered_pages.get(page, {}).get("image_sha256") or "")
        if not expected_hash or sha256_file(image_path) != expected_hash:
            raise SystemExit(f"Rendered sample page fingerprint mismatch: {image_path}")
        results = [result_payload(result) for result in pipeline.predict(input=str(image_path))]
        write_json(raw_dir / f"page-{page:04d}.json", results)
        from backend.dictionary_ocr import extract_paddle_lines
        lines = extract_paddle_lines(results)
        width = max((line["bbox"][2] for line in lines), default=1.0)
        pages.append(infer_page_prediction(page, width, lines))
    output = args.sample_dir / "paddle-predictions.json"
    write_json(output, {
        "schema_version": 1,
        "sample_id": manifest["sample_id"],
        "source_sha256": sample_run.get("source_sha256"),
        "pages": pages,
    })
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
