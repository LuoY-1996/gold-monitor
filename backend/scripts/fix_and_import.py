#!/usr/bin/env python3
"""重建表类型 + 重新导入数据到 Railway PostgreSQL"""
import os, sys, sqlite3, psycopg2, psycopg2.extras
from datetime import date, datetime

PG_URL = os.environ.get("PG_URL")
if not PG_URL:
    print("请设置 PG_URL 环境变量")
    sys.exit(1)

SQ = r"D:\claude软件\金价监测\backend\gold_monitor.db"

SCHEMAS = {
    "gold_prices_au9999": ("""id SERIAL PRIMARY KEY, trade_date DATE UNIQUE NOT NULL,
        open DOUBLE PRECISION, high DOUBLE PRECISION, low DOUBLE PRECISION,
        close DOUBLE PRECISION NOT NULL, volume DOUBLE PRECISION, source VARCHAR(50)""",
        ["trade_date","open","high","low","close","volume","source"]),
    "gold_prices_xau_usd": ("""id SERIAL PRIMARY KEY, trade_date DATE UNIQUE NOT NULL,
        open DOUBLE PRECISION, high DOUBLE PRECISION, low DOUBLE PRECISION,
        close DOUBLE PRECISION NOT NULL, volume DOUBLE PRECISION, source VARCHAR(50)""",
        ["trade_date","open","high","low","close","volume","source"]),
    "factor_usd_cny": ("""id SERIAL PRIMARY KEY, trade_date DATE UNIQUE NOT NULL,
        close DOUBLE PRECISION NOT NULL, open DOUBLE PRECISION, high DOUBLE PRECISION,
        low DOUBLE PRECISION, source VARCHAR(50)""",
        ["trade_date","close","open","high","low"]),
    "factor_vix": ("""id SERIAL PRIMARY KEY, trade_date DATE UNIQUE NOT NULL,
        close DOUBLE PRECISION NOT NULL, source VARCHAR(50)""",
        ["trade_date","close","source"]),
    "factor_treasury_10y": ("""id SERIAL PRIMARY KEY, trade_date DATE UNIQUE NOT NULL,
        yield_value DOUBLE PRECISION NOT NULL, source VARCHAR(50)""",
        ["trade_date","yield_value","source"]),
    "factor_oil": ("""id SERIAL PRIMARY KEY, trade_date DATE UNIQUE NOT NULL,
        close DOUBLE PRECISION NOT NULL, source VARCHAR(50)""",
        ["trade_date","close","source"]),
    "factor_fed_funds": ("""id SERIAL PRIMARY KEY, trade_date DATE UNIQUE NOT NULL,
        rate DOUBLE PRECISION NOT NULL, rate_prev DOUBLE PRECISION, source VARCHAR(50)""",
        ["trade_date","rate","rate_prev","source"]),
    "geopolitical_events": ("""id SERIAL PRIMARY KEY, event_date DATE NOT NULL,
        title TEXT NOT NULL, description TEXT, impact INTEGER NOT NULL,
        direction INTEGER NOT NULL, category VARCHAR(50) NOT NULL,
        risk_regions TEXT, source_url TEXT""",
        ["date","title","description","impact","direction","category","risk_regions","source_url"]),
    "geopolitical_risk_index": ("""id SERIAL PRIMARY KEY, trade_date DATE UNIQUE NOT NULL,
        risk_score DOUBLE PRECISION NOT NULL, event_intensity DOUBLE PRECISION NOT NULL,
        active_conflicts INTEGER NOT NULL, news_sentiment DOUBLE PRECISION,
        news_headline_count INTEGER, regional_scores TEXT, source VARCHAR(50)""",
        ["trade_date","risk_score","event_intensity","active_conflicts","news_sentiment","news_headline_count","regional_scores"]),
}

# Recreate all tables
pg = psycopg2.connect(PG_URL); cur = pg.cursor(); pg.autocommit = True
for t, (schema_sql, cols) in SCHEMAS.items():
    cur.execute(f'DROP TABLE IF EXISTS "{t}" CASCADE')
    cur.execute(f'CREATE TABLE "{t}" ({schema_sql})')
print("Tables created with proper types")

# Import data
sq = sqlite3.connect(SQ)
sq.row_factory = sqlite3.Row
sq_tables = {r["name"] for r in sq.execute("SELECT name FROM sqlite_master WHERE type='table'")}

for t, (_, cols) in SCHEMAS.items():
    if t not in sq_tables:
        print(f"  {t}: skip (no SQLite table)")
        continue
    rows = sq.execute(f'SELECT * FROM "{t}"').fetchall()
    if not rows:
        print(f"  {t}: 0 rows in SQLite")
        continue

    vals = []
    for r in rows:
        d = dict(r)
        vals.append(tuple(str(v) if isinstance(v, (date, datetime)) else v for c in cols for v in [d.get(c)]))

    # Fixed: build tuple correctly
    vals = []
    for r in rows:
        d = dict(r)
        row_vals = []
        for c in cols:
            v = d.get(c)
            if isinstance(v, (date, datetime)):
                v = str(v)
            row_vals.append(v)
        vals.append(tuple(row_vals))

    pg.autocommit = False
    cn = ", ".join([f'"{c}"' for c in cols])
    try:
        psycopg2.extras.execute_values(cur, f'INSERT INTO "{t}" ({cn}) VALUES %s ON CONFLICT DO NOTHING', vals, page_size=500)
        pg.commit()
        print(f"  {t}: {len(vals)} rows OK")
    except Exception as e:
        pg.rollback()
        print(f"  {t}: FAIL: {e}")
    pg.autocommit = True

sq.close(); cur.close(); pg.close()
print("ALL DONE!")
