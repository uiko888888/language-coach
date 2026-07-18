from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass


PHOTO_CREDIT_BLOCK_PATTERN = re.compile(
    r"(?is)^\s*(.{20,1600}?(?:AP\s+Photo|Getty\s+Images?|Reuters|AFP|via\s+Wikimedia\s+Commons))(?:\s+(.+))?$"
)
DISCLOSURE_PATTERN = re.compile(
    r"(?is)\n\s*\n([A-Z][A-Za-zÀ-ÖØ-öø-ÿ'’ .-]{2,100})\s+does not work for, consult, own shares in or receive funding from\b.*$"
)
GUARDIAN_CONTINUE_PATTERN = re.compile(
    r"(?is)\s*(?:Support the Guardian\s+)?Continue reading(?:\.{3}|…)?\s*$"
)
GUARDIAN_NEWSLETTER_PATTERN = re.compile(
    r"(?is)(?:•\s*)?(?:Don['’]t get .{1,100}? delivered to your inbox\?\s*Sign up here|"
    r"Sign up for the .{1,100}? newsletter email)\s*"
)
JSTOR_NEWSLETTER_PATTERN = re.compile(r"(?is)\s*Weekly Newsletter\b.*$")
JSTOR_SCRIPT_PATTERN = re.compile(
    r"(?is)(?:\bgform\s*\.\s*(?:initializeOnLoaded|scriptsLoaded|domLoaded)|"
    r"\bGF_AJAX_POSTBACK\b|\bvar\s+form_content\b|\bis_postback\b|"
    r"\bStudent\s+Undergraduate\s+Student\s+Graduate\s+Student\s+Instructor/Faculty\s+Librarian\s+Researcher\b)"
)
BLOCK_LABELS = ("body", "author", "image_caption", "disclosure", "boilerplate", "unsure")


@dataclass(frozen=True)
class SourceAdapter:
    key: str
    version: str
    confidence: float
    sources: tuple[str, ...]
    apply: Callable[[str, str], tuple[str, str, str, str, list[str]]]


def _normalize_abbreviations(text: str) -> str:
    return re.sub(r"\bU\.\s+S\.(?=\s|$)", "U.S.", text)


def _generic(text: str, author: str) -> tuple[str, str, str, str, list[str]]:
    return text.strip(), author, "", "", []


def _conversation(text: str, author: str) -> tuple[str, str, str, str, list[str]]:
    kept = []
    captions = []
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        match = PHOTO_CREDIT_BLOCK_PATTERN.match(paragraph.strip())
        if not match:
            kept.append(paragraph.strip())
            continue
        captions.append(_normalize_abbreviations(re.sub(r"\s+", " ", match.group(1))).strip())
        if match.group(2):
            kept.append(match.group(2).strip())
    body = "\n\n".join(value for value in kept if value).strip()
    removed = ["image_caption"] if captions else []
    disclosure = ""
    match = DISCLOSURE_PATTERN.search(body)
    if match:
        author = author or re.sub(r"\s+", " ", match.group(1)).strip()
        disclosure = re.sub(r"\s+", " ", match.group(0)).strip()
        body = body[:match.start()].rstrip()
        removed.append("disclosure")
    metadata = "\n\n".join(dict.fromkeys(captions))
    return body, author, metadata, disclosure, removed


def _bbc(text: str, author: str) -> tuple[str, str, str, str, list[str]]:
    return text.strip(), author, "", "", []


def _guardian(text: str, author: str) -> tuple[str, str, str, str, list[str]]:
    body = text.strip()
    removed = []
    cleaned = GUARDIAN_NEWSLETTER_PATTERN.sub("", body)
    if cleaned != body:
        body = re.sub(r"\s+", " ", cleaned).strip()
        removed.append("newsletter_prompt")
    cleaned = GUARDIAN_CONTINUE_PATTERN.sub("", body).rstrip()
    if cleaned != body:
        body = cleaned
        removed.append("continue_reading")
    return body, author, "", "", removed


def _jstor(text: str, author: str) -> tuple[str, str, str, str, list[str]]:
    body = text.strip()
    removed = []
    marker = JSTOR_NEWSLETTER_PATTERN.search(body)
    if not marker:
        marker = JSTOR_SCRIPT_PATTERN.search(body)
    if marker:
        body = body[:marker.start()].rstrip(" \t\r\n,;:{[(")
        removed.append("newsletter_or_form")
    return body, author, "", "", removed


