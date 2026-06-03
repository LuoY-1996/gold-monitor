"""VIX (CBOE Volatility Index) data fetchers.

Sources:
- Real-time: Sina Finance hf_VX (covers today's value)
- Historical: CBOE official daily CSV (1990-present, 9000+ records)
"""

from datetime import date
import re
import pandas as pd
import requests
from sqlalchemy import select

from app.data.fetcher_base import BaseFetcher


class VixRealtimeFetcher(BaseFetcher):
    """Fetch current VIX quote from Sina Finance (single data point)."""

    source = "sina"

    async def fetch(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        """Get latest VIX quote from Sina."""
        try:
            url = "https://hq.sinajs.cn/list=hf_VX"
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
        """Save VIX data."""
        from app.models.factor import FactorVix

        count = 0
        for _, row in df.iterrows():
            stmt = select(FactorVix).where(FactorVix.trade_date == row["date"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing is None:
                session.add(FactorVix(
                    trade_date=row["date"],
                    close=float(row["close"]),
                    source=self.source,
                ))
                count += 1
            else:
                existing.close = float(row["close"])
                existing.source = self.source

        return count


class VixHistoryFetcher(BaseFetcher):
    """Load full VIX historical data from CBOE official CSV.

    Source: https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv
    Free, no API key required. Daily OHLC from 1990-01-02 to present.
    """

    source = "cboe"
    CBOE_VIX_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"

    async def fetch(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        """Download full VIX history from CBOE and return as DataFrame.

        Returns columns: date, open, high, low, close
        """
        from io import StringIO

        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            r = requests.get(self.CBOE_VIX_URL, headers=headers, timeout=30)
            if r.status_code != 200:
                print(f"[vix] CBOE returned HTTP {r.status_code}")
                return pd.DataFrame()

            df = pd.read_csv(StringIO(r.text))
            if df.empty:
                return pd.DataFrame()

            # CBOE CSV format: DATE, OPEN, HIGH, LOW, CLOSE
            # Dates are MM/DD/YYYY
            df["date"] = pd.to_datetime(df["DATE"]).dt.date
            df = df.rename(columns={
                "OPEN": "open",
                "HIGH": "high",
                "LOW": "low",
                "CLOSE": "close",
            })

            # Filter date range if specified
            if start_date:
                df = df[df["date"] >= start_date]
            if end_date:
                df = df[df["date"] <= end_date]

            df = df[["date", "open", "high", "low", "close"]]
            df = df.dropna(subset=["close"])
            return df

        except Exception as e:
            print(f"[vix] CBOE history fetch error: {e}")
            return pd.DataFrame()

    async def save_to_db(self, df: pd.DataFrame, session) -> int:
        """Batch-upsert VIX history into factor_vix table.

        Uses INSERT OR IGNORE pattern — only adds new dates, skips existing.
        """
        from app.models.factor import FactorVix

        count = 0
        for _, row in df.iterrows():
            if pd.isna(row.get("close")):
                continue

            stmt = select(FactorVix).where(FactorVix.trade_date == row["date"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing is None:
                session.add(FactorVix(
                    trade_date=row["date"],
                    close=float(row["close"]),
                    source=self.source,
                ))
                count += 1
            # Don't overwrite existing — historical data doesn't change

        return count
