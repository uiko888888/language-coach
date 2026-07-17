from __future__ import annotations

import html
import hashlib
import email.utils
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
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DATA = ROOT / "data"
DB_PATH = DATA / "language_coach.sqlite"
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


def normalize_article_text(title: str, body: str) -> str:
    text = re.sub(r"\s+", " ", body or "").strip()
    clean_title = re.sub(r"\s+", " ", title or "").strip()
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
    return {"phrase": term, "meaning_zh": meaning_zh, "synonyms": synonyms or [], "antonyms": antonyms or []}


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
    "The New York Times": {"category": "每日新闻", "homepage": "https://www.nytimes.com/", "access_mode": "摘要与原站", "rights_mode": "仅元数据、摘要和用户授权摘录", "formats": ["文章", "播客"], "cadence": "每日"},
    "The New Yorker": {"category": "深度评论", "homepage": "https://www.newyorker.com/", "access_mode": "摘要与原站", "rights_mode": "仅元数据、摘要和用户授权摘录", "formats": ["文章", "播客"], "cadence": "每周"},
    "The Economist": {"category": "深度评论", "homepage": "https://www.economist.com/", "access_mode": "摘要与原站", "rights_mode": "仅元数据、摘要和用户授权摘录", "formats": ["文章", "播客"], "cadence": "每日"},
    "National Geographic": {"category": "科学与自然", "homepage": "https://www.nationalgeographic.com/", "access_mode": "摘要与原站", "rights_mode": "仅元数据、摘要和用户授权摘录", "formats": ["文章", "视频"], "cadence": "每周"},
    "VOA Learning English": {"category": "听力与演讲", "homepage": "https://learningenglish.voanews.com/", "access_mode": "公开页面", "rights_mode": "保存链接、公开 transcript 和短语境", "formats": ["文章", "音频", "视频"], "cadence": "每日"},
    "TED": {"category": "听力与演讲", "homepage": "https://www.ted.com/", "access_mode": "公开页面", "rights_mode": "保存链接、公开 transcript 和短语境", "formats": ["视频", "字幕", "演讲稿"], "cadence": "每周"},
    "Amazon Books": {"category": "小说与图书", "homepage": "https://www.amazon.com/books-used-books-textbooks/", "access_mode": "书籍发现", "rights_mode": "仅书籍元数据、简介和原站链接", "formats": ["图书元数据"], "cadence": "按需"},
    "HBO Max": {"category": "影视与流媒体", "homepage": "https://www.max.com/", "access_mode": "用户订阅与本地字幕", "rights_mode": "不抓取视频；仅用户合法字幕、时间点和短语境", "formats": ["视频", "字幕"], "cadence": "按需"},
    "Apple TV+": {"category": "影视与流媒体", "homepage": "https://tv.apple.com/", "access_mode": "用户订阅与本地字幕", "rights_mode": "不抓取视频；仅用户合法字幕、时间点和短语境", "formats": ["视频", "字幕"], "cadence": "按需"},
    "Prime Video": {"category": "影视与流媒体", "homepage": "https://www.primevideo.com/", "access_mode": "用户订阅与本地字幕", "rights_mode": "不抓取视频；仅用户合法字幕、时间点和短语境", "formats": ["视频", "字幕"], "cadence": "按需"},
    "Project Gutenberg": {"category": "小说与图书", "homepage": "https://www.gutenberg.org/", "access_mode": "开放全文", "rights_mode": "仅公共领域或许可允许的全文", "formats": ["小说", "图书"], "cadence": "按需"},
    "Standard Ebooks": {"category": "小说与图书", "homepage": "https://standardebooks.org/", "access_mode": "开放全文", "rights_mode": "公共领域电子书", "formats": ["小说", "图书"], "cadence": "按需"},
    "Google Scholar": {"category": "学术研究", "homepage": "https://scholar.google.com/", "access_mode": "检索与提醒", "rights_mode": "保存论文元数据、摘要、DOI 和合法链接", "formats": ["论文元数据", "摘要"], "cadence": "按提醒"},
    "arXiv": {"category": "学术研究", "homepage": "https://arxiv.org/", "access_mode": "开放元数据", "rights_mode": "按论文许可证处理全文", "formats": ["论文", "摘要"], "cadence": "每日"},
    "PubMed": {"category": "学术研究", "homepage": "https://pubmed.ncbi.nlm.nih.gov/", "access_mode": "开放元数据", "rights_mode": "保存元数据和摘要；全文按许可处理", "formats": ["论文元数据", "摘要"], "cadence": "每日"},
    "Substack": {"category": "博客与通讯", "homepage": "https://substack.com/", "access_mode": "用户订阅", "rights_mode": "按作者订阅权限保存摘要、链接和短语境", "formats": ["博客", "通讯", "播客"], "cadence": "按订阅"},
}


