"""
data_feed.py — All external fetches using yfinance (free, no API key needed).

yfinance pulls real-time and historical data directly from Yahoo Finance.
Reddit sentiment remains stubbed (neutral) until a live source is wired in.
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
            log.warning("fetch_ohlcv: no data returned for %s", ticker)
            return _stub_ohlcv(ticker, lookback_days)
        rows = []
        for dt, row in df.iterrows():
            rows.append({
                "date": str(dt.date()),
                "open":   round(float(row["Open"]),   4),
                "high":   round(float(row["High"]),   4),
                "low":    round(float(row["Low"]),    4),
                "close":  round(float(row["Close"]),  4),
                "volume": int(row["Volume"]),
            })
        return rows
    except Exception as exc:
        log.warning("fetch_ohlcv failed for %s: %s — using stub", ticker, exc)
        return _stub_ohlcv(ticker, lookback_days)


def _stub_ohlcv(ticker: str, days: int) -> List[Dict[str, Any]]:
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
    """Return latest VIX close via Yahoo Finance (^VIX)."""
    try:
        vix = yf.Ticker("^VIX")
        df = vix.history(period="5d", interval="1d")
        if not df.empty:
            return round(float(df["Close"].iloc[-1]), 2)
    except Exception as exc:
        log.warning("fetch_vix_level failed: %s — defaulting to 18.0", exc)
    return 18.0


# ── Reddit sentiment (stubbed — neutral) ──────────────────────────────────────

async def fetch_reddit_sentiment(ticker: str) -> Dict[str, Any]:
    """
    Reddit/social sentiment stub — returns neutral values.
    Replace this block when a live sentiment source is available.
    """
    log.debug("fetch_reddit_sentiment: STUBBED for %s", ticker)
    return {"mention_count": 0, "vader_compound": 0.0, "velocity": 0.0}


# ── News catalyst via yfinance ────────────────────────────────────────────────

async def fetch_news_catalyst(ticker: str) -> Dict[str, Any]:
    """
    Fetch recent news headlines for *ticker* via yfinance and score sentiment.
    Returns headline_score in [0, 1] where 0.5 is neutral.
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
            title = item.get("title", "")
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
    """Unusual Whales stub — returns neutral short-gate values."""
    log.debug("fetch_unusual_whales: STUBBED for %s", ticker)
    return {
        "borrow_rate": 0.0,
        "locate_available": True,
        "short_squeeze_score": 0.0,
    }


# ── Focus trade: full quote for MU / NVDA ────────────────────────────────────

def fetch_focus_quote(ticker: str) -> Dict[str, Any]:
    """
    Return a rich quote dict for the focus trader dashboard.
    Includes price, RSI, MACD, moving averages, volume, earnings date,
    analyst ratings, and put/call ratio estimate.
    """
    try:
        import pandas as pd
        t = yf.Ticker(ticker)

        # Price history — 1 year for MA calculations
        df = t.history(period="1y", interval="1d", auto_adjust=True)
        if df.empty:
            return _stub_focus_quote(ticker)

        close = df["Close"]
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
        ema12  = close.ewm(span=12, adjust=False).mean()
        ema26  = close.ewm(span=26, adjust=False).mean()
        macd_line   = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram   = macd_line - signal_line
        macd_val    = round(float(macd_line.iloc[-1]), 3)
        hist_val    = round(float(histogram.iloc[-1]), 3)
        macd_str    = ("bullish crossover" if hist_val > 0 else "bearish crossover")

        # Moving averages
        ma50  = round(float(close.rolling(50).mean().iloc[-1]), 2)
        ma200 = round(float(close.rolling(200).mean().iloc[-1]), 2)
        ma_cross = "above 200d" if latest_close > ma200 else "below 200d"
        golden_cross = ma50 > ma200

        # Info fields
        info = t.info or {}
        short_pct   = info.get("shortPercentOfFloat", 0)
        short_str   = f"{round(short_pct * 100, 1)}%" if short_pct else "N/A"
        analyst_rec = info.get("recommendationKey", "N/A").replace("_", " ").title()
        target_price = info.get("targetMeanPrice")
        market_cap  = info.get("marketCap")

        # Earnings date
        try:
            cal = t.calendar
            if cal is not None and not cal.empty:
                earn_date = cal.iloc[0]["Earnings Date"] if "Earnings Date" in cal.columns else None
                if earn_date:
                    days_to_earn = (pd.Timestamp(earn_date).date() - date.today()).days
                    earn_str = f"~{days_to_earn} days"
                else:
                    earn_str = "N/A"
            else:
                earn_str = "N/A"
        except Exception:
            earn_str = "N/A"

        return {
            "ticker":       ticker,
            "price":        latest_close,
            "rsi":          rsi,
            "macd":         macd_str,
            "macd_value":   macd_val,
            "histogram":    hist_val,
            "ma50":         ma50,
            "ma200":        ma200,
            "ma_cross":     ma_cross,
            "golden_cross": golden_cross,
            "rel_vol":      f"{rel_vol}x avg",
            "volume":       latest_vol,
            "short_interest": short_str,
            "analyst":      analyst_rec,
            "target_price": target_price,
            "earnings_days": earn_str,
            "market_cap":   market_cap,
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
        "macd_value":    0.0,
        "histogram":     0.0,
        "ma50":          0.0,
        "ma200":         0.0,
        "ma_cross":      "N/A",
        "golden_cross":  False,
        "rel_vol":       "N/A",
        "volume":        0,
        "short_interest": "N/A",
        "analyst":       "N/A",
        "target_price":  None,
        "earnings_days": "N/A",
        "market_cap":    None,
    }
