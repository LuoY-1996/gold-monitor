"""Technical indicator computation using pandas."""

import pandas as pd
import numpy as np
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gold_price import GoldPriceXauUsd, GoldPriceAu9999

GOLD_TYPE_MAP = {
    "xau_usd": GoldPriceXauUsd,
    "au9999": GoldPriceAu9999,
    "xau-usd": GoldPriceXauUsd,
    "au-9999": GoldPriceAu9999,
}


def _get_model(gold_type: str):
    model = GOLD_TYPE_MAP.get(gold_type.lower())
    if model is None:
        raise ValueError(f"Unknown gold type: {gold_type}")
    return model


async def get_price_df(session: AsyncSession, gold_type: str, days: int = 365) -> pd.DataFrame:
    """Load price data into a pandas DataFrame."""
    # For XAU/USD, derive from Au99.99 + USD/CNY
    if gold_type.lower() in ("xau_usd", "xau-usd"):
        from app.services.derived_xau_service import get_derived_xau_df
        return await get_derived_xau_df(session, days)

    model = _get_model(gold_type)

    cutoff = date.today() - timedelta(days=days)
    stmt = (
        select(model.trade_date, model.open, model.high, model.low, model.close, model.volume)
        .where(model.trade_date >= cutoff)
        .order_by(model.trade_date.asc())
    )
    result = await session.execute(stmt)
    rows = result.all()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    df = df.dropna(subset=["close"])
    df = df.set_index("date")
    return df


def compute_ma(df: pd.DataFrame, periods: list[int] = None) -> pd.DataFrame:
    """Compute Simple Moving Averages."""
    if periods is None:
        periods = [5, 10, 20, 60, 200]

    result = pd.DataFrame(index=df.index)
    for p in periods:
        result[f"ma_{p}"] = df["close"].rolling(window=p).mean()
    return result


def compute_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """Compute MACD indicator."""
    result = pd.DataFrame(index=df.index)
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    result["macd"] = ema_fast - ema_slow
    result["macd_signal"] = result["macd"].ewm(span=signal, adjust=False).mean()
    result["macd_histogram"] = result["macd"] - result["macd_signal"]
    return result


def compute_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Compute RSI (Relative Strength Index)."""
    result = pd.DataFrame(index=df.index)
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    result[f"rsi_{period}"] = 100 - (100 / (1 + rs))
    return result


def compute_bollinger(df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> pd.DataFrame:
    """Compute Bollinger Bands."""
    result = pd.DataFrame(index=df.index)
    result["bb_middle"] = df["close"].rolling(window=period).mean()
    bb_std = df["close"].rolling(window=period).std()
    result["bb_upper"] = result["bb_middle"] + std_dev * bb_std
    result["bb_lower"] = result["bb_middle"] - std_dev * bb_std
    result["bb_width"] = (result["bb_upper"] - result["bb_lower"]) / result["bb_middle"]
    return result


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Compute Average True Range."""
    result = pd.DataFrame(index=df.index)
    high = df["high"].fillna(df["close"])
    low = df["low"].fillna(df["close"])
    prev_close = df["close"].shift(1).fillna(df["close"])

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    result[f"atr_{period}"] = true_range.ewm(alpha=1/period, adjust=False).mean()
    return result


def _df_to_safe_json(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame to JSON-safe list of dicts, replacing NaN with None."""
    df = df.astype(object)
    df = df.where(pd.notna(df), None)
    return df.to_dict(orient="records")


def compute_all_indicators(df: pd.DataFrame) -> list[dict]:
    """Compute all technical indicators for a price DataFrame.
    Returns a JSON-safe list of dicts."""
    if df.empty:
        return []

    ma = compute_ma(df)
    macd = compute_macd(df)
    rsi = compute_rsi(df)
    bb = compute_bollinger(df)
    atr = compute_atr(df)

    # Combine all indicators
    result = pd.concat([ma, macd, rsi, bb, atr], axis=1)
    result["close"] = df["close"]
    result = result.reset_index()
    # Convert date to string for JSON serialization
    result["date"] = result["date"].astype(str)

    return _df_to_safe_json(result)


def compute_trend_signals(df: pd.DataFrame) -> dict:
    """Generate trend signals based on indicators."""
    if df.empty or len(df) < 60:
        return {"status": "insufficient_data", "message": "需要至少60个交易日的数据"}

    ma = compute_ma(df)
    macd = compute_macd(df)
    rsi = compute_rsi(df)
    bb = compute_bollinger(df)

    latest = df.index[-1]
    close = df.loc[latest, "close"]

    signals = []

    # MA trend
    if pd.notna(ma.loc[latest, "ma_5"]) and pd.notna(ma.loc[latest, "ma_20"]):
        ma5 = ma.loc[latest, "ma_5"]
        ma20 = ma.loc[latest, "ma_20"]
        if ma5 > ma20:
            signals.append({"indicator": "MA(5,20)", "signal": "bullish", "desc": "短期均线上穿长期均线，多头排列"})
        else:
            signals.append({"indicator": "MA(5,20)", "signal": "bearish", "desc": "短期均线下穿长期均线，空头排列"})

    # MACD
    if pd.notna(macd.loc[latest, "macd_histogram"]):
        hist = macd.loc[latest, "macd_histogram"]
        prev_hist = macd.iloc[-2]["macd_histogram"] if len(macd) > 1 else 0
        if hist > 0:
            signals.append({"indicator": "MACD", "signal": "bullish", "desc": "MACD柱状线为正"})
        else:
            signals.append({"indicator": "MACD", "signal": "bearish", "desc": "MACD柱状线为负"})

    # RSI
    if pd.notna(rsi.loc[latest, "rsi_14"]):
        rsi_val = rsi.loc[latest, "rsi_14"]
        if rsi_val > 70:
            signals.append({"indicator": "RSI(14)", "signal": "overbought", "desc": f"RSI={rsi_val:.1f}，超买区域"})
        elif rsi_val < 30:
            signals.append({"indicator": "RSI(14)", "signal": "oversold", "desc": f"RSI={rsi_val:.1f}，超卖区域"})
        else:
            signals.append({"indicator": "RSI(14)", "signal": "neutral", "desc": f"RSI={rsi_val:.1f}，中性区域"})

    # Bollinger
    if pd.notna(bb.loc[latest, "bb_upper"]):
        bb_upper = bb.loc[latest, "bb_upper"]
        bb_lower = bb.loc[latest, "bb_lower"]
        if close >= bb_upper:
            signals.append({"indicator": "Bollinger", "signal": "overbought", "desc": "价格触及布林带上轨"})
        elif close <= bb_lower:
            signals.append({"indicator": "Bollinger", "signal": "oversold", "desc": "价格触及布林带下轨"})
        else:
            signals.append({"indicator": "Bollinger", "signal": "neutral", "desc": "价格在布林带内运行"})

    # Overall trend
    bullish_count = sum(1 for s in signals if s["signal"] in ("bullish", "oversold"))
    bearish_count = sum(1 for s in signals if s["signal"] in ("bearish", "overbought"))

    if bullish_count > bearish_count:
        overall = "偏多"
    elif bearish_count > bullish_count:
        overall = "偏空"
    else:
        overall = "震荡"

    return {
        "status": "ok",
        "date": str(latest),
        "close": float(close),
        "overall_trend": overall,
        "signals": signals,
    }
