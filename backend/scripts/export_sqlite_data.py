"""Export local SQLite data to JSON for Railway import."""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "gold_monitor.db"
OUTPUT_PATH = Path(__file__).parent / "exported_data.json"

EXPORT_TABLES = {
    "gold_prices_au9999": {
        "columns": ["trade_date", "open", "high", "low", "close", "volume", "source"],
        "date_cols": ["trade_date"],
    },
    "gold_prices_xau_usd": {
        "columns": ["trade_date", "open", "high", "low", "close", "volume", "source"],
        "date_cols": ["trade_date"],
    },
    "factor_usd_cny": {
        "columns": ["trade_date", "open", "high", "low", "close"],
        "date_cols": ["trade_date"],
    },
    "factor_vix": {
        "columns": ["trade_date", "close", "source"],
        "date_cols": ["trade_date"],
    },
    "factor_treasury_10y": {
        "columns": ["trade_date", "yield_value", "source"],
        "date_cols": ["trade_date"],
    },
    "factor_oil": {
        "columns": ["trade_date", "close", "source"],
        "date_cols": ["trade_date"],
    },
    "geopolitical_events": {
        "columns": ["date", "title", "description", "impact", "direction", "category", "risk_regions", "source_url"],
        "date_cols": ["date"],
    },
    "geopolitical_risk_index": {
        "columns": ["trade_date", "risk_score", "event_intensity", "active_conflicts", "news_sentiment", "news_headline_count", "regional_scores"],
        "date_cols": ["trade_date"],
    },
}

conn = sqlite3.connect(str(DB_PATH))
cursor = conn.cursor()

export = {}

for table, config in EXPORT_TABLES.items():
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
    if not cursor.fetchone():
        print(f"⚠ Table {table} not found, skipping")
        continue

    columns = config["columns"]
    date_cols = config["date_cols"]
    col_list = ", ".join(columns)

    try:
        cursor.execute(f'SELECT {col_list} FROM "{table}" ORDER BY trade_date ASC')
        rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"⚠ Table {table} error: {e}, skipping")
        continue

    data = []
    for row in rows:
        record = {}
        for i, col in enumerate(columns):
            val = row[i]
            if col in date_cols and val is not None:
                val = str(val)
            record[col] = val
        data.append(record)

    export[table] = data
    print(f"✅ {table}: {len(data)} rows exported")

conn.close()

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(export, f, ensure_ascii=False, indent=2)

print(f"\n📦 总计: {sum(len(v) for v in export.values())} 条数据")
print(f"📁 已导出到: {OUTPUT_PATH}")
