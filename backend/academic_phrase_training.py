from __future__ import annotations

import re
from typing import Iterable

try:
    from .academic_phrases import search_academic_phrases
except ImportError:
    from academic_phrases import search_academic_phrases


TASK_TYPES = ("cloze", "zh_to_en", "personal")
TASK_LABELS = {"cloze": "语境填空", "zh_to_en": "中译英", "personal": "个人造句"}


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def _task(item: dict, task_type: str) -> dict:
    term = item["term"]
    if task_type == "cloze":
        prompt = re.sub(re.escape(term), "______", item["example"], count=1, flags=re.I)
        instruction = "根据语境填入完整词组，注意词组内部的介词和冠词。"
    elif task_type == "zh_to_en":
        prompt = f"将“{item['meaning_zh']}”按自然学术表达译成英语。"
        instruction = f"使用语法框架：{item['grammar_frame']}"
    else:
        prompt = f"使用“{term}”写一句与你的学习、研究或观点有关的英语。"
        instruction = "保留自然搭配，句子至少 5 个英文词，并且内容要与你自己有关。"
    return {
        "task_id": f"academic:{item['sense_key']}:{task_type}",
        "task_type": task_type,
        "label": TASK_LABELS[task_type],
        "term": term,
        "sense_key": item["sense_key"],
        "prompt": prompt,
        "instruction": instruction,
        "meaning_zh": item["meaning_zh"],
        "concept_en": item["concept_en"],
        "grammar_frame": item["grammar_frame"],
        "example": item["example"],
        "example_zh": item["example_zh"],
        "category": item["category"],
        "category_label": item["category_label"],
        "exam_tags": item["exam_tags"],
    }


def training_items(query: str = "", category: str = "", exam: str = "", task_type: str = "", limit: int = 20) -> list[dict]:
    if task_type and task_type not in TASK_TYPES:
        raise ValueError("Unsupported academic phrase task type")
    selected = search_academic_phrases(query, category, exam, min(max(int(limit or 20), 1), 100))
    types: Iterable[str] = (task_type,) if task_type else TASK_TYPES
    return [_task(item, kind) for item in selected for kind in types]


def find_training_item(task_id: str) -> dict | None:
    parts = str(task_id or "").split(":")
    prefix, task_type = (parts[0], parts[-1]) if len(parts) >= 3 else ("", "")
    sense_key = ":".join(parts[1:-1])
    if prefix != "academic" or task_type not in TASK_TYPES:
        return None
    return next((item for item in training_items(limit=100) if item["sense_key"] == sense_key and item["task_type"] == task_type), None)


def evaluate(item: dict, response: str) -> dict:
    answer = str(response or "").strip()
    normalized = _normalize(answer)
    expected = _normalize(item["term"])
    if item["task_type"] in {"cloze", "zh_to_en"}:
        correct = normalized == expected
        feedback = "词组完整且匹配。" if correct else f"建议回看完整词组：{item['term']}"
    else:
        words = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", answer)
        correct = expected in normalized and len(words) >= 5 and bool(re.search(r"[.!?]$", answer))
        feedback = "目标词组已放入完整个人句子。" if correct else "请保留目标词组，并写成至少 5 个英文词的完整句子。"
    return {"correct": correct, "feedback": feedback, "expected": item["term"], "response": answer}
