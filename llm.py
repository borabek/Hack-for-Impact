"""LLM provider wrapper (CLAUDE.md section 7). Owner: Person A."""
from __future__ import annotations


def available() -> bool:
    raise NotImplementedError


def complete(system: str, user: str, json_mode: bool = False) -> str | None:
    raise NotImplementedError


def complete_json(system: str, user: str) -> dict | None:
    raise NotImplementedError
