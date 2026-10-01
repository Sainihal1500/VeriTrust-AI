"""Small helpers for sanitizing local model output before it reaches users."""

import re
import os
import time
from urllib.error import URLError
from urllib.request import urlopen


_OLLAMA_CHECK_TTL = 10
_ollama_checked_at = 0.0
_ollama_is_available = False


def ollama_available() -> bool:
    global _ollama_checked_at, _ollama_is_available
    now = time.monotonic()
    if now - _ollama_checked_at < _OLLAMA_CHECK_TTL:
        return _ollama_is_available
    base_url = (os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip("/")
    try:
        with urlopen(f"{base_url}/api/tags", timeout=0.8):
            _ollama_is_available = True
    except (OSError, URLError, TimeoutError):
        _ollama_is_available = False
    _ollama_checked_at = now
    return _ollama_is_available


def strip_internal_reasoning(value: str | None) -> str:
    text = str(value or "")
    text = re.sub(r"(?is)<(?:think|analysis|reasoning)>.*?</(?:think|analysis|reasoning)>", "", text)
    text = re.sub(r"(?is)<think>.*$", "", text)
    text = re.sub(r"(?im)^\s*(?:analysis|chain.of.thought|reasoning)\s*:\s*.*?(?=^\s*(?:final|answer)\s*:|\Z)", "", text)
    text = re.sub(r"(?im)^\s*(?:final|answer)\s*:\s*", "", text)
    return text.strip()