def source_catalog() -> list[dict]:
    feed_by_name = {feed["name"]: feed for feed in DEFAULT_FEEDS}
    items = []
    for name, feed in feed_by_name.items():
        profile = SOURCE_PROFILES.get(name, {"topics": ["综合"]})
        source_kind, default_content_type = SOURCE_CLASSIFICATION.get(name, ("其他来源", "explainer"))
        items.append({
            "name": name,
            "category": profile["topics"][0] if profile.get("topics") else "综合",
            "homepage": feed["url"],
            "access_mode": "RSS 自动更新",
            "rights_mode": "保存合法摘要、源站链接和 feed 提供的完整内容",
            "formats": ["文章"],
            "cadence": "每日",
            "source_kind": source_kind,
            "default_content_type": default_content_type,
            "automatic": True,
        })
    for name, metadata in SOURCE_CATALOG_EXTRAS.items():
        items.append({
            "name": name,
            **metadata,
            "source_kind": "外部内容平台",
            "default_content_type": "culture" if metadata["category"] in {"影视与流媒体", "小说与图书"} else "explainer",
            "automatic": False,
        })
    return sorted(items, key=lambda item: (not item["automatic"], item["category"], item["name"]))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
           (title, language, level, topic, source, source_url, content_status, content_type, body, created_at, updated_at)
           VALUES (?, ?, ?, 'literature', 'private EPUB', ?, 'full', 'culture', ?, ?, ?)""",
        (title, row["language"] or "en", estimate_level(row["body"]), source_url, row["body"], now, now),
    )
    conn.execute("UPDATE book_chapters SET article_id = ?, updated_at = ? WHERE id = ?", (cursor.lastrowid, now, chapter_id))
    return dict(conn.execute("SELECT * FROM articles WHERE id = ?", (cursor.lastrowid,)).fetchone())


def unique_cards_payload(conn: sqlite3.Connection) -> list[dict]:
    rows = rows_to_dicts(conn.execute("SELECT * FROM cards ORDER BY updated_at DESC, id DESC").fetchall())
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
              status TEXT NOT NULL DEFAULT 'new',
              note TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (source_article_id) REFERENCES articles(id)
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
        article_columns = {row[1] for row in conn.execute("PRAGMA table_info(articles)")}
        if "translation_zh" not in article_columns:
            conn.execute("ALTER TABLE articles ADD COLUMN translation_zh TEXT NOT NULL DEFAULT ''")
        if "content_status" not in article_columns:
            conn.execute("ALTER TABLE articles ADD COLUMN content_status TEXT NOT NULL DEFAULT 'summary'")
        if "content_type" not in article_columns:
            conn.execute("ALTER TABLE articles ADD COLUMN content_type TEXT NOT NULL DEFAULT 'auto'")
        for column in ("published_at", "source_guid", "content_hash"):
            if column not in article_columns:
                conn.execute(f"ALTER TABLE articles ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
        feed_columns = {row[1] for row in conn.execute("PRAGMA table_info(feeds)")}
        for column, definition in {
            "etag": "TEXT NOT NULL DEFAULT ''",
            "last_modified": "TEXT NOT NULL DEFAULT ''",
            "last_attempt_at": "TEXT NOT NULL DEFAULT ''",
            "last_success_at": "TEXT NOT NULL DEFAULT ''",
            "consecutive_failures": "INTEGER NOT NULL DEFAULT 0",
            "last_error": "TEXT NOT NULL DEFAULT ''",
        }.items():
            if column not in feed_columns:
                conn.execute(f"ALTER TABLE feeds ADD COLUMN {column} {definition}")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_source_guid ON articles(source, source_guid) WHERE source_guid != ''"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_content_hash ON articles(source, content_hash) WHERE content_hash != ''"
        )
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
        mistake_columns = {row[1] for row in conn.execute("PRAGMA table_info(mistakes)")}
        if "reward_claimed" not in mistake_columns:
            conn.execute("ALTER TABLE mistakes ADD COLUMN reward_claimed INTEGER NOT NULL DEFAULT 0")
        if "skill" not in mistake_columns:
            conn.execute("ALTER TABLE mistakes ADD COLUMN skill TEXT NOT NULL DEFAULT ''")
        if "error_type" not in mistake_columns:
            conn.execute("ALTER TABLE mistakes ADD COLUMN error_type TEXT NOT NULL DEFAULT ''")
        if "explanation_json" not in mistake_columns:
            conn.execute("ALTER TABLE mistakes ADD COLUMN explanation_json TEXT NOT NULL DEFAULT '{}'")
        quiz_columns = {row[1] for row in conn.execute("PRAGMA table_info(quizzes)")}
        for column, definition in {
            "question_type": "TEXT NOT NULL DEFAULT ''",
            "skill": "TEXT NOT NULL DEFAULT ''",
            "difficulty": "TEXT NOT NULL DEFAULT 'B2'",
            "validation_json": "TEXT NOT NULL DEFAULT '{}'",
            "generation_source": "TEXT NOT NULL DEFAULT 'legacy'",
            "metadata_json": "TEXT NOT NULL DEFAULT '{}'",
        }.items():
            if column not in quiz_columns:
                conn.execute(f"ALTER TABLE quizzes ADD COLUMN {column} {definition}")
        attempt_columns = {row[1] for row in conn.execute("PRAGMA table_info(attempts)")}
        if "error_type" not in attempt_columns:
            conn.execute("ALTER TABLE attempts ADD COLUMN error_type TEXT NOT NULL DEFAULT ''")
        if "session_id" not in attempt_columns:
            conn.execute("ALTER TABLE attempts ADD COLUMN session_id INTEGER")
        if "confidence" not in attempt_columns:
            conn.execute("ALTER TABLE attempts ADD COLUMN confidence INTEGER")
        session_columns = {row[1] for row in conn.execute("PRAGMA table_info(practice_sessions)")}
        if "confidence_summary_json" not in session_columns:
            conn.execute("ALTER TABLE practice_sessions ADD COLUMN confidence_summary_json TEXT NOT NULL DEFAULT '{}'")
        card_columns = {row[1] for row in conn.execute("PRAGMA table_info(cards)")}
        if "kind" not in card_columns:
            conn.execute("ALTER TABLE cards ADD COLUMN kind TEXT NOT NULL DEFAULT 'word'")
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


def json_response(handler: BaseHTTPRequestHandler, payload: object, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
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


def clean_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


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
    guide = type_guides.get(quiz_type, type_guides["reading"])

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
DAILY_PLAN_TASKS = {"reading", "practice", "review", "vocabulary"}
DAILY_PLAN_DEFAULT_TARGETS = {"reading": 1, "practice": 5, "review": 2, "vocabulary": 5}
DEFAULT_LEARNER_SETTINGS = {
    "daily_minutes": 15,
    "daily_tasks": ["reading", "practice", "review"],
    "daily_targets": DAILY_PLAN_DEFAULT_TARGETS,
    "short_goal": "",
    "short_goal_date": "",
    "long_goal": "",
    "long_goal_date": "",
    "recommendations_enabled": True,
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
    settings["daily_minutes"] = settings["daily_minutes"] if settings["daily_minutes"] in DAILY_PLAN_MINUTES else 15
    settings["daily_tasks"] = [task for task in settings["daily_tasks"] if task in DAILY_PLAN_TASKS] or ["reading"]
    raw_targets = settings.get("daily_targets") if isinstance(settings.get("daily_targets"), dict) else {}
    settings["daily_targets"] = {
        task: max(1, min(50, int(raw_targets.get(task) or DAILY_PLAN_DEFAULT_TARGETS[task])))
        for task in DAILY_PLAN_TASKS
    }
    settings["recommendations_enabled"] = bool(settings["recommendations_enabled"])
    return settings


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
        "short_goal": str(payload.get("short_goal") or "").strip()[:160],
        "short_goal_date": str(payload.get("short_goal_date") or "").strip()[:20],
        "long_goal": str(payload.get("long_goal") or "").strip()[:160],
        "long_goal_date": str(payload.get("long_goal_date") or "").strip()[:20],
        "recommendations_enabled": bool(payload.get("recommendations_enabled", True)),
    }
    with db() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (LEARNER_SETTINGS_KEY, json.dumps(settings, ensure_ascii=False)),
        )
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
    return {
        "date": target_day,
        "minutes": settings["daily_minutes"],
        "tasks": tasks,
        "items": rows_to_dicts(item_rows),
        "overall_percent": overall_percent,
        "remaining_minutes": remaining_minutes,
        "completed": bool(tasks) and all(item["done"] for item in tasks),
        "summary": "今日计划已完成" if tasks and all(item["done"] for item in tasks) else f"还需约 {remaining_minutes} 分钟",
    }


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
    return {
        "source_tier": profile["tier"],
        "source_topics": profile["topics"],
        "source_exams": profile["exams"],
        "exam_fit": fit,
        "source_kind": source_kind,
        "default_content_type": default_content_type,
        "default_content_type_label": CONTENT_TYPE_LABELS.get(default_content_type, "学术解释"),
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
    score = source_quality + freshness + depth + level_fit + exam_score
    reasons = []
    if article["exam_fit"] >= 90:
        reasons.append("考试匹配")
    if freshness >= 15:
        reasons.append("近期更新")
    if source_quality >= 25:
        reasons.append("核心来源")
    if depth >= 10:
        reasons.append("适合精读")
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
    item.update(recommendation_profile(item))
    item["content_type"] = infer_content_type(item)
    item["content_type_label"] = CONTENT_TYPE_LABELS[item["content_type"]]
    item["content_status"] = item.get("content_status") or ("full" if item["source"] in {"seed", "manual"} else "summary")
    item["content_word_count"] = len(words(item.get("body", "")))
    original_paragraphs = [value for value in re.split(r"\n\s*\n", item.get("body", "")) if value.strip()]
    translated_paragraphs = [value for value in re.split(r"\n\s*\n", item.get("translation_zh", "")) if value.strip()]
    item["paragraph_count"] = len(original_paragraphs)
    item["translation_paragraph_count"] = len(translated_paragraphs)
    item["translation_aligned"] = bool(translated_paragraphs) and len(original_paragraphs) == len(translated_paragraphs)
    return item


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
    content_type = query.get("content_type", [""])[0]
    if content_type:
        ranked = [item for item in ranked if item["content_type"] == content_type]
    return ranked


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
    plan = daily_plan_snapshot(settings)
    articles = list_articles({"exam": [exam]})
    catalog = {item["name"]: item for item in source_catalog()}
    active = [item for item in subscription_payload() if item["active"]]
    source_subscriptions = {item["target_value"] for item in active if item["target_type"] == "source"}
    category_subscriptions = {item["target_value"] for item in active if item["target_type"] == "category"}

    enriched = []
    for article in articles:
        category = catalog.get(article["source"], {}).get("category", article.get("source_topics", ["综合"])[0])
        subscribed = article["source"] in source_subscriptions or category in category_subscriptions
        study_minutes = estimated_study_minutes(article)
        interest_bonus = (
            (24 if subscribed else 0)
            + (12 if article["content_type"] in {"culture", "report"} else 0)
            + (9 if study_minutes <= 15 else 0)
            + (8 if article.get("level") in {"B1", "B2", "B1-B2"} else 0)
        )
        exam_bonus = round(article["exam_fit"] * 0.25) + (10 if study_minutes >= 15 else 0)
        enriched.append({
            **article,
            "catalog_category": category,
            "subscribed": subscribed,
            "study_minutes": study_minutes,
            "today_score": article["recommendation_score"] + ((interest_bonus if mode == "interest" else exam_bonus) if settings["recommendations_enabled"] else 0),
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
            ("practice", "顺手练一练", choose(lambda item: item["content_type"] in {"report", "culture", "explainer"}), "把喜欢的内容转成词汇和小练习"),
        )
    else:
        lane_specs = (
            ("quick", "5 分钟热身", choose(lambda item: item["study_minutes"] <= 5 and item["content_type"] in {"report", "institution"}), "进入考试阅读状态"),
            ("focused", "15 分钟精读", choose(lambda item: item["exam_fit"] >= 90 and item["study_minutes"] <= 15), "匹配当前考试与难度"),
            ("deep", "30 分钟专项", choose(lambda item: item["content_type"] in {"opinion", "explainer", "research"}), "适合证据、同义替换与题型训练"),
        )

    lanes = []
    for lane_id, label, item, base_reason in lane_specs:
        if not item:
            continue
        if not settings["recommendations_enabled"]:
            reason = "通用内容安排"
        else:
            reason = "来自你的订阅" if item["subscribed"] else base_reason
            active_goal = settings["short_goal"] or settings["long_goal"]
            if active_goal:
                reason = f"{reason} · 对应当前目标"
        lanes.append({"id": lane_id, "label": label, "reason": reason, "article": item})
    return {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "exam": exam or "general",
        "mode": mode,
        "subscription_count": len(active),
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


def lexical_query_context(term: str, limit: int = 5) -> dict:
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
               WHERE lower(body) LIKE lower(?) ORDER BY updated_at DESC, id DESC LIMIT 20""",
            (f"%{normalized}%",),
        ).fetchall()

    if card and card["context"]:
        contexts.append({
            "text": card["context"],
            "source": "生词本语境",
            "article_id": card["source_article_id"],
            "article_title": "",
        })
    pattern = re.compile(rf"(?<![A-Za-z]){re.escape(normalized)}(?![A-Za-z])", re.I)
    for row in article_rows:
        context = next((sentence for sentence in sentences(row["body"]) if pattern.search(sentence)), "")
        if not context or any(item["text"] == context for item in contexts):
            continue
        contexts.append({
            "text": context,
            "source": row["source"],
            "article_id": row["id"],
            "article_title": row["title"],
        })
        if len(contexts) >= limit:
            break
    return {
        "translation_zh": (clip or cached or {"translated_text": ""})["translated_text"],
        "saved": bool(card),
        "card_id": card["id"] if card else None,
        "card_status": card["status"] if card else "",
        "contexts": contexts[:limit],
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
    unique = []
    seen = set()
    for phrase, sentence in candidates:
        key = phrase.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append({"phrase": phrase, "meaning_zh": "", "source": "个人文章语境", "context": sentence, "synonyms": [], "antonyms": []})
    return unique[:limit]


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
    collocations = contextual_collocations(term, learning["contexts"])
    source_segments = [term, *[item["phrase"] for item in collocations]]
    for row in rows:
        source_segments.extend(json.loads(row["definitions_json"] or "[]"))
        source_segments.extend(json.loads(row["examples_json"] or "[]"))
    cached_zh = cached_segment_translations(source_segments)
    grouped: dict[tuple[str, str], list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault((row["lemma"].casefold(), row["pos"]), []).append(row)

    results = []
    for (_, pos), sense_rows in list(grouped.items())[:limit]:
        headword = sense_rows[0]["lemma"]
        pronunciations = []
        senses = []
        synonyms = []
        examples = []
        semantic_relations: dict[str, list[str]] = {}
        for row in sense_rows:
            pronunciations.extend(json.loads(row["pronunciations_json"] or "[]"))
            definitions = json.loads(row["definitions_json"] or "[]")
            sense_examples = json.loads(row["examples_json"] or "[]")
            members = json.loads(row["members_json"] or "[]")
            synonyms.extend(member for member in members if member.casefold() != normalized)
            examples.extend(sense_examples)
            senses.append({
                "synset_id": row["synset_id"],
                "definitions": definitions,
                "definition_translations": [cached_zh.get(value, "") for value in definitions],
                "examples": sense_examples,
                "example_translations": [cached_zh.get(value, "") for value in sense_examples],
                "synonyms": members,
            })
            for relation_type, members in relations_by_synset.get(row["synset_id"], {}).items():
                semantic_relations.setdefault(relation_type, []).extend(members)

        unique = lambda values: list(dict.fromkeys(value for value in values if value))
        pronunciations = unique(pronunciations)
        synonyms = unique(synonyms)
        examples = unique(examples)
        antonyms = unique(semantic_relations.get("antonym", []))
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
            "pos": WORDNET_POS_LABELS.get(pos, pos),
            "ipa_uk": pronunciations[0] if pronunciations else "",
            "ipa_us": pronunciations[0] if pronunciations else "",
            "core_meaning": next((definition for sense in senses for definition in sense["definitions"]), ""),
            "meaning_zh": next((cached_zh.get(value, "") for sense in senses for value in sense["definitions"] if cached_zh.get(value)), learning["translation_zh"]),
            "headword_translation_zh": cached_zh.get(headword, ""),
            "level": "",
            "register_label": "开放词典",
            "origin": "",
            "breakdown": "",
            "forms": [],
            "aliases": [],
            "family": [{"term": value, "meaning_zh": cached_zh.get(value, "")} for value in family[:24]],
            "collocations": [{**item, "meaning_zh": cached_zh.get(item["phrase"], "")} for item in collocations],
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
            "source_name": source["source_name"],
            "source_version": source["source_version"],
            "license": source["license"],
            "attribution": source["attribution"],
            "source_url": source["source_url"],
        })
    return results


