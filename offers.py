"""Extraction, quote verification, update merge, eval CLI (CLAUDE.md section 7). Owner: Person A."""
from __future__ import annotations

from models import Offer, QuoteCheck


def load_messages() -> dict[str, str]:
    raise NotImplementedError


def parse_message(filename: str, text: str, use_llm: bool) -> tuple[Offer, str]:
    raise NotImplementedError


def verify(offer: Offer, text: str) -> list[QuoteCheck]:
    raise NotImplementedError


def merge_update(base: Offer, update: Offer) -> Offer:
    raise NotImplementedError


def compare(live: Offer, expected: Offer) -> tuple[int, int, list[str]]:
    raise NotImplementedError
