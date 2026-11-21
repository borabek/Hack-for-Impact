"""Orchestration, decision, explanation (CLAUDE.md section 7). Owner: Person A."""
from __future__ import annotations


def load_scenario():
    raise NotImplementedError


def gather_offers(use_llm: bool, fee_rise: bool):
    raise NotImplementedError


def run(scn, factors, payments, *, p_miss, fee_rise=False, use_llm=False):
    raise NotImplementedError


def confirm_slot(scn, factors, payments, *, paperwork_done):
    raise NotImplementedError
