"""Geopolitical risk index computation + news sentiment scraping.

Computes a daily geopolitical risk score (1-10) from:
1. Recent event intensity (exponentially decaying, 50% weight)
2. Active conflict regional risk (30% weight)
3. News headline sentiment from Jin10 / Sina Finance (20% weight)

News sources:
- Jin10 (金十数据): financial flash news, gold-related headlines
- Sina Finance gold channel: broader coverage
"""

import asyncio
import json
import logging
import math
import re
from datetime import date, timedelta
from collections import Counter

import pandas as pd
import requests
from bs4 import BeautifulSoup
from sqlalchemy import select

from app.data.fetcher_base import BaseFetcher

logger = logging.getLogger(__name__)

# ── News sentiment keyword dictionaries ──

NEGATIVE_KEYWORDS = [
    "冲突", "战争", "制裁", "紧张", "升级", "威胁", "攻击", "封锁",
    "危机", "恐慌", "暴跌", "衰退", "崩溃", "违约", "暴雷",
    "空袭", "导弹", "军事", "演习", "动员", "入侵", "占领",
    "关税", "脱钩", "遏制", "围堵", "禁运", "断交",
    "通胀", "加息", "鹰派", "缩表", "收紧",
    "违约", "抛售", "赎回", "踩踏", "熔断",
    "极端", "灾难", "紧急", "警告", "威胁",
    "恶化", "下调", "萎缩", "滞胀", "过热",
]

POSITIVE_KEYWORDS = [
    "缓和", "谈判", "停火", "和平", "合作", "稳定",
    "复苏", "增长", "反弹", "突破", "新高",
    "降息", "宽松", "鸽派", "放水", "刺激",
    "协议", "达成", "签署", "合作", "对话",
    "回暖", "修复", "企稳", "改善", "向好",
    "乐观", "信心", "利好", "强劲", "超预期",
]

GOLD_BULLISH = [
    "避险", "央行购金", "增持黄金", "去美元", "金价上涨",
    "黄金储备", "地缘风险", "中东局势", "俄乌",
    "实际利率下行", "美元走弱",
]

GOLD_BEARISH = [
    "风险偏好", "股市大涨", "美元走强", "利率走高",
    "金价下跌", "黄金ETF流出",
]

# ── News scraping ──

SINA_GOLD_URL = "https://finance.sina.com.cn/gold/"
JIN10_FLASH_URL = "https://flash-api.jin10.com/get_flash_list"
JIN10_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.jin10.com/",
}


def _analyze_sentiment(headlines: list[str]) -> dict:
    """Simple keyword-based sentiment analysis on a list of headlines.

    Returns dict with: sentiment_score (-1 to 1), negative_count, positive_count,
    gold_bullish_count, gold_bearish_count, total_headlines
    """
    if not headlines:
        return {
            "sentiment_score": None,
            "negative_count": 0,
            "positive_count": 0,
            "gold_bullish_count": 0,
            "gold_bearish_count": 0,
            "total_headlines": 0,
        }

    neg_count = 0
    pos_count = 0
    bull_count = 0
    bear_count = 0

    for text in headlines:
        for kw in NEGATIVE_KEYWORDS:
            if kw in text:
                neg_count += 1
                break
        for kw in POSITIVE_KEYWORDS:
            if kw in text:
                pos_count += 1
                break
        for kw in GOLD_BULLISH:
            if kw in text:
                bull_count += 1
                break
        for kw in GOLD_BEARISH:
            if kw in text:
                bear_count += 1
                break

    total = len(headlines)
    # Score: range -1 to 1, with gold-bullish bias giving a slight positive shift
    raw_score = (neg_count - pos_count) / max(total, 1)
    # Clamp
    sentiment_score = max(-1.0, min(1.0, raw_score))

    return {
        "sentiment_score": round(sentiment_score, 4),
        "negative_count": neg_count,
        "positive_count": pos_count,
        "gold_bullish_count": bull_count,
        "gold_bearish_count": bear_count,
        "total_headlines": total,
    }


