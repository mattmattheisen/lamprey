"""
regime_gate.py — Macro regime classifier.
Gates: VIX · MOVE · COR1M · VIX trend · contango · breadth
VIX gate is live via yfinance. All others stubbed to passing.
"""
from __future__ import annotations
import logging
from typing import Literal
from app.models.signals import MacroGates
from app.services.data_feed import fetch_vix_level

log = logging.getLogger("lamprey")
VIX_CAUTION = 25.0
VIX_DANGER  = 35.0


async def get_macro_gates() -> MacroGates:
    """Evaluate all macro gates and return a MacroGates with derived regime."""
    vix = fetch_vix_level()   # synchronous — no await needed with yfinance
    vix_ok       = vix < VIX_CAUTION
    vix_trend_ok = vix < VIX_DANGER

    # Stubbed gates — all pass until live feeds are connected
    move_ok     = True
    cor1m_ok    = True
    contango_ok = True
    breadth_ok  = True

    regime = _classify_regime(vix)
    long_edge, short_edge = _regime_edges(regime)

    return MacroGates(
        vix_ok=vix_ok,
        move_ok=move_ok,
        cor1m_ok=cor1m_ok,
        vix_trend_ok=vix_trend_ok,
        contango_ok=contango_ok,
        breadth_ok=breadth_ok,
        regime=regime,
        long_edge=long_edge,
        short_edge=short_edge,
    )


def _classify_regime(vix: float) -> Literal[
    "equity_trend", "rate_shock", "vol_expansion", "crash_panic", "low_vol_grind"
]:
    if vix >= VIX_DANGER:
        return "crash_panic"
    if vix >= VIX_CAUTION:
        return "vol_expansion"
    if vix < 15.0:
        return "low_vol_grind"
    return "equity_trend"


def _regime_edges(regime: str) -> tuple[
    Literal["strong", "reduced", "selective", "suspend", "flat"],
    Literal["strong", "caution", "news_gated", "weak", "flat"],
]:
    mapping = {
        "equity_trend":  ("strong",    "weak"),
        "rate_shock":    ("reduced",   "strong"),
        "vol_expansion": ("suspend",   "caution"),
        "crash_panic":   ("flat",      "flat"),
        "low_vol_grind": ("selective", "news_gated"),
    }
    return mapping.get(regime, ("strong", "weak"))  # type: ignore


def get_meme_overlay(macro: MacroGates) -> dict:
    """Return dict describing how the regime modifies meme stock edge."""
    return {
        "regime":      macro.regime,
        "long_edge":   macro.long_edge,
        "short_edge":  macro.short_edge,
        "long_gated":  macro.long_edge in ("suspend", "flat"),
        "short_gated": macro.short_edge == "flat",
    }
