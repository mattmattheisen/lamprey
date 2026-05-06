"""
short_gates.py — Evaluate the three short-specific gates.

All three must pass for a SHORT signal:
  1. Borrow available (status != "unavailable")
  2. Borrow rate < MAX_BORROW_RATE_PCT  (default 10%)
  3. Short interest < MAX_SHORT_INTEREST_PCT (default 30%)

LOCATE is returned when borrow is "tight" but rate and SI are within limits.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.config import get_settings
from app.models.signals import ShortGates

log = logging.getLogger("lamprey")
settings = get_settings()


def evaluate_short_gates(uw_data: Dict[str, Any]) -> ShortGates:
    """
    Evaluate short gates from Unusual Whales payload (or stub).

    uw_data expected keys:
        borrow_status      : str  ("available" | "tight" | "unavailable")
        borrow_rate_pct    : float
        short_interest_pct : float
    """
    borrow_status: str = str(uw_data.get("borrow_status", "available")).lower()
    borrow_rate: float = float(uw_data.get("borrow_rate_pct", 0.0))
    short_interest: float = float(uw_data.get("short_interest_pct", 0.0))

    borrow_available = borrow_status != "unavailable"
    rate_ok = borrow_rate < settings.max_borrow_rate_pct
    si_ok = short_interest < settings.max_short_interest_pct

    locate_required = borrow_status == "tight" and rate_ok and si_ok

    gate_pass = borrow_available and rate_ok and si_ok

    log.debug(
        "short_gates — borrow=%s rate=%.2f si=%.2f pass=%s locate=%s",
        borrow_status,
        borrow_rate,
        short_interest,
        gate_pass,
        locate_required,
    )

    return ShortGates(
        borrow_available=borrow_available,
        borrow_rate_pct=round(borrow_rate, 4),
        short_interest_pct=round(short_interest, 4),
        locate_required=locate_required,
        gate_pass=gate_pass,
    )


def short_gate_pass(gates: ShortGates) -> bool:
    """Return True if all short gates pass."""
    return gates.gate_pass