def lexical_search(query: str, limit: int = 30) -> dict:
    raw = (query or "").strip()
    needle = raw.lower()
    compact = needle.strip("-")
    with db() as conn:
        entries = [lexical_entry(row) for row in conn.execute("SELECT * FROM dictionary_entries ORDER BY headword")]
        morphemes = [morpheme_entry(row) for row in conn.execute("SELECT * FROM morphemes ORDER BY kind, form")]

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
    if wordnet_results:
        exact_lexical_match = True
        results.extend(wordnet_results)

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

    results.sort(key=lambda item: (-item["score"], item.get("headword", item.get("form", ""))))
    return {"query": raw, "count": len(results), "results": results[:limit]}


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
) -> dict:
    quiz_data = dict(quiz)
    selected = str(answer or "").strip()
    confidence_score = normalize_confidence(confidence)
    correct = selected.casefold() == str(quiz_data.get("answer") or "").strip().casefold()
    error_type = "" if correct else classify_answer_error(quiz_data, selected)
    explanation = explain_mistake(quiz_data, selected)
    first_attempt = conn.execute(
        "SELECT COUNT(*) FROM attempts WHERE quiz_id = ?", (quiz_data["id"],)
    ).fetchone()[0] == 0
    now = utc_now()
    cursor = conn.execute(
        """INSERT INTO attempts (quiz_id, session_id, user_answer, confidence, correct, error_type, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (quiz_data["id"], session_id, selected, confidence_score, 1 if correct else 0, error_type, now),
    )
    if not correct:
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
    points = (10 if correct else 2) if first_attempt else 0
    progress = award_progress(conn, points, correct=correct) if first_attempt else progress_payload(conn)
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
        SELECT at.id AS attempt_id, at.user_answer, at.confidence, at.correct, at.error_type, at.created_at,
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
        except Exception as error:
            errors.append(type(error).__name__)
    message = "DeepL 拒绝了当前 API Key（403），请使用 DeepL API 账户生成的有效密钥。" if 403 in errors else "无法连接 DeepL 验证接口。"
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
    body = normalize_article_text(title, encoded_text if use_full else summary_text)
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
    }


def upsert_feed_article(conn: sqlite3.Connection, feed: dict, item: dict, now: str) -> str:
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
                body, published_at, source_guid, content_hash, created_at, updated_at)
               VALUES (?, ?, ?, 'feed', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (item["title"], feed["language"], feed["level_hint"], feed["name"], item["link"],
             item["content_status"], item["content_type"], item["body"], item["published_at"],
             item["guid"], item["content_hash"], now, now),
        )
        return "imported"
    body = item["body"] if len(item["body"]) > len(existing["body"]) else existing["body"]
    status = "full" if item["content_status"] == "full" or existing["content_status"] == "full" else "summary"
    changed = any([
        item["title"] != existing["title"], body != existing["body"], status != existing["content_status"],
        item["content_type"] != existing["content_type"],
        bool(item["published_at"] and item["published_at"] != existing["published_at"]),
    ])
    if not changed:
        return "unchanged"
    conn.execute(
        """UPDATE articles SET title = ?, source_url = CASE WHEN source_url = '' THEN ? ELSE source_url END,
           content_status = ?, content_type = ?, body = ?,
           published_at = CASE WHEN ? != '' THEN ? ELSE published_at END,
           source_guid = CASE WHEN source_guid = '' THEN ? ELSE source_guid END,
           content_hash = ?, updated_at = ? WHERE id = ?""",
        (item["title"], item["link"], status, item["content_type"], body,
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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Language-Coach-Token")
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
                return json_response(self, {"ok": True, "database": str(DB_PATH), "time": utc_now()})
            if path == "/api/progress":
                with db() as conn:
                    return json_response(self, {"progress": progress_payload(conn)})
            if path == "/api/learner-settings":
                return json_response(self, {"settings": learner_settings()})
            if path == "/api/feeds/status":
                return json_response(self, feed_refresh_status())
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
                return json_response(self, {"articles": list_articles(query)})
            if path == "/api/article-topics":
                topics = [*ARTICLE_THEMES.keys(), "综合阅读"]
                return json_response(self, {"topics": topics})
            if path == "/api/article-content-types":
                return json_response(
                    self,
                    {"types": [{"id": key, "label": label} for key, label in CONTENT_TYPE_LABELS.items()]},
                )
            if path == "/api/source-catalog":
                return json_response(self, {"sources": source_catalog_payload()})
            if path == "/api/subscriptions":
                return json_response(self, {"subscriptions": subscription_payload()})
            if path == "/api/today":
                return json_response(self, today_content(query.get("exam", [""])[0], query.get("mode", ["exam"])[0]))
            if path == "/api/lexicon/search":
                return json_response(self, lexical_search(query.get("q", [""])[0]))
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
                if not article:
                    return json_response(self, {"error": "Article not found"}, 404)
                item = enrich_article(dict(article), query.get("exam", [""])[0])
                return json_response(self, {"article": item, "analysis": analyze_payload(item)})
            if path == "/api/cards":
                with db() as conn:
                    cards = unique_cards_payload(conn)
                return json_response(self, {"cards": cards})
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
                        SELECT m.*, q.style, q.type AS quiz_type, q.question_type,
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
                        try:
                            item["explanation"] = json.loads(item.get("explanation_json") or "{}") or explain_mistake(item, item["user_answer"])
                        except json.JSONDecodeError:
                            item["explanation"] = explain_mistake(item, item["user_answer"])
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

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            payload = read_json(self)
            if path == "/api/learner-settings":
                try:
                    settings = update_learner_settings(payload)
                except (TypeError, ValueError) as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, {"settings": settings})
            if path == "/api/import/epub":
                try:
                    book, created = import_epub(str(payload.get("path") or ""))
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                return json_response(self, {"book": book, "created": created}, 201 if created else 200)
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
                                   content_type = ?, source = 'browser', updated_at = ? WHERE id = ?""",
                                (title, body, translated, content_type, now, article_id),
                            )
                        else:
                            content_type = infer_content_type({"source": "browser", "title": title, "body": body})
                            cursor = conn.execute(
                                """INSERT INTO articles
                                   (title, language, level, topic, source, source_url, content_status, content_type, body, translation_zh, created_at, updated_at)
                                   VALUES (?, 'en', ?, 'browser', 'browser', ?, 'full', ?, ?, ?, ?, ?)""",
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
                        INSERT INTO articles (title, language, level, topic, source, source_url, content_type, body, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                if not article:
                    return json_response(self, {"error": "Article not found"}, 404)
                return json_response(self, {"article": enrich_article(dict(article), payload.get("exam") or "")})
            match = re.fullmatch(r"/api/articles/(\d+)/translate", path)
            if match:
                with db() as conn:
                    article = conn.execute("SELECT * FROM articles WHERE id = ?", (match.group(1),)).fetchone()
                if not article:
                    return json_response(self, {"error": "Article not found"}, 404)
                paragraphs = [value.strip() for value in re.split(r"\n\s*\n", article["body"]) if value.strip()]
                existing_translation = [
                    value.strip() for value in re.split(r"\n\s*\n", article["translation_zh"] or "") if value.strip()
                ]
                if len(existing_translation) == len(paragraphs) and not payload.get("force"):
                    return json_response(
                        self,
                        {
                            "article": enrich_article(dict(article), payload.get("exam") or ""),
                            "translated_segments": existing_translation,
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
                return json_response(
                    self,
                    {
                        "article": enrich_article(dict(updated), payload.get("exam") or ""),
                        "translated_segments": result["translated_segments"],
                        "provider": result["provider"],
                        "cached": result["cached"],
                    },
                )
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
                item = enrich_article(dict(article), payload.get("exam") or "")
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
                    items = generate_quiz_items(article["body"], mode, style, question_type)
                    now = utc_now()
                    saved = []
                    for item in items:
                        saved.append(save_quiz_item(conn, article_id, style, mode, item, now))
                return json_response(self, {"quizzes": saved}, 201)
            if path == "/api/cards":
                term = (payload.get("term") or "").strip()
                if not term:
                    return json_response(self, {"error": "Term is required"}, 400)
                now = utc_now()
                with db() as conn:
                    existing = conn.execute(
                        "SELECT * FROM cards WHERE lower(trim(term)) = lower(?) ORDER BY updated_at DESC, id DESC LIMIT 1",
                        (term,),
                    ).fetchone()
                    if existing:
                        context = (payload.get("context") or "").strip() or existing["context"]
                        source_article_id = payload.get("source_article_id") or existing["source_article_id"]
                        note = (payload.get("note") or "").strip() or existing["note"]
                        conn.execute(
                            """UPDATE cards SET term = ?, kind = ?, context = ?, source_article_id = ?, note = ?, updated_at = ?
                               WHERE id = ?""",
                            (
                                term,
                                payload.get("kind") or ("phrase" if " " in term else "word"),
                                context,
                                source_article_id,
                                note,
                                now,
                                existing["id"],
                            ),
                        )
                        card_id = existing["id"]
                        created = False
                    else:
                        cursor = conn.execute(
                            """
                            INSERT INTO cards (term, kind, context, source_article_id, status, note, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                term,
                                payload.get("kind") or ("phrase" if " " in term else "word"),
                                payload.get("context") or "",
                                payload.get("source_article_id"),
                                payload.get("status") or "new",
                                payload.get("note") or "",
                                now,
                                now,
                            ),
                        )
                        card_id = cursor.lastrowid
                        created = True
                        increment_daily_progress(conn, "vocabulary", 1)
                    card = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
                return json_response(self, {"card": dict(card), "created": created}, 201 if created else 200)
            if path == "/api/attempts":
                quiz_id = int(payload.get("quiz_id"))
                answer = str(payload.get("answer") or "").strip()
                with db() as conn:
                    quiz = conn.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
                    if not quiz:
                        return json_response(self, {"error": "Quiz not found"}, 404)
                    result = record_quiz_attempt(conn, quiz, answer, confidence=payload.get("confidence"))
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
                return json_response(self, detail, 201)
            if path == "/api/practice-sessions":
                raw_answers = payload.get("answers") or []
                if not isinstance(raw_answers, list) or not raw_answers:
                    return json_response(self, {"error": "At least one quiz answer is required"}, 400)
                if len(raw_answers) > 50:
                    return json_response(self, {"error": "A practice session supports at most 50 questions"}, 400)
                normalized: list[tuple[int, str, int | None]] = []
                seen: set[int] = set()
                for item in raw_answers:
                    quiz_id = int(item.get("quiz_id") or 0)
                    if not quiz_id or quiz_id in seen:
                        return json_response(self, {"error": "Quiz answers must use unique valid ids"}, 400)
                    seen.add(quiz_id)
                    normalized.append((quiz_id, str(item.get("answer") or "").strip(), normalize_confidence(item.get("confidence"))))
                placeholders = ",".join("?" for _ in normalized)
                with db() as conn:
                    rows = conn.execute(
                        f"SELECT * FROM quizzes WHERE id IN ({placeholders})", [item[0] for item in normalized]
                    ).fetchall()
                    by_id = {row["id"]: row for row in rows}
                    if len(by_id) != len(normalized):
                        return json_response(self, {"error": "One or more quizzes were not found"}, 404)
                    quizzes = [by_id[quiz_id] for quiz_id, _, _ in normalized]
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
                        record_quiz_attempt(conn, by_id[quiz_id], answer, session_id, confidence)
                        for quiz_id, answer, confidence in normalized
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
                    answered_count = sum(1 for _, answer, _ in normalized if answer)
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
                return json_response(
                    self,
                    {"session": practice_session_payload(session), "results": results, "progress": results[-1]["progress"]},
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
                        SELECT m.id AS mistake_id, m.user_answer, q.id AS quiz_id,
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
                    conn.execute("UPDATE mistakes SET solved = 1 - solved WHERE id = ?", (match.group(1),))
                    earns_reward = becoming_solved and not bool(current["reward_claimed"])
                    if earns_reward:
                        conn.execute("UPDATE mistakes SET reward_claimed = 1 WHERE id = ?", (match.group(1),))
                        increment_daily_progress(conn, "review", 1)
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
