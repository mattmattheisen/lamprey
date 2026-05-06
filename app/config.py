from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── API keys ───────────────────────────────────────────────────────────────
    tiingo_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "lamprey/0.1"
    unusual_whales_api_key: str = ""
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

    # ── Feature flags (derived from key presence) ─────────────────────────────
    @property
    def tiingo_live(self) -> bool:
        return bool(self.tiingo_api_key)

    @property
    def reddit_live(self) -> bool:
        return bool(self.reddit_client_id and self.reddit_client_secret)

    @property
    def unusual_whales_live(self) -> bool:
        return bool(self.unusual_whales_api_key)

    @property
    def newsapi_live(self) -> bool:
        return bool(self.newsapi_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
