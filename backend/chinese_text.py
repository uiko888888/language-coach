from __future__ import annotations

import os
from functools import lru_cache
from typing import Any


_ZH_CN_LEXICAL_REPAIRS = {
    "後": "后", "乾净": "干净", "乾燥": "干燥",
    "显着": "显著", "卓着": "卓著", "昭着": "昭著",
    "着作": "著作", "着名": "著名", "土着": "土著",
    "原着": "原著", "名着": "名著", "专着": "专著",
    "编着": "编著", "巨着": "巨著", "论着": "论著",
    "着书": "著书", "着述": "著述", "着称": "著称",
    "着录": "著录", "着者": "著者", "着文": "著文",
    "遗着": "遗著", "译着": "译著",
}


def _repair_simplified_lexemes(text: str) -> str:
    for incorrect, correct in _ZH_CN_LEXICAL_REPAIRS.items():
        text = text.replace(incorrect, correct)
    return text


@lru_cache(maxsize=4096)
def to_simplified_chinese(text: str) -> str:
    if not text or not any("\u3400" <= char <= "\u9fff" for char in text):
        return text
    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            flags = 0x02000000  # LCMAP_SIMPLIFIED_CHINESE
            size = kernel32.LCMapStringEx("zh-CN", flags, text, len(text), None, 0, None, None, 0)
            if size:
                buffer = ctypes.create_unicode_buffer(size)
                if kernel32.LCMapStringEx("zh-CN", flags, text, len(text), buffer, size, None, None, 0):
                    return _repair_simplified_lexemes(buffer.value)
        except (AttributeError, OSError, ValueError):
            pass
    return text


def simplify_chinese_payload(value: Any) -> Any:
    if isinstance(value, str):
        return to_simplified_chinese(value)
    if isinstance(value, list):
        return [simplify_chinese_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(simplify_chinese_payload(item) for item in value)
    if isinstance(value, dict):
        return {key: simplify_chinese_payload(item) for key, item in value.items()}
    return value
