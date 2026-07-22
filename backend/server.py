from __future__ import annotations

import html
import hashlib
import email.utils
import difflib
import json
import mimetypes
import posixpath
import random
import re
import os
import secrets
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from .chinese_text import simplify_chinese_payload
    from .collocations import corpus_collocations
    from .ai_feedback import feedback_provider_status, request_semantic_feedback
    from .backups import create_backup, list_backups, restore_backup
    from .content_extraction import BLOCK_LABELS, adapter_catalog, adapter_for_source, extract_source_content, suggest_annotation_blocks
    from .complete_word_review import complete_word_catalog, submit_complete_word_review
    from .dictionary_quality import audit_dictionary_data
    from .lexical_data import lookup_lexical_layers, search_open_entries
    from .lexical_compare import curated_comparison, curated_comparison_catalog, curated_term_profile, parse_comparison_terms
    from .migrations import run_migrations
    from .output_training import (
        create_output_task_set, latest_output_task_set, output_attempt_payload,
        output_history, save_feedback_decision, save_self_review, save_semantic_feedback,
        submit_output_attempt,
    )
    from .practice_state import active_practice_run, finish_practice_run, save_practice_run, training_prescription
    from .private_dictionaries import (
        private_dictionary_status, private_phrase_meanings, register_private_stardict,
        remove_private_dictionary_index, search_private_entries, update_private_dictionary,
    )
    from .review_scheduler import ensure_review_item, rate_review_item, review_queue, undo_last_review
    from .speaking_training import (
        attach_audio, create_speaking_attempt, create_speaking_task_set, latest_speaking_task_set,
        mark_speaking_attempt_deleted, save_speaking_self_review, save_transcript,
        speaking_attempt_payload, speaking_history,
    )
    from .speech_transcription import transcribe_audio, transcription_status
    from .versioning import SCHEMA_VERSION, app_version, version_payload
    from .usage_contrasts import contrast_by_slug, contrast_catalog
except ImportError:
    from chinese_text import simplify_chinese_payload
    from collocations import corpus_collocations
    from ai_feedback import feedback_provider_status, request_semantic_feedback
    from backups import create_backup, list_backups, restore_backup
    from content_extraction import BLOCK_LABELS, adapter_catalog, adapter_for_source, extract_source_content, suggest_annotation_blocks
    from complete_word_review import complete_word_catalog, submit_complete_word_review
    from dictionary_quality import audit_dictionary_data
    from lexical_data import lookup_lexical_layers, search_open_entries
    from lexical_compare import curated_comparison, curated_comparison_catalog, curated_term_profile, parse_comparison_terms
    from migrations import run_migrations
    from output_training import (
        create_output_task_set, latest_output_task_set, output_attempt_payload,
        output_history, save_feedback_decision, save_self_review, save_semantic_feedback,
        submit_output_attempt,
    )
    from practice_state import active_practice_run, finish_practice_run, save_practice_run, training_prescription
    from private_dictionaries import (
        private_dictionary_status, private_phrase_meanings, register_private_stardict,
        remove_private_dictionary_index, search_private_entries, update_private_dictionary,
    )
    from review_scheduler import ensure_review_item, rate_review_item, review_queue, undo_last_review
    from speaking_training import (
        attach_audio, create_speaking_attempt, create_speaking_task_set, latest_speaking_task_set,
        mark_speaking_attempt_deleted, save_speaking_self_review, save_transcript,
        speaking_attempt_payload, speaking_history,
    )
    from speech_transcription import transcribe_audio, transcription_status
    from versioning import SCHEMA_VERSION, app_version, version_payload
    from usage_contrasts import contrast_by_slug, contrast_catalog


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
PROCESS_APP_VERSION = app_version(ROOT)
DATA = ROOT / "data"
DB_PATH = Path(os.environ.get("LANGUAGE_COACH_DB_PATH", DATA / "language_coach.sqlite")).resolve()
BACKUP_DIR = DATA / "backups"
TRANSLATION_RUNTIME = {"verified": None, "last_error": "", "deepl_url": ""}


def load_local_environment() -> None:
    path = ROOT / ".env.local"
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_local_environment()


SAMPLE_ARTICLE = """Smart devices promise convenience, but they also create a quiet record of daily life. A speaker can learn when a family is at home, a watch can reveal health patterns, and a doorbell camera can capture people who never agreed to be recorded. Supporters argue that these tools save time and improve safety. However, critics point out that privacy policies are often difficult to read, and users may not understand how much information is stored or shared.

The central challenge is not whether technology should be rejected. It is whether companies can design useful products while giving people meaningful control over their own data. Clearer consent, shorter privacy notices, and stronger limits on data sharing would make smart devices easier to trust. Without those safeguards, convenience may gradually become a form of surveillance."""

SAMPLE_TRANSLATION = """智能设备承诺带来便利，但它们也会悄然记录日常生活。智能音箱可以了解一家人何时在家，手表可以揭示健康规律，门铃摄像头则可能拍到从未同意被记录的人。

支持者认为这些工具节省时间并提高安全性。然而，批评者指出，隐私政策往往难以阅读，用户可能并不清楚有多少信息被储存或共享。

核心问题并不是是否应该拒绝技术，而是企业能否在提供实用产品的同时，让人们真正掌控自己的数据。

更清晰的同意机制、更简短的隐私声明以及更严格的数据共享限制，会让智能设备更值得信任。缺少这些保障时，便利可能逐渐演变为一种监控。"""

EXAM_QUESTION_TYPES = {
    "IELTS": [("tfng", "判断题 True / False / Not Given", "reading"), ("heading", "段落标题匹配", "main-idea"), ("matching-info", "段落信息匹配", "reading"), ("gap-fill", "摘要填空", "cloze")],
    "TOEFL": [("complete-words", "Complete the Words（2026 模拟）", "cloze"), ("factual", "事实信息题", "reading"), ("negative-factual", "否定事实题", "reading"), ("inference", "推断题", "reading"), ("rhetorical-purpose", "修辞目的题", "paraphrase"), ("main-idea", "主旨题", "main-idea"), ("simplification", "句子简化", "paraphrase"), ("insertion", "句子插入题", "main-idea"), ("prose-summary", "篇章总结（单选基础）", "main-idea"), ("vocabulary", "语境词义", "cloze")],
    "CET4": [("detail", "仔细阅读·细节定位", "reading"), ("matching", "长篇阅读·信息匹配", "main-idea"), ("inference", "推断判断", "paraphrase"), ("banked-cloze", "选词填空", "cloze")],
    "CET6": [("inference", "深层推断", "reading"), ("matching", "长篇阅读·信息匹配", "main-idea"), ("paraphrase", "同义转述", "paraphrase"), ("banked-cloze", "选词填空", "cloze")],
    "KAOYAN": [("detail-inference", "细节与推断", "reading"), ("main-attitude", "主旨与作者态度", "main-idea"), ("sentence-meaning", "长难句语义", "paraphrase"), ("cloze-logic", "完形与语境逻辑", "cloze")],
    "TEM4": [("detail", "细节理解", "reading"), ("main-idea", "主旨概括", "main-idea"), ("meaning", "近义改写", "paraphrase"), ("lexico-grammar", "词汇语法", "cloze")],
    "TEM8": [("inference", "推断与态度", "reading"), ("title", "标题概括", "main-idea"), ("nuance", "长难句释义", "paraphrase"), ("semantic", "语义辨析", "cloze")],
    "GRE": [("implication", "推断题", "reading"), ("central-concern", "中心论点", "main-idea"), ("function", "句间逻辑", "paraphrase"), ("precision", "精确词义", "cloze")],
    "GMAT": [("support", "论证支持", "reading"), ("argument-role", "论证功能", "main-idea"), ("reasoning", "推理保真", "paraphrase"), ("business-context", "商科语境搭配", "cloze")],
    "general": [("evidence", "证据定位", "reading"), ("main-idea", "主旨题", "main-idea"), ("paraphrase", "同义改写", "paraphrase"), ("cloze", "选词填空", "cloze")],
}

SUPPORTED_EXAMS = [name for name in EXAM_QUESTION_TYPES if name != "general"]

OFFICIAL_EXAM_RESOURCES = [
    {
        "title": "IELTS official sample test questions",
        "exam": "IELTS", "provider": "IELTS", "resource_type": "official_sample",
        "source_url": "https://ielts.org/take-a-test/preparation-resources/sample-test-questions",
        "access_mode": "external_link", "rights_status": "link_only",
        "description": "IELTS 官方公开样题入口；应用只保存来源信息和链接。",
    },
    {
        "title": "British Council free IELTS practice tests",
        "exam": "IELTS", "provider": "British Council", "resource_type": "official_practice",
        "source_url": "https://takeielts.britishcouncil.org/take-ielts/prepare/free-ielts-english-practice-tests",
        "access_mode": "external_link", "rights_status": "link_only",
        "description": "British Council 免费练习入口；题目正文仍在官方页面使用。",
    },
    {
        "title": "IDP IELTS free practice tests",
        "exam": "IELTS", "provider": "IDP IELTS", "resource_type": "official_practice",
        "source_url": "https://ielts.idp.com/prepare/article-free-practice-tests",
        "access_mode": "external_link", "rights_status": "link_only",
        "description": "IDP IELTS 官方练习资料入口。",
    },
    {
        "title": "TOEFL iBT official practice",
        "exam": "TOEFL", "provider": "ETS", "resource_type": "official_sample",
        "source_url": "https://www.ets.org/toefl/test-takers/ibt/prepare/practice-tests.html",
        "access_mode": "external_link", "rights_status": "link_only",
        "description": "ETS TOEFL iBT 官方练习入口。",
    },
    {
        "title": "National College English Test official portal",
        "exam": "CET4", "provider": "NEEA", "resource_type": "official_portal",
        "source_url": "https://cet.neea.edu.cn/",
        "access_mode": "external_link", "rights_status": "link_only",
        "description": "全国大学英语四、六级考试官方网站；仅建立官方入口。",
    },
    {
        "title": "National College English Test official portal",
        "exam": "CET6", "provider": "NEEA", "resource_type": "official_portal",
        "source_url": "https://cet.neea.edu.cn/",
        "access_mode": "external_link", "rights_status": "link_only",
        "description": "全国大学英语四、六级考试官方网站；仅建立官方入口。",
    },
    {
        "title": "National postgraduate entrance examination portal",
        "exam": "KAOYAN", "provider": "CHSI / 研招网", "resource_type": "official_portal",
        "source_url": "https://yz.chsi.com.cn/",
        "access_mode": "external_link", "rights_status": "link_only",
        "description": "全国硕士研究生招生考试官方信息入口；应用不复制来源不明的历年试题。",
    },
]

ARTICLE_THEMES = {
    "环境保护": ["climate", "emission", "carbon", "pollution", "conservation", "biodiversity", "exxon", "renewable"],
    "自然与生态": ["plant", "animal", "species", "forest", "ocean", "mushroom", "wildlife", "ecology"],
    "健康医学": ["health", "medical", "disease", "medicine", "patient", "biology", "sleep", "hibernate"],
    "科技创新": ["technology", "digital", "artificial intelligence", "robot", "device", "data", "cyber", "hacker"],
    "太空探索": ["space", "mars", "planet", "astronaut", "lunar", "nasa", "galaxy"],
    "经济商业": ["business", "economy", "economic", "market", "company", "trade", "consumer", "industry"],
    "国际时政": ["government", "election", "war", "diplomatic", "international", "president", "minister", "parliament"],
    "法律政策": ["law", "court", "trial", "policy", "regulation", "legal", "rights", "justice"],
    "社会文化": ["society", "culture", "community", "identity", "media", "language", "family"],
    "历史考古": ["history", "historical", "ancient", "archaeology", "dna", "heritage"],
    "教育学习": ["education", "school", "student", "teacher", "learning", "university"],
    "心理行为": ["psychology", "behavior", "mental", "emotion", "decision", "memory"],
}

CONTENT_TYPE_LABELS = {
    "report": "新闻报道",
    "opinion": "观点评论",
    "explainer": "学术解释",
    "research": "研究摘要",
    "institution": "机构公告",
    "culture": "文化内容",
}

CONTENT_HUBS = {
    "news": "新闻",
    "opinion": "观点",
    "research": "研究",
    "science": "科学与自然",
    "culture-life": "文化与生活",
    "media": "影视与听力",
    "books": "小说与图书",
}

SOURCE_HUB_OVERRIDES = {
    "The Conversation": "research", "The Conversation Politics": "research", "JSTOR Daily": "research",
    "Guardian Science": "science", "Guardian Environment": "science", "MIT Technology Review": "science",
    "ScienceDaily": "science", "Aeon": "opinion", "Knowledge at Wharton": "opinion",
    "The Economist Business": "opinion", "Guardian Opinion": "opinion",
    "NPR": "news", "NPR World": "news", "BBC World": "news", "BBC Business": "news",
    "Guardian World": "news", "UN News": "news", "private EPUB": "books",
}

CATEGORY_HUBS = {
    "每日新闻": "news", "深度评论": "opinion", "学术研究": "research", "科学与自然": "science",
    "文化与社区": "culture-life", "校园与生活": "culture-life", "博客与通讯": "culture-life",
    "听力与演讲": "media", "影视与流媒体": "media", "小说与图书": "books",
}


def content_hub_for(source: str, content_type: str = "") -> str:
    if source in SOURCE_HUB_OVERRIDES:
        return SOURCE_HUB_OVERRIDES[source]
    return {
        "report": "news", "institution": "news", "opinion": "opinion", "research": "research",
        "culture": "culture-life", "explainer": "research",
    }.get(content_type, "culture-life")


def normalize_article_text(title: str, body: str, preserve_blocks: bool = False) -> str:
    raw_paragraphs = [re.sub(r"[ \t\r\f\v]+", " ", value).strip() for value in re.split(r"\n\s*\n", body or "") if value.strip()]
    clean_title = re.sub(r"\s+", " ", title or "").strip()
    if preserve_blocks and len(raw_paragraphs) > 1:
        if clean_title and raw_paragraphs[0].casefold() == clean_title.casefold():
            raw_paragraphs = raw_paragraphs[1:]
        return "\n\n".join(raw_paragraphs)
    text = re.sub(r"\s+", " ", " ".join(raw_paragraphs)).strip()
    if clean_title and text.lower().startswith(clean_title.lower()):
        text = text[len(clean_title):].lstrip(" .:;-—")
    if not text:
        return ""
    sentence_parts = re.findall(r"[^.!?]+[.!?]+(?:[\"'’”])?|[^.!?]+$", text)
    sentence_parts = [part.strip() for part in sentence_parts if part.strip()]
    if len(sentence_parts) <= 2:
        return " ".join(sentence_parts)
    paragraphs = [" ".join(sentence_parts[index:index + 2]) for index in range(0, len(sentence_parts), 2)]
    return "\n\n".join(paragraphs)


LEXICON = {
    "privacy": ["personal data", "confidentiality", "public exposure"],
    "concern": ["worry", "issue", "matter"],
    "evidence": ["proof", "support", "sign"],
    "significant": ["important", "meaningful", "notable"],
    "convenience": ["ease", "comfort", "efficiency"],
    "surveillance": ["monitoring", "tracking", "observation"],
    "consent": ["permission", "agreement", "approval"],
    "policy": ["rule", "guideline", "official plan"],
    "critic": ["opponent", "reviewer", "skeptic"],
    "supporter": ["advocate", "defender", "ally"],
}


def lexical_term(term: str, meaning_zh: str, note: str = "") -> dict:
    return {"term": term, "meaning_zh": meaning_zh, "note": note}


def phrase(term: str, meaning_zh: str, synonyms: list[dict] | None = None, antonyms: list[dict] | None = None) -> dict:
    return {
        "phrase": term,
        "meaning_zh": meaning_zh,
        "source": "人工精选常用搭配",
        "synonyms": synonyms or [],
        "antonyms": antonyms or [],
    }


def bilingual_example(text: str, translation: str) -> dict:
    return {"text": text, "translation": translation}


LEXICAL_SEEDS = [
    {
        "headword": "inspect", "pos": "verb", "ipa_uk": "/ɪnˈspekt/", "ipa_us": "/ɪnˈspekt/",
        "core_meaning": "to examine something carefully in order to check its condition or quality",
        "meaning_zh": "仔细检查；审查", "level": "B2", "register": "neutral",
        "origin": "Latin inspicere, from in- 'into' + specere 'to look'",
        "breakdown": "in-（向内）+ spect（看）→ 向里面仔细看",
        "forms": ["inspects", "inspected", "inspecting"],
        "aliases": ["检查", "审查", "查看", "观察"],
        "family": ["inspection", "inspector", "perspective", "prospect", "respect", "suspect"],
        "collocations": [
            phrase("inspect the premises", "检查场所", [lexical_term("examine the premises", "勘查场所")], [lexical_term("leave the premises unchecked", "不检查场所")]),
            phrase("inspect for damage", "检查是否有损坏", [lexical_term("check for damage", "查看有无损坏")], [lexical_term("ignore the damage", "忽视损坏")]),
            phrase("closely inspect", "仔细检查", [lexical_term("carefully examine", "认真查验")], [lexical_term("glance over", "粗略扫一眼")]),
        ],
        "synonyms": [lexical_term("examine", "检查；全面细看"), lexical_term("check", "核对；确认是否正确"), lexical_term("scrutinize", "极其仔细地审视")],
        "antonyms": [lexical_term("overlook", "忽略；漏看"), lexical_term("ignore", "不理会")],
        "examples": [
            bilingual_example("Engineers inspect the bridge for structural damage.", "工程师检查桥梁是否存在结构性损坏。"),
            bilingual_example("The documents must be inspected before approval.", "这些文件在批准之前必须经过审查。"),
        ],
        "morphemes": ["in-", "spect"],
    },
    {
        "headword": "inspection", "pos": "noun", "ipa_uk": "/ɪnˈspekʃən/", "ipa_us": "/ɪnˈspekʃən/",
        "core_meaning": "the act of examining something carefully",
        "meaning_zh": "检查；视察；审查", "level": "B2", "register": "neutral",
        "origin": "Late Latin inspectio, from inspicere 'to look into'",
        "breakdown": "in-（向内）+ spect（看）+ -tion（名词后缀）",
        "forms": ["inspections"], "aliases": ["检查", "视察", "检验"],
        "family": ["inspect", "inspector", "inspectional"],
        "collocations": [
            phrase("safety inspection", "安全检查", [lexical_term("safety check", "安全核查")], [lexical_term("unchecked operation", "未经检查的运行")]),
            phrase("routine inspection", "例行检查", [lexical_term("regular examination", "定期检查")], [lexical_term("exceptional inspection", "临时专项检查")]),
            phrase("conduct an inspection", "进行检查", [lexical_term("carry out an examination", "开展检查")], [lexical_term("waive an inspection", "免除检查")]),
        ],
        "synonyms": [lexical_term("examination", "检查；考察"), lexical_term("review", "审查；复核"), lexical_term("audit", "正式审计")],
        "antonyms": [lexical_term("neglect", "疏忽；疏于检查")],
        "examples": [bilingual_example("The building passed its annual safety inspection.", "这栋建筑通过了年度安全检查。")], "morphemes": ["in-", "spect", "-tion"],
    },
    {
        "headword": "respect", "pos": "noun / verb", "ipa_uk": "/rɪˈspekt/", "ipa_us": "/rɪˈspekt/",
        "core_meaning": "admiration for someone, or careful attention to a right or principle",
        "meaning_zh": "尊重；敬意；重视", "level": "B1", "register": "neutral",
        "origin": "Latin respicere, literally 'to look back at'",
        "breakdown": "re-（回）+ spect（看）→ 回头看、认真看待",
        "forms": ["respects", "respected", "respecting"], "aliases": ["尊重", "敬重", "方面"],
        "family": ["respectful", "respectively", "irrespective"],
        "collocations": [
            phrase("show respect for", "对……表示尊重", [lexical_term("treat with respect", "以尊重的态度对待")], [lexical_term("show contempt for", "对……表示轻蔑")]),
            phrase("with respect to", "关于；就……而言", [lexical_term("in relation to", "关于；与……有关")], [lexical_term("regardless of", "不管；不顾")]),
            phrase("mutual respect", "相互尊重", [lexical_term("reciprocal regard", "彼此尊重")], [lexical_term("mutual distrust", "相互不信任")]),
        ],
        "synonyms": [lexical_term("admire", "钦佩"), lexical_term("regard", "尊重；看待")],
        "antonyms": [lexical_term("disrespect", "不尊重"), lexical_term("scorn", "蔑视")],
        "examples": [bilingual_example("Good arguments respect the limits of the evidence.", "好的论证会尊重证据本身的限度。")], "morphemes": ["re-", "spect"],
    },
    {
        "headword": "perspective", "pos": "noun", "ipa_uk": "/pəˈspektɪv/", "ipa_us": "/pərˈspektɪv/",
        "core_meaning": "a particular way of viewing or judging a situation",
        "meaning_zh": "观点；视角；透视法", "level": "B2", "register": "neutral",
        "origin": "Latin perspicere 'to look through or see clearly'",
        "breakdown": "per-（穿过）+ spect（看）+ -ive（名词/形容词后缀）",
        "forms": ["perspectives"], "aliases": ["观点", "角度", "视角"],
        "family": ["prospect", "prospective", "retrospective"],
        "collocations": [
            phrase("from a different perspective", "从不同角度来看", [lexical_term("from another point of view", "从另一个观点来看")], [lexical_term("from the same perspective", "从相同角度来看")]),
            phrase("put into perspective", "客观看待；正确衡量", [lexical_term("see in context", "结合背景来看")], [lexical_term("blow out of proportion", "夸大其严重性")]),
            phrase("historical perspective", "历史视角", [lexical_term("historical viewpoint", "历史观点")], [lexical_term("present-day perspective", "当代视角")]),
        ],
        "synonyms": [lexical_term("viewpoint", "观点"), lexical_term("standpoint", "立场"), lexical_term("outlook", "看法；展望")], "antonyms": [],
        "examples": [bilingual_example("The article examines the issue from a historical perspective.", "这篇文章从历史视角审视这个问题。")], "morphemes": ["per-", "spect", "-ive"],
    },
    {
        "headword": "transport", "pos": "noun / verb", "ipa_uk": "/ˈtrænspɔːt/", "ipa_us": "/ˈtrænspɔːrt/",
        "core_meaning": "to carry people or goods from one place to another",
        "meaning_zh": "运输；交通运输系统", "level": "B1", "register": "neutral",
        "origin": "Latin transportare, from trans- 'across' + portare 'carry'", "breakdown": "trans-（跨越）+ port（携带）",
        "forms": ["transports", "transported", "transporting", "transportation"], "aliases": ["运输", "交通"],
        "family": ["portable", "import", "export", "support"], "collocations": [
            phrase("public transport", "公共交通", [lexical_term("public transit", "公共交通系统")], [lexical_term("private transport", "私人交通")]),
            phrase("transport goods", "运输货物", [lexical_term("carry freight", "运送货物")], [lexical_term("retain goods", "留存货物")]),
        ],
        "synonyms": [lexical_term("carry", "携带；运送"), lexical_term("convey", "输送；传达")], "antonyms": [],
        "examples": [bilingual_example("Railways transport goods efficiently.", "铁路能够高效地运输货物。")], "morphemes": ["trans-", "port"],
    },
    {
        "headword": "predict", "pos": "verb", "ipa_uk": "/prɪˈdɪkt/", "ipa_us": "/prɪˈdɪkt/",
        "core_meaning": "to say what you think will happen in the future", "meaning_zh": "预测；预言", "level": "B1", "register": "neutral",
        "origin": "Latin praedicere, from pre- 'before' + dicere 'say'", "breakdown": "pre-（之前）+ dict（说）",
        "forms": ["predicts", "predicted", "predicting", "prediction"], "aliases": ["预测", "预言"],
        "family": ["prediction", "predictable", "dictate", "contradict"], "collocations": [
            phrase("accurately predict", "准确预测", [lexical_term("forecast precisely", "精准预报")], [lexical_term("misjudge completely", "完全误判")]),
            phrase("predict an outcome", "预测结果", [lexical_term("anticipate a result", "预料结果")], [lexical_term("leave the outcome uncertain", "让结果保持未知")]),
        ],
        "synonyms": [lexical_term("forecast", "预测；预报"), lexical_term("anticipate", "预料；预期")], "antonyms": [],
        "examples": [bilingual_example("The model cannot accurately predict individual behavior.", "该模型无法准确预测个人行为。")], "morphemes": ["pre-", "dict"],
    },
]

MORPHEME_SEEDS = [
    ("spect", "root", "看", "Latin specere / spectare", "与视觉、观察和看待有关", ["inspect", "respect", "perspective", "prospect", "suspect"]),
    ("in-", "prefix", "向内；进入；在……上", "Latin in", "方向性前缀；在部分单词中也可表示否定", ["inspect", "include", "inject"]),
    ("re-", "prefix", "回；再次", "Latin re", "表示返回、重复或反向", ["respect", "review", "rewrite"]),
    ("-tion", "suffix", "行为、过程或结果", "Latin -io / -ionem", "常把动词变为抽象名词；也可见 -ion、-sion 等拼写", ["inspection", "prediction", "observation"]),
    ("port", "root", "携带；运送", "Latin portare", "与携带和运输有关", ["transport", "portable", "import", "export"]),
    ("dict", "root", "说；宣告", "Latin dicere / dictus", "与说话、断言和命令有关", ["predict", "dictate", "contradict"]),
    ("scrib", "root", "写", "Latin scribere", "词形常变为 script", ["describe", "manuscript", "transcript"]),
    ("struct", "root", "建造；排列", "Latin struere / structus", "与结构和建造有关", ["construct", "structure", "instruct"]),
]


DEFAULT_FEEDS = [
    {
        "name": "The Conversation",
        "url": "https://theconversation.com/global/articles.atom",
        "language": "en",
        "level_hint": "B2-C1",
    },
    {
        "name": "JSTOR Daily",
        "url": "https://daily.jstor.org/feed/",
        "language": "en",
        "level_hint": "C1",
    },
    {
        "name": "Guardian Science",
        "url": "https://www.theguardian.com/science/rss",
        "language": "en",
        "level_hint": "B2-C1",
    },
    {
        "name": "Guardian Environment",
        "url": "https://www.theguardian.com/environment/rss",
        "language": "en",
        "level_hint": "B2-C1",
    },
    {
        "name": "MIT Technology Review",
        "url": "https://www.technologyreview.com/feed/",
        "language": "en",
        "level_hint": "C1",
    },
    {
        "name": "ScienceDaily",
        "url": "https://www.sciencedaily.com/rss/all.xml",
        "language": "en",
        "level_hint": "B2-C1",
    },
    {
        "name": "Aeon",
        "url": "https://aeon.co/feed.rss",
        "language": "en",
        "level_hint": "C1",
    },
    {
        "name": "Knowledge at Wharton",
        "url": "https://knowledge.wharton.upenn.edu/feed",
        "language": "en",
        "level_hint": "C1",
    },
    {
        "name": "The Economist Business",
        "url": "https://www.economist.com/business/rss.xml",
        "language": "en",
        "level_hint": "C1",
    },
    {
        "name": "NPR",
        "url": "https://feeds.npr.org/1001/rss.xml",
        "language": "en",
        "level_hint": "B2",
    },
    {
        "name": "BBC World",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "language": "en",
        "level_hint": "B2",
    },
    {
        "name": "BBC Business",
        "url": "https://feeds.bbci.co.uk/news/business/rss.xml",
        "language": "en",
        "level_hint": "B2",
    },
    {
        "name": "Guardian World",
        "url": "https://www.theguardian.com/world/rss",
        "language": "en",
        "level_hint": "B2-C1",
    },
    {
        "name": "Guardian Opinion",
        "url": "https://www.theguardian.com/commentisfree/rss",
        "language": "en",
        "level_hint": "C1",
    },
    {
        "name": "The Conversation Politics",
        "url": "https://theconversation.com/us/politics/articles.atom",
        "language": "en",
        "level_hint": "B2-C1",
    },
    {
        "name": "NPR World",
        "url": "https://feeds.npr.org/1004/rss.xml",
        "language": "en",
        "level_hint": "B2",
    },
    {
        "name": "UN News",
        "url": "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
        "language": "en",
        "level_hint": "B2-C1",
    },
]


SOURCE_PROFILES = {
    "The Conversation": {"tier": "核心", "topics": ["科学", "社会", "教育"], "exams": ["IELTS", "TOEFL", "CET6", "KAOYAN", "TEM8", "GRE"]},
    "JSTOR Daily": {"tier": "核心", "topics": ["历史", "人文", "社会科学"], "exams": ["TOEFL", "CET6", "KAOYAN", "TEM8", "GRE"]},
    "Guardian Science": {"tier": "核心", "topics": ["科学", "健康"], "exams": ["IELTS", "TOEFL", "CET4", "CET6", "KAOYAN", "TEM4", "TEM8"]},
    "Guardian Environment": {"tier": "核心", "topics": ["环境", "社会"], "exams": ["IELTS", "TOEFL", "CET4", "CET6", "KAOYAN", "TEM4", "TEM8"]},
    "MIT Technology Review": {"tier": "核心", "topics": ["科技", "商业"], "exams": ["TOEFL", "CET6", "KAOYAN", "GRE", "GMAT", "TEM8"]},
    "ScienceDaily": {"tier": "核心", "topics": ["自然科学", "健康"], "exams": ["IELTS", "TOEFL", "CET4", "CET6", "GRE"]},
    "Aeon": {"tier": "核心", "topics": ["哲学", "心理", "文化"], "exams": ["CET6", "KAOYAN", "TEM8", "GRE"]},
    "Knowledge at Wharton": {"tier": "核心", "topics": ["商业", "经济", "管理"], "exams": ["CET6", "KAOYAN", "GMAT", "GRE", "TEM8"]},
    "The Economist Business": {"tier": "核心", "topics": ["商业", "经济", "政策"], "exams": ["CET6", "KAOYAN", "GMAT", "GRE", "TEM8"]},
    "BBC Learning English": {"tier": "补充", "topics": ["语言", "时事"], "exams": ["IELTS", "CET4", "CET6", "TEM4"]},
    "NPR": {"tier": "补充", "topics": ["时事", "社会"], "exams": ["IELTS", "TOEFL", "CET4", "CET6", "KAOYAN", "TEM4", "TEM8"]},
    "BBC World": {"tier": "核心", "topics": ["国际时政", "社会", "公共政策"], "exams": ["IELTS", "TOEFL", "CET4", "CET6", "KAOYAN", "TEM4", "TEM8"]},
    "BBC Business": {"tier": "核心", "topics": ["商业", "经济", "公共政策"], "exams": ["IELTS", "TOEFL", "CET4", "CET6", "KAOYAN", "GMAT"]},
    "Guardian World": {"tier": "核心", "topics": ["国际时政", "社会", "法律"], "exams": ["IELTS", "TOEFL", "CET6", "KAOYAN", "TEM8"]},
    "Guardian Opinion": {"tier": "核心", "topics": ["观点", "文化评论", "公共政策"], "exams": ["IELTS", "CET6", "KAOYAN", "TEM8", "GRE"]},
    "The Conversation Politics": {"tier": "核心", "topics": ["政治", "公共政策", "社会"], "exams": ["IELTS", "TOEFL", "CET6", "KAOYAN", "TEM8", "GRE"]},
    "NPR World": {"tier": "补充", "topics": ["国际时政", "社会", "文化"], "exams": ["IELTS", "TOEFL", "CET4", "CET6", "KAOYAN", "TEM4", "TEM8"]},
    "UN News": {"tier": "核心", "topics": ["国际事务", "公共政策", "健康"], "exams": ["IELTS", "TOEFL", "CET4", "CET6", "KAOYAN", "TEM8"]},
    "manual": {"tier": "个人", "topics": ["自选"], "exams": SUPPORTED_EXAMS},
    "seed": {"tier": "示例", "topics": ["科技", "社会"], "exams": SUPPORTED_EXAMS},
}

SOURCE_CLASSIFICATION = {
    "The Conversation": ("学术解释平台", "explainer"),
    "The Conversation Politics": ("学术解释平台", "explainer"),
    "JSTOR Daily": ("学术解释平台", "explainer"),
    "Guardian Science": ("新闻媒体", "report"),
    "Guardian Environment": ("新闻媒体", "report"),
    "Guardian World": ("新闻媒体", "report"),
    "Guardian Opinion": ("新闻媒体", "opinion"),
    "BBC World": ("新闻媒体", "report"),
    "BBC Business": ("新闻媒体", "report"),
    "MIT Technology Review": ("科技媒体", "explainer"),
    "ScienceDaily": ("研究资讯", "research"),
    "Aeon": ("文化评论", "culture"),
    "Knowledge at Wharton": ("学术解释平台", "explainer"),
    "The Economist Business": ("新闻媒体", "opinion"),
    "BBC Learning English": ("教育媒体", "explainer"),
    "NPR": ("公共媒体", "report"),
    "NPR World": ("公共媒体", "report"),
    "UN News": ("公共机构", "institution"),
    "manual": ("个人导入", "explainer"),
    "browser": ("网页导入", "explainer"),
    "seed": ("示例内容", "explainer"),
}

SOURCE_CATALOG_EXTRAS = {
    "Reuters": {"category": "每日新闻", "homepage": "https://www.reuters.com/", "access_mode": "摘要与原站", "rights_mode": "保存标题、摘要、元数据和原站链接", "formats": ["文章", "视频"], "cadence": "实时"},
    "Associated Press": {"category": "每日新闻", "homepage": "https://apnews.com/", "access_mode": "摘要与原站", "rights_mode": "保存标题、摘要、元数据和原站链接", "formats": ["文章", "视频"], "cadence": "实时"},
    "Financial Times": {"category": "每日新闻", "homepage": "https://www.ft.com/", "access_mode": "摘要与原站", "rights_mode": "仅元数据、摘要和用户授权摘录", "formats": ["文章", "播客"], "cadence": "每日"},
    "Bloomberg": {"category": "每日新闻", "homepage": "https://www.bloomberg.com/", "access_mode": "摘要与原站", "rights_mode": "仅元数据、摘要和用户授权摘录", "formats": ["文章", "视频", "播客"], "cadence": "实时"},
    "The Wall Street Journal": {"category": "每日新闻", "homepage": "https://www.wsj.com/", "access_mode": "摘要与原站", "rights_mode": "仅元数据、摘要和用户授权摘录", "formats": ["文章", "播客"], "cadence": "每日"},
    "The New York Times": {"category": "每日新闻", "homepage": "https://www.nytimes.com/", "access_mode": "摘要与原站", "rights_mode": "仅元数据、摘要和用户授权摘录", "formats": ["文章", "播客"], "cadence": "每日"},
    "The New Yorker": {"category": "深度评论", "homepage": "https://www.newyorker.com/", "access_mode": "摘要与原站", "rights_mode": "仅元数据、摘要和用户授权摘录", "formats": ["文章", "播客"], "cadence": "每周"},
    "The Economist": {"category": "深度评论", "homepage": "https://www.economist.com/", "access_mode": "摘要与原站", "rights_mode": "仅元数据、摘要和用户授权摘录", "formats": ["文章", "播客"], "cadence": "每日"},
    "The Atlantic": {"category": "深度评论", "homepage": "https://www.theatlantic.com/", "access_mode": "摘要与原站", "rights_mode": "仅元数据、摘要和用户授权摘录", "formats": ["文章", "播客"], "cadence": "每日"},
    "Foreign Affairs": {"category": "深度评论", "homepage": "https://www.foreignaffairs.com/", "access_mode": "摘要与原站", "rights_mode": "仅元数据、摘要和用户授权摘录", "formats": ["文章", "播客"], "cadence": "每周"},
    "National Geographic": {"category": "科学与自然", "homepage": "https://www.nationalgeographic.com/", "access_mode": "摘要与原站", "rights_mode": "仅元数据、摘要和用户授权摘录", "formats": ["文章", "视频"], "cadence": "每周"},
    "Nature News": {"category": "科学与自然", "homepage": "https://www.nature.com/news", "access_mode": "摘要与原站", "rights_mode": "保存元数据、摘要和合法链接", "formats": ["文章", "研究资讯"], "cadence": "每日"},
    "Science": {"category": "科学与自然", "homepage": "https://www.science.org/news", "access_mode": "摘要与原站", "rights_mode": "保存元数据、摘要和合法链接", "formats": ["文章", "研究资讯"], "cadence": "每日"},
    "NASA": {"category": "科学与自然", "homepage": "https://www.nasa.gov/", "access_mode": "开放页面与 API", "rights_mode": "按美国政府作品和页面标注逐项处理", "formats": ["文章", "图片", "视频"], "cadence": "每日"},
    "NOAA": {"category": "科学与自然", "homepage": "https://www.noaa.gov/", "access_mode": "开放页面与 API", "rights_mode": "按美国政府作品和页面标注逐项处理", "formats": ["文章", "数据", "视频"], "cadence": "每日"},
    "VOA Learning English": {"category": "听力与演讲", "homepage": "https://learningenglish.voanews.com/", "access_mode": "公开页面", "rights_mode": "保存链接、公开 transcript 和短语境", "formats": ["文章", "音频", "视频"], "cadence": "每日"},
    "TED": {"category": "听力与演讲", "homepage": "https://www.ted.com/", "access_mode": "公开页面", "rights_mode": "保存链接、公开 transcript 和短语境", "formats": ["视频", "字幕", "演讲稿"], "cadence": "每周"},
    "BBC World Service": {"category": "听力与演讲", "homepage": "https://www.bbc.co.uk/worldserviceradio", "access_mode": "公开页面与播客源", "rights_mode": "保存链接、节目元数据和公开 transcript", "formats": ["音频", "播客", "讲稿"], "cadence": "每日"},
    "NPR Podcasts": {"category": "听力与演讲", "homepage": "https://www.npr.org/podcasts/", "access_mode": "公开页面与播客源", "rights_mode": "保存链接、节目元数据和公开 transcript", "formats": ["音频", "播客", "讲稿"], "cadence": "每日"},
    "Amazon Books": {"category": "小说与图书", "homepage": "https://www.amazon.com/books-used-books-textbooks/", "access_mode": "书籍发现", "rights_mode": "仅书籍元数据、简介和原站链接", "formats": ["图书元数据"], "cadence": "按需"},
    "HBO Max": {"category": "影视与流媒体", "homepage": "https://www.max.com/", "access_mode": "用户订阅与本地字幕", "rights_mode": "不抓取视频；仅用户合法字幕、时间点和短语境", "formats": ["视频", "字幕"], "cadence": "按需"},
    "Apple TV+": {"category": "影视与流媒体", "homepage": "https://tv.apple.com/", "access_mode": "用户订阅与本地字幕", "rights_mode": "不抓取视频；仅用户合法字幕、时间点和短语境", "formats": ["视频", "字幕"], "cadence": "按需"},
    "Prime Video": {"category": "影视与流媒体", "homepage": "https://www.primevideo.com/", "access_mode": "用户订阅与本地字幕", "rights_mode": "不抓取视频；仅用户合法字幕、时间点和短语境", "formats": ["视频", "字幕"], "cadence": "按需"},
    "Project Gutenberg": {"category": "小说与图书", "homepage": "https://www.gutenberg.org/", "access_mode": "开放全文", "rights_mode": "仅公共领域或许可允许的全文", "formats": ["小说", "图书"], "cadence": "按需"},
    "Standard Ebooks": {"category": "小说与图书", "homepage": "https://standardebooks.org/", "access_mode": "开放全文", "rights_mode": "公共领域电子书", "formats": ["小说", "图书"], "cadence": "按需"},
    "Google Scholar": {"category": "学术研究", "homepage": "https://scholar.google.com/", "access_mode": "检索与提醒", "rights_mode": "保存论文元数据、摘要、DOI 和合法链接", "formats": ["论文元数据", "摘要"], "cadence": "按提醒"},
    "arXiv": {"category": "学术研究", "homepage": "https://arxiv.org/", "access_mode": "开放元数据", "rights_mode": "按论文许可证处理全文", "formats": ["论文", "摘要"], "cadence": "每日"},
    "PubMed": {"category": "学术研究", "homepage": "https://pubmed.ncbi.nlm.nih.gov/", "access_mode": "开放元数据", "rights_mode": "保存元数据和摘要；全文按许可处理", "formats": ["论文元数据", "摘要"], "cadence": "每日"},
    "SSRN": {"category": "学术研究", "homepage": "https://www.ssrn.com/", "access_mode": "开放元数据", "rights_mode": "保存论文元数据、摘要和合法链接", "formats": ["论文元数据", "摘要"], "cadence": "每日"},
    "Project MUSE": {"category": "学术研究", "homepage": "https://muse.jhu.edu/", "access_mode": "检索与机构访问", "rights_mode": "保存元数据、摘要、DOI 和机构访问链接", "formats": ["论文元数据", "摘要"], "cadence": "按提醒"},
    "Open Library": {"category": "小说与图书", "homepage": "https://openlibrary.org/", "access_mode": "开放元数据 API", "rights_mode": "保存书籍元数据；正文按借阅与版权状态处理", "formats": ["图书元数据"], "cadence": "按需"},
    "University public lectures": {"category": "校园与生活", "homepage": "", "access_mode": "学校公开页面与用户订阅", "rights_mode": "保存通知、公开讲座链接和用户自有材料", "formats": ["校园通知", "讲座", "视频"], "cadence": "按学校"},
    "Local life services": {"category": "校园与生活", "homepage": "", "access_mode": "用户选择的本地服务", "rights_mode": "保存公开通知、实用信息和原始链接", "formats": ["天气", "交通", "活动", "招聘"], "cadence": "每日"},
    "Substack": {"category": "博客与通讯", "homepage": "https://substack.com/", "access_mode": "用户订阅", "rights_mode": "按作者订阅权限保存摘要、链接和短语境", "formats": ["博客", "通讯", "播客"], "cadence": "按订阅"},
}


def source_catalog() -> list[dict]:
    feed_by_name = {feed["name"]: feed for feed in DEFAULT_FEEDS}
    items = []
    for name, feed in feed_by_name.items():
        profile = SOURCE_PROFILES.get(name, {"topics": ["综合"]})
        source_kind, default_content_type = SOURCE_CLASSIFICATION.get(name, ("其他来源", "explainer"))
        hub = content_hub_for(name, default_content_type)
        items.append({
            "name": name,
            "category": CONTENT_HUBS[hub],
            "hub": hub,
            "hub_label": CONTENT_HUBS[hub],
            "homepage": feed["url"],
            "access_mode": "RSS 自动更新",
            "rights_mode": "保存合法摘要、源站链接和 feed 提供的完整内容",
            "formats": ["文章"],
            "cadence": "每日",
            "difficulty": feed.get("level_hint", "B2-C1"),
            "transcript_available": False,
            "source_kind": source_kind,
            "default_content_type": default_content_type,
            "automatic": True,
        })
    for name, metadata in SOURCE_CATALOG_EXTRAS.items():
        hub = CATEGORY_HUBS.get(metadata["category"], "culture-life")
        items.append({
            "name": name,
            **metadata,
            "category": CONTENT_HUBS[hub],
            "hub": hub,
            "hub_label": CONTENT_HUBS[hub],
            "difficulty": metadata.get("difficulty", "B2-C1" if hub in {"news", "media", "culture-life"} else "C1"),
            "transcript_available": any(value in metadata["formats"] for value in ("字幕", "演讲稿", "讲稿")),
            "source_kind": "外部内容平台",
            "default_content_type": "culture" if metadata["category"] in {"影视与流媒体", "小说与图书"} else "explainer",
            "automatic": False,
        })
    return sorted(items, key=lambda item: (not item["automatic"], item["category"], item["name"]))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def speaking_audio_dir() -> Path:
    return Path(os.environ.get("LANGUAGE_COACH_AUDIO_DIR", DB_PATH.parent / "speaking")).resolve()


@contextmanager
def db():
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


EPUB_MAX_FILE_BYTES = 100 * 1024 * 1024
EPUB_MAX_ENTRY_BYTES = 10 * 1024 * 1024
EPUB_MAX_TOTAL_BYTES = 150 * 1024 * 1024
EPUB_MAX_ENTRIES = 5000
EPUB_MAX_CHAPTERS = 1000


class EpubTextParser(HTMLParser):
    block_tags = {"p", "div", "li", "blockquote", "h1", "h2", "h3", "h4", "title"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self.headings: list[str] = []
        self.current: list[str] = []
        self.current_tag = ""
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "svg"}:
            self.ignored_depth += 1
        if not self.ignored_depth and tag in self.block_tags:
            self.flush()
            self.current_tag = tag

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "svg"} and self.ignored_depth:
            self.ignored_depth -= 1
            return
        if not self.ignored_depth and tag in self.block_tags:
            self.flush()

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.current.append(data)

    def flush(self) -> None:
        value = re.sub(r"\s+", " ", " ".join(self.current)).strip()
        if value:
            self.blocks.append(value)
            if self.current_tag in {"h1", "h2", "h3", "title"}:
                self.headings.append(value)
        self.current = []
        self.current_tag = ""


def xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def epub_file_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_epub(path_value: str) -> dict:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file() or path.suffix.casefold() != ".epub":
        raise ValueError("请选择存在的 EPUB 文件")
    if path.stat().st_size > EPUB_MAX_FILE_BYTES:
        raise ValueError("EPUB 文件超过 100 MB 安全上限")
    fingerprint = epub_file_fingerprint(path)
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError("EPUB ZIP 结构无效") from exc
    with archive:
        entries = archive.infolist()
        if len(entries) > EPUB_MAX_ENTRIES or sum(item.file_size for item in entries) > EPUB_MAX_TOTAL_BYTES:
            raise ValueError("EPUB 解压规模超过安全上限")
        if any(item.file_size > EPUB_MAX_ENTRY_BYTES for item in entries):
            raise ValueError("EPUB 包含过大的单个内容文件")
        names = {item.filename for item in entries}
        opf_name = ""
        if "META-INF/container.xml" in names:
            container = ET.fromstring(archive.read("META-INF/container.xml"))
            rootfile = next((node for node in container.iter() if xml_local_name(node.tag) == "rootfile"), None)
            if rootfile is not None:
                opf_name = rootfile.attrib.get("full-path", "")
        if not opf_name:
            opf_name = next((name for name in names if name.casefold().endswith(".opf")), "")
        if not opf_name or opf_name not in names:
            raise ValueError("EPUB 缺少 OPF package 文档")
        package = ET.fromstring(archive.read(opf_name))
        metadata_nodes = [node for node in package.iter() if xml_local_name(node.tag) in {"title", "creator", "language"}]
        metadata = {}
        for node in metadata_nodes:
            key = xml_local_name(node.tag)
            if key not in metadata and (node.text or "").strip():
                metadata[key] = re.sub(r"\s+", " ", node.text or "").strip()
        manifest = {
            node.attrib.get("id", ""): node.attrib.get("href", "")
            for node in package.iter()
            if xml_local_name(node.tag) == "item" and node.attrib.get("id") and node.attrib.get("href")
        }
        spine = [
            node.attrib.get("idref", "")
            for node in package.iter()
            if xml_local_name(node.tag) == "itemref" and node.attrib.get("idref")
        ]
        opf_dir = posixpath.dirname(opf_name)
        chapters = []
        seen_hashes = set()
        for idref in spine:
            href = urllib.parse.unquote(manifest.get(idref, "").split("#", 1)[0])
            entry_name = posixpath.normpath(posixpath.join(opf_dir, href))
            if not href or entry_name not in names or not entry_name.casefold().endswith((".html", ".htm", ".xhtml")):
                continue
            parser = EpubTextParser()
            parser.feed(archive.read(entry_name).decode("utf-8", errors="replace"))
            parser.flush()
            blocks = [value for value in parser.blocks if len(value) > 1]
            body = "\n\n".join(blocks)
            word_count = len(re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", body))
            if word_count < 20:
                continue
            body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
            if body_hash in seen_hashes:
                continue
            seen_hashes.add(body_hash)
            chapters.append({
                "position": len(chapters) + 1,
                "title": parser.headings[0][:180] if parser.headings else f"Chapter {len(chapters) + 1}",
                "body": body,
                "body_hash": body_hash,
                "word_count": word_count,
            })
            if len(chapters) >= EPUB_MAX_CHAPTERS:
                break
    if not chapters:
        raise ValueError("EPUB 中没有可读取的章节正文")
    return {
        "fingerprint": fingerprint,
        "title": metadata.get("title") or path.stem,
        "author": metadata.get("creator", ""),
        "language": metadata.get("language", "en")[:16] or "en",
        "source_path": str(path),
        "chapters": chapters,
    }


def book_detail(conn: sqlite3.Connection, book_id: int, include_chapters: bool = True) -> dict | None:
    row = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["source_path"] = Path(item["source_path"]).name
    if include_chapters:
        item["chapters"] = rows_to_dicts(conn.execute(
            """SELECT id, book_id, position, title, word_count, article_id
               FROM book_chapters WHERE book_id = ? ORDER BY position""", (book_id,)
        ).fetchall())
    return item


def import_epub(path_value: str) -> tuple[dict, bool]:
    parsed = parse_epub(path_value)
    now = utc_now()
    with db() as conn:
        existing = conn.execute("SELECT id FROM books WHERE fingerprint = ?", (parsed["fingerprint"],)).fetchone()
        if existing:
            return book_detail(conn, existing["id"]), False
        cursor = conn.execute(
            """INSERT INTO books
               (fingerprint, title, author, language, source_path, rights_status, chapter_count, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'private_user_material', ?, ?, ?)""",
            (parsed["fingerprint"], parsed["title"], parsed["author"], parsed["language"],
             parsed["source_path"], len(parsed["chapters"]), now, now),
        )
        book_id = cursor.lastrowid
        conn.executemany(
            """INSERT INTO book_chapters
               (book_id, position, title, body, body_hash, word_count, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [(book_id, item["position"], item["title"], item["body"], item["body_hash"], item["word_count"], now, now)
             for item in parsed["chapters"]],
        )
        return book_detail(conn, book_id), True


def materialize_book_chapter(conn: sqlite3.Connection, chapter_id: int) -> dict | None:
    row = conn.execute(
        """SELECT c.*, b.title AS book_title, b.author, b.language, b.fingerprint
           FROM book_chapters c JOIN books b ON b.id = c.book_id WHERE c.id = ?""", (chapter_id,)
    ).fetchone()
    if not row:
        return None
    if row["article_id"]:
        return dict(conn.execute("SELECT * FROM articles WHERE id = ?", (row["article_id"],)).fetchone())
    now = utc_now()
    source_url = f"private-epub://{row['fingerprint']}/{row['position']}"
    title = f"{row['book_title']} · {row['title']}"
    cursor = conn.execute(
        """INSERT INTO articles
           (title, language, level, topic, source, visibility, source_url, content_status, content_type, body, created_at, updated_at)
           VALUES (?, ?, ?, 'literature', 'private EPUB', 'private', ?, 'full', 'culture', ?, ?, ?)""",
        (title, row["language"] or "en", estimate_level(row["body"]), source_url, row["body"], now, now),
    )
    conn.execute("UPDATE book_chapters SET article_id = ?, updated_at = ? WHERE id = ?", (cursor.lastrowid, now, chapter_id))
    return dict(conn.execute("SELECT * FROM articles WHERE id = ?", (cursor.lastrowid,)).fetchone())


def unique_cards_payload(conn: sqlite3.Connection) -> list[dict]:
    rows = rows_to_dicts(conn.execute(
        """SELECT c.*, ri.state AS review_state, ri.due_at AS review_due_at,
                  ri.repetitions AS review_repetitions, ri.lapses AS review_lapses
           FROM cards c
           LEFT JOIN review_items ri ON ri.item_type = 'card' AND ri.item_id = c.id AND ri.learner_key = 'local'
           ORDER BY c.updated_at DESC, c.id DESC"""
    ).fetchall())
    seen: set[str] = set()
    unique = []
    for item in rows:
        key = re.sub(r"\s+", " ", item["term"]).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def ensure_wordnet_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS dictionary_sources (
          source_key TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          version TEXT NOT NULL,
          license TEXT NOT NULL,
          attribution TEXT NOT NULL,
          source_url TEXT NOT NULL,
          checksum TEXT NOT NULL,
          imported_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS wordnet_synsets (
          synset_id TEXT PRIMARY KEY,
          pos TEXT NOT NULL,
          definitions_json TEXT NOT NULL DEFAULT '[]',
          examples_json TEXT NOT NULL DEFAULT '[]',
          members_json TEXT NOT NULL DEFAULT '[]',
          ili TEXT NOT NULL DEFAULT '',
          source_key TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS wordnet_lemmas (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          lemma TEXT NOT NULL,
          normalized TEXT NOT NULL,
          pos TEXT NOT NULL,
          synset_id TEXT NOT NULL,
          sense_id TEXT NOT NULL,
          pronunciations_json TEXT NOT NULL DEFAULT '[]',
          source_key TEXT NOT NULL,
          UNIQUE(normalized, pos, synset_id, sense_id)
        );

        CREATE TABLE IF NOT EXISTS wordnet_relations (
          synset_id TEXT NOT NULL,
          relation_type TEXT NOT NULL,
          target_synset_id TEXT NOT NULL,
          source_key TEXT NOT NULL,
          PRIMARY KEY (synset_id, relation_type, target_synset_id)
        );

        CREATE INDEX IF NOT EXISTS idx_wordnet_lemmas_normalized
        ON wordnet_lemmas(normalized);

        CREATE INDEX IF NOT EXISTS idx_wordnet_relations_source
        ON wordnet_relations(synset_id, relation_type);
        """
    )


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS articles (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL,
              language TEXT NOT NULL DEFAULT 'en',
              level TEXT NOT NULL DEFAULT 'B1-B2',
              topic TEXT NOT NULL DEFAULT 'general',
              source TEXT NOT NULL DEFAULT 'manual',
              visibility TEXT NOT NULL DEFAULT 'public',
              source_url TEXT NOT NULL DEFAULT '',
              content_status TEXT NOT NULL DEFAULT 'summary',
              content_type TEXT NOT NULL DEFAULT 'auto',
              body TEXT NOT NULL,
              published_at TEXT NOT NULL DEFAULT '',
              source_guid TEXT NOT NULL DEFAULT '',
              content_hash TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS books (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              fingerprint TEXT NOT NULL UNIQUE,
              title TEXT NOT NULL,
              author TEXT NOT NULL DEFAULT '',
              language TEXT NOT NULL DEFAULT 'en',
              source_path TEXT NOT NULL,
              rights_status TEXT NOT NULL DEFAULT 'private_user_material',
              chapter_count INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS book_chapters (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              book_id INTEGER NOT NULL,
              position INTEGER NOT NULL,
              title TEXT NOT NULL,
              body TEXT NOT NULL,
              body_hash TEXT NOT NULL,
              word_count INTEGER NOT NULL DEFAULT 0,
              article_id INTEGER,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(book_id, position),
              UNIQUE(book_id, body_hash),
              FOREIGN KEY(book_id) REFERENCES books(id),
              FOREIGN KEY(article_id) REFERENCES articles(id)
            );

            CREATE TABLE IF NOT EXISTS cards (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              term TEXT NOT NULL,
              kind TEXT NOT NULL DEFAULT 'word',
              context TEXT NOT NULL DEFAULT '',
              source_article_id INTEGER,
              source_quiz_id INTEGER,
              status TEXT NOT NULL DEFAULT 'new',
              note TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (source_article_id) REFERENCES articles(id),
              FOREIGN KEY (source_quiz_id) REFERENCES quizzes(id)
            );

            CREATE TABLE IF NOT EXISTS quizzes (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              article_id INTEGER,
              style TEXT NOT NULL,
              mode TEXT NOT NULL,
              type TEXT NOT NULL,
              question_type TEXT NOT NULL DEFAULT '',
              skill TEXT NOT NULL DEFAULT '',
              difficulty TEXT NOT NULL DEFAULT 'B2',
              prompt TEXT NOT NULL,
              answer TEXT NOT NULL,
              options_json TEXT NOT NULL DEFAULT '[]',
              evidence TEXT NOT NULL DEFAULT '',
              note TEXT NOT NULL DEFAULT '',
              validation_json TEXT NOT NULL DEFAULT '{}',
              generation_source TEXT NOT NULL DEFAULT 'legacy',
              metadata_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL,
              FOREIGN KEY (article_id) REFERENCES articles(id)
            );

            CREATE TABLE IF NOT EXISTS attempts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              quiz_id INTEGER NOT NULL,
              session_id INTEGER,
              user_answer TEXT NOT NULL,
              confidence INTEGER,
              elapsed_seconds INTEGER NOT NULL DEFAULT 0,
              answer_changes INTEGER NOT NULL DEFAULT 0,
              hint_used INTEGER NOT NULL DEFAULT 0,
              correct INTEGER NOT NULL,
              error_type TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
            );

            CREATE TABLE IF NOT EXISTS practice_sessions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              article_id INTEGER,
              style TEXT NOT NULL DEFAULT 'IELTS',
              question_type TEXT NOT NULL DEFAULT '',
              session_mode TEXT NOT NULL DEFAULT 'practice',
              question_count INTEGER NOT NULL DEFAULT 0,
              answered_count INTEGER NOT NULL DEFAULT 0,
              correct_count INTEGER NOT NULL DEFAULT 0,
              elapsed_seconds INTEGER NOT NULL DEFAULT 0,
              score INTEGER NOT NULL DEFAULT 0,
              skill_summary_json TEXT NOT NULL DEFAULT '{}',
              error_summary_json TEXT NOT NULL DEFAULT '{}',
              confidence_summary_json TEXT NOT NULL DEFAULT '{}',
              completed_at TEXT NOT NULL,
              FOREIGN KEY (article_id) REFERENCES articles(id)
            );

            CREATE TABLE IF NOT EXISTS practice_runs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              learner_key TEXT NOT NULL DEFAULT 'local',
              practice_session_id INTEGER,
              article_id INTEGER,
              style TEXT NOT NULL DEFAULT 'IELTS',
              question_type TEXT NOT NULL DEFAULT '',
              scope TEXT NOT NULL DEFAULT 'specialty',
              session_mode TEXT NOT NULL DEFAULT 'practice',
              status TEXT NOT NULL DEFAULT 'in_progress',
              quiz_ids_json TEXT NOT NULL DEFAULT '[]',
              answers_json TEXT NOT NULL DEFAULT '{}',
              confidence_json TEXT NOT NULL DEFAULT '{}',
              flagged_json TEXT NOT NULL DEFAULT '{}',
              answer_changes_json TEXT NOT NULL DEFAULT '{}',
              hint_used_json TEXT NOT NULL DEFAULT '{}',
              feedback_json TEXT NOT NULL DEFAULT '{}',
              active_index INTEGER NOT NULL DEFAULT 0,
              display_mode TEXT NOT NULL DEFAULT 'single',
              elapsed_seconds INTEGER NOT NULL DEFAULT 0,
              started_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              completed_at TEXT NOT NULL DEFAULT '',
              FOREIGN KEY (article_id) REFERENCES articles(id),
              FOREIGN KEY (practice_session_id) REFERENCES practice_sessions(id)
            );

            CREATE TABLE IF NOT EXISTS profile_calibrations (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              period_start TEXT NOT NULL,
              period_end TEXT NOT NULL,
              trigger_type TEXT NOT NULL DEFAULT 'weekly',
              domain_summary_json TEXT NOT NULL DEFAULT '{}',
              overall_summary_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS exam_resources (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL,
              exam TEXT NOT NULL,
              year INTEGER,
              provider TEXT NOT NULL DEFAULT '',
              resource_type TEXT NOT NULL,
              source_url TEXT NOT NULL DEFAULT '',
              access_mode TEXT NOT NULL DEFAULT 'external_link',
              rights_status TEXT NOT NULL DEFAULT 'link_only',
              description TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              UNIQUE(exam, source_url)
            );

            CREATE TABLE IF NOT EXISTS exam_papers (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL,
              exam TEXT NOT NULL,
              paper_type TEXT NOT NULL DEFAULT 'simulation',
              source_class TEXT NOT NULL DEFAULT 'system_simulation',
              duration_minutes INTEGER NOT NULL DEFAULT 60,
              question_count INTEGER NOT NULL DEFAULT 0,
              provenance_note TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS exam_paper_sections (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              paper_id INTEGER NOT NULL,
              article_id INTEGER NOT NULL,
              position INTEGER NOT NULL,
              title TEXT NOT NULL DEFAULT '',
              FOREIGN KEY (paper_id) REFERENCES exam_papers(id),
              FOREIGN KEY (article_id) REFERENCES articles(id),
              UNIQUE(paper_id, position)
            );

            CREATE TABLE IF NOT EXISTS exam_paper_questions (
              paper_id INTEGER NOT NULL,
              section_id INTEGER NOT NULL,
              quiz_id INTEGER NOT NULL,
              position INTEGER NOT NULL,
              FOREIGN KEY (paper_id) REFERENCES exam_papers(id),
              FOREIGN KEY (section_id) REFERENCES exam_paper_sections(id),
              FOREIGN KEY (quiz_id) REFERENCES quizzes(id),
              PRIMARY KEY (paper_id, position)
            );

            CREATE TABLE IF NOT EXISTS mistakes (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              quiz_id INTEGER,
              prompt TEXT NOT NULL,
              answer TEXT NOT NULL,
              user_answer TEXT NOT NULL,
              evidence TEXT NOT NULL DEFAULT '',
              source TEXT NOT NULL DEFAULT 'quiz',
              skill TEXT NOT NULL DEFAULT '',
              error_type TEXT NOT NULL DEFAULT '',
              explanation_json TEXT NOT NULL DEFAULT '{}',
              remedial_attempts INTEGER NOT NULL DEFAULT 0,
              remedial_correct_streak INTEGER NOT NULL DEFAULT 0,
              mastered_at TEXT NOT NULL DEFAULT '',
              mastery_source TEXT NOT NULL DEFAULT '',
              solved INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
            );

            CREATE TABLE IF NOT EXISTS feeds (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              url TEXT NOT NULL UNIQUE,
              language TEXT NOT NULL DEFAULT 'en',
              level_hint TEXT NOT NULL DEFAULT 'B1-B2',
              active INTEGER NOT NULL DEFAULT 1,
              etag TEXT NOT NULL DEFAULT '',
              last_modified TEXT NOT NULL DEFAULT '',
              last_attempt_at TEXT NOT NULL DEFAULT '',
              last_success_at TEXT NOT NULL DEFAULT '',
              consecutive_failures INTEGER NOT NULL DEFAULT 0,
              last_error TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS feed_refresh_runs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              trigger_type TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'running',
              imported_count INTEGER NOT NULL DEFAULT 0,
              updated_count INTEGER NOT NULL DEFAULT 0,
              unchanged_count INTEGER NOT NULL DEFAULT 0,
              error_count INTEGER NOT NULL DEFAULT 0,
              started_at TEXT NOT NULL,
              completed_at TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS feed_refresh_sources (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              run_id INTEGER NOT NULL,
              feed_id INTEGER NOT NULL,
              status TEXT NOT NULL,
              http_status INTEGER NOT NULL DEFAULT 0,
              imported_count INTEGER NOT NULL DEFAULT 0,
              updated_count INTEGER NOT NULL DEFAULT 0,
              unchanged_count INTEGER NOT NULL DEFAULT 0,
              duration_ms INTEGER NOT NULL DEFAULT 0,
              error TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              FOREIGN KEY(run_id) REFERENCES feed_refresh_runs(id),
              FOREIGN KEY(feed_id) REFERENCES feeds(id)
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              target_type TEXT NOT NULL,
              target_value TEXT NOT NULL,
              active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(target_type, target_value)
            );

            CREATE TABLE IF NOT EXISTS settings (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS daily_plan_progress (
              day TEXT NOT NULL,
              task TEXT NOT NULL,
              completed_count INTEGER NOT NULL DEFAULT 0,
              updated_at TEXT NOT NULL,
              PRIMARY KEY (day, task)
            );

            CREATE TABLE IF NOT EXISTS daily_plan_items (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              day TEXT NOT NULL,
              task TEXT NOT NULL,
              item_type TEXT NOT NULL,
              item_id INTEGER NOT NULL,
              title TEXT NOT NULL DEFAULT '',
              completed INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(day, item_type, item_id)
            );

            CREATE TABLE IF NOT EXISTS progress (
              id INTEGER PRIMARY KEY CHECK (id = 1),
              xp INTEGER NOT NULL DEFAULT 0,
              correct_count INTEGER NOT NULL DEFAULT 0,
              reviewed_count INTEGER NOT NULL DEFAULT 0,
              streak INTEGER NOT NULL DEFAULT 0,
              last_study_date TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS translation_cache (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              text_hash TEXT NOT NULL,
              source_lang TEXT NOT NULL,
              target_lang TEXT NOT NULL,
              provider TEXT NOT NULL,
              source_text TEXT NOT NULL,
              translated_text TEXT NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE(text_hash, source_lang, target_lang, provider)
            );

            CREATE TABLE IF NOT EXISTS browser_clips (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              kind TEXT NOT NULL,
              source_text TEXT NOT NULL,
              translated_text TEXT NOT NULL DEFAULT '',
              context TEXT NOT NULL DEFAULT '',
              page_title TEXT NOT NULL DEFAULT '',
              page_url TEXT NOT NULL DEFAULT '',
              card_id INTEGER,
              article_id INTEGER,
              created_at TEXT NOT NULL,
              FOREIGN KEY (card_id) REFERENCES cards(id),
              FOREIGN KEY (article_id) REFERENCES articles(id)
            );

            CREATE TABLE IF NOT EXISTS dictionary_entries (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              headword TEXT NOT NULL UNIQUE,
              pos TEXT NOT NULL DEFAULT '',
              ipa_uk TEXT NOT NULL DEFAULT '',
              ipa_us TEXT NOT NULL DEFAULT '',
              core_meaning TEXT NOT NULL DEFAULT '',
              meaning_zh TEXT NOT NULL DEFAULT '',
              level TEXT NOT NULL DEFAULT '',
              register_label TEXT NOT NULL DEFAULT '',
              origin TEXT NOT NULL DEFAULT '',
              breakdown TEXT NOT NULL DEFAULT '',
              forms_json TEXT NOT NULL DEFAULT '[]',
              aliases_json TEXT NOT NULL DEFAULT '[]',
              family_json TEXT NOT NULL DEFAULT '[]',
              collocations_json TEXT NOT NULL DEFAULT '[]',
              synonyms_json TEXT NOT NULL DEFAULT '[]',
              antonyms_json TEXT NOT NULL DEFAULT '[]',
              examples_json TEXT NOT NULL DEFAULT '[]',
              morphemes_json TEXT NOT NULL DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS morphemes (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              form TEXT NOT NULL UNIQUE,
              kind TEXT NOT NULL,
              meaning_zh TEXT NOT NULL,
              origin TEXT NOT NULL DEFAULT '',
              note TEXT NOT NULL DEFAULT '',
              examples_json TEXT NOT NULL DEFAULT '[]'
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_source_url
            ON articles(source_url)
            WHERE source_url != '';
            """
        )
        ensure_wordnet_schema(conn)
        run_migrations(conn)
        conn.execute("UPDATE articles SET translation_zh = ? WHERE source = 'seed'", (SAMPLE_TRANSLATION,))
        conn.execute("UPDATE articles SET content_status = 'full' WHERE source IN ('seed', 'manual')")
        for source, (_, content_type) in SOURCE_CLASSIFICATION.items():
            conn.execute(
                "UPDATE articles SET content_type = ? WHERE source = ? AND content_type IN ('', 'auto')",
                (content_type, source),
            )
        for row in conn.execute("SELECT id, title, body FROM articles").fetchall():
            normalized = normalize_article_text(row["title"], row["body"])
            if normalized and normalized != row["body"]:
                conn.execute("UPDATE articles SET body = ? WHERE id = ?", (normalized, row["id"]))
        conn.execute("INSERT OR IGNORE INTO progress (id) VALUES (1)")
        now = utc_now()
        conn.executemany(
            """
            INSERT OR IGNORE INTO exam_resources
            (title, exam, provider, resource_type, source_url, access_mode, rights_status, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["title"], item["exam"], item["provider"], item["resource_type"],
                    item["source_url"], item["access_mode"], item["rights_status"], item["description"], now,
                )
                for item in OFFICIAL_EXAM_RESOURCES
            ],
        )
        if not conn.execute("SELECT 1 FROM settings WHERE key = 'browser_bridge_token'").fetchone():
            conn.execute("INSERT INTO settings (key, value) VALUES ('browser_bridge_token', ?)", (secrets.token_urlsafe(24),))
        conn.execute("UPDATE cards SET kind = 'phrase' WHERE instr(trim(term), ' ') > 0")
        article_count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        if article_count == 0:
            now = utc_now()
            conn.execute(
                """
                INSERT INTO articles (title, language, level, topic, source, source_url, content_type, body, created_at, updated_at)
                VALUES (?, 'en', 'B2', 'technology', 'seed', '', 'explainer', ?, ?, ?)
                """,
                (
                    "Privacy concerns in the age of smart devices",
                    normalize_article_text("Privacy concerns in the age of smart devices", SAMPLE_ARTICLE),
                    now,
                    now,
                ),
            )
        conn.execute("UPDATE articles SET translation_zh = ? WHERE source = 'seed'", (SAMPLE_TRANSLATION,))
        conn.execute("UPDATE articles SET content_status = 'full' WHERE source IN ('seed', 'manual')")
        now = utc_now()
        conn.execute(
            "UPDATE feeds SET url = ?, active = 1 WHERE name = 'Knowledge at Wharton'",
            ("https://knowledge.wharton.upenn.edu/feed",),
        )
        conn.execute("UPDATE feeds SET active = 0 WHERE name = 'BBC Learning English'")
        conn.executemany(
            """
            INSERT OR IGNORE INTO feeds (name, url, language, level_hint, active, created_at)
            VALUES (:name, :url, :language, :level_hint, 1, :created_at)
            """,
            [{**feed, "created_at": now} for feed in DEFAULT_FEEDS],
        )
        for entry in LEXICAL_SEEDS:
            conn.execute(
                """
                INSERT INTO dictionary_entries
                (headword, pos, ipa_uk, ipa_us, core_meaning, meaning_zh, level, register_label,
                 origin, breakdown, forms_json, aliases_json, family_json, collocations_json,
                 synonyms_json, antonyms_json, examples_json, morphemes_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(headword) DO UPDATE SET
                  pos = excluded.pos, ipa_uk = excluded.ipa_uk, ipa_us = excluded.ipa_us,
                  core_meaning = excluded.core_meaning, meaning_zh = excluded.meaning_zh,
                  level = excluded.level, register_label = excluded.register_label,
                  origin = excluded.origin, breakdown = excluded.breakdown,
                  forms_json = excluded.forms_json, aliases_json = excluded.aliases_json,
                  family_json = excluded.family_json, collocations_json = excluded.collocations_json,
                  synonyms_json = excluded.synonyms_json, antonyms_json = excluded.antonyms_json,
                  examples_json = excluded.examples_json, morphemes_json = excluded.morphemes_json
                """,
                (
                    entry["headword"], entry["pos"], entry["ipa_uk"], entry["ipa_us"], entry["core_meaning"],
                    entry["meaning_zh"], entry["level"], entry["register"], entry["origin"], entry["breakdown"],
                    *[json.dumps(entry[key], ensure_ascii=False) for key in
                      ("forms", "aliases", "family", "collocations", "synonyms", "antonyms", "examples", "morphemes")],
                ),
            )
        conn.executemany(
            """
            INSERT OR IGNORE INTO morphemes (form, kind, meaning_zh, origin, note, examples_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [(form, kind, meaning, origin, note, json.dumps(examples, ensure_ascii=False))
             for form, kind, meaning, origin, note, examples in MORPHEME_SEEDS],
        )
        conn.execute("DELETE FROM morphemes WHERE form = '-ion'")


def runtime_metadata() -> dict:
    payload = version_payload(ROOT)
    payload["app_version"] = PROCESS_APP_VERSION
    with db() as conn:
        row = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
    payload["database_schema_version"] = int(row[0])
    payload["compatible"] = payload["database_schema_version"] == SCHEMA_VERSION
    return payload


def json_response(handler: BaseHTTPRequestHandler, payload: object, status: int = 200) -> None:
    body = json.dumps(simplify_chinese_payload(payload), ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(length).decode("utf-8") if length else "{}"
    if not raw.strip():
        return {}
    return json.loads(raw)


def text_response(handler: BaseHTTPRequestHandler, content: bytes, content_type: str, status: int = 200, cache_control: str = "") -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    if cache_control:
        handler.send_header("Cache-Control", cache_control)
    handler.send_header("Content-Length", str(len(content)))
    handler.end_headers()
    handler.wfile.write(content)


class ReadableHTMLParser(HTMLParser):
    ignored_tags = {"script", "style", "svg", "noscript", "template"}
    block_tags = {"p", "div", "li", "blockquote", "figcaption", "h1", "h2", "h3", "h4", "section", "article"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self.current: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        if tag in self.ignored_tags:
            self.ignored_depth += 1
        elif not self.ignored_depth and tag in self.block_tags:
            self.flush()
        elif not self.ignored_depth and tag == "br":
            self.current.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in self.ignored_tags and self.ignored_depth:
            self.ignored_depth -= 1
        elif not self.ignored_depth and tag in self.block_tags:
            self.flush()

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.current.append(data)

    def flush(self) -> None:
        value = re.sub(r"\s+", " ", " ".join(self.current)).strip()
        if value and (not self.blocks or self.blocks[-1] != value):
            self.blocks.append(value)
        self.current = []

    def text(self) -> str:
        self.flush()
        return "\n\n".join(self.blocks)


EMBEDDED_SCRIPT_NOISE = re.compile(
    r"(?i)(?:\bGF_AJAX_POSTBACK\b|\bgform_confirmation_loaded\b|\bgform_pre_post_render\b|"
    r"\bgformRedirect\b|\bgform_wrapper_\d+\b|\bconfirmation_content\b|window\[['\"]gf_|jQuery\(['\"]#gform)"
)


def strip_embedded_script_noise(value: str) -> str:
    marker = EMBEDDED_SCRIPT_NOISE.search(value or "")
    return (value or "")[:marker.start()].rstrip(" \t\r\n,;:{[(") if marker else (value or "")


def clean_html(value: str) -> str:
    parser = ReadableHTMLParser()
    parser.feed(value or "")
    parser.close()
    text = strip_embedded_script_noise(parser.text())
    return re.sub(r"[ \t\r\f\v]+", " ", html.unescape(text)).strip()


def sentences(text: str) -> list[str]:
    found = re.findall(r"[^.!?]+[.!?]+", text.replace("\n", " "))
    return [item.strip() for item in found if len(item.strip()) > 18] or [text.strip()]


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*", text.lower())


def estimate_level(text: str) -> str:
    all_words = words(text)
    sents = sentences(text)
    if not all_words:
        return "A1"
    avg_sentence = len(all_words) / max(1, len(sents))
    long_ratio = len([w for w in all_words if len(w) >= 9]) / len(all_words)
    if avg_sentence > 24 or long_ratio > 0.16:
        return "C1"
    if avg_sentence > 18 or long_ratio > 0.11:
        return "B2"
    if avg_sentence > 12 or long_ratio > 0.07:
        return "B1"
    return "A2"


def article_keywords(text: str) -> list[str]:
    seen: dict[str, int] = {}
    for word in words(text):
        if len(word) < 6:
            continue
        if word in {"because", "however", "therefore", "between", "without", "should", "people"}:
            continue
        seen[word] = seen.get(word, 0) + 1
    lexicon_words = [word for word in LEXICON if re.search(rf"\b{re.escape(word)}\b", text, re.I)]
    frequent = sorted(seen, key=lambda item: (-seen[item], -len(item), item))
    return list(dict.fromkeys([*lexicon_words, *frequent]))[:12]


def score_sentence(sentence: str) -> int:
    signal_words = ["however", "therefore", "because", "central", "challenge", "critics", "supporters", "without"]
    lower = sentence.lower()
    return sum(3 for word in signal_words if word in lower) + len(article_keywords(sentence))


def focus_sentences(text: str, limit: int = 3) -> list[str]:
    ranked = sorted(sentences(text), key=score_sentence, reverse=True)
    return ranked[:limit]


def paraphrase(sentence: str) -> str:
    return (
        sentence.replace("Supporters argue that", "The text suggests that some people believe")
        .replace("However, critics point out that", "The text also notes that critics believe")
        .replace("significant benefits", "important advantages")
        .replace("privacy policies", "rules about personal data")
        .replace("The central challenge is not", "The main issue is not")
        .strip()
    )


def sentence_for(text: str, keyword: str) -> str:
    lower = keyword.lower()
    for sentence in sentences(text):
        if re.search(rf"\b{re.escape(lower)}\b", sentence, re.I):
            return sentence
    return sentences(text)[0]


def style_profile(style: str) -> dict:
    profiles = {
        "general": {
            "support_prompt": "Which option is best supported by the article?",
            "main_prompt": "What is the main focus of this part of the article?",
            "para_prompt": "Which sentence is the closest paraphrase of the evidence?",
            "support_wrong": [
                "The article makes a claim that is not supported by any evidence.",
                "The article argues the opposite of the main evidence.",
                "The article focuses only on a minor detail.",
            ],
            "main_wrong": [
                "A personal story unrelated to the article.",
                "A list of random vocabulary words.",
                "A conclusion that rejects all technology.",
            ],
            "para_wrong": [
                "The sentence removes the original condition and becomes too broad.",
                "The sentence changes the writer's attitude completely.",
                "The sentence adds a detail that the article does not mention.",
            ],
            "notes": ["阅读证据题", "主旨 / 定位", "同义改写", "选词填空 / 语境搭配", "首字母填空 / 主动回忆"],
        },
        "IELTS": {
            "support_prompt": "IELTS-style: Which statement is best supported by the passage?",
            "main_prompt": "IELTS-style: Which heading best matches this part of the passage?",
            "para_prompt": "IELTS-style: Which option best paraphrases the writer's point?",
            "support_wrong": [
                "It is NOT GIVEN because the passage does not state it.",
                "It contradicts the writer's evidence.",
                "It is a true-sounding detail but not the answer to this question.",
            ],
            "main_wrong": [
                "A narrow example rather than the paragraph's overall heading.",
                "A heading with stronger wording than the passage supports.",
                "A heading about a different stage of the argument.",
            ],
            "para_wrong": [
                "It changes the degree of certainty in the original sentence.",
                "It keeps key words but misses the real relationship.",
                "It adds a cause-and-effect link that the passage does not give.",
            ],
            "notes": ["IELTS / 证据定位", "IELTS / 段落标题", "IELTS / 同义替换", "IELTS / 搭配与替换", "IELTS / 定位词回忆"],
        },
        "TOEFL": {
            "support_prompt": "TOEFL-style: According to the passage, which statement is true?",
            "main_prompt": "TOEFL-style: What is the main idea of the paragraph?",
            "para_prompt": "TOEFL-style: Which option best expresses the essential information?",
            "support_wrong": [
                "It reverses the relationship described in the passage.",
                "It is too extreme compared with the passage.",
                "It mentions a familiar topic but is not stated in the passage.",
            ],
            "main_wrong": [
                "A detail that supports the paragraph rather than summarizes it.",
                "An idea from outside the passage.",
                "A claim that is broader than the paragraph.",
            ],
            "para_wrong": [
                "It omits a key condition from the original sentence.",
                "It changes the logical connection between the ideas.",
                "It keeps a detail but loses the main point.",
            ],
            "notes": ["TOEFL / 事实信息", "TOEFL / 主旨题", "TOEFL / 句子简化", "TOEFL / 语境词义", "TOEFL / 结构回忆"],
        },
        "CET4": {
            "support_prompt": "CET-4 style: Which statement agrees with the passage?",
            "main_prompt": "CET-4 style: Which paragraph idea best matches this information?",
            "para_prompt": "CET-4 style: Which option best restates the sentence?",
            "support_wrong": [
                "It repeats a familiar word but changes the stated fact.",
                "It turns one example into a general conclusion.",
                "It is related to the topic but is not stated in the passage.",
            ],
            "main_wrong": [
                "A minor detail rather than the paragraph's focus.",
                "An idea that appears in a different part of the passage.",
                "A broad topic label without the paragraph's key information.",
            ],
            "para_wrong": [
                "It changes the subject or object of the original sentence.",
                "It uses a near-synonym in the wrong collocation.",
                "It removes a condition and makes the claim too broad.",
            ],
            "notes": ["四级 / 仔细阅读", "四级 / 长篇匹配", "四级 / 推断判断", "四级 / 选词填空", "四级 / 词汇回忆"],
        },
        "CET6": {
            "support_prompt": "CET-6 style: Which conclusion is best supported by the passage?",
            "main_prompt": "CET-6 style: Which idea best represents the paragraph's role?",
            "para_prompt": "CET-6 style: Which option best preserves the writer's meaning?",
            "support_wrong": [
                "It extends the evidence beyond the scope of the passage.",
                "It mistakes the writer's qualification for a firm conclusion.",
                "It is plausible in general but unsupported by this passage.",
            ],
            "main_wrong": [
                "A supporting illustration rather than the central point.",
                "A related issue the paragraph does not address.",
                "A conclusion stronger than the paragraph permits.",
            ],
            "para_wrong": [
                "It keeps the topic but changes the logical relationship.",
                "It loses the writer's degree of certainty.",
                "It adds a cause that the sentence does not establish.",
            ],
            "notes": ["六级 / 深层推断", "六级 / 长篇匹配", "六级 / 同义转述", "六级 / 选词填空", "六级 / 词汇回忆"],
        },
        "KAOYAN": {
            "support_prompt": "Postgraduate entrance exam style: Which inference is most consistent with the text?",
            "main_prompt": "Postgraduate entrance exam style: What best captures the author's purpose or attitude?",
            "para_prompt": "Postgraduate entrance exam style: Which option best explains the sentence in context?",
            "support_wrong": [
                "It draws an absolute conclusion from qualified evidence.",
                "It confuses the author's report of a view with endorsement of that view.",
                "It relies on background knowledge rather than textual evidence.",
            ],
            "main_wrong": [
                "A local example that does not represent the author's purpose.",
                "A neutral description that misses the author's attitude.",
                "A position the passage presents in order to question it.",
            ],
            "para_wrong": [
                "It preserves individual words but reverses the sentence logic.",
                "It ignores a contrast or qualification in the context.",
                "It adds an evaluation that the author does not make.",
            ],
            "notes": ["考研 / 细节与推断", "考研 / 主旨与态度", "考研 / 长难句语义", "考研 / 完形逻辑", "考研 / 关键词回忆"],
        },
        "TEM4": {
            "support_prompt": "TEM4-style: Choose the statement that agrees with the passage.",
            "main_prompt": "TEM4-style: What is the paragraph mainly about?",
            "para_prompt": "TEM4-style: Which option has the closest meaning to the underlined idea?",
            "support_wrong": [
                "It contains a grammar-correct sentence but the meaning is different.",
                "It overgeneralizes one example from the passage.",
                "It confuses the subject and object of the sentence.",
            ],
            "main_wrong": ["A supporting example.", "A vocabulary item rather than an idea.", "A conclusion not reached by the passage."],
            "para_wrong": [
                "It uses a similar word with a different collocation.",
                "It changes the time or condition of the action.",
                "It sounds natural but misses the writer's attitude.",
            ],
            "notes": ["专四 / 细节理解", "专四 / 主旨概括", "专四 / 近义改写", "专四 / 词汇语法", "专四 / 词汇拼写"],
        },
        "TEM8": {
            "support_prompt": "TEM8-style: Which inference is most consistent with the passage?",
            "main_prompt": "TEM8-style: Which title best captures the argument of this paragraph?",
            "para_prompt": "TEM8-style: Which option best preserves the nuance of the original sentence?",
            "support_wrong": [
                "It is plausible but not warranted by the author's reasoning.",
                "It mistakes a qualification for the central claim.",
                "It ignores the author's contrast between two positions.",
            ],
            "main_wrong": [
                "A partial topic that misses the author's stance.",
                "A title with an unsupported evaluative claim.",
                "A title based on background rather than argument.",
            ],
            "para_wrong": [
                "It flattens the nuance of the original wording.",
                "It changes a contrast into a cause.",
                "It preserves vocabulary but not the author's logic.",
            ],
            "notes": ["专八 / 推断与态度", "专八 / 标题概括", "专八 / 长难句释义", "专八 / 语义辨析", "专八 / 高阶词汇回忆"],
        },
        "GRE": {
            "support_prompt": "GRE-style: Which choice is most strongly implied by the passage?",
            "main_prompt": "GRE-style: Which statement best describes the author's central concern?",
            "para_prompt": "GRE-style: Which choice best captures the logical function of the sentence?",
            "support_wrong": [
                "It draws a broader conclusion than the evidence permits.",
                "It mistakes correlation for causation.",
                "It is compatible with the topic but not entailed by the passage.",
            ],
            "main_wrong": [
                "A secondary illustration of the argument.",
                "A position the passage implicitly criticizes.",
                "A claim that depends on information outside the passage.",
            ],
            "para_wrong": [
                "It weakens the qualification in the original sentence.",
                "It changes the sentence from evidence into conclusion.",
                "It preserves the topic but misses the logical contrast.",
            ],
            "notes": ["GRE / 推断与逻辑", "GRE / 中心论点", "GRE / 句间逻辑", "GRE / 精确词义", "GRE / 学术词汇回忆"],
        },
        "GMAT": {
            "support_prompt": "GMAT-style: Which option is best supported by the passage's reasoning?",
            "main_prompt": "GMAT-style: What role does this part play in the argument?",
            "para_prompt": "GMAT-style: Which option best preserves the author's reasoning?",
            "support_wrong": [
                "It assumes something the passage never establishes.",
                "It weakens rather than follows from the argument.",
                "It confuses a premise with the conclusion.",
            ],
            "main_wrong": [
                "It is an irrelevant background detail.",
                "It is a conclusion stronger than the passage allows.",
                "It is an assumption rather than a stated function.",
            ],
            "para_wrong": [
                "It changes the argument's scope.",
                "It reverses the relationship between evidence and claim.",
                "It introduces a business outcome the passage does not mention.",
            ],
            "notes": ["GMAT / 论证支持", "GMAT / 论证功能", "GMAT / 推理保真", "GMAT / 商科语境搭配", "GMAT / 关键词回忆"],
        },
    }
    return profiles.get(style, profiles["general"])


def with_options(answer: str, wrong: list[str]) -> list[str]:
    options = [answer, *wrong[:3]]
    random.shuffle(options)
    return options


IELTS_TASK_META = {
    "tfng": {"skill": "证据一致、矛盾与未提及判断", "difficulty": "B2", "type": "tfng"},
    "heading": {"skill": "段落主旨与信息层级", "difficulty": "B2", "type": "heading"},
    "matching-info": {"skill": "段落定位与同义替换", "difficulty": "B2", "type": "matching-info"},
    "gap-fill": {"skill": "摘要定位、词性与字数限制", "difficulty": "B2", "type": "gap-fill"},
}


def article_paragraphs(text: str) -> list[str]:
    paragraphs = [re.sub(r"\s+", " ", value).strip() for value in re.split(r"\n\s*\n", text or "") if value.strip()]
    if len(paragraphs) >= 2:
        return paragraphs
    values = sentences(text)
    return [" ".join(values[index:index + 2]) for index in range(0, len(values), 2) if values[index:index + 2]]


def paragraph_heading(paragraph: str) -> str:
    first = sentences(paragraph)[0] if sentences(paragraph) else paragraph
    heading = re.sub(r"^(However|Therefore|Moreover|Meanwhile|In contrast|For example),?\s+", "", first, flags=re.I)
    heading = re.sub(r"[,;:].*$", "", heading).strip()
    words_in_heading = heading.split()
    return " ".join(words_in_heading[:11]) or "The paragraph's central idea"


def contradicted_statement(sentence: str) -> str:
    replacements = [
        (r"\bcannot\b", "can"), (r"\bcan\b", "cannot"),
        (r"\bshould not\b", "should"), (r"\bshould\b", "should not"),
        (r"\bwill not\b", "will"), (r"\bwill\b", "will not"),
        (r"\bdoes not\b", "does"), (r"\bdoes\b", "does not"),
        (r"\bis not\b", "is"), (r"\bis\b", "is not"),
        (r"\bare not\b", "are"), (r"\bare\b", "are not"),
    ]
    for pattern, replacement in replacements:
        changed, count = re.subn(pattern, replacement, sentence, count=1, flags=re.I)
        if count:
            return changed
    # Keep a traceable, controlled negation when the sentence has no simple modal or copular flip.
    return f"It is not the case that {sentence}"


def ielts_tfng_items(text: str) -> list[dict]:
    ranked = sorted(sentences(text), key=score_sentence, reverse=True)
    if not ranked:
        return []
    true_evidence = ranked[0]
    false_evidence = next((value for value in ranked[1:] if contradicted_statement(value) != "The passage rejects the central claim described in this sentence."), ranked[0])
    rows = [
        (paraphrase(true_evidence), "TRUE", true_evidence, "证据一致"),
        (contradicted_statement(false_evidence), "FALSE", false_evidence, "证据矛盾"),
        ("The passage states that the policy was first introduced in 2010.", "NOT GIVEN", "全文未提供该时间信息", "原文未提及"),
    ]
    return [
        {
            "type": "tfng",
            "question_type": "tfng",
            "prompt": f"Statement: {statement}\nChoose TRUE, FALSE, or NOT GIVEN.",
            "answer": answer,
            "statement": statement,
            "evidence_relation": {"TRUE": "agrees", "FALSE": "contradicts", "NOT GIVEN": "absent"}[answer],
            "options": ["TRUE", "FALSE", "NOT GIVEN"],
            "evidence": evidence,
            "note": f"IELTS / 判断题 / {reason}",
            **IELTS_TASK_META["tfng"],
        }
        for statement, answer, evidence, reason in rows
    ]


def ielts_heading_items(text: str) -> list[dict]:
    paragraphs = article_paragraphs(text)
    headings = [paragraph_heading(value) for value in paragraphs]
    distractors = ["A historical overview unrelated to the writer's argument", "A complete rejection of the topic"]
    items = []
    for index, paragraph in enumerate(paragraphs[:5]):
        answer = headings[index]
        options = list(dict.fromkeys([answer, *[value for position, value in enumerate(headings) if position != index], *distractors]))[:6]
        random.shuffle(options)
        items.append({
            "type": "heading",
            "question_type": "heading",
            "prompt": f"Choose the best heading for Paragraph {chr(65 + index)}.",
            "answer": answer,
            "options": options,
            "evidence": paragraph,
            "note": "IELTS / 段落标题匹配",
            **IELTS_TASK_META["heading"],
        })
    return items


def ielts_matching_items(text: str) -> list[dict]:
    paragraphs = article_paragraphs(text)
    options = [f"Paragraph {chr(65 + index)}" for index in range(len(paragraphs))]
    items = []
    for index, paragraph in enumerate(paragraphs[:5]):
        evidence = sorted(sentences(paragraph), key=score_sentence, reverse=True)[0] if sentences(paragraph) else paragraph
        items.append({
            "type": "matching-info",
            "question_type": "matching-info",
            "prompt": f"Which paragraph contains the following information?\n{paraphrase(evidence)}",
            "answer": options[index],
            "options": options,
            "evidence": evidence,
            "note": "IELTS / 段落信息匹配",
            **IELTS_TASK_META["matching-info"],
        })
    return items


def ielts_gap_fill_items(text: str) -> list[dict]:
    items = []
    for keyword in article_keywords(text)[:6]:
        if not re.fullmatch(r"[A-Za-z][A-Za-z'-]*", keyword):
            continue
        evidence = sentence_for(text, keyword)
        prompt_text = re.sub(rf"\b{re.escape(keyword)}\b", "_____", evidence, count=1, flags=re.I)
        if prompt_text == evidence:
            continue
        items.append({
            "type": "gap-fill",
            "question_type": "gap-fill",
            "prompt": f"Complete the summary below. Choose ONE WORD ONLY from the passage.\n{prompt_text}",
            "answer": keyword,
            "options": [],
            "evidence": evidence,
            "note": "IELTS / 摘要填空 / ONE WORD ONLY",
            **IELTS_TASK_META["gap-fill"],
        })
    return items


TOEFL_TASK_META = {
    "complete-words": {"skill": "语境拼写、词形与词汇识别", "difficulty": "B1-C1", "type": "complete-words"},
    "factual": {"skill": "事实定位与限定信息核对", "difficulty": "B2", "type": "factual"},
    "negative-factual": {"skill": "多项事实核对与未提及识别", "difficulty": "B2-C1", "type": "negative-factual"},
    "inference": {"skill": "文本推断与证据边界", "difficulty": "B2-C1", "type": "inference"},
    "rhetorical-purpose": {"skill": "句子功能与论证推进", "difficulty": "B2-C1", "type": "rhetorical-purpose"},
    "main-idea": {"skill": "段落主旨与信息层级", "difficulty": "B2", "type": "main-idea"},
    "simplification": {"skill": "核心信息与逻辑关系保真", "difficulty": "B2-C1", "type": "simplification"},
    "insertion": {"skill": "指代衔接与篇章连贯", "difficulty": "C1", "type": "insertion"},
    "prose-summary": {"skill": "跨段主旨整合与细节取舍", "difficulty": "C1", "type": "prose-summary"},
    "vocabulary": {"skill": "语境词义与近义辨析", "difficulty": "B2", "type": "vocabulary"},
}


TOEFL_COMPLETE_WORDS_STOPWORDS = {
    "about", "after", "again", "against", "because", "before", "between", "could", "every",
    "first", "however", "might", "other", "should", "their", "there", "these", "those", "through",
    "under", "which", "while", "would",
}


def mask_complete_word(word: str) -> tuple[str, str, int]:
    reveal_count = max(2, (len(word) + 1) // 2)
    prefix = word[:reveal_count]
    missing_count = len(word) - reveal_count
    return prefix + "_" * missing_count, prefix, missing_count


def toefl_complete_words_items(text: str) -> list[dict]:
    candidates = []
    seen = set()
    for sentence_index, sentence in enumerate(sentences(text), start=1):
        if sentence_index == 1:
            continue
        for match in re.finditer(r"\b[A-Za-z][A-Za-z'-]{5,13}\b", sentence):
            target = match.group(0)
            normalized = target.casefold()
            if normalized in seen or normalized in TOEFL_COMPLETE_WORDS_STOPWORDS:
                continue
            seen.add(normalized)
            candidates.append((sentence, target))
    items = []
    for evidence, target in candidates[:10]:
        masked_word, prefix, missing_count = mask_complete_word(target)
        masked_text = re.sub(rf"\b{re.escape(target)}\b", masked_word, evidence, count=1, flags=re.I)
        items.append({
            "question_type": "complete-words",
            "prompt": f"Complete the word in context. Type the whole word.\n\n{masked_text}",
            "answer": target,
            "options": [],
            "evidence": evidence,
            "target_word": target,
            "visible_prefix": prefix,
            "missing_count": missing_count,
            "masked_text": masked_text,
            "spec_basis": "ETS public 2026 task name; local evidence-validated simulation rules",
            "official_equivalence": False,
            "note": "TOEFL 2026 / Complete the Words / 单空规则模拟，不是 ETS 原题",
            **TOEFL_TASK_META["complete-words"],
        })
    return items


def toefl_content_options(answer: str, evidence: str, kind: str) -> list[str]:
    wrong = {
        "factual": [
            contradicted_statement(evidence),
            "The paragraph presents the topic but does not make this claim.",
            "The paragraph reaches a broader conclusion than the evidence supports.",
        ],
        "inference": [
            "The evidence proves an absolute conclusion with no exceptions.",
            "The writer rejects the topic entirely.",
            "The paragraph supports a cause that it never discusses.",
        ],
        "simplification": [
            "The sentence removes the original condition and changes the conclusion.",
            "The sentence reverses the relationship between the two ideas.",
            "The sentence preserves a detail but omits the essential point.",
        ],
    }[kind]
    return with_options(answer, wrong)


def toefl_factual_items(text: str) -> list[dict]:
    items = []
    for paragraph_index, paragraph in enumerate(article_paragraphs(text)[:4], start=1):
        evidence = sorted(sentences(paragraph), key=score_sentence, reverse=True)[0]
        keyword = (article_keywords(evidence) or article_keywords(paragraph) or ["the topic"])[0]
        answer = paraphrase(evidence)
        items.append({
            "question_type": "factual",
            "prompt": f"According to paragraph {paragraph_index}, what does the passage state about {keyword}?",
            "answer": answer,
            "options": toefl_content_options(answer, evidence, "factual"),
            "evidence": evidence,
            "paragraph_index": paragraph_index,
            "note": "TOEFL / 事实信息题",
            **TOEFL_TASK_META["factual"],
        })
    return items


def toefl_negative_factual_items(text: str) -> list[dict]:
    items = []
    absent_claims = [
        "The paragraph states that the issue has been completely resolved.",
        "The paragraph says that every researcher accepts the same explanation.",
        "The paragraph claims that cost is the only factor affecting the outcome.",
        "The paragraph reports that the change happened in a single day.",
    ]
    for paragraph_index, paragraph in enumerate(article_paragraphs(text)[:4], start=1):
        supported = sentences(paragraph)[:3]
        if len(supported) < 3:
            continue
        answer = next((claim for claim in absent_claims if claim.casefold() not in paragraph.casefold()), absent_claims[0])
        items.append({
            "question_type": "negative-factual",
            "prompt": f"All of the following are mentioned in paragraph {paragraph_index} EXCEPT:",
            "answer": answer,
            "options": with_options(answer, supported),
            "supported_options": supported,
            "evidence": paragraph,
            "paragraph_index": paragraph_index,
            "note": "TOEFL / 否定事实题 / 三项有据、一项未提及",
            **TOEFL_TASK_META["negative-factual"],
        })
    return items


def toefl_inference_items(text: str) -> list[dict]:
    items = []
    for paragraph_index, paragraph in enumerate(article_paragraphs(text)[:4], start=1):
        evidence = sorted(sentences(paragraph), key=score_sentence, reverse=True)[0]
        answer = paraphrase(evidence)
        items.append({
            "question_type": "inference",
            "prompt": f"What can be inferred from paragraph {paragraph_index}?",
            "answer": answer,
            "options": toefl_content_options(answer, evidence, "inference"),
            "evidence": evidence,
            "paragraph_index": paragraph_index,
            "note": "TOEFL / 推断题",
            **TOEFL_TASK_META["inference"],
        })
    return items


def rhetorical_purpose(sentence: str) -> str:
    lower = sentence.casefold()
    if re.search(r"\b(however|but|although|yet|in contrast)\b", lower):
        return "To introduce a contrast or qualification"
    if re.search(r"\b(for example|for instance|such as)\b", lower):
        return "To provide an example of the preceding idea"
    if re.search(r"\b(therefore|thus|consequently|as a result)\b", lower):
        return "To state a result or conclusion"
    if re.search(r"\b(supporters|critics|researchers|scholars)\b", lower):
        return "To present a relevant perspective in the discussion"
    return "To develop the paragraph's central idea with a key detail"


def toefl_rhetorical_purpose_items(text: str) -> list[dict]:
    distractors = [
        "To introduce a contrast or qualification",
        "To provide an example of the preceding idea",
        "To state a result or conclusion",
        "To present a relevant perspective in the discussion",
        "To develop the paragraph's central idea with a key detail",
        "To dismiss the entire topic as irrelevant",
    ]
    items = []
    for paragraph_index, paragraph in enumerate(article_paragraphs(text)[:4], start=1):
        target = max(sentences(paragraph), key=score_sentence)
        answer = rhetorical_purpose(target)
        wrong = [value for value in distractors if value != answer]
        items.append({
            "question_type": "rhetorical-purpose",
            "prompt": f"Why does the author include the highlighted sentence in paragraph {paragraph_index}?",
            "answer": answer,
            "options": with_options(answer, wrong),
            "evidence": target,
            "target_sentence": target,
            "purpose": answer,
            "paragraph_index": paragraph_index,
            "note": "TOEFL / 修辞目的题 / 句子功能",
            **TOEFL_TASK_META["rhetorical-purpose"],
        })
    return items


def toefl_main_idea_items(text: str) -> list[dict]:
    paragraphs = article_paragraphs(text)
    headings = [paragraph_heading(paragraph) for paragraph in paragraphs]
    items = []
    for index, paragraph in enumerate(paragraphs[:4]):
        answer = headings[index]
        wrong = [value for position, value in enumerate(headings) if position != index]
        wrong.extend(["A detail that the paragraph does not develop", "A conclusion broader than the passage"])
        options = list(dict.fromkeys([answer, *wrong]))[:4]
        if len(options) < 4:
            options.extend([f"An unrelated interpretation {number}" for number in range(1, 5 - len(options))])
        random.shuffle(options)
        items.append({
            "question_type": "main-idea",
            "prompt": f"What is the main idea of paragraph {index + 1}?",
            "answer": answer,
            "options": options,
            "evidence": paragraph,
            "paragraph_index": index + 1,
            "note": "TOEFL / 段落主旨题",
            **TOEFL_TASK_META["main-idea"],
        })
    return items


def toefl_simplification_items(text: str) -> list[dict]:
    items = []
    for evidence in sorted(sentences(text), key=lambda value: (-len(words(value)), -score_sentence(value))):
        answer = paraphrase(evidence)
        if answer == evidence:
            continue
        items.append({
            "question_type": "simplification",
            "prompt": "Which choice best expresses the essential information in the highlighted sentence?",
            "answer": answer,
            "options": toefl_content_options(answer, evidence, "simplification"),
            "evidence": evidence,
            "note": "TOEFL / 句子简化题",
            **TOEFL_TASK_META["simplification"],
        })
        if len(items) >= 4:
            break
    return items


def insertion_option(position: int, base_sentences: list[str]) -> str:
    if position == 0:
        return f"Before: {base_sentences[0]}"
    if position == len(base_sentences):
        return f"After: {base_sentences[-1]}"
    return f"Between: {base_sentences[position - 1]} / {base_sentences[position]}"


def toefl_insertion_items(text: str) -> list[dict]:
    items = []
    for paragraph_index, paragraph in enumerate(article_paragraphs(text)[:4], start=1):
        paragraph_sentences = sentences(paragraph)
        if len(paragraph_sentences) < 4:
            continue
        target_index = min(1, len(paragraph_sentences) - 1)
        target = paragraph_sentences[target_index]
        base = [value for index, value in enumerate(paragraph_sentences) if index != target_index]
        positions = list(range(min(4, len(base) + 1)))
        if target_index not in positions:
            positions[-1] = target_index
            positions.sort()
        answer = insertion_option(target_index, base)
        options = [insertion_option(position, base) for position in positions]
        random.shuffle(options)
        items.append({
            "question_type": "insertion",
            "prompt": f"Where would the sentence below best fit in paragraph {paragraph_index}?\n\n{target}",
            "answer": answer,
            "options": options,
            "evidence": paragraph,
            "target_sentence": target,
            "base_sentences": base,
            "insertion_position": target_index,
            "paragraph_index": paragraph_index,
            "note": "TOEFL / 句子插入题 / 连贯与衔接",
            **TOEFL_TASK_META["insertion"],
        })
    return items


def toefl_prose_summary_items(text: str) -> list[dict]:
    paragraphs = article_paragraphs(text)
    if len(paragraphs) < 2:
        return []
    covered = list(range(1, min(3, len(paragraphs)) + 1))
    ideas = [paragraph_heading(paragraphs[index - 1]) for index in covered]
    answer = "The passage connects " + "; then ".join(idea.rstrip(".") for idea in ideas) + "."
    wrong = [
        f"The passage focuses only on the minor detail that {ideas[0].lower()}.",
        "The passage argues that the topic has one simple cause and no competing concerns.",
        "The passage lists unrelated examples without developing a central relationship.",
    ]
    return [{
        "question_type": "prose-summary",
        "prompt": "Which option best summarizes the passage by preserving its major ideas?",
        "answer": answer,
        "options": with_options(answer, wrong),
        "evidence": text,
        "covered_paragraphs": covered,
        "key_ideas": ideas,
        "note": "TOEFL / 篇章总结单选基础 / 跨段覆盖；不是正式六选三",
        **TOEFL_TASK_META["prose-summary"],
    }]


def toefl_vocabulary_items(text: str) -> list[dict]:
    items = []
    for keyword in article_keywords(text):
        if keyword not in LEXICON:
            continue
        evidence = sentence_for(text, keyword)
        answer = LEXICON[keyword][0]
        distractors = [values[0] for term, values in LEXICON.items() if term != keyword and values[0] != answer]
        items.append({
            "question_type": "vocabulary",
            "prompt": f"The word “{keyword}” in the passage is closest in meaning to",
            "answer": answer,
            "options": with_options(answer, distractors[:3]),
            "evidence": evidence,
            "target_word": keyword,
            "note": "TOEFL / 语境词义题",
            **TOEFL_TASK_META["vocabulary"],
        })
        if len(items) >= 5:
            break
    return items


def validate_quiz_item(item: dict, text: str, style: str, question_type: str) -> dict:
    errors = []
    checks = {
        "has_prompt": bool(str(item.get("prompt") or "").strip()),
        "has_answer": bool(str(item.get("answer") or "").strip()),
        "has_skill": bool(str(item.get("skill") or "").strip()),
        "has_difficulty": bool(str(item.get("difficulty") or "").strip()),
    }
    for name, passed in checks.items():
        if not passed:
            errors.append(name)
    options = item.get("options") or []
    if options:
        checks["unique_options"] = len(options) == len(set(options))
        checks["answer_in_options"] = item.get("answer") in options
        if not checks["unique_options"]:
            errors.append("duplicate_options")
        if not checks["answer_in_options"]:
            errors.append("answer_not_in_options")
    evidence = str(item.get("evidence") or "")
    checks["evidence_traceable"] = item.get("answer") == "NOT GIVEN" or evidence in text
    if not checks["evidence_traceable"]:
        errors.append("evidence_not_in_source")
    if style == "IELTS" and question_type == "tfng":
        checks["tfng_format"] = options == ["TRUE", "FALSE", "NOT GIVEN"] and item.get("answer") in options
        if not checks["tfng_format"]:
            errors.append("invalid_tfng_format")
        statement = str(item.get("statement") or "")
        expected_relation = {"TRUE": "agrees", "FALSE": "contradicts", "NOT GIVEN": "absent"}.get(item.get("answer"))
        checks["evidence_relation"] = item.get("evidence_relation") == expected_relation
        if item.get("answer") == "FALSE":
            checks["controlled_contradiction"] = contradicted_statement(evidence) == statement and not statement.startswith("The passage rejects")
        elif item.get("answer") == "NOT GIVEN":
            key_markers = re.findall(r"\b(?:\d{4}|[A-Z][a-z]{3,})\b", statement)
            checks["absent_from_source"] = all(marker.casefold() not in text.casefold() for marker in key_markers)
        else:
            checks["statement_grounded"] = bool(statement) and evidence in text
        for name in ("evidence_relation", "controlled_contradiction", "absent_from_source", "statement_grounded"):
            if name in checks and not checks[name]:
                errors.append(name)
    if style == "IELTS" and question_type == "heading":
        checks["heading_option_count"] = len(options) >= 3
        if not checks["heading_option_count"]:
            errors.append("too_few_headings")
    if style == "IELTS" and question_type == "matching-info":
        checks["matching_option_count"] = len(options) >= 2
        if not checks["matching_option_count"]:
            errors.append("too_few_paragraph_options")
    if style == "IELTS" and question_type == "gap-fill":
        checks["word_limit"] = len(str(item.get("answer") or "").split()) == 1 and "ONE WORD ONLY" in item.get("prompt", "")
        if not checks["word_limit"]:
            errors.append("word_limit_violation")
    if style == "TOEFL" and question_type in TOEFL_TASK_META:
        checks["toefl_option_count"] = len(options) == (0 if question_type == "complete-words" else 4)
        if not checks["toefl_option_count"]:
            errors.append("invalid_toefl_option_count")
        if question_type == "complete-words":
            target_word = str(item.get("target_word") or "")
            prefix = str(item.get("visible_prefix") or "")
            masked_text = str(item.get("masked_text") or "")
            missing_count = item.get("missing_count")
            expected_mask, expected_prefix, expected_missing = mask_complete_word(target_word) if target_word else ("", "", 0)
            checks["complete_word_traceable"] = bool(target_word) and re.search(rf"\b{re.escape(target_word)}\b", evidence, re.I) is not None
            checks["complete_word_answer"] = str(item.get("answer") or "").casefold() == target_word.casefold()
            checks["complete_word_mask"] = (
                prefix == expected_prefix
                and missing_count == expected_missing
                and expected_mask in masked_text
                and target_word not in masked_text
            )
            for name in ("complete_word_traceable", "complete_word_answer", "complete_word_mask"):
                if not checks[name]:
                    errors.append(name)
        if item.get("paragraph_index"):
            paragraphs = article_paragraphs(text)
            index = int(item["paragraph_index"]) - 1
            checks["paragraph_reference"] = 0 <= index < len(paragraphs) and evidence in paragraphs[index]
            if not checks["paragraph_reference"]:
                errors.append("invalid_paragraph_reference")
        if question_type == "simplification":
            checks["essential_information_rewrite"] = item.get("answer") != evidence and "essential information" in item.get("prompt", "")
            if not checks["essential_information_rewrite"]:
                errors.append("invalid_simplification")
        if question_type == "vocabulary":
            target_word = str(item.get("target_word") or "")
            checks["word_in_context"] = bool(target_word) and re.search(rf"\b{re.escape(target_word)}\b", evidence, re.I) is not None
            if not checks["word_in_context"]:
                errors.append("vocabulary_target_not_in_context")
        if question_type == "negative-factual":
            supported = item.get("supported_options") or []
            checks["three_supported_options"] = len(supported) == 3 and all(value in evidence for value in supported)
            checks["except_answer_absent"] = bool(item.get("answer")) and item["answer"] not in evidence
            if not checks["three_supported_options"]:
                errors.append("invalid_supported_options")
            if not checks["except_answer_absent"]:
                errors.append("except_answer_is_mentioned")
        if question_type == "rhetorical-purpose":
            target_sentence = str(item.get("target_sentence") or "")
            checks["purpose_target_traceable"] = bool(target_sentence) and target_sentence == evidence
            checks["purpose_matches_function"] = item.get("answer") == rhetorical_purpose(target_sentence)
            if not checks["purpose_target_traceable"]:
                errors.append("invalid_rhetorical_target")
            if not checks["purpose_matches_function"]:
                errors.append("invalid_rhetorical_purpose")
        if question_type == "insertion":
            target_sentence = str(item.get("target_sentence") or "")
            base_sentences = item.get("base_sentences") or []
            position = item.get("insertion_position")
            reconstructed = list(base_sentences)
            valid_position = isinstance(position, int) and 0 <= position <= len(base_sentences)
            if valid_position:
                reconstructed.insert(position, target_sentence)
            checks["insertion_target_traceable"] = target_sentence in evidence
            checks["insertion_reconstructs_paragraph"] = valid_position and reconstructed == sentences(evidence)
            checks["insertion_answer_matches_position"] = valid_position and item.get("answer") == insertion_option(position, base_sentences)
            for name in ("insertion_target_traceable", "insertion_reconstructs_paragraph", "insertion_answer_matches_position"):
                if not checks[name]:
                    errors.append(name)
        if question_type == "prose-summary":
            covered = item.get("covered_paragraphs") or []
            ideas = item.get("key_ideas") or []
            paragraphs = article_paragraphs(text)
            checks["summary_cross_paragraph"] = len(covered) >= 2 and len(covered) == len(ideas)
            checks["summary_ideas_traceable"] = checks["summary_cross_paragraph"] and all(
                1 <= index <= len(paragraphs) and idea == paragraph_heading(paragraphs[index - 1])
                for index, idea in zip(covered, ideas)
            )
            checks["summary_answer_covers_ideas"] = all(idea in str(item.get("answer") or "") for idea in ideas)
            for name in ("summary_cross_paragraph", "summary_ideas_traceable", "summary_answer_covers_ideas"):
                if not checks[name]:
                    errors.append(name)
    return {"valid": not errors, "errors": errors, "checks": checks, "validator": "rule-v1"}


def ielts_quiz_items(text: str, question_type: str) -> list[dict]:
    builders = {
        "tfng": ielts_tfng_items,
        "heading": ielts_heading_items,
        "matching-info": ielts_matching_items,
        "gap-fill": ielts_gap_fill_items,
    }
    if question_type in {"mixed", "passage"}:
        items = []
        for builder in (ielts_tfng_items, ielts_heading_items, ielts_matching_items, ielts_gap_fill_items):
            items.extend(builder(text))
        validated = []
        for item in items:
            item["validation"] = validate_quiz_item(item, text, "IELTS", item["question_type"])
            item["generation_source"] = "ielts-rule-v1"
            if item["validation"]["valid"]:
                validated.append(item)
        return validated
    builder = builders.get(question_type or "tfng", ielts_tfng_items)
    items = builder(text)
    validated = []
    for item in items:
        item["validation"] = validate_quiz_item(item, text, "IELTS", item["question_type"])
        item["generation_source"] = "ielts-rule-v1"
        if item["validation"]["valid"]:
            validated.append(item)
    return validated


def toefl_quiz_items(text: str, question_type: str) -> list[dict]:
    builders = {
        "complete-words": toefl_complete_words_items,
        "factual": toefl_factual_items,
        "negative-factual": toefl_negative_factual_items,
        "inference": toefl_inference_items,
        "rhetorical-purpose": toefl_rhetorical_purpose_items,
        "main-idea": toefl_main_idea_items,
        "simplification": toefl_simplification_items,
        "insertion": toefl_insertion_items,
        "prose-summary": toefl_prose_summary_items,
        "vocabulary": toefl_vocabulary_items,
    }
    if question_type in {"mixed", "passage"}:
        items = []
        for builder in builders.values():
            items.extend(builder(text))
    else:
        items = builders.get(question_type or "factual", toefl_factual_items)(text)
    validated = []
    for item in items:
        item["validation"] = validate_quiz_item(item, text, "TOEFL", item["question_type"])
        item["generation_source"] = "toefl-2026-sim-v1" if item["question_type"] == "complete-words" else "toefl-rule-v2"
        if item["validation"]["valid"]:
            validated.append(item)
    return validated


def save_quiz_item(
    conn: sqlite3.Connection,
    article_id: int,
    style: str,
    mode: str,
    item: dict,
    created_at: str,
) -> dict:
    standard_keys = {
        "type", "question_type", "skill", "difficulty", "prompt", "answer", "options",
        "evidence", "note", "validation", "generation_source",
    }
    metadata = {key: value for key, value in item.items() if key not in standard_keys}
    cursor = conn.execute(
        """
        INSERT INTO quizzes
        (article_id, style, mode, type, question_type, skill, difficulty,
         prompt, answer, options_json, evidence, note, validation_json, generation_source, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            article_id, style, mode, item["type"], item.get("question_type") or item["type"],
            item.get("skill") or "阅读理解", item.get("difficulty") or "B2", item["prompt"],
            item["answer"], json.dumps(item.get("options") or [], ensure_ascii=False),
            item.get("evidence") or "", item.get("note") or "",
            json.dumps(item.get("validation") or {}, ensure_ascii=False),
            item.get("generation_source") or "general-rule-v1",
            json.dumps(metadata, ensure_ascii=False), created_at,
        ),
    )
    return {**item, "id": cursor.lastrowid, "article_id": article_id, "style": style, "mode": mode}


def quiz_payload(row: sqlite3.Row | dict) -> dict:
    item = dict(row)
    item["options"] = json.loads(item.pop("options_json", "[]") or "[]")
    item["validation"] = json.loads(item.pop("validation_json", "{}") or "{}")
    metadata = json.loads(item.pop("metadata_json", "{}") or "{}")
    item["metadata"] = metadata
    for key, value in metadata.items():
        item.setdefault(key, value)
    return item


IELTS_MOCK_SECTION_SPECS = [
    [("tfng", 3), ("heading", 5), ("matching-info", 5)],
    [("tfng", 3), ("heading", 5), ("gap-fill", 5)],
    [("tfng", 3), ("heading", 5), ("matching-info", 5), ("gap-fill", 1)],
]


def ielts_mock_section_items(text: str, spec: list[tuple[str, int]]) -> list[dict]:
    selected = []
    for question_type, count in spec:
        candidates = ielts_quiz_items(text, question_type)
        if len(candidates) < count:
            return []
        selected.extend(candidates[:count])
    return selected


def create_ielts_mock_paper(conn: sqlite3.Connection) -> dict:
    candidates = conn.execute(
        """
        SELECT * FROM articles
        WHERE content_status = 'full' AND language = 'en'
        ORDER BY length(body) DESC, updated_at DESC
        """
    ).fetchall()
    chosen: list[tuple[sqlite3.Row, list[dict]]] = []
    used: set[int] = set()
    for spec in IELTS_MOCK_SECTION_SPECS:
        match = None
        for article in candidates:
            if article["id"] in used:
                continue
            items = ielts_mock_section_items(article["body"], spec)
            if items:
                match = (article, items)
                break
        if not match:
            raise ValueError("需要至少 3 篇段落完整、可生成 13-14 道有效题目的英文全文")
        chosen.append(match)
        used.add(match[0]["id"])

    now = utc_now()
    cursor = conn.execute(
        """
        INSERT INTO exam_papers
        (title, exam, paper_type, source_class, duration_minutes, question_count, provenance_note, created_at)
        VALUES (?, 'IELTS', 'full_mock', 'system_simulation', 60, 40, ?, ?)
        """,
        (
            f"IELTS Reading 模拟套题 {now[:10]}",
            "由本地文章和经规则校验的 IELTS 专项模板生成；不是官方真题。",
            now,
        ),
    )
    paper_id = cursor.lastrowid
    question_position = 1
    for section_position, (article, items) in enumerate(chosen, start=1):
        section_cursor = conn.execute(
            """INSERT INTO exam_paper_sections (paper_id, article_id, position, title)
               VALUES (?, ?, ?, ?)""",
            (paper_id, article["id"], section_position, f"Passage {section_position}: {article['title']}"),
        )
        section_id = section_cursor.lastrowid
        for item in items:
            saved = save_quiz_item(conn, article["id"], "IELTS", "full-paper", item, now)
            conn.execute(
                """INSERT INTO exam_paper_questions (paper_id, section_id, quiz_id, position)
                   VALUES (?, ?, ?, ?)""",
                (paper_id, section_id, saved["id"], question_position),
            )
            question_position += 1
    paper = conn.execute("SELECT * FROM exam_papers WHERE id = ?", (paper_id,)).fetchone()
    return dict(paper)


def exam_paper_detail(conn: sqlite3.Connection, paper_id: int) -> dict | None:
    paper = conn.execute("SELECT * FROM exam_papers WHERE id = ?", (paper_id,)).fetchone()
    if not paper:
        return None
    sections = []
    rows = conn.execute(
        """
        SELECT s.id AS paper_section_id, s.position AS paper_section_position,
               s.title AS paper_section_title,
               a.id AS article_id, a.title AS article_title, a.language, a.level, a.topic,
               a.source, a.source_url, a.content_status, a.content_type, a.body,
               a.translation_zh, a.created_at, a.updated_at
        FROM exam_paper_sections s
        JOIN articles a ON a.id = s.article_id
        WHERE s.paper_id = ? ORDER BY s.position
        """,
        (paper_id,),
    ).fetchall()
    for row in rows:
        article = dict(row)
        section_id = article.pop("paper_section_id")
        section_position = article.pop("paper_section_position")
        section_title = article.pop("paper_section_title")
        article["id"] = article.pop("article_id")
        article["title"] = article.pop("article_title")
        question_rows = conn.execute(
            """
            SELECT q.*, pq.position AS paper_position
            FROM exam_paper_questions pq
            JOIN quizzes q ON q.id = pq.quiz_id
            WHERE pq.paper_id = ? AND pq.section_id = ? ORDER BY pq.position
            """,
            (paper_id, section_id),
        ).fetchall()
        sections.append({
            "id": section_id,
            "position": section_position,
            "title": section_title,
            "article": enrich_article(article, "IELTS"),
            "quizzes": [quiz_payload(question) for question in question_rows],
        })
    return {**dict(paper), "sections": sections}


KAOYAN_TASK_META = {
    "detail-inference": {"skill": "细节定位、范围控制与合理推断", "difficulty": "C1"},
    "main-attitude": {"skill": "主旨、篇章功能与作者态度", "difficulty": "C1"},
    "sentence-meaning": {"skill": "长难句主干、逻辑与语义保真", "difficulty": "C1"},
    "cloze-logic": {"skill": "完形语境、搭配与篇章逻辑", "difficulty": "B2-C1"},
}


def kaoyan_detail_items(text: str) -> list[dict]:
    ranked = sorted(sentences(text), key=score_sentence, reverse=True)[:3]
    return [
        {
            "type": "reading",
            "question_type": "detail-inference",
            "prompt": "According to the text, which of the following can be inferred?",
            "answer": paraphrase(evidence),
            "options": with_options(paraphrase(evidence), [
                "The evidence supports an absolute conclusion without qualification.",
                "The author accepts a position that the text merely reports.",
                "Background knowledge alone is sufficient to establish the claim.",
            ]),
            "evidence": evidence,
            "note": "考研英语 / 阅读 Part A / 细节与推断",
            **KAOYAN_TASK_META["detail-inference"],
        }
        for evidence in ranked
    ]


def kaoyan_main_attitude_items(text: str) -> list[dict]:
    lower = text.casefold()
    if any(marker in lower for marker in ("however", "although", "but ", "yet ")):
        answer = "The author offers a qualified assessment rather than an absolute judgment."
    elif any(marker in lower for marker in ("should", "must", "need to", "ought to")):
        answer = "The author argues for a measured change supported by the evidence."
    else:
        answer = "The author examines the issue in an analytical and generally cautious manner."
    evidence = sorted(sentences(text), key=score_sentence, reverse=True)[0] if sentences(text) else text
    return [{
        "type": "main-idea",
        "question_type": "main-attitude",
        "prompt": "Which of the following best describes the author's main purpose and attitude?",
        "answer": answer,
        "options": with_options(answer, [
            "To reject the subject entirely in an emotional and hostile tone.",
            "To list an isolated example without advancing a broader point.",
            "To endorse every view mentioned in the text without reservation.",
        ]),
        "evidence": evidence,
        "note": "考研英语 / 阅读 Part A / 主旨与作者态度",
        **KAOYAN_TASK_META["main-attitude"],
    }]


def kaoyan_sentence_meaning_items(text: str) -> list[dict]:
    candidates = sorted(sentences(text), key=lambda value: (len(value.split()), score_sentence(value)), reverse=True)[:2]
    return [
        {
            "type": "paraphrase",
            "question_type": "sentence-meaning",
            "prompt": f"What does the following sentence most probably mean?\n{evidence}",
            "answer": paraphrase(evidence),
            "options": with_options(paraphrase(evidence), [
                "The sentence removes its original condition and makes an unlimited claim.",
                "The sentence reverses the contrast or causal direction in the original.",
                "The sentence adds an evaluation that the author does not express.",
            ]),
            "evidence": evidence,
            "note": "考研英语 / 长难句语义 / 逻辑保真",
            **KAOYAN_TASK_META["sentence-meaning"],
        }
        for evidence in candidates
    ]


def kaoyan_cloze_items(text: str) -> list[dict]:
    items = []
    for keyword in article_keywords(text)[:6]:
        evidence = sentence_for(text, keyword)
        prompt = re.sub(rf"\b{re.escape(keyword)}\b", "_____", evidence, count=1, flags=re.I)
        if prompt == evidence:
            continue
        distractors = [word for word in article_keywords(text) if word != keyword]
        items.append({
            "type": "cloze",
            "question_type": "cloze-logic",
            "prompt": f"Choose the best word for the blank in context.\n{prompt}",
            "answer": keyword,
            "options": with_options(keyword, distractors[:3] or ["however", "therefore", "otherwise"]),
            "evidence": evidence,
            "note": "考研英语 / 完形填空 / 语境与篇章逻辑",
            **KAOYAN_TASK_META["cloze-logic"],
        })
    return items


def kaoyan_quiz_items(text: str, question_type: str) -> list[dict]:
    builders = {
        "detail-inference": kaoyan_detail_items,
        "main-attitude": kaoyan_main_attitude_items,
        "sentence-meaning": kaoyan_sentence_meaning_items,
        "cloze-logic": kaoyan_cloze_items,
    }
    if question_type in {"mixed", "passage"}:
        items = [item for builder in builders.values() for item in builder(text)]
    else:
        items = builders.get(question_type or "detail-inference", kaoyan_detail_items)(text)
    validated = []
    for item in items:
        item["validation"] = validate_quiz_item(item, text, "KAOYAN", item["question_type"])
        item["generation_source"] = "kaoyan-rule-v1"
        if item["validation"]["valid"]:
            validated.append(item)
    return validated


def generate_quiz_items(text: str, mode: str, style: str, question_type: str = "") -> list[dict]:
    if style == "IELTS":
        return ielts_quiz_items(text, question_type or "tfng")
    if style == "TOEFL":
        return toefl_quiz_items(text, question_type or "factual")
    if style == "KAOYAN":
        return kaoyan_quiz_items(text, question_type or "detail-inference")
    profile = style_profile(style)
    configured = next((item for item in EXAM_QUESTION_TYPES.get(style, EXAM_QUESTION_TYPES["general"]) if item[0] == question_type), None)
    if configured:
        engine_type = configured[2]
        mode = engine_type if engine_type == "cloze" else "reading"
    sents = sentences(text)
    ranked = sorted(sents, key=score_sentence, reverse=True)
    evidence = ranked[0] if ranked else ""
    second = ranked[1] if len(ranked) > 1 else evidence
    first = sents[0] if sents else ""
    title_idea = re.sub(r"[,;:].*$", "", first).strip() or "The central issue discussed in the article."
    items: list[dict] = []
    if mode in {"mixed", "reading"}:
        items.extend(
            [
                {
                    "type": "reading",
                    "prompt": profile["support_prompt"],
                    "answer": paraphrase(evidence),
                    "options": with_options(paraphrase(evidence), profile["support_wrong"]),
                    "evidence": evidence,
                    "note": profile["notes"][0],
                },
                {
                    "type": "main-idea",
                    "prompt": profile["main_prompt"],
                    "answer": title_idea,
                    "options": with_options(title_idea, profile["main_wrong"]),
                    "evidence": first,
                    "note": profile["notes"][1],
                },
                {
                    "type": "paraphrase",
                    "prompt": profile["para_prompt"],
                    "answer": paraphrase(second),
                    "options": with_options(paraphrase(second), profile["para_wrong"]),
                    "evidence": second,
                    "note": profile["notes"][2],
                },
            ]
        )
    if mode in {"mixed", "cloze"}:
        for keyword in article_keywords(text)[:7]:
            context = sentence_for(text, keyword)
            prompt = re.sub(rf"\b{re.escape(keyword)}\b", "_____", context, flags=re.I)
            if prompt == context:
                continue
            distractors = [word for word in LEXICON if word != keyword][:]
            random.shuffle(distractors)
            items.append(
                {
                    "type": "cloze",
                    "prompt": prompt,
                    "answer": keyword,
                    "options": with_options(keyword, distractors[:3]),
                    "evidence": context,
                    "note": profile["notes"][3],
                }
            )
    if question_type:
        if configured:
            _, label, engine_type = configured
            items = [item for item in items if item["type"] == engine_type]
            for item in items:
                item["note"] = f"{style} / {label}"
    generic_skills = {
        "reading": "证据定位与同义替换",
        "main-idea": "主旨概括与信息层级",
        "paraphrase": "句意改写与逻辑保真",
        "cloze": "语境词义、词性与搭配",
    }
    validated = []
    for item in items:
        item["question_type"] = question_type or item["type"]
        item["skill"] = generic_skills.get(item["type"], "阅读理解")
        item["difficulty"] = "B2"
        item["generation_source"] = "general-rule-v1"
        item["validation"] = validate_quiz_item(item, text, style, item["question_type"])
        if item["validation"]["valid"]:
            validated.append(item)
    return validated


def explain_mistake(quiz: sqlite3.Row | dict, user_answer: str) -> dict:
    quiz_type = quiz.get("quiz_type") or quiz.get("type") or "reading"
    question_type = quiz.get("question_type") or quiz_type
    style = quiz.get("style") or "general"
    answer = str(quiz.get("answer") or "").strip()
    selected = str(user_answer or "").strip()
    evidence = str(quiz.get("evidence") or "").strip()
    note = str(quiz.get("quiz_note") or quiz.get("note") or "").strip()

    type_guides = {
        "reading": {
            "point": "证据定位与同义替换",
            "correct": "正确选项与证据句表达同一个事实关系。关键词可以变化，但主体、动作、范围和语气强度必须一致。",
            "method": ["圈出题干中的主体和限定词", "回原文定位同义表达", "逐项检查是否偷换范围、方向或因果"],
        },
        "main-idea": {
            "point": "主旨概括与信息层级",
            "correct": "正确答案覆盖这一部分的核心对象和主要观点，不会只抓一个例子，也不会把结论扩大到原文之外。",
            "method": ["先概括每句在做什么", "区分中心观点和支持细节", "选择覆盖全文且措辞不过强的选项"],
        },
        "paraphrase": {
            "point": "句意改写与逻辑保真",
            "correct": "正确改写保留了原句的逻辑关系、条件和态度，只替换表达方式，没有增加或删掉关键含义。",
            "method": ["先拆出原句主干", "标记转折、因果和条件", "检查改写是否改变确定程度或逻辑方向"],
        },
        "cloze": {
            "point": "语境词义、词性与搭配",
            "correct": f"把 {answer} 放回空格后，词义、词性和上下文搭配能够同时成立。选词填空不能只看中文近义，还要看句法位置和固定搭配。",
            "method": ["先判断空格需要的词性", "读取空格前后的搭配", "最后用整句含义排除近义干扰词"],
        },
        "tfng": {
            "point": "证据一致、矛盾与未提及判断",
            "correct": "TRUE 必须与原文一致，FALSE 必须被原文明确信息反驳，NOT GIVEN 表示原文没有足够信息判断，三者不能凭常识互换。",
            "method": ["拆出题干中的主体、动作和限定词", "定位原文同义表达", "分别判断一致、矛盾还是信息缺失"],
        },
        "heading": {
            "point": "段落主旨与信息层级",
            "correct": "标题需要覆盖整段的主要功能，不能只复述一个例子，也不能加入段落没有表达的评价。",
            "method": ["概括每句功能", "找重复对象与作者推进方向", "用整段覆盖度排除局部标题"],
        },
        "matching-info": {
            "point": "段落定位与同义替换",
            "correct": "匹配依据是信息关系而非重复词。正确段落必须包含题干所述的完整事实或观点。",
            "method": ["圈出题干中的不可替代信息", "预判同义替换", "逐段核对主体、动作和限定条件"],
        },
        "gap-fill": {
            "point": "摘要定位、词性与字数限制",
            "correct": f"答案 {answer} 直接来自原文，并同时满足句意、词性和 ONE WORD ONLY 的字数限制。",
            "method": ["先判断空格词性", "定位摘要的同义句", "从原文抄取并检查字数与拼写"],
        },
        "factual": {
            "point": "事实定位与限定信息核对",
            "correct": "正确选项完整保留证据中的主体、动作、范围和限定条件，不会因为复现原词就偷换事实。",
            "method": ["用题干对象定位对应段落", "圈出数字、程度和否定等限定词", "逐项核对主体、动作和范围"],
        },
        "complete-words": {
            "point": "语境拼写、词形与词汇识别",
            "correct": f"完整单词 {answer} 同时符合已给字母、缺失长度、句法位置和上下文含义。这里只认完整单词，不接受只填写缺失字母。",
            "method": ["先读完整句判断词性和含义", "用已给前缀缩小候选范围", "输入完整单词并检查词形与拼写"],
        },
        "negative-factual": {
            "point": "多项事实核对与未提及识别",
            "correct": "否定事实题的正确选项是段落没有提到的一项；其余三项都必须能回到明确原文，而不是判断哪项看起来最不合理。",
            "method": ["先圈出题干中的 EXCEPT", "为每个选项逐一定位证据", "选择唯一无法建立原文对应的一项"],
        },
        "inference": {
            "point": "文本推断与证据边界",
            "correct": "正确推断可以由原文信息合理推出，但不会加入新的原因、绝对结论或作者没有表达的态度。",
            "method": ["先写出原文明示事实", "判断选项是否只前进一步", "排除依赖常识或扩大范围的结论"],
        },
        "rhetorical-purpose": {
            "point": "句子功能与论证推进",
            "correct": "正确答案说明目标句在段落中做什么，例如举例、转折、呈现观点或得出结果，而不是只复述句子内容。",
            "method": ["先概括目标句内容", "观察前后句和连接词", "把内容改写成功能动词后选择答案"],
        },
        "simplification": {
            "point": "核心信息与逻辑关系保真",
            "correct": "正确改写保留原句的核心主干和因果、转折、条件关系，可以删除次要细节，但不能改变逻辑方向。",
            "method": ["拆出主句与从句", "标记因果、转折和条件", "检查改写是否遗漏必要信息或改变关系"],
        },
        "insertion": {
            "point": "指代衔接与篇章连贯",
            "correct": "正确位置能让目标句的指代对象、逻辑连接和已知信息自然承接前文，并为后文继续展开提供明确对象。",
            "method": ["圈出代词和连接词", "判断目标句需要什么前置信息", "把句子放入每个位置后检查前后衔接"],
        },
        "prose-summary": {
            "point": "跨段主旨整合与细节取舍",
            "correct": "正确总结覆盖文章多个主要段落及其关系，保留中心推进，同时排除只覆盖一个例子、措辞过强或没有中心关系的选项。",
            "method": ["每段各写一句主旨", "合并重复对象并标出段落关系", "排除局部细节和超出原文的结论"],
        },
        "vocabulary": {
            "point": "语境词义与近义辨析",
            "correct": "正确词义能够放回当前句子并保持语义和语域成立，而不是选择这个词在其他场景中的常见译法。",
            "method": ["先遮住目标词读完整句", "判断目标词在句中的词性和语义角色", "把选项逐一代回原句"],
        },
    }
    guide = type_guides.get(question_type, type_guides.get(quiz_type, type_guides["reading"]))

    lower = selected.lower()
    if not selected:
        trap = "未作答"
        why_wrong = "这次没有形成可比较的答案。先写出一个候选，再用证据排除，训练效果会比直接跳过更好。"
    elif quiz_type in {"cloze", "gap-fill"}:
        trap = "词义或词形未同时满足"
        why_wrong = f"{selected} 放回原句后，至少有一项不匹配：语境含义、词性、固定搭配或拼写。正确答案是 {answer}。"
    elif any(word in lower for word in ["not given", "not stated", "does not mention", "outside"]):
        trap = "无中生有"
        why_wrong = "这个选项听起来合理，但原文没有提供足够证据。考试只认文章能支持的内容，不认常识推测。"
    elif any(word in lower for word in ["opposite", "reverse", "contradict", "reject"]):
        trap = "方向颠倒"
        why_wrong = "这个选项保留了原文主题词，却把态度、因果或论证方向反过来了。"
    elif any(word in lower for word in ["only", "all", "never", "extreme", "broader", "stronger"]):
        trap = "范围扩大或措辞过强"
        why_wrong = "这个选项把原文有限、带条件的表达改成绝对结论，范围或确定程度超过了证据。"
    elif any(word in lower for word in ["detail", "example", "minor", "narrow", "partial"]):
        trap = "用细节冒充主旨"
        why_wrong = "这个选项可能对应原文中的一个细节，但覆盖不了题目要求的中心观点或完整关系。"
    else:
        trap = "语义相近但逻辑不等价"
        why_wrong = "你的答案与原文主题相关，但没有完整保留证据中的主体、范围、条件或逻辑关系。相似词不等于同义答案。"

    raw_options = quiz.get("options")
    if raw_options is None:
        try:
            raw_options = json.loads(quiz.get("options_json") or "[]")
        except (TypeError, json.JSONDecodeError):
            raw_options = []
    options = [str(option) for option in raw_options or []]
    generic_distractor = {
        "tfng": "判断题不能凭语感选择；必须分别证明一致、矛盾或信息不足。",
        "heading": "该选项可能碰到段落局部词汇，但需要检查能否覆盖整段功能。",
        "matching-info": "出现相同单词不等于信息关系一致，主体、动作和限定条件必须同时对应。",
        "gap-fill": "代回原句后至少需要重新核对词性、原文形式和字数限制。",
        "main-idea": "该选项可能只覆盖局部细节，或把结论扩大到了全文之外。",
        "inference": "该选项需要额外常识或多走了一步，超出了原文可支持的推断距离。",
        "negative-factual": "EXCEPT 题必须为其余选项分别找到证据，不能只挑最陌生的一项。",
        "simplification": "该改写需要检查是否丢失主干，或改变因果、转折、条件关系。",
        "vocabulary": "该词义可能在其他语境成立，但需要代回当前句核对词性、语义和语域。",
    }.get(question_type, "该选项与主题有关，但需要逐项核对主体、范围、条件和逻辑方向。")
    option_analysis = []
    for option in options:
        if option.casefold() == answer.casefold():
            option_analysis.append({"option": option, "status": "correct", "reason": guide["correct"]})
        elif option.casefold() == selected.casefold():
            option_analysis.append({"option": option, "status": "selected-wrong", "reason": why_wrong})
        else:
            reason = generic_distractor
            if re.search(r"\b(all|only|always|never|entirely|must)\b", option, re.I):
                reason = "该选项含有绝对化或范围强化表达，需要原文提供同等强度的明确证据。"
            option_analysis.append({"option": option, "status": "distractor", "reason": reason})

    stop_words = {"that", "this", "with", "from", "which", "their", "there", "about", "what", "when", "where", "have", "does", "were", "been", "into"}
    prompt_terms = [word.lower() for word in re.findall(r"[A-Za-z]{4,}", str(quiz.get("prompt") or "")) if word.lower() not in stop_words]
    evidence_terms = {word.lower() for word in re.findall(r"[A-Za-z]{4,}", evidence) if word.lower() not in stop_words}
    shared_terms = list(dict.fromkeys(word for word in prompt_terms if word in evidence_terms))[:5]
    location_signals = {
        "shared_terms": shared_terms,
        "locator": "、".join(shared_terms) if shared_terms else "题干与证据未直接复现明显关键词，需要按主体和关系定位。",
        "paraphrase_check": guide["point"],
    }

    return {
        "style": style,
        "question_type": question_type,
        "skill": quiz.get("skill") or guide["point"],
        "error_type": classify_answer_error(quiz, selected),
        "test_point": note or guide["point"],
        "trap": trap,
        "why_wrong": why_wrong,
        "why_correct": guide["correct"],
        "evidence_guide": "先在证据句中确认谁做什么，再核对否定、转折、因果、程度词和范围词。正确答案必须能逐项对应。",
        "steps": guide["method"],
        "retry": f"遮住答案，把“{answer}”换成自己的话复述一次，再重新作答。",
        "evidence": evidence,
        "option_analysis": option_analysis,
        "location_signals": location_signals,
    }


def classify_answer_error(quiz: sqlite3.Row | dict, selected: str) -> str:
    question_type = str(quiz.get("question_type") or quiz.get("type") or "reading")
    answer = str(quiz.get("answer") or "").strip().upper()
    choice = str(selected or "").strip().upper()
    if not choice:
        return "未作答"
    if question_type == "tfng":
        if {answer, choice} == {"FALSE", "NOT GIVEN"}:
            return "矛盾与未提及混淆"
        if {answer, choice} == {"TRUE", "NOT GIVEN"}:
            return "一致与未提及混淆"
        return "证据方向判断错误"
    if question_type == "heading":
        return "主旨与细节混淆"
    if question_type == "matching-info":
        return "段落定位或同义替换错误"
    if question_type == "gap-fill":
        return "词性、拼写或字数限制错误"
    if question_type == "factual":
        return "事实定位或限定范围错误"
    if question_type == "complete-words":
        target = str(quiz.get("answer") or "").casefold()
        attempt = str(selected or "").casefold()
        if attempt and target.startswith(attempt):
            return "只填写了已知部分或单词未补完整"
        if attempt and abs(len(attempt) - len(target)) <= 2:
            return "拼写或词形错误"
        return "语境词义判断错误"
    if question_type == "negative-factual":
        return "EXCEPT 方向或多项证据核对错误"
    if question_type == "inference":
        return "推断距离过远或证据范围扩大"
    if question_type == "rhetorical-purpose":
        return "句子内容与修辞功能混淆"
    if question_type == "main-idea":
        return "主旨与细节混淆"
    if question_type == "simplification":
        return "关键信息遗漏或逻辑关系改变"
    if question_type == "insertion":
        return "指代或篇章衔接判断错误"
    if question_type == "prose-summary":
        return "主旨覆盖不足或细节权重错误"
    if question_type == "vocabulary":
        return "语境词义判断错误"
    if question_type == "detail-inference":
        return "证据范围扩大或推断过度"
    if question_type == "main-attitude":
        return "主旨、观点转述与作者态度混淆"
    if question_type == "sentence-meaning":
        return "长难句主干或逻辑关系判断错误"
    if question_type == "cloze-logic":
        return "词义、搭配或篇章逻辑错误"
    return "语义或逻辑关系错误"


def generate_similar_items(text: str, original: dict, count: int = 3) -> list[dict]:
    quiz_type = original.get("type") or original.get("quiz_type") or "reading"
    style = original.get("style") or "IELTS"
    question_type = original.get("question_type") or quiz_type
    if style == "IELTS" and question_type in IELTS_TASK_META:
        candidates = ielts_quiz_items(text, question_type)
        distinct = [item for item in candidates if item.get("evidence") != original.get("evidence")]
        return (distinct or candidates)[:count]
    if style == "TOEFL" and question_type in TOEFL_TASK_META:
        candidates = toefl_quiz_items(text, question_type)
        distinct = [item for item in candidates if item.get("evidence") != original.get("evidence")]
        return (distinct or candidates)[:count]
    if style == "KAOYAN" and question_type in KAOYAN_TASK_META:
        candidates = kaoyan_quiz_items(text, question_type)
        distinct = [item for item in candidates if item.get("evidence") != original.get("evidence")]
        return (distinct or candidates)[:count]
    original_answer = str(original.get("answer") or "").lower()
    profile = style_profile(style)
    sents = [sentence for sentence in sentences(text) if sentence != original.get("evidence")]
    if not sents:
        sents = sentences(text)
    items: list[dict] = []

    if quiz_type == "reading":
        for sentence in sents[:count]:
            answer = paraphrase(sentence)
            items.append(
                {
                    "type": "reading",
                    "prompt": profile["support_prompt"],
                    "answer": answer,
                    "options": with_options(answer, profile["support_wrong"]),
                    "evidence": sentence,
                    "note": f"同类巩固 / {profile['notes'][0]}",
                }
            )
    elif quiz_type == "main-idea":
        segments = [part.strip() for part in re.split(r"\n\s*\n", text) if len(part.strip()) > 40]
        segments.extend(" ".join(sents[index:index + 2]) for index in range(0, len(sents), 2))
        unique_segments = list(dict.fromkeys(segment for segment in segments if segment))
        for segment in unique_segments[:count]:
            first = sentences(segment)[0]
            answer = paraphrase(first)
            items.append(
                {
                    "type": "main-idea",
                    "prompt": profile["main_prompt"],
                    "answer": answer,
                    "options": with_options(answer, profile["main_wrong"]),
                    "evidence": segment,
                    "note": f"同类巩固 / {profile['notes'][1]}",
                }
            )
    elif quiz_type == "paraphrase":
        for sentence in sents[:count]:
            answer = paraphrase(sentence)
            items.append(
                {
                    "type": "paraphrase",
                    "prompt": profile["para_prompt"],
                    "answer": answer,
                    "options": with_options(answer, profile["para_wrong"]),
                    "evidence": sentence,
                    "note": f"同类巩固 / {profile['notes'][2]}",
                }
            )
    elif quiz_type == "cloze":
        keywords = [word for word in article_keywords(text) if word != original_answer]
        for keyword in keywords[:count]:
            context = sentence_for(text, keyword)
            prompt = re.sub(rf"\b{re.escape(keyword)}\b", "_____", context, flags=re.I)
            distractors = [word for word in LEXICON if word != keyword]
            random.shuffle(distractors)
            items.append(
                {
                    "type": "cloze",
                    "prompt": prompt,
                    "answer": keyword,
                    "options": with_options(keyword, distractors[:3]),
                    "evidence": context,
                    "note": f"同类巩固 / {profile['notes'][3]}",
                }
            )
    return items[:count]


CEFR_ORDER = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}

LEARNER_SETTINGS_KEY = "learner_profile"
DAILY_PLAN_MINUTES = {5, 15, 30, 60}
DAILY_PLAN_TASKS = {"reading", "output", "practice", "review", "vocabulary"}
DAILY_PLAN_DEFAULT_TARGETS = {"reading": 1, "output": 3, "practice": 5, "review": 2, "vocabulary": 5}
DAILY_METRIC_DEFAULT_TARGETS = {"reading_words": 400, "output_sentences": 3, "speaking_seconds": 60, "review_chunks": 5}
DAILY_METRIC_LIMITS = {"reading_words": (50, 5000), "output_sentences": (1, 50), "speaking_seconds": (15, 3600), "review_chunks": (1, 100)}
PROFILE_SECTIONS = {"reading", "listening", "writing", "speaking", "vocabulary"}
PROFILE_WEAK_AREAS = {
    "reading-speed", "evidence", "inference", "paraphrase", "vocabulary-use",
    "listening", "speaking", "writing", "grammar",
}
PROFILE_INTEREST_TOPICS = {
    "国际时政", "社会文化", "科学技术", "商业经济", "环境保护", "健康医学",
    "影视娱乐", "明星访谈", "小说文学", "日常生活",
}
PROFILE_TOPIC_ALIASES = {
    "国际时政": {"国际时政", "法律政策"}, "社会文化": {"社会文化", "教育学习", "心理行为"},
    "科学技术": {"科技创新", "太空探索", "自然与生态"}, "商业经济": {"经济商业"},
    "环境保护": {"环境保护", "自然与生态"}, "健康医学": {"健康医学", "心理行为"},
    "影视娱乐": {"社会文化"}, "明星访谈": {"社会文化"}, "小说文学": {"社会文化", "历史考古"},
    "日常生活": {"社会文化", "教育学习", "健康医学"},
}
PROFILE_CONTENT_TYPES = {"report", "opinion", "explainer", "research", "institution", "culture", "subtitles", "interview", "fiction", "blog"}
ASSESSMENT_RANGES = {
    "IELTS": (0, 9), "TOEFL": (0, 120), "EF_SET": (0, 100),
    "CET4": (0, 710), "CET6": (0, 710), "KAOYAN": (0, 100), "OTHER": (0, 1000),
}
QUICK_TEST_ITEMS = [
    {
        "id": "context-a2", "domain": "vocabulary", "level": "A2",
        "prompt": "The train was delayed, so Maya arrived later than expected. What does delayed mean?",
        "options": ["made late", "made cheaper", "made quieter", "made shorter"], "answer": "made late",
    },
    {
        "id": "purpose-b1", "domain": "reading", "level": "B1",
        "prompt": "A library extended its opening hours after students asked for more evening study space. Why did it extend its hours?",
        "options": ["To answer student demand", "To sell more books", "To reduce staffing", "To host a concert"], "answer": "To answer student demand",
    },
    {
        "id": "contrast-b1", "domain": "reading", "level": "B1",
        "prompt": "The device is inexpensive to buy; however, replacement parts are costly. Which statement is supported?",
        "options": ["Maintenance may be expensive", "The device is never repaired", "Replacement parts are free", "The purchase price is high"], "answer": "Maintenance may be expensive",
    },
    {
        "id": "context-b2", "domain": "vocabulary", "level": "B2",
        "prompt": "The committee rejected the proposal because its benefits were speculative rather than proven. What does speculative mean here?",
        "options": ["uncertain", "immediate", "measurable", "unrelated"], "answer": "uncertain",
    },
    {
        "id": "inference-b2", "domain": "reading", "level": "B2",
        "prompt": "Although remote work reduced commuting, several employees visited the office weekly to exchange ideas informally. What can be inferred?",
        "options": ["Some collaboration benefits from meeting in person", "Remote work ended completely", "Employees disliked exchanging ideas", "Commuting time increased for everyone"], "answer": "Some collaboration benefits from meeting in person",
    },
    {
        "id": "stance-c1", "domain": "reading", "level": "C1",
        "prompt": "The author calls the policy 'a useful first step, though hardly a substitute for structural reform.' What is the author's position?",
        "options": ["Cautious approval with reservations", "Complete rejection", "Unqualified enthusiasm", "Indifference to reform"], "answer": "Cautious approval with reservations",
    },
]
DEFAULT_LEARNER_SETTINGS = {
    "daily_minutes": 15,
    "daily_tasks": ["reading", "output", "practice", "review"],
    "daily_targets": DAILY_PLAN_DEFAULT_TARGETS,
    "daily_metric_targets": DAILY_METRIC_DEFAULT_TARGETS,
    "short_goal": "",
    "short_goal_date": "",
    "long_goal": "",
    "long_goal_date": "",
    "recommendations_enabled": True,
    "article_layout": "split",
    "article_density": "comfortable",
    "profile_completed": False,
    "profile_source": "",
    "assessment": {"type": "", "date": "", "overall": None, "sections": {}},
    "target_exam": "IELTS",
    "target_score": None,
    "target_date": "",
    "self_levels": {},
    "weak_areas": [],
    "interest_topics": [],
    "interest_content_types": [],
    "quick_test_result": {},
    "profile_started_at": "",
    "ability_domains": {},
    "overall_ability": {},
    "last_calibration_at": "",
}


def learner_settings() -> dict:
    with db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (LEARNER_SETTINGS_KEY,)).fetchone()
    if not row:
        return dict(DEFAULT_LEARNER_SETTINGS)
    try:
        saved = json.loads(row["value"])
    except (TypeError, ValueError):
        saved = {}
    settings = {**DEFAULT_LEARNER_SETTINGS, **(saved if isinstance(saved, dict) else {})}
    assessment = settings.get("assessment") if isinstance(settings.get("assessment"), dict) else {}
    settings["assessment"] = {"type": "", "date": "", "overall": None, "sections": {}, **assessment}
    settings["assessment"]["sections"] = settings["assessment"]["sections"] if isinstance(settings["assessment"].get("sections"), dict) else {}
    settings["self_levels"] = settings["self_levels"] if isinstance(settings.get("self_levels"), dict) else {}
    settings["quick_test_result"] = settings["quick_test_result"] if isinstance(settings.get("quick_test_result"), dict) else {}
    settings["ability_domains"] = settings["ability_domains"] if isinstance(settings.get("ability_domains"), dict) else {}
    settings["overall_ability"] = settings["overall_ability"] if isinstance(settings.get("overall_ability"), dict) else {}
    settings["weak_areas"] = [value for value in settings.get("weak_areas", []) if value in PROFILE_WEAK_AREAS]
    settings["interest_topics"] = [value for value in settings.get("interest_topics", []) if value in PROFILE_INTEREST_TOPICS]
    settings["interest_content_types"] = [value for value in settings.get("interest_content_types", []) if value in PROFILE_CONTENT_TYPES]
    settings["daily_minutes"] = settings["daily_minutes"] if settings["daily_minutes"] in DAILY_PLAN_MINUTES else 15
    settings["daily_tasks"] = [task for task in settings["daily_tasks"] if task in DAILY_PLAN_TASKS] or ["reading"]
    raw_targets = settings.get("daily_targets") if isinstance(settings.get("daily_targets"), dict) else {}
    settings["daily_targets"] = {
        task: max(1, min(50, int(raw_targets.get(task) or DAILY_PLAN_DEFAULT_TARGETS[task])))
        for task in DAILY_PLAN_TASKS
    }
    raw_metric_targets = settings.get("daily_metric_targets") if isinstance(settings.get("daily_metric_targets"), dict) else {}
    settings["daily_metric_targets"] = {
        metric: max(bounds[0], min(bounds[1], int(raw_metric_targets.get(metric) or DAILY_METRIC_DEFAULT_TARGETS[metric])))
        for metric, bounds in DAILY_METRIC_LIMITS.items()
    }
    settings["recommendations_enabled"] = bool(settings["recommendations_enabled"])
    settings["article_layout"] = settings["article_layout"] if settings["article_layout"] in {"split", "grid"} else "split"
    settings["article_density"] = settings["article_density"] if settings["article_density"] in {"comfortable", "compact"} else "comfortable"
    return settings


def save_learner_settings(settings: dict) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (LEARNER_SETTINGS_KEY, json.dumps(settings, ensure_ascii=False)),
        )


def optional_score(value: object, minimum: float, maximum: float, field: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a number") from exc
    if not minimum <= score <= maximum:
        raise ValueError(f"{field} must be between {minimum:g} and {maximum:g}")
    return round(score, 2)


def assessment_cefr(assessment_type: str, score: float | None) -> str:
    if score is None:
        return ""
    if assessment_type == "IELTS":
        return "C2" if score >= 8.5 else "C1" if score >= 7 else "B2" if score >= 5.5 else "B1" if score >= 4 else "A2"
    if assessment_type == "TOEFL":
        return "C1" if score >= 95 else "B2" if score >= 72 else "B1" if score >= 42 else "A2"
    if assessment_type == "EF_SET":
        return "C2" if score >= 71 else "C1" if score >= 61 else "B2" if score >= 51 else "B1" if score >= 41 else "A2" if score >= 31 else "A1"
    if assessment_type in {"CET4", "CET6"}:
        return "C1" if score >= 600 else "B2" if score >= 500 else "B1" if score >= 425 else "A2"
    if assessment_type == "KAOYAN":
        return "C1" if score >= 80 else "B2" if score >= 65 else "B1" if score >= 50 else "A2"
    return ""


ABILITY_DOMAINS = ("reading", "listening", "vocabulary", "writing", "speaking")
ABILITY_SCORE_BY_CEFR = {"A1": 20, "A2": 35, "B1": 50, "B2": 65, "C1": 80, "C2": 95}


def cefr_from_ability_score(score: float) -> str:
    return "C2" if score >= 88 else "C1" if score >= 73 else "B2" if score >= 58 else "B1" if score >= 43 else "A2" if score >= 28 else "A1"


def quiz_ability_domain(question_type: str, quiz_type: str = "", skill: str = "") -> str:
    combined = f"{question_type} {quiz_type} {skill}".casefold()
    vocabulary_signals = ("vocabulary", "complete-words", "cloze", "词汇", "选词", "完形", "语境词义")
    return "vocabulary" if any(signal in combined for signal in vocabulary_signals) else "reading"


def initial_ability_domains(settings: dict, overall_level: str) -> dict:
    saved = settings.get("ability_domains") if isinstance(settings.get("ability_domains"), dict) else {}
    self_levels = settings.get("self_levels") if isinstance(settings.get("self_levels"), dict) else {}
    result = {}
    for domain in ABILITY_DOMAINS:
        current = saved.get(domain) if isinstance(saved.get(domain), dict) else {}
        level = current.get("cefr") if current.get("cefr") in CEFR_ORDER else self_levels.get(domain)
        level = level if level in CEFR_ORDER else overall_level
        result[domain] = {
            "cefr": level,
            "score": max(0, min(100, float(current.get("score", ABILITY_SCORE_BY_CEFR[level])))),
            "confidence": current.get("confidence") or ("low" if domain not in self_levels else "self"),
            "evidence_count": max(0, int(current.get("evidence_count") or 0)),
            "updated_at": current.get("updated_at") or "",
        }
    return result


def learner_profile_summary(settings: dict | None = None) -> dict:
    settings = settings or learner_settings()
    assessment = settings.get("assessment") or {}
    quick = settings.get("quick_test_result") or {}
    self_levels = settings.get("self_levels") or {}
    source = settings.get("profile_source") or ""
    assessment_type = str(assessment.get("type") or "")
    assessment_score = assessment.get("overall")
    section_values = [float(value) for value in (assessment.get("sections") or {}).values() if isinstance(value, (int, float))]
    if assessment_score is None and section_values:
        section_average = sum(section_values) / len(section_values)
        assessment_score = section_average * 4 if assessment_type == "TOEFL" else section_average
    level = assessment_cefr(assessment_type, assessment_score) if source == "score" else ""
    confidence = "medium" if level else ""
    if level and assessment.get("date"):
        try:
            age_days = (datetime.now().date() - datetime.fromisoformat(str(assessment["date"])).date()).days
            confidence = "high" if age_days <= 365 else "medium" if age_days <= 730 else "low"
        except ValueError:
            confidence = "medium"
    evidence = "已有成绩"
    if source == "quick_test" and quick.get("cefr"):
        level, confidence, evidence = quick["cefr"], "medium", "阅读与词汇快速基线"
    if source == "self_assessment" or not level:
        valid_self = [value for value in self_levels.values() if value in CEFR_ORDER]
        if valid_self:
            rank = round(sum(CEFR_ORDER[value] for value in valid_self) / len(valid_self))
            level = next((key for key, value in CEFR_ORDER.items() if value == rank), "B1")
            confidence, evidence = "low", "自评"
    level = level or "B1"
    domains = initial_ability_domains(settings, level)
    overall_saved = settings.get("overall_ability") if isinstance(settings.get("overall_ability"), dict) else {}
    overall_level = overall_saved.get("cefr") if overall_saved.get("cefr") in CEFR_ORDER else level
    current_rank = CEFR_ORDER[level]
    recommended_levels = [key for key, value in CEFR_ORDER.items() if value in {current_rank, min(6, current_rank + 1)}]
    return {
        "completed": bool(settings.get("profile_completed")),
        "source": settings.get("profile_source") or "",
        "cefr": level,
        "overall_cefr": overall_level,
        "confidence": confidence or "low",
        "evidence": evidence if settings.get("profile_completed") else "默认起点",
        "recommended_levels": recommended_levels,
        "target_exam": settings.get("target_exam") or "IELTS",
        "target_score": settings.get("target_score"),
        "target_date": settings.get("target_date") or "",
        "weak_areas": settings.get("weak_areas") or [],
        "interest_topics": settings.get("interest_topics") or [],
        "interest_content_types": settings.get("interest_content_types") or [],
        "domains": domains,
        "last_calibration_at": settings.get("last_calibration_at") or "",
    }


def update_learner_profile(payload: dict) -> dict:
    settings = learner_settings()
    previous_source = settings.get("profile_source") or ""
    previous_assessment = settings.get("assessment") or {}
    previous_self_levels = settings.get("self_levels") or {}
    source = str(payload.get("profile_source") or "self_assessment")
    if source not in {"score", "quick_test", "self_assessment"}:
        raise ValueError("profile_source must be score, quick_test, or self_assessment")
    if source == "quick_test" and not settings.get("quick_test_result"):
        raise ValueError("Complete the quick test before saving this profile")
    assessment_type = str(payload.get("assessment_type") or "").upper()
    assessment = settings.get("assessment") if source == "quick_test" else {"type": "", "date": "", "overall": None, "sections": {}}
    if source == "score":
        if assessment_type not in ASSESSMENT_RANGES:
            raise ValueError("Select a supported assessment type")
        minimum, maximum = ASSESSMENT_RANGES[assessment_type]
        overall = optional_score(payload.get("overall_score"), minimum, maximum, "overall_score")
        raw_sections = payload.get("section_scores") if isinstance(payload.get("section_scores"), dict) else {}
        section_maximum = 9 if assessment_type == "IELTS" else 30 if assessment_type == "TOEFL" else maximum
        sections = {
            key: score for key in PROFILE_SECTIONS
            if (score := optional_score(raw_sections.get(key), 0, section_maximum, f"section_scores.{key}")) is not None
        }
        if overall is None and not sections:
            raise ValueError("Enter at least one overall or section score")
        assessment = {"type": assessment_type, "date": str(payload.get("assessment_date") or "")[:10], "overall": overall, "sections": sections}
    self_levels = {
        key: str(value) for key, value in (payload.get("self_levels") or {}).items()
        if key in PROFILE_SECTIONS and str(value) in CEFR_ORDER
    }
    if source == "quick_test":
        self_levels = settings.get("self_levels") or {}
    if source == "self_assessment" and not self_levels:
        raise ValueError("Select at least one self-assessed skill level")
    target_exam = str(payload.get("target_exam") or "IELTS").upper()
    if target_exam not in SUPPORTED_EXAMS and target_exam != "GENERAL":
        raise ValueError("Select a supported target exam")
    target_range = ASSESSMENT_RANGES.get(target_exam, (0, 1000))
    target_score = optional_score(payload.get("target_score"), target_range[0], target_range[1], "target_score")
    baseline_changed = (
        source != previous_source
        or (source == "score" and assessment != previous_assessment)
        or (source == "self_assessment" and self_levels != previous_self_levels)
    )
    settings.update({
        "profile_completed": True,
        "profile_source": source,
        "assessment": assessment,
        "target_exam": target_exam,
        "target_score": target_score,
        "target_date": str(payload.get("target_date") or "")[:10],
        "self_levels": self_levels,
        "weak_areas": list(dict.fromkeys(value for value in payload.get("weak_areas", []) if value in PROFILE_WEAK_AREAS)),
        "interest_topics": list(dict.fromkeys(value for value in payload.get("interest_topics", []) if value in PROFILE_INTEREST_TOPICS)),
        "interest_content_types": list(dict.fromkeys(value for value in payload.get("interest_content_types", []) if value in PROFILE_CONTENT_TYPES)),
    })
    if baseline_changed:
        settings.update({"ability_domains": {}, "overall_ability": {}, "last_calibration_at": "", "profile_started_at": utc_now()})
    elif not settings.get("profile_started_at"):
        settings["profile_started_at"] = utc_now()
    save_learner_settings(settings)
    return {"settings": settings, "profile": learner_profile_summary(settings)}


def quick_test_payload() -> list[dict]:
    return [{key: value for key, value in item.items() if key != "answer"} for item in QUICK_TEST_ITEMS]


def submit_quick_test(payload: dict) -> dict:
    responses = payload.get("responses") if isinstance(payload.get("responses"), dict) else {}
    answered = [item for item in QUICK_TEST_ITEMS if str(responses.get(item["id"], "")).strip()]
    if len(answered) < 4:
        raise ValueError("Answer at least four quick-test questions")
    correct = [item for item in answered if responses.get(item["id"]) == item["answer"]]
    count = len(correct)
    cefr = "C1" if count == 6 else "B2" if count >= 4 else "B1" if count >= 2 else "A2"
    domains = {}
    for domain in {item["domain"] for item in QUICK_TEST_ITEMS}:
        domain_answered = [item for item in answered if item["domain"] == domain]
        domain_correct = [item for item in correct if item["domain"] == domain]
        domains[domain] = {"correct": len(domain_correct), "answered": len(domain_answered)}
    settings = learner_settings()
    target_exam = str(payload.get("target_exam") or settings.get("target_exam") or "IELTS").upper()
    if target_exam not in SUPPORTED_EXAMS and target_exam != "GENERAL":
        raise ValueError("Select a supported target exam")
    target_range = ASSESSMENT_RANGES.get(target_exam, (0, 1000))
    target_score = optional_score(payload.get("target_score"), target_range[0], target_range[1], "target_score")
    settings.update({
        "profile_completed": True,
        "profile_source": "quick_test",
        "quick_test_result": {"cefr": cefr, "correct": count, "answered": len(answered), "domains": domains, "completed_at": utc_now()},
        "target_exam": target_exam,
        "target_score": target_score,
        "target_date": str(payload.get("target_date") or "")[:10],
        "weak_areas": list(dict.fromkeys(value for value in payload.get("weak_areas", []) if value in PROFILE_WEAK_AREAS)),
        "interest_topics": list(dict.fromkeys(value for value in payload.get("interest_topics", []) if value in PROFILE_INTEREST_TOPICS)),
        "interest_content_types": list(dict.fromkeys(value for value in payload.get("interest_content_types", []) if value in PROFILE_CONTENT_TYPES)),
        "ability_domains": {},
        "overall_ability": {},
        "last_calibration_at": "",
        "profile_started_at": utc_now(),
    })
    save_learner_settings(settings)
    return {"result": settings["quick_test_result"], "settings": settings, "profile": learner_profile_summary(settings)}


def update_learner_settings(payload: dict) -> dict:
    minutes = int(payload.get("daily_minutes") or 15)
    if minutes not in DAILY_PLAN_MINUTES:
        raise ValueError("daily_minutes must be one of 5, 15, 30, or 60")
    tasks = [str(task) for task in (payload.get("daily_tasks") or []) if str(task) in DAILY_PLAN_TASKS]
    if not tasks:
        raise ValueError("Select at least one daily learning task")
    settings = {
        "daily_minutes": minutes,
        "daily_tasks": list(dict.fromkeys(tasks)),
        "daily_targets": {
            task: max(1, min(50, int((payload.get("daily_targets") or {}).get(task) or DAILY_PLAN_DEFAULT_TARGETS[task])))
            for task in DAILY_PLAN_TASKS
        },
        "daily_metric_targets": {
            metric: max(bounds[0], min(bounds[1], int((payload.get("daily_metric_targets") or {}).get(metric) or DAILY_METRIC_DEFAULT_TARGETS[metric])))
            for metric, bounds in DAILY_METRIC_LIMITS.items()
        },
        "short_goal": str(payload.get("short_goal") or "").strip()[:160],
        "short_goal_date": str(payload.get("short_goal_date") or "").strip()[:20],
        "long_goal": str(payload.get("long_goal") or "").strip()[:160],
        "long_goal_date": str(payload.get("long_goal_date") or "").strip()[:20],
        "recommendations_enabled": bool(payload.get("recommendations_enabled", True)),
    }
    current = learner_settings()
    current.update(settings)
    save_learner_settings(current)
    return current


def update_article_preferences(payload: dict) -> dict:
    layout = str(payload.get("article_layout") or "split")
    density = str(payload.get("article_density") or "comfortable")
    if layout not in {"split", "grid"}:
        raise ValueError("article_layout must be split or grid")
    if density not in {"comfortable", "compact"}:
        raise ValueError("article_density must be comfortable or compact")
    settings = learner_settings()
    settings.update({"article_layout": layout, "article_density": density})
    save_learner_settings(settings)
    return settings


def current_plan_day() -> str:
    return datetime.now().astimezone().date().isoformat()


def increment_daily_progress(conn: sqlite3.Connection, task: str, amount: int = 1, day: str = "") -> None:
    if task not in DAILY_PLAN_TASKS or amount <= 0:
        return
    target_day = day or current_plan_day()
    conn.execute(
        """
        INSERT INTO daily_plan_progress (day, task, completed_count, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(day, task) DO UPDATE SET
          completed_count = daily_plan_progress.completed_count + excluded.completed_count,
          updated_at = excluded.updated_at
        """,
        (target_day, task, amount, utc_now()),
    )


def decrement_daily_progress(conn: sqlite3.Connection, task: str, amount: int = 1, day: str = "") -> None:
    if task not in DAILY_PLAN_TASKS or amount <= 0:
        return
    target_day = day or current_plan_day()
    conn.execute(
        """UPDATE daily_plan_progress
           SET completed_count = MAX(0, completed_count - ?), updated_at = ?
           WHERE day = ? AND task = ?""",
        (amount, utc_now(), target_day, task),
    )


def set_daily_progress(conn: sqlite3.Connection, task: str, completed_count: int, day: str = "") -> None:
    target_day = day or current_plan_day()
    conn.execute(
        """
        INSERT INTO daily_plan_progress (day, task, completed_count, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(day, task) DO UPDATE SET
          completed_count = excluded.completed_count,
          updated_at = excluded.updated_at
        """,
        (target_day, task, max(0, completed_count), utc_now()),
    )


def increment_daily_metric(conn: sqlite3.Connection, metric: str, amount: int, day: str = "") -> None:
    if metric not in DAILY_METRIC_DEFAULT_TARGETS or amount <= 0:
        return
    target_day = day or current_plan_day()
    conn.execute(
        """INSERT INTO daily_learning_metrics (day, metric, value, updated_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(day, metric) DO UPDATE SET
             value = daily_learning_metrics.value + excluded.value,
             updated_at = excluded.updated_at""",
        (target_day, metric, amount, utc_now()),
    )


def decrement_daily_metric(conn: sqlite3.Connection, metric: str, amount: int, day: str = "") -> None:
    if metric not in DAILY_METRIC_DEFAULT_TARGETS or amount <= 0:
        return
    target_day = day or current_plan_day()
    conn.execute(
        """UPDATE daily_learning_metrics SET value = MAX(0, value - ?), updated_at = ?
           WHERE day = ? AND metric = ?""",
        (amount, utc_now(), target_day, metric),
    )


def mark_article_read(conn: sqlite3.Connection, article_id: int) -> dict:
    article = conn.execute("SELECT id, body FROM articles WHERE id = ?", (article_id,)).fetchone()
    if not article:
        raise ValueError("Article not found")
    count = len(words(article["body"]))
    day = current_plan_day()
    cursor = conn.execute(
        """INSERT OR IGNORE INTO article_reading_events (day, article_id, word_count, created_at)
           VALUES (?, ?, ?, ?)""",
        (day, article_id, count, utc_now()),
    )
    recorded = cursor.rowcount > 0
    if recorded:
        increment_daily_metric(conn, "reading_words", count, day)
        increment_daily_progress(conn, "reading", 1, day)
    return {"recorded": recorded, "word_count": count, "day": day}


def daily_plan_snapshot(settings: dict | None = None, day: str = "") -> dict:
    settings = settings or learner_settings()
    target_day = day or current_plan_day()
    with db() as conn:
        progress_rows = conn.execute(
            "SELECT task, completed_count FROM daily_plan_progress WHERE day = ?", (target_day,)
        ).fetchall()
        item_rows = conn.execute(
            "SELECT * FROM daily_plan_items WHERE day = ? ORDER BY completed, created_at, id", (target_day,)
        ).fetchall()
        metric_rows = conn.execute(
            "SELECT metric, value FROM daily_learning_metrics WHERE day = ?", (target_day,)
        ).fetchall()
    completed_by_task = {row["task"]: row["completed_count"] for row in progress_rows}
    tasks = []
    target_total = 0
    completed_total = 0
    for task in settings["daily_tasks"]:
        target = settings["daily_targets"].get(task, DAILY_PLAN_DEFAULT_TARGETS[task])
        completed = completed_by_task.get(task, 0)
        target_total += target
        completed_total += min(target, completed)
        tasks.append({
            "task": task,
            "target": target,
            "completed": completed,
            "done": completed >= target,
            "percent": min(100, round(completed / max(1, target) * 100)),
        })
    overall_percent = min(100, round(completed_total / max(1, target_total) * 100))
    remaining_minutes = max(0, round(settings["daily_minutes"] * (100 - overall_percent) / 100))
    if overall_percent < 100:
        remaining_minutes = max(1, remaining_minutes)
    metric_values = {row["metric"]: row["value"] for row in metric_rows}
    metrics = []
    for metric, target in settings["daily_metric_targets"].items():
        value = metric_values.get(metric, 0)
        metrics.append({
            "metric": metric, "target": target, "value": value,
            "done": value >= target, "percent": min(100, round(value / max(1, target) * 100)),
        })
    return {
        "date": target_day,
        "minutes": settings["daily_minutes"],
        "tasks": tasks,
        "items": rows_to_dicts(item_rows),
        "metrics": metrics,
        "overall_percent": overall_percent,
        "remaining_minutes": remaining_minutes,
        "completed": bool(tasks) and all(item["done"] for item in tasks),
        "summary": "今日计划已完成" if tasks and all(item["done"] for item in tasks) else f"还需约 {remaining_minutes} 分钟",
    }


def save_output_review_item(
    conn: sqlite3.Connection,
    attempt_id: int,
    custom_term: str = "",
    custom_context: str = "",
    custom_note: str = "",
) -> dict:
    attempt = output_attempt_payload(conn, attempt_id)
    if not attempt:
        raise ValueError("Output attempt not found")
    is_custom = bool(str(custom_term or "").strip())
    if is_custom:
        term = re.sub(r"\s+", " ", str(custom_term)).strip()
        context = str(custom_context or attempt["source_text"] or attempt["reference_text"]).strip()
        if not re.search(r"[A-Za-z]", term):
            raise ValueError("The saved word, phrase, or sentence must contain English")
        if len(term) > 500 or len(context) > 3000:
            raise ValueError("The review item is too long")
        link_type = "custom"
    else:
        existing = conn.execute(
            """SELECT l.*, c.term, c.context FROM output_review_links l
               JOIN cards c ON c.id = l.card_id WHERE l.attempt_id = ? AND l.link_type = 'reference'""",
            (attempt_id,),
        ).fetchone()
        if existing:
            return {"created": False, "card": dict(existing), "attempt": attempt}
        if attempt["task_type"] == "zh_to_en":
            context = attempt["reference_text"]
        else:
            context = attempt["source_text"] or attempt["reference_text"]
        matching_chunks = [
            chunk for chunk in (attempt["target_chunks"] or [])
            if str(chunk).strip() and str(chunk).casefold() in str(context).casefold()
        ]
        term = matching_chunks[0] if matching_chunks else context
        link_type = "reference"
    term = re.sub(r"\s+", " ", str(term)).strip()[:500]
    context = str(context or "").strip()[:3000]
    now = utc_now()
    card = conn.execute(
        "SELECT * FROM cards WHERE lower(trim(term)) = lower(?) ORDER BY id DESC LIMIT 1", (term,)
    ).fetchone()
    created = False
    if card:
        card_id = int(card["id"])
        conn.execute(
            "UPDATE cards SET context = ?, source_article_id = ?, note = ?, updated_at = ? WHERE id = ?",
            (
                context or card["context"], attempt["article_id"],
                str(custom_note or f"输出复习 · {attempt['task_label']}").strip()[:500], now, card_id,
            ),
        )
    else:
        cursor = conn.execute(
            """INSERT INTO cards
               (term, kind, context, source_article_id, status, note, created_at, updated_at)
               VALUES (?, 'phrase', ?, ?, 'new', ?, ?, ?)""",
            (
                term, context, attempt["article_id"],
                str(custom_note or f"输出复习 · {attempt['task_label']}").strip()[:500], now, now,
            ),
        )
        card_id = int(cursor.lastrowid)
        created = True
        increment_daily_progress(conn, "vocabulary", 1)
    ensure_review_item(conn, "card", card_id, now)
    conn.execute(
        """INSERT OR IGNORE INTO output_review_links (attempt_id, card_id, link_type, created_at)
           VALUES (?, ?, ?, ?)""",
        (attempt_id, card_id, link_type, now),
    )
    saved = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
    return {"created": created, "card": dict(saved), "attempt": output_attempt_payload(conn, attempt_id)}


def usage_contrast_catalog_payload(conn: sqlite3.Connection, query: str = "") -> dict:
    attempts = {
        row["contrast_slug"]: {"attempts": row["attempts"], "correct": row["correct"]}
        for row in conn.execute(
            """SELECT contrast_slug, COUNT(*) AS attempts, COALESCE(SUM(correct), 0) AS correct
               FROM usage_contrast_attempts GROUP BY contrast_slug"""
        ).fetchall()
    }
    items = []
    for contrast in contrast_catalog(query):
        item = dict(contrast)
        item.pop("answer_index", None)
        item.pop("explanation", None)
        item["history"] = attempts.get(item["slug"], {"attempts": 0, "correct": 0})
        items.append(item)
    return {"contrasts": items, "query": query, "source": "curated-v1"}


def save_speaking_review_item(
    conn: sqlite3.Connection,
    attempt_id: int,
    term: str,
    context: str = "",
) -> dict:
    attempt = speaking_attempt_payload(conn, attempt_id)
    if not attempt or attempt["status"] == "deleted":
        raise ValueError("Speaking attempt not found")
    clean_term = re.sub(r"\s+", " ", str(term or "")).strip()
    clean_context = str(context or attempt["transcript_text"] or attempt["prompt_text"]).strip()
    if not re.search(r"[A-Za-z]", clean_term):
        raise ValueError("The saved speaking expression must contain English")
    if len(clean_term) > 500 or len(clean_context) > 3000:
        raise ValueError("The speaking review item is too long")
    now = utc_now()
    card = conn.execute(
        "SELECT * FROM cards WHERE lower(trim(term)) = lower(?) ORDER BY id DESC LIMIT 1",
        (clean_term,),
    ).fetchone()
    created = False
    if card:
        card_id = int(card["id"])
        conn.execute(
            "UPDATE cards SET context = ?, source_article_id = ?, note = ?, updated_at = ? WHERE id = ?",
            (clean_context or card["context"], attempt["article_id"], "口语卡住表达", now, card_id),
        )
    else:
        cursor = conn.execute(
            """INSERT INTO cards
               (term, kind, context, source_article_id, status, note, created_at, updated_at)
               VALUES (?, 'phrase', ?, ?, 'new', '口语卡住表达', ?, ?)""",
            (clean_term, clean_context, attempt["article_id"], now, now),
        )
        card_id = int(cursor.lastrowid)
        created = True
        increment_daily_progress(conn, "vocabulary", 1)
    ensure_review_item(conn, "card", card_id, now)
    conn.execute(
        "INSERT OR IGNORE INTO speaking_review_links (attempt_id, card_id, created_at) VALUES (?, ?, ?)",
        (attempt_id, card_id, now),
    )
    saved = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
    return {"created": created, "card": dict(saved), "attempt": speaking_attempt_payload(conn, attempt_id)}


def current_learner_level() -> str:
    with db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = 'learner_level'").fetchone()
    level = row["value"] if row else "B1"
    return level if level in CEFR_ORDER else "B1"


def heuristic_word_level(term: str) -> str:
    clean = re.sub(r"[^A-Za-z]", "", term)
    if len(clean) >= 12:
        return "C1"
    if len(clean) >= 9:
        return "B2"
    if len(clean) >= 7:
        return "B1"
    return "A2"


def vocabulary_candidates(text: str, limit: int = 10) -> list[dict]:
    learner_level = current_learner_level()
    candidates = article_keywords(text)
    with db() as conn:
        entries = {
            row["headword"].lower(): dict(row)
            for row in conn.execute("SELECT headword, level FROM dictionary_entries").fetchall()
        }
        saved_cards = rows_to_dicts(conn.execute("SELECT term, kind FROM cards WHERE status != 'known'").fetchall())

    text_lower = text.lower()
    saved_terms = {
        card["term"].lower(): card["kind"]
        for card in saved_cards
        if card["term"].strip() and card["term"].lower() in text_lower
    }
    terms = list(dict.fromkeys([*saved_terms.keys(), *candidates]))
    results = []
    for term in terms:
        level = entries.get(term, {}).get("level") or heuristic_word_level(term)
        saved = term in saved_terms
        above_level = CEFR_ORDER.get(level, 3) > CEFR_ORDER[learner_level]
        reason = "已在生词本" if saved else "高于当前等级" if above_level else "文章关键词"
        score = (100 if saved else 40 if above_level else 10) + CEFR_ORDER.get(level, 3) * 4 + len(term)
        results.append({
            "term": term,
            "kind": saved_terms.get(term, "phrase" if " " in term else "word"),
            "level": level,
            "reason": reason,
            "saved": saved,
            "score": score,
        })
    results.sort(key=lambda item: (-item["score"], item["term"]))
    return [{key: value for key, value in item.items() if key != "score"} for item in results[:limit]]


def analyze_payload(article: sqlite3.Row | dict) -> dict:
    text = article["body"]
    return {
        "id": article["id"],
        "title": article["title"],
        "level": estimate_level(text),
        "keywords": article_keywords(text),
        "vocabulary_candidates": vocabulary_candidates(text),
        "learner_level": current_learner_level(),
        "focus_sentences": focus_sentences(text),
        "sentence_count": len(sentences(text)),
        "word_count": len(words(text)),
    }


def source_profile(source: str, exam: str = "") -> dict:
    profile = SOURCE_PROFILES.get(
        source,
        {"tier": "其他", "topics": ["综合"], "exams": SUPPORTED_EXAMS},
    )
    if source in {"manual", "seed"}:
        fit = 95
    elif not exam or exam == "general":
        fit = 80 if profile["tier"] == "核心" else 60
    elif exam in profile["exams"]:
        fit = 100 if profile["tier"] == "核心" else 75
    else:
        fit = 35
    source_kind, default_content_type = SOURCE_CLASSIFICATION.get(source, ("其他来源", "explainer"))
    content_hub = content_hub_for(source, default_content_type)
    return {
        "source_tier": profile["tier"],
        "source_topics": profile["topics"],
        "source_exams": profile["exams"],
        "exam_fit": fit,
        "source_kind": source_kind,
        "default_content_type": default_content_type,
        "default_content_type_label": CONTENT_TYPE_LABELS.get(default_content_type, "学术解释"),
        "content_hub": content_hub,
        "content_hub_label": CONTENT_HUBS[content_hub],
    }


EXAM_WORD_RANGES = {
    "IELTS": (650, 1000),
    "TOEFL": (500, 850),
    "CET4": (250, 450),
    "CET6": (300, 500),
    "KAOYAN": (350, 550),
    "TEM4": (300, 500),
    "TEM8": (500, 850),
    "GRE": (150, 450),
    "GMAT": (200, 450),
}

USER_CONTROLLED_SOURCES = {"manual", "browser", "private EPUB", "seed"}


def article_quality_profile(article: dict, exam: str = "") -> dict:
    text = str(article.get("body") or "").strip()
    word_count = len(words(text))
    paragraph_values = [value.strip() for value in re.split(r"\n\s*\n", text) if value.strip()]
    sentence_values = sentences(text) if text else []
    normalized_paragraphs = [re.sub(r"\s+", " ", value).casefold() for value in paragraph_values]
    duplicate_count = len(normalized_paragraphs) - len(set(normalized_paragraphs))
    script_noise = bool(EMBEDDED_SCRIPT_NOISE.search(text))
    status = article.get("content_status") or ("full" if article.get("source") in USER_CONTROLLED_SOURCES else "summary")
    requested_exam = str(exam or "IELTS").upper()
    minimum, maximum = EXAM_WORD_RANGES.get(requested_exam, EXAM_WORD_RANGES["IELTS"])
    length_status = "matched" if minimum <= word_count <= maximum else "short" if word_count < minimum else "long"

    issues = []
    score = 100
    if status != "full":
        score -= 45
        issues.append("仅有来源摘要，不是完整正文")
    if word_count < 50:
        score -= 30
        issues.append("自然语言内容过短")
    if len(sentence_values) < 3:
        score -= 15
        issues.append("可分析句子不足")
    if script_noise:
        score -= 70
        issues.append("检测到网页脚本污染")
    if duplicate_count:
        score -= min(25, duplicate_count * 5)
        issues.append("存在重复段落")
    if status == "full" and article.get("source") not in USER_CONTROLLED_SOURCES:
        confidence = float(article.get("extraction_confidence") or 0)
        if not article.get("extraction_version"):
            score -= 15
            issues.append("尚未记录正文区块提取版本")
        elif confidence < 0.70:
            score -= 15
            issues.append("正文区块提取置信度偏低")
    if length_status == "short":
        issues.append(f"低于 {requested_exam} 建议下限 {minimum} 词")
    elif length_status == "long":
        issues.append(f"高于 {requested_exam} 建议上限 {maximum} 词")

    user_controlled = article.get("source") in USER_CONTROLLED_SOURCES
    training_eligible = status == "full" and score >= 60 and not script_noise and (length_status == "matched" or user_controlled)
    if status != "full":
        block_reason = "当前只有 RSS 摘要，请打开原文或补充合法正文后再训练"
    elif score < 60 or script_noise:
        block_reason = "正文质量未通过训练门槛"
    elif length_status != "matched" and not user_controlled:
        block_reason = f"正文共 {word_count} 词，不在 {requested_exam} 建议的 {minimum}-{maximum} 词范围内"
    else:
        block_reason = ""
    return {
        "content_quality_score": max(0, score),
        "content_quality_label": "优" if score >= 85 else "合格" if score >= 60 else "待修复",
        "content_quality_issues": issues,
        "exam_word_min": minimum,
        "exam_word_max": maximum,
        "exam_length_status": length_status,
        "exam_length_label": "字数匹配" if length_status == "matched" else "字数偏短" if length_status == "short" else "字数偏长",
        "training_eligible": training_eligible,
        "training_block_reason": block_reason,
        "user_length_override": user_controlled and length_status != "matched",
    }


def recommendation_profile(article: dict) -> dict:
    try:
        source_date = article.get("published_at") or article["created_at"]
        created = datetime.fromisoformat(source_date.replace("Z", "+00:00"))
        age_days = max(0, (datetime.now(timezone.utc) - created).days)
    except (TypeError, ValueError):
        age_days = 30
    freshness = max(0, 20 - min(20, age_days))
    source_quality = 25 if article["source_tier"] == "核心" else 17 if article["source_tier"] == "补充" else 12
    depth = min(15, len(words(article.get("body", ""))) // 18)
    level_fit = 10 if article.get("level") in {"B2", "B2-C1", "C1"} else 7
    exam_score = round(article["exam_fit"] * 0.3)
    quality_bonus = round(article.get("content_quality_score", 0) * 0.15)
    training_penalty = 0 if article.get("training_eligible") else 35
    score = source_quality + freshness + depth + level_fit + exam_score + quality_bonus - training_penalty
    reasons = []
    if article["exam_fit"] >= 90:
        reasons.append("考试匹配")
    if freshness >= 15:
        reasons.append("近期更新")
    if source_quality >= 25:
        reasons.append("核心来源")
    if depth >= 10 and article.get("training_eligible"):
        reasons.append("适合精读")
    if article.get("exam_length_status") == "matched":
        reasons.append("字数匹配")
    return {"recommendation_score": score, "recommendation_reasons": reasons[:3] or ["主题补充"]}


def article_theme_profile(article: dict) -> dict:
    text = f"{article.get('title', '')} {article.get('body', '')}".lower()
    scored = []
    for theme, keywords in ARTICLE_THEMES.items():
        score = sum(2 if re.search(rf"\b{re.escape(keyword)}\b", text) else 0 for keyword in keywords)
        if score:
            scored.append((score, theme))
    scored.sort(key=lambda item: (-item[0], item[1]))
    themes = [theme for _, theme in scored[:3]] or ["综合阅读"]
    highlights = focus_sentences(article.get("body", ""), 1)
    return {"theme_tags": themes, "highlight": highlights[0] if highlights else article.get("body", "")}


def infer_content_type(article: dict) -> str:
    explicit = str(article.get("content_type") or "").strip()
    if explicit in CONTENT_TYPE_LABELS:
        return explicit
    source = str(article.get("source") or "manual")
    default_type = SOURCE_CLASSIFICATION.get(source, ("其他来源", "explainer"))[1]
    title = str(article.get("title") or "").lower()
    if any(marker in title for marker in ("opinion:", "comment:", "editorial:")):
        return "opinion"
    if any(marker in title for marker in ("study finds", "researchers find", "new study")):
        return "research"
    return default_type if default_type in CONTENT_TYPE_LABELS else "explainer"


def enrich_article(article: dict, exam: str = "") -> dict:
    item = dict(article)
    item.update(source_profile(item["source"], exam))
    item.update(article_theme_profile(item))
    item["content_type"] = infer_content_type(item)
    item["content_type_label"] = CONTENT_TYPE_LABELS[item["content_type"]]
    item["content_hub"] = content_hub_for(item["source"], item["content_type"])
    item["content_hub_label"] = CONTENT_HUBS[item["content_hub"]]
    item["content_status"] = item.get("content_status") or ("full" if item["source"] in {"seed", "manual"} else "summary")
    item["content_word_count"] = len(words(item.get("body", "")))
    item.update(article_quality_profile(item, exam))
    item.update(recommendation_profile(item))
    original_paragraphs = [value for value in re.split(r"\n\s*\n", item.get("body", "")) if value.strip()]
    translated_paragraphs = [value for value in re.split(r"\n\s*\n", item.get("translation_zh", "")) if value.strip()]
    item["paragraph_count"] = len(original_paragraphs)
    item["translation_paragraph_count"] = len(translated_paragraphs)
    item["translation_aligned"] = bool(translated_paragraphs) and len(original_paragraphs) == len(translated_paragraphs)
    return item


def article_paragraph_values(body: str) -> list[str]:
    return [value.strip() for value in re.split(r"\n\s*\n", body or "") if value.strip()]


def article_paragraph_translation_values(conn: sqlite3.Connection, article: dict) -> list[str]:
    originals = article_paragraph_values(article.get("body", ""))
    values = [""] * len(originals)
    rows = conn.execute(
        """SELECT paragraph_index, source_hash, translation_zh
           FROM article_paragraph_translations WHERE article_id = ?""",
        (article["id"],),
    ).fetchall()
    for row in rows:
        index = int(row["paragraph_index"])
        if 0 <= index < len(originals):
            digest = hashlib.sha256(originals[index].encode("utf-8")).hexdigest()
            if row["source_hash"] == digest:
                values[index] = row["translation_zh"]
    return values


def article_with_paragraph_translations(conn: sqlite3.Connection, article: dict, exam: str = "") -> dict:
    item = enrich_article(article, exam)
    values = article_paragraph_translation_values(conn, item)
    item["paragraph_translations"] = values
    item["translation_paragraph_count"] = sum(bool(value.strip()) for value in values)
    item["translation_aligned"] = bool(values) and all(value.strip() for value in values)
    return item


def replace_article_paragraph_translations(
    conn: sqlite3.Connection,
    article: dict,
    translations: list[str],
    provider: str,
) -> list[str]:
    originals = article_paragraph_values(article.get("body", ""))
    now = utc_now()
    conn.execute("DELETE FROM article_paragraph_translations WHERE article_id = ?", (article["id"],))
    rows = []
    for index, source in enumerate(originals):
        translated = translations[index].strip() if index < len(translations) else ""
        if translated:
            rows.append((article["id"], index, hashlib.sha256(source.encode("utf-8")).hexdigest(), source, translated, provider, now))
    if rows:
        conn.executemany(
            """INSERT INTO article_paragraph_translations
               (article_id, paragraph_index, source_hash, source_text, translation_zh, provider, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
    return article_paragraph_translation_values(conn, article)


def list_articles(query: dict[str, list[str]]) -> list[dict]:
    where = []
    params: list[str] = []
    if query.get("level", [""])[0]:
        where.append("level = ?")
        params.append(query["level"][0])
    if query.get("q", [""])[0]:
        where.append("(title LIKE ? OR body LIKE ?)")
        needle = f"%{query['q'][0]}%"
        params.extend([needle, needle])
    sql = "SELECT * FROM articles"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC, id DESC"
    with db() as conn:
        items = rows_to_dicts(conn.execute(sql, params).fetchall())
    exam = query.get("exam", [""])[0]
    items = [enrich_article(item, exam) for item in items]
    active = [item for item in subscription_payload() if item["active"]]
    source_subscriptions = {item["target_value"] for item in active if item["target_type"] == "source"}
    category_subscriptions = {item["target_value"] for item in active if item["target_type"] == "category"}
    for item in items:
        item["subscribed"] = item["source"] in source_subscriptions or item["content_hub_label"] in category_subscriptions
    ranked = sorted(items, key=lambda item: (-item["recommendation_score"], item["id"]))
    daily_ids = {item["id"]: index + 1 for index, item in enumerate(ranked[:3])}
    for item in ranked:
        item["recommended_today"] = item["id"] in daily_ids
        item["daily_rank"] = daily_ids.get(item["id"])
    topic = query.get("topic", [""])[0]
    if topic:
        ranked = [item for item in ranked if topic in item["theme_tags"]]
    if query.get("recommended", [""])[0] == "1":
        ranked = [item for item in ranked if item["recommended_today"]]
    visibility = query.get("visibility", [""])[0]
    if visibility in {"public", "private"}:
        ranked = [item for item in ranked if item.get("visibility", "public") == visibility]
    content_type = query.get("content_type", [""])[0]
    if content_type:
        ranked = [item for item in ranked if item["content_type"] == content_type]
    hub = query.get("hub", [""])[0]
    if hub == "subscribed":
        ranked = [item for item in ranked if item["subscribed"]]
    elif hub:
        ranked = [item for item in ranked if item["content_hub"] == hub]
    return ranked


def article_facets(query: dict[str, list[str]]) -> dict:
    base_query = {key: value for key, value in query.items() if key in {"exam", "q", "level"}}
    items = list_articles(base_query)
    visibility = {"all": len(items), "public": 0, "private": 0}
    topics: dict[str, int] = {}
    levels: dict[str, int] = {}
    for item in items:
        scope = item.get("visibility", "public")
        visibility[scope] = visibility.get(scope, 0) + 1
        levels[item["level"]] = levels.get(item["level"], 0) + 1
        for topic in item.get("theme_tags") or []:
            topics[topic] = topics.get(topic, 0) + 1
    return {
        "visibility": visibility,
        "topics": dict(sorted(topics.items(), key=lambda value: (-value[1], value[0]))),
        "levels": dict(sorted(levels.items())),
    }


def subscription_payload() -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            "SELECT target_type, target_value, active, created_at, updated_at FROM subscriptions ORDER BY target_type, target_value"
        ).fetchall()
    return rows_to_dicts(rows)


def source_catalog_payload() -> list[dict]:
    active = {
        (item["target_type"], item["target_value"])
        for item in subscription_payload()
        if item["active"]
    }
    return [
        {
            **item,
            "content_type_label": CONTENT_TYPE_LABELS.get(item["default_content_type"], "学术解释"),
            "access_method": item["access_mode"],
            "rights_status": item["rights_mode"],
            "update_frequency": item["cadence"],
            "content_formats": item["formats"],
            "subscribed": ("source", item["name"]) in active or ("category", item["category"]) in active,
        }
        for item in source_catalog()
    ]


def estimated_study_minutes(article: dict) -> int:
    word_count = max(1, int(article.get("content_word_count") or len(words(article.get("body", "")))))
    reading_blocks = max(1, (word_count + 119) // 120)
    return min(30, max(5, reading_blocks * 5))


def today_content(exam: str = "", mode: str = "exam") -> dict:
    mode = mode if mode in {"interest", "exam"} else "exam"
    settings = learner_settings()
    profile = learner_profile_summary(settings)
    plan = daily_plan_snapshot(settings)
    articles = list_articles({"exam": [exam]})
    active = [item for item in subscription_payload() if item["active"]]

    enriched = []
    for article in articles:
        category = article["content_hub_label"]
        subscribed = article["subscribed"]
        study_minutes = estimated_study_minutes(article)
        interest_bonus = (
            (24 if subscribed else 0)
            + (12 if article["content_type"] in {"culture", "report"} else 0)
            + (9 if study_minutes <= 15 else 0)
            + (8 if article.get("level") in {"B1", "B2", "B1-B2"} else 0)
        )
        exam_bonus = round(article["exam_fit"] * 0.25) + (10 if study_minutes >= 15 else 0)
        article_levels = [value for value in re.findall(r"A1|A2|B1|B2|C1|C2", str(article.get("level") or ""))]
        level_distance = min((abs(CEFR_ORDER[value] - CEFR_ORDER[profile["cefr"]]) for value in article_levels), default=2)
        level_bonus = 18 if level_distance == 0 else 8 if level_distance == 1 else -4
        preferred_theme_tags = set().union(*(PROFILE_TOPIC_ALIASES.get(value, {value}) for value in profile["interest_topics"])) if profile["interest_topics"] else set()
        topic_bonus = 14 if set(article.get("theme_tags") or []) & preferred_theme_tags else 0
        content_bonus = 12 if article["content_type"] in profile["interest_content_types"] else 0
        enriched.append({
            **article,
            "catalog_category": category,
            "subscribed": subscribed,
            "study_minutes": study_minutes,
            "profile_level_distance": level_distance,
            "profile_topic_match": topic_bonus > 0,
            "profile_content_match": content_bonus > 0,
            "today_score": article["recommendation_score"] + (((interest_bonus if mode == "interest" else exam_bonus) + level_bonus + topic_bonus + content_bonus) if settings["recommendations_enabled"] else 0),
        })
    enriched.sort(key=lambda item: (-item["today_score"], item["id"]))

    used: set[int] = set()
    used_sources: set[str] = set()

    def choose(predicate, fallback=True):
        item = next(
            (
                candidate for candidate in enriched
                if candidate["id"] not in used and candidate["source"] not in used_sources and predicate(candidate)
            ),
            None,
        )
        if not item and fallback:
            item = next(
                (candidate for candidate in enriched if candidate["id"] not in used and candidate["source"] not in used_sources),
                None,
            )
        if not item:
            item = next((candidate for candidate in enriched if candidate["id"] not in used and predicate(candidate)), None)
        if not item and fallback:
            item = next((candidate for candidate in enriched if candidate["id"] not in used), None)
        if item:
            used.add(item["id"])
            used_sources.add(item["source"])
        return item

    if mode == "interest":
        lane_specs = (
            ("quick", "5 分钟看看", choose(lambda item: item["study_minutes"] <= 5), "轻松了解一个新话题"),
            ("focused", "15 分钟沉浸", choose(lambda item: item["subscribed"] or item["content_type"] == "culture"), "来自兴趣与订阅"),
            ("practice", "顺手练一练", choose(lambda item: item["training_eligible"] and item["content_type"] in {"report", "culture", "explainer"}, fallback=False), "把喜欢的内容转成词汇和小练习"),
        )
    else:
        lane_specs = (
            ("quick", "5 分钟热身", choose(lambda item: item["training_eligible"] and item["content_type"] in {"report", "institution"}, fallback=False), "进入考试阅读状态"),
            ("focused", "15 分钟精读", choose(lambda item: item["training_eligible"] and item["exam_fit"] >= 90, fallback=False), "匹配当前考试与难度"),
            ("deep", "30 分钟专项", choose(lambda item: item["training_eligible"] and item["content_type"] in {"opinion", "explainer", "research"}, fallback=False), "适合证据、同义替换与题型训练"),
        )

    lanes = []
    for lane_id, label, item, base_reason in lane_specs:
        if not item:
            continue
        if not settings["recommendations_enabled"]:
            reason = "通用内容安排"
        else:
            reason = "来自你的订阅" if item["subscribed"] else base_reason
            if item["profile_level_distance"] == 0:
                reason = f"{reason} · 难度接近你的 {profile['cefr']}"
            if item["profile_topic_match"] or item["profile_content_match"]:
                reason = f"{reason} · 匹配兴趣画像"
            active_goal = settings["short_goal"] or settings["long_goal"]
            if active_goal:
                reason = f"{reason} · 对应当前目标"
        lanes.append({"id": lane_id, "label": label, "reason": reason, "article": item})
    calibration = profile_calibration_status(settings)
    if mode == "interest":
        mode_focus = {
            "title": "内容沉浸与表达积累",
            "primary": "从喜欢的内容开始",
            "signals": [
                f"已选 {len(profile['interest_topics'])} 个兴趣主题",
                f"已订阅 {len(active)} 个来源或分类",
                "阅读、查词和词块积累优先，练习可选",
            ],
            "next_action": "reading",
        }
    else:
        analytics = practice_analytics(exam or profile["target_exam"] or "IELTS")
        recommendation = analytics.get("recommendation") or {}
        target_label = f"{profile['target_exam']} {profile['target_score']}" if profile.get("target_score") is not None else profile["target_exam"]
        mode_focus = {
            "title": "目标驱动的训练处方",
            "primary": "按弱项开始训练",
            "signals": [
                f"目标：{target_label}{' · ' + profile['target_date'] if profile.get('target_date') else ''}",
                recommendation.get("reason") or "完成一次训练后生成弱项建议。",
                f"画像校准：{'本周待执行' if calibration['due'] else str(calibration['days_remaining']) + ' 天后'}",
            ],
            "next_action": "practice",
            "recommended_question_type": recommendation.get("question_type") or "",
            "recommended_skill": recommendation.get("skill") or "",
        }
    return {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "exam": exam or "general",
        "mode": mode,
        "subscription_count": len(active),
        "profile": profile,
        "calibration": calibration,
        "mode_focus": mode_focus,
        "plan": {**plan, "recommendations_enabled": settings["recommendations_enabled"]},
        "goals": {
            "short": settings["short_goal"],
            "short_date": settings["short_goal_date"],
            "long": settings["long_goal"],
            "long_date": settings["long_goal_date"],
        },
        "lanes": lanes,
    }


LEXICAL_JSON_FIELDS = {
    "forms_json": "forms", "aliases_json": "aliases", "family_json": "family",
    "collocations_json": "collocations", "synonyms_json": "synonyms",
    "antonyms_json": "antonyms", "examples_json": "examples", "morphemes_json": "morphemes",
}


def lexical_entry(row: sqlite3.Row) -> dict:
    item = dict(row)
    for source, target in LEXICAL_JSON_FIELDS.items():
        item[target] = json.loads(item.pop(source) or "[]")
    return item


def morpheme_entry(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["examples"] = json.loads(item.pop("examples_json") or "[]")
    return item


def lexical_query_context(term: str, limit: int = 12) -> dict:
    normalized = re.sub(r"\s+", " ", term).strip()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    contexts: list[dict] = []
    with db() as conn:
        card = conn.execute(
            "SELECT * FROM cards WHERE lower(trim(term)) = lower(?) ORDER BY updated_at DESC, id DESC LIMIT 1",
            (normalized,),
        ).fetchone()
        clip = conn.execute(
            """SELECT translated_text FROM browser_clips
               WHERE lower(trim(source_text)) = lower(?) AND translated_text != ''
               ORDER BY created_at DESC, id DESC LIMIT 1""",
            (normalized,),
        ).fetchone()
        cached = conn.execute(
            """SELECT translated_text FROM translation_cache
               WHERE text_hash = ? AND source_lang = 'EN' AND target_lang = 'ZH-HANS'
               ORDER BY created_at DESC, id DESC LIMIT 1""",
            (digest,),
        ).fetchone()
        article_rows = conn.execute(
            """SELECT id, title, source, body FROM articles
               WHERE lower(body) LIKE lower(?) ORDER BY updated_at DESC, id DESC""",
            (f"%{normalized}%",),
        ).fetchall()

    if card and card["context"]:
        contexts.append({
            "text": card["context"],
            "source": "生词本语境",
            "article_id": card["source_article_id"],
            "article_title": "",
            "translation_zh": "",
        })
    pattern = re.compile(rf"(?<![A-Za-z]){re.escape(normalized)}(?![A-Za-z])", re.I)
    article_count = 0
    occurrence_count = 0
    for row in article_rows:
        row_occurrences = len(pattern.findall(row["body"]))
        if row_occurrences:
            article_count += 1
            occurrence_count += row_occurrences
        for context in (sentence for sentence in sentences(row["body"]) if pattern.search(sentence)):
            if any(item["text"] == context for item in contexts):
                continue
            contexts.append({
                "text": context,
                "source": row["source"],
                "article_id": row["id"],
                "article_title": row["title"],
                "translation_zh": "",
            })
            if len(contexts) >= limit:
                break
        if len(contexts) >= limit:
            break
    context_translations = cached_segment_translations([item["text"] for item in contexts])
    for item in contexts:
        item["translation_zh"] = context_translations.get(item["text"], "")
    return {
        "translation_zh": (clip or cached or {"translated_text": ""})["translated_text"],
        "saved": bool(card),
        "card_id": card["id"] if card else None,
        "card_status": card["status"] if card else "",
        "contexts": contexts[:limit],
        "article_count": article_count,
        "occurrence_count": occurrence_count,
    }


def contextual_collocations(term: str, contexts: list[dict], limit: int = 8) -> list[dict]:
    clean = term.strip()
    if not clean or " " in clean:
        return []
    escaped = re.escape(clean)
    trailing = re.compile(
        rf"\b{escaped}\b\s+(?:of|from|for|by|over|as|with|against|into|on)\s+(?:[A-Za-z][A-Za-z'-]*\s*){{1,3}}",
        re.IGNORECASE,
    )
    leading = re.compile(rf"\b[A-Za-z][A-Za-z'-]*\s+\b{escaped}\b", re.IGNORECASE)
    weak_leaders = {"a", "an", "the", "this", "that", "his", "her", "its", "their", "your", "my", "and", "or", "but"}
    weak_trailing = {"and", "or", "but", "which", "that", "who", "when", "while"}
    candidates: list[tuple[str, str]] = []
    for context in contexts:
        sentence = context.get("text", "")
        for match in trailing.finditer(sentence):
            words_in_phrase = match.group(0).split()
            while words_in_phrase and words_in_phrase[-1].lower() in weak_trailing:
                words_in_phrase.pop()
            if len(words_in_phrase) >= 3:
                candidates.append((" ".join(words_in_phrase), sentence))
        for match in leading.finditer(sentence):
            phrase = match.group(0)
            leader = phrase.split()[0].lower()
            if leader not in weak_leaders and not leader.endswith("'s"):
                candidates.append((phrase, sentence))
    grouped: dict[str, dict] = {}
    for phrase, sentence in candidates:
        key = phrase.casefold()
        item = grouped.setdefault(key, {
            "phrase": phrase,
            "meaning_zh": "",
            "source": "个人文章语料",
            "observed_count": 0,
            "contexts": [],
            "synonyms": [],
            "antonyms": [],
        })
        item["observed_count"] += 1
        if sentence not in item["contexts"]:
            item["contexts"].append(sentence)
    ranked = sorted(grouped.values(), key=lambda item: (-item["observed_count"], len(item["phrase"]), item["phrase"].casefold()))
    return ranked[:limit]


def cached_segment_translations(segments: list[str], source_lang: str = "EN", target_lang: str = "ZH-HANS") -> dict[str, str]:
    values = list(dict.fromkeys(segment.strip() for segment in segments if segment and segment.strip()))
    if not values:
        return {}
    hashes = {hashlib.sha256(value.encode("utf-8")).hexdigest(): value for value in values}
    placeholders = ",".join("?" for _ in hashes)
    with db() as conn:
        rows = conn.execute(
            f"""SELECT text_hash, translated_text FROM translation_cache
                WHERE text_hash IN ({placeholders}) AND source_lang = ? AND target_lang = ?
                ORDER BY created_at DESC, id DESC""",
            (*hashes.keys(), source_lang, target_lang),
        ).fetchall()
    translated = {}
    for row in rows:
        source = hashes.get(row["text_hash"])
        if source and source not in translated:
            translated[source] = row["translated_text"]
    return translated


def related_term_translation(entries: list[dict], term: str) -> str:
    needle = term.lower()
    for entry in entries:
        related = [*(entry.get("synonyms") or []), *(entry.get("antonyms") or [])]
        for collocation in entry.get("collocations") or []:
            related.append(collocation)
            if isinstance(collocation, dict):
                related.extend(collocation.get("synonyms") or [])
                related.extend(collocation.get("antonyms") or [])
        for item in related:
            if not isinstance(item, dict):
                continue
            label = item.get("term") or item.get("phrase") or ""
            if label.lower() == needle:
                return item.get("meaning_zh") or ""
    return ""


WORDNET_POS_LABELS = {
    "n": "noun", "v": "verb", "a": "adjective", "s": "adjective satellite", "r": "adverb",
}

WORDNET_RELATION_LABELS = {
    "hypernym": "上位概念",
    "hyponym": "下位概念",
    "instance_hypernym": "上位实例",
    "instance_hyponym": "下位实例",
    "antonym": "反义关系",
    "similar": "相似表达",
    "also": "相关表达",
    "entails": "蕴含动作",
    "causes": "导致",
    "derivation": "派生关系",
}


def resolve_pronunciations(open_values: list, generic_values: list[str] | None = None) -> dict[str, str]:
    """Keep dialect labels when an open source provides them, with an honest generic fallback."""
    generic_values = generic_values or []
    uk = ""
    us = ""
    generic = ""
    for value in open_values or []:
        if isinstance(value, dict):
            pronunciation = str(value.get("ipa") or value.get("enpr") or "").strip()
            tags = {str(tag).strip().casefold() for tag in (value.get("tags") or [])}
        else:
            pronunciation = str(value).strip()
            tags = set()
        if not pronunciation:
            continue
        if tags.intersection({"uk", "british", "received pronunciation", "rp"}):
            uk = uk or pronunciation
        elif tags.intersection({"us", "american", "general american", "ga"}):
            us = us or pronunciation
        else:
            generic = generic or pronunciation
    generic = generic or next((str(value).strip() for value in generic_values if str(value).strip()), "")
    return {
        "ipa_uk": uk or generic,
        "ipa_us": us or generic,
        "pronunciation_scope": "dialect-specific" if uk or us else ("generic" if generic else "unavailable"),
    }


def wordnet_lookup(term: str, limit: int = 8) -> list[dict]:
    normalized = re.sub(r"\s+", " ", term).strip().casefold()
    if not normalized:
        return []
    with db() as conn:
        rows = conn.execute(
            """SELECT l.id, l.lemma, l.pos, l.synset_id, l.sense_id, l.pronunciations_json,
                      s.definitions_json, s.examples_json, s.members_json, s.ili,
                      d.name AS source_name, d.version AS source_version, d.license,
                      d.attribution, d.source_url
               FROM wordnet_lemmas l
               JOIN wordnet_synsets s ON s.synset_id = l.synset_id
               JOIN dictionary_sources d ON d.source_key = l.source_key
               WHERE l.normalized = ?
               ORDER BY l.pos, l.id LIMIT 80""",
            (normalized,),
        ).fetchall()
        if not rows:
            return []
        lexical_layers = lookup_lexical_layers(conn, term)
        profile = curated_term_profile(term)
        common_collocation_data = corpus_collocations(
            conn,
            term,
            registered_phrases=lexical_layers["phrases"],
            curated_patterns=(profile or {}).get("patterns") or [],
        )
        private_collocation_meanings = private_phrase_meanings(
            conn,
            [item["phrase"] for item in common_collocation_data["items"]]
            + [str(value.get("word") if isinstance(value, dict) else value) for value in lexical_layers["phrases"]],
        )
        synset_ids = list(dict.fromkeys(row["synset_id"] for row in rows))
        placeholders = ",".join("?" for _ in synset_ids)
        relation_rows = conn.execute(
            f"""SELECT synset_id, relation_type, target_synset_id FROM wordnet_relations
                WHERE synset_id IN ({placeholders})""",
            synset_ids,
        ).fetchall()
        target_ids = list(dict.fromkeys(row["target_synset_id"] for row in relation_rows))
        target_members: dict[str, list[str]] = {}
        if target_ids:
            target_placeholders = ",".join("?" for _ in target_ids)
            targets = conn.execute(
                f"SELECT synset_id, members_json FROM wordnet_synsets WHERE synset_id IN ({target_placeholders})",
                target_ids,
            ).fetchall()
            target_members = {row["synset_id"]: json.loads(row["members_json"] or "[]") for row in targets}

    relations_by_synset: dict[str, dict[str, list[str]]] = {}
    for relation in relation_rows:
        members = target_members.get(relation["target_synset_id"], [])
        if not members:
            continue
        bucket = relations_by_synset.setdefault(relation["synset_id"], {})
        bucket.setdefault(relation["relation_type"], []).extend(members)

    learning = lexical_query_context(term)
    personal_collocations = contextual_collocations(term, learning["contexts"])
    common_collocations = common_collocation_data["items"]
    open_phrases = []
    for phrase in lexical_layers["phrases"][:12]:
        value = phrase.get("word") if isinstance(phrase, dict) else str(phrase)
        if value and " " in value and re.search(rf"(?<![A-Za-z]){re.escape(normalized)}(?![A-Za-z])", value, re.I):
            open_phrases.append({
                "phrase": value,
                "meaning_zh": phrase.get("meaning_zh", "") if isinstance(phrase, dict) else "",
                "source": "Kaikki / Wiktionary",
                "observed_count": 0,
                "contexts": [],
                "synonyms": [],
                "antonyms": [],
            })
    collocations = [*common_collocations, *personal_collocations]
    source_segments = [term, *[item["phrase"] for item in collocations], *[item["phrase"] for item in open_phrases]]
    for row in rows:
        source_segments.extend(json.loads(row["definitions_json"] or "[]"))
        source_segments.extend(json.loads(row["examples_json"] or "[]"))
    cached_zh = cached_segment_translations(source_segments)
    grouped: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault(row["lemma"].casefold(), []).append(row)

    results = []
    for _, sense_rows in list(grouped.items())[:limit]:
        headword = sense_rows[0]["lemma"]
        pos_values = list(dict.fromkeys(row["pos"] for row in sense_rows if row["pos"]))
        generic_pronunciations = []
        senses = []
        synonyms = []
        examples = []
        semantic_relations: dict[str, list[str]] = {}
        for row in sense_rows:
            generic_pronunciations.extend(json.loads(row["pronunciations_json"] or "[]"))
            definitions = json.loads(row["definitions_json"] or "[]")
            sense_examples = json.loads(row["examples_json"] or "[]")
            members = json.loads(row["members_json"] or "[]")
            synonyms.extend(member for member in members if member.casefold() != normalized)
            examples.extend(sense_examples)
            senses.append({
                "synset_id": row["synset_id"],
                "pos": WORDNET_POS_LABELS.get(row["pos"], row["pos"]),
                "definitions": definitions,
                "definition_translations": [cached_zh.get(value, "") for value in definitions],
                "examples": sense_examples,
                "example_translations": [cached_zh.get(value, "") for value in sense_examples],
                "synonyms": members,
            })
            for relation_type, members in relations_by_synset.get(row["synset_id"], {}).items():
                semantic_relations.setdefault(relation_type, []).extend(members)

        unique = lambda values: list(dict.fromkeys(value for value in values if value))
        pronunciation = resolve_pronunciations(lexical_layers["pronunciations"], unique(generic_pronunciations))
        open_synonyms = [value.get("word", "") if isinstance(value, dict) else str(value) for value in lexical_layers["synonyms"]]
        open_antonyms = [value.get("word", "") if isinstance(value, dict) else str(value) for value in lexical_layers["antonyms"]]
        synonyms = unique([*synonyms, *open_synonyms])
        examples = unique(examples)
        antonyms = unique([*semantic_relations.get("antonym", []), *open_antonyms])
        family = unique(
            semantic_relations.get("hypernym", [])
            + semantic_relations.get("hyponym", [])
            + semantic_relations.get("derivation", [])
        )
        cached_zh.update(cached_segment_translations([
            *synonyms,
            *antonyms,
            *family,
            *[value for values in semantic_relations.values() for value in values],
        ]))
        source = sense_rows[0]
        results.append({
            "type": "wordnet",
            "id": sense_rows[0]["id"],
            "score": 94,
            "matched_by": "Open English WordNet",
            "headword": headword,
            "pos": " / ".join(WORDNET_POS_LABELS.get(value, value) for value in pos_values),
            "parts_of_speech": [WORDNET_POS_LABELS.get(value, value) for value in pos_values],
            **pronunciation,
            "core_meaning": next((definition for sense in senses for definition in sense["definitions"]), ""),
            "meaning_zh": next(iter(lexical_layers["translations_zh"]), next((cached_zh.get(value, "") for sense in senses for value in sense["definitions"] if cached_zh.get(value)), learning["translation_zh"])),
            "headword_translation_zh": cached_zh.get(headword, ""),
            "level": "",
            "register_label": "开放词典",
            "origin": "\n\n".join(lexical_layers["etymologies"][:3]),
            "breakdown": "",
            "forms": lexical_layers["forms"],
            "aliases": [],
            "family": [{"term": value, "meaning_zh": cached_zh.get(value, "")} for value in family[:24]],
            "collocations": [{
                **item,
                "meaning_zh": private_collocation_meanings.get(item["phrase"].casefold(), {}).get("meaning_zh") or cached_zh.get(item["phrase"], ""),
                "meaning_source": private_collocation_meanings.get(item["phrase"].casefold(), {}).get("source", ""),
            } for item in collocations],
            "common_collocations": [{
                **item,
                "meaning_zh": private_collocation_meanings.get(item["phrase"].casefold(), {}).get("meaning_zh") or cached_zh.get(item["phrase"], ""),
                "meaning_source": private_collocation_meanings.get(item["phrase"].casefold(), {}).get("source", ""),
            } for item in common_collocations],
            "personal_collocations": [{**item, "meaning_zh": cached_zh.get(item["phrase"], "")} for item in personal_collocations],
            "open_phrases": [{**item, "meaning_zh": cached_zh.get(item["phrase"], item["meaning_zh"])} for item in open_phrases],
            "collocation_corpus": {
                "examples_scanned": common_collocation_data["examples_scanned"],
                "sources": common_collocation_data["sources"],
            },
            "synonyms": [{"term": value, "meaning_zh": cached_zh.get(value, "")} for value in synonyms[:32]],
            "antonyms": [{"term": value, "meaning_zh": cached_zh.get(value, "")} for value in antonyms[:16]],
            "examples": [{"text": value, "translation": cached_zh.get(value, "")} for value in examples[:16]],
            "morphemes": [],
            "senses": senses[:16],
            "semantic_relations": [
                {
                    "type": relation_type,
                    "label": WORDNET_RELATION_LABELS.get(relation_type, relation_type.replace("_", " ")),
                    "terms": unique(values)[:20],
                    "term_details": [{"term": value, "meaning_zh": cached_zh.get(value, "")} for value in unique(values)[:20]],
                }
                for relation_type, values in semantic_relations.items()
                if values
            ],
            "saved": learning["saved"],
            "card_status": learning["card_status"],
            "contexts": learning["contexts"],
            "corpus_frequency": {
                "article_count": learning["article_count"],
                "occurrence_count": learning["occurrence_count"],
            },
            "frequency": lexical_layers["primary_frequency"],
            "open_examples": lexical_layers["examples"],
            "open_sources": lexical_layers["sources"],
            "open_entries": lexical_layers["entries"],
            "source_name": source["source_name"],
            "source_version": source["source_version"],
            "license": source["license"],
            "attribution": source["attribution"],
            "source_url": source["source_url"],
        })
    return results


def lexical_query_kind(query: str) -> str:
    if re.search(r"[\u3400-\u9fff]", query):
        return "chinese"
    if " " in query.strip():
        return "phrase"
    if query.startswith("-") or query.endswith("-"):
        return "morpheme"
    return "word"


def record_lexical_query(query: str) -> None:
    clean = re.sub(r"\s+", " ", query).strip()
    normalized = clean.casefold()
    if not normalized:
        return
    now = utc_now()
    with db() as conn:
        conn.execute(
            """INSERT INTO lexical_queries
               (normalized, query, query_kind, lookup_count, first_searched_at, last_searched_at)
               VALUES (?, ?, ?, 1, ?, ?)
               ON CONFLICT(normalized) DO UPDATE SET
                 query = excluded.query,
                 query_kind = excluded.query_kind,
                 lookup_count = lexical_queries.lookup_count + 1,
                 last_searched_at = excluded.last_searched_at""",
            (normalized, clean, lexical_query_kind(clean), now, now),
        )


def lexical_query_history(limit: int = 30) -> dict:
    try:
        safe_limit = max(1, min(100, int(limit or 30)))
    except (TypeError, ValueError):
        safe_limit = 30
    with db() as conn:
        recent = rows_to_dicts(conn.execute(
            "SELECT * FROM lexical_queries ORDER BY last_searched_at DESC LIMIT ?", (safe_limit,),
        ).fetchall())
        frequent = rows_to_dicts(conn.execute(
            "SELECT * FROM lexical_queries ORDER BY lookup_count DESC, last_searched_at DESC LIMIT 10"
        ).fetchall())
    return {"recent": recent, "frequent": frequent}


def lexical_candidate_exists(conn: sqlite3.Connection, candidate: str, curated_entries: list[dict]) -> bool:
    normalized = candidate.casefold()
    if any(
        entry["headword"].casefold() == normalized
        or normalized in {str(form).casefold() for form in entry.get("forms", [])}
        for entry in curated_entries
    ):
        return True
    if conn.execute("SELECT 1 FROM wordnet_lemmas WHERE normalized = ? LIMIT 1", (normalized,)).fetchone():
        return True
    return bool(conn.execute(
        "SELECT 1 FROM open_lexical_entries WHERE normalized = ? LIMIT 1", (normalized,)
    ).fetchone())


def morphology_candidates(term: str) -> list[str]:
    word = term.casefold()
    if not re.fullmatch(r"[a-z][a-z'-]{2,79}", word):
        return []
    candidates: list[str] = []
    if word.endswith("ies") and len(word) > 4:
        candidates.append(word[:-3] + "y")
    if word.endswith("ied") and len(word) > 4:
        candidates.append(word[:-3] + "y")
    if word.endswith("ing") and len(word) > 5:
        stem = word[:-3]
        candidates.extend([stem, stem + "e"])
        if len(stem) > 2 and stem[-1] == stem[-2]:
            candidates.append(stem[:-1])
    if word.endswith("ed") and len(word) > 4:
        stem = word[:-2]
        candidates.extend([stem, stem + "e"])
        if len(stem) > 2 and stem[-1] == stem[-2]:
            candidates.append(stem[:-1])
    if word.endswith("es") and len(word) > 4:
        candidates.extend([word[:-2], word[:-1]])
    elif word.endswith("s") and len(word) > 3:
        candidates.append(word[:-1])
    if word.endswith("est") and len(word) > 5:
        candidates.extend([word[:-3], word[:-3] + "e"])
    elif word.endswith("er") and len(word) > 4:
        candidates.extend([word[:-2], word[:-2] + "e"])
    return list(dict.fromkeys(value for value in candidates if value != word))


def resolve_lexical_form(conn: sqlite3.Connection, term: str, curated_entries: list[dict]) -> str:
    for candidate in morphology_candidates(term):
        if lexical_candidate_exists(conn, candidate, curated_entries):
            return candidate
    return ""


def spelling_suggestions(conn: sqlite3.Connection, term: str, curated_entries: list[dict], limit: int = 5) -> list[str]:
    normalized = term.casefold()
    if not re.fullmatch(r"[a-z][a-z'-]{2,39}", normalized):
        return []
    minimum, maximum = max(2, len(normalized) - 2), len(normalized) + 2
    prefix = normalized[:1] + "%"
    candidates = [entry["headword"].casefold() for entry in curated_entries]
    candidates.extend(row[0] for row in conn.execute(
        """SELECT DISTINCT normalized FROM wordnet_lemmas
           WHERE normalized LIKE ? AND length(normalized) BETWEEN ? AND ? LIMIT 700""",
        (prefix, minimum, maximum),
    ))
    candidates.extend(row[0] for row in conn.execute(
        """SELECT DISTINCT normalized FROM open_lexical_entries
           WHERE normalized LIKE ? AND length(normalized) BETWEEN ? AND ? LIMIT 300""",
        (prefix, minimum, maximum),
    ))
    pool = list(dict.fromkeys(value for value in candidates if value and value != normalized))
    return difflib.get_close_matches(normalized, pool, n=limit, cutoff=0.72)


def lexical_search(query: str, limit: int = 30, track: bool = False) -> dict:
    raw = (query or "").strip()
    needle = raw.lower()
    compact = needle.strip("-")
    with db() as conn:
        entries = [lexical_entry(row) for row in conn.execute("SELECT * FROM dictionary_entries ORDER BY headword")]
        morphemes = [morpheme_entry(row) for row in conn.execute("SELECT * FROM morphemes ORDER BY kind, form")]
        resolved_to = resolve_lexical_form(conn, raw, entries) if raw else ""

    results: list[dict] = []
    exact_lexical_match = False
    for entry in entries:
        headword = entry["headword"].lower()
        forms = [value.lower() for value in entry["forms"]]
        aliases = [value.lower() for value in entry["aliases"]]
        related = json.dumps(entry["family"] + entry["collocations"], ensure_ascii=False).lower()
        roots = [value.lower() for value in entry["morphemes"]]
        score, matched_by = 0, ""
        if not needle:
            score, matched_by = 10, "推荐词条"
        elif needle == headword:
            score, matched_by = 100, "单词完全匹配"
            exact_lexical_match = True
        elif needle in roots or compact in [root.strip("-") for root in roots]:
            score, matched_by = 92, "构词成分匹配"
        elif needle in forms:
            score, matched_by = 86, "词形匹配"
            exact_lexical_match = True
        elif any(needle == alias or needle in alias for alias in aliases) or needle in entry["meaning_zh"].lower():
            score, matched_by = 78, "中文释义匹配"
        elif needle in headword:
            score, matched_by = 68, "单词部分匹配"
        elif needle in related:
            score, matched_by = 58, "词族或搭配匹配"
        elif needle in entry["origin"].lower():
            score, matched_by = 72, "词源匹配"
        if score:
            results.append({"type": "entry", "score": score, "matched_by": matched_by, **entry})

    for morpheme in morphemes:
        form = morpheme["form"].lower()
        score, matched_by = 0, ""
        if not needle:
            score, matched_by = 9, "推荐构词成分"
        elif needle == form or compact == form.strip("-"):
            score, matched_by = 96, "词根词缀完全匹配"
        elif needle in morpheme["origin"].lower():
            score, matched_by = 90, "拉丁/希腊词源匹配"
        elif needle in morpheme["meaning_zh"] or needle in morpheme["note"].lower():
            score, matched_by = 80, "中文含义匹配"
        elif needle in form or any(needle in value.lower() for value in morpheme["examples"]):
            score, matched_by = 60, "相关词匹配"
        if score:
            results.append({"type": "morpheme", "score": score, "matched_by": matched_by, **morpheme})

    wordnet_results = wordnet_lookup(raw) if raw else []
    if not wordnet_results and resolved_to:
        wordnet_results = wordnet_lookup(resolved_to)
        for item in wordnet_results:
            item["matched_by"] = f"词形还原：{raw} → {resolved_to}"
    if wordnet_results:
        exact_lexical_match = True
        results.extend(wordnet_results)
    with db() as conn:
        open_results = search_open_entries(conn, raw) if raw else []
        private_results = search_private_entries(conn, raw) if raw else []
    if private_results:
        exact_lexical_match = exact_lexical_match or any(item["score"] >= 90 for item in private_results)
        results.extend(private_results)
    if open_results and not wordnet_results:
        for item in open_results:
            learning = lexical_query_context(item["headword"])
            item.update({
                "saved": learning["saved"],
                "card_status": learning["card_status"],
                "contexts": learning["contexts"],
                "corpus_frequency": {
                    "article_count": learning["article_count"],
                    "occurrence_count": learning["occurrence_count"],
                },
                "frequency": item["lexical_layers"]["primary_frequency"],
            })
        exact_lexical_match = any(item["score"] >= 90 for item in open_results)
        results.extend(open_results)

    is_english_term = bool(re.fullmatch(r"[A-Za-z][A-Za-z' -]{0,79}", raw)) and len(raw.split()) <= 6
    if is_english_term and not exact_lexical_match:
        learning = lexical_query_context(raw)
        if not learning["translation_zh"]:
            learning["translation_zh"] = related_term_translation(entries, raw)
        results.append({
            "type": "query",
            "id": 0,
            "score": 110 if " " in raw else 88,
            "matched_by": "短语查询" if " " in raw else "个人查询",
            "term": re.sub(r"\s+", " ", raw),
            "kind": "phrase" if " " in raw else "word",
            **learning,
        })

    for item in results:
        label = item.get("headword") or item.get("term") or ""
        profile = curated_term_profile(label)
        if profile:
            item["learning_profile"] = profile
    results.sort(key=lambda item: (-item["score"], item.get("headword", item.get("form", ""))))
    with db() as conn:
        suggestions = [] if not raw or exact_lexical_match or resolved_to else spelling_suggestions(conn, raw, entries)
    if track and raw:
        record_lexical_query(raw)
    return {
        "query": raw,
        "count": len(results),
        "results": results[:limit],
        "resolution": {"from": raw, "to": resolved_to} if resolved_to else None,
        "suggestions": suggestions,
    }


def _comparison_evidence(term: str) -> dict:
    payload = lexical_search(term, limit=8)
    normalized = term.casefold()
    item = next((candidate for candidate in payload["results"] if str(
        candidate.get("headword") or candidate.get("term") or candidate.get("form") or ""
    ).casefold() == normalized), payload["results"][0] if payload["results"] else {})
    layers = item.get("lexical_layers") or {}
    meaning = item.get("meaning_zh") or item.get("translation_zh") or item.get("headword_translation_zh") or ""
    definitions: list[str] = []
    examples: list[dict] = []
    for sense in item.get("senses") or []:
        definitions.extend(str(value) for value in (sense.get("definitions") or []) if value)
        translations = sense.get("example_translations") or []
        for index, value in enumerate(sense.get("examples") or []):
            examples.append({"text": value, "translation_zh": translations[index] if index < len(translations) else ""})
    for entry in layers.get("entries") or []:
        definitions.extend(str(value) for value in (entry.get("glosses") or []) if value)
    for value in layers.get("examples") or []:
        if isinstance(value, dict):
            examples.append({
                "text": value.get("text") or value.get("sentence") or "",
                "translation_zh": value.get("translation_zh") or value.get("translation") or "",
            })
    patterns = []
    for value in item.get("collocations") or []:
        if isinstance(value, dict):
            source = str(value.get("source") or "")
            if not value.get("observed_count") and not source.startswith(("人工", "本地整理")):
                continue
            label = value.get("phrase")
        else:
            label = value
        if label and label not in patterns:
            patterns.append(str(label))
    sources = []
    for value in (item.get("source_name"), item.get("matched_by")):
        if value and value not in sources:
            sources.append(str(value))
    for value in layers.get("sources") or []:
        label = value.get("name") or value.get("source_name") if isinstance(value, dict) else value
        if label and label not in sources:
            sources.append(str(label))
    frequency = item.get("frequency") or layers.get("primary_frequency") or {}
    return {
        "term": item.get("headword") or item.get("term") or term,
        "pos": item.get("pos") or "",
        "meaning_zh": meaning,
        "core_meaning": item.get("core_meaning") or next(iter(definitions), ""),
        "definitions": definitions[:5],
        "patterns": patterns[:6],
        "examples": [value for value in examples if value["text"]][:4],
        "frequency": frequency,
        "sources": sources,
        "found": bool(item) and item.get("type") != "query",
    }


def lexical_comparison(query: str) -> dict:
    terms = parse_comparison_terms(query)
    evidence = {term.casefold(): _comparison_evidence(term) for term in terms}
    curated = curated_comparison(terms)
    if curated:
        items = []
        for item in curated["items"]:
            dictionary = evidence[item["term"].casefold()]
            items.append({
                **item,
                "dictionary": dictionary,
                "frequency": dictionary["frequency"],
                "sources": ["本地人工整理基础组"],
                "evidence_sources": dictionary["sources"],
            })
        return {
            "query": query, "terms": terms, "mode": "curated", "reviewed": True,
            "source_note": "语义边界来自本地人工整理基础组；义项核对证据来自本机开放与私人词典层，不代表这些词典提供了本页辨析结论。",
            **{key: value for key, value in curated.items() if key != "items"}, "items": items,
        }
    return {
        "query": query, "terms": terms, "mode": "evidence", "reviewed": False,
        "title": " / ".join(terms),
        "shared_translation": "这些词尚未进入人工审核辨析组。",
        "summary": "当前只并排展示词性、开放释义、搭配、例句和常用度，不根据相同中文翻译强行判断它们可以互换。",
        "memory_rule": "先比较词性和句型，再比较搭配与具体语境。",
        "dimensions": [],
        "source_note": "自动汇总本机开放词典证据，不作强行结论；不是出版词典的编辑性辨析。",
        "items": [
            {
                **evidence[term.casefold()],
                "focus": evidence[term.casefold()]["core_meaning"] or "当前开放数据暂无核心英文释义。",
                "register": "尚无人工审核语域结论。",
                "avoid": "请根据例句和搭配判断，不要仅凭中文释义替换。",
                "example": next((value["text"] for value in evidence[term.casefold()]["examples"]), ""),
                "example_zh": next((value["translation_zh"] for value in evidence[term.casefold()]["examples"] if value["translation_zh"]), ""),
                "dictionary": evidence[term.casefold()],
            }
            for term in terms
        ],
    }


def dictionary_data_status() -> dict:
    with db() as conn:
        sources = rows_to_dicts(conn.execute(
            "SELECT * FROM dictionary_sources ORDER BY imported_at DESC, source_key"
        ).fetchall())
        counts = {
            "wordnet_lemmas": conn.execute("SELECT COUNT(*) FROM wordnet_lemmas").fetchone()[0],
            "open_entries": conn.execute("SELECT COUNT(*) FROM open_lexical_entries").fetchone()[0],
            "bilingual_examples": conn.execute("SELECT COUNT(*) FROM open_bilingual_examples").fetchone()[0],
            "frequencies": conn.execute("SELECT COUNT(*) FROM lexical_frequencies").fetchone()[0],
            "curated_entries": conn.execute("SELECT COUNT(*) FROM dictionary_entries").fetchone()[0],
            "private_entries": conn.execute("SELECT COUNT(*) FROM private_dictionary_entries").fetchone()[0],
        }
        private_sources = private_dictionary_status(conn)
        quality = audit_dictionary_data(conn)
    installed = {item["source_key"] for item in sources}
    layers = [
        {"id": "wordnet", "label": "英文语义", "source_key": "open-english-wordnet", "count": counts["wordnet_lemmas"]},
        {"id": "kaikki", "label": "词形与词源", "source_key": "kaikki-english", "count": counts["open_entries"]},
        {"id": "tatoeba", "label": "英汉例句", "source_key": "tatoeba-en-zh", "count": counts["bilingual_examples"]},
        {"id": "wordfreq", "label": "通用频率", "source_key": "wordfreq", "count": counts["frequencies"]},
    ]
    for layer in layers:
        layer["installed"] = layer["source_key"] in installed and layer["count"] > 0
    return {
        "sources": sources,
        "private_sources": private_sources,
        "layers": layers,
        "counts": counts,
        "quality": quality,
    }


def progress_payload(conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT * FROM progress WHERE id = 1").fetchone()
    item = dict(row)
    item["level"] = item["xp"] // 100 + 1
    item["level_xp"] = item["xp"] % 100
    item["next_level_xp"] = 100
    return item


def award_progress(conn: sqlite3.Connection, points: int, correct: bool = False, reviewed: bool = False) -> dict:
    today = datetime.now(timezone.utc).date()
    row = conn.execute("SELECT * FROM progress WHERE id = 1").fetchone()
    last = datetime.fromisoformat(row["last_study_date"]).date() if row["last_study_date"] else None
    streak = row["streak"]
    if last != today:
        streak = streak + 1 if last and (today - last).days == 1 else 1
    conn.execute(
        """UPDATE progress SET xp = xp + ?, correct_count = correct_count + ?,
           reviewed_count = reviewed_count + ?, streak = ?, last_study_date = ? WHERE id = 1""",
        (points, 1 if correct else 0, 1 if reviewed else 0, streak, today.isoformat()),
    )
    return progress_payload(conn)


def normalize_confidence(value: object) -> int | None:
    try:
        score = int(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None
    return score if score in {1, 2, 3} else None


def record_quiz_attempt(
    conn: sqlite3.Connection,
    quiz: sqlite3.Row | dict,
    answer: str,
    session_id: int | None = None,
    confidence: object = None,
    elapsed_seconds: object = 0,
    answer_changes: object = 0,
    hint_used: object = False,
) -> dict:
    quiz_data = dict(quiz)
    selected = str(answer or "").strip()
    confidence_score = normalize_confidence(confidence)
    correct = selected.casefold() == str(quiz_data.get("answer") or "").strip().casefold()
    error_type = "" if correct else classify_answer_error(quiz_data, selected)
    explanation = explain_mistake(quiz_data, selected)
    try:
        elapsed = max(0, min(7200, int(elapsed_seconds or 0)))
        changes = max(0, min(100, int(answer_changes or 0)))
    except (TypeError, ValueError):
        elapsed, changes = 0, 0
    hint = 1 if hint_used else 0
    try:
        metadata = json.loads(quiz_data.get("metadata_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        metadata = {}
    parent_mistake_id = int(metadata.get("parent_mistake_id") or 0)
    first_attempt = conn.execute(
        "SELECT COUNT(*) FROM attempts WHERE quiz_id = ?", (quiz_data["id"],)
    ).fetchone()[0] == 0
    now = utc_now()
    cursor = conn.execute(
        """INSERT INTO attempts
           (quiz_id, session_id, user_answer, confidence, elapsed_seconds, answer_changes, hint_used, correct, error_type, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (quiz_data["id"], session_id, selected, confidence_score, elapsed, changes, hint, 1 if correct else 0, error_type, now),
    )
    mastery = None
    mastery_reward = 0
    if parent_mistake_id:
        parent = conn.execute(
            "SELECT solved, reward_claimed, remedial_attempts, remedial_correct_streak FROM mistakes WHERE id = ?",
            (parent_mistake_id,),
        ).fetchone()
        if parent:
            streak = int(parent["remedial_correct_streak"] or 0) + 1 if correct else 0
            attempts = int(parent["remedial_attempts"] or 0) + 1
            mastered = bool(correct and streak >= 2)
            conn.execute(
                """UPDATE mistakes SET remedial_attempts = ?, remedial_correct_streak = ?,
                   solved = CASE WHEN ? THEN 1 WHEN ? THEN 0 ELSE solved END,
                   mastered_at = CASE WHEN ? THEN ? WHEN ? THEN '' ELSE mastered_at END,
                   mastery_source = CASE WHEN ? THEN 'remedial-streak' WHEN ? THEN '' ELSE mastery_source END
                   WHERE id = ?""",
                (attempts, streak, mastered, not correct, mastered, now, not correct, mastered, not correct, parent_mistake_id),
            )
            if mastered and not bool(parent["reward_claimed"]):
                conn.execute("UPDATE mistakes SET reward_claimed = 1 WHERE id = ?", (parent_mistake_id,))
                increment_daily_progress(conn, "review", 1)
                mastery_reward = 5
            mastery = {"mistake_id": parent_mistake_id, "attempts": attempts, "streak": streak, "mastered": mastered}
    if not correct and not parent_mistake_id:
        conn.execute(
            """
            INSERT INTO mistakes
            (quiz_id, prompt, answer, user_answer, evidence, source, skill, error_type, explanation_json, solved, created_at)
            VALUES (?, ?, ?, ?, ?, 'quiz', ?, ?, ?, 0, ?)
            """,
            (
                quiz_data["id"], quiz_data["prompt"], quiz_data["answer"], selected,
                quiz_data.get("evidence") or "", quiz_data.get("skill") or "阅读理解", error_type,
                json.dumps(explanation, ensure_ascii=False), now,
            ),
        )
        if quiz_data.get("question_type") == "complete-words":
            target_word = str(quiz_data.get("answer") or "").strip()
            existing_card = conn.execute(
                "SELECT id FROM cards WHERE lower(term) = lower(?) ORDER BY id LIMIT 1", (target_word,)
            ).fetchone()
            note = "TOEFL 2026 Complete the Words 错词"
            if existing_card:
                conn.execute(
                    "UPDATE cards SET context = ?, note = ?, updated_at = ? WHERE id = ?",
                    (quiz_data.get("evidence") or "", note, now, existing_card["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO cards
                       (term, kind, context, source_article_id, status, note, created_at, updated_at)
                       VALUES (?, 'word', ?, ?, 'new', ?, ?, ?)""",
                    (target_word, quiz_data.get("evidence") or "", quiz_data.get("article_id"), note, now, now),
                )
                increment_daily_progress(conn, "vocabulary", 1)
    points = ((10 if correct else 2) if first_attempt else 0) + mastery_reward
    progress = award_progress(conn, points, correct=correct, reviewed=bool(mastery and mastery["mastered"])) if points else progress_payload(conn)
    return {
        "attempt_id": cursor.lastrowid,
        "quiz_id": quiz_data["id"],
        "correct": correct,
        "user_answer": selected,
        "confidence": confidence_score,
        "answer": quiz_data["answer"],
        "evidence": quiz_data.get("evidence") or "",
        "explanation": explanation,
        "skill": quiz_data.get("skill") or "阅读理解",
        "error_type": error_type,
        "elapsed_seconds": elapsed,
        "answer_changes": changes,
        "hint_used": bool(hint),
        "mastery": mastery,
        "points": points,
        "progress": progress,
    }


def practice_session_payload(row: sqlite3.Row | dict) -> dict:
    item = dict(row)
    item["skill_summary"] = json.loads(item.pop("skill_summary_json", "{}") or "{}")
    item["error_summary"] = json.loads(item.pop("error_summary_json", "{}") or "{}")
    item["confidence_summary"] = json.loads(item.pop("confidence_summary_json", "{}") or "{}")
    return item


def summarize_attempt_rows(rows: list[sqlite3.Row | dict], question_count: int | None = None) -> dict:
    values = [dict(row) for row in rows]
    total = max(len(values), int(question_count or 0))
    skill_summary: dict[str, dict[str, int]] = {}
    error_summary: dict[str, int] = {}
    confidence_summary: dict[str, dict[str, int]] = {}
    confidence_labels = {1: "猜测", 2: "犹豫", 3: "确定"}
    for item in values:
        skill = item.get("skill") or "阅读理解"
        skill_stats = skill_summary.setdefault(skill, {"total": 0, "correct": 0})
        skill_stats["total"] += 1
        skill_stats["correct"] += 1 if item.get("correct") else 0
        if item.get("error_type"):
            error_summary[item["error_type"]] = error_summary.get(item["error_type"], 0) + 1
        confidence = normalize_confidence(item.get("confidence"))
        if confidence:
            label = confidence_labels[confidence]
            confidence_stats = confidence_summary.setdefault(label, {"total": 0, "correct": 0})
            confidence_stats["total"] += 1
            confidence_stats["correct"] += 1 if item.get("correct") else 0
    unanswered = max(0, total - len(values))
    if unanswered:
        error_summary["未作答"] = unanswered
    correct_count = sum(1 for item in values if item.get("correct"))
    return {
        "question_count": total,
        "answered_count": len(values),
        "correct_count": correct_count,
        "score": round(correct_count / max(1, total) * 100),
        "skill_summary": skill_summary,
        "error_summary": error_summary,
        "confidence_summary": confidence_summary,
    }


def practice_session_detail(conn: sqlite3.Connection, session_id: int) -> dict | None:
    session = conn.execute(
        """
        SELECT s.*, a.title AS article_title
        FROM practice_sessions s
        LEFT JOIN articles a ON a.id = s.article_id
        WHERE s.id = ?
        """,
        (session_id,),
    ).fetchone()
    if not session:
        return None
    attempts = conn.execute(
        """
        SELECT at.id AS attempt_id, at.user_answer, at.confidence, at.elapsed_seconds,
               at.answer_changes, at.hint_used, at.correct, at.error_type, at.created_at,
               q.id AS quiz_id, q.prompt, q.answer, q.evidence, q.skill, q.question_type,
               q.difficulty, q.article_id, ar.title AS article_title
        FROM attempts at
        JOIN quizzes q ON q.id = at.quiz_id
        LEFT JOIN articles ar ON ar.id = q.article_id
        WHERE at.session_id = ?
        ORDER BY at.id
        """,
        (session_id,),
    ).fetchall()
    return {"session": practice_session_payload(session), "attempts": rows_to_dicts(attempts)}


def practice_analytics(style: str) -> dict:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT at.correct, at.error_type, at.created_at, q.skill, q.question_type
            FROM attempts at
            JOIN quizzes q ON q.id = at.quiz_id
            WHERE q.style = ?
            ORDER BY at.created_at, at.id
            """,
            (style,),
        ).fetchall()
        sessions = conn.execute(
            "SELECT * FROM practice_sessions WHERE style = ? ORDER BY completed_at DESC, id DESC LIMIT 8",
            (style,),
        ).fetchall()

    def grouped(key: str) -> list[dict]:
        buckets: dict[str, list[int]] = {}
        for row in rows:
            label = row[key] or "未分类"
            buckets.setdefault(label, []).append(1 if row["correct"] else 0)
        result = []
        for label, values in buckets.items():
            recent = values[-5:]
            previous = values[-10:-5]
            recent_accuracy = round(sum(recent) / len(recent) * 100)
            previous_accuracy = round(sum(previous) / len(previous) * 100) if previous else None
            result.append({
                "label": label,
                "total": len(values),
                "correct": sum(values),
                "accuracy": round(sum(values) / len(values) * 100),
                "recent_accuracy": recent_accuracy,
                "trend": recent_accuracy - previous_accuracy if previous_accuracy is not None else None,
            })
        return sorted(result, key=lambda item: (item["accuracy"], -item["total"], item["label"]))

    skill_stats = grouped("skill")
    type_stats = grouped("question_type")
    total = len(rows)
    correct = sum(1 for row in rows if row["correct"])
    weakest = skill_stats[0] if skill_stats else None
    weakest_type = type_stats[0] if type_stats else None
    return {
        "style": style,
        "summary": {"attempts": total, "correct": correct, "accuracy": round(correct / max(1, total) * 100)},
        "skills": skill_stats,
        "question_types": type_stats,
        "recent_sessions": [practice_session_payload(row) for row in sessions],
        "recommendation": {
            "skill": weakest["label"] if weakest else "",
            "question_type": weakest_type["label"] if weakest_type else "",
            "reason": f"当前最低正确率能力为 {weakest['label']}（{weakest['accuracy']}%）。" if weakest else "完成一次训练后生成建议。",
        },
    }


def parse_utc_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def calibration_evidence(period_start: datetime, period_end: datetime) -> dict:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT at.correct, at.confidence, at.created_at, at.session_id,
                   q.question_type, q.type AS quiz_type, q.skill, q.difficulty
            FROM attempts at
            JOIN quizzes q ON q.id = at.quiz_id
            WHERE at.session_id IS NOT NULL AND at.created_at >= ? AND at.created_at <= ?
            ORDER BY at.created_at, at.id
            """,
            (period_start.isoformat(), period_end.isoformat()),
        ).fetchall()
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        item = dict(row)
        domain = quiz_ability_domain(item["question_type"], item["quiz_type"], item["skill"])
        grouped.setdefault(domain, []).append(item)
    result = {}
    for domain in ABILITY_DOMAINS:
        items = grouped.get(domain, [])
        sessions = {item["session_id"] for item in items}
        active_days = {str(item["created_at"])[:10] for item in items}
        correct = sum(1 for item in items if item["correct"])
        certainty_errors = sum(1 for item in items if item["confidence"] == 3 and not item["correct"])
        difficulty_ranks = [CEFR_ORDER.get(str(item["difficulty"]), 4) for item in items]
        accuracy = round(correct / max(1, len(items)) * 100)
        difficulty_adjustment = round(((sum(difficulty_ranks) / max(1, len(difficulty_ranks))) - 4) * 3)
        performance = max(0, min(100, accuracy + difficulty_adjustment - min(6, certainty_errors * 2)))
        result[domain] = {
            "attempts": len(items), "correct": correct, "accuracy": accuracy,
            "sessions": len(sessions), "active_days": len(active_days),
            "certainty_errors": certainty_errors, "performance": performance,
            "eligible": len(items) >= 8 and len(sessions) >= 2 and len(active_days) >= 2,
        }
    return result


def profile_calibration_status(settings: dict | None = None, now: datetime | None = None) -> dict:
    settings = settings or learner_settings()
    now = now or datetime.now(timezone.utc)
    anchor = parse_utc_datetime(settings.get("last_calibration_at") or settings.get("profile_started_at") or "") or now
    due_at = anchor + timedelta(days=7)
    period_start = max(anchor, now - timedelta(days=7))
    evidence = calibration_evidence(period_start, now) if settings.get("profile_completed") else {}
    eligible_domains = [domain for domain, item in evidence.items() if item.get("eligible")]
    with db() as conn:
        history = rows_to_dicts(conn.execute(
            "SELECT * FROM profile_calibrations ORDER BY id DESC LIMIT 8"
        ).fetchall())
    for item in history:
        item["domains"] = json.loads(item.pop("domain_summary_json") or "{}")
        item["overall"] = json.loads(item.pop("overall_summary_json") or "{}")
    return {
        "profile_completed": bool(settings.get("profile_completed")),
        "due": bool(settings.get("profile_completed")) and now >= due_at,
        "due_at": due_at.isoformat(),
        "days_remaining": max(0, (due_at.date() - now.date()).days),
        "period_start": period_start.isoformat(),
        "period_end": now.isoformat(),
        "evidence": evidence,
        "eligible_domains": eligible_domains,
        "overall_requires": {"minimum_domains": 3, "receptive": ["reading", "listening"], "productive": ["writing", "speaking"]},
        "history": history,
    }


def run_profile_calibration(force: bool = False, now: datetime | None = None, trigger_type: str = "weekly") -> dict:
    now = now or datetime.now(timezone.utc)
    settings = learner_settings()
    status = profile_calibration_status(settings, now)
    if not settings.get("profile_completed") or (not force and not status["due"]):
        return {**status, "ran": False}
    profile = learner_profile_summary(settings)
    domains = initial_ability_domains(settings, profile["cefr"])
    domain_summary = {}
    eligible = []
    for domain, evidence in status["evidence"].items():
        current = domains[domain]
        if evidence["eligible"]:
            delta = max(-4, min(4, round((evidence["performance"] - 65) / 7)))
            new_score = max(0, min(100, round(current["score"] + delta, 1)))
            updated = {
                **current, "score": new_score, "cefr": cefr_from_ability_score(new_score),
                "confidence": "high" if current["evidence_count"] + evidence["attempts"] >= 20 else "medium",
                "evidence_count": current["evidence_count"] + evidence["attempts"], "updated_at": now.isoformat(),
            }
            domains[domain] = updated
            eligible.append(domain)
            domain_summary[domain] = {**evidence, "before": current, "after": updated, "delta": delta, "adjusted": True}
        else:
            domain_summary[domain] = {**evidence, "before": current, "after": current, "delta": 0, "adjusted": False}
    receptive = bool(set(eligible) & {"reading", "listening"})
    productive = bool(set(eligible) & {"writing", "speaking"})
    overall_eligible = len(eligible) >= 3 and receptive and productive
    previous_overall = settings.get("overall_ability") if isinstance(settings.get("overall_ability"), dict) else {}
    if overall_eligible:
        overall_score = round(sum(domains[domain]["score"] for domain in ABILITY_DOMAINS) / len(ABILITY_DOMAINS), 1)
        overall = {"adjusted": True, "score": overall_score, "cefr": cefr_from_ability_score(overall_score), "coverage": eligible, "updated_at": now.isoformat()}
    else:
        overall = {
            "adjusted": False, "cefr": previous_overall.get("cefr") or profile["cefr"],
            "score": previous_overall.get("score", ABILITY_SCORE_BY_CEFR[profile["cefr"]]),
            "coverage": eligible, "reason": "综合等级至少需要 3 个分项，并同时包含输入与输出能力证据。",
        }
    overall["algorithm"] = "weekly-rule-v1"
    settings["ability_domains"] = domains
    settings["overall_ability"] = overall
    settings["last_calibration_at"] = now.isoformat()
    save_learner_settings(settings)
    with db() as conn:
        conn.execute(
            """INSERT INTO profile_calibrations
               (period_start, period_end, trigger_type, domain_summary_json, overall_summary_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (status["period_start"], status["period_end"], trigger_type,
             json.dumps(domain_summary, ensure_ascii=False), json.dumps(overall, ensure_ascii=False), now.isoformat()),
        )
    return {**profile_calibration_status(settings, now), "ran": True, "domains": domain_summary, "overall": overall}


def browser_bridge_token() -> str:
    with db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = 'browser_bridge_token'").fetchone()
    return row["value"] if row else ""


def translation_status() -> dict:
    deepl_configured = bool(os.environ.get("DEEPL_API_KEY", "").strip())
    libre_url = os.environ.get("LIBRETRANSLATE_URL", "").strip().rstrip("/")
    preferred = os.environ.get("TRANSLATION_PROVIDER", "").strip().lower()
    if preferred not in {"deepl", "libretranslate"}:
        preferred = "deepl" if deepl_configured else "libretranslate" if libre_url else "deepl"
    configured = deepl_configured if preferred == "deepl" else bool(libre_url)
    return {
        "provider": "DeepL" if preferred == "deepl" else "LibreTranslate",
        "provider_id": preferred,
        "configured": configured,
        "verified": TRANSLATION_RUNTIME["verified"] if preferred == "deepl" else None,
        "last_error": TRANSLATION_RUNTIME["last_error"] if preferred == "deepl" else "",
        "target_language": "ZH-HANS",
        "options": [
            {"id": "deepl", "label": "DeepL API Free", "configured": deepl_configured, "hosted": True},
            {"id": "libretranslate", "label": "LibreTranslate 自托管", "configured": bool(libre_url), "hosted": False},
            {"id": "manual", "label": "手动逐段译文", "configured": True, "hosted": False},
        ],
    }


def verify_deepl_configuration() -> dict:
    key = os.environ.get("DEEPL_API_KEY", "").strip()
    if not key:
        TRANSLATION_RUNTIME.update({"verified": False, "last_error": "DeepL API Key 未填写。", "deepl_url": ""})
        return translation_status()
    configured_url = os.environ.get("DEEPL_API_URL", "https://api-free.deepl.com/v2/translate").strip()
    candidates = [configured_url]
    alternative = (
        "https://api.deepl.com/v2/translate"
        if "api-free.deepl.com" in configured_url
        else "https://api-free.deepl.com/v2/translate"
    )
    if alternative not in candidates:
        candidates.append(alternative)
    errors = []
    for endpoint in candidates:
        usage_url = endpoint.rsplit("/", 1)[0] + "/usage"
        request = urllib.request.Request(usage_url, headers={"Authorization": f"DeepL-Auth-Key {key}"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                response.read()
            TRANSLATION_RUNTIME.update({"verified": True, "last_error": "", "deepl_url": endpoint})
            return translation_status()
        except urllib.error.HTTPError as error:
            errors.append(error.code)
            error.close()
        except urllib.error.URLError as error:
            errors.append(f"network:{type(error.reason).__name__}")
        except Exception as error:
            errors.append(type(error).__name__)
    if 403 in errors:
        message = "DeepL 拒绝了当前 API Key（403），请使用 DeepL API 账户生成的有效密钥。"
    elif any(str(value).startswith("network:") for value in errors):
        detail = ", ".join(str(value).split(":", 1)[1] for value in errors if str(value).startswith("network:"))
        message = f"当前网络无法连接 DeepL 验证接口（{detail}）；尚未验证 API Key 是否有效。"
    else:
        message = "无法连接 DeepL 验证接口；尚未验证 API Key 是否有效。"
    TRANSLATION_RUNTIME.update({"verified": False, "last_error": message, "deepl_url": ""})
    return translation_status()


def translate_with_deepl(missing: list[tuple[int, str, str]], source_lang: str, target_lang: str) -> list[str]:
    api_key = os.environ.get("DEEPL_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DeepL API key is not configured. Add DEEPL_API_KEY to .env.local and restart the server.")
    endpoint = TRANSLATION_RUNTIME["deepl_url"] or os.environ.get("DEEPL_API_URL", "https://api-free.deepl.com/v2/translate")
    translated: list[str] = []
    for start in range(0, len(missing), 40):
        batch = missing[start:start + 40]
        fields = [("text", segment) for _, segment, _ in batch]
        fields.extend([("source_lang", source_lang), ("target_lang", target_lang)])
        request = urllib.request.Request(
            endpoint,
            data=urllib.parse.urlencode(fields).encode("utf-8"),
            headers={"Authorization": f"DeepL-Auth-Key {api_key}", "Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 403:
                TRANSLATION_RUNTIME.update({
                    "verified": False,
                    "last_error": "DeepL 拒绝了当前 API Key 或接口地址（403）。请重新生成 DeepL API 密钥。",
                    "deepl_url": "",
                })
                raise RuntimeError(TRANSLATION_RUNTIME["last_error"]) from error
            if error.code == 456:
                raise RuntimeError("DeepL translation quota has been exhausted (456).") from error
            raise RuntimeError(f"DeepL request failed with HTTP {error.code}.") from error
        translated.extend(item["text"] for item in payload.get("translations", []))
    TRANSLATION_RUNTIME.update({"verified": True, "last_error": "", "deepl_url": endpoint})
    return translated


def translate_with_libre(missing: list[tuple[int, str, str]], source_lang: str, target_lang: str) -> list[str]:
    base_url = os.environ.get("LIBRETRANSLATE_URL", "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError("LibreTranslate is not configured. Add LIBRETRANSLATE_URL to .env.local and restart the server.")
    api_key = os.environ.get("LIBRETRANSLATE_API_KEY", "").strip()
    translated: list[str] = []
    for _, segment, _ in missing:
        body = {"q": segment, "source": source_lang.lower(), "target": "zh", "format": "text"}
        if api_key:
            body["api_key"] = api_key
        request = urllib.request.Request(
            f"{base_url}/translate",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
        translated.append(payload.get("translatedText") or "")
    return translated


def translate_segments(segments: list[str], source_lang: str = "EN", target_lang: str = "ZH-HANS") -> dict:
    source_segments = [(segment or "").strip() for segment in segments if (segment or "").strip()]
    if not source_segments:
        raise ValueError("Text is required")
    if len(source_segments) > 200 or any(len(segment) > 8000 for segment in source_segments):
        raise ValueError("Translate at most 200 segments and 8000 characters per segment")
    status = translation_status()
    provider = status["provider_id"]
    cached_by_hash: dict[str, str] = {}
    hashes = [hashlib.sha256(segment.encode("utf-8")).hexdigest() for segment in source_segments]
    with db() as conn:
        placeholders = ",".join("?" for _ in hashes)
        rows = conn.execute(
            f"SELECT text_hash, translated_text FROM translation_cache WHERE text_hash IN ({placeholders}) AND source_lang = ? AND target_lang = ? AND provider = ?",
            (*hashes, source_lang, target_lang, provider),
        ).fetchall()
        cached_by_hash = {row["text_hash"]: row["translated_text"] for row in rows}

    missing = [(index, source_segments[index], hashes[index]) for index in range(len(source_segments)) if hashes[index] not in cached_by_hash]
    translated_missing: list[str] = []
    if missing:
        translated_missing = (
            translate_with_deepl(missing, source_lang, target_lang)
            if provider == "deepl"
            else translate_with_libre(missing, source_lang, target_lang)
        )
        if len(translated_missing) != len(missing):
            raise RuntimeError("DeepL returned an unexpected number of translated segments")
        with db() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO translation_cache
                   (text_hash, source_lang, target_lang, provider, source_text, translated_text, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (digest, source_lang, target_lang, provider, source, translated, utc_now())
                    for (_, source, digest), translated in zip(missing, translated_missing)
                ],
            )
        cached_by_hash.update({digest: translated for (_, _, digest), translated in zip(missing, translated_missing)})

    translated_segments = [cached_by_hash[digest] for digest in hashes]
    return {
        "source_segments": source_segments,
        "translated_segments": translated_segments,
        "provider": status["provider"],
        "cached": not missing,
    }


def translate_text(text: str, source_lang: str = "EN", target_lang: str = "ZH-HANS") -> dict:
    result = translate_segments([text], source_lang, target_lang)
    return {
        "source_text": result["source_segments"][0],
        "translated_text": result["translated_segments"][0],
        "provider": result["provider"],
        "cached": result["cached"],
    }


FEED_REFRESH_LOCK = threading.Lock()
FEED_REFRESH_HOURS = max(1, int(os.environ.get("FEED_REFRESH_HOURS", "6")))


def feed_entry_text(entry: ET.Element, *names: str) -> str:
    for name in names:
        for node in entry.iter():
            if xml_local_name(node.tag) == name and (node.text or "").strip():
                return node.text or ""
    return ""


def feed_entry_author(entry: ET.Element) -> str:
    author_node = next((node for node in entry.iter() if xml_local_name(node.tag) == "author"), None)
    if author_node is None:
        return ""
    name_node = next((node for node in author_node.iter() if xml_local_name(node.tag) == "name"), None)
    value = "".join((name_node or author_node).itertext())
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def extract_article_semantic_blocks(text: str, source: str, author: str = "") -> dict:
    return extract_source_content(text, source, author)


def extraction_quality_report() -> dict:
    with db() as conn:
        rows = conn.execute(
            """SELECT a.source, a.extraction_version, COUNT(DISTINCT a.id) AS article_count,
                      COUNT(f.id) AS feedback_count,
                      SUM(CASE WHEN f.verdict != 'correct' THEN 1 ELSE 0 END) AS issue_count
               FROM articles a
               LEFT JOIN article_extraction_feedback f ON f.article_id = a.id
               WHERE a.source != ''
               GROUP BY a.source, a.extraction_version
               ORDER BY issue_count DESC, feedback_count DESC, article_count DESC"""
        ).fetchall()
        totals = conn.execute(
            """SELECT COUNT(*) AS feedback_count,
                      SUM(CASE WHEN verdict != 'correct' THEN 1 ELSE 0 END) AS issue_count
               FROM article_extraction_feedback"""
        ).fetchone()
        block_labels = conn.execute(
            "SELECT COUNT(*) FROM article_extraction_block_labels WHERE label != 'unsure'"
        ).fetchone()[0]
        corrected_blocks = conn.execute(
            """SELECT COUNT(*) FROM article_extraction_block_labels
               WHERE label != 'unsure' AND label != suggested_label"""
        ).fetchone()[0]
        reviewed_articles = conn.execute(
            """SELECT COUNT(DISTINCT article_id) FROM (
                 SELECT article_id FROM article_extraction_feedback
                 UNION ALL
                 SELECT article_id FROM article_extraction_block_labels
               )"""
        ).fetchone()[0]
        reviewed_sources = conn.execute(
            """SELECT COUNT(DISTINCT source) FROM (
                 SELECT a.source AS source FROM article_extraction_feedback f JOIN articles a ON a.id = f.article_id
                 UNION ALL
                 SELECT source FROM article_extraction_block_labels
               ) WHERE source != ''"""
        ).fetchone()[0]
    reviewed_articles = int(reviewed_articles or 0)
    issue_count = int(totals["issue_count"] or 0) + int(corrected_blocks or 0)
    thresholds = {"reviewed_articles": 100, "issue_examples": 25, "reviewed_sources": 3, "block_labels": 500}
    observed = {
        "reviewed_articles": reviewed_articles,
        "issue_examples": issue_count,
        "reviewed_sources": int(reviewed_sources or 0),
        "block_labels": int(block_labels or 0),
    }
    unmet = [key for key, minimum in thresholds.items() if observed[key] < minimum]
    return {
        "adapters": adapter_catalog(),
        "sources": [dict(row) for row in rows],
        "feedback_count": int(totals["feedback_count"] or 0),
        "classifier_readiness": {
            "ready": not unmet,
            "thresholds": thresholds,
            "observed": observed,
            "unmet": unmet,
            "policy": "A classifier may label blocks but must not rewrite text or bypass deterministic quality gates.",
        },
    }


BLOCK_LABEL_NAMES = {
    "body": "正文",
    "author": "作者",
    "image_caption": "图片说明",
    "disclosure": "披露",
    "boilerplate": "订阅噪声",
    "unsure": "不确定",
}


def extraction_annotation_payload(conn: sqlite3.Connection, article_id: int) -> dict | None:
    article = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    if not article:
        return None
    audit = conn.execute(
        "SELECT original_body FROM article_extraction_audits WHERE article_id = ? ORDER BY id LIMIT 1",
        (article_id,),
    ).fetchone()
    source_text = audit["original_body"] if audit else article["body"]
    blocks = suggest_annotation_blocks(
        source_text,
        article["source"],
        article["author"],
        article["image_caption"],
        article["disclosure"],
    )
    labels = {
        row["block_hash"]: dict(row)
        for row in conn.execute(
            "SELECT * FROM article_extraction_block_labels WHERE article_id = ?", (article_id,)
        ).fetchall()
    }
    for block in blocks:
        saved = labels.get(block["block_hash"])
        block["label"] = saved["label"] if saved else ""
        block["labeled_at"] = saved["updated_at"] if saved else ""
    labeled = sum(bool(block["label"]) for block in blocks)
    usable = sum(block["label"] not in {"", "unsure"} for block in blocks)
    return {
        "article": {
            "id": article["id"],
            "title": article["title"],
            "source": article["source"],
            "extraction_version": article["extraction_version"],
        },
        "blocks": blocks,
        "labels": [{"id": label, "label": BLOCK_LABEL_NAMES[label]} for label in BLOCK_LABELS],
        "summary": {"total": len(blocks), "labeled": labeled, "usable": usable, "remaining": len(blocks) - labeled},
    }


def create_extraction_review_batch(conn: sqlite3.Connection, target_size: int = 20, force_new: bool = False) -> dict:
    target_size = max(4, min(int(target_size or 20), 40))
    if not force_new:
        active = conn.execute(
            "SELECT id FROM article_extraction_review_batches WHERE status = 'active' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if active:
            return extraction_review_batch_payload(conn, active["id"])
    rows = conn.execute(
        """SELECT a.*, COUNT(DISTINCT l.id) AS label_count,
                  COUNT(DISTINCT CASE WHEN f.verdict IS NOT NULL AND f.verdict != 'correct' THEN f.id END) AS issue_count
           FROM articles a
           LEFT JOIN article_extraction_block_labels l ON l.article_id = a.id
           LEFT JOIN article_extraction_feedback f ON f.article_id = a.id
           WHERE a.extraction_version != '' AND a.body != ''
           GROUP BY a.id
           ORDER BY label_count, issue_count DESC,
                    CASE WHEN a.content_status = 'full' THEN 0 ELSE 1 END,
                    a.published_at DESC, a.id DESC"""
    ).fetchall()
    groups: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        adapter = adapter_for_source(row["source"])
        if adapter.key == "generic":
            continue
        groups.setdefault(adapter.key, []).append(row)
    adapter_keys = [key for key in ("conversation", "bbc", "guardian", "jstor") if groups.get(key)]
    selected: list[tuple[str, sqlite3.Row]] = []
    quota = max(1, target_size // max(1, len(adapter_keys)))
    for key in adapter_keys:
        selected.extend((key, row) for row in groups[key][:quota])
        groups[key] = groups[key][quota:]
    while len(selected) < target_size and any(groups.get(key) for key in adapter_keys):
        for key in adapter_keys:
            if len(selected) >= target_size:
                break
            if groups.get(key):
                selected.append((key, groups[key].pop(0)))
    if not selected:
        raise ValueError("No eligible source-adapter articles are available for extraction review")
    now = utc_now()
    cursor = conn.execute(
        """INSERT INTO article_extraction_review_batches (name, target_size, status, created_at)
           VALUES (?, ?, 'active', ?)""",
        (f"代表性来源抽检 {now[:10]}", len(selected), now),
    )
    batch_id = cursor.lastrowid
    for position, (adapter, row) in enumerate(selected, start=1):
        annotation = extraction_annotation_payload(conn, row["id"])
        conn.execute(
            """INSERT INTO article_extraction_review_items
               (batch_id, article_id, position, source, adapter, extraction_version, total_blocks)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (batch_id, row["id"], position, row["source"], adapter, row["extraction_version"], annotation["summary"]["total"]),
        )
    return extraction_review_batch_payload(conn, batch_id)


def extraction_review_batch_payload(conn: sqlite3.Connection, batch_id: int) -> dict | None:
    batch = conn.execute("SELECT * FROM article_extraction_review_batches WHERE id = ?", (batch_id,)).fetchone()
    if not batch:
        return None
    rows = conn.execute(
        """SELECT i.*, a.title, a.content_status FROM article_extraction_review_items i
           JOIN articles a ON a.id = i.article_id WHERE i.batch_id = ? ORDER BY i.position""",
        (batch_id,),
    ).fetchall()
    items = []
    confusion: dict[tuple[str, str], int] = {}
    accepted = corrected = unsure = usable = 0
    source_stats: dict[str, dict] = {}
    completed_seconds = []
    for row in rows:
        annotation = extraction_annotation_payload(conn, row["article_id"])
        summary = annotation["summary"]
        status = "completed" if summary["total"] and summary["remaining"] == 0 else "in_progress" if summary["labeled"] else row["status"]
        completed_at = row["completed_at"]
        if status == "completed" and not completed_at:
            completed_at = utc_now()
        conn.execute(
            """UPDATE article_extraction_review_items SET total_blocks = ?, status = ?, completed_at = ? WHERE id = ?""",
            (summary["total"], status, completed_at, row["id"]),
        )
        if status == "completed":
            completed_seconds.append(row["active_seconds"])
        stats = source_stats.setdefault(row["adapter"], {"adapter": row["adapter"], "articles": 0, "completed": 0, "labels": 0, "corrected": 0})
        stats["articles"] += 1
        stats["completed"] += int(status == "completed")
        for block in annotation["blocks"]:
            label = block["label"]
            if not label:
                continue
            if label == "unsure":
                unsure += 1
                continue
            usable += 1
            stats["labels"] += 1
            if label == block["suggested_label"]:
                accepted += 1
            else:
                corrected += 1
                stats["corrected"] += 1
            confusion[(block["suggested_label"], label)] = confusion.get((block["suggested_label"], label), 0) + 1
        items.append({
            "id": row["id"], "article_id": row["article_id"], "position": row["position"],
            "title": row["title"], "source": row["source"], "adapter": row["adapter"],
            "content_status": row["content_status"], "status": status,
            "active_seconds": row["active_seconds"], **summary,
        })
    completed = sum(item["status"] == "completed" for item in items)
    batch_status = "completed" if items and completed == len(items) else "active"
    completed_at = batch["completed_at"] or (utc_now() if batch_status == "completed" else "")
    conn.execute(
        "UPDATE article_extraction_review_batches SET status = ?, completed_at = ? WHERE id = ?",
        (batch_status, completed_at, batch_id),
    )
    return {
        "batch": {**dict(batch), "status": batch_status, "completed_at": completed_at},
        "items": items,
        "summary": {"total": len(items), "completed": completed, "remaining": len(items) - completed},
        "analytics": {
            "usable_labels": usable,
            "accepted_suggestions": accepted,
            "corrected_suggestions": corrected,
            "unsure_labels": unsure,
            "suggestion_hit_rate": round(accepted / usable, 4) if usable else None,
            "average_active_minutes": round(sum(completed_seconds) / len(completed_seconds) / 60, 1) if completed_seconds else None,
            "confusion": [
                {"suggested_label": source, "label": target, "count": count}
                for (source, target), count in sorted(confusion.items()) if source != target
            ],
            "sources": list(source_stats.values()),
        },
    }
def parse_feed_datetime(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    try:
        parsed = email.utils.parsedate_to_datetime(raw)
        if parsed:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        pass
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        return ""


def feed_entry_payload(entry: ET.Element, feed: dict) -> dict:
    title = clean_html(feed_entry_text(entry, "title") or "Untitled")
    link = feed_entry_text(entry, "link").strip()
    if not link:
        link_node = next((node for node in entry.iter() if xml_local_name(node.tag) == "link"), None)
        if link_node is not None:
            link = link_node.attrib.get("href", "").strip()
    guid = feed_entry_text(entry, "guid", "id").strip()
    summary = feed_entry_text(entry, "description", "summary") or title
    encoded = feed_entry_text(entry, "encoded", "content")
    summary_text = clean_html(summary)
    encoded_text = clean_html(encoded)
    use_full = len(words(encoded_text)) >= 250 and len(encoded_text) > len(summary_text)
    semantic = extract_article_semantic_blocks(encoded_text if use_full else summary_text, feed["name"], feed_entry_author(entry))
    body = normalize_article_text(title, semantic["body"], preserve_blocks=True)
    published_at = parse_feed_datetime(feed_entry_text(entry, "pubDate", "published", "updated"))
    return {
        "title": title,
        "link": link,
        "guid": guid,
        "body": body,
        "content_hash": hashlib.sha256(body.casefold().encode("utf-8")).hexdigest() if body else "",
        "content_status": "full" if use_full else "summary",
        "content_type": infer_content_type({"source": feed["name"], "title": title, "body": body}),
        "published_at": published_at,
        "author": semantic["author"],
        "image_caption": semantic["image_caption"],
        "disclosure": semantic["disclosure"],
        "extraction_version": semantic["extraction_version"],
        "extraction_confidence": semantic["extraction_confidence"],
        "extraction_notes_json": json.dumps({"removed_blocks": semantic["removed_blocks"], "review_status": "automatic"}, ensure_ascii=False),
    }


def upsert_feed_article(conn: sqlite3.Connection, feed: dict, item: dict, now: str) -> str:
    item = {
        "author": "", "image_caption": "", "disclosure": "",
        "extraction_version": "legacy-feed", "extraction_confidence": 0,
        "extraction_notes_json": "{}", **item,
    }
    conditions = []
    params: list[object] = []
    if item["link"]:
        conditions.append("source_url = ?")
        params.append(item["link"])
    if item["guid"]:
        conditions.append("(source = ? AND source_guid = ?)")
        params.extend([feed["name"], item["guid"]])
    if item["content_hash"]:
        conditions.append("(source = ? AND content_hash = ?)")
        params.extend([feed["name"], item["content_hash"]])
    existing = conn.execute(
        "SELECT * FROM articles WHERE " + " OR ".join(conditions) + " ORDER BY id LIMIT 1", params
    ).fetchone() if conditions else None
    if not existing:
        conn.execute(
            """INSERT INTO articles
               (title, language, level, topic, source, source_url, content_status, content_type,
                body, author, image_caption, disclosure, extraction_version, extraction_confidence,
                extraction_notes_json, published_at, source_guid, content_hash, created_at, updated_at)
               VALUES (?, ?, ?, 'feed', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (item["title"], feed["language"], feed["level_hint"], feed["name"], item["link"],
             item["content_status"], item["content_type"], item["body"], item["author"], item["image_caption"],
             item["disclosure"], item["extraction_version"], item["extraction_confidence"], item["extraction_notes_json"], item["published_at"],
             item["guid"], item["content_hash"], now, now),
        )
        return "imported"
    body = item["body"] if item.get("extraction_version") or len(item["body"]) > len(existing["body"]) else existing["body"]
    body_changed = body != existing["body"]
    status = "full" if item["content_status"] == "full" or existing["content_status"] == "full" else "summary"
    changed = any([
        item["title"] != existing["title"], body != existing["body"], status != existing["content_status"],
        item["content_type"] != existing["content_type"], body_changed,
        item["author"] != existing["author"], item["image_caption"] != existing["image_caption"],
        item["disclosure"] != existing["disclosure"], item["extraction_version"] != existing["extraction_version"],
        bool(item["published_at"] and item["published_at"] != existing["published_at"]),
    ])
    if not changed:
        return "unchanged"
    conn.execute(
        """UPDATE articles SET title = ?, source_url = CASE WHEN source_url = '' THEN ? ELSE source_url END,
           content_status = ?, content_type = ?, body = ?, author = ?, image_caption = ?, disclosure = ?,
           extraction_version = ?, extraction_confidence = ?, extraction_notes_json = ?,
           translation_zh = CASE WHEN ? THEN '' ELSE translation_zh END,
           published_at = CASE WHEN ? != '' THEN ? ELSE published_at END,
           source_guid = CASE WHEN source_guid = '' THEN ? ELSE source_guid END,
           content_hash = ?, updated_at = ? WHERE id = ?""",
        (item["title"], item["link"], status, item["content_type"], body, item["author"], item["image_caption"],
         item["disclosure"], item["extraction_version"], item["extraction_confidence"], item["extraction_notes_json"], int(body_changed),
         item["published_at"], item["published_at"], item["guid"], item["content_hash"], now, existing["id"]),
    )
    return "updated"


def feed_retry_ready(feed: dict, now: datetime | None = None) -> bool:
    failures = int(feed.get("consecutive_failures") or 0)
    if failures <= 0 or not feed.get("last_attempt_at"):
        return True
    try:
        attempted = datetime.fromisoformat(str(feed["last_attempt_at"])).astimezone(timezone.utc)
    except ValueError:
        return True
    delay_minutes = min(360, 15 * (2 ** min(5, failures - 1)))
    return ((now or datetime.now(timezone.utc)) - attempted).total_seconds() >= delay_minutes * 60


def fetch_feed_items(limit_per_feed: int = 4, trigger_type: str = "manual") -> dict:
    if not FEED_REFRESH_LOCK.acquire(blocking=False):
        return {"status": "busy", "imported": 0, "updated": 0, "unchanged": 0, "errors": []}
    started_at = utc_now()
    try:
        with db() as conn:
            run_id = conn.execute(
                "INSERT INTO feed_refresh_runs (trigger_type, started_at) VALUES (?, ?)", (trigger_type, started_at)
            ).lastrowid
            feeds = rows_to_dicts(conn.execute("SELECT * FROM feeds WHERE active = 1 ORDER BY id").fetchall())
        totals = {"imported": 0, "updated": 0, "unchanged": 0}
        errors: list[str] = []
        for feed in feeds:
            source_started = time.perf_counter()
            counts = {"imported": 0, "updated": 0, "unchanged": 0}
            if trigger_type != "manual" and not feed_retry_ready(feed):
                with db() as conn:
                    conn.execute(
                        """INSERT INTO feed_refresh_sources
                           (run_id, feed_id, status, duration_ms, created_at) VALUES (?, ?, 'backoff', 0, ?)""",
                        (run_id, feed["id"], utc_now()),
                    )
                continue
            status = "success"
            http_status = 0
            error_text = ""
            attempt_at = utc_now()
            try:
                headers = {"User-Agent": "LanguageCoachV2/0.8 (+local-reader)"}
                if feed.get("etag"):
                    headers["If-None-Match"] = feed["etag"]
                if feed.get("last_modified"):
                    headers["If-Modified-Since"] = feed["last_modified"]
                request = urllib.request.Request(feed["url"], headers=headers)
                try:
                    response_context = urllib.request.urlopen(request, timeout=12)
                except urllib.error.HTTPError as exc:
                    if exc.code == 304:
                        response_context = exc
                    else:
                        raise
                with response_context as response:
                    http_status = getattr(response, "status", None) or response.getcode()
                    raw = b"" if http_status == 304 else response.read(10 * 1024 * 1024 + 1)
                    response_headers = response.headers
                if len(raw) > 10 * 1024 * 1024:
                    raise ValueError("Feed response exceeds 10 MB")
                if http_status == 304:
                    status = "not_modified"
                else:
                    root = ET.fromstring(raw)
                    entries = [node for node in root.iter() if xml_local_name(node.tag) in {"item", "entry"}]
                    with db() as conn:
                        for entry in entries[:limit_per_feed]:
                            item = feed_entry_payload(entry, feed)
                            if not item["body"]:
                                continue
                            outcome = upsert_feed_article(conn, feed, item, attempt_at)
                            counts[outcome] += 1
                with db() as conn:
                    conn.execute(
                        """UPDATE feeds SET etag = ?, last_modified = ?, last_attempt_at = ?, last_success_at = ?,
                           consecutive_failures = 0, last_error = '' WHERE id = ?""",
                        (response_headers.get("ETag", feed.get("etag", "")),
                         response_headers.get("Last-Modified", feed.get("last_modified", "")),
                         attempt_at, attempt_at, feed["id"]),
                    )
            except Exception as exc:  # A single source must not abort the refresh run.
                status = "error"
                error_text = str(exc)[:500]
                errors.append(f"{feed['name']}: {error_text}")
                with db() as conn:
                    conn.execute(
                        """UPDATE feeds SET last_attempt_at = ?, consecutive_failures = consecutive_failures + 1,
                           last_error = ? WHERE id = ?""", (attempt_at, error_text, feed["id"]),
                    )
            for key in totals:
                totals[key] += counts[key]
            with db() as conn:
                conn.execute(
                    """INSERT INTO feed_refresh_sources
                       (run_id, feed_id, status, http_status, imported_count, updated_count,
                        unchanged_count, duration_ms, error, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (run_id, feed["id"], status, http_status, counts["imported"], counts["updated"],
                     counts["unchanged"], round((time.perf_counter() - source_started) * 1000), error_text, utc_now()),
                )
        completed_at = utc_now()
        run_status = "success" if not errors else "partial" if len(errors) < len(feeds) else "failed"
        with db() as conn:
            conn.execute(
                """UPDATE feed_refresh_runs SET status = ?, imported_count = ?, updated_count = ?,
                   unchanged_count = ?, error_count = ?, completed_at = ? WHERE id = ?""",
                (run_status, totals["imported"], totals["updated"], totals["unchanged"], len(errors), completed_at, run_id),
            )
        return {"status": run_status, "run_id": run_id, **totals, "errors": errors, "completed_at": completed_at}
    finally:
        FEED_REFRESH_LOCK.release()


def feed_refresh_due(hours: int = FEED_REFRESH_HOURS) -> bool:
    with db() as conn:
        row = conn.execute(
            "SELECT completed_at FROM feed_refresh_runs WHERE status IN ('success', 'partial') ORDER BY id DESC LIMIT 1"
        ).fetchone()
        failed_sources = rows_to_dicts(conn.execute(
            "SELECT consecutive_failures, last_attempt_at FROM feeds WHERE active = 1 AND consecutive_failures > 0"
        ).fetchall())
    if any(feed_retry_ready(feed) for feed in failed_sources):
        return True
    if not row or not row["completed_at"]:
        return True
    try:
        completed = datetime.fromisoformat(row["completed_at"])
        return (datetime.now(timezone.utc) - completed.astimezone(timezone.utc)).total_seconds() >= hours * 3600
    except ValueError:
        return True


def feed_refresh_status() -> dict:
    with db() as conn:
        latest = conn.execute("SELECT * FROM feed_refresh_runs ORDER BY id DESC LIMIT 1").fetchone()
        feeds = rows_to_dicts(conn.execute(
            """SELECT id, name, active, last_attempt_at, last_success_at, consecutive_failures, last_error
               FROM feeds ORDER BY name"""
        ).fetchall())
    return {
        "refreshing": FEED_REFRESH_LOCK.locked(),
        "due": feed_refresh_due(),
        "interval_hours": FEED_REFRESH_HOURS,
        "latest_run": dict(latest) if latest else None,
        "sources": feeds,
    }


def request_feed_refresh(trigger_type: str = "startup") -> bool:
    if FEED_REFRESH_LOCK.locked():
        return False
    threading.Thread(target=fetch_feed_items, kwargs={"trigger_type": trigger_type}, daemon=True).start()
    return True


def start_feed_scheduler() -> None:
    def loop() -> None:
        if feed_refresh_due():
            request_feed_refresh("startup")
        while True:
            time.sleep(300)
            if feed_refresh_due():
                request_feed_refresh("scheduled")
    threading.Thread(target=loop, name="language-coach-feed-scheduler", daemon=True).start()


class App(BaseHTTPRequestHandler):
    server_version = "LanguageCoachV2/0.1"

    def end_headers(self) -> None:
        origin = self.headers.get("Origin", "")
        if origin.startswith(("chrome-extension://", "edge-extension://", "http://127.0.0.1:", "http://localhost:")):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Private-Network", "true")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Language-Coach-Token, X-Audio-Duration")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def browser_authorized(self) -> bool:
        supplied = self.headers.get("X-Language-Coach-Token", "")
        expected = browser_bridge_token()
        return bool(supplied and expected and secrets.compare_digest(supplied, expected))

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path == "/api/health":
                return json_response(self, {
                    "ok": True, "database": str(DB_PATH), "time": utc_now(), **runtime_metadata(),
                })
            if path == "/api/version":
                return json_response(self, runtime_metadata())
            if path == "/api/backups":
                return json_response(self, {"backups": list_backups(BACKUP_DIR)})
            if path == "/api/progress":
                with db() as conn:
                    return json_response(self, {"progress": progress_payload(conn)})
            if path == "/api/learner-settings":
                settings = learner_settings()
                return json_response(self, {"settings": settings, "profile": learner_profile_summary(settings)})
            if path == "/api/profile/quick-test":
                return json_response(self, {"items": quick_test_payload(), "estimated_minutes": 8, "domains": ["reading", "vocabulary"]})
            if path == "/api/profile/calibration":
                return json_response(self, profile_calibration_status())
            if path == "/api/feeds/status":
                return json_response(self, feed_refresh_status())
            if path == "/api/extraction/quality":
                return json_response(self, extraction_quality_report())
            if path == "/api/extraction/review-batches/active":
                with db() as conn:
                    row = conn.execute(
                        "SELECT id FROM article_extraction_review_batches WHERE status = 'active' ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                    batch = extraction_review_batch_payload(conn, row["id"]) if row else None
                return json_response(self, batch) if batch else json_response(self, {"error": "No active review batch"}, 404)
            match = re.fullmatch(r"/api/extraction/review-batches/(\d+)", path)
            if match:
                with db() as conn:
                    batch = extraction_review_batch_payload(conn, int(match.group(1)))
                return json_response(self, batch) if batch else json_response(self, {"error": "Review batch not found"}, 404)
            match = re.fullmatch(r"/api/articles/(\d+)/extraction-blocks", path)
            if match:
                with db() as conn:
                    annotation = extraction_annotation_payload(conn, int(match.group(1)))
                return json_response(self, annotation) if annotation else json_response(self, {"error": "Article not found"}, 404)
            if path == "/api/books":
                with db() as conn:
                    books = [book_detail(conn, row["id"], include_chapters=False) for row in conn.execute(
                        "SELECT id FROM books ORDER BY updated_at DESC, id DESC"
                    ).fetchall()]
                return json_response(self, {"books": books})
            match = re.fullmatch(r"/api/books/(\d+)", path)
            if match:
                with db() as conn:
                    book = book_detail(conn, int(match.group(1)))
                return json_response(self, {"book": book}) if book else json_response(self, {"error": "Book not found"}, 404)
            if path == "/api/daily-plan":
                return json_response(self, {"plan": daily_plan_snapshot()})
            if path == "/api/output/tasks":
                try:
                    article_id = int(query.get("article_id", [""])[0])
                except (TypeError, ValueError):
                    return json_response(self, {"error": "article_id is required"}, 400)
                with db() as conn:
                    task_set = latest_output_task_set(conn, article_id)
                return json_response(self, task_set or {"set": None, "tasks": [], "summary": {"total": 0, "completed": 0, "remaining": 0}})
            if path == "/api/output/history":
                try:
                    limit = int(query.get("limit", [50])[0])
                except (TypeError, ValueError):
                    limit = 50
                with db() as conn:
                    history = output_history(conn, limit)
                return json_response(self, history)
            if path == "/api/output/feedback/status":
                return json_response(self, feedback_provider_status())
            if path == "/api/output/contrasts":
                search = query.get("query", [""])[0]
                with db() as conn:
                    catalog = usage_contrast_catalog_payload(conn, search)
                return json_response(self, catalog)
            if path == "/api/speaking/tasks":
                try:
                    article_id = int(query.get("article_id", [""])[0])
                    duration = int(query.get("duration", [0])[0] or 0)
                except (TypeError, ValueError):
                    return json_response(self, {"error": "article_id is required"}, 400)
                with db() as conn:
                    task_set = latest_speaking_task_set(conn, article_id, duration)
                return json_response(self, task_set or {"set": None, "tasks": [], "summary": {"total": 0, "attempted": 0}})
            if path == "/api/speaking/history":
                try:
                    limit = int(query.get("limit", [50])[0])
                except (TypeError, ValueError):
                    limit = 50
                with db() as conn:
                    history = speaking_history(conn, limit)
                return json_response(self, history)
            if path == "/api/speaking/transcription/status":
                return json_response(self, transcription_status())
            match = re.fullmatch(r"/api/speaking/audio/(\d+)", path)
            if match:
                with db() as conn:
                    attempt = speaking_attempt_payload(conn, int(match.group(1)))
                if not attempt or not attempt["audio_filename"] or attempt["status"] == "deleted":
                    return json_response(self, {"error": "Speaking audio not found"}, 404)
                directory = speaking_audio_dir()
                audio_path = (directory / Path(attempt["audio_filename"]).name).resolve()
                if directory not in audio_path.parents or not audio_path.is_file():
                    return json_response(self, {"error": "Speaking audio file is unavailable"}, 404)
                return text_response(self, audio_path.read_bytes(), attempt["audio_mime"] or "application/octet-stream", cache_control="no-store")
            if path == "/api/browser/status":
                return json_response(self, {"ok": True, "translation": translation_status()})
            if path == "/api/browser/token":
                origin = self.headers.get("Origin", "")
                if origin and not origin.startswith(("http://127.0.0.1:", "http://localhost:")):
                    return json_response(self, {"error": "Token is only available to the local app"}, 403)
                return json_response(self, {"token": browser_bridge_token(), "translation": translation_status()})
            if path == "/api/browser/clips":
                if not self.browser_authorized():
                    return json_response(self, {"error": "Invalid browser bridge token"}, 401)
                with db() as conn:
                    clips = rows_to_dicts(conn.execute("SELECT * FROM browser_clips ORDER BY id DESC LIMIT 100").fetchall())
                return json_response(self, {"clips": clips})
            if path == "/api/exam-types":
                style = query.get("style", ["general"])[0]
                types = [{"id": key, "label": label, "engine_type": engine} for key, label, engine in EXAM_QUESTION_TYPES.get(style, EXAM_QUESTION_TYPES["general"])]
                return json_response(self, {"style": style, "types": types})
            if path == "/api/articles":
                return json_response(self, {"articles": list_articles(query), "facets": article_facets(query)})
            if path == "/api/article-topics":
                topics = [*ARTICLE_THEMES.keys(), "综合阅读"]
                return json_response(self, {"topics": topics})
            if path == "/api/article-content-types":
                return json_response(
                    self,
                    {"types": [{"id": key, "label": label} for key, label in CONTENT_TYPE_LABELS.items()]},
                )
            if path == "/api/content-hubs":
                return json_response(
                    self,
                    {"hubs": [{"id": key, "label": label} for key, label in CONTENT_HUBS.items()]},
                )
            if path == "/api/source-catalog":
                return json_response(self, {"sources": source_catalog_payload()})
            if path == "/api/subscriptions":
                return json_response(self, {"subscriptions": subscription_payload()})
            if path == "/api/today":
                return json_response(self, today_content(query.get("exam", [""])[0], query.get("mode", ["exam"])[0]))
            if path == "/api/lexicon/search":
                tracked = query.get("track", ["0"])[0].lower() in {"1", "true", "yes"}
                return json_response(self, lexical_search(query.get("q", [""])[0], track=tracked))
            if path == "/api/lexicon/compare":
                try:
                    return json_response(self, lexical_comparison(query.get("q", [""])[0]))
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 400)
            if path == "/api/lexicon/comparisons":
                return json_response(self, {"groups": curated_comparison_catalog()})
            if path == "/api/lexicon/history":
                return json_response(self, lexical_query_history(query.get("limit", [30])[0]))
            if path == "/api/dictionary/status":
                return json_response(self, dictionary_data_status())
            match = re.fullmatch(r"/api/lexicon/entries/(\d+)", path)
            if match:
                with db() as conn:
                    row = conn.execute("SELECT * FROM dictionary_entries WHERE id = ?", (match.group(1),)).fetchone()
                if not row:
                    return json_response(self, {"error": "Dictionary entry not found"}, 404)
                return json_response(self, {"entry": {"type": "entry", **lexical_entry(row)}})
            match = re.fullmatch(r"/api/lexicon/morphemes/(\d+)", path)
            if match:
                with db() as conn:
                    row = conn.execute("SELECT * FROM morphemes WHERE id = ?", (match.group(1),)).fetchone()
                if not row:
                    return json_response(self, {"error": "Morpheme not found"}, 404)
                return json_response(self, {"entry": {"type": "morpheme", **morpheme_entry(row)}})
            match = re.fullmatch(r"/api/articles/(\d+)", path)
            if match:
                with db() as conn:
                    article = conn.execute("SELECT * FROM articles WHERE id = ?", (match.group(1),)).fetchone()
                    item = article_with_paragraph_translations(conn, dict(article), query.get("exam", [""])[0]) if article else None
                if not article:
                    return json_response(self, {"error": "Article not found"}, 404)
                return json_response(self, {"article": item, "analysis": analyze_payload(item)})
            if path == "/api/cards":
                with db() as conn:
                    cards = unique_cards_payload(conn)
                return json_response(self, {"cards": cards})
            if path == "/api/reviews":
                kind = query.get("kind", ["all"])[0]
                try:
                    limit = int(query.get("limit", [20])[0])
                except (TypeError, ValueError):
                    limit = 20
                with db() as conn:
                    payload = review_queue(conn, kind=kind, limit=limit)
                return json_response(self, payload)
            if path == "/api/complete-word-reviews":
                scope = query.get("scope", ["wrong"])[0]
                search = query.get("q", [""])[0]
                try:
                    limit = int(query.get("limit", [200])[0])
                except (TypeError, ValueError):
                    limit = 200
                with db() as conn:
                    payload = complete_word_catalog(conn, scope=scope, search=search, limit=limit)
                return json_response(self, payload)
            if path == "/api/quizzes":
                article_id = query.get("article_id", [""])[0]
                style = query.get("style", [""])[0]
                question_type = query.get("question_type", [""])[0]
                sql = "SELECT * FROM quizzes"
                where = []
                params: list[str] = []
                if article_id:
                    where.append("article_id = ?")
                    params.append(article_id)
                if style:
                    where.append("style = ?")
                    params.append(style)
                if question_type:
                    where.append("question_type = ?")
                    params.append(question_type)
                if where:
                    sql += " WHERE " + " AND ".join(where)
                sql += " ORDER BY created_at DESC, id DESC"
                with db() as conn:
                    quizzes = [self.quiz_row(row) for row in conn.execute(sql, params).fetchall()]
                return json_response(self, {"quizzes": quizzes})
            if path == "/api/exam-resources":
                exam = query.get("exam", [""])[0]
                sql = "SELECT * FROM exam_resources"
                params: list[str] = []
                if exam:
                    sql += " WHERE exam = ?"
                    params.append(exam)
                sql += " ORDER BY exam, provider, id"
                with db() as conn:
                    resources = rows_to_dicts(conn.execute(sql, params).fetchall())
                return json_response(self, {"resources": resources})
            if path == "/api/exam-papers":
                exam = query.get("exam", [""])[0]
                sql = "SELECT * FROM exam_papers"
                params: list[str] = []
                if exam:
                    sql += " WHERE exam = ?"
                    params.append(exam)
                sql += " ORDER BY created_at DESC, id DESC"
                with db() as conn:
                    papers = rows_to_dicts(conn.execute(sql, params).fetchall())
                return json_response(self, {"papers": papers})
            match = re.fullmatch(r"/api/exam-papers/(\d+)", path)
            if match:
                with db() as conn:
                    paper = exam_paper_detail(conn, int(match.group(1)))
                if not paper:
                    return json_response(self, {"error": "Exam paper not found"}, 404)
                return json_response(self, {"paper": paper})
            if path == "/api/practice-runs/active":
                with db() as conn:
                    run = active_practice_run(conn)
                    quizzes = []
                    if run:
                        quiz_ids = run.get("quiz_ids") or []
                        if quiz_ids:
                            placeholders = ",".join("?" for _ in quiz_ids)
                            rows = conn.execute(f"SELECT * FROM quizzes WHERE id IN ({placeholders})", quiz_ids).fetchall()
                            by_id = {row["id"]: quiz_payload(row) for row in rows}
                            quizzes = [by_id[quiz_id] for quiz_id in quiz_ids if quiz_id in by_id]
                return json_response(self, {"run": run, "quizzes": quizzes})
            if path == "/api/practice/prescription":
                style = query.get("style", ["IELTS"])[0]
                configured = EXAM_QUESTION_TYPES.get(style, EXAM_QUESTION_TYPES["general"])
                default_type = configured[0][0] if configured else ""
                with db() as conn:
                    prescription = training_prescription(conn, style, default_type)
                return json_response(self, {"prescription": prescription})
            if path == "/api/practice-sessions":
                style = query.get("style", [""])[0]
                where = "WHERE s.style = ?" if style else ""
                params = (style,) if style else ()
                with db() as conn:
                    rows = conn.execute(
                        f"""
                        SELECT s.*, a.title AS article_title
                        FROM practice_sessions s
                        LEFT JOIN articles a ON a.id = s.article_id
                        {where}
                        ORDER BY s.completed_at DESC, s.id DESC LIMIT 50
                        """,
                        params,
                    ).fetchall()
                return json_response(self, {"sessions": [practice_session_payload(row) for row in rows]})
            match = re.fullmatch(r"/api/practice-sessions/(\d+)", path)
            if match:
                with db() as conn:
                    detail = practice_session_detail(conn, int(match.group(1)))
                if not detail:
                    return json_response(self, {"error": "Practice session not found"}, 404)
                return json_response(self, detail)
            if path == "/api/practice/analytics":
                style = query.get("style", ["IELTS"])[0]
                return json_response(self, practice_analytics(style))
            if path == "/api/mistakes":
                with db() as conn:
                    rows = conn.execute(
                        """
                        SELECT m.*, q.style, q.type AS quiz_type, q.question_type, q.options_json,
                               q.skill AS quiz_skill, q.difficulty, q.note AS quiz_note,
                               q.article_id, a.title AS article_title
                        FROM mistakes m
                        LEFT JOIN quizzes q ON q.id = m.quiz_id
                        LEFT JOIN articles a ON a.id = q.article_id
                        ORDER BY m.solved, m.created_at DESC
                        """
                    ).fetchall()
                    mistakes = []
                    for row in rows:
                        item = dict(row)
                        item["skill"] = item.get("skill") or item.get("quiz_skill") or "阅读理解"
                        fresh_explanation = explain_mistake(item, item["user_answer"])
                        try:
                            item["explanation"] = json.loads(item.get("explanation_json") or "{}") or fresh_explanation
                        except json.JSONDecodeError:
                            item["explanation"] = fresh_explanation
                        for key, value in fresh_explanation.items():
                            item["explanation"].setdefault(key, value)
                        mistakes.append(item)
                return json_response(self, {"mistakes": mistakes})
            if path == "/api/feeds":
                with db() as conn:
                    feeds = rows_to_dicts(conn.execute("SELECT * FROM feeds WHERE active = 1 ORDER BY id").fetchall())
                exam = query.get("exam", [""])[0]
                for feed in feeds:
                    feed.update(source_profile(feed["name"], exam))
                feeds.sort(key=lambda item: item["exam_fit"], reverse=True)
                return json_response(self, {"feeds": feeds})
            return self.serve_static(path)
        except Exception as exc:
            return json_response(self, {"error": str(exc)}, 500)

    def save_speaking_audio(self, attempt_id: int) -> None:
        allowed = {
            "audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a",
            "audio/wav": ".wav", "audio/x-wav": ".wav",
        }
        mime_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if mime_type not in allowed:
            return json_response(self, {"error": "Unsupported speaking audio format"}, 415)
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            duration = int(float(self.headers.get("X-Audio-Duration", "0") or "0"))
        except ValueError:
            return json_response(self, {"error": "Invalid audio metadata"}, 400)
        if length < 1 or length > 15 * 1024 * 1024:
            return json_response(self, {"error": "Speaking audio must be between 1 byte and 15 MB"}, 413)
        with db() as conn:
            previous = speaking_attempt_payload(conn, attempt_id)
        if not previous or previous["status"] == "deleted":
            return json_response(self, {"error": "Speaking attempt not found"}, 404)
        content = self.rfile.read(length)
        if len(content) != length:
            return json_response(self, {"error": "Incomplete speaking audio upload"}, 400)
        directory = speaking_audio_dir()
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"speaking-{attempt_id}-{secrets.token_hex(8)}{allowed[mime_type]}"
        target = (directory / filename).resolve()
        if directory not in target.parents:
            return json_response(self, {"error": "Invalid speaking audio path"}, 400)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(target)
        try:
            with db() as conn:
                attempt = attach_audio(conn, attempt_id, filename, mime_type, length, duration)
                if not previous.get("audio_filename"):
                    increment_daily_metric(conn, "speaking_seconds", int(attempt["duration_seconds"] or 0))
        except ValueError as exc:
            target.unlink(missing_ok=True)
            return json_response(self, {"error": str(exc)}, 404)
        previous_name = Path(previous.get("audio_filename") or "").name
        if previous_name and previous_name != filename:
            (directory / previous_name).unlink(missing_ok=True)
        return json_response(self, {"attempt": attempt}, 201)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        audio_match = re.fullmatch(r"/api/speaking-attempts/(\d+)/audio", path)
        if audio_match:
            return self.save_speaking_audio(int(audio_match.group(1)))
        try:
            payload = read_json(self)
            if path == "/api/extraction/review-batches":
                try:
                    with db() as conn:
                        batch = create_extraction_review_batch(
                            conn,
                            int(payload.get("target_size") or 20),
                            bool(payload.get("force_new")),
                        )
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 422)
                return json_response(self, batch, 201)
            match = re.fullmatch(r"/api/articles/(\d+)/output-tasks", path)
            if match:
                with db() as conn:
                    article = conn.execute("SELECT * FROM articles WHERE id = ?", (int(match.group(1)),)).fetchone()
                    if not article:
                        return json_response(self, {"error": "Article not found"}, 404)
                    try:
                        task_set = create_output_task_set(
                            conn, article, article_keywords(article["body"]), bool(payload.get("force_new")),
                        )
                    except ValueError as exc:
                        return json_response(self, {"error": str(exc)}, 422)
                return json_response(self, task_set, 201)
            match = re.fullmatch(r"/api/articles/(\d+)/speaking-tasks", path)
            if match:
                with db() as conn:
                    article = conn.execute("SELECT * FROM articles WHERE id = ?", (int(match.group(1)),)).fetchone()
                    if not article:
                        return json_response(self, {"error": "Article not found"}, 404)
                    try:
                        task_set = create_speaking_task_set(
                            conn, article, article_keywords(article["body"]),
                            int(payload.get("duration_target") or 60), int(payload.get("prep_seconds") or 15),
                            bool(payload.get("force_new")),
                        )
                    except (TypeError, ValueError) as exc:
                        return json_response(self, {"error": str(exc)}, 422)
                return json_response(self, task_set, 201)
            match = re.fullmatch(r"/api/articles/(\d+)/read", path)
            if match:
                try:
                    with db() as conn:
                        result = mark_article_read(conn, int(match.group(1)))
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 404)
                return json_response(self, {**result, "plan": daily_plan_snapshot()})
            if path == "/api/output-attempts":
                try:
                    with db() as conn:
                        attempt = submit_output_attempt(
                            conn,
                            int(payload.get("task_id") or 0),
                            str(payload.get("response") or ""),
                            int(payload.get("elapsed_seconds") or 0),
                            bool(payload.get("hint_used")),
                            payload.get("confidence"),
                        )
                        increment_daily_metric(conn, "output_sentences", int(attempt["sentence_count"] or 1))
                        increment_daily_progress(conn, "output", int(attempt["sentence_count"] or 1))
                except (TypeError, ValueError) as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, {"attempt": attempt, "plan": daily_plan_snapshot()}, 201)
            if path == "/api/speaking-attempts":
                try:
                    with db() as conn:
                        attempt = create_speaking_attempt(
                            conn, int(payload.get("task_id") or 0), int(payload.get("prep_seconds") or 0),
                            int(payload["repeat_of_id"]) if payload.get("repeat_of_id") else None,
                        )
                except (TypeError, ValueError) as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, {"attempt": attempt}, 201)
            match = re.fullmatch(r"/api/speaking-attempts/(\d+)/self-review", path)
            if match:
                try:
                    with db() as conn:
                        attempt = save_speaking_self_review(
                            conn, int(match.group(1)), payload.get("ratings") or {},
                            str(payload.get("note") or ""), str(payload.get("stuck_expression") or ""),
                        )
                except (TypeError, ValueError) as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, {"attempt": attempt})
            match = re.fullmatch(r"/api/speaking-attempts/(\d+)/transcript", path)
            if match:
                try:
                    with db() as conn:
                        attempt = save_transcript(
                            conn, int(match.group(1)), str(payload.get("text") or ""), "manual",
                        )
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, {"attempt": attempt})
            match = re.fullmatch(r"/api/speaking-attempts/(\d+)/transcribe", path)
            if match:
                with db() as conn:
                    attempt = speaking_attempt_payload(conn, int(match.group(1)))
                if not attempt or not attempt["audio_filename"] or attempt["status"] == "deleted":
                    return json_response(self, {"error": "Recorded speaking audio is required"}, 404)
                directory = speaking_audio_dir()
                audio_path = (directory / Path(attempt["audio_filename"]).name).resolve()
                if directory not in audio_path.parents or not audio_path.is_file():
                    return json_response(self, {"error": "Speaking audio file is unavailable"}, 404)
                try:
                    result = transcribe_audio(audio_path, attempt["audio_mime"])
                    with db() as conn:
                        saved = save_transcript(
                            conn, attempt["id"], result["text"], "provider", result["provider"], result["model"],
                        )
                except RuntimeError as exc:
                    return json_response(self, {"error": str(exc), "status": transcription_status()}, 503)
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 502)
                return json_response(self, {"attempt": saved})
            match = re.fullmatch(r"/api/speaking-attempts/(\d+)/review-items", path)
            if match:
                try:
                    with db() as conn:
                        result = save_speaking_review_item(
                            conn, int(match.group(1)), str(payload.get("term") or ""),
                            str(payload.get("context") or ""),
                        )
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, result, 201 if result["created"] else 200)
            match = re.fullmatch(r"/api/output-attempts/(\d+)/self-review", path)
            if match:
                try:
                    with db() as conn:
                        attempt = save_self_review(
                            conn, int(match.group(1)), payload.get("ratings") or {}, str(payload.get("note") or ""),
                        )
                except (TypeError, ValueError) as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, {"attempt": attempt})
            match = re.fullmatch(r"/api/output-attempts/(\d+)/semantic-feedback", path)
            if match:
                attempt_id = int(match.group(1))
                with db() as conn:
                    attempt = output_attempt_payload(conn, attempt_id)
                if not attempt:
                    return json_response(self, {"error": "Output attempt not found"}, 404)
                if attempt.get("semantic_feedback") and not payload.get("force_new"):
                    return json_response(self, {"semantic_feedback": attempt["semantic_feedback"], "reused": True})
                try:
                    result = request_semantic_feedback(attempt)
                    with db() as conn:
                        feedback = save_semantic_feedback(conn, attempt_id, result)
                except RuntimeError as exc:
                    return json_response(self, {"error": str(exc), "status": feedback_provider_status()}, 503)
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 502)
                return json_response(self, {"semantic_feedback": feedback}, 201)
            match = re.fullmatch(r"/api/output-feedback/(\d+)/decision", path)
            if match:
                try:
                    with db() as conn:
                        feedback = save_feedback_decision(
                            conn, int(match.group(1)), str(payload.get("decision") or ""),
                            str(payload.get("revised_response") or ""),
                        )
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, {"semantic_feedback": feedback})
            match = re.fullmatch(r"/api/output-attempts/(\d+)/save-review-item", path)
            if match:
                try:
                    with db() as conn:
                        result = save_output_review_item(conn, int(match.group(1)))
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 404)
                return json_response(self, result, 201 if result["created"] else 200)
            match = re.fullmatch(r"/api/output-attempts/(\d+)/review-items", path)
            if match:
                try:
                    with db() as conn:
                        result = save_output_review_item(
                            conn, int(match.group(1)), str(payload.get("term") or ""),
                            str(payload.get("context") or ""), str(payload.get("note") or ""),
                        )
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, result, 201 if result["created"] else 200)
            match = re.fullmatch(r"/api/output/contrasts/([a-z0-9-]+)/attempt", path)
            if match:
                contrast = contrast_by_slug(match.group(1))
                if not contrast:
                    return json_response(self, {"error": "Usage contrast not found"}, 404)
                try:
                    selected_index = int(payload.get("selected_index"))
                except (TypeError, ValueError):
                    return json_response(self, {"error": "selected_index is required"}, 400)
                if selected_index < 0 or selected_index >= len(contrast["options"]):
                    return json_response(self, {"error": "Invalid contrast option"}, 400)
                correct = selected_index == int(contrast["answer_index"])
                with db() as conn:
                    conn.execute(
                        """INSERT INTO usage_contrast_attempts
                           (contrast_slug, selected_index, correct, created_at) VALUES (?, ?, ?, ?)""",
                        (contrast["slug"], selected_index, int(correct), utc_now()),
                    )
                    catalog = usage_contrast_catalog_payload(conn, contrast["terms"][0])
                return json_response(self, {
                    "correct": correct,
                    "answer_index": contrast["answer_index"],
                    "answer": contrast["options"][contrast["answer_index"]],
                    "explanation": contrast["explanation"],
                    "history": next(item["history"] for item in catalog["contrasts"] if item["slug"] == contrast["slug"]),
                })
            match = re.fullmatch(r"/api/extraction/review-items/(\d+)/activity", path)
            if match:
                elapsed = max(0, min(int(payload.get("elapsed_seconds") or 0), 300))
                with db() as conn:
                    item = conn.execute(
                        "SELECT * FROM article_extraction_review_items WHERE id = ?", (int(match.group(1)),)
                    ).fetchone()
                    if not item:
                        return json_response(self, {"error": "Review item not found"}, 404)
                    now = utc_now()
                    conn.execute(
                        """UPDATE article_extraction_review_items SET
                           status = CASE WHEN status = 'pending' THEN 'in_progress' ELSE status END,
                           started_at = CASE WHEN started_at = '' THEN ? ELSE started_at END,
                           last_activity_at = ?, active_seconds = active_seconds + ? WHERE id = ?""",
                        (now, now, elapsed, item["id"]),
                    )
                    batch = extraction_review_batch_payload(conn, item["batch_id"])
                return json_response(self, batch)
            match = re.fullmatch(r"/api/reviews/(\d+)/rate", path)
            if match:
                try:
                    with db() as conn:
                        result = rate_review_item(conn, int(match.group(1)), str(payload.get("rating") or ""))
                        increment_daily_progress(conn, "review", 1)
                        if result["item"]["item_type"] == "card":
                            increment_daily_metric(conn, "review_chunks", 1)
                        queue = review_queue(conn, kind=str(payload.get("kind") or "all"), limit=20)
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, {**result, "queue": queue})
            match = re.fullmatch(r"/api/complete-word-reviews/(\d+)/answer", path)
            if match:
                try:
                    with db() as conn:
                        result = submit_complete_word_review(
                            conn, int(match.group(1)), str(payload.get("answer") or ""),
                            elapsed_seconds=payload.get("elapsed_seconds") or 0,
                        )
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, result, 201)
            if path == "/api/reviews/undo":
                try:
                    with db() as conn:
                        kind = str(payload.get("kind") or "all")
                        result = undo_last_review(conn, kind=kind)
                        review_item = conn.execute(
                            "SELECT item_type FROM review_items WHERE id = ?", (result["review_item_id"],)
                        ).fetchone()
                        reviewed_day = datetime.fromisoformat(result["reviewed_at"]).astimezone().date().isoformat()
                        if reviewed_day == current_plan_day():
                            decrement_daily_progress(conn, "review", 1, reviewed_day)
                            if review_item and review_item["item_type"] == "card":
                                decrement_daily_metric(conn, "review_chunks", 1, reviewed_day)
                        queue = review_queue(conn, kind=kind, limit=20)
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, {**result, "queue": queue})
            if path == "/api/lexicon/history/clear":
                with db() as conn:
                    conn.execute("DELETE FROM lexical_queries")
                return json_response(self, {"cleared": True, "recent": [], "frequent": []})
            if path == "/api/backups":
                backup = create_backup(DB_PATH, BACKUP_DIR, PROCESS_APP_VERSION)
                return json_response(self, {"backup": backup, "backups": list_backups(BACKUP_DIR)}, 201)
            if path == "/api/backups/restore":
                try:
                    result = restore_backup(
                        DB_PATH, BACKUP_DIR, str(payload.get("filename") or ""), PROCESS_APP_VERSION,
                    )
                    init_db()
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, {**result, "version": runtime_metadata()})
            if path == "/api/learner-settings":
                try:
                    settings = update_learner_settings(payload)
                except (TypeError, ValueError) as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, {"settings": settings})
            if path == "/api/article-preferences":
                try:
                    settings = update_article_preferences(payload)
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, {"settings": settings})
            if path == "/api/learner-profile":
                try:
                    result = update_learner_profile(payload)
                except (TypeError, ValueError) as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, result)
            if path == "/api/profile/quick-test":
                try:
                    result = submit_quick_test(payload)
                except (TypeError, ValueError) as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, result)
            if path == "/api/practice-runs":
                try:
                    with db() as conn:
                        run = save_practice_run(conn, payload, utc_now())
                except (TypeError, ValueError) as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, {"run": run}, 200 if payload.get("id") else 201)
            match = re.fullmatch(r"/api/practice-runs/(\d+)/(complete|abandon)", path)
            if match:
                try:
                    with db() as conn:
                        run = finish_practice_run(
                            conn, int(match.group(1)), utc_now(),
                            "completed" if match.group(2) == "complete" else "abandoned",
                            int(payload.get("practice_session_id")) if payload.get("practice_session_id") else None,
                        )
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 404)
                return json_response(self, {"run": run})
            if path == "/api/import/epub":
                try:
                    book, created = import_epub(str(payload.get("path") or ""))
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, {"book": book, "created": created}, 201 if created else 200)
            if path == "/api/private-dictionaries/stardict":
                if not self.browser_authorized():
                    return json_response(self, {"error": "Invalid local dictionary token"}, 401)
                source_path = Path(str(payload.get("path") or "")).expanduser()
                name = str(payload.get("name") or source_path.stem).strip()
                kind = str(payload.get("kind") or "bilingual_dictionary")
                if kind not in {"bilingual_dictionary", "monolingual_dictionary", "encyclopedia"}:
                    return json_response(self, {"error": "Unsupported private dictionary kind"}, 400)
                try:
                    priority = max(0, min(999, int(payload.get("priority", 20))))
                    if source_path.suffix.casefold() != ".ifo" or not source_path.is_file():
                        raise ValueError("Select an existing StarDict .ifo file")
                    with db() as conn:
                        source = register_private_stardict(
                            conn, source_path, name=name, kind=kind,
                            priority=priority, now=utc_now(),
                        )
                        sources = private_dictionary_status(conn)
                except (OSError, ValueError, sqlite3.DatabaseError) as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, {"source": source, "private_sources": sources}, 201)
            match = re.fullmatch(r"/api/private-dictionaries/(\d+)", path)
            if match:
                if not self.browser_authorized():
                    return json_response(self, {"error": "Invalid local dictionary token"}, 401)
                try:
                    priority = int(payload["priority"]) if "priority" in payload else None
                    if "enabled" in payload and not isinstance(payload["enabled"], bool):
                        raise ValueError("enabled must be a boolean")
                    enabled = payload.get("enabled")
                    with db() as conn:
                        source = update_private_dictionary(
                            conn, int(match.group(1)), enabled=enabled,
                            priority=priority, now=utc_now(),
                        )
                        sources = private_dictionary_status(conn)
                except (TypeError, ValueError) as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                if not source:
                    return json_response(self, {"error": "Private dictionary not found"}, 404)
                return json_response(self, {"source": source, "private_sources": sources})
            match = re.fullmatch(r"/api/book-chapters/(\d+)/article", path)
            if match:
                with db() as conn:
                    article = materialize_book_chapter(conn, int(match.group(1)))
                if not article:
                    return json_response(self, {"error": "Book chapter not found"}, 404)
                return json_response(self, {"article": enrich_article(article, str(payload.get("exam") or ""))}, 201)
            if path == "/api/daily-plan/progress":
                task = str(payload.get("task") or "")
                if task not in DAILY_PLAN_TASKS:
                    return json_response(self, {"error": "Unknown daily task"}, 400)
                with db() as conn:
                    if "completed_count" in payload:
                        set_daily_progress(conn, task, int(payload.get("completed_count") or 0))
                    else:
                        increment_daily_progress(conn, task, max(1, int(payload.get("amount") or 1)))
                return json_response(self, {"plan": daily_plan_snapshot()})
            if path == "/api/daily-plan/items":
                task = str(payload.get("task") or "")
                item_type = str(payload.get("item_type") or "")
                item_id = int(payload.get("item_id") or 0)
                if task not in DAILY_PLAN_TASKS or item_type not in {"mistake", "clip", "article"} or not item_id:
                    return json_response(self, {"error": "A valid task and source item are required"}, 400)
                now = utc_now()
                with db() as conn:
                    conn.execute(
                        """
                        INSERT INTO daily_plan_items (day, task, item_type, item_id, title, completed, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                        ON CONFLICT(day, item_type, item_id) DO UPDATE SET
                          task = excluded.task, title = excluded.title, updated_at = excluded.updated_at
                        """,
                        (current_plan_day(), task, item_type, item_id, str(payload.get("title") or "")[:180], now, now),
                    )
                return json_response(self, {"plan": daily_plan_snapshot()}, 201)
            match = re.fullmatch(r"/api/daily-plan/items/(\d+)/complete", path)
            if match:
                with db() as conn:
                    item = conn.execute("SELECT * FROM daily_plan_items WHERE id = ?", (int(match.group(1)),)).fetchone()
                    if not item:
                        return json_response(self, {"error": "Daily plan item not found"}, 404)
                    if not item["completed"]:
                        conn.execute(
                            "UPDATE daily_plan_items SET completed = 1, updated_at = ? WHERE id = ?",
                            (utc_now(), item["id"]),
                        )
                        increment_daily_progress(conn, item["task"], 1, item["day"])
                return json_response(self, {"plan": daily_plan_snapshot()})
            if path == "/api/browser/translate":
                if not self.browser_authorized():
                    return json_response(self, {"error": "Invalid browser bridge token"}, 401)
                try:
                    result = translate_text(payload.get("text") or "", payload.get("source_lang") or "EN", payload.get("target_lang") or "ZH-HANS")
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                except RuntimeError as exc:
                    return json_response(self, {"error": str(exc), "translation": translation_status()}, 503)
                return json_response(self, result)
            if path == "/api/browser/translate-segments":
                if not self.browser_authorized():
                    return json_response(self, {"error": "Invalid browser bridge token"}, 401)
                segments = payload.get("segments") or []
                if not isinstance(segments, list) or not all(isinstance(value, str) for value in segments):
                    return json_response(self, {"error": "Segments must be a list of strings"}, 400)
                try:
                    result = translate_segments(
                        segments,
                        payload.get("source_lang") or "EN",
                        payload.get("target_lang") or "ZH-HANS",
                    )
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                except RuntimeError as exc:
                    return json_response(self, {"error": str(exc), "translation": translation_status()}, 503)
                return json_response(self, result)
            if path == "/api/browser/translation-verify":
                if not self.browser_authorized():
                    return json_response(self, {"error": "Invalid browser bridge token"}, 401)
                return json_response(self, {"translation": verify_deepl_configuration()})
            if path == "/api/browser/clips":
                if not self.browser_authorized():
                    return json_response(self, {"error": "Invalid browser bridge token"}, 401)
                source_text = (payload.get("text") or "").strip()
                if not source_text:
                    return json_response(self, {"error": "Clip text is required"}, 400)
                kind = payload.get("kind") or "selection"
                if kind not in {"word", "selection", "article"}:
                    return json_response(self, {"error": "Unsupported clip kind"}, 400)
                context = (payload.get("context") or "").strip()
                page_title = (payload.get("page_title") or "").strip()
                page_url = (payload.get("page_url") or "").strip()
                translated = (payload.get("translation") or "").strip()
                note_parts = ["浏览器摘录", page_title, page_url]
                note = " · ".join(part for part in note_parts if part)
                now = utc_now()
                with db() as conn:
                    card_id = None
                    article_id = None
                    if kind == "article":
                        title = page_title or "Browser article"
                        body = normalize_article_text(title, source_text)
                        if page_url:
                            existing = conn.execute("SELECT id FROM articles WHERE source_url = ?", (page_url,)).fetchone()
                        else:
                            existing = None
                        if existing:
                            article_id = existing["id"]
                            content_type = infer_content_type({"source": "browser", "title": title, "body": body})
                            conn.execute(
                                """UPDATE articles SET title = ?, body = ?, translation_zh = ?, content_status = 'full',
                                   content_type = ?, source = 'browser', visibility = 'private', updated_at = ? WHERE id = ?""",
                                (title, body, translated, content_type, now, article_id),
                            )
                        else:
                            content_type = infer_content_type({"source": "browser", "title": title, "body": body})
                            cursor = conn.execute(
                                """INSERT INTO articles
                                   (title, language, level, topic, source, visibility, source_url, content_status, content_type, body, translation_zh, created_at, updated_at)
                                   VALUES (?, 'en', ?, 'browser', 'browser', 'private', ?, 'full', ?, ?, ?, ?, ?)""",
                                (title, estimate_level(body), page_url, content_type, body, translated, now, now),
                            )
                            article_id = cursor.lastrowid
                    elif payload.get("save_to", "wordbook") == "wordbook":
                        term = source_text if len(source_text) <= 180 else source_text[:177] + "..."
                        existing_card = conn.execute(
                            "SELECT * FROM cards WHERE lower(trim(term)) = lower(?) ORDER BY updated_at DESC, id DESC LIMIT 1",
                            (term,),
                        ).fetchone()
                        if existing_card:
                            conn.execute(
                                """UPDATE cards SET context = ?, note = ?, updated_at = ? WHERE id = ?""",
                                (context or source_text or existing_card["context"], note or existing_card["note"], now, existing_card["id"]),
                            )
                            card_id = existing_card["id"]
                        else:
                            cursor = conn.execute(
                                """INSERT INTO cards (term, kind, context, status, note, created_at, updated_at)
                                   VALUES (?, ?, ?, 'new', ?, ?, ?)""",
                                (term, "phrase" if " " in term.strip() else "word", context or source_text, note, now, now),
                            )
                            card_id = cursor.lastrowid
                    cursor = conn.execute(
                        """INSERT INTO browser_clips
                           (kind, source_text, translated_text, context, page_title, page_url, card_id, article_id, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (kind, source_text, translated, context, page_title, page_url, card_id, article_id, now),
                    )
                    clip = conn.execute("SELECT * FROM browser_clips WHERE id = ?", (cursor.lastrowid,)).fetchone()
                    card = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone() if card_id else None
                article = None
                if article_id:
                    with db() as conn:
                        row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
                    article = enrich_article(dict(row), payload.get("exam") or "") if row else None
                return json_response(self, {"clip": dict(clip), "card": dict(card) if card else None, "article": article}, 201)
            if path == "/api/articles":
                now = utc_now()
                body = (payload.get("body") or "").strip()
                if not body:
                    return json_response(self, {"error": "Article body is required"}, 400)
                title = (payload.get("title") or "Untitled").strip()
                level = payload.get("level") or estimate_level(body)
                requested_content_type = payload.get("content_type") or "auto"
                content_type = infer_content_type({"source": payload.get("source") or "manual", "title": title, "body": body, "content_type": requested_content_type})
                with db() as conn:
                    cursor = conn.execute(
                        """
                        INSERT INTO articles (title, language, level, topic, source, visibility, source_url, content_type, body, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, 'private', ?, ?, ?, ?, ?)
                        """,
                        (
                            title,
                            payload.get("language") or "en",
                            level,
                            payload.get("topic") or "manual",
                            payload.get("source") or "manual",
                            payload.get("source_url") or "",
                            content_type,
                            body,
                            now,
                            now,
                        ),
                    )
                    article = conn.execute("SELECT * FROM articles WHERE id = ?", (cursor.lastrowid,)).fetchone()
                    conn.execute("UPDATE articles SET content_status = 'full' WHERE id = ?", (cursor.lastrowid,))
                    article = conn.execute("SELECT * FROM articles WHERE id = ?", (cursor.lastrowid,)).fetchone()
                    if payload.get("translation_zh"):
                        conn.execute("UPDATE articles SET translation_zh = ? WHERE id = ?", (payload["translation_zh"], cursor.lastrowid))
                        article = conn.execute("SELECT * FROM articles WHERE id = ?", (cursor.lastrowid,)).fetchone()
                return json_response(self, {"article": dict(article), "analysis": analyze_payload(article)}, 201)
            if path == "/api/exam-resources":
                title = (payload.get("title") or "").strip()
                exam = (payload.get("exam") or "").strip().upper()
                if not title or exam not in EXAM_QUESTION_TYPES:
                    return json_response(self, {"error": "Title and a supported exam are required"}, 400)
                source_url = (payload.get("source_url") or "").strip() or f"user-import://{secrets.token_urlsafe(10)}"
                now = utc_now()
                with db() as conn:
                    cursor = conn.execute(
                        """
                        INSERT INTO exam_resources
                        (title, exam, year, provider, resource_type, source_url, access_mode, rights_status, description, created_at)
                        VALUES (?, ?, ?, ?, 'user_import', ?, 'local_import', 'user_provided', ?, ?)
                        """,
                        (
                            title, exam, int(payload["year"]) if str(payload.get("year") or "").isdigit() else None,
                            (payload.get("provider") or "用户导入").strip(), source_url,
                            (payload.get("description") or "由用户自行提供；未向项目分发原题文本。").strip(), now,
                        ),
                    )
                    resource = conn.execute("SELECT * FROM exam_resources WHERE id = ?", (cursor.lastrowid,)).fetchone()
                return json_response(self, {"resource": dict(resource)}, 201)
            if path == "/api/exam-papers/generate":
                exam = (payload.get("exam") or "IELTS").strip().upper()
                if exam != "IELTS":
                    return json_response(self, {"error": "Full-paper generation is currently available for IELTS only"}, 422)
                try:
                    with db() as conn:
                        paper = create_ielts_mock_paper(conn)
                        detail = exam_paper_detail(conn, paper["id"])
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 422)
                return json_response(self, {"paper": detail}, 201)
            if path == "/api/subscriptions":
                target_type = (payload.get("target_type") or "source").strip()
                target_value = (payload.get("target_value") or "").strip()
                if target_type not in {"source", "category"}:
                    return json_response(self, {"error": "Subscription type must be source or category"}, 400)
                catalog = source_catalog()
                allowed = {item["name"] for item in catalog} if target_type == "source" else {item["category"] for item in catalog}
                if target_value not in allowed:
                    return json_response(self, {"error": "Unknown subscription target"}, 400)
                active = 1 if payload.get("active", True) else 0
                now = utc_now()
                with db() as conn:
                    conn.execute(
                        """INSERT INTO subscriptions (target_type, target_value, active, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?)
                           ON CONFLICT(target_type, target_value) DO UPDATE SET active = excluded.active, updated_at = excluded.updated_at""",
                        (target_type, target_value, active, now, now),
                    )
                return json_response(
                    self,
                    {"ok": True, "target_type": target_type, "target_value": target_value, "active": bool(active)},
                )
            match = re.fullmatch(r"/api/articles/(\d+)/translation", path)
            if match:
                translation = (payload.get("translation_zh") or "").strip()
                with db() as conn:
                    conn.execute("UPDATE articles SET translation_zh = ?, updated_at = ? WHERE id = ?", (translation, utc_now(), match.group(1)))
                    article = conn.execute("SELECT * FROM articles WHERE id = ?", (match.group(1),)).fetchone()
                    if article:
                        translations = [value.strip() for value in re.split(r"\n\s*\n", translation) if value.strip()]
                        replace_article_paragraph_translations(conn, dict(article), translations, "manual")
                        item = article_with_paragraph_translations(conn, dict(article), payload.get("exam") or "")
                if not article:
                    return json_response(self, {"error": "Article not found"}, 404)
                return json_response(self, {"article": item})
            match = re.fullmatch(r"/api/articles/(\d+)/translate", path)
            if match:
                with db() as conn:
                    article = conn.execute("SELECT * FROM articles WHERE id = ?", (match.group(1),)).fetchone()
                    valid_translations = article_paragraph_translation_values(conn, dict(article)) if article else []
                if not article:
                    return json_response(self, {"error": "Article not found"}, 404)
                paragraphs = [value.strip() for value in re.split(r"\n\s*\n", article["body"]) if value.strip()]
                if valid_translations and all(value.strip() for value in valid_translations) and not payload.get("force"):
                    with db() as conn:
                        item = article_with_paragraph_translations(conn, dict(article), payload.get("exam") or "")
                    return json_response(
                        self,
                        {
                            "article": item,
                            "translated_segments": valid_translations,
                            "provider": "saved",
                            "cached": True,
                        },
                    )
                try:
                    result = translate_segments(paragraphs)
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                except RuntimeError as exc:
                    return json_response(self, {"error": str(exc), "translation": translation_status()}, 503)
                translation = "\n\n".join(result["translated_segments"])
                with db() as conn:
                    conn.execute(
                        "UPDATE articles SET translation_zh = ?, updated_at = ? WHERE id = ?",
                        (translation, utc_now(), match.group(1)),
                    )
                    updated = conn.execute("SELECT * FROM articles WHERE id = ?", (match.group(1),)).fetchone()
                    replace_article_paragraph_translations(conn, dict(updated), result["translated_segments"], result["provider"])
                    item = article_with_paragraph_translations(conn, dict(updated), payload.get("exam") or "")
                return json_response(
                    self,
                    {
                        "article": item,
                        "translated_segments": result["translated_segments"],
                        "provider": result["provider"],
                        "cached": result["cached"],
                    },
                )
            match = re.fullmatch(r"/api/articles/(\d+)/paragraphs/(\d+)/translate", path)
            if match:
                article_id, paragraph_index = int(match.group(1)), int(match.group(2))
                with db() as conn:
                    article = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
                if not article:
                    return json_response(self, {"error": "Article not found"}, 404)
                originals = article_paragraph_values(article["body"])
                if paragraph_index < 0 or paragraph_index >= len(originals):
                    return json_response(self, {"error": "Paragraph not found"}, 404)
                try:
                    result = translate_segments([originals[paragraph_index]])
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                except RuntimeError as exc:
                    return json_response(self, {"error": str(exc), "translation": translation_status()}, 503)
                translated = result["translated_segments"][0]
                now = utc_now()
                with db() as conn:
                    conn.execute(
                        """INSERT INTO article_paragraph_translations
                           (article_id, paragraph_index, source_hash, source_text, translation_zh, provider, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT(article_id, paragraph_index) DO UPDATE SET
                             source_hash = excluded.source_hash, source_text = excluded.source_text,
                             translation_zh = excluded.translation_zh, provider = excluded.provider,
                             updated_at = excluded.updated_at""",
                        (article_id, paragraph_index, hashlib.sha256(originals[paragraph_index].encode("utf-8")).hexdigest(),
                         originals[paragraph_index], translated, result["provider"], now),
                    )
                    updated = dict(conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone())
                    values = article_paragraph_translation_values(conn, updated)
                    if values and all(value.strip() for value in values):
                        conn.execute(
                            "UPDATE articles SET translation_zh = ?, updated_at = ? WHERE id = ?",
                            ("\n\n".join(values), now, article_id),
                        )
                        updated["translation_zh"] = "\n\n".join(values)
                    item = article_with_paragraph_translations(conn, updated, payload.get("exam") or "")
                return json_response(self, {
                    "article": item,
                    "paragraph_index": paragraph_index,
                    "translated_text": translated,
                    "provider": result["provider"],
                    "cached": result["cached"],
                })
            match = re.fullmatch(r"/api/articles/(\d+)/content", path)
            if match:
                body = normalize_article_text(payload.get("title") or "", (payload.get("body") or "").strip())
                if not body:
                    return json_response(self, {"error": "Article body is required"}, 400)
                with db() as conn:
                    current = conn.execute("SELECT * FROM articles WHERE id = ?", (match.group(1),)).fetchone()
                    if not current:
                        return json_response(self, {"error": "Article not found"}, 404)
                    body = normalize_article_text(current["title"], body)
                    conn.execute("UPDATE articles SET body = ?, content_status = 'full', updated_at = ? WHERE id = ?", (body, utc_now(), match.group(1)))
                    article = conn.execute("SELECT * FROM articles WHERE id = ?", (match.group(1),)).fetchone()
                    item = article_with_paragraph_translations(conn, dict(article), payload.get("exam") or "")
                return json_response(self, {"article": item, "analysis": analyze_payload(item)})
            match = re.fullmatch(r"/api/articles/(\d+)/analyze", path)
            if match:
                with db() as conn:
                    article = conn.execute("SELECT * FROM articles WHERE id = ?", (match.group(1),)).fetchone()
                if not article:
                    return json_response(self, {"error": "Article not found"}, 404)
                return json_response(self, {"analysis": analyze_payload(article)})
            match = re.fullmatch(r"/api/articles/(\d+)/quizzes", path)
            if match:
                article_id = int(match.group(1))
                mode = payload.get("mode") or "mixed"
                style = payload.get("style") or "IELTS"
                question_type = payload.get("question_type") or ""
                with db() as conn:
                    article = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
                    if not article:
                        return json_response(self, {"error": "Article not found"}, 404)
                    quality = article_quality_profile(dict(article), style)
                    if not quality["training_eligible"]:
                        return json_response(self, {
                            "error": quality["training_block_reason"],
                            "quality": quality,
                        }, 422)
                    items = generate_quiz_items(article["body"], mode, style, question_type)
                    now = utc_now()
                    saved = []
                    for item in items:
                        saved.append(save_quiz_item(conn, article_id, style, mode, item, now))
                return json_response(self, {"quizzes": saved}, 201)
            match = re.fullmatch(r"/api/articles/(\d+)/extraction-feedback", path)
            if match:
                verdict = str(payload.get("verdict") or "").strip()
                allowed = {"correct", "caption_in_body", "author_disclosure_in_body", "other"}
                if verdict not in allowed:
                    return json_response(self, {"error": "Unsupported extraction feedback"}, 400)
                with db() as conn:
                    article = conn.execute("SELECT id, extraction_version FROM articles WHERE id = ?", (match.group(1),)).fetchone()
                    if not article:
                        return json_response(self, {"error": "Article not found"}, 404)
                    cursor = conn.execute(
                        """INSERT INTO article_extraction_feedback
                           (article_id, verdict, note, extraction_version, created_at)
                           VALUES (?, ?, ?, ?, ?)""",
                        (article["id"], verdict, str(payload.get("note") or "").strip()[:500], article["extraction_version"], utc_now()),
                    )
                    feedback = conn.execute("SELECT * FROM article_extraction_feedback WHERE id = ?", (cursor.lastrowid,)).fetchone()
                return json_response(self, {"feedback": dict(feedback)}, 201)
            match = re.fullmatch(r"/api/articles/(\d+)/extraction-block-labels", path)
            if match:
                label = str(payload.get("label") or "").strip()
                block_hash = str(payload.get("block_hash") or "").strip()
                if label not in BLOCK_LABELS:
                    return json_response(self, {"error": "Unsupported block label"}, 400)
                with db() as conn:
                    annotation = extraction_annotation_payload(conn, int(match.group(1)))
                    if not annotation:
                        return json_response(self, {"error": "Article not found"}, 404)
                    block = next((item for item in annotation["blocks"] if item["block_hash"] == block_hash), None)
                    if not block:
                        return json_response(self, {"error": "Extraction block not found"}, 404)
                    batch_item_id = int(payload.get("batch_item_id") or 0)
                    review_item = None
                    if batch_item_id:
                        review_item = conn.execute(
                            "SELECT * FROM article_extraction_review_items WHERE id = ? AND article_id = ?",
                            (batch_item_id, annotation["article"]["id"]),
                        ).fetchone()
                        if not review_item:
                            return json_response(self, {"error": "Review item does not match article"}, 400)
                    now = utc_now()
                    conn.execute(
                        """INSERT INTO article_extraction_block_labels
                           (article_id, block_hash, block_index, block_text, suggested_label, label,
                            source, extraction_version, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT(article_id, block_hash) DO UPDATE SET
                             block_index = excluded.block_index,
                             block_text = excluded.block_text,
                             suggested_label = excluded.suggested_label,
                             label = excluded.label,
                             source = excluded.source,
                             extraction_version = excluded.extraction_version,
                             updated_at = excluded.updated_at""",
                        (
                            annotation["article"]["id"], block_hash, block["block_index"], block["text"],
                            block["suggested_label"], label, annotation["article"]["source"],
                            annotation["article"]["extraction_version"], now, now,
                        ),
                    )
                    updated = extraction_annotation_payload(conn, annotation["article"]["id"])
                    if review_item:
                        elapsed = max(0, min(int(payload.get("elapsed_seconds") or 0), 300))
                        status = "completed" if updated["summary"]["remaining"] == 0 else "in_progress"
                        completed_at = now if status == "completed" else review_item["completed_at"]
                        conn.execute(
                            """UPDATE article_extraction_review_items SET status = ?,
                               started_at = CASE WHEN started_at = '' THEN ? ELSE started_at END,
                               last_activity_at = ?, completed_at = ?, active_seconds = active_seconds + ?
                               WHERE id = ?""",
                            (status, now, now, completed_at, elapsed, review_item["id"]),
                        )
                return json_response(self, updated)
            if path == "/api/cards":
                term = (payload.get("term") or "").strip()
                if not term:
                    return json_response(self, {"error": "Term is required"}, 400)
                sense_fields = {
                    "sense_key": str(payload.get("sense_key") or "").strip()[:200],
                    "part_of_speech": str(payload.get("part_of_speech") or "").strip()[:80],
                    "meaning_zh": str(payload.get("meaning_zh") or "").strip()[:1000],
                    "concept_en": str(payload.get("concept_en") or "").strip()[:2000],
                    "grammar_frame": str(payload.get("grammar_frame") or "").strip()[:1000],
                    "confusion_note": str(payload.get("confusion_note") or "").strip()[:1000],
                    "lexical_source": str(payload.get("lexical_source") or "").strip()[:300],
                }
                now = utc_now()
                with db() as conn:
                    existing = conn.execute(
                        """SELECT * FROM cards WHERE lower(trim(term)) = lower(?) AND sense_key = ?
                           ORDER BY updated_at DESC, id DESC LIMIT 1""",
                        (term, sense_fields["sense_key"]),
                    ).fetchone()
                    if existing:
                        context = (payload.get("context") or "").strip() or existing["context"]
                        source_article_id = payload.get("source_article_id") or existing["source_article_id"]
                        note = (payload.get("note") or "").strip() or existing["note"]
                        conn.execute(
                            """UPDATE cards SET term = ?, kind = ?, context = ?, source_article_id = ?, note = ?,
                               part_of_speech = ?, meaning_zh = ?, concept_en = ?, grammar_frame = ?,
                               confusion_note = ?, lexical_source = ?, updated_at = ?
                               WHERE id = ?""",
                            (
                                term,
                                payload.get("kind") or ("phrase" if " " in term else "word"),
                                context,
                                source_article_id,
                                note,
                                sense_fields["part_of_speech"] or existing["part_of_speech"],
                                sense_fields["meaning_zh"] or existing["meaning_zh"],
                                sense_fields["concept_en"] or existing["concept_en"],
                                sense_fields["grammar_frame"] or existing["grammar_frame"],
                                sense_fields["confusion_note"] or existing["confusion_note"],
                                sense_fields["lexical_source"] or existing["lexical_source"],
                                now,
                                existing["id"],
                            ),
                        )
                        card_id = existing["id"]
                        created = False
                    else:
                        cursor = conn.execute(
                            """
                            INSERT INTO cards
                            (term, kind, context, source_article_id, status, note, sense_key, part_of_speech,
                             meaning_zh, concept_en, grammar_frame, confusion_note, lexical_source, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                term,
                                payload.get("kind") or ("phrase" if " " in term else "word"),
                                payload.get("context") or "",
                                payload.get("source_article_id"),
                                payload.get("status") or "new",
                                payload.get("note") or "",
                                sense_fields["sense_key"],
                                sense_fields["part_of_speech"],
                                sense_fields["meaning_zh"],
                                sense_fields["concept_en"],
                                sense_fields["grammar_frame"],
                                sense_fields["confusion_note"],
                                sense_fields["lexical_source"],
                                now,
                                now,
                            ),
                        )
                        card_id = cursor.lastrowid
                        created = True
                        increment_daily_progress(conn, "vocabulary", 1)
                    card = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
                    ensure_review_item(conn, "card", int(card_id), now)
                return json_response(self, {"card": dict(card), "created": created}, 201 if created else 200)
            if path == "/api/attempts":
                quiz_id = int(payload.get("quiz_id"))
                answer = str(payload.get("answer") or "").strip()
                with db() as conn:
                    quiz = conn.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
                    if not quiz:
                        return json_response(self, {"error": "Quiz not found"}, 404)
                    result = record_quiz_attempt(
                        conn, quiz, answer,
                        confidence=payload.get("confidence"),
                        elapsed_seconds=payload.get("elapsed_seconds"),
                        answer_changes=payload.get("answer_changes"),
                        hint_used=payload.get("hint_used"),
                    )
                return json_response(self, result)
            if path == "/api/practice-sessions/record":
                raw_ids = payload.get("attempt_ids") or []
                if not isinstance(raw_ids, list) or not raw_ids:
                    return json_response(self, {"error": "At least one attempt is required"}, 400)
                try:
                    attempt_ids = list(dict.fromkeys(int(value) for value in raw_ids if int(value) > 0))
                except (TypeError, ValueError):
                    return json_response(self, {"error": "Attempt ids must be integers"}, 400)
                if not attempt_ids or len(attempt_ids) > 50:
                    return json_response(self, {"error": "Record between 1 and 50 attempts"}, 400)
                placeholders = ",".join("?" for _ in attempt_ids)
                with db() as conn:
                    attempts = conn.execute(
                        f"""
                        SELECT at.*, q.article_id, q.style, q.question_type, q.skill
                        FROM attempts at
                        JOIN quizzes q ON q.id = at.quiz_id
                        WHERE at.id IN ({placeholders})
                        ORDER BY at.id
                        """,
                        attempt_ids,
                    ).fetchall()
                    if len(attempts) != len(attempt_ids):
                        return json_response(self, {"error": "One or more attempts were not found"}, 404)
                    if any(row["session_id"] is not None for row in attempts):
                        return json_response(self, {"error": "One or more attempts already belong to a session"}, 409)
                    article_ids = {row["article_id"] for row in attempts}
                    styles = {row["style"] for row in attempts}
                    question_types = {row["question_type"] for row in attempts}
                    question_count = max(len(attempts), min(50, int(payload.get("question_count") or len(attempts))))
                    summary = summarize_attempt_rows(attempts, question_count)
                    cursor = conn.execute(
                        """
                        INSERT INTO practice_sessions
                        (article_id, style, question_type, session_mode, question_count, answered_count,
                         correct_count, elapsed_seconds, score, skill_summary_json, error_summary_json,
                         confidence_summary_json, completed_at)
                        VALUES (?, ?, ?, 'practice', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            next(iter(article_ids)) if len(article_ids) == 1 else None,
                            next(iter(styles)) if len(styles) == 1 else "mixed",
                            next(iter(question_types)) if len(question_types) == 1 else "mixed",
                            summary["question_count"], summary["answered_count"], summary["correct_count"],
                            max(0, min(21600, int(payload.get("elapsed_seconds") or 0))), summary["score"],
                            json.dumps(summary["skill_summary"], ensure_ascii=False),
                            json.dumps(summary["error_summary"], ensure_ascii=False),
                            json.dumps(summary["confidence_summary"], ensure_ascii=False), utc_now(),
                        ),
                    )
                    session_id = cursor.lastrowid
                    conn.execute(
                        f"UPDATE attempts SET session_id = ? WHERE id IN ({placeholders})",
                        (session_id, *attempt_ids),
                    )
                    increment_daily_progress(conn, "practice", summary["answered_count"])
                    detail = practice_session_detail(conn, session_id)
                detail["calibration"] = run_profile_calibration()
                return json_response(self, detail, 201)
            if path == "/api/practice-sessions":
                raw_answers = payload.get("answers") or []
                if not isinstance(raw_answers, list) or not raw_answers:
                    return json_response(self, {"error": "At least one quiz answer is required"}, 400)
                if len(raw_answers) > 50:
                    return json_response(self, {"error": "A practice session supports at most 50 questions"}, 400)
                normalized: list[tuple[int, str, int | None, int, int, bool]] = []
                seen: set[int] = set()
                for item in raw_answers:
                    quiz_id = int(item.get("quiz_id") or 0)
                    if not quiz_id or quiz_id in seen:
                        return json_response(self, {"error": "Quiz answers must use unique valid ids"}, 400)
                    seen.add(quiz_id)
                    normalized.append((
                        quiz_id, str(item.get("answer") or "").strip(), normalize_confidence(item.get("confidence")),
                        max(0, min(7200, int(item.get("elapsed_seconds") or 0))),
                        max(0, min(100, int(item.get("answer_changes") or 0))), bool(item.get("hint_used")),
                    ))
                placeholders = ",".join("?" for _ in normalized)
                with db() as conn:
                    rows = conn.execute(
                        f"SELECT * FROM quizzes WHERE id IN ({placeholders})", [item[0] for item in normalized]
                    ).fetchall()
                    by_id = {row["id"]: row for row in rows}
                    if len(by_id) != len(normalized):
                        return json_response(self, {"error": "One or more quizzes were not found"}, 404)
                    quizzes = [by_id[item[0]] for item in normalized]
                    article_ids = {row["article_id"] for row in quizzes}
                    styles = {row["style"] for row in quizzes}
                    question_types = {row["question_type"] for row in quizzes}
                    now = utc_now()
                    cursor = conn.execute(
                        """
                        INSERT INTO practice_sessions
                        (article_id, style, question_type, session_mode, question_count, completed_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            next(iter(article_ids)) if len(article_ids) == 1 else None,
                            next(iter(styles)) if len(styles) == 1 else "mixed",
                            next(iter(question_types)) if len(question_types) == 1 else "mixed",
                            "mock" if payload.get("session_mode") == "mock" else "practice",
                            len(quizzes), now,
                        ),
                    )
                    session_id = cursor.lastrowid
                    results = [
                        record_quiz_attempt(conn, by_id[quiz_id], answer, session_id, confidence, elapsed, changes, hint)
                        for quiz_id, answer, confidence, elapsed, changes, hint in normalized
                    ]
                    skill_summary: dict[str, dict[str, int]] = {}
                    error_summary: dict[str, int] = {}
                    confidence_summary: dict[str, dict[str, int]] = {}
                    confidence_labels = {1: "猜测", 2: "犹豫", 3: "确定"}
                    for result in results:
                        skill = result["skill"]
                        stats = skill_summary.setdefault(skill, {"total": 0, "correct": 0})
                        stats["total"] += 1
                        stats["correct"] += 1 if result["correct"] else 0
                        if result["error_type"]:
                            error_summary[result["error_type"]] = error_summary.get(result["error_type"], 0) + 1
                        confidence = result.get("confidence")
                        if confidence in confidence_labels:
                            label = confidence_labels[confidence]
                            stats = confidence_summary.setdefault(label, {"total": 0, "correct": 0})
                            stats["total"] += 1
                            stats["correct"] += 1 if result["correct"] else 0
                    correct_count = sum(1 for result in results if result["correct"])
                    answered_count = sum(1 for item in normalized if item[1])
                    elapsed_seconds = max(0, min(21600, int(payload.get("elapsed_seconds") or 0)))
                    score = round(correct_count / len(results) * 100)
                    conn.execute(
                        """
                        UPDATE practice_sessions
                        SET answered_count = ?, correct_count = ?, elapsed_seconds = ?, score = ?,
                            skill_summary_json = ?, error_summary_json = ?, confidence_summary_json = ?
                        WHERE id = ?
                        """,
                        (
                            answered_count, correct_count, elapsed_seconds, score,
                            json.dumps(skill_summary, ensure_ascii=False),
                            json.dumps(error_summary, ensure_ascii=False),
                            json.dumps(confidence_summary, ensure_ascii=False), session_id,
                        ),
                    )
                    increment_daily_progress(conn, "practice", answered_count)
                    session = conn.execute("SELECT * FROM practice_sessions WHERE id = ?", (session_id,)).fetchone()
                calibration = run_profile_calibration()
                return json_response(
                    self,
                    {"session": practice_session_payload(session), "results": results, "progress": results[-1]["progress"], "calibration": calibration},
                    201,
                )
            if path == "/api/practice/next-set":
                style = str(payload.get("style") or "IELTS").strip()
                focus_type = str(payload.get("question_type") or "").strip()
                focus_error = str(payload.get("error_type") or "").strip()
                limit = max(3, min(10, int(payload.get("limit") or 10)))
                with db() as conn:
                    filters = ["m.solved = 0", "q.style = ?"]
                    filter_params: list[object] = [style]
                    if focus_type:
                        filters.append("q.question_type = ?")
                        filter_params.append(focus_type)
                    if focus_error:
                        filters.append("m.error_type = ?")
                        filter_params.append(focus_error)
                    weak_rows = conn.execute(
                        f"""
                        SELECT m.error_type, m.evidence AS mistake_evidence,
                               q.*, a.body AS article_body
                        FROM mistakes m
                        JOIN quizzes q ON q.id = m.quiz_id
                        JOIN articles a ON a.id = q.article_id
                        WHERE {' AND '.join(filters)}
                        ORDER BY m.created_at DESC
                        LIMIT 12
                        """,
                        filter_params,
                    ).fetchall()
                    saved: list[dict] = []
                    focus: list[str] = []
                    now = utc_now()
                    used_prompts: set[str] = set()
                    for row in weak_rows:
                        original = dict(row)
                        if original.get("error_type") and original["error_type"] not in focus:
                            focus.append(original["error_type"])
                        for item in generate_similar_items(original["article_body"], original, 3):
                            if item["prompt"] in used_prompts:
                                continue
                            used_prompts.add(item["prompt"])
                            saved.append(save_quiz_item(conn, original["article_id"], style, "weakness-next", item, now))
                            if len(saved) >= limit:
                                break
                        if len(saved) >= limit:
                            break
                    if len(saved) < limit:
                        existing = conn.execute(
                            f"""
                            SELECT q.* FROM quizzes q
                            WHERE q.style = ?
                              {"AND q.question_type = ?" if focus_type else ""}
                              AND NOT EXISTS (
                              SELECT 1 FROM attempts a WHERE a.quiz_id = q.id
                            )
                            ORDER BY q.created_at DESC, q.id DESC LIMIT ?
                            """,
                            tuple([style] + ([focus_type] if focus_type else []) + [limit - len(saved)]),
                        ).fetchall()
                        saved.extend(quiz_payload(row) for row in existing)
                return json_response(
                    self,
                    {
                        "quizzes": saved[:limit],
                        "focus": focus,
                        "reason": "优先依据未解决错题的题型和错因生成；不足部分使用当前考试未作答题。",
                        "filters": {"question_type": focus_type, "error_type": focus_error},
                    },
                    201,
                )
            match = re.fullmatch(r"/api/mistakes/(\d+)/similar", path)
            if match:
                count = max(1, min(5, int(payload.get("count") or 3)))
                with db() as conn:
                    original = conn.execute(
                        """
                        SELECT m.id AS mistake_id, m.user_answer, m.remedial_correct_streak,
                               q.id AS quiz_id,
                               q.article_id, q.style, q.type, q.question_type, q.skill, q.difficulty,
                               q.prompt, q.answer, q.evidence, q.note, a.body AS article_body
                        FROM mistakes m
                        LEFT JOIN quizzes q ON q.id = m.quiz_id
                        LEFT JOIN articles a ON a.id = q.article_id
                        WHERE m.id = ?
                        """,
                        (match.group(1),),
                    ).fetchone()
                    if not original or not original["quiz_id"]:
                        return json_response(self, {"error": "Original quiz not found"}, 404)
                    original_item = dict(original)
                    source_text = original_item.get("article_body") or original_item.get("evidence") or ""
                    items = generate_similar_items(source_text, original_item, count)
                    now = utc_now()
                    saved = []
                    for item in items:
                        item["parent_mistake_id"] = int(original_item["mistake_id"])
                        item["remedial_level"] = min(3, int(original_item.get("remedial_correct_streak") or 0) + 1)
                        saved.append(save_quiz_item(
                            conn, original_item["article_id"], original_item["style"] or "IELTS", "remedial", item, now
                        ))
                return json_response(self, {"quizzes": saved}, 201)
            match = re.fullmatch(r"/api/mistakes/(\d+)/solve", path)
            if match:
                with db() as conn:
                    current = conn.execute("SELECT solved, reward_claimed FROM mistakes WHERE id = ?", (match.group(1),)).fetchone()
                    if not current:
                        return json_response(self, {"error": "Mistake not found"}, 404)
                    becoming_solved = not bool(current["solved"])
                    conn.execute(
                        """UPDATE mistakes SET solved = 1 - solved,
                           mastered_at = CASE WHEN solved = 0 THEN ? ELSE '' END,
                           mastery_source = CASE WHEN solved = 0 THEN 'self-confirmed' ELSE '' END
                           WHERE id = ?""",
                        (utc_now(), match.group(1)),
                    )
                    earns_reward = becoming_solved and not bool(current["reward_claimed"])
                    if earns_reward:
                        conn.execute("UPDATE mistakes SET reward_claimed = 1 WHERE id = ?", (match.group(1),))
                        increment_daily_progress(conn, "review", 1)
                    if becoming_solved:
                        ensure_review_item(conn, "mistake", int(match.group(1)), utc_now())
                    progress = award_progress(conn, 5, reviewed=True) if earns_reward else progress_payload(conn)
                return json_response(self, {"ok": True, "points": 5 if earns_reward else 0, "progress": progress})
            if path == "/api/feeds":
                now = utc_now()
                with db() as conn:
                    cursor = conn.execute(
                        """
                        INSERT OR IGNORE INTO feeds (name, url, language, level_hint, active, created_at)
                        VALUES (?, ?, ?, ?, 1, ?)
                        """,
                        (
                            payload.get("name") or "Custom feed",
                            payload.get("url") or "",
                            payload.get("language") or "en",
                            payload.get("level_hint") or "B1-B2",
                            now,
                        ),
                    )
                return json_response(self, {"id": cursor.lastrowid}, 201)
            if path == "/api/feeds/refresh":
                return json_response(self, fetch_feed_items(trigger_type="manual"))
            return json_response(self, {"error": "Not found"}, 404)
        except json.JSONDecodeError:
            return json_response(self, {"error": "Invalid JSON"}, 400)
        except Exception as exc:
            return json_response(self, {"error": str(exc)}, 500)

    def do_DELETE(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        dictionary_match = re.fullmatch(r"/api/private-dictionaries/(\d+)", path)
        if dictionary_match:
            if not self.browser_authorized():
                return json_response(self, {"error": "Invalid local dictionary token"}, 401)
            with db() as conn:
                removed = remove_private_dictionary_index(conn, int(dictionary_match.group(1)))
                sources = private_dictionary_status(conn)
            if not removed:
                return json_response(self, {"error": "Private dictionary not found"}, 404)
            return json_response(self, {"removed": True, "private_sources": sources})
        match = re.fullmatch(r"/api/speaking-attempts/(\d+)", path)
        if not match:
            return json_response(self, {"error": "Not found"}, 404)
        attempt_id = int(match.group(1))
        try:
            with db() as conn:
                attempt = speaking_attempt_payload(conn, attempt_id)
            if not attempt:
                return json_response(self, {"error": "Speaking attempt not found"}, 404)
            filename = Path(attempt.get("audio_filename") or "").name
            if filename:
                directory = speaking_audio_dir()
                target = (directory / filename).resolve()
                if directory not in target.parents:
                    return json_response(self, {"error": "Invalid speaking audio path"}, 400)
                target.unlink(missing_ok=True)
            with db() as conn:
                mark_speaking_attempt_deleted(conn, attempt_id)
            return json_response(self, {"deleted": True, "attempt_id": attempt_id})
        except Exception as exc:
            return json_response(self, {"error": str(exc)}, 500)

    def quiz_row(self, row: sqlite3.Row) -> dict:
        return quiz_payload(row)

    def serve_static(self, path: str) -> None:
        if path == "/":
            path = "/index.html"
        safe = Path(urllib.parse.unquote(path.lstrip("/")))
        file_path = (FRONTEND / safe).resolve()
        if FRONTEND.resolve() not in file_path.parents and file_path != FRONTEND.resolve():
            return json_response(self, {"error": "Forbidden"}, 403)
        if not file_path.exists() or not file_path.is_file():
            return json_response(self, {"error": "Not found"}, 404)
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        text_response(self, file_path.read_bytes(), content_type, cache_control="no-store, max-age=0")


def main() -> None:
    init_db()
    port_value = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("LANGUAGE_COACH_PORT", "8765")
    try:
        port = int(port_value)
    except ValueError as exc:
        raise SystemExit(f"Invalid Language Coach port: {port_value}") from exc
    if not 1 <= port <= 65535:
        raise SystemExit(f"Language Coach port must be between 1 and 65535: {port}")
    server = ThreadingHTTPServer(("127.0.0.1", port), App)
    print(f"Language Coach v2 running at http://127.0.0.1:{port}")
    print(f"SQLite database: {DB_PATH}")
    start_feed_scheduler()
    server.serve_forever()


if __name__ == "__main__":
    main()