def _scrape_sina_gold() -> list[str]:
    """Scrape Sina Finance gold channel headlines."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(SINA_GOLD_URL, headers=headers, timeout=15)
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        headlines = []
        # Find news list items
        for item in soup.select(".news-item h2 a, .news-item h3 a, .news-list li a"):
            text = item.get_text(strip=True)
            if text and len(text) > 5:
                headlines.append(text)

        # Also try generic link extraction from news blocks
        for item in soup.select(".feed-card-item h2 a, .news-item h2, .m-list li a"):
            text = item.get_text(strip=True)
            if text and len(text) > 5:
                headlines.append(text)

        return headlines[:50]  # Limit to 50
    except Exception as e:
        logger.warning(f"[geo] Sina scrape error: {e}")
        return []


def _scrape_jin10_flash() -> list[str]:
    """Try to fetch Jin10 flash news headlines.

    Jin10 has an internal API that may require auth. Falls back gracefully.
    """
    try:
        params = {
            "channel": "-8200",  # General financial news
            "vip": "1",
            "_": str(int(asyncio.get_event_loop().time() * 1000)),
        }
        r = requests.get(JIN10_FLASH_URL, headers=JIN10_HEADERS, params=params, timeout=10)
        if r.status_code != 200:
            return []

        data = r.json()
        if "data" not in data:
            return []

        headlines = []
        for item in data["data"]:
            content = item.get("data", {}).get("content", "")
            if content:
                # Strip HTML tags
                text = re.sub(r"<[^>]+>", "", content)
                headlines.append(text)
        return headlines[:50]
    except Exception as e:
        logger.debug(f"[geo] Jin10 API not available: {e}")
        return []


def _scrape_news_headlines() -> list[str]:
    """Aggregate headlines from multiple sources."""
    all_headlines = []

    # Sina Finance gold channel (most reliable in China)
    sina_headlines = _scrape_sina_gold()
    all_headlines.extend(sina_headlines)

    # Jin10 flash (optional, may not work)
    jin10_headlines = _scrape_jin10_flash()
    all_headlines.extend(jin10_headlines)

    return all_headlines


# ── Risk score computation ──


async def _get_recent_events(session, lookback_days: int = 30) -> list[dict]:
    """Load recent geopolitical events from the database."""
    from app.models.geopolitics import GeopoliticalEvent

    cutoff = date.today() - timedelta(days=lookback_days)
    stmt = (
        select(GeopoliticalEvent)
        .where(GeopoliticalEvent.event_date >= cutoff)
        .order_by(GeopoliticalEvent.event_date.desc())
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "event_date": r.event_date,
            "impact": r.impact,
            "direction": r.direction,
            "category": r.category,
            "risk_regions": json.loads(r.risk_regions) if r.risk_regions else [],
        }
        for r in rows
    ]


def _compute_event_intensity(events: list[dict], target_date: date) -> float:
    """Compute event intensity score with exponential decay.

    intensity = sum(impact_i * e^(-days_since_i / 15))
    Normalized to 1-10 scale.
    """
    if not events:
        return 1.0

    total = 0.0
    for ev in events:
        days_since = (target_date - ev["event_date"]).days
        if days_since < 0:
            continue
        decay = math.exp(-days_since / 15.0)  # Half-life ~10 days
        total += ev["impact"] * decay

    # Normalize: max reasonable is ~15 (3 events of impact=3 on same day)
    return 1.0 + min(9.0, total * 3.0)


def _compute_regional_risk(events: list[dict]) -> tuple[int, dict]:
    """Count active conflict regions and assign scores (1-3 each).

    Returns (active_conflict_count, regional_scores dict).
    """
    regions = Counter()
    for ev in events:
        for region in ev.get("risk_regions", []):
            # Impact adds to regional score
            regions[region] = max(regions[region], ev["impact"])

    # Clamp each region to 1-3
    scores = {r: min(3, max(1, v)) for r, v in regions.items()}
    return len(scores), scores


def _news_sentiment_to_risk(sentiment_score: float | None) -> float:
    """Convert sentiment (-1 to 1) to risk contribution (1-10)."""
    if sentiment_score is None:
        return 5.0  # Neutral when no data
    # -1 sentiment → 10 risk, +1 sentiment → 1 risk, 0 → 5.5
    return 5.5 - sentiment_score * 4.5


def compute_risk_score(
    events: list[dict],
    target_date: date,
    sentiment_result: dict,
) -> dict:
    """Compute the aggregate daily geopolitical risk score (1-10).

    Weights:
    - Event intensity: 50%
    - Regional risk: 30%
    - News sentiment: 20%
    """
    event_intensity = _compute_event_intensity(events, target_date)
    active_conflicts, regional_scores = _compute_regional_risk(events)

    # Regional risk: sum of regional scores (typically 3-9), normalize to 1-10
    total_regional = sum(regional_scores.values()) if regional_scores else 3
    regional_component = 1.0 + (total_regional - 3) / 6 * 9  # Map 3→1, 9→10

    # News sentiment to risk
    news_component = _news_sentiment_to_risk(sentiment_result.get("sentiment_score"))

    # Weighted combination
    risk_score = (
        0.5 * event_intensity
        + 0.3 * regional_component
        + 0.2 * news_component
    )

    return {
        "risk_score": round(min(10.0, max(1.0, risk_score)), 2),
        "event_intensity": round(event_intensity, 2),
        "active_conflicts": active_conflicts,
        "news_sentiment": sentiment_result.get("sentiment_score"),
        "news_headline_count": sentiment_result.get("total_headlines", 0),
        "regional_scores": json.dumps(regional_scores) if regional_scores else None,
    }


# ── Main fetcher class ──


class GeopoliticalRiskFetcher(BaseFetcher):
    """Compute and save daily geopolitical risk index."""

    source = "computed"

    async def fetch(
        self,
        session,
        target_date: date | None = None,
        events_lookback: int = 30,
    ) -> pd.DataFrame:
        """Compute risk score for a given date (default: today)."""
        if target_date is None:
            target_date = date.today()

        # Load recent events
        events = await _get_recent_events(session, lookback_days=events_lookback)

        # Scrape news headlines for sentiment
        headlines = _scrape_news_headlines()
        sentiment_result = _analyze_sentiment(headlines)

        # Compute risk score
        result = compute_risk_score(events, target_date, sentiment_result)

        df = pd.DataFrame([{
            "date": target_date,
            **result,
        }])
        return df

    async def save_to_db(self, df: pd.DataFrame, session) -> int:
        """Save daily geopolitical risk index."""
        from app.models.geopolitics import GeopoliticalRiskIndex

        count = 0
        for _, row in df.iterrows():
            stmt = select(GeopoliticalRiskIndex).where(
                GeopoliticalRiskIndex.trade_date == row["date"]
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing is None:
                session.add(GeopoliticalRiskIndex(
                    trade_date=row["date"],
                    risk_score=float(row["risk_score"]),
                    event_intensity=float(row["event_intensity"]),
                    active_conflicts=int(row.get("active_conflicts", 0)),
                    news_sentiment=(
                        float(row["news_sentiment"])
                        if pd.notna(row.get("news_sentiment"))
                        else None
                    ),
                    news_headline_count=(
                        int(row["news_headline_count"])
                        if pd.notna(row.get("news_headline_count"))
                        else None
                    ),
                    regional_scores=row.get("regional_scores"),
                    source=self.source,
                ))
                count += 1
            else:
                # Update with latest computed values
                existing.risk_score = float(row["risk_score"])
                existing.event_intensity = float(row["event_intensity"])
                existing.active_conflicts = int(row.get("active_conflicts", 0))
                if pd.notna(row.get("news_sentiment")):
                    existing.news_sentiment = float(row["news_sentiment"])
                if pd.notna(row.get("news_headline_count")):
                    existing.news_headline_count = int(row["news_headline_count"])
                if row.get("regional_scores"):
                    existing.regional_scores = row["regional_scores"]

        return count
