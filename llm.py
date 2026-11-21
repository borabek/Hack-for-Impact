"""LLM provider wrapper (CLAUDE.md section 7). Owner: Person A.

Provider from env LLM_PROVIDER (anthropic | openai | gemini | none), model from LLM_MODEL.
Every failure returns None and prints to stderr: the app must never crash because of the LLM,
and callers fall back to the replayed (hand-checked) answers.
"""
from __future__ import annotations

import json
import os
import re
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # python-dotenv missing: env vars still work
    pass

DEFAULT_MODELS = {
    "anthropic": "claude-opus-5-5",
    "openai": "gpt-4.1",
    "gemini": "gemini-3.5-flash-lite",  # the larger flash models were overloaded on the free tier
}
KEY_VARS = {
    "anthropic": ["ANTHROPIC_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
}
TIMEOUT_S = 90


def _log(msg: str) -> None:
    print(f"llm: {msg}", file=sys.stderr)


def provider() -> str:
    p = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if p:
        return p
    for name, keys in KEY_VARS.items():  # no provider set: infer from whichever key exists
        if any(os.getenv(k) for k in keys):
            return name
    return "none"


def model() -> str:
    return (os.getenv("LLM_MODEL") or "").strip() or DEFAULT_MODELS.get(provider(), "")


def _key() -> str | None:
    for k in KEY_VARS.get(provider(), []):
        if os.getenv(k):
            return os.getenv(k)
    return None


def available() -> bool:
    """True only if a provider is configured, its key is set and its SDK imports."""
    p = provider()
    if p not in KEY_VARS or not _key():
        return False
    try:
        if p == "anthropic":
            import anthropic  # noqa: F401
        elif p == "openai":
            import openai  # noqa: F401
        else:
            from google import genai  # noqa: F401
    except Exception:
        return False
    return True


def label() -> str:
    return f"{provider()}/{model()}" if available() else "none"


def _anthropic(system: str, user: str, json_mode: bool) -> str | None:
    import anthropic

    client = anthropic.Anthropic(api_key=_key(), timeout=TIMEOUT_S, max_retries=1)
    if json_mode:
        system += "\n\nRespond with a single JSON object only: no prose, no code fences."
    base = dict(model=model(), max_tokens=16000, system=system,
                messages=[{"role": "user", "content": user}])
    # Current Claude models reject sampling params (temperature), so none is sent.
    # Ask for server-side refusal fallback first; retry without it if the model/account rejects it.
    attempts = [
        lambda: client.beta.messages.create(**base, betas=["server-side-fallback-2026-07-01"], fallbacks="default"),
        lambda: client.messages.create(**base),
    ]
    resp = None
    for i, call in enumerate(attempts):
        try:
            resp = call()
            break
        except (anthropic.BadRequestError, TypeError) as exc:
            if i == len(attempts) - 1:
                raise
            _log(f"retrying without fallbacks ({exc.__class__.__name__})")
    if resp.stop_reason == "refusal":
        _log("model declined the request")
        return None
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text") or None


def _openai(system: str, user: str, json_mode: bool) -> str | None:
    import openai

    client = openai.OpenAI(api_key=_key(), timeout=TIMEOUT_S)
    kwargs = dict(model=model(), messages=[{"role": "system", "content": system},
                                           {"role": "user", "content": user}])
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        resp = client.chat.completions.create(**kwargs, temperature=0)
    except openai.BadRequestError as exc:  # some models reject temperature: retry once without it
        _log(f"retrying without temperature ({exc})")
        resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content


def _gemini(system: str, user: str, json_mode: bool) -> str | None:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=_key(), http_options=types.HttpOptions(timeout=TIMEOUT_S * 1000))
    cfg = dict(system_instruction=system)
    if json_mode:
        cfg["response_mime_type"] = "application/json"
    try:
        resp = client.models.generate_content(model=model(), contents=user,
                                              config=types.GenerateContentConfig(**cfg, temperature=0))
    except Exception as exc:
        _log(f"retrying without temperature ({exc})")
        resp = client.models.generate_content(model=model(), contents=user,
                                              config=types.GenerateContentConfig(**cfg))
    return resp.text


def complete(system: str, user: str, json_mode: bool = False) -> str | None:
    if not available():
        return None
    try:
        fn = {"anthropic": _anthropic, "openai": _openai, "gemini": _gemini}[provider()]
        return fn(system, user, json_mode)
    except Exception as exc:
        _log(f"{provider()} call failed: {exc.__class__.__name__}: {exc}")
        return None


def parse_json(text: str | None) -> dict | None:
    """Pull one JSON object out of a model reply (tolerates code fences and stray prose)."""
    if not text:
        return None
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        out = json.loads(t)
        return out if isinstance(out, dict) else None
    except json.JSONDecodeError:
        pass
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        out = json.loads(t[start:end + 1])
        return out if isinstance(out, dict) else None
    except json.JSONDecodeError as exc:
        _log(f"could not parse JSON: {exc}")
        return None


def complete_json(system: str, user: str) -> dict | None:
    return parse_json(complete(system, user, json_mode=True))
