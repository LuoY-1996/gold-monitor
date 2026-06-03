"""ML feature engineering pipeline for gold price prediction.

Builds a feature matrix from:
1. Price data + technical indicators (via indicator_service)
2. Macro factors: USD/CNY, Treasury 10Y, VIX, Oil (via factor tables)
3. Geopolitical risk index (via geopolitics table)
4. Derived features: returns, volatility, ratios, changes

Target variables:
- target_dir_7d: binary, 1 if close 7 trading days later > today's close
- target_ret_7d: float, percentage return over next 7 trading days
"""

import logging
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import indicator_service

logger = logging.getLogger(__name__)

# Columns to exclude as features (identifiers, targets, derived flags)
META_COLS = {"date", "trade_date", "_derived", "_usd_cny",
             "target_dir_1d", "target_ret_1d",
             "target_dir_3d", "target_ret_3d",
             "target_dir_5d", "target_ret_5d",
             "target_dir_7d", "target_ret_7d"}


async def _load_price_features(
    session: AsyncSession, gold_type: str, days: int
) -> pd.DataFrame:
    """Load price data with technical indicators.

    get_price_df returns a DataFrame with DatetimeIndex named 'date'.
    compute_all_indicators expects this structure and calls reset_index() internally,
    producing a 'date' column in the returned list of dicts.
    """
    df = await indicator_service.get_price_df(session, gold_type, days)
    if df.empty:
        return df

    # Compute all technical indicators (keeps index intact internally)
    indicators = indicator_service.compute_all_indicators(df)
    if not indicators:
        return pd.DataFrame()

    result = pd.DataFrame(indicators)
    # The indicator service returns 'date' as string; convert to proper date
    if "date" in result.columns:
        result["trade_date"] = pd.to_datetime(result["date"]).dt.date
    return result


async def _load_factor_series(
    session: AsyncSession,
    table,
    date_col,
    value_col,
    start_date: date,
    label: str,
) -> pd.DataFrame:
    """Load a single macro factor as a daily time series."""
    stmt = (
        select(date_col, value_col)
        .where(date_col >= start_date)
        .order_by(date_col.asc())
    )
    result = await session.execute(stmt)
    rows = result.all()
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["trade_date", label])
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    # Drop duplicates by date (keep last)
    df = df.drop_duplicates(subset=["trade_date"], keep="last")
    df[label] = pd.to_numeric(df[label], errors="coerce")
    return df


async def _load_all_macro_factors(
    session: AsyncSession, start_date: date
) -> pd.DataFrame:
    """Load all macro factors into a single DataFrame joined on trade_date."""
    from app.models.factor import (
        FactorUsdCny, FactorTreasury10y, FactorVix, FactorOil,
    )
    from app.models.geopolitics import GeopoliticalRiskIndex

    factors = []

    # USD/CNY
    df_usd = await _load_factor_series(
        session, FactorUsdCny, FactorUsdCny.trade_date,
        FactorUsdCny.close, start_date, "usd_cny"
    )
    if not df_usd.empty:
        factors.append(df_usd)

    # Treasury 10Y
    df_t10 = await _load_factor_series(
        session, FactorTreasury10y, FactorTreasury10y.trade_date,
        FactorTreasury10y.yield_value, start_date, "treasury_10y"
    )
    if not df_t10.empty:
        factors.append(df_t10)

    # VIX
    df_vix = await _load_factor_series(
        session, FactorVix, FactorVix.trade_date,
        FactorVix.close, start_date, "vix"
    )
    if not df_vix.empty:
        factors.append(df_vix)

    # Oil
    df_oil = await _load_factor_series(
        session, FactorOil, FactorOil.trade_date,
        FactorOil.close, start_date, "oil"
    )
    if not df_oil.empty:
        factors.append(df_oil)

    # Geopolitical risk index
    df_geo = await _load_factor_series(
        session, GeopoliticalRiskIndex, GeopoliticalRiskIndex.trade_date,
        GeopoliticalRiskIndex.risk_score, start_date, "geo_risk"
    )
    if not df_geo.empty:
        factors.append(df_geo)

    # Merge all factors on trade_date
    if not factors:
        return pd.DataFrame()

    merged = factors[0]
    for df in factors[1:]:
        merged = merged.merge(df, on="trade_date", how="outer")

    merged = merged.sort_values("trade_date").reset_index(drop=True)
    return merged


