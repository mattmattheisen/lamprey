"""
signals.py — Pydantic models for all signal data structures.
"""
from __future__ import annotations
from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, field_validator


class SignalComponents(BaseModel):
    sentiment: float = 0.0
    volume_zscore: float = 0.0
    candlestick: float = 0.0
    news_catalyst: float = 0.0
    composite: float = 0.0

    @field_validator("sentiment", "volume_zscore", "candlestick", "news_catalyst", "composite", mode="before")
    @classmethod
    def round4(cls, v: float) -> float:
        return round(float(v), 4)


class ShortGates(BaseModel):
    borrow_available: bool = False
    borrow_rate_pct: float = 0.0
    short_interest_pct: float = 0.0
    locate_required: bool = False
    gate_pass: bool = False

    @field_validator("borrow_rate_pct", "short_interest_pct", mode="before")
    @classmethod
    def round4(cls, v: float) -> float:
        return round(float(v), 4)


class MacroGates(BaseModel):
    vix_ok: bool = True
    move_ok: bool = True
    cor1m_ok: bool = True
    vix_trend_ok: bool = True
    contango_ok: bool = True
    breadth_ok: bool = True
    regime: Literal[
        "equity_trend", "rate_shock", "vol_expansion", "crash_panic", "low_vol_grind"
    ] = "equity_trend"
    long_edge: Literal["strong", "reduced", "selective", "suspend", "flat"] = "strong"
    short_edge: Literal["strong", "caution", "news_gated", "weak", "flat"] = "weak"


class TickerResult(BaseModel):
    ticker: str
    signal: Literal["LONG", "SHORT", "WATCH", "FLAT"]
    long_components: SignalComponents
    short_components: SignalComponents
    short_gates: ShortGates
    macro: MacroGates
    notes: str = ""
    scanned_at: datetime


class ScanResult(BaseModel):
    scanned_at: datetime
    macro: MacroGates
    tickers: List[TickerResult]
    duration_ms: float

    @field_validator("duration_ms", mode="before")
    @classmethod
    def round4(cls, v: float) -> float:
        return round(float(v), 4)
