"""
scanner.py — Orchestrator.  run_scan() → ScanResult.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import List, Literal, Optional

from app.config import get_settings
from app.models.signals import MacroGates, ScanResult, TickerResult
from app.services.data_feed import (
    fetch_news_catalyst,
    fetch_ohlcv,
    fetch_reddit_sentiment,
    fetch_unusual_whales,
)
from app.services.regime_gate import get_macro_gates, get_meme_overlay
from app.services.short_gates import evaluate_short_gates, short_gate_pass
from app.services.signal_engine import compute_signals, short_composite

log = logging.getLogger("lamprey")
settings = get_settings()


async def _scan_ticker(ticker: str, macro: MacroGates) -> TickerResult:
    overlay = get_meme_overlay(macro)
    now = datetime.now(timezone.utc)

    ohlcv, reddit, news, uw = await asyncio.gather(
        fetch_ohlcv(ticker),
        fetch_reddit_sentiment(ticker),
        fetch_news_catalyst(ticker),
        fetch_unusual_whales(ticker),
    )

    long_comp = await compute_signals(ticker, ohlcv, reddit, news)
    short_comp = await short_composite(ticker, ohlcv, reddit, news)
    short_gates = evaluate_short_gates(uw)

    notes_parts: List[str] = []

    signal: Literal["LONG", "SHORT", "WATCH", "FLAT"] = "FLAT"

    if overlay["long_gated"] and overlay["short_gated"]:
        signal = "FLAT"
        notes_parts.append(f"regime={macro.regime} gates both suspended")

    elif overlay["long_gated"]:
        if (
            short_comp.composite >= settings.short_composite_threshold
            and short_gate_pass(short_gates)
            and not overlay["short_gated"]
        ):
            signal = "SHORT"
            if short_gates.locate_required:
                notes_parts.append("LOCATE required")
        else:
            signal = "FLAT"
        notes_parts.append(f"long suspended ({macro.long_edge})")

    else:
        if long_comp.composite >= settings.long_composite_threshold:
            signal = "LONG"
        elif (
            short_comp.composite >= settings.short_composite_threshold
            and short_gate_pass(short_gates)
            and not overlay["short_gated"]
        ):
            signal = "SHORT"
            if short_gates.locate_required:
                notes_parts.append("LOCATE required")
        elif long_comp.composite >= settings.long_composite_threshold * 0.85:
            signal = "WATCH"
        else:
            signal = "FLAT"

    if macro.short_edge == "news_gated" and signal == "SHORT":
        if news.get("article_count", 0) == 0:
            signal = "FLAT"
            notes_parts.append("short news-gated: no catalyst")

    log.info(
        "%-6s signal=%-5s long_comp=%.4f short_comp=%.4f regime=%s",
        ticker, signal, long_comp.composite, short_comp.composite, macro.regime,
    )

    return TickerResult(
        ticker=ticker,
        signal=signal,
        long_components=long_comp,
        short_components=short_comp,
        short_gates=short_gates,
        macro=macro,
        notes="; ".join(notes_parts),
        scanned_at=now,
    )


async def run_scan(tickers: Optional[List[str]] = None) -> ScanResult:
    """Run a full scan and return a ScanResult."""
    t0 = time.perf_counter()
    watchlist = tickers or settings.watchlist
    macro = await get_macro_gates()

    results = await asyncio.gather(*[_scan_ticker(t, macro) for t in watchlist])

    duration_ms = round((time.perf_counter() - t0) * 1000, 4)
    log.info("scan complete: %d tickers in %.1f ms", len(results), duration_ms)

    return ScanResult(
        scanned_at=datetime.now(timezone.utc),
        macro=macro,
        tickers=list(results),
        duration_ms=duration_ms,
    )
