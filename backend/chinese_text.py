from __future__ import annotations

import os
from functools import lru_cache
from typing import Any


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
                    return buffer.value
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
