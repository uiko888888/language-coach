from __future__ import annotations

import re


CURATED_COMPARISONS = (
    {
        "slug": "cordial-keen-zeal",
        "terms": ("cordial", "keen", "zeal"),
        "title": "cordial / keen / zeal",
        "shared_translation": "中文都可能出现“热情”，但英文语义焦点和词性不同。",
        "summary": "cordial 描写对人的友好态度；keen 描写个人强烈的兴趣或意愿；zeal 描写为目标投入的精力与热忱。",
        "memory_rule": "待人 cordial，想做 keen，投入目标用 zeal。",
        "dimensions": [
            {"label": "语义焦点", "value": "cordial = 人际态度；keen = 兴趣或意愿；zeal = 为事业、目标或活动投入精力。"},
            {"label": "词性", "value": "cordial、keen 在本组用法中是形容词；zeal 是不可数名词，对应形容词是 zealous。"},
            {"label": "可互换性", "value": "三者通常不能直接互换。中文译成同一个词，不代表英文句法位置或语义角色相同。"},
            {"label": "强度与语气", "value": "cordial 偏克制、礼貌且正式；keen 可从日常兴趣到强烈渴望；zeal 强调持续投入，过强时可能让人联想到 overzealous。"},
        ],
        "items": {
            "cordial": {
                "pos": "adjective",
                "meaning_zh": "热情友好的；诚恳而有礼的",
                "focus": "对他人表现出的温暖、友好和礼貌，常用于社交或正式关系。",
                "patterns": ["a cordial welcome", "cordial relations", "a cordial meeting"],
                "register": "较正式；常见于欢迎、会面、外交或工作关系。",
                "avoid": "不表示自己很想做某事，不能说 cordial to join。",
                "example": "The hosts gave the visiting students a cordial welcome.",
                "example_zh": "主人热情友好地欢迎了来访学生。",
            },
            "keen": {
                "pos": "adjective",
                "meaning_zh": "渴望的；热衷的；兴趣强烈的",
                "focus": "个人很想做某事，或对某个对象具有强烈兴趣。另有“敏锐、锋利”等独立义项。",
                "patterns": ["be keen to do", "be keen on something", "a keen interest in"],
                "register": "日常和正式语境都常见；be keen on 在英式英语中尤其自然。",
                "avoid": "不等于待人友好，也不直接表示为事业长期投入。",
                "example": "She is keen to join the public-health project.",
                "example_zh": "她非常想参加这个公共卫生项目。",
            },
            "zeal": {
                "pos": "noun",
                "meaning_zh": "热忱；干劲；为目标投入的热情",
                "focus": "为事业、信念、改革或活动付出的强烈精力和投入。",
                "patterns": ["zeal for reform", "with great zeal", "missionary zeal"],
                "register": "较正式，常见于评论、历史、政治和学术写作。",
                "avoid": "它是名词，不能直接放在 welcome 前或接 to do；过度热忱可用 excessive zeal。",
                "example": "He approached the reform with remarkable zeal.",
                "example_zh": "他以非凡的热忱投入这项改革。",
            },
        },
    },
)


def parse_comparison_terms(query: str, minimum: int = 2, maximum: int = 5) -> list[str]:
    raw = re.sub(r"\s+", " ", str(query or "")).strip()
    if not raw:
        raise ValueError("Enter two to five English words")
    normalized = re.sub(r"\s+(?:vs\.?|versus)\s+", ",", raw, flags=re.IGNORECASE)
    parts = [part.strip() for part in re.split(r"[,，;/／|]+", normalized) if part.strip()]
    unique: list[str] = []
    for part in parts:
        clean = re.sub(r"\s+", " ", part)
        if not re.fullmatch(r"[A-Za-z][A-Za-z' -]{0,39}", clean) or len(clean.split()) > 3:
            raise ValueError("Comparison terms must be short English words or phrases")
        if clean.casefold() not in {value.casefold() for value in unique}:
            unique.append(clean)
    if len(unique) < minimum or len(unique) > maximum:
        raise ValueError("Enter two to five different terms separated by commas, slashes, or vs")
    return unique


def curated_comparison(terms: list[str]) -> dict | None:
    normalized = [term.casefold() for term in terms]
    term_set = set(normalized)
    for comparison in CURATED_COMPARISONS:
        if term_set != set(comparison["terms"]) or len(terms) != len(comparison["terms"]):
            continue
        return {
            "slug": comparison["slug"],
            "title": comparison["title"],
            "shared_translation": comparison["shared_translation"],
            "summary": comparison["summary"],
            "memory_rule": comparison["memory_rule"],
            "dimensions": [dict(item) for item in comparison["dimensions"]],
            "items": [
                {"term": original, **comparison["items"][normalized_term]}
                for original, normalized_term in zip(terms, normalized)
            ],
        }
    return None
