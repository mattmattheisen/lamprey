"""
routers/scan.py — API endpoints.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
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
) -> ScanResult:
    ticker_list: Optional[List[str]] = None
    if tickers:
        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    result = await run_scan(ticker_list)
    set_latest_result(result)
    return result


@router.get("/latest", response_model=ScanResult, summary="Return last cached scan")
async def latest_scan() -> ScanResult:
    result = get_latest_result()
    if result is None:
        raise HTTPException(status_code=404, detail="No scan has been run yet.")
    return result


@router.get("/watchlist", summary="Return configured watchlist")
async def get_watchlist() -> JSONResponse:
    return JSONResponse({"watchlist": settings.watchlist})
