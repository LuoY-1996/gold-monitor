"""Business logic for forex/exchange rate queries."""

from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.factor import FactorUsdCny


async def get_usd_cny_realtime(session: AsyncSession) -> dict | None:
    """Get latest USD/CNY rate."""
    stmt = (
        select(FactorUsdCny)
        .order_by(FactorUsdCny.trade_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        return None

    return {
        "trade_date": row.trade_date,
        "close": row.close,
        "open": row.open,
        "high": row.high,
        "low": row.low,
    }


async def get_usd_cny_history(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 365,
) -> list[dict]:
    """Get USD/CNY historical data."""
    stmt = select(FactorUsdCny).order_by(FactorUsdCny.trade_date.asc())

    if start_date:
        stmt = stmt.where(FactorUsdCny.trade_date >= start_date)
    if end_date:
        stmt = stmt.where(FactorUsdCny.trade_date <= end_date)

    if not start_date and not end_date:
        cutoff = date.today() - timedelta(days=limit)
        stmt = stmt.where(FactorUsdCny.trade_date >= cutoff)

    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "trade_date": r.trade_date,
            "close": r.close,
            "open": r.open,
            "high": r.high,
            "low": r.low,
        }
        for r in rows
    ]


def calculate_cross_rate(xau_close: float, au9999_close: float) -> dict:
    """
    Calculate implied USD/CNY rate from gold prices.

    XAU/USD = USD per troy ounce
    Au99.99 = CNY per gram
    1 troy ounce = 31.1035 grams

    Implied rate = (Au99.99 * 31.1035) / XAU
    """
    if xau_close <= 0 or au9999_close <= 0:
        return {"implied_rate": None, "deviation_pct": None}

    implied = (au9999_close * 31.1035) / xau_close
    return {"implied_rate": round(implied, 4), "deviation_pct": None}


def calculate_gold_premium(xau_close: float, au9999_close: float, usd_cny: float) -> dict:
    """
    Calculate domestic gold premium vs international.

    Theoretical domestic price = XAU * USDCNY / 31.1035
    Premium = (actual - theoretical) / theoretical * 100
    """
    if xau_close <= 0 or usd_cny <= 0:
        return {"theoretical_au": None, "premium_pct": None}

    theoretical = (xau_close * usd_cny) / 31.1035
    actual = au9999_close
    premium = ((actual - theoretical) / theoretical) * 100

    return {
        "theoretical_au": round(theoretical, 2),
        "premium_pct": round(premium, 2),
    }
