"""
python/ai_client.py — shared AI provider wrapper (Gemini primary / Groq
fallback), used by research (WF-05), personalization (WF-08), and
classification (WF-12) — the only three workflows in the system that call an
AI model at all (docs/14-security-spec.md §1 table + §4).

Kept in one file so:
  1. Credential handling for AI providers lives in exactly one place
     (docs/14-security-spec.md §1).
  2. The Gemini-primary/Groq-fallback-with-backoff pattern (docs/14 §4,
     "consistent with the rest of the Hooze stack") is implemented once,
     not reimplemented slightly differently in three modules.
  3. All three callers get the same "always return valid JSON, no
     preamble/fences" contract enforcement (every prompts/*.md file ends
     with this instruction) via one shared parser.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from python.config import ai_provider


class AIError(RuntimeError):
    pass


def _strip_markdown_fences(text: str) -> str:
    """Prompts instruct the model to never wrap output in ```json fences,
    but models don't always comply — strip them defensively rather than
    trust the instruction blindly."""
    stripped = text.strip()
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def call_ai(system_prompt: str, user_input: dict[str, Any], max_retries: int = 3) -> dict[str, Any]:
    """Sends `system_prompt` + JSON-serialized `user_input` to the configured
    provider, parses the response as JSON, and returns it as a dict.

    Retries with exponential backoff on transient errors (per docs/14-
    security-spec.md §4 "respect... backoff"), and falls back from Gemini to
    Groq if Gemini is unavailable — matching the existing Hooze stack
    pattern referenced in that same section.

    Raises AIError if all providers/retries are exhausted or the response
    isn't valid JSON — callers (research/personalization/classification) are
    each responsible for their OWN safe-default behavior on that error
    (e.g. classification defaults to UNKNOWN per docs/12 §4; that default
    lives in classification/classifier.py, not here, because "what's safe"
    is domain-specific).
    """
    providers = [ai_provider()]
    if "groq" not in providers:
        providers.append("groq")
    if "gemini" not in providers:
        providers.append("gemini")

    last_error: Exception | None = None

    for provider in providers:
        for attempt in range(max_retries):
            try:
                raw_text = _call_provider(provider, system_prompt, user_input)
                cleaned = _strip_markdown_fences(raw_text)
                return json.loads(cleaned)
            except (AIError, json.JSONDecodeError) as exc:
                last_error = exc
                time.sleep(min(2**attempt, 8))  # exponential backoff, capped at 8s
                continue

    raise AIError(f"All AI providers/retries exhausted. Last error: {last_error}")


def _call_provider(provider: str, system_prompt: str, user_input: dict[str, Any]) -> str:
    import os

    if provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise AIError("GEMINI_API_KEY not set")
        return _call_gemini(api_key, system_prompt, user_input)
    if provider == "groq":
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise AIError("GROQ_API_KEY not set")
        return _call_groq(api_key, system_prompt, user_input)
    raise AIError(f"Unknown AI provider: {provider}")


def _call_gemini(api_key: str, system_prompt: str, user_input: dict[str, Any]) -> str:
    import httpx

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={api_key}"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": json.dumps(user_input)}]}],
        "generationConfig": {"temperature": 0.4, "response_mime_type": "application/json"},
    }
    resp = httpx.post(url, json=payload, timeout=30.0)
    if resp.status_code != 200:
        raise AIError(f"Gemini call failed: {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise AIError(f"Unexpected Gemini response shape: {data}") from exc


def _call_groq(api_key: str, system_prompt: str, user_input: dict[str, Any]) -> str:
    import httpx

    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_input)},
        ],
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
    }
    resp = httpx.post(
        url, json=payload, headers={"Authorization": f"Bearer {api_key}"}, timeout=30.0
    )
    if resp.status_code != 200:
        raise AIError(f"Groq call failed: {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise AIError(f"Unexpected Groq response shape: {data}") from exc
