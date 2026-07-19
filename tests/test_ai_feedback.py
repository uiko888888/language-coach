import json
import unittest
from unittest.mock import patch

from backend.ai_feedback import feedback_provider_status, request_semantic_feedback


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit=-1):
        return json.dumps(self.payload).encode("utf-8")


class OversizedResponse(FakeResponse):
    def read(self, _limit=-1):
        return b"x" * 1_000_001


class AiFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.attempt = {
            "task_type": "zh_to_en",
            "prompt_text": "研究显示了明确的变化。",
            "source_text": "The study shows a clear change in behavior.",
            "reference_text": "The study shows a clear change in behavior.",
            "response_text": "The study shows a clear change in behavior.",
            "target_chunks": ["clear change"],
        }

    def provider_payload(self, evidence_quote="clear change"):
        dimensions = {
            key: {
                "score": 4,
                "finding": "The response preserves the intended meaning.",
                "suggestion": "Keep the wording concise.",
                "evidence_quote": evidence_quote,
            }
            for key in ("information", "collocation", "register", "coherence", "naturalness")
        }
        content = json.dumps({
            "summary": "Accurate and concise.",
            "dimensions": dimensions,
            "revised_response": "The study reveals a clear change in behavior.",
        })
        return {"choices": [{"message": {"content": content}}]}

    @patch.dict("os.environ", {
        "OUTPUT_AI_PROVIDER": "openai-compatible",
        "OUTPUT_AI_API_KEY": "test-key",
        "OUTPUT_AI_API_URL": "http://provider.test/v1/chat/completions",
        "OUTPUT_AI_MODEL": "test-model",
    }, clear=False)
    def test_valid_feedback_keeps_five_dimensions_and_traceable_evidence(self):
        result = request_semantic_feedback(
            self.attempt,
            opener=lambda *_args, **_kwargs: FakeResponse(self.provider_payload()),
        )
        self.assertEqual(result["model"], "test-model")
        self.assertEqual(len(result["feedback"]["dimensions"]), 5)
        self.assertTrue(all(item["evidence_origin"] in {"source", "response"} for item in result["feedback"]["dimensions"]))

    @patch.dict("os.environ", {
        "OUTPUT_AI_PROVIDER": "openai-compatible",
        "OUTPUT_AI_API_KEY": "test-key",
        "OUTPUT_AI_API_URL": "http://provider.test/v1/chat/completions",
        "OUTPUT_AI_MODEL": "test-model",
    }, clear=False)
    def test_untraceable_feedback_evidence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "untraceable evidence"):
            request_semantic_feedback(
                self.attempt,
                opener=lambda *_args, **_kwargs: FakeResponse(self.provider_payload("an invented quotation")),
            )

    @patch.dict("os.environ", {
        "OUTPUT_AI_PROVIDER": "openai-compatible",
        "OUTPUT_AI_API_KEY": "test-key",
        "OUTPUT_AI_API_URL": "http://provider.test/v1/chat/completions",
        "OUTPUT_AI_MODEL": "test-model",
    }, clear=False)
    def test_oversized_provider_response_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "1 MB limit"):
            request_semantic_feedback(
                self.attempt,
                opener=lambda *_args, **_kwargs: OversizedResponse({}),
            )

    @patch.dict("os.environ", {
        "OUTPUT_AI_API_KEY": "",
        "OPENAI_API_KEY": "",
        "OUTPUT_AI_MODEL": "",
        "OPENAI_MODEL": "",
    }, clear=False)
    def test_unconfigured_provider_reports_no_ai_fallback(self):
        status = feedback_provider_status()
        self.assertFalse(status["configured"])
        self.assertIn("规则检查", status["message"])
