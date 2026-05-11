"""
short_gates.py — Evaluate the three short-specific gates.
All three must pass for a SHORT signal:
  1. Borrow available  (status != "unavailable")
  2. Borrow rate       < max_borrow_rate_pct  (default 10%)
  3. Short interest    < max_short_interest_pct (default 30%)
"""
from __future__ import annotations
import logging
from typing import Any, Dict
from app.config import get_settings
from app.models.signals import ShortGates

log = logging.getLogger("lamprey")
settings = get_settings()


def evaluate_short_gates(uw_data: Dict[str, Any]) -> ShortGates:
    borrow_status  = str(uw_data.get("borrow_status", "available")).lower()
    borrow_rate    = float(uw_data.get("borrow_rate_pct", 0.0))
    short_interest = float(uw_data.get("short_interest_pct", 0.0))

    borrow_available = borrow_status != "unavailable"
    rate_ok          = borrow_rate < settings.max_borrow_rate_pct
    si_ok            = short_interest < settings.max_short_interest_pct
    locate_required  = borrow_status == "tight" and rate_ok and si_ok
    gate_pass        = borrow_available and rate_ok and si_ok

    return ShortGates(
        borrow_available=borrow_available,
        borrow_rate_pct=round(borrow_rate, 4),
        short_interest_pct=round(short_interest, 4),
        locate_required=locate_required,
        gate_pass=gate_pass,
    )


def short_gate_pass(gates: ShortGates) -> bool:
    return gates.gate_pass
