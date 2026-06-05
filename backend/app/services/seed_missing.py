"""Auto-seed missing data sources on startup.

Checks tables that may be empty (gold_etf, breakeven_inflation, etc.)
and fetches their historical data if needed.
"""
import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.gold_etf_fetcher import GoldEtfFetcher
from app.data.tips_fetcher import TipsBreakevenFetcher

logger = logging.getLogger(__name__)


async def _run_fetcher(fetcher, session) -> dict:
    """Run a single fetcher: fetch + save, return result summary."""
    try:
        df = await fetcher.fetch()
        if df is not None and not df.empty:
            count = await fetcher.save_to_db(df, session)
            return {"status": "success", "records": count}
        return {"status": "empty", "records": 0}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


async def seed_missing_data_sources(session: AsyncSession):
    """Check and seed any empty data source tables.

    Called on every PostgreSQL startup after the initial full seed.
    Only fetches data for tables that are currently empty.
    """
    from app.models.factor import FactorGoldEtf, FactorBreakevenInflation

    checks = [
        (FactorGoldEtf, "黄金ETF持仓", GoldEtfFetcher()),
        (FactorBreakevenInflation, "盈亏平衡通胀率", TipsBreakevenFetcher()),
    ]

    for model, label, fetcher in checks:
        try:
            result = await session.execute(select(func.count()).select_from(model))
            count = result.scalar()
            if count == 0:
                print(f"  [seed] {label}: 空表，正在抓取历史数据...")
                r = await _run_fetcher(fetcher, session)
                await session.commit()
                print(f"  [seed] {label}: {r.get('status')} ({r.get('records', 0)} 条)")
            else:
                print(f"  [seed] {label}: 已有 {count} 条数据，跳过")
        except Exception as e:
            print(f"  [seed] {label}: 检查/抓取失败: {e}")
            await session.rollback()
