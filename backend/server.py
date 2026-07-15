from __future__ import annotations

import html
import json
import mimetypes
import random
import re
import sqlite3
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DATA = ROOT / "data"
DB_PATH = DATA / "language_coach.sqlite"


SAMPLE_ARTICLE = """Smart devices promise convenience, but they also create a quiet record of daily life. A speaker can learn when a family is at home, a watch can reveal health patterns, and a doorbell camera can capture people who never agreed to be recorded. Supporters argue that these tools save time and improve safety. However, critics point out that privacy policies are often difficult to read, and users may not understand how much information is stored or shared.

The central challenge is not whether technology should be rejected. It is whether companies can design useful products while giving people meaningful control over their own data. Clearer consent, shorter privacy notices, and stronger limits on data sharing would make smart devices easier to trust. Without those safeguards, convenience may gradually become a form of surveillance."""

SAMPLE_TRANSLATION = """智能设备承诺带来便利，但它们也会悄然记录日常生活。智能音箱可以了解一家人何时在家，手表可以揭示健康规律，门铃摄像头则可能拍到从未同意被记录的人。支持者认为这些工具节省时间并提高安全性。然而，批评者指出，隐私政策往往难以阅读，用户可能并不清楚有多少信息被储存或共享。

核心问题并不是是否应该拒绝技术，而是企业能否在提供实用产品的同时，让人们真正掌控自己的数据。更清晰的同意机制、更简短的隐私声明以及更严格的数据共享限制，会让智能设备更值得信任。缺少这些保障时，便利可能逐渐演变为一种监控。"""

EXAM_QUESTION_TYPES = {
    "IELTS": [("evidence", "判断与证据定位", "reading"), ("heading", "段落标题匹配", "main-idea"), ("paraphrase", "同义替换", "paraphrase"), ("gap-fill", "选词填空", "cloze")],
    "TOEFL": [("factual", "事实信息题", "reading"), ("main-idea", "主旨题", "main-idea"), ("simplification", "句子简化", "paraphrase"), ("vocabulary", "语境词义", "cloze")],
    "TEM4": [("detail", "细节理解", "reading"), ("main-idea", "主旨概括", "main-idea"), ("meaning", "近义改写", "paraphrase"), ("lexico-grammar", "词汇语法", "cloze")],
    "TEM8": [("inference", "推断与态度", "reading"), ("title", "标题概括", "main-idea"), ("nuance", "长难句释义", "paraphrase"), ("semantic", "语义辨析", "cloze")],
    "GRE": [("implication", "推断题", "reading"), ("central-concern", "中心论点", "main-idea"), ("function", "句间逻辑", "paraphrase"), ("precision", "精确词义", "cloze")],
    "GMAT": [("support", "论证支持", "reading"), ("argument-role", "论证功能", "main-idea"), ("reasoning", "推理保真", "paraphrase"), ("business-context", "商科语境搭配", "cloze")],
    "general": [("evidence", "证据定位", "reading"), ("main-idea", "主旨题", "main-idea"), ("paraphrase", "同义改写", "paraphrase"), ("cloze", "选词填空", "cloze"), ("initial", "首字母填空", "initial")],
}

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
]


