"""Thin LLM client. Supports three free options:
  - Google Gemini API (free tier key from aistudio.google.com)
  - Groq API (free tier key from console.groq.com; hosts Llama 3)
  - Ollama (fully local, e.g. llama3)
When none is configured the app uses the built-in offline generator.
"""
import json
import re
import time

import httpx

from .. import config


class LLMError(RuntimeError):
    pass


RETRY_STATUS = {429, 500, 502, 503, 504}   # overloaded / rate limited: worth retrying
RETRY_WAITS = [2, 5]                       # seconds between attempts
last_used: str | None = None               # provider that answered the most recent call


def providers() -> list[str]:
    """Configured providers in order of preference. Later ones are automatic backups."""
    p = config.LLM_PROVIDER
    if p == "offline":
        return []
    available = []
    if config.GEMINI_API_KEY:
        available.append("gemini")
    if config.GROQ_API_KEY:
        available.append("groq")
    if config.OLLAMA_URL:
        available.append("ollama")
    if p in available:  # an explicit choice goes first, the rest stay as backups
        available.remove(p)
        available.insert(0, p)
    return available


def provider() -> str:
    found = providers()
    return found[0] if found else "offline"


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


def _call(client: httpx.Client, p: str, system: str, prompt: str, temperature: float) -> str:
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
        return "".join(part.get("text", "") for part in parts)
    if p == "groq":
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
        return r.json()["choices"][0]["message"]["content"]
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
    return r.json()["message"]["content"]


def chat_json(system: str, prompt: str, temperature: float = 0.6):
    """Send a prompt and return the parsed JSON reply.

    A busy or rate-limited provider (429/5xx) is retried a couple of times; if it still
    fails, the next configured provider is tried before giving up."""
    global last_used
    chain = providers()
    if not chain:
        raise LLMError("No LLM provider configured")
    errors: list[str] = []
    with httpx.Client(timeout=config.LLM_TIMEOUT) as client:
        for p in chain:
            for attempt in range(len(RETRY_WAITS) + 1):
                try:
                    data = _parse_json(_call(client, p, system, prompt, temperature))
                    last_used = p
                    return data
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    error = f"{p} API returned {status}: {exc.response.text[:200]}"
                    retryable = status in RETRY_STATUS
                except Exception as exc:  # network errors, malformed JSON, unexpected payloads
                    error, retryable = f"{p} request failed: {exc}", True
                if not retryable or attempt == len(RETRY_WAITS):
                    errors.append(error)
                    break
                time.sleep(RETRY_WAITS[attempt])
    raise LLMError("; ".join(errors))
