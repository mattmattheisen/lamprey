"""
config.py — App settings via environment variables.
yfinance requires no API key. NewsAPI optional for news scoring.
"""
from __future__ import annotations
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ── Optional API keys ──────────────────────────────────────────────────────
    newsapi_key: str = ""

    # ── Short gate thresholds ──────────────────────────────────────────────────
    max_borrow_rate_pct: float = 10.0
    max_short_interest_pct: float = 30.0

    # ── Signal thresholds ─────────────────────────────────────────────────────
    long_composite_threshold: float = 0.65
    short_composite_threshold: float = 0.75

    # ── Watchlist ─────────────────────────────────────────────────────────────
    default_watchlist: str = "GME,AMC,BBBY,SPCE,MVIS,CLOV,WKHS,RIDE,NKLA,KOSS"

    @property
    def watchlist(self) -> List[str]:
        return [t.strip().upper() for t in self.default_watchlist.split(",") if t.strip()]

    @property
    def newsapi_live(self) -> bool:
        return bool(self.newsapi_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
