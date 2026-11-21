"""SolvaPay-style buyer payments, simulated (CLAUDE.md section 7). Owner: Person A."""
from __future__ import annotations

from models import Buyer, SpendPolicy


class Payments:
    def __init__(self, policy: SpendPolicy, buyer: Buyer, path: str = "data/state.json"):
        raise NotImplementedError
