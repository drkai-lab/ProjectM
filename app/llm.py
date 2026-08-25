"""Optional fail-safe OpenAI-compatible translation; local dictionary stays primary."""
from __future__ import annotations
import httpx
from . import config

TRANSLATION_TIMEOUT = 3.0

def translate(text: str, target_language: str, *, client=None) -> str:
    if not text or not config.LLM_ENABLED:
        return text
    owned = client is None
    client = client or httpx.Client(timeout=TRANSLATION_TIMEOUT)
    try:
        r = client.post(
            f"{config.LLM_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
            json={"model": config.LLM_MODEL, "temperature": 0,
                  "messages": [{"role": "system", "content": f"Translate to {target_language}; return only the translation."},
                               {"role": "user", "content": text}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip() or text
    except Exception:
        return text
    finally:
        if owned:
            client.close()