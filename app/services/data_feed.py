"""
data_feed.py — All external fetches (live + stubbed).

Live vs stub is controlled by whether the relevant API key is set in Settings.
Stubs return neutral dicts (zeros / safe defaults) and never raise exceptions.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

from app.config import get_settings

log = logging.getLogger("lamprey")
settings = get_settings()


# ── Tiingo OHLCV ──────────────────────────────────────────────────────────────

async def fetch_ohlcv(ticker: str, lookback_days: int = 30) -> List[Dict[str, Any]]:
    """Return list of daily OHLCV dicts for *ticker*.  Live if TIINGO_API_KEY set."""
    if not settings.tiingo_live:
        log.debug("fetch_ohlcv: STUBBED for %s", ticker)
        return _stub_ohlcv(ticker, lookback_days)

    from datetime import date, timedelta
    start_date = (date.today() - timedelta(days=lookback_days)).isoformat()
    url = f"https://api.tiingo.com/tiingo/daily/{ticker}/prices"
    params = {
        "token": settings.tiingo_api_key,
        "resampleFreq": "daily",
        "startDate": start_date,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            return r.json()
    except Exception as exc:
        log.warning("fetch_ohlcv live failed for %s: %s — falling back to stub", ticker, exc)
        return _stub_ohlcv(ticker, lookback_days)


def _stub_ohlcv(ticker: str, days: int) -> List[Dict[str, Any]]:
    import random
    from datetime import date, timedelta

    rows = []
    price = 10.0
    for i in range(days):
        d = date.today() - timedelta(days=days - i)
        price = max(1.0, price + random.uniform(-0.5, 0.5))
        rows.append({
            "date": str(d),
            "open": round(price, 4),
            "high": round(price * 1.02, 4),
            "low": round(price * 0.98, 4),
            "close": round(price, 4),
            "volume": int(random.uniform(500_000, 5_000_000)),
        })
    return rows


# ── VIX (via Tiingo) ─────────────────────────────────────────────────────────

async def fetch_vix_level() -> float:
    """Return latest VIX close directly from Tiingo.  Live if TIINGO_API_KEY set."""
    if not settings.tiingo_live:
        log.debug("fetch_vix_level: STUBBED")
        return 18.0

    from datetime import date, timedelta
    start_date = (date.today() - timedelta(days=7)).isoformat()
    url = "https://api.tiingo.com/tiingo/daily/%5EVIX/prices"
    params = {
        "token": settings.tiingo_api_key,
        "resampleFreq": "daily",
        "startDate": start_date,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            rows = r.json()
        if rows:
            return float(rows[-1].get("close", 18.0))
    except Exception as exc:
        log.warning("fetch_vix_level failed: %s — returning default 18.0", exc)
    return 18.0


# ── Reddit sentiment (public scraper — no API key required) ──────────────────

async def fetch_reddit_sentiment(ticker: str) -> Dict[str, Any]:
    """Scrape public WSB search results via old.reddit.com JSON — no API key needed.

    Uses old.reddit.com/r/wallstreetbets/search.json which is publicly readable.
    Runs post titles through vaderSentiment to produce compound score.
    Falls back to neutral on any error so the scanner never crashes.
    """
    url = "https://old.reddit.com/r/wallstreetbets/search.json"
    params = {
        "q": ticker,
        "sort": "new",
        "t": "day",
        "limit": 25,
        "restrict_sr": "on",
    }
    headers = {
        # Reddit requires a real User-Agent or returns 429
        "User-Agent": "lamprey/0.1 (stock sentiment scanner; non-commercial)",
    }
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            r = await client.get(url, params=params, headers=headers)
            r.raise_for_status()
            data = r.json()

        posts = data.get("data", {}).get("children", [])
        texts = [
            p["data"].get("title", "") + " " + p["data"].get("selftext", "")
            for p in posts
            if p.get("data")
        ]

        if not texts:
            log.debug("fetch_reddit_sentiment: no posts found for %s", ticker)
            return {"mention_count": 0, "vader_compound": 0.0, "velocity": 0.0}

        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore
        analyzer = SentimentIntensityAnalyzer()
        compounds = [analyzer.polarity_scores(t)["compound"] for t in texts]
        compound = round(sum(compounds) / len(compounds), 4)
        mention_count = len(texts)
        velocity = round(min(mention_count / 25.0, 1.0), 4)

        log.info("fetch_reddit_sentiment: %s — %d posts, compound=%.4f", ticker, mention_count, compound)
        return {
            "mention_count": mention_count,
            "vader_compound": compound,
            "velocity": velocity,
        }
    except Exception as exc:
        log.warning("fetch_reddit_sentiment failed for %s: %s", ticker, exc)
        return {"mention_count": 0, "vader_compound": 0.0, "velocity": 0.0}


# ── Unusual Whales flow ───────────────────────────────────────────────────────

async def fetch_unusual_whales(ticker: str) -> Dict[str, Any]:
    """Return borrow/short data from Unusual Whales.  Stubbed until key is set."""
    if not settings.unusual_whales_live:
        log.debug("fetch_unusual_whales: STUBBED for %s", ticker)
        return {
            "borrow_status": "available",
            "borrow_rate_pct": 2.0,
            "short_interest_pct": 10.0,
        }

    url = f"https://phx.unusualwhales.com/api/stock/{ticker}/short-interest"
    headers = {"Authorization": f"Bearer {settings.unusual_whales_api_key}"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
            return {
                "borrow_status": data.get("borrow_status", "available"),
                "borrow_rate_pct": float(data.get("borrow_rate", 2.0)),
                "short_interest_pct": float(data.get("short_interest_percent", 10.0)),
            }
    except Exception as exc:
        log.warning("fetch_unusual_whales failed for %s: %s", ticker, exc)
        return {"borrow_status": "available", "borrow_rate_pct": 2.0, "short_interest_pct": 10.0}


# ── NewsAPI ───────────────────────────────────────────────────────────────────

async def fetch_news_catalyst(ticker: str) -> Dict[str, Any]:
    """Return NLP headline score 0-1.  Stubbed until NEWSAPI_KEY is set."""
    if not settings.newsapi_live:
        log.debug("fetch_news_catalyst: STUBBED for %s", ticker)
        return {"headline_score": 0.0, "article_count": 0}

    url = "https://newsapi.org/v2/everything"
    params = {
        "q": ticker,
        "language": "en",
        "pageSize": 10,
        "apiKey": settings.newsapi_key,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            articles = r.json().get("articles", [])
        if not articles:
            return {"headline_score": 0.0, "article_count": 0}
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore
        analyzer = SentimentIntensityAnalyzer()
        scores = [analyzer.polarity_scores(a.get("title", ""))["compound"] for a in articles]
        avg = sum(scores) / len(scores)
        normalized = round((avg + 1) / 2, 4)
        return {"headline_score": normalized, "article_count": len(articles)}
    except Exception as exc:
        log.warning("fetch_news_catalyst failed for %s: %s", ticker, exc)
        return {"headline_score": 0.0, "article_count": 0}
