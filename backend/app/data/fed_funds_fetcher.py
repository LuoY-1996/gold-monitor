"""Federal Funds Rate fetcher — AKShare macro_bank_usa_interest_rate."""

from datetime import date
import pandas as pd
from sqlalchemy import select

from app.data.fetcher_base import BaseFetcher


class FedFundsFetcher(BaseFetcher):
    """Fetch US Federal Funds Target Rate (upper bound) from AKShare."""

    source = "akshare"

    async def fetch(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        """Fetch Fed Funds rate history from AKShare."""
        try:
            import akshare as ak
            df = ak.macro_bank_usa_interest_rate()
            if df.empty:
                return df

            # Column names are Chinese; rename to standard fields
            col_map = {
                df.columns[0]: "name",      # 商品
                df.columns[1]: "date",      # 日期
                df.columns[2]: "rate",      # 今值
                df.columns[3]: "forecast",  # 预测值
                df.columns[4]: "prev",      # 前值
            }
            df = df.rename(columns=col_map)
            df["date"] = pd.to_datetime(df["date"]).dt.date
            df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
            df["prev"] = pd.to_numeric(df["prev"], errors="coerce")

            # Only keep rows with actual rate data (not forecasts/FOMC meeting dates with NaN rate)
            df = df.dropna(subset=["rate"])
            df = df.sort_values("date")

            if start_date:
                df = df[df["date"] >= start_date]
            if end_date:
                df = df[df["date"] <= end_date]

            return df[["date", "rate", "prev"]]
        except Exception as e:
            print(f"[fed_funds] AKShare fetch failed: {e}")
            return pd.DataFrame()

    async def save_to_db(self, df: pd.DataFrame, session) -> int:
        """Save Fed Funds rate data."""
        from app.models.factor import FactorFedFunds

        count = 0
        for _, row in df.iterrows():
            stmt = select(FactorFedFunds).where(FactorFedFunds.trade_date == row["date"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            rate_val = float(row["rate"])
            prev_val = float(row["prev"]) if pd.notna(row.get("prev")) else None

            if existing is None:
                session.add(FactorFedFunds(
                    trade_date=row["date"],
                    rate=rate_val,
                    rate_prev=prev_val,
                    source=self.source,
                ))
                count += 1
            else:
                existing.rate = rate_val
                existing.rate_prev = prev_val

        return count
