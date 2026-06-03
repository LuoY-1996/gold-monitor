"""Crude oil price data fetchers.

Sources:
- Real-time: Sina Finance hf_OIL (Brent crude, current quote)
- Historical: Sina futures daily K-line via AKShare (Brent, ~2500 records from 2015)
"""

from datetime import date
import re
import pandas as pd
import requests
from sqlalchemy import select

from app.data.fetcher_base import BaseFetcher


class OilRealtimeFetcher(BaseFetcher):
    """Fetch current Brent crude oil quote from Sina Finance."""

    source = "sina"

    async def fetch(self, start_date=None, end_date=None) -> pd.DataFrame:
        """Get latest Brent crude oil quote."""
        try:
            url = "https://hq.sinajs.cn/list=hf_OIL"
            headers = {"Referer": "https://finance.sina.com.cn"}
            r = requests.get(url, headers=headers, timeout=10)
            r.encoding = "gbk"

            match = re.search(r'"([^"]*)"', r.text)
            if not match:
                return pd.DataFrame()

            parts = match.group(1).split(",")
            if len(parts) < 13:
                return pd.DataFrame()

            close_price = float(parts[0])
            trade_date_str = parts[12] if len(parts) > 12 else str(date.today())
            trade_date = date.fromisoformat(trade_date_str)

            df = pd.DataFrame([{"date": trade_date, "close": close_price}])
            return df
        except Exception:
            return pd.DataFrame()

    async def save_to_db(self, df: pd.DataFrame, session) -> int:
        """Save oil data."""
        from app.models.factor import FactorOil

        count = 0
        for _, row in df.iterrows():
            stmt = select(FactorOil).where(FactorOil.trade_date == row["date"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing is None:
                session.add(FactorOil(
                    trade_date=row["date"],
                    close=float(row["close"]),
                    source=self.source,
                ))
                count += 1
            else:
                existing.close = float(row["close"])
                existing.source = self.source
        return count


class OilHistoryFetcher(BaseFetcher):
    """Load full Brent crude oil historical data from Sina futures via AKShare.

    Uses ak.futures_foreign_hist('OIL') which returns daily OHLCV for Brent.
    Typically ~2500 records from ~2015 to present.
    """

    source = "sina_futures"

    async def fetch(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        """Download full Brent oil history from Sina futures (via AKShare)."""
        try:
            import akshare as ak

            df = ak.futures_foreign_hist(symbol="OIL")
            if df.empty:
                return pd.DataFrame()

            # Standardize columns: date, open, high, low, close, volume
            df["date"] = pd.to_datetime(df["date"]).dt.date

            # Filter date range if specified
            if start_date:
                df = df[df["date"] >= start_date]
            if end_date:
                df = df[df["date"] <= end_date]

            # Keep only needed columns: date + close always, optionally OHLCV
            keep_cols = ["date", "close"]
            for c in ["open", "high", "low", "volume"]:
                if c in df.columns:
                    keep_cols.append(c)
            result = df[keep_cols].copy()
            result["close"] = pd.to_numeric(result["close"], errors="coerce")
            result = result.dropna(subset=["close"])
            return result

        except Exception as e:
            print(f"[oil] Sina futures history fetch error: {e}")
            return pd.DataFrame()

    async def save_to_db(self, df: pd.DataFrame, session) -> int:
        """Batch-upsert oil history into factor_oil table."""
        from app.models.factor import FactorOil

        count = 0
        for _, row in df.iterrows():
            if pd.isna(row.get("close")):
                continue

            stmt = select(FactorOil).where(FactorOil.trade_date == row["date"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing is None:
                session.add(FactorOil(
                    trade_date=row["date"],
                    close=float(row["close"]),
                    source=self.source,
                ))
                count += 1
            # Don't overwrite existing — historical data is immutable

        return count
