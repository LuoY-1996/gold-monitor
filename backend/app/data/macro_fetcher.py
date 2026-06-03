"""Macro factor fetchers: DXY proxy, US Treasury 10Y, CPI."""

from datetime import date
import pandas as pd
import numpy as np
from sqlalchemy import select

from app.data.fetcher_base import BaseFetcher


class Treasury10YFetcher(BaseFetcher):
    """
    Fetch US 10-Year Treasury yield from akshare bond_zh_us_rate.
    This gives China-US bond comparison data including US Treasury yields.
    """

    source = "akshare"

    async def fetch(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        """Fetch US 10Y Treasury yield history."""
        import akshare as ak

        if start_date is None:
            start_date = date(2015, 1, 1)
        if end_date is None:
            end_date = date.today()

        try:
            df = ak.bond_zh_us_rate()
            if df.empty:
                return pd.DataFrame()

            cols = list(df.columns)

            # Column mapping: 日期, ..., 美国国债收益率10年 (10Y Treasury)
            date_col = cols[0]  # First column = date
            # US 10Y is typically the 9th column (0-indexed: 8)
            us10y_col = None
            for i, c in enumerate(cols):
                c_str = str(c)
                if '10' in c_str and ('美国' in c_str or '美' in c_str):
                    us10y_col = cols[i]
                    break

            if us10y_col is None:
                # Fallback: try column at position 8
                us10y_col = cols[min(8, len(cols) - 1)]

            result = pd.DataFrame()
            result["date"] = pd.to_datetime(df[date_col]).dt.date
            result["yield_value"] = pd.to_numeric(df[us10y_col], errors="coerce")
            result = result.dropna(subset=["yield_value"])
            result = result[(result["date"] >= start_date) & (result["date"] <= end_date)]
            return result

        except Exception as e:
            print(f"[macro] Treasury fetch error: {e}")
            return pd.DataFrame()

    async def save_to_db(self, df: pd.DataFrame, session) -> int:
        """Save Treasury 10Y data."""
        from app.models.factor import FactorTreasury10y

        count = 0
        for _, row in df.iterrows():
            if pd.isna(row.get("yield_value")):
                continue

            stmt = select(FactorTreasury10y).where(FactorTreasury10y.trade_date == row["date"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing is None:
                session.add(FactorTreasury10y(
                    trade_date=row["date"],
                    yield_value=float(row["yield_value"]),
                    source=self.source,
                ))
                count += 1
            else:
                existing.yield_value = float(row["yield_value"])
                existing.source = self.source

        return count


class DxyProxyFetcher(BaseFetcher):
    """
    Construct a DXY proxy from available forex pairs.

    DXY formula (simplified, using available pairs):
    DXY ≈ weighted geometric mean of USD vs major currencies

    We use forex_spot_em data to get current rates and build a simplified DXY.
    Since historical forex data is rate-limited, we compute the current DXY proxy
    and store it daily to build history.
    """

    source = "akshare_dxy_proxy"

    async def fetch(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        """Compute current DXY proxy from forex spot data."""
        import akshare as ak

        try:
            df = ak.forex_spot_em()
            if df.empty:
                return pd.DataFrame()

            # Extract forex rates from spot data
            pairs = {}
            for _, row in df.iterrows():
                code = str(row.iloc[1]) if len(row) > 1 else ""
                rate = float(row.iloc[3]) if len(row) > 3 else None
                if rate is not None:
                    pairs[code] = rate

            # Get USDCNH as base
            usdcnh = pairs.get("USDCNH", 6.77)

            # Convert CNH pairs to USD pairs
            eurusd = pairs.get("EURCNH", 0) / usdcnh if "EURCNH" in pairs else None
            usdjpy = (usdcnh * 100 / pairs["JPYCNH"]) if "JPYCNH" in pairs and pairs["JPYCNH"] > 0 else None
            gbpusd = pairs.get("GBPCNH", 0) / usdcnh if "GBPCNH" in pairs else None
            usdcad_val = pairs.get("CADCNH", 0) / usdcnh if "CADCNH" in pairs else None

            # DXY weights for available pairs (renormalized)
            # Standard DXY weights: EUR 57.6%, JPY 13.6%, GBP 11.9%, CAD 9.1%, SEK 4.2%, CHF 3.6%
            # Weights renormalized for EUR+JPY+GBP+CAD = 92.2% of DXY
            if all(v is not None for v in [eurusd, usdjpy, gbpusd, usdcad_val]):
                weights = {
                    "EUR": 0.576 / 0.922,
                    "JPY": 0.136 / 0.922,
                    "GBP": 0.119 / 0.922,
                    "CAD": 0.091 / 0.922,
                }

                # DXY = 100 * product of (pair_i / base_i)^weight_i
                # Using Feb 2024 approximate base levels
                bases = {"EUR": 1.08, "JPY": 148.0, "GBP": 1.26, "CAD": 1.35}
                dxy = 100.0
                for pair, weight in [
                    ("EUR", weights["EUR"]),
                    ("JPY", weights["JPY"]),
                    ("GBP", weights["GBP"]),
                    ("CAD", weights["CAD"]),
                ]:
                    rate = {"EUR": eurusd, "JPY": usdjpy, "GBP": gbpusd, "CAD": usdcad_val}[pair]
                    base = bases[pair]
                    dxy *= (rate / base) ** weight

                today = date.today()
                return pd.DataFrame([{"date": today, "close": round(dxy, 2)}])

        except Exception as e:
            print(f"[macro] DXY proxy error: {e}")

        return pd.DataFrame()

    async def save_to_db(self, df: pd.DataFrame, session) -> int:
        """Save DXY proxy data."""
        from app.models.factor import FactorDxy

        count = 0
        for _, row in df.iterrows():
            if pd.isna(row.get("close")):
                continue

            stmt = select(FactorDxy).where(FactorDxy.trade_date == row["date"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing is None:
                session.add(FactorDxy(
                    trade_date=row["date"],
                    close=float(row["close"]),
                    source=self.source,
                ))
                count += 1
            else:
                existing.close = float(row["close"])
                existing.source = self.source

        return count
