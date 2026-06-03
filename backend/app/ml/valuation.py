"""Macro fair-value valuation model for gold.

Philosophy: Instead of predicting future prices, estimate what gold "should" be worth
based on current macro conditions. This is how institutional analysts actually value gold.

Model: Gold_Price = f(Treasury_10Y, USD/CNY, VIX, Oil, CB_Purchases, Geo_Risk)

Monthly frequency — aligns sparse factors (CPI, CB purchases) with daily data.
Output: fair value, valuation gap, historical percentile.
"""

import logging
from datetime import date, timedelta
from pathlib import Path
import os

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.preprocessing import StandardScaler

from app.models.gold_price import GoldPriceAu9999
from app.models.factor import FactorUsdCny, FactorTreasury10y, FactorVix, FactorOil
from app.models.geopolitics import GeopoliticalRiskIndex

logger = logging.getLogger(__name__)

# Central bank quarterly purchases (tons) — same data as frontend
CB_QUARTERLY = {
    "2021Q1": 150, "2021Q2": 200, "2021Q3": 69, "2021Q4": 44,
    "2022Q1": 84, "2022Q2": 180, "2022Q3": 459, "2022Q4": 359,
    "2023Q1": 228, "2023Q2": 175, "2023Q3": 361, "2023Q4": 273,
    "2024Q1": 290, "2024Q2": 183, "2024Q3": 186, "2024Q4": 333,
    "2025Q1": 309, "2025Q2": 246, "2025Q3": 272, "2025Q4": 356,
    "2026Q1": 316,
}


def _quarter_to_monthly(qdata: dict) -> pd.Series:
    """Convert quarterly CB purchases to monthly (equal monthly distribution)."""
    from calendar import monthrange
    monthly = {}
    for q, tons in qdata.items():
        year = int(q[:4])
        q_num = int(q[5])
        for m_offset in range(3):
            month = q_num * 3 - 2 + m_offset  # 1-12
            _, last_day = monthrange(year, month)
            month_end = date(year, month, last_day)
            monthly[month_end] = tons / 3.0
    return pd.Series(monthly, name="cb_purchases")


async def build_valuation_dataset(session: AsyncSession, months: int = 72) -> pd.DataFrame:
    """Build monthly macro dataset for gold valuation.

    Returns DataFrame with: date, gold_close, treasury_10y, usd_cny, vix, oil,
    geo_risk, cb_purchases (all monthly frequency, end-of-month values).
    """
    start_date = date.today() - timedelta(days=months * 31)
    end_date = date.today()

    # 1. Gold prices (Au99.99 → USD via derived XAU)
    from app.services.derived_xau_service import get_derived_xau_history
    xau_data = await get_derived_xau_history(session, start_date=start_date, end_date=end_date, days=9999)
    if not xau_data:
        return pd.DataFrame()

    df = pd.DataFrame(xau_data)
    df["date"] = pd.to_datetime(df["trade_date"])
    df = df.set_index("date")[["close"]].rename(columns={"close": "gold"})
    # Resample to month-end
    df_monthly = df.resample("ME").last()

    def _resample_to_month_end(df_daily: pd.DataFrame, value_col: str) -> pd.DataFrame:
        """Resample daily data to month-end, returning DataFrame with DatetimeIndex."""
        df_daily = df_daily.copy()
        df_daily.index = pd.to_datetime(df_daily.index)
        monthly = df_daily.resample("ME").last()
        monthly.index = pd.to_datetime(monthly.index)
        return monthly

    # 2. Treasury 10Y
    stmt = select(FactorTreasury10y.trade_date, FactorTreasury10y.yield_value).where(
        FactorTreasury10y.trade_date >= start_date
    ).order_by(FactorTreasury10y.trade_date.asc())
    result = await session.execute(stmt)
    rows = result.all()
    if rows:
        t10 = pd.DataFrame(rows, columns=["date", "treasury_10y"]).set_index("date")
        df_monthly = df_monthly.join(_resample_to_month_end(t10, "treasury_10y"), how="left")

    # 3. USD/CNY
    stmt = select(FactorUsdCny.trade_date, FactorUsdCny.close).where(
        FactorUsdCny.trade_date >= start_date
    ).order_by(FactorUsdCny.trade_date.asc())
    result = await session.execute(stmt)
    rows = result.all()
    if rows:
        usd = pd.DataFrame(rows, columns=["date", "usd_cny"]).set_index("date")
        df_monthly = df_monthly.join(_resample_to_month_end(usd, "usd_cny"), how="left")

    # 4. VIX
    stmt = select(FactorVix.trade_date, FactorVix.close).where(
        FactorVix.trade_date >= start_date
    ).order_by(FactorVix.trade_date.asc())
    result = await session.execute(stmt)
    rows = result.all()
    if rows:
        vix = pd.DataFrame(rows, columns=["date", "vix"]).set_index("date")
        df_monthly = df_monthly.join(_resample_to_month_end(vix, "vix"), how="left")

    # 5. Oil
    stmt = select(FactorOil.trade_date, FactorOil.close).where(
        FactorOil.trade_date >= start_date
    ).order_by(FactorOil.trade_date.asc())
    result = await session.execute(stmt)
    rows = result.all()
    if rows:
        oil = pd.DataFrame(rows, columns=["date", "oil"]).set_index("date")
        df_monthly = df_monthly.join(_resample_to_month_end(oil, "oil"), how="left")

    # 6. Geo risk
    stmt = select(GeopoliticalRiskIndex.trade_date, GeopoliticalRiskIndex.risk_score).where(
        GeopoliticalRiskIndex.trade_date >= start_date
    ).order_by(GeopoliticalRiskIndex.trade_date.asc())
    result = await session.execute(stmt)
    rows = result.all()
    if rows:
        geo = pd.DataFrame(rows, columns=["date", "geo_risk"]).set_index("date")
        df_monthly = df_monthly.join(_resample_to_month_end(geo, "geo_risk"), how="left")

    # 7. Central bank purchases (quarterly → monthly interpolation)
    cb_series = _quarter_to_monthly(CB_QUARTERLY)
    cb_series.index = pd.to_datetime(cb_series.index)
    df_monthly["cb_purchases"] = cb_series
    df_monthly["cb_purchases"] = df_monthly["cb_purchases"].interpolate(method="linear").fillna(100)

    # 8. Forward-fill gaps
    for col in ["treasury_10y", "usd_cny", "vix", "oil", "geo_risk"]:
        if col in df_monthly.columns:
            df_monthly[col] = df_monthly[col].ffill().bfill()

    return df_monthly.dropna()


