"""FastAPI application entry point."""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import FileResponse

from app.config import CORS_ORIGINS, HOST, PORT, FETCH_INTERVAL_MINUTES, BASE_DIR, IS_SQLITE
from app.database import init_db, async_session


async def periodic_fetch(interval_seconds: int = 300):
    """Background task: periodically fetch latest gold prices."""
    from app.data.orchestrator import fetch_all_data

    # Wait a bit for the server to fully start
    await asyncio.sleep(5)

    while True:
        try:
            async with async_session() as session:
                results = await fetch_all_data(session)
                # Log summary
                xau = results.get("xau_usd", {})
                au = results.get("au9999", {})
                print(f"[auto-fetch] XAU: {xau.get('status')}, AU: {au.get('status')}")
        except Exception as e:
            print(f"[auto-fetch] Error: {e}")

        await asyncio.sleep(interval_seconds)


async def _run_fetcher(fetcher, session) -> dict:
    """Run a single fetcher: fetch + save, return result summary."""
    try:
        df = await fetcher.fetch()
        if df is not None and not df.empty:
            count = await fetcher.save_to_db(df, session)
            return {"status": "success", "records": count}
        return {"status": "empty", "records": 0}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


async def _seed_historical_data(session):
    """Load historical data on fresh PostgreSQL deployment."""
    from app.data.orchestrator import (
        fetch_historical_au9999,
        fetch_historical_forex,
        fetch_historical_treasury,
    )
    from app.data.fed_funds_fetcher import FedFundsFetcher
    from app.data.gold_etf_fetcher import GoldEtfFetcher
    from app.data.tips_fetcher import TipsBreakevenFetcher

    tasks = [
        ("Au99.99 历史数据", fetch_historical_au9999(session)),
        ("USD/CNY 历史数据", fetch_historical_forex(session)),
        ("美债10Y 历史数据", fetch_historical_treasury(session)),
        ("联邦基金利率 历史数据", _run_fetcher(FedFundsFetcher(), session)),
        ("黄金ETF持仓 历史数据", _run_fetcher(GoldEtfFetcher(), session)),
        ("盈亏平衡通胀率 历史数据", _run_fetcher(TipsBreakevenFetcher(), session)),
    ]

    for label, task in tasks:
        try:
            result = await task
            print(f"  [seed] {label}: {result.get('status')} ({result.get('records', 0)} 条)")
        except Exception as e:
            print(f"  [seed] {label} 失败: {e}")

    print("[startup] Historical data seeding complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    # Startup: create tables
    await init_db()

    # Log which database is connected
    db_type = "PostgreSQL" if not IS_SQLITE else "SQLite"
    print(f"[startup] Database: {db_type}")

    if IS_SQLITE:
        print("[startup] WARNING: Using SQLite on Railway — no PostgreSQL DATABASE_URL set!")
    else:
        print("[startup] PostgreSQL connected — data persisted")

    # If PostgreSQL and database is fresh, auto-seed historical data
    if not IS_SQLITE:
        try:
            async with async_session() as session:
                from app.models.gold_price import GoldPriceAu9999
                from sqlalchemy import select, func
                result = await session.execute(select(func.count()).select_from(GoldPriceAu9999))
                count = result.scalar()
                if count == 0:
                    print("[startup] Fresh PostgreSQL detected — loading historical data...")
                    await _seed_historical_data(session)
                else:
                    print(f"[startup] PostgreSQL already has data ({count} Au99.99 records), skipping seed")
        except Exception as e:
            print(f"[startup] Seed check failed (non-fatal): {e}")

        # Auto-seed empty data sources (gold_etf, breakeven_inflation, etc.)
        from app.services.seed_missing import seed_missing_data_sources
        try:
            async with async_session() as session:
                await seed_missing_data_sources(session)
        except Exception as e:
            print(f"[startup] Missing-data seed failed (non-fatal): {e}")

    # Start background periodic fetch task
    interval_seconds = FETCH_INTERVAL_MINUTES * 60
    fetch_task = asyncio.create_task(periodic_fetch(interval_seconds))
    print(f"[startup] Background auto-fetch started (every {FETCH_INTERVAL_MINUTES} min)")

    yield

    # Shutdown: cancel background task
    fetch_task.cancel()
    try:
        await fetch_task
    except asyncio.CancelledError:
        pass
    print("[shutdown] Application stopped")


app = FastAPI(
    title="Gold Monitor",
    description="金价监控与预测系统",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Import and register API routers
from app.api.v1.router import api_router
app.include_router(api_router, prefix="/api/v1")


# ── Serve React frontend in production (SPA-aware) ──
STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    class _SPAStaticFiles(StaticFiles):
        """Serve static files; for unmatched paths, serve index.html (SPA fallback)."""
        async def get_response(self, path: str, scope):
            try:
                return await super().get_response(path, scope)
            except StarletteHTTPException as ex:
                if ex.status_code == 404:
                    return FileResponse(self.directory / "index.html")
                raise

    app.mount("/", _SPAStaticFiles(directory=str(STATIC_DIR), html=True), name="static")
else:
    @app.get("/")
    async def root():
        return {"status": "ok", "service": "Gold Monitor API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
