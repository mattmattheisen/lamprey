"""
state.py — Simple in-process cache for the latest ScanResult.
APScheduler and the /api/scan endpoint both write here.
/api/latest reads from here without re-running a scan.
"""
from __future__ import annotations

from typing import Optional

from app.models.signals import ScanResult

_latest: Optional[ScanResult] = None


def get_latest_result() -> Optional[ScanResult]:
    return _latest


def set_latest_result(result: ScanResult) -> None:
    global _latest
    _latest = result
