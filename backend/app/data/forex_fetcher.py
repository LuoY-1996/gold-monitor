"""USD/CNY exchange rate fetcher."""

from datetime import date
import pandas as pd
import requests
from bs4 import BeautifulSoup
from sqlalchemy import select

from app.data.fetcher_base import BaseFetcher


class UsdCnyFetcher(BaseFetcher):
    """
    Fetch USD/CNY exchange rate (current spot + historical).
    Uses akshare fx_spot_quote for onshore rate and forex_hist_em for offshore history.
    """

    source = "akshare"

    async def fetch_current(self) -> pd.DataFrame:
        """Fetch current USD/CNY onshore spot rate."""
        import akshare as ak

        try:
            spot_df = ak.fx_spot_quote()
            if spot_df.empty:
                return pd.DataFrame()

            for _, row in spot_df.iterrows():
                if str(row.iloc[0]) == "USD/CNY":
                    today = date.today()
                    rate = float(row.iloc[1])
                    return pd.DataFrame([{
                        "date": today,
                        "close": rate,
                        "source_type": "onshore",
                    }])
        except Exception as e:
            print(f"[forex] Spot fetch error: {e}")

        return pd.DataFrame()

    async def _fetch_sina_page(self, start_date: date, end_date: date) -> list[dict]:
        """Fetch one page of Sina BOC forex data (max ~50 rows per request)."""
        url = "https://biz.finance.sina.com.cn/forex/forex.php"
        params = {
            "startdate": start_date.isoformat(),
            "enddate": end_date.isoformat(),
            "money_code": "USD",
            "type": "0",
        }
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.sina.com.cn/",
        }
        r = requests.get(url, params=params, headers=headers, timeout=30)
        r.encoding = "gbk"

        soup = BeautifulSoup(r.text, "html.parser")
        tables = soup.find_all("table")
        if len(tables) < 2:
            return []

        rows = tables[1].find_all("tr")
        data = []
        for row in rows[1:]:  # Skip header
            cells = row.find_all("td")
            if len(cells) < 5:
                continue
            date_str = cells[0].get_text(strip=True)
            middle_rate_str = cells[4].get_text(strip=True)  # 中间价
            if middle_rate_str == "--" or not middle_rate_str:
                continue
            try:
                trade_date = date.fromisoformat(date_str)
                rate = float(middle_rate_str) / 100.0  # 分 → 元
                data.append({"date": trade_date, "close": rate})
            except (ValueError, TypeError):
                continue
        return data

    async def fetch_history(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        """Fetch USD/CNY historical data from Sina BOC central parity rate.

        Sina paginates ~50 rows per request, so we fetch in 6-month chunks.
        Returns PBOC daily central parity rate (中间价).
        """
        from datetime import timedelta

        if start_date is None:
            start_date = date(2015, 1, 1)
        if end_date is None:
            end_date = date.today()

        all_data: list[dict] = []
        chunk_start = start_date
        chunk_size = timedelta(days=180)  # ~6 months per request

        try:
            while chunk_start <= end_date:
                chunk_end = min(chunk_start + chunk_size, end_date)
                page_data = await self._fetch_sina_page(chunk_start, chunk_end)
                all_data.extend(page_data)
                chunk_start = chunk_end + timedelta(days=1)

            if not all_data:
                return pd.DataFrame()

            # Deduplicate by date
            seen = set()
            unique = []
            for d in all_data:
                if d["date"] not in seen:
                    seen.add(d["date"])
                    unique.append(d)

            result = pd.DataFrame(unique)
            result = result.sort_values("date")
            result["open"] = None
            result["high"] = None
            result["low"] = None
            result["source_type"] = "sina_boc_central_parity"
            return result

        except Exception as e:
            print(f"[forex] Sina BOC history fetch error: {e}")
            return pd.DataFrame()

    async def fetch(self, start_date=None, end_date=None) -> pd.DataFrame:
        """Fetch current rate only (fast). Use fetch_history for bulk data."""
        return await self.fetch_current()

    async def save_to_db(self, df: pd.DataFrame, session) -> int:
        """Save USD/CNY data."""
        from app.models.factor import FactorUsdCny

        count = 0
        for _, row in df.iterrows():
            if pd.isna(row.get("close")):
                continue

            close_val = float(row["close"])

            stmt = select(FactorUsdCny).where(FactorUsdCny.trade_date == row["date"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            source = str(row.get("source_type", self.source))

            if existing is None:
                session.add(FactorUsdCny(
                    trade_date=row["date"],
                    close=close_val,
                    open=float(row["open"]) if pd.notna(row.get("open")) else None,
                    high=float(row["high"]) if pd.notna(row.get("high")) else None,
                    low=float(row["low"]) if pd.notna(row.get("low")) else None,
                    source=source,
                ))
                count += 1
            else:
                existing.close = close_val
                if pd.notna(row.get("open")):
                    existing.open = float(row["open"])
                if pd.notna(row.get("high")):
                    existing.high = float(row["high"])
                if pd.notna(row.get("low")):
                    existing.low = float(row["low"])
                existing.source = source

        return count