def _compute_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
    """Compute Stochastic Oscillator (%K and %D)."""
    result = pd.DataFrame(index=df.index)
    low_min = df["low"].rolling(k_period).min()
    high_max = df["high"].rolling(k_period).max()
    result["stoch_k"] = ((df["close"] - low_min) / (high_max - low_min).replace(0, np.nan)) * 100
    result["stoch_d"] = result["stoch_k"].rolling(d_period).mean()
    return result


def _compute_cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Compute Commodity Channel Index."""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean())
    return (tp - sma) / (0.015 * mad.replace(0, np.nan))


def _compute_obv(df: pd.DataFrame) -> pd.Series:
    """Compute On-Balance Volume."""
    obv = [0]
    for i in range(1, len(df)):
        close_diff = df["close"].iloc[i] - df["close"].iloc[i - 1]
        vol = df["volume"].iloc[i] if pd.notna(df["volume"].iloc[i]) else 0
        if close_diff > 0:
            obv.append(obv[-1] + vol)
        elif close_diff < 0:
            obv.append(obv[-1] - vol)
        else:
            obv.append(obv[-1])
    return pd.Series(obv, index=df.index)


def _add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add lagged returns, volatility, ratios, technical indicators, calendar & interaction features."""
    close_col = "close"

    # ── Price returns at multiple horizons ──
    df["ret_1d"] = df[close_col].pct_change(1)
    for horizon in [3, 5, 14, 20, 30]:
        df[f"ret_{horizon}d"] = df[close_col].pct_change(horizon)

    # ── Volatility ──
    for window in [5, 14, 20]:
        df[f"vol_{window}d"] = df["ret_1d"].rolling(window).std()

    # ── Price-to-MA ratios ──
    for ma in [5, 10, 20, 60, 200]:
        ma_col = f"ma_{ma}"
        if ma_col in df.columns:
            df[f"close_div_{ma_col}"] = df[close_col] / df[ma_col] - 1.0

    # ── Bollinger position ──
    if all(c in df.columns for c in ["bb_upper", "bb_lower"]):
        bb_range = df["bb_upper"] - df["bb_lower"]
        df["bb_position"] = (df[close_col] - df["bb_lower"]) / bb_range.replace(0, np.nan)

    # ── RSI momentum ──
    if "rsi_14" in df.columns:
        df["rsi_change_5d"] = df["rsi_14"].diff(5)
        df["rsi_change_14d"] = df["rsi_14"].diff(14)

    # ── MACD histogram ──
    if "macd_histogram" in df.columns:
        df["macd_hist_change_3d"] = df["macd_histogram"].diff(3)

    # ── Stochastic Oscillator ──
    if all(c in df.columns for c in ["high", "low"]):
        stoch = _compute_stochastic(df)
        df["stoch_k"] = stoch["stoch_k"]
        df["stoch_d"] = stoch["stoch_d"]

    # ── CCI (Commodity Channel Index) ──
    if "high" in df.columns and "low" in df.columns:
        df["cci_20"] = _compute_cci(df)

    # ── OBV (On-Balance Volume) ──
    if "volume" in df.columns:
        obv = _compute_obv(df)
        df["obv"] = obv
        df["obv_chg_5d"] = obv.diff(5)

    # ── Calendar features ──
    if "trade_date" in df.columns:
        dates = pd.to_datetime(df["trade_date"])
        df["day_of_week"] = dates.dt.dayofweek  # 0=Mon, 4=Fri
        df["is_month_start"] = (dates.dt.day <= 3).astype(int)
        df["is_month_end"] = (dates.dt.day >= 25).astype(int)

    # ── Interaction features ──
    if "oil" in df.columns:
        df["gold_oil_ratio"] = df[close_col] / df["oil"].replace(0, np.nan)
        df["gold_oil_ratio_chg_5d"] = df["gold_oil_ratio"].diff(5)
    if "vix" in df.columns:
        df["gold_vix_ratio"] = df[close_col] / df["vix"].replace(0, np.nan)
    if "usd_cny" in df.columns and "treasury_10y" in df.columns:
        df["usdcny_treasury_spread"] = df["usd_cny"] - df["treasury_10y"]

    # ── Factor changes at multiple horizons ──
    for col in ["usd_cny", "treasury_10y", "vix", "oil", "geo_risk"]:
        if col in df.columns:
            for h in [3, 5, 14, 20]:
                df[f"{col}_chg_{h}d"] = df[col].diff(h)

    return df


