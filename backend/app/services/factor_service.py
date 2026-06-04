"""Factor analysis business logic."""

from datetime import date, timedelta
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.factor import FactorVix, FactorUsdCny, FactorDxy, FactorTreasury10y, FactorCpi, FactorOil, FactorFedFunds, FactorGoldEtf, FactorBreakevenInflation
from app.models.gold_price import GoldPriceXauUsd, GoldPriceAu9999

FACTOR_MODEL_MAP = {
    "vix": FactorVix,
    "usd_cny": FactorUsdCny,
    "dxy": FactorDxy,
    "treasury_10y": FactorTreasury10y,
    "cpi": FactorCpi,
    "oil": FactorOil,
    "fed_funds": FactorFedFunds,
    "gold_etf": FactorGoldEtf,
    "breakeven_inflation": FactorBreakevenInflation,
}

GOLD_MODEL_MAP = {
    "xau_usd": GoldPriceXauUsd,
    "au9999": GoldPriceAu9999,
    "xau-usd": GoldPriceXauUsd,
    "au-9999": GoldPriceAu9999,
}


async def get_factor_history(
    session: AsyncSession,
    factor_type: str,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 365,
) -> list[dict]:
    """Get historical data for a factor."""
    model = FACTOR_MODEL_MAP.get(factor_type.lower())
    if model is None:
        raise ValueError(f"Unknown factor type: {factor_type}. Available: {list(FACTOR_MODEL_MAP.keys())}")

    if start_date is None and end_date is None:
        start_date = date.today() - timedelta(days=limit)
    if end_date is None:
        end_date = date.today()

    # Determine the date and value columns per factor type
    if factor_type == "cpi":
        date_col = model.report_date
        value_col = model.cpi_value
    elif factor_type == "treasury_10y":
        date_col = model.trade_date
        value_col = model.yield_value
    elif factor_type == "fed_funds":
        date_col = model.trade_date
        value_col = model.rate
    elif factor_type == "gold_etf":
        date_col = model.trade_date
        value_col = model.holdings_tons
    elif factor_type == "breakeven_inflation":
        date_col = model.trade_date
        value_col = model.breakeven_rate
    else:
        date_col = model.trade_date
        value_col = model.close

    stmt = (
        select(date_col, value_col)
        .where(date_col >= start_date)
        .where(date_col <= end_date)
        .order_by(date_col.asc())
    )
    result = await session.execute(stmt)
    rows = result.all()

    return [
        {"trade_date": r[0], "value": float(r[1]) if r[1] is not None else None}
        for r in rows
    ]


async def compute_correlation(
    session: AsyncSession,
    gold_type: str,
    days: int = 365,
) -> dict:
    """Compute correlation between gold price and all available factors."""
    gold_model = GOLD_MODEL_MAP.get(gold_type.lower())
    if gold_model is None:
        raise ValueError(f"Unknown gold type: {gold_type}")

    start_date = date.today() - timedelta(days=days)

    # Get gold prices
    stmt = (
        select(gold_model.trade_date, gold_model.close)
        .where(gold_model.trade_date >= start_date)
        .order_by(gold_model.trade_date.asc())
    )
    result = await session.execute(stmt)
    gold_rows = result.all()

    if not gold_rows:
        return {"status": "empty", "factors": [], "correlations": []}

    gold_df = pd.DataFrame(gold_rows, columns=["date", "gold_close"])
    gold_df = gold_df.set_index("date")

    correlations = []

    # For each factor, get data and compute correlation
    for factor_type, model in FACTOR_MODEL_MAP.items():
        if factor_type == "cpi":
            date_col = model.report_date
            value_col = model.cpi_value
        elif factor_type == "treasury_10y":
            date_col = model.trade_date
            value_col = model.yield_value
        elif factor_type == "fed_funds":
            date_col = model.trade_date
            value_col = model.rate
        elif factor_type == "gold_etf":
            date_col = model.trade_date
            value_col = model.holdings_tons
        elif factor_type == "breakeven_inflation":
            date_col = model.trade_date
            value_col = model.breakeven_rate
        else:
            date_col = model.trade_date
            value_col = model.close

        stmt = (
            select(date_col, value_col)
            .where(date_col >= start_date)
            .order_by(date_col.asc())
        )
        result = await session.execute(stmt)
        factor_rows = result.all()

        if not factor_rows:
            continue

        factor_df = pd.DataFrame(factor_rows, columns=["date", "value"])
        factor_df = factor_df.set_index("date")
        factor_df = factor_df.dropna()

        if len(factor_df) < 10:
            continue

        # Merge on date and compute correlation
        merged = gold_df.join(factor_df, how="inner")
        if len(merged) < 10:
            continue

        # Correlation
        pearson = merged["gold_close"].corr(merged["value"])

        # Also compute rolling 60-day correlation
        merged["gold_return"] = merged["gold_close"].pct_change()
        merged["factor_return"] = merged["value"].pct_change()
        merged["rolling_corr_60d"] = merged["gold_return"].rolling(60).corr(merged["factor_return"])

        # Latest rolling correlation
        latest_rolling = None
        rolling_vals = merged["rolling_corr_60d"].dropna()
        if len(rolling_vals) > 0:
            latest_rolling = round(float(rolling_vals.iloc[-1]), 4)

        correlations.append({
            "factor": factor_type,
            "label": {
                "vix": "VIX 恐慌指数",
                "usd_cny": "美元/人民币",
                "dxy": "美元指数 DXY",
                "oil": "布伦特原油",
                "treasury_10y": "美债10Years收益率",
                "cpi": "CPI 通胀",
                "fed_funds": "联邦基金利率",
                "gold_etf": "黄金ETF持仓",
                "breakeven_inflation": "盈亏平衡通胀率",
            }.get(factor_type, factor_type),
            "pearson_correlation": round(float(pearson), 4),
            "rolling_corr_60d": latest_rolling,
            "data_points": len(merged),
        })

    # Sort by absolute correlation (strongest first)
    correlations.sort(key=lambda x: abs(x["pearson_correlation"]), reverse=True)

    return {
        "status": "ok",
        "gold_type": gold_type,
        "factors": [c["factor"] for c in correlations],
        "correlations": correlations,
    }
