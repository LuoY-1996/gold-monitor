"""Business logic for geopolitical events and risk index."""

import json
from datetime import date, timedelta
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geopolitics import GeopoliticalEvent, GeopoliticalRiskIndex


async def get_events(
    session: AsyncSession,
    months: int = 3,
    category: str | None = None,
) -> list[dict]:
    """Get geopolitical events within the last N months, optional category filter."""
    cutoff = date.today() - timedelta(days=months * 30)

    # Debug: verify data exists
    try:
        total_check = await session.execute(text("SELECT COUNT(*) FROM geopolitical_events"))
        total_count = total_check.scalar()
        cutoff_check = await session.execute(
            text("SELECT COUNT(*) FROM geopolitical_events WHERE event_date >= :c"),
            {"c": cutoff},
        )
        cutoff_count = cutoff_check.scalar()
        event_dates = await session.execute(text("SELECT MIN(event_date), MAX(event_date) FROM geopolitical_events"))
        min_date, max_date = event_dates.one()
        print(f"[geo] total={total_count} cutoff={cutoff} cutoff_count={cutoff_count} date_range={min_date}->{max_date}")
    except Exception as e:
        print(f"[geo] debug error: {e}")

    # Use raw SQL to avoid ORM metadata caching issues
    if category:
        result = await session.execute(
            text("""
                SELECT id, event_date, title, description, impact, direction,
                       category, risk_regions, source_url
                FROM geopolitical_events
                WHERE event_date >= :cutoff AND category = :category
                ORDER BY event_date DESC
            """),
            {"cutoff": cutoff, "category": category},
        )
    else:
        result = await session.execute(
            text("""
                SELECT id, event_date, title, description, impact, direction,
                       category, risk_regions, source_url
                FROM geopolitical_events
                WHERE event_date >= :cutoff
                ORDER BY event_date DESC
            """),
            {"cutoff": cutoff},
        )

    rows = result.all()

    return [
        {
            "id": r.id,
            "date": r.event_date.isoformat() if hasattr(r.event_date, 'isoformat') else str(r.event_date),
            "title": r.title,
            "description": r.description,
            "impact": r.impact,
            "direction": r.direction,
            "category": r.category,
            "risk_regions": json.loads(r.risk_regions) if r.risk_regions else [],
            "source_url": r.source_url,
        }
        for r in rows
    ]


async def seed_events(session: AsyncSession, events: list[dict]) -> int:
    """Batch insert events, skipping those with duplicate date+title.

    Args:
        events: list of dicts with keys matching GeopoliticalEvent columns

    Returns:
        Number of newly inserted events
    """
    count = 0
    for ev in events:
        # Check for existing by date + title
        stmt = select(GeopoliticalEvent).where(
            GeopoliticalEvent.event_date == ev["event_date"],
            GeopoliticalEvent.title == ev["title"],
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            session.add(GeopoliticalEvent(
                event_date=ev["event_date"],
                title=ev["title"],
                description=ev.get("description"),
                impact=ev.get("impact", 1),
                direction=ev.get("direction", 0),
                category=ev.get("category", "geopolitics"),
                risk_regions=json.dumps(ev.get("risk_regions", [])) if ev.get("risk_regions") else None,
                source_url=ev.get("source_url"),
            ))
            count += 1

    return count


async def get_risk_index(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 90,
) -> list[dict]:
    """Get daily geopolitical risk index history."""
    stmt = (
        select(GeopoliticalRiskIndex)
        .order_by(GeopoliticalRiskIndex.trade_date.asc())
    )

    if start_date:
        stmt = stmt.where(GeopoliticalRiskIndex.trade_date >= start_date)
    if end_date:
        stmt = stmt.where(GeopoliticalRiskIndex.trade_date <= end_date)

    if not start_date and not end_date:
        cutoff = date.today() - timedelta(days=limit)
        stmt = stmt.where(GeopoliticalRiskIndex.trade_date >= cutoff)

    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "trade_date": r.trade_date.isoformat(),
            "risk_score": r.risk_score,
            "event_intensity": r.event_intensity,
            "active_conflicts": r.active_conflicts,
            "news_sentiment": r.news_sentiment,
            "news_headline_count": r.news_headline_count,
            "regional_scores": json.loads(r.regional_scores) if r.regional_scores else None,
        }
        for r in rows
    ]


async def get_latest_risk(session: AsyncSession) -> dict | None:
    """Get the most recent geopolitical risk score."""
    stmt = (
        select(GeopoliticalRiskIndex)
        .order_by(GeopoliticalRiskIndex.trade_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        return None

    return {
        "trade_date": row.trade_date.isoformat(),
        "risk_score": row.risk_score,
        "event_intensity": row.event_intensity,
        "active_conflicts": row.active_conflicts,
        "news_sentiment": row.news_sentiment,
        "news_headline_count": row.news_headline_count,
        "regional_scores": json.loads(row.regional_scores) if row.regional_scores else None,
    }
