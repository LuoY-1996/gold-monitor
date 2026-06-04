"""Geopolitical events and risk index API endpoints."""

from datetime import date
from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.api.deps import DBSession
from app.services import geo_service
from app.data.geopolitics_fetcher import GeopoliticalRiskFetcher

router = APIRouter(prefix="/geo", tags=["Geopolitics"])


class GeoEventResponse(BaseModel):
    id: int
    date: str
    title: str
    description: str | None = None
    impact: int
    direction: int
    category: str
    risk_regions: list[str] = []
    source_url: str | None = None

    class Config:
        from_attributes = True


class GeoRiskResponse(BaseModel):
    trade_date: str
    risk_score: float
    event_intensity: float
    active_conflicts: int
    news_sentiment: float | None = None
    news_headline_count: int | None = None
    regional_scores: dict | None = None


class SeedEventsRequest(BaseModel):
    events: list[dict]


class ComputeRiskResponse(BaseModel):
    status: str
    trade_date: str
    risk_score: float
    event_intensity: float
    active_conflicts: int
    news_sentiment: float | None = None
    news_headline_count: int | None = None


@router.get("/events", response_model=list[GeoEventResponse])
async def get_geo_events(
    months: int = Query(3, ge=1, le=24, description="Look back N months"),
    category: str | None = Query(None, description="Filter by category"),
    session: AsyncSession = DBSession,
):
    """Get geopolitical events within the specified time range.

    Categories: fed, geopolitics, economy, china, market
    """
    events = await geo_service.get_events(session, months=months, category=category)
    return [GeoEventResponse(**e) for e in events]


@router.get("/events-debug")
async def get_geo_events_debug(
    months: int = Query(3, ge=1, le=24),
    session: AsyncSession = DBSession,
):
    """Debug endpoint for geo events."""
    from sqlalchemy import text
    from datetime import date, timedelta
    cutoff = date.today() - timedelta(days=months * 30)
    results = {}
    try:
        r1 = await session.execute(text("SELECT COUNT(*) FROM geopolitical_events"))
        results["total"] = r1.scalar()
        r2 = await session.execute(text("SELECT COUNT(*) FROM geopolitical_events WHERE event_date >= :c"), {"c": cutoff})
        results["matching_cutoff"] = r2.scalar()
        r3 = await session.execute(text("SELECT MIN(event_date), MAX(event_date) FROM geopolitical_events"))
        min_d, max_d = r3.one()
        results["date_range"] = f"{min_d} -> {max_d}"
        r4 = await session.execute(text("SELECT COUNT(*) FROM geopolitical_events LIMIT 5"))
        results["sample_count"] = r4.scalar()
    except Exception as e:
        results["error"] = str(e)
    results["today"] = str(date.today())
    results["cutoff"] = str(cutoff)
    results["months"] = months
    return results


@router.get("/risk", response_model=list[GeoRiskResponse])
async def get_geo_risk(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    limit: int = Query(90, description="Default days if no date range"),
    session: AsyncSession = DBSession,
):
    """Get geopolitical risk index history."""
    data = await geo_service.get_risk_index(session, start_date, end_date, limit)
    return [GeoRiskResponse(**d) for d in data]


@router.get("/risk/latest", response_model=GeoRiskResponse | None)
async def get_latest_geo_risk(session: AsyncSession = DBSession):
    """Get the latest geopolitical risk score."""
    return await geo_service.get_latest_risk(session)


@router.post("/events/seed")
async def seed_geo_events(
    body: SeedEventsRequest,
    session: AsyncSession = DBSession,
):
    """Seed geopolitical events into the database.

    Accepts a list of event dicts. Skips duplicates by date+title.
    This endpoint is used to migrate events from the frontend hardcoded data.
    """
    count = await geo_service.seed_events(session, body.events)
    return {"status": "completed", "inserted": count, "total_sent": len(body.events)}


@router.post("/risk/compute")
async def compute_risk_now(session: AsyncSession = DBSession):
    """Compute and save today's geopolitical risk score.

    Loads recent events from DB, scrapes news headlines, computes aggregate score.
    """
    try:
        fetcher = GeopoliticalRiskFetcher()
        df = await fetcher.fetch(session, target_date=date.today())
        if df.empty:
            return {"status": "failed", "message": "No data produced"}
        count = await fetcher.save_to_db(df, session)
        row = df.iloc[0]
        return ComputeRiskResponse(
            status="success" if count > 0 else "updated",
            trade_date=date.today().isoformat(),
            risk_score=float(row["risk_score"]),
            event_intensity=float(row["event_intensity"]),
            active_conflicts=int(row.get("active_conflicts", 0)),
            news_sentiment=(
                float(row["news_sentiment"])
                if row.get("news_sentiment") is not None
                and str(row["news_sentiment"]) != "nan"
                else None
            ),
            news_headline_count=(
                int(row["news_headline_count"])
                if row.get("news_headline_count") is not None
                and str(row["news_headline_count"]) != "nan"
                else None
            ),
        )
    except Exception as e:
        return {"status": "failed", "message": str(e)}
