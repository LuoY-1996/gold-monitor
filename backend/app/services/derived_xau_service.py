"""
Derive XAU/USD historical prices from Au99.99 + USD/CNY daily rates.

XAU/USD = (Au99.99 CNY/gram * 31.1035 g/oz) / USDCNY

Uses daily USD/CNY rates for each trading day to maximize historical accuracy.
For dates without an exact USD/CNY match, falls back to the most recent prior rate.
"""

from datetime import date, timedelta
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gold_price import GoldPriceAu9999
from app.models.factor import FactorUsdCny

TROY_OZ_GRAMS = 31.1035
DEFAULT_USD_CNY = 6.77  # Fallback if no USD/CNY data at all


async def _load_usd_cny_map(
    session: AsyncSession,
    start_date: date | None = None,
) -> dict[date, float]:
    """Load USD/CNY daily rates into a dict keyed by trade_date.

    Returns all available rates. For missing dates, the caller should forward-fill.
    """
    stmt = (
        select(FactorUsdCny.trade_date, FactorUsdCny.close)
        .order_by(FactorUsdCny.trade_date.asc())
    )
    if start_date:
        # Load a bit before start_date for forward-fill
        stmt = stmt.where(FactorUsdCny.trade_date >= start_date - timedelta(days=30))
    result = await session.execute(stmt)
    rows = result.all()
    return {row.trade_date: float(row.close) for row in rows if row.close and row.close > 0}


def _get_rate_for_date(
    trade_date: date,
    rate_map: dict[date, float],
    fallback: float,
) -> float:
    """Get the USD/CNY rate for a given date.

    Exact match first, then most recent prior date (forward-fill),
    then the earliest available, then hardcoded fallback.
    """
    if trade_date in rate_map:
        return rate_map[trade_date]

    # Find the most recent rate before trade_date
    prev_dates = [d for d in rate_map if d < trade_date]
    if prev_dates:
        return rate_map[max(prev_dates)]

    # No prior rate — use earliest available
    if rate_map:
        return rate_map[min(rate_map)]

    return fallback


async def get_derived_xau_history(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
    days: int = 365,
) -> list[dict]:
    """Get derived XAU/USD historical data from Au99.99 + daily USD/CNY rates.

    Returns list of dicts with: trade_date, open, high, low, close, _derived, _usd_cny
    """
    if start_date is None and end_date is None:
        start_date = date.today() - timedelta(days=days)
    if end_date is None:
        end_date = date.today()

    # Load daily USD/CNY rates
    rate_map = await _load_usd_cny_map(session, start_date)

    # Determine fallback: latest rate from map, or hardcoded default
    if rate_map:
        fallback_rate = rate_map[max(rate_map)]
    else:
        fallback_rate = DEFAULT_USD_CNY

    # Load Au99.99 prices
    stmt = (
        select(
            GoldPriceAu9999.trade_date,
            GoldPriceAu9999.open,
            GoldPriceAu9999.high,
            GoldPriceAu9999.low,
            GoldPriceAu9999.close,
            GoldPriceAu9999.volume,
        )
        .order_by(GoldPriceAu9999.trade_date.asc())
    )

    if start_date:
        stmt = stmt.where(GoldPriceAu9999.trade_date >= start_date)
    if end_date:
        stmt = stmt.where(GoldPriceAu9999.trade_date <= end_date)

    result = await session.execute(stmt)
    rows = result.all()

    data = []
    for row in rows:
        usd_cny = _get_rate_for_date(row.trade_date, rate_map, fallback_rate)
        factor = TROY_OZ_GRAMS / usd_cny
        data.append({
            "trade_date": row.trade_date,
            "open": round(float(row.open) * factor, 2) if row.open else None,
            "high": round(float(row.high) * factor, 2) if row.high else None,
            "low": round(float(row.low) * factor, 2) if row.low else None,
            "close": round(float(row.close) * factor, 2) if row.close else None,
            "volume": row.volume,
            "_derived": True,
            "_usd_cny": round(usd_cny, 4),
        })

    return data


async def get_derived_xau_df(
    session: AsyncSession,
    days: int = 365,
) -> pd.DataFrame:
    """Get derived XAU/USD as a DataFrame (for indicator computation)."""
    data = await get_derived_xau_history(session, days=days)

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["trade_date"])
    df = df.set_index("date")
    df = df.rename(columns={
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
    })
    return df
