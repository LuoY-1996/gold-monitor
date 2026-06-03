"""Gold price API endpoints."""

from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DBSession
from app.services import gold_service
from app.schemas.gold import (
    GoldPriceResponse,
    GoldRealtimeResponse,
    GoldCompareResponse,
)
from app.data.orchestrator import fetch_all_data, fetch_historical_au9999

router = APIRouter(prefix="/gold", tags=["Gold Prices"])


@router.get("/xau-usd/realtime", response_model=GoldRealtimeResponse)
async def get_xau_usd_realtime(session: AsyncSession = DBSession):
    """Get latest XAU/USD spot price."""
    result = await gold_service.get_realtime(session, "xau_usd")
    if result is None:
        return GoldRealtimeResponse(
            gold_type="xau_usd",
            available=False,
        )
    return GoldRealtimeResponse(**result)


@router.get("/xau-usd/history", response_model=GoldPriceResponse)
async def get_xau_usd_history(
    start_date: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(365, description="Max records if no date range specified"),
    session: AsyncSession = DBSession,
):
    """Get historical XAU/USD OHLCV data."""
    data = await gold_service.get_history(session, "xau_usd", start_date, end_date, limit)
    return GoldPriceResponse(gold_type="xau_usd", count=len(data), data=data)


@router.get("/au9999/realtime", response_model=GoldRealtimeResponse)
async def get_au9999_realtime(session: AsyncSession = DBSession):
    """Get latest Shanghai Gold Au99.99 price."""
    result = await gold_service.get_realtime(session, "au9999")
    if result is None:
        return GoldRealtimeResponse(
            gold_type="au9999",
            available=False,
        )
    return GoldRealtimeResponse(**result)


@router.get("/au9999/history", response_model=GoldPriceResponse)
async def get_au9999_history(
    start_date: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(365, description="Max records if no date range specified"),
    session: AsyncSession = DBSession,
):
    """Get historical Au99.99 price data."""
    data = await gold_service.get_history(session, "au9999", start_date, end_date, limit)
    return GoldPriceResponse(gold_type="au9999", count=len(data), data=data)


@router.get("/compare", response_model=list[GoldCompareResponse])
async def compare_gold(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    limit: int = Query(365),
    session: AsyncSession = DBSession,
):
    """Get XAU/USD and Au99.99 prices side-by-side."""
    data = await gold_service.get_compare(session, start_date, end_date, limit)
    return [GoldCompareResponse(**d) for d in data]


@router.post("/fetch")
async def trigger_fetch(session: AsyncSession = DBSession):
    """Manually trigger data fetching from all sources."""
    results = await fetch_all_data(session)
    return {"status": "completed", "results": results}


@router.post("/load-history")
async def load_history(session: AsyncSession = DBSession):
    """Load full historical Au99.99 data from SGE (one-time, ~2000+ records)."""
    result = await fetch_historical_au9999(session)
    return {"status": "completed", "result": result}
