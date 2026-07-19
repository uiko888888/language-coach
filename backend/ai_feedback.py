from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Callable


PROMPT_VERSION = "output-feedback-v1"
DIMENSIONS = ("information", "collocation", "register", "coherence", "naturalness")
DIMENSION_LABELS = {
    "information": "信息准确",
    "collocation": "搭配",
    "register": "语域",
    "coherence": "衔接",
    "naturalness": "自然度",
}


def _api_url() -> str:
    explicit = os.environ.get("OUTPUT_AI_API_URL", "").strip()
    if explicit:
        return explicit
    base = os.environ.get("OPENAI_BASE_URL", "").strip().rstrip("/")
    return f"{base}/chat/completions" if base else "https://api.openai.com/v1/chat/completions"


def feedback_provider_status() -> dict:
    provider = os.environ.get("OUTPUT_AI_PROVIDER", "openai-compatible").strip().lower() or "openai-compatible"
    api_key = (os.environ.get("OUTPUT_AI_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
    api_url = _api_url()
    model = (os.environ.get("OUTPUT_AI_MODEL") or os.environ.get("OPENAI_MODEL") or "").strip()
    configured = provider == "openai-compatible" and bool(api_key and api_url and model)
    return {
        "provider": provider,
        "configured": configured,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "message": "AI 五维反馈已配置" if configured else "未配置 AI；规则检查、自评和复习仍可使用",
    }


def _strip_json_fence(value: str) -> str:
    clean = str(value or "").strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", clean, re.S | re.I)
    return match.group(1).strip() if match else clean


def _validate_feedback(payload: dict, evidence_text: str, response_text: str) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("dimensions"), dict):
        raise ValueError("AI feedback did not contain a dimensions object")
    evidence_casefold = re.sub(r"\s+", " ", evidence_text).strip().casefold()
    response_casefold = re.sub(r"\s+", " ", response_text).strip().casefold()
    dimensions = []
    for key in DIMENSIONS:
        item = payload["dimensions"].get(key)
        if not isinstance(item, dict):
            raise ValueError(f"AI feedback is missing dimension: {key}")
        score = int(item.get("score") or 0)
        if score not in {1, 2, 3, 4, 5}:
            raise ValueError(f"AI feedback has an invalid score for {key}")
        quote = re.sub(r"\s+", " ", str(item.get("evidence_quote") or "")).strip()[:400]
        quote_casefold = quote.casefold()
        if quote and quote_casefold not in evidence_casefold and quote_casefold not in response_casefold:
            raise ValueError(f"AI feedback cited untraceable evidence for {key}")
        origin = "response" if quote and quote_casefold in response_casefold else "source" if quote else "none"
        dimensions.append({
            "id": key,
            "label": DIMENSION_LABELS[key],
            "score": score,
            "finding": str(item.get("finding") or "").strip()[:600],
            "suggestion": str(item.get("suggestion") or "").strip()[:600],
            "evidence_quote": quote,
            "evidence_origin": origin,
        })
    revised = str(payload.get("revised_response") or "").strip()[:5000]
    return {
        "summary": str(payload.get("summary") or "").strip()[:800],
        "dimensions": dimensions,
        "revised_response": revised,
        "boundary": "AI 建议是可拒绝的反馈，不是唯一答案，也不会直接改变能力等级。",
    }


def request_semantic_feedback(
    attempt: dict,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> dict:
    status = feedback_provider_status()
    if not status["configured"]:
        raise RuntimeError(status["message"])
    source = str(attempt.get("source_text") or "")
    reference = str(attempt.get("reference_text") or "")
    response = str(attempt.get("response_text") or "")
    evidence_text = f"{source}\n{reference}"
    system = (
        "You are an evidence-bound English writing coach. Return JSON only. Evaluate the learner's response "
        "without treating the reference as the only correct answer. For each of information, collocation, "
        "register, coherence, and naturalness return score 1-5, a concise finding, a concrete suggestion, "
        "and an exact evidence_quote copied from SOURCE, REFERENCE, or LEARNER RESPONSE. Use an empty quote "
        "when no exact quote is needed. Also return summary and revised_response. Do not invent facts."
    )
    user = json.dumps({
        "task_type": attempt.get("task_type"),
        "prompt": attempt.get("prompt_text"),
        "source": source,
        "reference_non_unique": reference,
        "learner_response": response,
        "target_chunks": attempt.get("target_chunks") or [],
        "required_json_shape": {
            "summary": "string",
            "dimensions": {key: {"score": 1, "finding": "", "suggestion": "", "evidence_quote": ""} for key in DIMENSIONS},
            "revised_response": "string",
        },
    }, ensure_ascii=False)
    api_url = _api_url()
    api_key = (os.environ.get("OUTPUT_AI_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
    body = {
        "model": status["model"],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    request = urllib.request.Request(
        api_url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener(request, timeout=60) as response_handle:
            raw_payload = response_handle.read(1_000_001)
            if len(raw_payload) > 1_000_000:
                raise ValueError("AI feedback response exceeded the 1 MB limit")
            provider_payload = json.loads(raw_payload.decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"AI feedback request failed with HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError("AI feedback provider is unavailable") from error
    try:
        content = provider_payload["choices"][0]["message"]["content"]
        parsed = json.loads(_strip_json_fence(content))
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("AI feedback response was not valid JSON") from error
    return {
        "provider": status["provider"],
        "model": status["model"],
        "prompt_version": PROMPT_VERSION,
        "feedback": _validate_feedback(parsed, evidence_text, response),
    }
