"""TIPS Yield & Breakeven Inflation fetcher — FRED CSV direct read (no API key needed)."""

from datetime import date
import pandas as pd
from sqlalchemy import select

from app.data.fetcher_base import BaseFetcher


class TipsBreakevenFetcher(BaseFetcher):
    """Fetch 10Y TIPS yield and compute breakeven inflation rate."""

    source = "fred"

    async def fetch(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        try:
            if start_date is None:
                start_date = date(2015, 1, 1)
            if end_date is None:
                end_date = date.today()

            tips_df = self._fetch_fred_csv("DFII10", start_date, end_date)
            treasury_df = self._fetch_fred_csv("DGS10", start_date, end_date)

            if tips_df.empty or treasury_df.empty:
                return pd.DataFrame()

            merged = pd.merge(tips_df, treasury_df, on="date", suffixes=("_tips", "_treasury"))
            merged["breakeven_rate"] = merged["value_treasury"] - merged["value_tips"]
            merged = merged.dropna(subset=["breakeven_rate"])
            merged = merged.rename(columns={"value_tips": "tips_10y", "value_treasury": "treasury_10y"})

            return merged[["date", "tips_10y", "treasury_10y", "breakeven_rate"]]

        except Exception as e:
            print(f"[tips] Fetch failed: {e}")
            return pd.DataFrame()

    def _fetch_fred_csv(self, series_id: str, start_date: date, end_date: date) -> pd.DataFrame:
        import requests
        from io import StringIO

        url = (
            "https://fred.stlouisfed.org/graph/fredgraph.csv"
            f"?id={series_id}"
            f"&cosd={start_date.isoformat()}"
            f"&coed={end_date.isoformat()}"
        )
        headers = {"User-Agent": "Mozilla/5.0"}

        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()

        df = pd.read_csv(StringIO(r.text), parse_dates=["DATE"])
        df["date"] = pd.to_datetime(df["DATE"]).dt.date
        df["value"] = pd.to_numeric(df[df.columns[1]], errors="coerce")
        df = df.dropna(subset=["value"])
        return df[["date", "value"]]

    async def save_to_db(self, df: pd.DataFrame, session) -> int:
        from app.models.factor import FactorBreakevenInflation

        count = 0
        for _, row in df.iterrows():
            stmt = select(FactorBreakevenInflation).where(FactorBreakevenInflation.trade_date == row["date"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            data = {
                "trade_date": row["date"],
                "breakeven_rate": float(row["breakeven_rate"]),
                "treasury_10y": float(row["treasury_10y"]) if pd.notna(row.get("treasury_10y")) else None,
                "tips_10y": float(row["tips_10y"]) if pd.notna(row.get("tips_10y")) else None,
                "source": self.source,
            }

            if existing is None:
                session.add(FactorBreakevenInflation(**data))
                count += 1
            else:
                existing.breakeven_rate = data["breakeven_rate"]
                if data["treasury_10y"] is not None:
                    existing.treasury_10y = data["treasury_10y"]
                if data["tips_10y"] is not None:
                    existing.tips_10y = data["tips_10y"]
        return count
