"""
data_feed.py — All external data fetches using yfinance (free, no API key).
NewsAPI optional for enhanced news scoring.
Reddit sentiment is stubbed at neutral.
Unusual Whales is stubbed at neutral.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List

import yfinance as yf

from app.config import get_settings

log = logging.getLogger("lamprey")
settings = get_settings()


# ── OHLCV via yfinance ────────────────────────────────────────────────────────

def fetch_ohlcv(ticker: str, lookback_days: int = 30) -> List[Dict[str, Any]]:
    """Return list of daily OHLCV dicts for *ticker* via Yahoo Finance."""
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=f"{lookback_days}d", interval="1d", auto_adjust=True)
        if df.empty:
            log.warning("fetch_ohlcv: no data for %s — using stub", ticker)
            return _stub_ohlcv(lookback_days)
        rows = []
        for dt, row in df.iterrows():
            rows.append({
                "date":   str(dt.date()),
                "open":   round(float(row["Open"]),   4),
                "high":   round(float(row["High"]),   4),
                "low":    round(float(row["Low"]),    4),
                "close":  round(float(row["Close"]),  4),
                "volume": int(row["Volume"]),
            })
        return rows
    except Exception as exc:
        log.warning("fetch_ohlcv failed for %s: %s — using stub", ticker, exc)
        return _stub_ohlcv(lookback_days)


def _stub_ohlcv(days: int) -> List[Dict[str, Any]]:
    import random
    rows = []
    price = 10.0
    for i in range(days):
        d = date.today() - timedelta(days=days - i)
        price = max(1.0, price + random.uniform(-0.5, 0.5))
        rows.append({
            "date":   str(d),
            "open":   round(price, 4),
            "high":   round(price * 1.02, 4),
            "low":    round(price * 0.98, 4),
            "close":  round(price, 4),
            "volume": int(random.uniform(500_000, 5_000_000)),
        })
    return rows


# ── VIX via yfinance ──────────────────────────────────────────────────────────

def fetch_vix_level() -> float:
    """Return latest VIX level. Tries ^VIX then UVXY as fallback."""
    for ticker in ["^VIX", "UVXY"]:
        try:
            df = yf.Ticker(ticker).history(period="5d", interval="1d")
            if not df.empty:
                val = round(float(df["Close"].iloc[-1]), 2)
                log.info("fetch_vix_level: %s = %.2f", ticker, val)
                return val
        except Exception as exc:
            log.warning("fetch_vix_level %s failed: %s", ticker, exc)
    log.warning("fetch_vix_level: all sources failed — defaulting to 18.0")
    return 18.0


# ── Reddit sentiment (stubbed) ────────────────────────────────────────────────

async def fetch_reddit_sentiment(ticker: str) -> Dict[str, Any]:
    """Stubbed — returns neutral sentiment values."""
    log.debug("fetch_reddit_sentiment: STUBBED for %s", ticker)
    return {"mention_count": 0, "vader_compound": 0.0, "velocity": 0.0}


# ── News catalyst ─────────────────────────────────────────────────────────────

async def fetch_news_catalyst(ticker: str) -> Dict[str, Any]:
    """
    Fetch recent news headlines via yfinance and score with VADER.
    Falls back to neutral 0.5 if no headlines found.
    """
    try:
        t = yf.Ticker(ticker)
        news = t.news
        if not news:
            return {"headline_score": 0.5, "articles": 0}

        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        sia = SentimentIntensityAnalyzer()
        scores = []
        for item in news[:10]:
            title = item.get("content", {}).get("title", "") or item.get("title", "")
            if title:
                compound = sia.polarity_scores(title)["compound"]
                scores.append(compound)

        if not scores:
            return {"headline_score": 0.5, "articles": 0}

        avg = sum(scores) / len(scores)
        normalized = round((avg + 1) / 2, 4)
        return {"headline_score": normalized, "articles": len(scores)}
    except Exception as exc:
        log.warning("fetch_news_catalyst failed for %s: %s", ticker, exc)
        return {"headline_score": 0.5, "articles": 0}


# ── Unusual Whales (stubbed) ──────────────────────────────────────────────────

async def fetch_unusual_whales(ticker: str) -> Dict[str, Any]:
    """Stubbed — returns neutral short-gate values."""
    log.debug("fetch_unusual_whales: STUBBED for %s", ticker)
    return {
        "borrow_status":    "available",
        "borrow_rate_pct":  0.0,
        "short_interest_pct": 0.0,
    }


# ── Focus trade quote for MU / NVDA dashboard ─────────────────────────────────

def fetch_focus_quote(ticker: str) -> Dict[str, Any]:
    """
    Return a rich quote dict for the focus trader dashboard.
    Includes price, RSI, MACD, moving averages, volume, earnings date,
    and analyst ratings — all via yfinance.
    """
    try:
        import pandas as pd
        t = yf.Ticker(ticker)

        df = t.history(period="1y", interval="1d", auto_adjust=True)
        if df.empty:
            return _stub_focus_quote(ticker)

        close  = df["Close"]
        volume = df["Volume"]
        latest_close = round(float(close.iloc[-1]), 2)
        latest_vol   = int(volume.iloc[-1])
        avg_vol_20   = int(volume.rolling(20).mean().iloc[-1])
        rel_vol      = round(latest_vol / avg_vol_20, 2) if avg_vol_20 else 1.0

        # RSI (14)
        delta = close.diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rs    = gain / loss
        rsi   = round(float(100 - (100 / (1 + rs.iloc[-1]))), 1)

        # MACD (12, 26, 9)
        ema12       = close.ewm(span=12, adjust=False).mean()
        ema26       = close.ewm(span=26, adjust=False).mean()
        macd_line   = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram   = macd_line - signal_line
        hist_val    = round(float(histogram.iloc[-1]), 3)
        macd_str    = "bullish crossover" if hist_val > 0 else "bearish crossover"

        # Moving averages
        ma50  = round(float(close.rolling(50).mean().iloc[-1]), 2)
        ma200 = round(float(close.rolling(200).mean().iloc[-1]), 2)
        ma_cross = "above 200d" if latest_close > ma200 else "below 200d"

        # Info
        info        = t.info or {}
        short_pct   = info.get("shortPercentOfFloat", 0)
        short_str   = f"{round(short_pct * 100, 1)}%" if short_pct else "N/A"
        analyst_rec = info.get("recommendationKey", "N/A").replace("_", " ").title()
        target_price = info.get("targetMeanPrice")

        # Earnings date
        try:
            cal = t.calendar
            if cal is not None and not cal.empty:
                earn_col  = cal.columns[0] if len(cal.columns) > 0 else None
                earn_date = cal.iloc[0][earn_col] if earn_col else None
                if earn_date:
                    days_to = (pd.Timestamp(earn_date).date() - date.today()).days
                    earn_str = f"~{days_to} days"
                else:
                    earn_str = "N/A"
            else:
                earn_str = "N/A"
        except Exception:
            earn_str = "N/A"

        return {
            "ticker":        ticker,
            "price":         latest_close,
            "rsi":           str(rsi),
            "macd":          macd_str,
            "ma_cross":      ma_cross,
            "ma50":          ma50,
            "ma200":         ma200,
            "rel_vol":       f"{rel_vol}x avg",
            "volume":        latest_vol,
            "short_interest": short_str,
            "analyst":       analyst_rec,
            "target_price":  target_price,
            "earnings_days": earn_str,
        }

    except Exception as exc:
        log.warning("fetch_focus_quote failed for %s: %s", ticker, exc)
        return _stub_focus_quote(ticker)


def _stub_focus_quote(ticker: str) -> Dict[str, Any]:
    return {
        "ticker":        ticker,
        "price":         0.0,
        "rsi":           "N/A",
        "macd":          "N/A",
        "ma_cross":      "N/A",
        "ma50":          0.0,
        "ma200":         0.0,
        "rel_vol":       "N/A",
        "volume":        0,
        "short_interest": "N/A",
        "analyst":       "N/A",
        "target_price":  None,
        "earnings_days": "N/A",
    }
