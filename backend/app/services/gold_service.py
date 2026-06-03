"""Business logic for gold price queries."""

from datetime import date, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gold_price import GoldPriceXauUsd, GoldPriceAu9999

GOLD_TYPE_MAP = {
    "xau_usd": GoldPriceXauUsd,
    "au9999": GoldPriceAu9999,
    "xau-usd": GoldPriceXauUsd,
    "au-9999": GoldPriceAu9999,
}


def _get_model(gold_type: str):
    """Resolve gold type string to ORM model."""
    model = GOLD_TYPE_MAP.get(gold_type.lower())
    if model is None:
        raise ValueError(f"Unknown gold type: {gold_type}. Use 'xau_usd' or 'au9999'.")
    return model


async def get_realtime(session: AsyncSession, gold_type: str) -> dict | None:
    """Get the latest gold price from database."""
    model = _get_model(gold_type)
    stmt = (
        select(model)
        .order_by(model.trade_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        return None

    return {
        "gold_type": gold_type,
        "trade_date": row.trade_date,
        "open": row.open,
        "high": row.high,
        "low": row.low,
        "close": row.close,
        "volume": row.volume,
    }


async def get_history(
    session: AsyncSession,
    gold_type: str,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 365,
) -> list[dict]:
    """Get historical gold prices."""
    model = _get_model(gold_type)

    stmt = select(model).order_by(model.trade_date.asc())

    if start_date:
        stmt = stmt.where(model.trade_date >= start_date)
    if end_date:
        stmt = stmt.where(model.trade_date <= end_date)

    if not start_date and not end_date:
        # Default: last `limit` days
        cutoff = date.today() - timedelta(days=limit)
        stmt = stmt.where(model.trade_date >= cutoff)

    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "trade_date": r.trade_date,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "volume": r.volume,
        }
        for r in rows
    ]


async def get_compare(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 365,
) -> list[dict]:
    """Get side-by-side comparison of XAU/USD and Au99.99 on shared trading days."""
    from sqlalchemy import and_

    # Get all dates that exist in both tables
    if not start_date and not end_date:
        start_date = date.today() - timedelta(days=limit)
    if not end_date:
        end_date = date.today()

    # Subquery approach: join on trade_date
    stmt = (
        select(
            GoldPriceXauUsd.trade_date,
            GoldPriceXauUsd.close.label("xau_usd_close"),
            GoldPriceAu9999.close.label("au9999_close"),
        )
        .join(
            GoldPriceAu9999,
            GoldPriceXauUsd.trade_date == GoldPriceAu9999.trade_date,
        )
        .where(GoldPriceXauUsd.trade_date >= start_date)
        .where(GoldPriceXauUsd.trade_date <= end_date)
        .order_by(GoldPriceXauUsd.trade_date.asc())
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "trade_date": r.trade_date,
            "xau_usd_close": float(r.xau_usd_close) if r.xau_usd_close else None,
            "au9999_close": float(r.au9999_close) if r.au9999_close else None,
        }
        for r in rows
    ]
