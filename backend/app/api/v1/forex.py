"""Forex / exchange rate API endpoints."""

from datetime import date
from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.api.deps import DBSession
from app.services import forex_service, gold_service
from app.data.orchestrator import fetch_historical_forex

router = APIRouter(prefix="/forex", tags=["Forex"])


class UsdCnyRealtimeResponse(BaseModel):
    available: bool = True
    trade_date: date | None = None
    close: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None

    class Config:
        from_attributes = True


class UsdCnyPoint(BaseModel):
    trade_date: date
    close: float
    open: float | None = None
    high: float | None = None
    low: float | None = None

    class Config:
        from_attributes = True


class UsdCnyHistoryResponse(BaseModel):
    count: int
    data: list[UsdCnyPoint]


class GoldPremiumResponse(BaseModel):
    xau_usd: float
    au9999: float
    usd_cny: float
    implied_rate: float | None = None  # 金价隐含汇率
    theoretical_au9999: float | None = None  # 理论国内金价
    premium_pct: float | None = None  # 溢价百分比


@router.get("/usd-cny/realtime", response_model=UsdCnyRealtimeResponse)
async def get_usd_cny_realtime(session: AsyncSession = DBSession):
    """Get latest USD/CNY exchange rate."""
    result = await forex_service.get_usd_cny_realtime(session)
    if result is None:
        return UsdCnyRealtimeResponse(available=False)
    return UsdCnyRealtimeResponse(**result)


@router.get("/usd-cny/history", response_model=UsdCnyHistoryResponse)
async def get_usd_cny_history(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    limit: int = Query(365),
    session: AsyncSession = DBSession,
):
    """Get USD/CNY historical data."""
    data = await forex_service.get_usd_cny_history(session, start_date, end_date, limit)
    return UsdCnyHistoryResponse(count=len(data), data=data)


@router.post("/load-history")
async def load_forex_history(session: AsyncSession = DBSession):
    """Load full historical USD/CNY data (one-time, ~4000 records from 2015)."""
    result = await fetch_historical_forex(session)
    return {"status": "completed", "result": result}


@router.get("/premium", response_model=GoldPremiumResponse)
async def get_gold_premium(session: AsyncSession = DBSession):
    """Calculate gold premium: domestic vs international with exchange rate."""
    # Get latest prices
    xau = await gold_service.get_realtime(session, "xau_usd")
    au = await gold_service.get_realtime(session, "au9999")
    cny = await forex_service.get_usd_cny_realtime(session)

    xau_close = xau["close"] if xau else 0
    au_close = au["close"] if au else 0
    usd_cny = cny["close"] if cny else 0

    # Calculate cross metrics
    cross = forex_service.calculate_cross_rate(xau_close, au_close)
    premium = forex_service.calculate_gold_premium(xau_close, au_close, usd_cny)

    return GoldPremiumResponse(
        xau_usd=xau_close,
        au9999=au_close,
        usd_cny=usd_cny,
        implied_rate=cross["implied_rate"],
        theoretical_au9999=premium["theoretical_au"],
        premium_pct=premium["premium_pct"],
    )
