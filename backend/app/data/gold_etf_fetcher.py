"""Gold ETF Holdings fetcher — gold.org API (World Gold Council).

Fetches weekly North America gold ETF holdings in tonnes.
Data from gold.org/goldhub/data/gold-etfs-holdings-and-flows
~1210 weekly data points, covering 2003-present.
"""

from datetime import date, datetime
import pandas as pd
from sqlalchemy import select

from app.data.fetcher_base import BaseFetcher


GOLD_ORG_API = (
    "https://fsapi.gold.org/api/v11/charts/etfv2/revised/holdings-chart2"
    "?etf=GLD"
)


class GoldEtfFetcher(BaseFetcher):
    """Fetch gold ETF holdings (North America region) from World Gold Council."""

    source = "gold_org"

    async def fetch(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        """Fetch weekly gold ETF holdings in tonnes."""
        try:
            import requests

            r = requests.get(GOLD_ORG_API, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            r.raise_for_status()
            data = r.json()

            chart = data.get("chartData", {}).get("data", {})
            weekly = chart.get("Weekly", {})
            tonnes_data = weekly.get("tonnes", {})
            rows = tonnes_data.get("set", [])

            if not rows:
                return pd.DataFrame()

            records = []
            for row in rows:
                ts = row[0]  # Unix timestamp in milliseconds
                na_tonnes = row[1]  # North America holdings (tonnes)
                eu_tonnes = row[2]
                asia_tonnes = row[3]
                other_tonnes = row[4]
                gold_price = row[5]

                if na_tonnes is None:
                    continue

                d = datetime.fromtimestamp(ts / 1000).date()

                if start_date and d < start_date:
                    continue
                if end_date and d > end_date:
                    continue

                records.append({
                    "date": d,
                    "holdings_tons": float(na_tonnes),
                    "europe_tons": float(eu_tonnes) if eu_tonnes else 0,
                    "asia_tons": float(asia_tonnes) if asia_tonnes else 0,
                    "other_tons": float(other_tonnes) if other_tonnes else 0,
                    "gold_price_usd": float(gold_price) if gold_price else None,
                })

            df = pd.DataFrame(records)
            df = df.drop_duplicates(subset=["date"])
            df = df.sort_values("date")
            return df

        except Exception as e:
            print(f"[gold_etf] gold.org fetch failed: {e}")
            return pd.DataFrame()

    async def save_to_db(self, df: pd.DataFrame, session) -> int:
        """Save gold ETF holdings data."""
        from app.models.factor import FactorGoldEtf

        count = 0
        for _, row in df.iterrows():
            stmt = select(FactorGoldEtf).where(FactorGoldEtf.trade_date == row["date"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            data = {
                "trade_date": row["date"],
                "holdings_tons": float(row["holdings_tons"]),
                "close_price": float(row["gold_price_usd"]) if pd.notna(row.get("gold_price_usd")) else None,
                "source": self.source,
            }

            if existing is None:
                session.add(FactorGoldEtf(**data))
                count += 1
            else:
                if data["holdings_tons"] is not None:
                    existing.holdings_tons = data["holdings_tons"]
                if data["close_price"] is not None:
                    existing.close_price = data["close_price"]

        return count
