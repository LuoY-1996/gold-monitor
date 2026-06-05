"""FastAPI application entry point."""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.config import CORS_ORIGINS, HOST, PORT, FETCH_INTERVAL_MINUTES, BASE_DIR, IS_SQLITE
from app.database import init_db, async_session


async def fetch_realtime_prices(interval_seconds: int = 3600):
    """Background task: fetch only gold prices every hour."""
    from app.data.orchestrator import fetch_realtime_prices as _fetch_prices

    await asyncio.sleep(10)

    while True:
        try:
            async with async_session() as session:
                results = await _fetch_prices(session)
                xau = results.get("xau_usd", {})
                au = results.get("au9999", {})
                print(f"[realtime] XAU: {xau.get('status')}, AU: {au.get('status')}")
        except Exception as e:
            print(f"[realtime] Error: {e}")

        await asyncio.sleep(interval_seconds)


async def fetch_daily_update():
    """Background task: fetch all factors + retrain model at 8:00 AM Beijing (00:00 UTC)."""
    from app.data.orchestrator import fetch_all_data
    from app.ml.model_trainer import train_model

    now = datetime.utcnow()
    target = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    delay = (target - now).total_seconds()
    print(f"[daily] First daily update in {delay/3600:.1f}h (next 8AM Beijing)")

    await asyncio.sleep(delay)

    while True:
        try:
            print(f"[daily] Starting daily update...")
            async with async_session() as session:
                results = await fetch_all_data(session)
                ok = sum(1 for r in results.values() if r.get("status") == "success")
                print(f"[daily] Factors: {ok}/{len(results)} sources updated")
                train_result = await train_model(session, "xau_usd", 730)
                acc = train_result.get("direction_accuracy", 0)
                print(f"[daily] Model retrained, accuracy: {acc:.1%}")
        except Exception as e:
            print(f"[daily] Error: {e}")

        await asyncio.sleep(24 * 3600)


async def _run_fetcher(fetcher, session) -> dict:
    try:
        df = await fetcher.fetch()
        if df is not None and not df.empty:
            count = await fetcher.save_to_db(df, session)
            return {"status": "success", "records": count}
        return {"status": "empty", "records": 0}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


async def _seed_historical_data(session):
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
    await init_db()
    db_type = "PostgreSQL" if not IS_SQLITE else "SQLite"
    print(f"[startup] Database: {db_type}")

    if not IS_SQLITE:
        try:
            async with async_session() as session:
                from app.models.gold_price import GoldPriceAu9999
                from sqlalchemy import select, func
                result = await session.execute(select(func.count()).select_from(GoldPriceAu9999))
                count = result.scalar()
                if count == 0:
                    print("[startup] Fresh PostgreSQL detected -- loading historical data...")
                    await _seed_historical_data(session)
                else:
                    print(f"[startup] PostgreSQL already has data ({count} Au99.99 records), skipping seed")
        except Exception as e:
            print(f"[startup] Seed check failed (non-fatal): {e}")

        from app.services.seed_missing import seed_missing_data_sources
        try:
            async with async_session() as session:
                await seed_missing_data_sources(session)
        except Exception as e:
            print(f"[startup] Missing-data seed failed (non-fatal): {e}")

    # --- Background tasks ---
    realtime_task = asyncio.create_task(fetch_realtime_prices(FETCH_INTERVAL_MINUTES * 60))
    daily_task = asyncio.create_task(fetch_daily_update())
    print(f"[startup] Realtime: every {FETCH_INTERVAL_MINUTES} min")
    print(f"[startup] Daily: 8:00 AM Beijing (00:00 UTC)")

    yield

    realtime_task.cancel()
    daily_task.cancel()
    try:
        await realtime_task
    except asyncio.CancelledError:
        pass
    try:
        await daily_task
    except asyncio.CancelledError:
        pass
    print("[shutdown] Application stopped")


app = FastAPI(
    title="Gold Monitor",
    description="金价监控与预测系统",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.v1.router import api_router
app.include_router(api_router, prefix="/api/v1")

STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    from starlette.staticfiles import StaticFiles
    if (STATIC_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path and (STATIC_DIR / full_path).exists() and (STATIC_DIR / full_path).is_file():
            return FileResponse(str(STATIC_DIR / full_path))
        return FileResponse(str(STATIC_DIR / "index.html"))

    @app.get("/")
    async def serve_root_spa():
        return FileResponse(str(STATIC_DIR / "index.html"))
else:
    @app.get("/")
    async def root():
        return {"status": "ok", "service": "Gold Monitor API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
