"""
signal_engine.py — Compute long and short composite signals.

Weights:
  Sentiment      35%
  Volume z-score 30%
  Candlestick    20%
  News catalyst  15%

Long threshold:  0.65
Short threshold: 0.75
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd
import pandas_ta_classic as ta

from app.config import get_settings
from app.models.signals import SignalComponents

log = logging.getLogger("lamprey")
settings = get_settings()

W_SENTIMENT = 0.35
W_VOLUME = 0.30
W_CANDLE = 0.20
W_NEWS = 0.15

VOLUME_Z_CAP = 4.0
VOLUME_ROLLING_WINDOW = 20


def _volume_zscore_normalised(ohlcv: List[Dict[str, Any]]) -> float:
    if len(ohlcv) < 2:
        return 0.0
    df = pd.DataFrame(ohlcv)
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    roll = df["volume"].rolling(VOLUME_ROLLING_WINDOW, min_periods=2)
    mean = roll.mean().iloc[-1]
    std = roll.std().iloc[-1]
    if not std or std == 0:
        return 0.0
    latest_vol = df["volume"].iloc[-1]
    z = (latest_vol - mean) / std
    z_capped = min(max(z, 0.0), VOLUME_Z_CAP)
    return round(z_capped / VOLUME_Z_CAP, 4)


def _candlestick_score(ohlcv: List[Dict[str, Any]]) -> float:
    if len(ohlcv) < 10:
        return 0.0
    try:
        df = pd.DataFrame(ohlcv)
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df.dropna(subset=["open", "high", "low", "close"], inplace=True)
        if df.empty:
            return 0.0
        patterns = df.ta.cdl_pattern(name="all")
        if patterns is None or patterns.empty:
            return 0.0
        last_row = patterns.iloc[-1]
        bullish = last_row[last_row > 0].sum()
        total_possible = len(last_row) * 100
        return round(min(float(bullish) / max(total_possible, 1), 1.0), 4)
    except Exception as exc:
        log.warning("candlestick_score failed: %s", exc)
        return 0.0


def _sentiment_score(reddit: Dict[str, Any]) -> float:
    compound = float(reddit.get("vader_compound", 0.0))
    velocity = float(reddit.get("velocity", 0.0))
    base = (compound + 1) / 2
    boosted = base + velocity * 0.15
    return round(min(max(boosted, 0.0), 1.0), 4)


async def compute_signals(
    ticker: str,
    ohlcv: List[Dict[str, Any]],
    reddit: Dict[str, Any],
    news: Dict[str, Any],
) -> SignalComponents:
    sentiment = _sentiment_score(reddit)
    volume = _volume_zscore_normalised(ohlcv)
    candle = _candlestick_score(ohlcv)
    news_score = round(float(news.get("headline_score", 0.0)), 4)

    composite = round(
        W_SENTIMENT * sentiment
        + W_VOLUME * volume
        + W_CANDLE * candle
        + W_NEWS * news_score,
        4,
    )
    return SignalComponents(
        sentiment=sentiment,
        volume_zscore=volume,
        candlestick=candle,
        news_catalyst=news_score,
        composite=composite,
    )


async def short_composite(
    ticker: str,
    ohlcv: List[Dict[str, Any]],
    reddit: Dict[str, Any],
    news: Dict[str, Any],
) -> SignalComponents:
    compound = float(reddit.get("vader_compound", 0.0))
    velocity = float(reddit.get("velocity", 0.0))
    inv_compound = ((-compound) + 1) / 2
    reversal_velocity = velocity * (1 - ((compound + 1) / 2))
    short_sentiment = round(min(max(inv_compound + reversal_velocity * 0.2, 0.0), 1.0), 4)

    volume = _volume_zscore_normalised(ohlcv)

    inv_candle = 0.0
    if len(ohlcv) >= 10:
        try:
            df = pd.DataFrame(ohlcv)
            for col in ["open", "high", "low", "close"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df.dropna(subset=["open", "high", "low", "close"], inplace=True)
            if not df.empty:
                patterns = df.ta.cdl_pattern(name="all")
                if patterns is not None and not patterns.empty:
                    last_row = patterns.iloc[-1]
                    bearish = abs(last_row[last_row < 0].sum())
                    total_possible = len(last_row) * 100
                    inv_candle = round(min(float(bearish) / max(total_possible, 1), 1.0), 4)
        except Exception as exc:
            log.warning("short candlestick failed: %s", exc)

    news_score = round(float(news.get("headline_score", 0.0)), 4)
    short_news = round(1.0 - news_score, 4)

    composite = round(
        W_SENTIMENT * short_sentiment
        + W_VOLUME * volume
        + W_CANDLE * inv_candle
        + W_NEWS * short_news,
        4,
    )
    return SignalComponents(
        sentiment=short_sentiment,
        volume_zscore=volume,
        candlestick=inv_candle,
        news_catalyst=short_news,
        composite=composite,
    )
