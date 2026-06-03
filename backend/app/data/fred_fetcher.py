"""FRED (Federal Reserve Economic Data) fetcher for CPI and Treasury yields."""

from datetime import date
import pandas as pd
from sqlalchemy import select

from app.data.fetcher_base import BaseFetcher
from app.config import FRED_API_KEY


FRED_SERIES = {
    "cpi": "CPIAUCSL",       # Consumer Price Index (monthly)
    "core_cpi": "CPILFESL",  # Core CPI (ex food & energy)
    "treasury_2y": "DGS2",   # 2-Year Treasury
    "treasury_10y": "DGS10", # 10-Year Treasury
}


class FREDFetcher(BaseFetcher):
    """Fetch economic data from FRED (St. Louis Fed)."""

    source = "fredapi"

    def __init__(self, series_key: str):
        """
        Args:
            series_key: One of 'cpi', 'core_cpi', 'treasury_2y', 'treasury_10y'
        """
        self.series_key = series_key
        self.series_id = FRED_SERIES[series_key]

    async def fetch(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        """Download data from FRED API."""
        if not FRED_API_KEY:
            return pd.DataFrame()  # Skip if no API key configured

        from fredapi import Fred

        if start_date is None:
            start_date = date(2015, 1, 1)
        if end_date is None:
            end_date = date.today()

        try:
            fred = Fred(api_key=FRED_API_KEY)
            series = fred.get_series(
                self.series_id,
                observation_start=start_date,
                observation_end=end_date,
            )
            df = pd.DataFrame({"date": series.index, "value": series.values})
            df["date"] = pd.to_datetime(df["date"]).dt.date
            df = df.dropna()
            return df
        except Exception:
            return pd.DataFrame()

    async def save_to_db(self, df: pd.DataFrame, session) -> int:
        """Save FRED data to database."""
        from app.models.factor import FactorCpi, FactorTreasury10y

        if self.series_key == "cpi":
            model = FactorCpi
            count = 0
            for _, row in df.iterrows():
                stmt = select(model).where(model.report_date == row["date"])
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing is None:
                    data = {
                        "report_date": row["date"],
                        "cpi_value": float(row["value"]),
                        "source": self.source,
                    }
                    session.add(model(**data))
                    count += 1
            return count

        elif self.series_key == "treasury_10y":
            model = FactorTreasury10y
            count = 0
            for _, row in df.iterrows():
                stmt = select(model).where(model.trade_date == row["date"])
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing is None:
                    data = {
                        "trade_date": row["date"],
                        "yield_value": float(row["value"]),
                        "source": self.source,
                    }
                    session.add(model(**data))
                    count += 1
            return count

        return 0
