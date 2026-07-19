from __future__ import annotations

import json
import os
import secrets
import urllib.error
import urllib.request
from pathlib import Path


def transcription_status() -> dict:
    provider = os.environ.get("SPEECH_TRANSCRIPTION_PROVIDER", "openai-compatible").strip().lower() or "openai-compatible"
    api_key = (os.environ.get("SPEECH_TRANSCRIPTION_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
    api_url = os.environ.get("SPEECH_TRANSCRIPTION_API_URL", "https://api.openai.com/v1/audio/transcriptions").strip()
    model = os.environ.get("SPEECH_TRANSCRIPTION_MODEL", "").strip()
    configured = provider == "openai-compatible" and bool(api_key and api_url and model)
    return {
        "provider": provider,
        "configured": configured,
        "model": model,
        "message": "可选转写已配置" if configured else "未配置转写；录音、回放、手动文本和自评仍可使用",
    }


def transcribe_audio(path: Path, mime_type: str, opener=urllib.request.urlopen) -> dict:
    status = transcription_status()
    if not status["configured"]:
        raise RuntimeError(status["message"])
    audio = path.read_bytes()
    if not audio or len(audio) > 25 * 1024 * 1024:
        raise ValueError("Audio must be between 1 byte and 25 MB for transcription")
    boundary = f"----LanguageCoach{secrets.token_hex(12)}"
    filename = path.name
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{status['model']}\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: {mime_type}\r\n\r\n".encode(),
        audio,
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    request = urllib.request.Request(
        os.environ.get("SPEECH_TRANSCRIPTION_API_URL", "https://api.openai.com/v1/audio/transcriptions").strip(),
        data=b"".join(parts),
        headers={
            "Authorization": f"Bearer {(os.environ.get('SPEECH_TRANSCRIPTION_API_KEY') or os.environ.get('OPENAI_API_KEY') or '').strip()}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with opener(request, timeout=90) as response:
            raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError("Transcription response exceeded the 1 MB limit")
            payload = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Transcription request failed with HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError("Transcription provider is unavailable") from error
    text = str(payload.get("text") or "").strip()
    if not text:
        raise ValueError("Transcription provider returned no text")
    return {"text": text, "provider": status["provider"], "model": status["model"]}
