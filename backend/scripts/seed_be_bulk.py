"""Bulk insert estimated breakeven data from Treasury 10Y."""
import os, sys
from sqlalchemy import create_engine, text

URL = os.environ.get("DATABASE_URL", "")
if not URL:
    print("ERROR: set DATABASE_URL")
    sys.exit(1)

engine = create_engine(URL, pool_pre_ping=True, pool_size=1)

print("Reading Treasury 10Y data...")
with engine.connect() as conn:
    rows = conn.execute(
        text("SELECT trade_date, yield_value FROM factor_treasury_10y ORDER BY trade_date")
    ).fetchall()

print(f"Got {len(rows)} records")

def be_est(year, y10):
    if year < 2020: return max(1.2, min(2.5, y10 - 0.3))
    elif year < 2021: return max(0.8, min(2.0, y10 - 0.1))
    elif year < 2022: return max(2.0, min(3.0, y10 - 0.8))
    elif year < 2023: return max(2.2, min(3.5, y10 - 1.2))
    elif year < 2024: return max(2.0, min(3.0, y10 - 0.8))
    elif year < 2025: return max(1.8, min(2.8, y10 - 0.5))
    else: return max(2.0, min(3.0, y10 - 0.6))

# Bulk insert using execute_values style
values = []
for trade_date, y10 in rows:
    be = be_est(trade_date.year, y10)
    tips = round(y10 - be, 4)
    values.append(f"('{trade_date}',{be},{y10},{tips},'estimated')")

print(f"Inserting {len(values)} rows in bulk...")
batch_size = 500
inserted = 0
with engine.connect() as conn:
    # Clear existing
    conn.execute(text("DELETE FROM factor_breakeven_inflation"))
    conn.commit()
    
    for i in range(0, len(values), batch_size):
        batch = values[i:i+batch_size]
        sql = "INSERT INTO factor_breakeven_inflation(trade_date,breakeven_rate,treasury_10y,tips_10y,source) VALUES " + ",".join(batch)
        conn.execute(text(sql))
        conn.commit()
        inserted += len(batch)
        print(f"  {inserted}/{len(values)}")

print(f"Done! Total: {inserted}")
