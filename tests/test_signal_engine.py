"""
test_signal_engine.py — Smoke tests.  No API calls required.

All tests use synthetic OHLCV data and stub reddit/news dicts.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import pytest

from app.services.signal_engine import (
    _candlestick_score,
    _sentiment_score,
    _volume_zscore_normalised,
    compute_signals,
    short_composite,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 30, trend: str = "flat") -> List[Dict[str, Any]]:
    from datetime import date, timedelta
    rows = []
    price = 10.0
    for i in range(n):
        d = date(2024, 1, 1) + timedelta(days=i)
        if trend == "up":
            price += 0.2
        elif trend == "down":
            price -= 0.1
        volume = 1_000_000 if i < n - 1 else 5_000_000
        rows.append({
            "date": str(d),
            "open": round(price, 4),
            "high": round(price * 1.01, 4),
            "low":  round(price * 0.99, 4),
            "close": round(price, 4),
            "volume": volume,
        })
    return rows


NEUTRAL_REDDIT: Dict[str, Any] = {"mention_count": 0, "vader_compound": 0.0, "velocity": 0.0}
NEUTRAL_NEWS:   Dict[str, Any] = {"headline_score": 0.0, "article_count": 0}

BULLISH_REDDIT: Dict[str, Any] = {"mention_count": 50, "vader_compound": 0.8, "velocity": 0.9}
BEARISH_REDDIT: Dict[str, Any] = {"mention_count": 30, "vader_compound": -0.7, "velocity": 0.6}


# ── Unit tests ────────────────────────────────────────────────────────────────

class TestVolumeZScore:
    def test_spike_returns_positive(self):
        ohlcv = _make_ohlcv(30)
        score = _volume_zscore_normalised(ohlcv)
        assert score > 0.0
        assert 0.0 <= score <= 1.0

    def test_empty_returns_zero(self):
        assert _volume_zscore_normalised([]) == 0.0

    def test_single_row_returns_zero(self):
        assert _volume_zscore_normalised(_make_ohlcv(1)) == 0.0

    def test_uniform_volume_returns_zero(self):
        rows = _make_ohlcv(30)
        for r in rows:
            r["volume"] = 1_000_000
        assert _volume_zscore_normalised(rows) == 0.0


class TestSentimentScore:
    def test_neutral(self):
        score = _sentiment_score(NEUTRAL_REDDIT)
        assert abs(score - 0.5) < 0.01

    def test_bullish(self):
        score = _sentiment_score(BULLISH_REDDIT)
        assert score > 0.7

    def test_bearish(self):
        score = _sentiment_score(BEARISH_REDDIT)
        assert score < 0.3

    def test_bounds(self):
        score = _sentiment_score({"vader_compound": 1.0, "velocity": 1.0})
        assert 0.0 <= score <= 1.0


class TestCandlestickScore:
    def test_returns_float_in_range(self):
        ohlcv = _make_ohlcv(30, trend="up")
        score = _candlestick_score(ohlcv)
        assert 0.0 <= score <= 1.0

    def test_short_ohlcv_returns_zero(self):
        assert _candlestick_score(_make_ohlcv(5)) == 0.0


# ── Integration smoke tests ───────────────────────────────────────────────────

class TestComputeSignals:
    def test_neutral_inputs(self):
        ohlcv = _make_ohlcv(30)
        result = asyncio.get_event_loop().run_until_complete(
            compute_signals("TEST", ohlcv, NEUTRAL_REDDIT, NEUTRAL_NEWS)
        )
        assert 0.0 <= result.composite <= 1.0
        assert result.sentiment == round(result.sentiment, 4)

    def test_bullish_inputs_higher_composite(self):
        ohlcv = _make_ohlcv(30, trend="up")
        bullish_news = {"headline_score": 0.8, "article_count": 5}
        neutral = asyncio.get_event_loop().run_until_complete(
            compute_signals("TEST", ohlcv, NEUTRAL_REDDIT, NEUTRAL_NEWS)
        )
        bullish = asyncio.get_event_loop().run_until_complete(
            compute_signals("TEST", ohlcv, BULLISH_REDDIT, bullish_news)
        )
        assert bullish.composite > neutral.composite

    def test_weights_sum_check(self):
        ohlcv = _make_ohlcv(30)
        reddit = {"vader_compound": 1.0, "velocity": 1.0, "mention_count": 100}
        news   = {"headline_score": 1.0, "article_count": 10}
        result = asyncio.get_event_loop().run_until_complete(
            compute_signals("TEST", ohlcv, reddit, news)
        )
        assert result.composite <= 1.0


class TestShortComposite:
    def test_bearish_sentiment_raises_short_composite(self):
        ohlcv = _make_ohlcv(30)
        result = asyncio.get_event_loop().run_until_complete(
            short_composite("TEST", ohlcv, BEARISH_REDDIT, NEUTRAL_NEWS)
        )
        neutral_result = asyncio.get_event_loop().run_until_complete(
            short_composite("TEST", ohlcv, NEUTRAL_REDDIT, NEUTRAL_NEWS)
        )
        assert result.sentiment > neutral_result.sentiment

    def test_returns_signal_components(self):
        from app.models.signals import SignalComponents
        ohlcv = _make_ohlcv(30)
        result = asyncio.get_event_loop().run_until_complete(
            short_composite("TEST", ohlcv, BEARISH_REDDIT, NEUTRAL_NEWS)
        )
        assert isinstance(result, SignalComponents)
        assert 0.0 <= result.composite <= 1.0
