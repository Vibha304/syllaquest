"""Thin LLM client. Supports three free options:
  - Google Gemini API (free tier key from aistudio.google.com)
  - Groq API (free tier key from console.groq.com; hosts Llama 3)
  - Ollama (fully local, e.g. llama3)
When none is configured the app uses the built-in offline generator.
"""
import json
import re

import httpx

from .. import config


class LLMError(RuntimeError):
    pass


def provider() -> str:
    p = config.LLM_PROVIDER
    if p == "offline":
        return "offline"
    if p in ("gemini", "auto") and config.GEMINI_API_KEY:
        return "gemini"
    if p in ("groq", "auto") and config.GROQ_API_KEY:
        return "groq"
    if p in ("ollama", "auto") and config.OLLAMA_URL:
        return "ollama"
    return "offline"


def model_name() -> str:
    return {"gemini": config.GEMINI_MODEL, "groq": config.GROQ_MODEL, "ollama": config.OLLAMA_MODEL}.get(
        provider(), "rule-based NLP generator"
    )


def _parse_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"[\[{].*[\]}]", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise


def chat_json(system: str, prompt: str, temperature: float = 0.6):
    """Send a prompt and return the parsed JSON reply."""
    p = provider()
    try:
        with httpx.Client(timeout=config.LLM_TIMEOUT) as client:
            if p == "gemini":
                r = client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent",
                    headers={"x-goog-api-key": config.GEMINI_API_KEY},
                    json={
                        "systemInstruction": {"parts": [{"text": system}]},
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
                    },
                )
                r.raise_for_status()
                parts = r.json()["candidates"][0]["content"]["parts"]
                text = "".join(part.get("text", "") for part in parts)
            elif p == "groq":
                r = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
                    json={
                        "model": config.GROQ_MODEL,
                        "temperature": temperature,
                        "response_format": {"type": "json_object"},
                        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                    },
                )
                r.raise_for_status()
                text = r.json()["choices"][0]["message"]["content"]
            elif p == "ollama":
                r = client.post(
                    f"{config.OLLAMA_URL.rstrip('/')}/api/chat",
                    json={
                        "model": config.OLLAMA_MODEL,
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": temperature},
                        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                    },
                )
                r.raise_for_status()
                text = r.json()["message"]["content"]
            else:
                raise LLMError("No LLM provider configured")
        return _parse_json(text)
    except LLMError:
        raise
    except httpx.HTTPStatusError as exc:
        raise LLMError(f"{p} API returned {exc.response.status_code}: {exc.response.text[:200]}") from exc
    except Exception as exc:  # network errors, malformed JSON, unexpected payloads
        raise LLMError(f"{p} request failed: {exc}") from exc
