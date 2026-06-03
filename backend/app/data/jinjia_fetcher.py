"""Jinjia.com.cn data fetcher for real-time gold prices.

Scrapes https://www.jinjia.com.cn/gngold/ (domestic) and
https://www.jinjia.com.cn/gjgold/ (international) for near-real-time gold prices.
"""

from datetime import date, datetime
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from sqlalchemy import select

from app.data.fetcher_base import BaseFetcher

JINJIA_DOMESTIC_URL = "https://www.jinjia.com.cn/gngold/"
JINJIA_INTERNATIONAL_URL = "https://www.jinjia.com.cn/gjgold/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def _parse_jinjia_page(html: str, page_type: str) -> list[dict]:
    """
    Parse a jinjia.com.cn gold price page.

    Args:
        html: Raw HTML content
        page_type: 'domestic' or 'international'
            - domestic: open=开盘价, prec=昨收价
            - international: open=最高价, prec=最低价

    Returns:
        List of dicts with: name, price, change_pct, open_val, prec_val, update_time
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Find all <li> items in the price list
    list_div = soup.find("div", class_="list")
    if not list_div:
        return results

    for li in list_div.find_all("li"):
        # Skip header row
        if "bgx" in li.get("class", []):
            continue

        name_div = li.find("div", class_="name")
        new_div = li.find("div", class_="new")
        rise_div = li.find("div", class_="rise")
        open_div = li.find("div", class_="open")
        prec_div = li.find("div", class_="prec")
        time_div = li.find("div", class_="time")

        if not name_div or not new_div:
            continue

        name = name_div.get_text(strip=True)
        price_span = new_div.find("span")
        price_text = price_span.get_text(strip=True) if price_span else new_div.get_text(strip=True)
        rise_text = rise_div.get_text(strip=True) if rise_div else ""
        open_text = open_div.get_text(strip=True) if open_div else ""
        prec_text = prec_div.get_text(strip=True) if prec_div else ""
        time_text = time_div.get_text(strip=True) if time_div else ""

        try:
            price = float(price_text.replace(",", ""))
        except ValueError:
            continue

        # Parse change percentage
        change_pct = None
        if rise_text:
            pct_match = re.search(r"([+-]?[\d.]+)%", rise_text)
            if pct_match:
                change_pct = float(pct_match.group(1))

        # Parse open/prec values
        try:
            open_val = float(open_text.replace(",", "")) if open_text else None
        except ValueError:
            open_val = None

        try:
            prec_val = float(prec_text.replace(",", "")) if prec_text else None
        except ValueError:
            prec_val = None

        result = {
            "name": name,
            "price": price,
            "change_pct": change_pct,
            "update_time": time_text,
        }

        if page_type == "domestic":
            result["open"] = open_val  # 开盘价
            result["prev_close"] = prec_val  # 昨收价
        else:
            result["high"] = open_val  # 最高价
            result["low"] = prec_val  # 最低价

        results.append(result)

    return results


class JinjiaDomesticFetcher(BaseFetcher):
    """Fetch domestic gold prices from jinjia.com.cn."""

    source = "jinjia"

    async def fetch(self, start_date=None, end_date=None) -> pd.DataFrame:
        """Scrape domestic gold page for AU9999 and other prices."""
        try:
            r = requests.get(JINJIA_DOMESTIC_URL, headers=HEADERS, timeout=15)
            r.encoding = "utf-8"
            data = _parse_jinjia_page(r.text, "domestic")

            if not data:
                return pd.DataFrame()

            # Find AU9999 specifically
            au9999 = None
            today_gold = None
            for item in data:
                if "AU9999" in item["name"] or "Au9999" in item["name"]:
                    au9999 = item
                if "今日金价" in item["name"] or "黄金价格" in item["name"]:
                    if today_gold is None:
                        today_gold = item

            # Use AU9999 as primary, fallback to first item
            target = au9999 or today_gold or data[0]

            today = date.today()
            df = pd.DataFrame([{
                "date": today,
                "open": target.get("open"),
                "high": target.get("open"),  # Approximate
                "low": target.get("prev_close"),  # Approximate
                "close": target["price"],
            }])
            return df

        except Exception as e:
            print(f"[jinjia] Domestic fetch error: {e}")
            return pd.DataFrame()

    async def save_to_db(self, df: pd.DataFrame, session) -> int:
        """Save Au99.99 data."""
        from app.models.gold_price import GoldPriceAu9999

        count = 0
        for _, row in df.iterrows():
            stmt = select(GoldPriceAu9999).where(GoldPriceAu9999.trade_date == row["date"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            close_val = float(row["close"])
            if existing is None:
                session.add(GoldPriceAu9999(
                    trade_date=row["date"],
                    open=float(row["open"]) if pd.notna(row.get("open")) else None,
                    high=float(row["high"]) if pd.notna(row.get("high")) else None,
                    low=float(row["low"]) if pd.notna(row.get("low")) else None,
                    close=close_val,
                    source=self.source,
                ))
                count += 1
            else:
                # Update with latest price
                existing.open = float(row["open"]) if pd.notna(row.get("open")) else existing.open
                existing.high = float(row["high"]) if pd.notna(row.get("high")) else existing.high
                existing.low = float(row["low"]) if pd.notna(row.get("low")) else existing.low
                existing.close = close_val
                existing.source = self.source

        return count


class JinjiaInternationalFetcher(BaseFetcher):
    """Fetch international gold prices from jinjia.com.cn."""

    source = "jinjia"

    async def fetch(self, start_date=None, end_date=None) -> pd.DataFrame:
        """Scrape international gold page for London gold (XAU/USD)."""
        try:
            r = requests.get(JINJIA_INTERNATIONAL_URL, headers=HEADERS, timeout=15)
            r.encoding = "utf-8"
            data = _parse_jinjia_page(r.text, "international")

            if not data:
                return pd.DataFrame()

            # Find London gold
            london_gold = None
            for item in data:
                if "伦敦金" in item["name"]:
                    london_gold = item
                    break

            target = london_gold or data[0]

            today = date.today()
            df = pd.DataFrame([{
                "date": today,
                "open": target["price"],  # No true open from page
                "high": target.get("high"),
                "low": target.get("low"),
                "close": target["price"],
            }])
            return df

        except Exception as e:
            print(f"[jinjia] International fetch error: {e}")
            return pd.DataFrame()

    async def save_to_db(self, df: pd.DataFrame, session) -> int:
        """Save XAU/USD data."""
        from app.models.gold_price import GoldPriceXauUsd

        count = 0
        for _, row in df.iterrows():
            stmt = select(GoldPriceXauUsd).where(GoldPriceXauUsd.trade_date == row["date"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            close_val = float(row["close"])
            if existing is None:
                session.add(GoldPriceXauUsd(
                    trade_date=row["date"],
                    open=float(row["open"]) if pd.notna(row.get("open")) else None,
                    high=float(row["high"]) if pd.notna(row.get("high")) else None,
                    low=float(row["low"]) if pd.notna(row.get("low")) else None,
                    close=close_val,
                    source=self.source,
                ))
                count += 1
            else:
                existing.open = float(row["open"]) if pd.notna(row.get("open")) else existing.open
                existing.high = float(row["high"]) if pd.notna(row.get("high")) else existing.high
                existing.low = float(row["low"]) if pd.notna(row.get("low")) else existing.low
                existing.close = close_val
                existing.source = self.source

        return count
