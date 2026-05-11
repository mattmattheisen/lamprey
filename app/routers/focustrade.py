"""
focustrade.py — /api/focustrade endpoint.
Returns live technical data for MU and NVDA (or any tickers passed in).
Powers the Focus Trader dashboard.
"""
from __future__ import annotations
import logging
from typing import List
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from app.services.data_feed import fetch_focus_quote

log = logging.getLogger("lamprey")
router = APIRouter()


@router.get("/api/focustrade")
async def focus_trade(
    tickers: List[str] = Query(default=["MU", "NVDA"])
):
    """
    Return live quote data for focus tickers.
    GET /api/focustrade
    GET /api/focustrade?tickers=MU&tickers=NVDA
    GET /api/focustrade?tickers=AMD
    """
    results = []
    for ticker in tickers:
        ticker = ticker.upper().strip()
        try:
            quote = await asyncio.to_thread(fetch_focus_quote, ticker)
            results.append(quote)
            log.info("focustrade: %s @ $%s", ticker, quote.get("price"))
        except Exception as exc:
            log.warning("focustrade: failed for %s — %s", ticker, exc)
            results.append({"ticker": ticker, "error": str(exc)})
    return JSONResponse(content={"tickers": results})


import asyncio  # noqa: E402 — imported here to keep top clean