SOURCE_PROFILES = {
    "The Conversation": {"tier": "核心", "topics": ["科学", "社会", "教育"], "exams": ["IELTS", "TOEFL", "TEM8", "GRE"]},
    "JSTOR Daily": {"tier": "核心", "topics": ["历史", "人文", "社会科学"], "exams": ["TOEFL", "TEM8", "GRE"]},
    "Guardian Science": {"tier": "核心", "topics": ["科学", "健康"], "exams": ["IELTS", "TOEFL", "TEM4", "TEM8"]},
    "Guardian Environment": {"tier": "核心", "topics": ["环境", "社会"], "exams": ["IELTS", "TOEFL", "TEM4", "TEM8"]},
    "MIT Technology Review": {"tier": "核心", "topics": ["科技", "商业"], "exams": ["TOEFL", "GRE", "GMAT", "TEM8"]},
    "ScienceDaily": {"tier": "核心", "topics": ["自然科学", "健康"], "exams": ["IELTS", "TOEFL", "GRE"]},
    "Aeon": {"tier": "核心", "topics": ["哲学", "心理", "文化"], "exams": ["TEM8", "GRE"]},
    "Knowledge at Wharton": {"tier": "核心", "topics": ["商业", "经济", "管理"], "exams": ["GMAT", "GRE", "TEM8"]},
    "The Economist Business": {"tier": "核心", "topics": ["商业", "经济", "政策"], "exams": ["GMAT", "GRE", "TEM8"]},
    "BBC Learning English": {"tier": "补充", "topics": ["语言", "时事"], "exams": ["IELTS", "TEM4"]},
    "NPR": {"tier": "补充", "topics": ["时事", "社会"], "exams": ["IELTS", "TOEFL", "TEM4", "TEM8"]},
    "manual": {"tier": "个人", "topics": ["自选"], "exams": ["IELTS", "TOEFL", "TEM4", "TEM8", "GRE", "GMAT"]},
    "seed": {"tier": "示例", "topics": ["科技", "社会"], "exams": ["IELTS", "TOEFL", "TEM4", "TEM8", "GRE", "GMAT"]},
}


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
              body TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cards (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              term TEXT NOT NULL,
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
              prompt TEXT NOT NULL,
              answer TEXT NOT NULL,
              options_json TEXT NOT NULL DEFAULT '[]',
              evidence TEXT NOT NULL DEFAULT '',
              note TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              FOREIGN KEY (article_id) REFERENCES articles(id)
            );

            CREATE TABLE IF NOT EXISTS attempts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              quiz_id INTEGER NOT NULL,
              user_answer TEXT NOT NULL,
              correct INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
            );

            CREATE TABLE IF NOT EXISTS mistakes (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              quiz_id INTEGER,
              prompt TEXT NOT NULL,
              answer TEXT NOT NULL,
              user_answer TEXT NOT NULL,
              evidence TEXT NOT NULL DEFAULT '',
              source TEXT NOT NULL DEFAULT 'quiz',
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
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS progress (
              id INTEGER PRIMARY KEY CHECK (id = 1),
              xp INTEGER NOT NULL DEFAULT 0,
              correct_count INTEGER NOT NULL DEFAULT 0,
              reviewed_count INTEGER NOT NULL DEFAULT 0,
              streak INTEGER NOT NULL DEFAULT 0,
              last_study_date TEXT NOT NULL DEFAULT ''
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
        article_columns = {row[1] for row in conn.execute("PRAGMA table_info(articles)")}
        if "translation_zh" not in article_columns:
            conn.execute("ALTER TABLE articles ADD COLUMN translation_zh TEXT NOT NULL DEFAULT ''")
        conn.execute("UPDATE articles SET translation_zh = ? WHERE source = 'seed' AND translation_zh = ''", (SAMPLE_TRANSLATION,))
        for row in conn.execute("SELECT id, title, body FROM articles").fetchall():
            normalized = normalize_article_text(row["title"], row["body"])
            if normalized and normalized != row["body"]:
                conn.execute("UPDATE articles SET body = ? WHERE id = ?", (normalized, row["id"]))
        conn.execute("INSERT OR IGNORE INTO progress (id) VALUES (1)")
        mistake_columns = {row[1] for row in conn.execute("PRAGMA table_info(mistakes)")}
        if "reward_claimed" not in mistake_columns:
            conn.execute("ALTER TABLE mistakes ADD COLUMN reward_claimed INTEGER NOT NULL DEFAULT 0")
        article_count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        if article_count == 0:
            now = utc_now()
            conn.execute(
                """
                INSERT INTO articles (title, language, level, topic, source, source_url, body, created_at, updated_at)
                VALUES (?, 'en', 'B2', 'technology', 'seed', '', ?, ?, ?)
                """,
                ("Privacy concerns in the age of smart devices", SAMPLE_ARTICLE, now, now),
            )
        conn.execute("UPDATE articles SET translation_zh = ? WHERE source = 'seed' AND translation_zh = ''", (SAMPLE_TRANSLATION,))
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


def text_response(handler: BaseHTTPRequestHandler, content: bytes, content_type: str, status: int = 200) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
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


def generate_quiz_items(text: str, mode: str, style: str, question_type: str = "") -> list[dict]:
    profile = style_profile(style)
    configured = next((item for item in EXAM_QUESTION_TYPES.get(style, EXAM_QUESTION_TYPES["general"]) if item[0] == question_type), None)
    if configured:
        engine_type = configured[2]
        mode = engine_type if engine_type in {"cloze", "initial"} else "reading"
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
    if mode in {"mixed", "initial"}:
        for keyword in article_keywords(text)[:8]:
            context = sentence_for(text, keyword)
            clue = keyword[0] + "_" * max(2, len(keyword) - 1)
            prompt = re.sub(rf"\b{re.escape(keyword)}\b", clue, context, flags=re.I)
            if prompt == context:
                continue
            items.append(
                {
                    "type": "initial",
                    "prompt": prompt,
                    "answer": keyword,
                    "options": [],
                    "evidence": context,
                    "note": profile["notes"][4],
                }
            )
    if question_type:
        if configured:
            _, label, engine_type = configured
            items = [item for item in items if item["type"] == engine_type]
            for item in items:
                item["note"] = f"{style} / {label}"
    return items


def explain_mistake(quiz: sqlite3.Row | dict, user_answer: str) -> dict:
    quiz_type = quiz.get("quiz_type") or quiz.get("type") or "reading"
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
        "initial": {
            "point": "语境提取与完整拼写",
            "correct": f"语境指向 {answer}，首字母和词长也与答案一致。这类题同时考词义提取和完整拼写。",
            "method": ["根据句意回忆目标词", "用首字母和词长核对", "检查词形、单复数和时态"],
        },
    }
    guide = type_guides.get(quiz_type, type_guides["reading"])

    lower = selected.lower()
    if not selected:
        trap = "未作答"
        why_wrong = "这次没有形成可比较的答案。先写出一个候选，再用证据排除，训练效果会比直接跳过更好。"
    elif quiz_type in {"cloze", "initial"}:
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
        "question_type": quiz_type,
        "test_point": note or guide["point"],
        "trap": trap,
        "why_wrong": why_wrong,
        "why_correct": guide["correct"],
        "evidence_guide": "先在证据句中确认谁做什么，再核对否定、转折、因果、程度词和范围词。正确答案必须能逐项对应。",
        "steps": guide["method"],
        "retry": f"遮住答案，把“{answer}”换成自己的话复述一次，再重新作答。",
        "evidence": evidence,
    }


