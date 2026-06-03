"""International gold (XAU/USD) fetcher using Sina Finance API."""

from datetime import date
import re
import pandas as pd
import requests
from sqlalchemy import select

from app.data.fetcher_base import BaseFetcher


class XauUsdFetcher(BaseFetcher):
    """
    Fetch international gold (XAU/USD) data.
    Uses Sina Finance for real-time quotes and builds history.
    """

    source = "sina"

    async def fetch(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        """Get latest XAU/USD quote from Sina Finance."""
        try:
            url = "https://hq.sinajs.cn/list=hf_XAU"
            headers = {"Referer": "https://finance.sina.com.cn"}
            r = requests.get(url, headers=headers, timeout=10)
            r.encoding = "gbk"

            # Parse: var hq_str_hf_XAU="price,open,...,date,name";
            match = re.search(r'"([^"]*)"', r.text)
            if not match:
                return pd.DataFrame()

            parts = match.group(1).split(",")
            if len(parts) < 13:
                return pd.DataFrame()

            # Fields: 0=最新价, 1=开盘, 6=时间, 7=昨收, 12=日期, 13=名称
            close_price = float(parts[0])
            open_price = float(parts[1]) if parts[1] else close_price
            high_price = float(parts[4]) if parts[4] else close_price
            low_price = float(parts[5]) if parts[5] else close_price
            trade_date_str = parts[12] if len(parts) > 12 else str(date.today())
            trade_date = date.fromisoformat(trade_date_str)

            df = pd.DataFrame([{
                "date": trade_date,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
            }])
            return df

        except Exception:
            return pd.DataFrame()

    async def save_to_db(self, df: pd.DataFrame, session) -> int:
        """Save XAU/USD data to database."""
        from app.models.gold_price import GoldPriceXauUsd

        count = 0
        for _, row in df.iterrows():
            stmt = select(GoldPriceXauUsd).where(GoldPriceXauUsd.trade_date == row["date"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing is None:
                session.add(GoldPriceXauUsd(
                    trade_date=row["date"],
                    open=float(row.get("open", row["close"])),
                    high=float(row.get("high", row["close"])),
                    low=float(row.get("low", row["close"])),
                    close=float(row["close"]),
                    source=self.source,
                ))
                count += 1
            else:
                # Update existing with latest data
                existing.open = float(row.get("open", row["close"]))
                existing.high = float(row.get("high", row["close"]))
                existing.low = float(row.get("low", row["close"]))
                existing.close = float(row["close"])
                existing.source = self.source

        return count


class OilFetcher(BaseFetcher):
    """Fetch crude oil price (Brent) from Sina Finance."""

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
        from app.models.factor import FactorOil

        count = 0
        for _, row in df.iterrows():
            stmt = select(FactorOil).where(FactorOil.trade_date == row["date"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing is None:
                session.add(FactorOil(trade_date=row["date"], close=float(row["close"]), source=self.source))
                count += 1
            else:
                existing.close = float(row["close"])
                existing.source = self.source
        return count


class DxyFetcher(BaseFetcher):
    """Fetch US Dollar Index from Sina Finance."""

    source = "sina"

    async def fetch(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        """Get latest DXY quote."""
        try:
            url = "https://hq.sinajs.cn/list=hf_DINIW"
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

            df = pd.DataFrame([{
                "date": trade_date,
                "close": close_price,
            }])
            return df

        except Exception:
            return pd.DataFrame()

    async def save_to_db(self, df: pd.DataFrame, session) -> int:
        """Save DXY data."""
        from app.models.factor import FactorDxy

        count = 0
        for _, row in df.iterrows():
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


class VixFetcher(BaseFetcher):
    """Fetch VIX from Sina Finance."""

    source = "sina"

    async def fetch(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        """Get latest VIX quote."""
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

            df = pd.DataFrame([{
                "date": trade_date,
                "close": close_price,
            }])
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
