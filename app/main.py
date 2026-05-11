"""
main.py — FastAPI entry point + APScheduler lifespan.
Scheduler: Mon–Fri, 09:00–15:59 ET, every 15 minutes.
Manual trigger: GET /api/scan or the UI "scan now" button.
"""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.config import get_settings
from app.routers.scan import router as scan_router
from app.routers.focustrade import router as focustrade_router
from app.services.scanner import run_scan
from app.state import set_latest_result

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("lamprey")
settings = get_settings()
scheduler = AsyncIOScheduler(timezone="America/New_York")


async def _scheduled_scan() -> None:
    log.info("Scheduled scan triggered")
    result = await run_scan()
    set_latest_result(result)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        _scheduled_scan,
        CronTrigger(
            day_of_week="mon-fri",
            hour="9-15",
            minute="*/15",
            timezone="America/New_York",
        ),
        id="lamprey_scan",
        replace_existing=True,
    )
    scheduler.start()
    log.info("APScheduler started — scanning Mon-Fri 09:00-15:59 ET every 15 min")

    try:
        result = await run_scan()
        set_latest_result(result)
        log.info("Startup scan complete")
    except Exception as exc:
        log.warning("Startup scan failed: %s", exc)

    yield

    scheduler.shutdown(wait=False)
    log.info("APScheduler shut down")


app = FastAPI(
    title="Lamprey — Meme Stock Momentum Scanner",
    description="Long/short composite signals with regime gating. Built by Shomer Analytics.",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(scan_router)
app.include_router(focustrade_router)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
