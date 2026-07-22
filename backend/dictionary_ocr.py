from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path


SAMPLE_SCHEMA_VERSION = 1
REQUIRED_SAMPLE_PAGES = 20
ALLOWED_LAYOUTS = {
    "standard_three_column",
    "illustration_wrap",
    "cross_column_panel",
    "usage_and_reference_box",
}
DEFAULT_THRESHOLDS = {
    "headword_accuracy": 0.98,
    "reading_order_accuracy": 0.99,
    "chinese_alignment_error_rate": 0.01,
}
HEADWORD_PATTERN = re.compile(r"^[A-Za-z][A-Za-z' -]{0,48}")
CHINESE_PATTERN = re.compile(r"[\u3400-\u9fff]")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_sample_manifest(manifest: dict) -> dict:
    if int(manifest.get("schema_version", 0)) != SAMPLE_SCHEMA_VERSION:
        raise ValueError("Unsupported OCR sample manifest schema")
    pages = manifest.get("pages")
    if not isinstance(pages, list) or len(pages) != REQUIRED_SAMPLE_PAGES:
        raise ValueError(f"OCR sample must contain exactly {REQUIRED_SAMPLE_PAGES} pages")
    page_count = int(manifest.get("source_page_count", 0))
    numbers = []
    layouts = Counter()
    for item in pages:
        page = int(item.get("page", 0))
        layout = str(item.get("layout") or "")
        if page < 1 or page > page_count:
            raise ValueError(f"OCR sample page is outside the PDF: {page}")
        if layout not in ALLOWED_LAYOUTS:
            raise ValueError(f"Unsupported OCR layout class: {layout}")
        numbers.append(page)
        layouts[layout] += 1
    if len(set(numbers)) != len(numbers):
        raise ValueError("OCR sample pages must be unique")
    if set(layouts) != ALLOWED_LAYOUTS:
        raise ValueError("OCR sample must cover every required layout class")
    thresholds = {**DEFAULT_THRESHOLDS, **(manifest.get("thresholds") or {})}
    if not 0 < float(thresholds["headword_accuracy"]) <= 1:
        raise ValueError("Invalid headword accuracy threshold")
    if not 0 < float(thresholds["reading_order_accuracy"]) <= 1:
        raise ValueError("Invalid reading-order threshold")
    if not 0 <= float(thresholds["chinese_alignment_error_rate"]) < 1:
        raise ValueError("Invalid Chinese-alignment threshold")
    return {**manifest, "thresholds": thresholds, "layout_counts": dict(layouts)}


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def annotation_template(manifest: dict, source_sha256: str) -> dict:
    checked = validate_sample_manifest(manifest)
    return {
        "schema_version": SAMPLE_SCHEMA_VERSION,
        "sample_id": checked["sample_id"],
        "source_sha256": source_sha256,
        "review_policy": "manual_ground_truth",
        "pages": [
            {
                "page": item["page"],
                "layout": item["layout"],
                "status": "pending",
                "headwords": [],
                "reading_order": [],
                "alignments": [],
                "notes": "",
            }
            for item in checked["pages"]
        ],
    }


