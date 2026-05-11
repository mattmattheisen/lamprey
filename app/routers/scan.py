"""
routers/scan.py — API endpoints for the meme stock scanner.
"""
from __future__ import annotations
import logging
from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.models.signals import ScanResult
from app.services.scanner import run_scan
from app.state import get_latest_result, set_latest_result

log = logging.getLogger("lamprey")
router = APIRouter(prefix="/api")
settings = get_settings()


@router.get("/scan", response_model=ScanResult, summary="Trigger a full scan")
async def scan_now(
    tickers: Optional[str] = Query(
        default=None,
        description="Comma-separated tickers to scan. Defaults to watchlist.",
    )
):
    ticker_list = (
        [t.strip().upper() for t in tickers.split(",") if t.strip()]
        if tickers
        else None
    )
    result = await run_scan(ticker_list)
    set_latest_result(result)
    return result


@router.get("/latest", response_model=ScanResult, summary="Return last cached scan")
async def latest():
    result = get_latest_result()
    if result is None:
        return JSONResponse(status_code=404, content={"detail": "No scan results yet."})
    return result


@router.get("/watchlist", summary="Return current watchlist")
async def watchlist():
    return {"watchlist": settings.watchlist}