def generate_similar_items(text: str, original: dict, count: int = 3) -> list[dict]:
    quiz_type = original.get("type") or original.get("quiz_type") or "reading"
    style = original.get("style") or "IELTS"
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
    else:
        keywords = [word for word in article_keywords(text) if word != original_answer]
        for keyword in keywords[:count]:
            context = sentence_for(text, keyword)
            clue = keyword[0] + "_" * max(2, len(keyword) - 1)
            prompt = re.sub(rf"\b{re.escape(keyword)}\b", clue, context, flags=re.I)
            items.append(
                {
                    "type": "initial",
                    "prompt": prompt,
                    "answer": keyword,
                    "options": [],
                    "evidence": context,
                    "note": f"同类巩固 / {profile['notes'][4]}",
                }
            )
    return items[:count]


def analyze_payload(article: sqlite3.Row | dict) -> dict:
    text = article["body"]
    return {
        "id": article["id"],
        "title": article["title"],
        "level": estimate_level(text),
        "keywords": article_keywords(text),
        "focus_sentences": focus_sentences(text),
        "sentence_count": len(sentences(text)),
        "word_count": len(words(text)),
    }


def source_profile(source: str, exam: str = "") -> dict:
    profile = SOURCE_PROFILES.get(
        source,
        {"tier": "其他", "topics": ["综合"], "exams": ["IELTS", "TOEFL", "TEM4", "TEM8", "GRE", "GMAT"]},
    )
    if source in {"manual", "seed"}:
        fit = 95
    elif not exam or exam == "general":
        fit = 80 if profile["tier"] == "核心" else 60
    elif exam in profile["exams"]:
        fit = 100 if profile["tier"] == "核心" else 75
    else:
        fit = 35
    return {
        "source_tier": profile["tier"],
        "source_topics": profile["topics"],
        "source_exams": profile["exams"],
        "exam_fit": fit,
    }


