"""Shanghai Gold Exchange (Au99.99) fetcher using AKShare."""

from datetime import date
import pandas as pd
from sqlalchemy import select

from app.data.fetcher_base import BaseFetcher


class Au9999Fetcher(BaseFetcher):
    """Fetch Shanghai Gold Exchange Au99.99 daily prices via AKShare."""

    source = "akshare"

    async def fetch(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        """Download Au99.99 historical data from SGE."""
        import akshare as ak

        if start_date is None:
            start_date = date(2015, 1, 1)
        if end_date is None:
            end_date = date.today()

        try:
            df = ak.spot_hist_sge()
            if df.empty:
                return pd.DataFrame()

            # Columns: ['date', 'open', 'close', 'low', 'high']
            df["date"] = pd.to_datetime(df["date"]).dt.date
            df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
            df = df.sort_values("date")
            return df

        except Exception:
            return pd.DataFrame()

    async def save_to_db(self, df: pd.DataFrame, session) -> int:
        """Save Au99.99 prices to database."""
        from app.models.gold_price import GoldPriceAu9999

        count = 0
        for _, row in df.iterrows():
            stmt = select(GoldPriceAu9999).where(GoldPriceAu9999.trade_date == row["date"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing is None:
                close_val = float(row["close"])
                session.add(GoldPriceAu9999(
                    trade_date=row["date"],
                    open=float(row.get("open", close_val)) if pd.notna(row.get("open")) else None,
                    high=float(row.get("high", close_val)) if pd.notna(row.get("high")) else None,
                    low=float(row.get("low", close_val)) if pd.notna(row.get("low")) else None,
                    close=close_val,
                    source=self.source,
                ))
                count += 1

        return count