def normalize_headword(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    return re.sub(r"\s+", " ", text).strip(" .,:;|[](){}")


def normalize_chinese(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)


def _occurrences(values: list[object]) -> list[str]:
    counts = Counter()
    result = []
    for value in values:
        normalized = normalize_headword(value)
        if not normalized:
            continue
        counts[normalized] += 1
        result.append(f"{normalized}#{counts[normalized]}")
    return result


def _headword_score(expected: list[object], predicted: list[object]) -> tuple[int, int, float]:
    expected_counter = Counter(normalize_headword(item) for item in expected if normalize_headword(item))
    predicted_counter = Counter(normalize_headword(item) for item in predicted if normalize_headword(item))
    correct = sum((expected_counter & predicted_counter).values())
    total = max(sum(expected_counter.values()), sum(predicted_counter.values()))
    return correct, total, correct / total if total else 0.0


def _reading_order_score(expected: list[object], predicted: list[object]) -> tuple[int, int, float]:
    expected_tokens = _occurrences(expected)
    predicted_tokens = _occurrences(predicted)
    predicted_position = {token: index for index, token in enumerate(predicted_tokens)}
    common = [token for token in expected_tokens if token in predicted_position]
    correct = 0
    total = 0
    for left_index, left in enumerate(common):
        for right in common[left_index + 1:]:
            total += 1
            if predicted_position[left] < predicted_position[right]:
                correct += 1
    return correct, total, correct / total if total else 0.0


def _alignment_map(items: list[dict]) -> dict[str, str]:
    result = {}
    for item in items:
        headword = normalize_headword(item.get("headword"))
        meaning = normalize_chinese(item.get("meaning_zh"))
        if headword and meaning:
            result[headword] = meaning
    return result


def _alignment_score(expected: list[dict], predicted: list[dict]) -> tuple[int, int, float]:
    expected_map = _alignment_map(expected)
    predicted_map = _alignment_map(predicted)
    errors = sum(predicted_map.get(headword) != meaning for headword, meaning in expected_map.items())
    total = len(expected_map)
    return errors, total, errors / total if total else 1.0


def evaluate_sample(manifest: dict, gold: dict, prediction: dict) -> dict:
    checked = validate_sample_manifest(manifest)
    sample_id = checked["sample_id"]
    if gold.get("sample_id") != sample_id:
        raise ValueError("Gold annotations do not belong to this OCR sample")
    if prediction.get("sample_id") != sample_id:
        raise ValueError("OCR predictions do not belong to this OCR sample")
    gold_source = str(gold.get("source_sha256") or "")
    predicted_source = str(prediction.get("source_sha256") or "")
    if not gold_source or predicted_source != gold_source:
        raise ValueError("OCR prediction source fingerprint does not match the gold sample")
    gold_pages = {int(item["page"]): item for item in gold.get("pages", [])}
    predicted_pages = {int(item["page"]): item for item in prediction.get("pages", [])}
    expected_pages = [int(item["page"]) for item in checked["pages"]]
    reviewed = [page for page in expected_pages if gold_pages.get(page, {}).get("status") == "reviewed"]
    headword_correct = headword_total = 0
    order_correct = order_total = 0
    alignment_errors = alignment_total = 0
    page_results = []
    for page in expected_pages:
        gold_page = gold_pages.get(page, {})
        predicted_page = predicted_pages.get(page, {})
        hc, ht, ha = _headword_score(gold_page.get("headwords", []), predicted_page.get("headwords", []))
        oc, ot, oa = _reading_order_score(
            gold_page.get("reading_order", []), predicted_page.get("reading_order", [])
        )
        ae, at, ar = _alignment_score(gold_page.get("alignments", []), predicted_page.get("alignments", []))
        headword_correct += hc
        headword_total += ht
        order_correct += oc
        order_total += ot
        alignment_errors += ae
        alignment_total += at
        page_results.append({
            "page": page,
            "reviewed": gold_page.get("status") == "reviewed",
            "headword_accuracy": ha,
            "reading_order_accuracy": oa,
            "chinese_alignment_error_rate": ar,
        })
    metrics = {
        "headword_accuracy": headword_correct / headword_total if headword_total else 0.0,
        "reading_order_accuracy": order_correct / order_total if order_total else 0.0,
        "chinese_alignment_error_rate": (
            alignment_errors / alignment_total if alignment_total else 1.0
        ),
    }
    thresholds = checked["thresholds"]
    complete = len(reviewed) == REQUIRED_SAMPLE_PAGES
    enough_evidence = headword_total > 0 and order_total > 0 and alignment_total > 0
    passed = (
        complete
        and enough_evidence
        and metrics["headword_accuracy"] >= float(thresholds["headword_accuracy"])
        and metrics["reading_order_accuracy"] >= float(thresholds["reading_order_accuracy"])
        and metrics["chinese_alignment_error_rate"] < float(thresholds["chinese_alignment_error_rate"])
    )
    return {
        "sample_id": sample_id,
        "reviewed_pages": len(reviewed),
        "required_pages": REQUIRED_SAMPLE_PAGES,
        "evidence": {
            "headwords": headword_total,
            "reading_order_pairs": order_total,
            "chinese_alignments": alignment_total,
        },
        "metrics": metrics,
        "thresholds": thresholds,
        "passed": passed,
        "promotion_allowed": passed,
        "failure_reasons": [
            reason
            for condition, reason in (
                (not complete, "20-page manual review is incomplete"),
                (not enough_evidence, "gold annotations do not contain enough scoring evidence"),
                (metrics["headword_accuracy"] < float(thresholds["headword_accuracy"]), "headword gate failed"),
                (metrics["reading_order_accuracy"] < float(thresholds["reading_order_accuracy"]), "reading-order gate failed"),
                (metrics["chinese_alignment_error_rate"] >= float(thresholds["chinese_alignment_error_rate"]), "Chinese-alignment gate failed"),
            )
            if condition
        ],
        "pages": page_results,
    }


def extract_paddle_lines(payload: object) -> list[dict]:
    lines = []

    def visit(value: object) -> None:
        if isinstance(value, dict):
            texts = value.get("rec_texts")
            boxes = value.get("rec_boxes") or value.get("rec_polys")
            scores = value.get("rec_scores") or []
            if isinstance(texts, list) and isinstance(boxes, list):
                for index, text in enumerate(texts[:len(boxes)]):
                    box = boxes[index]
                    if isinstance(box, list) and len(box) == 4 and not isinstance(box[0], list):
                        bbox = [float(number) for number in box]
                    elif isinstance(box, list) and box and isinstance(box[0], list):
                        xs = [float(point[0]) for point in box]
                        ys = [float(point[1]) for point in box]
                        bbox = [min(xs), min(ys), max(xs), max(ys)]
                    else:
                        continue
                    lines.append({
                        "text": str(text),
                        "confidence": float(scores[index]) if index < len(scores) else None,
                        "bbox": bbox,
                    })
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)
    unique = {}
    for line in lines:
        key = (line["text"], *(round(number, 1) for number in line["bbox"]))
        unique[key] = line
    return list(unique.values())


def infer_page_prediction(page: int, width: float, lines: list[dict]) -> dict:
    usable = [line for line in lines if str(line.get("text") or "").strip()]
    for line in usable:
        x1, y1, x2, y2 = line["bbox"]
        center = (x1 + x2) / 2
        line["column"] = min(2, max(0, int(center / max(width, 1) * 3)))
        line["full_width"] = (x2 - x1) / max(width, 1) > 0.48
    ordered = sorted(
        usable,
        key=lambda line: (
            0 if line["full_width"] else 1,
            line["bbox"][1] if line["full_width"] else line["column"],
            line["bbox"][1],
            line["bbox"][0],
        ),
    )
    headwords = []
    alignments = []
    for line in ordered:
        text = str(line["text"]).strip()
        match = HEADWORD_PATTERN.match(text)
        if match and (line.get("confidence") is None or line["confidence"] >= 0.75):
            candidate = match.group(0).strip(" -")
            if candidate and len(candidate.split()) <= 4:
                headwords.append(candidate)
                chinese = "".join(CHINESE_PATTERN.findall(text))
                if chinese:
                    alignments.append({"headword": candidate, "meaning_zh": chinese})
    return {
        "page": int(page),
        "headwords": headwords,
        "reading_order": headwords.copy(),
        "alignments": alignments,
        "lines": ordered,
    }
