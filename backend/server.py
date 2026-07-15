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
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DATA = ROOT / "data"
DB_PATH = DATA / "language_coach.sqlite"


SAMPLE_ARTICLE = """Smart devices promise convenience, but they also create a quiet record of daily life. A speaker can learn when a family is at home, a watch can reveal health patterns, and a doorbell camera can capture people who never agreed to be recorded. Supporters argue that these tools save time and improve safety. However, critics point out that privacy policies are often difficult to read, and users may not understand how much information is stored or shared.

The central challenge is not whether technology should be rejected. It is whether companies can design useful products while giving people meaningful control over their own data. Clearer consent, shorter privacy notices, and stronger limits on data sharing would make smart devices easier to trust. Without those safeguards, convenience may gradually become a form of surveillance."""


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


DEFAULT_FEEDS = [
    {
        "name": "BBC Learning English",
        "url": "https://feeds.bbci.co.uk/learningenglish/english/features/rss.xml",
        "language": "en",
        "level_hint": "B1-B2",
    },
    {
        "name": "The Conversation",
        "url": "https://theconversation.com/global/articles.atom",
        "language": "en",
        "level_hint": "B2-C1",
    },
    {
        "name": "NPR",
        "url": "https://feeds.npr.org/1001/rss.xml",
        "language": "en",
        "level_hint": "B2",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db() -> sqlite3.Connection:
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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

            CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_source_url
            ON articles(source_url)
            WHERE source_url != '';
            """
        )
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
        feed_count = conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0]
        if feed_count == 0:
            now = utc_now()
            conn.executemany(
                """
                INSERT OR IGNORE INTO feeds (name, url, language, level_hint, active, created_at)
                VALUES (:name, :url, :language, :level_hint, 1, :created_at)
                """,
                [{**feed, "created_at": now} for feed in DEFAULT_FEEDS],
            )


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


def generate_quiz_items(text: str, mode: str, style: str) -> list[dict]:
    profile = style_profile(style)
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
    return items


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
        return rows_to_dicts(conn.execute(sql, params).fetchall())


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
                    body = clean_html(f"{title}. {summary}")
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
            if path == "/api/articles":
                return json_response(self, {"articles": list_articles(query)})
            match = re.fullmatch(r"/api/articles/(\d+)", path)
            if match:
                with db() as conn:
                    article = conn.execute("SELECT * FROM articles WHERE id = ?", (match.group(1),)).fetchone()
                if not article:
                    return json_response(self, {"error": "Article not found"}, 404)
                return json_response(self, {"article": dict(article), "analysis": analyze_payload(article)})
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
                    mistakes = rows_to_dicts(conn.execute("SELECT * FROM mistakes ORDER BY solved, created_at DESC").fetchall())
                return json_response(self, {"mistakes": mistakes})
            if path == "/api/feeds":
                with db() as conn:
                    feeds = rows_to_dicts(conn.execute("SELECT * FROM feeds ORDER BY id").fetchall())
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
                return json_response(self, {"article": dict(article), "analysis": analyze_payload(article)}, 201)
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
                with db() as conn:
                    article = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
                    if not article:
                        return json_response(self, {"error": "Article not found"}, 404)
                    items = generate_quiz_items(article["body"], mode, style)
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
                return json_response(self, {"correct": correct, "answer": quiz["answer"], "evidence": quiz["evidence"]})
            match = re.fullmatch(r"/api/mistakes/(\d+)/solve", path)
            if match:
                with db() as conn:
                    conn.execute("UPDATE mistakes SET solved = 1 - solved WHERE id = ?", (match.group(1),))
                return json_response(self, {"ok": True})
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
