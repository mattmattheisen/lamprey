"""
signal_engine.py — Compute long and short composite signals.

Weights:
  Sentiment      35%
  Volume z-score 30%
  Candlestick    20%
  News catalyst  15%
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List
import pandas as pd
from app.models.signals import SignalComponents

log = logging.getLogger("lamprey")

W_SENTIMENT = 0.35
W_VOLUME    = 0.30
W_CANDLE    = 0.20
W_NEWS      = 0.15

VOLUME_Z_CAP        = 4.0
VOLUME_ROLLING_WINDOW = 20


def _volume_zscore_normalised(ohlcv: List[Dict[str, Any]]) -> float:
    if len(ohlcv) < 2:
        return 0.0
    df = pd.DataFrame(ohlcv)
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    roll = df["volume"].rolling(VOLUME_ROLLING_WINDOW, min_periods=2)
    mean = roll.mean().iloc[-1]
    std  = roll.std().iloc[-1]
    if not std or std == 0:
        return 0.0
    latest_vol = df["volume"].iloc[-1]
    z = (latest_vol - mean) / std
    z_capped = min(max(z, 0.0), VOLUME_Z_CAP)
    return round(z_capped / VOLUME_Z_CAP, 4)


def _candlestick_score(ohlcv: List[Dict[str, Any]]) -> float:
    """
    Score bullish candlestick structure 0-1 using three components:
      1. Trend direction  (price vs MA10, MA5 vs MA20)
      2. Candle body      (green candle with large body)
      3. Volume confirm   (up-day volume > down-day volume over 5 days)
    """
    if len(ohlcv) < 10:
        return 0.0
    try:
        df = pd.DataFrame(ohlcv)
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df.dropna(subset=["open", "high", "low", "close"], inplace=True)
        if len(df) < 10:
            return 0.0

        close = df["close"]
        ma5   = close.rolling(5).mean().iloc[-1]
        ma10  = close.rolling(10).mean().iloc[-1]
        ma20  = close.rolling(20, min_periods=10).mean().iloc[-1]
        last  = close.iloc[-1]

        trend = 0.0
        if last > ma10:
            trend += 0.5
        if ma5 > ma20:
            trend += 0.5

        last_open  = df["open"].iloc[-1]
        last_high  = df["high"].iloc[-1]
        last_low   = df["low"].iloc[-1]
        last_close = df["close"].iloc[-1]
        candle_range = last_high - last_low
        body = abs(last_close - last_open)
        body_pct = (body / candle_range) if candle_range > 0 else 0.0
        green = 1.0 if last_close > last_open else 0.0
        candle_score = green * body_pct

        recent = df.tail(5).copy()
        recent["up_vol"]   = recent["volume"].where(recent["close"] > recent["open"], 0)
        recent["down_vol"] = recent["volume"].where(recent["close"] <= recent["open"], 0)
        up_vol   = recent["up_vol"].sum()
        down_vol = recent["down_vol"].sum()
        total_vol = up_vol + down_vol
        vol_confirm = (up_vol / total_vol) if total_vol > 0 else 0.5

        score = round((trend + candle_score + vol_confirm) / 3, 4)
        return min(max(score, 0.0), 1.0)
    except Exception as exc:
        log.warning("_candlestick_score failed: %s", exc)
        return 0.0


def _sentiment_score(reddit: Dict[str, Any]) -> float:
    compound = float(reddit.get("vader_compound", 0.0))
    velocity = float(reddit.get("velocity", 0.0))
    base     = (compound + 1) / 2
    boosted  = base + velocity * 0.15
    return round(min(max(boosted, 0.0), 1.0), 4)


async def compute_signals(
    ticker: str,
    ohlcv: List[Dict[str, Any]],
    reddit: Dict[str, Any],
    news: Dict[str, Any],
) -> SignalComponents:
    sentiment  = _sentiment_score(reddit)
    volume     = _volume_zscore_normalised(ohlcv)
    candle     = _candlestick_score(ohlcv)
    news_score = round(float(news.get("headline_score", 0.5)), 4)

    composite = round(
        W_SENTIMENT * sentiment
        + W_VOLUME  * volume
        + W_CANDLE  * candle
        + W_NEWS    * news_score,
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
    compound  = float(reddit.get("vader_compound", 0.0))
    velocity  = float(reddit.get("velocity", 0.0))
    inv_compound       = ((-compound) + 1) / 2
    reversal_velocity  = velocity * (1 - ((compound + 1) / 2))
    short_sentiment    = round(min(max(inv_compound + reversal_velocity * 0.2, 0.0), 1.0), 4)

    volume     = _volume_zscore_normalised(ohlcv)
    inv_candle = round(1.0 - _candlestick_score(ohlcv), 4)
    news_score = round(float(news.get("headline_score", 0.5)), 4)
    short_news = round(1.0 - news_score, 4)

    composite = round(
        W_SENTIMENT * short_sentiment
        + W_VOLUME  * volume
        + W_CANDLE  * inv_candle
        + W_NEWS    * short_news,
        4,
    )
    return SignalComponents(
        sentiment=short_sentiment,
        volume_zscore=volume,
        candlestick=inv_candle,
        news_catalyst=short_news,
        composite=composite,
    )
