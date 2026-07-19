import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.speech_transcription import transcribe_audio, transcription_status


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit=-1):
        return json.dumps({"text": "The article explains why local spaces matter."}).encode()


class SpeechTranscriptionTests(unittest.TestCase):
    @patch.dict("os.environ", {
        "SPEECH_TRANSCRIPTION_PROVIDER": "openai-compatible",
        "SPEECH_TRANSCRIPTION_API_URL": "http://provider.test/v1/audio/transcriptions",
        "SPEECH_TRANSCRIPTION_API_KEY": "test-key",
        "SPEECH_TRANSCRIPTION_MODEL": "test-transcriber",
    }, clear=False)
    def test_configured_transcription_sends_audio_and_returns_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.webm"
            path.write_bytes(b"fake-webm-audio")
            captured = {}

            def opener(request, timeout):
                captured["body"] = request.data
                captured["authorization"] = request.headers["Authorization"]
                captured["timeout"] = timeout
                return FakeResponse()

            result = transcribe_audio(path, "audio/webm", opener=opener)
        self.assertEqual(result["model"], "test-transcriber")
        self.assertIn(b"fake-webm-audio", captured["body"])
        self.assertEqual(captured["authorization"], "Bearer test-key")
        self.assertEqual(result["text"], "The article explains why local spaces matter.")

    @patch.dict("os.environ", {
        "SPEECH_TRANSCRIPTION_API_KEY": "",
        "OPENAI_API_KEY": "",
        "SPEECH_TRANSCRIPTION_MODEL": "",
    }, clear=False)
    def test_unconfigured_transcription_preserves_manual_fallback(self):
        status = transcription_status()
        self.assertFalse(status["configured"])
        self.assertIn("手动文本", status["message"])
