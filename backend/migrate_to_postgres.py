#!/usr/bin/env python3
"""Migrate data from SQLite to PostgreSQL.

Usage:
    1. Set DATABASE_URL to your Railway PostgreSQL URL (with postgresql:// prefix)
    2. Run: python migrate_to_postgres.py

    The script reads from the local SQLite database and writes to PostgreSQL.
    If a record already exists (same date), it will be updated.
"""

import os
import sys
from datetime import date
from pathlib import Path

# Ensure we can import from the backend package
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# ── Config ──────────────────────────────────────────────────────────────────

SQLITE_PATH = Path(__file__).parent / "gold_monitor.db"
PG_URL = os.getenv("DATABASE_URL", "")

if not PG_URL:
    print("❌ 请设置 DATABASE_URL 环境变量，指向你的 PostgreSQL 数据库")
    print("   例如: DATABASE_URL=postgresql://user:pass@host:5432/railway")
    sys.exit(1)

# Ensure postgresql:// prefix (sync driver uses psycopg2)
if PG_URL.startswith("postgresql+asyncpg://"):
    PG_URL_SYNC = PG_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
elif PG_URL.startswith("postgresql://"):
    PG_URL_SYNC = PG_URL
else:
    PG_URL_SYNC = PG_URL

# ── Tables to migrate ───────────────────────────────────────────────────────

TABLES = [
    {
        "name": "gold_prices_xau_usd",
        "columns": ["trade_date", "open", "high", "low", "close", "volume", "source"],
        "date_col": "trade_date",
    },
    {
        "name": "gold_prices_au9999",
        "columns": ["trade_date", "open", "high", "low", "close", "volume", "source"],
        "date_col": "trade_date",
    },
    {
        "name": "factor_dxy",
        "columns": ["trade_date", "close", "source"],
        "date_col": "trade_date",
    },
    {
        "name": "factor_vix",
        "columns": ["trade_date", "close", "source"],
        "date_col": "trade_date",
    },
    {
        "name": "factor_treasury_10y",
        "columns": ["trade_date", "yield_value", "source"],
        "date_col": "trade_date",
    },
    {
        "name": "factor_cpi",
        "columns": ["report_date", "cpi_value", "cpi_yoy_pct", "source"],
        "date_col": "report_date",
    },
    {
        "name": "factor_oil",
        "columns": ["trade_date", "close", "source"],
        "date_col": "trade_date",
    },
    {
        "name": "factor_usd_cny",
        "columns": ["trade_date", "close", "open", "high", "low", "source"],
        "date_col": "trade_date",
    },
    {
        "name": "geopolitical_events",
        "columns": ["event_date", "title", "description", "impact", "direction",
                     "category", "risk_regions", "source_url"],
        "date_col": "event_date",
    },
    {
        "name": "geopolitical_risk_index",
        "columns": ["trade_date", "risk_score", "event_intensity", "active_conflicts",
                     "news_sentiment", "news_headline_count", "regional_scores", "source"],
        "date_col": "trade_date",
    },
]


def migrate():
    if not SQLITE_PATH.exists():
        print(f"❌ 找不到 SQLite 数据库: {SQLITE_PATH}")
        print("   先在本地启动一次后端，确保有数据后再迁移")
        sys.exit(1)

    # Connect to SQLite
    sqlite_engine = create_engine(f"sqlite:///{SQLITE_PATH}")
    sqlite_conn = sqlite_engine.connect()

    # Connect to PostgreSQL
    pg_engine = create_engine(PG_URL_SYNC)
    pg_conn = pg_engine.connect()

    print(f"📦 SQLite: {SQLITE_PATH}")
    print(f"🐘 PostgreSQL: {PG_URL_SYNC.split('@')[1] if '@' in PG_URL_SYNC else PG_URL_SYNC}")
    print()

    total_inserted = 0
    total_updated = 0

    for table in TABLES:
        name = table["name"]
        cols = table["columns"]
        date_col = table["date_col"]
        col_list = ", ".join(cols)
        placeholders = ", ".join([f":{c}" for c in cols])

        # Read from SQLite
        rows = sqlite_conn.execute(text(f"SELECT {col_list} FROM {name}")).fetchall()
        if not rows:
            print(f"  ⏭️  {name}: 0 条数据，跳过")
            continue

        print(f"  📋 {name}: {len(rows)} 条数据 → ", end="", flush=True)

        inserted = 0
        updated = 0

        for row in rows:
            row_dict = dict(row._mapping)

            # Convert date objects
            for k, v in row_dict.items():
                if isinstance(v, date):
                    row_dict[k] = v

            # Check if record exists
            exists = pg_conn.execute(
                text(f"SELECT 1 FROM {name} WHERE {date_col} = :{date_col}"),
                {date_col: row_dict[date_col]}
            ).fetchone()

            if exists:
                # Update
                set_clause = ", ".join([
                    f"{c} = :{c}" for c in cols if c != date_col
                ])
                pg_conn.execute(
                    text(f"UPDATE {name} SET {set_clause} WHERE {date_col} = :{date_col}"),
                    row_dict
                )
                updated += 1
            else:
                # Insert
                pg_conn.execute(
                    text(f"INSERT INTO {name} ({col_list}) VALUES ({placeholders})"),
                    row_dict
                )
                inserted += 1

        pg_conn.commit()
        total_inserted += inserted
        total_updated += updated
        print(f"新增 {inserted}, 更新 {updated}")

    sqlite_conn.close()
    pg_conn.close()

    print()
    print(f"✅ 迁移完成！")
    print(f"   新增: {total_inserted} 条")
    print(f"   更新: {total_updated} 条")
    print(f"   总计: {total_inserted + total_updated} 条")


if __name__ == "__main__":
    migrate()