def _add_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Create target variables: direction and return for multiple horizons.

    No look-ahead bias: shift(-N) means predict N days ahead using today's features.
    """
    close_col = "close"

    for horizon in [1, 3, 5, 7]:
        future_close = df[close_col].shift(-horizon)
        df[f"target_dir_{horizon}d"] = (future_close > df[close_col]).astype(int)
        df[f"target_ret_{horizon}d"] = (future_close / df[close_col] - 1.0)

    return df


async def build_training_dataset(
    session: AsyncSession,
    gold_type: str = "xau_usd",
    days: int = 730,
) -> tuple[pd.DataFrame, list[str]]:
    """Build complete ML training dataset.

    Args:
        session: DB session
        gold_type: 'xau_usd' or 'au9999'
        days: how many days of history to include

    Returns:
        (X, feature_names) — X is the feature matrix (NaN rows dropped),
        feature_names excludes meta/target columns
    """
    if days < 120:
        logger.warning(f"days={days} is low; indicators need ≥60, recommend ≥365")
        days = max(days, 120)

    start_date = date.today() - timedelta(days=days + 30)  # Extra buffer for lagged features

    # 1. Load price + indicator features
    df = await _load_price_features(session, gold_type, days + 30)
    if df.empty:
        logger.error(f"No price data for {gold_type}")
        return pd.DataFrame(), []

    # 2. Load and merge macro factors
    factors_df = await _load_all_macro_factors(session, start_date)
    if not factors_df.empty:
        # Merge on trade_date (left join: keep all price dates)
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        df = df.merge(factors_df, on="trade_date", how="left")

    # 3. Forward-fill sparse factors (CPI monthly → daily, geo_risk gaps)
    for col in ["usd_cny", "treasury_10y", "vix", "oil", "geo_risk"]:
        if col in df.columns:
            df[col] = df[col].ffill().bfill()

    # 4. Add derived features (lagged returns, volatility, ratios)
    df = _add_derived_features(df)

    # 5. Add target variables
    df = _add_targets(df)

    # 6. Clean up: drop rows without any target (last 7 rows), then rows with NaN features
    target_cols = [c for c in df.columns if c.startswith("target_")]
    if target_cols:
        df = df.dropna(subset=target_cols, how="all")

    # Identify feature columns (exclude meta and target)
    feature_names = [c for c in df.columns if c not in META_COLS]

    # Drop rows where any feature is NaN (first ~200 days due to MA200, etc.)
    df_clean = df.dropna(subset=feature_names)

    skipped = len(df) - len(df_clean)
    if skipped > 0:
        logger.info(f"Dropped {skipped} rows with NaN features (from {len(df)} total)")

    logger.info(
        f"Training dataset: {len(df_clean)} rows, {len(feature_names)} features, "
        f"target balance: {df_clean['target_dir_7d'].mean():.1%} up"
    )

    return df_clean, feature_names


def get_latest_features(df: pd.DataFrame, feature_names: list[str]) -> pd.DataFrame:
    """Extract the most recent row of features for live prediction.

    Args:
        df: full feature DataFrame (must have all feature_names columns)
        feature_names: list of feature column names

    Returns:
        Single-row DataFrame with only feature columns
    """
    if df.empty:
        return pd.DataFrame()
    latest = df.iloc[[-1]][feature_names].copy()
    return latest