def train_valuation_model(df: pd.DataFrame) -> dict:
    """Train a macro fair-value model.

    Uses Ridge regression (regularized linear model) for interpretability.
    Returns fitted model + scaler + metrics.
    """
    feature_cols = ["treasury_10y", "usd_cny", "vix", "oil", "geo_risk", "cb_purchases"]
    available_features = [c for c in feature_cols if c in df.columns and df[c].notna().sum() > 10]

    if len(available_features) < 3:
        return {"status": "error", "message": "Too few features available"}

    X = df[available_features].values
    y = df["gold"].values

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Ridge regression (regularized, interpretable)
    model = Ridge(alpha=1.0)
    model.fit(X_scaled, y)

    # Predictions for entire dataset
    y_pred = model.predict(X_scaled)
    residuals = y - y_pred
    residual_pct = residuals / y * 100

    # R²
    ss_res = np.sum(residuals ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot

    # Coefficients (direction and magnitude)
    coefs = sorted(
        zip(available_features, model.coef_),
        key=lambda x: abs(x[1]), reverse=True
    )

    # Current valuation
    current_fair = float(y_pred[-1])
    current_actual = float(y[-1])
    current_gap_pct = float(residual_pct[-1])
    # Percentile of residual: where does current gap rank historically?
    current_percentile = float((residual_pct < residual_pct[-1]).mean() * 100)

    # Valuation bands (±1 and ±2 std of residuals)
    res_std = float(np.std(residual_pct))
    bands = {
        "overvalued_threshold": round(res_std * 1.5, 1),
        "undervalued_threshold": round(-res_std * 1.5, 1),
        "extreme_overvalued": round(res_std * 3, 1),
        "extreme_undervalued": round(-res_std * 3, 1),
    }

    # Fair value time series
    fair_value_series = pd.Series(y_pred, index=df.index)

    return {
        "status": "ok",
        "r2": round(r2, 4),
        "features_used": available_features,
        "coefficients": [{"feature": f, "coefficient": round(c, 2)} for f, c in coefs],
        "current_fair_value": round(current_fair, 2),
        "current_actual": current_actual,
        "current_gap_pct": round(current_gap_pct, 2),
        "current_percentile": round(current_percentile, 1),
        "valuation_bands": bands,
        "residual_std": round(res_std, 2),
        "fair_value_history": {
            str(d.date()): round(v, 2)
            for d, v in fair_value_series.items()
        },
        "actual_history": {
            str(d.date()): round(v, 2)
            for d, v in df["gold"].items()
        },
        "gap_history": {
            str(d.date()): round(float(r), 2)
            for d, r in zip(df.index, residual_pct)
        },
    }


async def compute_valuation(session: AsyncSession) -> dict:
    """Full pipeline: build dataset, train model, return valuation."""
    df = await build_valuation_dataset(session)
    if df.empty:
        return {"status": "error", "message": "No valuation data available"}
    result = train_valuation_model(df)
    return result
