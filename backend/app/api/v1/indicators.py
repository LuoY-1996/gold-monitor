"""Technical indicators API endpoints."""

from datetime import date
from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DBSession
from app.services import indicator_service

router = APIRouter(prefix="/indicators", tags=["Indicators"])


@router.get("/{gold_type}")
async def get_indicators(
    gold_type: str,
    days: int = Query(365, description="Days of history to analyze"),
    session: AsyncSession = DBSession,
):
    """Get all technical indicators for a gold type.

    Returns MA(5,10,20,60,200), MACD, RSI(14), Bollinger Bands, ATR(14).
    """
    try:
        df = await indicator_service.get_price_df(session, gold_type, days)
        if df.empty:
            return {"status": "empty", "message": f"暂无{gold_type}的历史数据", "data": []}

        data = indicator_service.compute_all_indicators(df)
        return {
            "status": "ok",
            "gold_type": gold_type,
            "count": len(data),
            "data": data,
        }
    except ValueError as e:
        return {"status": "error", "message": str(e), "data": []}


@router.get("/{gold_type}/signals")
async def get_trend_signals(
    gold_type: str,
    days: int = Query(365, description="Days of history to analyze"),
    session: AsyncSession = DBSession,
):
    """Get trend signals based on technical indicators."""
    try:
        df = await indicator_service.get_price_df(session, gold_type, days)
        if df.empty:
            return {"status": "insufficient_data", "message": "数据不足"}

        signals = indicator_service.compute_trend_signals(df)
        return signals
    except ValueError as e:
        return {"status": "error", "message": str(e)}
