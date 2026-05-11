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
    """Score 0-1 measuring bullish candlestick/trend signals.

    Three equally-weighted components:
      1. Trend direction  — is price above key moving averages?
      2. Candle body      — is today's candle green and strong?
      3. Volume confirm   — is volume expanding on up days?
    """
    if len(ohlcv) < 5:
        return 0.0

    df = pd.DataFrame(ohlcv)
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    scores: List[float] = []

    # ── 1. Trend direction ────────────────────────────────────────────────────
    trend_score = 0.0
    close = df["close"]

    # Is close above 10-day MA?
    if len(close) >= 10:
        ma10 = close.rolling(10).mean().iloc[-1]
        if close.iloc[-1] > ma10:
            trend_score += 0.5

    # Is 5-day MA above 20-day MA? (mini golden cross)
    if len(close) >= 20:
        ma5 = close.rolling(5).mean().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        if ma5 > ma20:
            trend_score += 0.5
    elif len(close) >= 5:
        # Fallback: is today's close above 5-day MA?
        ma5 = close.rolling(5).mean().iloc[-1]
        if close.iloc[-1] > ma5:
            trend_score += 0.5

    scores.append(round(min(trend_score, 1.0), 4))

    # ── 2. Candle body strength ───────────────────────────────────────────────
    today = df.iloc[-1]
    high_low_range = today["high"] - today["low"]
    body = today["close"] - today["open"]

    if high_low_range == 0:
        candle_score = 0.5  # neutral — no range (e.g. halted stock)
    else:
        # Body ratio: how much of the candle range is the body?
        body_ratio = abs(body) / high_low_range  # 0-1
        is_green = body > 0
        # Green candle: score by body ratio; red candle: invert
        candle_score = body_ratio if is_green else (1.0 - body_ratio) * 0.3
        candle_score = round(min(max(candle_score, 0.0), 1.0), 4)

    scores.append(candle_score)

    # ── 3. Volume confirmation ────────────────────────────────────────────────
    # Are up days over the last 5 sessions heavier volume than down days?
    recent = df.tail(5).copy()
    recent["direction"] = (recent["close"] - recent["open"]).apply(
        lambda x: 1 if x > 0 else (-1 if x < 0 else 0)
    )
    up_vol = recent.loc[recent["direction"] == 1, "volume"].mean()
    down_vol = recent.loc[recent["direction"] == -1, "volume"].mean()

    if pd.isna(up_vol) and pd.isna(down_vol):
        vol_confirm = 0.5  # no data either way
    elif pd.isna(down_vol) or down_vol == 0:
        vol_confirm = 1.0  # all up days
    elif pd.isna(up_vol) or up_vol == 0:
        vol_confirm = 0.0  # all down days
    else:
        ratio = up_vol / (up_vol + down_vol)  # 0-1, 0.5 = equal
        vol_confirm = round(ratio, 4)

    scores.append(vol_confirm)

    return round(sum(scores) / len(scores), 4)


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
    # Invert CDL for short — bearish candles score high
    inv_candle = round(1.0 - _candlestick_score(ohlcv), 4)
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
