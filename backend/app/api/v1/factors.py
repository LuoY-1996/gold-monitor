"""Factor analysis API endpoints."""

from datetime import date
from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.api.deps import DBSession
from app.services import factor_service
from app.data.orchestrator import fetch_historical_treasury
from app.data.vix_fetcher import VixHistoryFetcher
from app.data.oil_fetcher import OilHistoryFetcher

router = APIRouter(prefix="/factors", tags=["Factors"])


class FactorDataResponse(BaseModel):
    factor_type: str
    count: int
    data: list[dict]


class CorrelationResponse(BaseModel):
    factors: list[str]
    correlations: list[dict]


@router.get("/{factor_type}")
async def get_factor_data(
    factor_type: str,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    limit: int = Query(365),
    session: AsyncSession = DBSession,
):
    """Get historical data for a specific factor.

    factor_type: vix, usd_cny, dxy, treasury_10y, cpi, oil
    """
    try:
        data = await factor_service.get_factor_history(session, factor_type, start_date, end_date, limit)
        return FactorDataResponse(factor_type=factor_type, count=len(data), data=data)
    except ValueError as e:
        return {"status": "error", "message": str(e), "data": []}
    except Exception as e:
        return {"status": "error", "error_type": type(e).__name__, "message": str(e), "data": []}


@router.post("/load-history")
async def load_factor_history(session: AsyncSession = DBSession):
    """Load full US Treasury 10Y historical data (~9000 records)."""
    result = await fetch_historical_treasury(session)
    return {"status": "completed", "result": result}


@router.post("/load-vix-history")
async def load_vix_history(session: AsyncSession = DBSession):
    """Load full VIX historical data from CBOE (~9000 records from 1990)."""
    fetcher = VixHistoryFetcher()
    df = await fetcher.fetch()
    if df.empty:
        return {"status": "failed", "message": "No data from CBOE"}
    count = await fetcher.save_to_db(df, session)
    date_range = f"{df.iloc[0]['date']} → {df.iloc[-1]['date']}"
    return {"status": "completed", "records": count, "date_range": date_range}


@router.post("/load-oil-history")
async def load_oil_history(session: AsyncSession = DBSession):
    """Load full Brent crude oil historical data from Sina futures (~2500 records)."""
    fetcher = OilHistoryFetcher()
    df = await fetcher.fetch()
    if df.empty:
        return {"status": "failed", "message": "No data from Sina futures"}
    count = await fetcher.save_to_db(df, session)
    date_range = f"{df.iloc[0]['date']} → {df.iloc[-1]['date']}"
    return {"status": "completed", "records": count, "date_range": date_range}


@router.get("/correlation/{gold_type}")
async def get_correlation(
    gold_type: str,
    days: int = Query(365),
    session: AsyncSession = DBSession,
):
    """Compute correlation matrix between gold price and all factors."""
    try:
        result = await factor_service.compute_correlation(session, gold_type, days)
        return result
    except ValueError as e:
        return {"status": "error", "message": str(e)}