ADAPTERS = (
    SourceAdapter("conversation", "conversation-rules-v2", 0.98, ("The Conversation", "The Conversation Politics"), _conversation),
    SourceAdapter("bbc", "bbc-rss-v1", 0.96, ("BBC World", "BBC Business"), _bbc),
    SourceAdapter(
        "guardian", "guardian-rss-v1", 0.94,
        ("Guardian World", "Guardian Opinion", "Guardian Science", "Guardian Environment"), _guardian,
    ),
    SourceAdapter("jstor", "jstor-rss-v1", 0.96, ("JSTOR Daily",), _jstor),
)
GENERIC_ADAPTER = SourceAdapter("generic", "generic-blocks-v1", 0.75, (), _generic)


def adapter_for_source(source: str) -> SourceAdapter:
    return next((adapter for adapter in ADAPTERS if source in adapter.sources), GENERIC_ADAPTER)


def extract_source_content(text: str, source: str, author: str = "") -> dict:
    adapter = adapter_for_source(source)
    body, extracted_author, image_caption, disclosure, removed = adapter.apply(text or "", author or "")
    return {
        "body": body,
        "author": extracted_author,
        "image_caption": image_caption,
        "disclosure": disclosure,
        "extraction_version": adapter.version,
        "extraction_confidence": adapter.confidence,
        "removed_blocks": removed,
        "adapter": adapter.key,
    }


def adapter_catalog() -> list[dict]:
    return [
        {
            "key": adapter.key,
            "version": adapter.version,
            "confidence": adapter.confidence,
            "sources": list(adapter.sources),
        }
        for adapter in ADAPTERS
    ]


def _block_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _body_chunks(text: str, limit: int = 1200) -> list[str]:
    chunks = []
    for paragraph in re.split(r"\n\s*\n", text or ""):
        paragraph = re.sub(r"[ \t\r\f\v]+", " ", paragraph).strip()
        if not paragraph:
            continue
        if len(paragraph) <= limit:
            chunks.append(paragraph)
            continue
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", paragraph)
        current = ""
        for sentence in sentences:
            if len(sentence) > limit:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.extend(sentence[index:index + limit].strip() for index in range(0, len(sentence), limit))
                continue
            candidate = f"{current} {sentence}".strip()
            if current and len(candidate) > limit:
                chunks.append(current)
                current = sentence
            else:
                current = candidate
        if current:
            chunks.append(current)
    return chunks


def suggest_annotation_blocks(
    text: str,
    source: str,
    author: str = "",
    image_caption: str = "",
    disclosure: str = "",
) -> list[dict]:
    result = extract_source_content(text, source, author)
    candidates: list[tuple[str, str, float]] = []

    resolved_author = author or result["author"]
    resolved_caption = image_caption or result["image_caption"]
    resolved_disclosure = disclosure or result["disclosure"]
    if resolved_author:
        candidates.append((resolved_author, "author", 0.98))
    for caption in re.split(r"\n\s*\n", resolved_caption):
        if caption.strip():
            candidates.append((caption.strip(), "image_caption", 0.96))
    candidates.extend((chunk, "body", result["extraction_confidence"]) for chunk in _body_chunks(result["body"]))
    if resolved_disclosure:
        candidates.append((resolved_disclosure, "disclosure", 0.98))

    if source.startswith("Guardian "):
        candidates.extend((match.group(0).strip(), "boilerplate", 0.98) for match in GUARDIAN_NEWSLETTER_PATTERN.finditer(text))
        match = GUARDIAN_CONTINUE_PATTERN.search(text)
        if match:
            candidates.append((match.group(0).strip(), "boilerplate", 0.99))
    if source == "JSTOR Daily":
        match = JSTOR_NEWSLETTER_PATTERN.search(text) or JSTOR_SCRIPT_PATTERN.search(text)
        if match:
            candidates.extend((chunk, "boilerplate", 0.99) for chunk in _body_chunks(text[match.start():]))

    blocks = []
    seen = set()
    for text_value, suggested_label, confidence in candidates:
        text_value = text_value.strip()
        digest = _block_hash(text_value)
        if not text_value or digest in seen:
            continue
        seen.add(digest)
        blocks.append({
            "block_index": len(blocks),
            "block_hash": digest,
            "text": text_value,
            "suggested_label": suggested_label,
            "suggestion_confidence": confidence,
        })
    return blocks
