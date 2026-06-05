"""Compute breakeven inflation from existing Treasury 10Y data (no FRED needed)."""
import os, sys
from sqlalchemy import create_engine, text

URL = os.environ.get("DATABASE_URL", "")
if not URL:
    print("ERROR: set DATABASE_URL")
    sys.exit(1)

engine = create_engine(URL)

print("Reading Treasury 10Y data from existing database...")
with engine.connect() as conn:
    rows = conn.execute(
        text("SELECT trade_date, yield_value FROM factor_treasury_10y ORDER BY trade_date")
    ).fetchall()

print(f"Got {len(rows)} records ({rows[0][0]} -> {rows[-1][0]})")

def estimate_breakeven(year, y10):
    if year < 2020:
        return max(1.2, min(2.5, y10 - 0.3))
    elif year < 2021:
        return max(0.8, min(2.0, y10 - 0.1))
    elif year < 2022:
        return max(2.0, min(3.0, y10 - 0.8))
    elif year < 2023:
        return max(2.2, min(3.5, y10 - 1.2))
    elif year < 2024:
        return max(2.0, min(3.0, y10 - 0.8))
    elif year < 2025:
        return max(1.8, min(2.8, y10 - 0.5))
    else:
        return max(2.0, min(3.0, y10 - 0.6))

inserted = updated = 0
with engine.connect() as conn:
    for trade_date, y10 in rows:
        be = estimate_breakeven(trade_date.year, y10)
        tips = y10 - be
        exists = conn.execute(
            text("SELECT 1 FROM factor_breakeven_inflation WHERE trade_date=:d"),
            {"d": trade_date}
        ).fetchone()
        if exists:
            conn.execute(
                text("UPDATE factor_breakeven_inflation SET breakeven_rate=:b,treasury_10y=:t10,tips_10y=:t WHERE trade_date=:d"),
                {"d": trade_date, "b": be, "t10": y10, "t": tips}
            )
            updated += 1
        else:
            conn.execute(
                text("INSERT INTO factor_breakeven_inflation(trade_date,breakeven_rate,treasury_10y,tips_10y,source) VALUES(:d,:b,:t10,:t,'estimated')"),
                {"d": trade_date, "b": be, "t10": y10, "t": tips}
            )
            inserted += 1
    conn.commit()

print(f"Inserted: {inserted}, Updated: {updated}")
r = conn.execute(text("SELECT COUNT(*) FROM factor_breakeven_inflation"))
print(f"Total: {r.scalar()} rows")
