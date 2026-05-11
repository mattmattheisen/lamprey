"""
config.py — App settings via environment variables.
Tiingo removed — yfinance requires no API key.
"""
from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Watchlist for the meme stock scanner
    watchlist: list[str] = [
        "GME", "AMC", "BBBY", "MVIS", "CLOV",
        "WISH", "SOFI", "PLTR", "RIVN", "LCID",
    ]

    # Signal thresholds
    long_composite_threshold: float  = 0.65
    short_composite_threshold: float = 0.60

    # VIX regime gate
    vix_high_threshold: float = 25.0
    vix_low_threshold:  float = 15.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
