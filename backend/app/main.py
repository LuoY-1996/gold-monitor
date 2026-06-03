"""FastAPI application entry point."""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from app.config import CORS_ORIGINS, HOST, PORT, FETCH_INTERVAL_MINUTES, BASE_DIR
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    # Startup: create tables
    await init_db()
    print("[startup] Database tables created")

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


@app.get("/")
async def root():
    """Health check."""
    return {"status": "ok", "service": "Gold Monitor API"}


# Import and register API routers
from app.api.v1.router import api_router
app.include_router(api_router, prefix="/api/v1")


# ── Serve React frontend (production only) ──
STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    # Serve static assets (JS, CSS, images)
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
    # Serve public files (logo, favicon, etc.)
    for f in STATIC_DIR.glob("*"):
        if f.is_file() and f.suffix != ".html":
            fname = f.name
            app.mount(f"/{fname}", StaticFiles(directory=str(STATIC_DIR), html=False), name=fname)

    # SPA fallback — all non-API routes return index.html
    @app.get("/{path:path}")
    async def spa_fallback(path: str):
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"message": "Frontend not built"}

    @app.get("/")
    async def root_spa():
        return FileResponse(str(STATIC_DIR / "index.html"))
else:
    @app.get("/")
    async def root():
        return {"status": "ok", "service": "Gold Monitor API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