def recommendation_profile(article: dict) -> dict:
    try:
        created = datetime.fromisoformat(article["created_at"].replace("Z", "+00:00"))
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


def enrich_article(article: dict, exam: str = "") -> dict:
    item = dict(article)
    item.update(source_profile(item["source"], exam))
    item.update(article_theme_profile(item))
    item.update(recommendation_profile(item))
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
    return ranked


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


def lexical_search(query: str, limit: int = 30) -> dict:
    raw = (query or "").strip()
    needle = raw.lower()
    compact = needle.strip("-")
    with db() as conn:
        entries = [lexical_entry(row) for row in conn.execute("SELECT * FROM dictionary_entries ORDER BY headword")]
        morphemes = [morpheme_entry(row) for row in conn.execute("SELECT * FROM morphemes ORDER BY kind, form")]

    results: list[dict] = []
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
        elif needle in roots or compact in [root.strip("-") for root in roots]:
            score, matched_by = 92, "构词成分匹配"
        elif needle in forms:
            score, matched_by = 86, "词形匹配"
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


def fetch_feed_items(limit_per_feed: int = 4) -> dict:
    imported = 0
    errors: list[str] = []
    with db() as conn:
        feeds = conn.execute("SELECT * FROM feeds WHERE active = 1").fetchall()
        for feed in feeds:
            try:
                req = urllib.request.Request(feed["url"], headers={"User-Agent": "LanguageCoachV2/0.1"})
                with urllib.request.urlopen(req, timeout=10) as response:
                    raw = response.read()
                root = ET.fromstring(raw)
                entries = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
                for entry in entries[:limit_per_feed]:
                    title = entry.findtext("title") or entry.findtext("{http://www.w3.org/2005/Atom}title") or "Untitled"
                    link = entry.findtext("link") or ""
                    atom_link = entry.find("{http://www.w3.org/2005/Atom}link")
                    if not link and atom_link is not None:
                        link = atom_link.attrib.get("href", "")
                    summary = (
                        entry.findtext("description")
                        or entry.findtext("summary")
                        or entry.findtext("{http://www.w3.org/2005/Atom}summary")
                        or title
                    )
                    body = normalize_article_text(clean_html(title), clean_html(summary))
                    now = utc_now()
                    before = conn.total_changes
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO articles
                        (title, language, level, topic, source, source_url, body, created_at, updated_at)
                        VALUES (?, ?, ?, 'feed', ?, ?, ?, ?, ?)
                        """,
                        (clean_html(title), feed["language"], feed["level_hint"], feed["name"], link, body, now, now),
                    )
                    if conn.total_changes > before:
                        imported += 1
            except Exception as exc:  # Feed failures should not break the app.
                errors.append(f"{feed['name']}: {exc}")
    return {"imported": imported, "errors": errors}


class App(BaseHTTPRequestHandler):
    server_version = "LanguageCoachV2/0.1"

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
            if path == "/api/exam-types":
                style = query.get("style", ["general"])[0]
                types = [{"id": key, "label": label, "engine_type": engine} for key, label, engine in EXAM_QUESTION_TYPES.get(style, EXAM_QUESTION_TYPES["general"])]
                return json_response(self, {"style": style, "types": types})
            if path == "/api/articles":
                return json_response(self, {"articles": list_articles(query)})
            if path == "/api/article-topics":
                topics = [*ARTICLE_THEMES.keys(), "综合阅读"]
                return json_response(self, {"topics": topics})
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
                    cards = rows_to_dicts(conn.execute("SELECT * FROM cards ORDER BY updated_at DESC, id DESC").fetchall())
                return json_response(self, {"cards": cards})
            if path == "/api/quizzes":
                article_id = query.get("article_id", [""])[0]
                sql = "SELECT * FROM quizzes"
                params: list[str] = []
                if article_id:
                    sql += " WHERE article_id = ?"
                    params.append(article_id)
                sql += " ORDER BY created_at DESC, id DESC"
                with db() as conn:
                    quizzes = [self.quiz_row(row) for row in conn.execute(sql, params).fetchall()]
                return json_response(self, {"quizzes": quizzes})
            if path == "/api/mistakes":
                with db() as conn:
                    rows = conn.execute(
                        """
                        SELECT m.*, q.style, q.type AS quiz_type, q.note AS quiz_note,
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
            if path == "/api/articles":
                now = utc_now()
                body = (payload.get("body") or "").strip()
                if not body:
                    return json_response(self, {"error": "Article body is required"}, 400)
                title = (payload.get("title") or "Untitled").strip()
                level = payload.get("level") or estimate_level(body)
                with db() as conn:
                    cursor = conn.execute(
                        """
                        INSERT INTO articles (title, language, level, topic, source, source_url, body, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            title,
                            payload.get("language") or "en",
                            level,
                            payload.get("topic") or "manual",
                            payload.get("source") or "manual",
                            payload.get("source_url") or "",
                            body,
                            now,
                            now,
                        ),
                    )
                    article = conn.execute("SELECT * FROM articles WHERE id = ?", (cursor.lastrowid,)).fetchone()
                    if payload.get("translation_zh"):
                        conn.execute("UPDATE articles SET translation_zh = ? WHERE id = ?", (payload["translation_zh"], cursor.lastrowid))
                        article = conn.execute("SELECT * FROM articles WHERE id = ?", (cursor.lastrowid,)).fetchone()
                return json_response(self, {"article": dict(article), "analysis": analyze_payload(article)}, 201)
            match = re.fullmatch(r"/api/articles/(\d+)/translation", path)
            if match:
                translation = (payload.get("translation_zh") or "").strip()
                with db() as conn:
                    conn.execute("UPDATE articles SET translation_zh = ?, updated_at = ? WHERE id = ?", (translation, utc_now(), match.group(1)))
                    article = conn.execute("SELECT * FROM articles WHERE id = ?", (match.group(1),)).fetchone()
                if not article:
                    return json_response(self, {"error": "Article not found"}, 404)
                return json_response(self, {"article": dict(article)})
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
                        cursor = conn.execute(
                            """
                            INSERT INTO quizzes
                            (article_id, style, mode, type, prompt, answer, options_json, evidence, note, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                article_id,
                                style,
                                mode,
                                item["type"],
                                item["prompt"],
                                item["answer"],
                                json.dumps(item["options"], ensure_ascii=False),
                                item["evidence"],
                                item["note"],
                                now,
                            ),
                        )
                        saved.append({**item, "id": cursor.lastrowid, "article_id": article_id, "style": style, "mode": mode})
                return json_response(self, {"quizzes": saved}, 201)
            if path == "/api/cards":
                term = (payload.get("term") or "").strip()
                if not term:
                    return json_response(self, {"error": "Term is required"}, 400)
                now = utc_now()
                with db() as conn:
                    cursor = conn.execute(
                        """
                        INSERT INTO cards (term, context, source_article_id, status, note, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            term,
                            payload.get("context") or "",
                            payload.get("source_article_id"),
                            payload.get("status") or "new",
                            payload.get("note") or "",
                            now,
                            now,
                        ),
                    )
                    card = conn.execute("SELECT * FROM cards WHERE id = ?", (cursor.lastrowid,)).fetchone()
                return json_response(self, {"card": dict(card)}, 201)
            if path == "/api/attempts":
                quiz_id = int(payload.get("quiz_id"))
                answer = str(payload.get("answer") or "").strip()
                with db() as conn:
                    quiz = conn.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
                    if not quiz:
                        return json_response(self, {"error": "Quiz not found"}, 404)
                    correct = answer.lower() == quiz["answer"].lower()
                    first_attempt = conn.execute("SELECT COUNT(*) FROM attempts WHERE quiz_id = ?", (quiz_id,)).fetchone()[0] == 0
                    now = utc_now()
                    conn.execute(
                        "INSERT INTO attempts (quiz_id, user_answer, correct, created_at) VALUES (?, ?, ?, ?)",
                        (quiz_id, answer, 1 if correct else 0, now),
                    )
                    if not correct:
                        conn.execute(
                            """
                            INSERT INTO mistakes (quiz_id, prompt, answer, user_answer, evidence, source, solved, created_at)
                            VALUES (?, ?, ?, ?, ?, 'quiz', 0, ?)
                            """,
                            (quiz_id, quiz["prompt"], quiz["answer"], answer, quiz["evidence"], now),
                        )
                    explanation = explain_mistake(dict(quiz), answer)
                    points = (10 if correct else 2) if first_attempt else 0
                    progress = award_progress(conn, points, correct=correct) if first_attempt else progress_payload(conn)
                return json_response(
                    self,
                    {
                        "correct": correct,
                        "answer": quiz["answer"],
                        "evidence": quiz["evidence"],
                        "explanation": explanation,
                        "points": points,
                        "progress": progress,
                    },
                )
            match = re.fullmatch(r"/api/mistakes/(\d+)/similar", path)
            if match:
                count = max(1, min(5, int(payload.get("count") or 3)))
                with db() as conn:
                    original = conn.execute(
                        """
                        SELECT m.id AS mistake_id, m.user_answer, q.id AS quiz_id,
                               q.article_id, q.style, q.type, q.prompt, q.answer,
                               q.evidence, q.note, a.body AS article_body
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
                        cursor = conn.execute(
                            """
                            INSERT INTO quizzes
                            (article_id, style, mode, type, prompt, answer, options_json, evidence, note, created_at)
                            VALUES (?, ?, 'remedial', ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                original_item["article_id"],
                                original_item["style"] or "IELTS",
                                item["type"], item["prompt"], item["answer"],
                                json.dumps(item["options"], ensure_ascii=False),
                                item["evidence"], item["note"], now,
                            ),
                        )
                        saved.append({**item, "id": cursor.lastrowid, "article_id": original_item["article_id"], "style": original_item["style"] or "IELTS", "mode": "remedial"})
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
                return json_response(self, fetch_feed_items())
            return json_response(self, {"error": "Not found"}, 404)
        except json.JSONDecodeError:
            return json_response(self, {"error": "Invalid JSON"}, 400)
        except Exception as exc:
            return json_response(self, {"error": str(exc)}, 500)

    def quiz_row(self, row: sqlite3.Row) -> dict:
        item = dict(row)
        item["options"] = json.loads(item.pop("options_json") or "[]")
        return item

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
        text_response(self, file_path.read_bytes(), content_type)


def main() -> None:
    init_db()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ThreadingHTTPServer(("127.0.0.1", port), App)
    print(f"Language Coach v2 running at http://127.0.0.1:{port}")
    print(f"SQLite database: {DB_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()
