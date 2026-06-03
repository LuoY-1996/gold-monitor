"""Data fetching orchestrator — coordinates all fetchers and upserts data."""

import asyncio
import logging
from datetime import date

from app.data.yfinance_fetcher import VixFetcher as VixRealtimeFetcher
from app.data.yfinance_fetcher import OilFetcher as OilRealtimeFetcher
from app.data.vix_fetcher import VixHistoryFetcher
from app.data.oil_fetcher import OilHistoryFetcher
from app.data.akshare_fetcher import Au9999Fetcher
from app.data.jinjia_fetcher import JinjiaDomesticFetcher, JinjiaInternationalFetcher
from app.data.forex_fetcher import UsdCnyFetcher
from app.data.macro_fetcher import Treasury10YFetcher, DxyProxyFetcher
from app.data.geopolitics_fetcher import GeopoliticalRiskFetcher

logger = logging.getLogger(__name__)


async def _fetch_one_task(fetcher, start_date, end_date):
    """Run a single fetcher's async fetch method."""
    return await fetcher.fetch(start_date, end_date)


async def _fetch_one(fetcher, label: str, start_date, end_date) -> tuple[str, dict, object]:
    """Fetch data from one source in a thread, return (label, result_dict, (fetcher, df) or None)."""
    try:
        df = await _fetch_one_task(fetcher, start_date, end_date)
        if df is not None and not df.empty:
            return (label, {"status": "success", "records": len(df)}, (fetcher, df))
        else:
            return (label, {"status": "empty", "records": 0}, None)
    except Exception as e:
        logger.error(f"[{label}] fetch failed: {e}")
        return (label, {"status": "failed", "error": str(e)}, None)


async def fetch_all_data(session, start_date: date | None = None, end_date: date | None = None) -> dict:
    """Fetch all data from all sources concurrently, then save to DB sequentially.

    Network fetches run in parallel via thread pool (all fetchers use blocking HTTP).
    DB saves run sequentially to avoid SQLite database-locked errors.
    """
    results = {}

    # Phase 1: Run all network fetches concurrently in thread pool
    fetch_tasks = [
        # Gold prices (real-time)
        _fetch_one(JinjiaInternationalFetcher(), "xau_usd", start_date, end_date),
        _fetch_one(JinjiaDomesticFetcher(), "au9999", start_date, end_date),
        # Macro factors — real-time snapshots
        _fetch_one(VixRealtimeFetcher(), "vix", start_date, end_date),
        _fetch_one(OilRealtimeFetcher(), "oil", None, None),
        _fetch_one(UsdCnyFetcher(), "usd_cny", None, None),
        _fetch_one(Treasury10YFetcher(), "treasury_10y", start_date, end_date),
        _fetch_one(DxyProxyFetcher(), "dxy", start_date, end_date),
        # Historical depth (incremental — only inserts new dates)
        _fetch_one(VixHistoryFetcher(), "vix_history", None, None),
        _fetch_one(OilHistoryFetcher(), "oil_history", None, None),
    ]

    fetched = await asyncio.gather(*fetch_tasks)

    # Phase 2: Compute geopolitical risk (needs session to query events)
    try:
        geo_fetcher = GeopoliticalRiskFetcher()
        geo_df = await geo_fetcher.fetch(session)
        if not geo_df.empty:
            geo_count = await geo_fetcher.save_to_db(geo_df, session)
            results["geo_risk"] = {"status": "success", "records": geo_count}
            logger.info(f"[geo] risk score: {geo_df.iloc[0]['risk_score']:.2f}, "
                        f"intensity: {geo_df.iloc[0]['event_intensity']:.2f}")
        else:
            results["geo_risk"] = {"status": "empty", "records": 0}
    except Exception as e:
        results["geo_risk"] = {"status": "failed", "error": str(e)}
        logger.error(f"[geo] risk computation failed: {e}")

    # Phase 3: Save fetched data to DB sequentially (avoids SQLite lock contention)
    for label, result, payload in fetched:
        if payload is None:
            results[label] = result
            continue

        fetcher, df = payload
        try:
            count = await fetcher.save_to_db(df, session)
            result["records"] = count
            results[label] = result
            # Log the latest value
            if label == "treasury_10y":
                logger.info(f"[{label}] {count} records, last={df.iloc[-1]['yield_value']:.2f}%")
            elif label == "usd_cny":
                logger.info(f"[{label}] {count} records, close={df.iloc[-1]['close']:.4f}")
            else:
                logger.info(f"[{label}] {count} records, close={df.iloc[-1]['close']:.2f}")
        except Exception as save_err:
            results[label] = {"status": "save_failed", "error": str(save_err)}
            logger.error(f"[{label}] save failed: {save_err}")

    return results


async def fetch_historical_treasury(session) -> dict:
    """Load full US Treasury 10Y historical data (one-time, ~9000+ records)."""
    try:
        fetcher = Treasury10YFetcher()
        df = await fetcher.fetch()
        if not df.empty:
            count = await fetcher.save_to_db(df, session)
            logger.info(f"[macro] Treasury 10Y historical: {count} records loaded")
            return {"status": "success", "records": count}
        return {"status": "empty", "records": 0}
    except Exception as e:
        logger.error(f"[macro] Treasury 10Y historical failed: {e}")
        return {"status": "failed", "error": str(e)}


async def fetch_historical_forex(session) -> dict:
    """Load full historical USD/CNY data (one-time, ~4000+ records)."""
    try:
        fetcher = UsdCnyFetcher()
        df = await fetcher.fetch_history()
        if not df.empty:
            count = await fetcher.save_to_db(df, session)
            logger.info(f"[forex] USD/CNY historical: {count} records loaded")
            return {"status": "success", "records": count}
        return {"status": "empty", "records": 0}
    except Exception as e:
        logger.error(f"[forex] USD/CNY historical failed: {e}")
        return {"status": "failed", "error": str(e)}


async def fetch_historical_au9999(session) -> dict:
    """Fetch full historical Au99.99 data from AKShare (one-time)."""
    try:
        fetcher = Au9999Fetcher()
        df = await fetcher.fetch()
        if not df.empty:
            count = await fetcher.save_to_db(df, session)
            logger.info(f"[akshare] Au99.99 historical: {count} records loaded")
            return {"status": "success", "records": count}
        return {"status": "empty", "records": 0}
    except Exception as e:
        logger.error(f"[akshare] Au99.99 historical failed: {e}")
        return {"status": "failed", "error": str(e)}
