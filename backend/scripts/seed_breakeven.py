"""Fetch TIPS/breakeven from FRED and seed Railway PostgreSQL."""
import os, sys, pandas as pd, requests
from io import StringIO
from sqlalchemy import create_engine, text

URL = os.environ.get("DATABASE_URL", "")
if not URL:
    print("Usage: set DATABASE_URL=postgresql://... && python seed_breakeven.py")
    sys.exit(1)

engine = create_engine(URL)

print("Fetching TIPS yield (DFII10)...")
r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFII10&cosd=2015-01-01&coed=2026-06-05",
                 headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
tips = pd.read_csv(StringIO(r.text), parse_dates=["DATE"])
tips["date"] = tips["DATE"].dt.date
tips["value"] = pd.to_numeric(tips.iloc[:, 1], errors="coerce")
tips = tips.dropna(subset=["value"])[["date", "value"]]

print("Fetching 10Y Treasury (DGS10)...")
r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10&cosd=2015-01-01&coed=2026-06-05",
                 headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
tsy = pd.read_csv(StringIO(r.text), parse_dates=["DATE"])
tsy["date"] = tsy["DATE"].dt.date
tsy["value"] = pd.to_numeric(tsy.iloc[:, 1], errors="coerce")
tsy = tsy.dropna(subset=["value"])[["date", "value"]]

merged = pd.merge(tips, tsy, on="date", suffixes=("_tips", "_treasury"))
merged["breakeven"] = merged["value_treasury"] - merged["value_tips"]
merged = merged.dropna(subset=["breakeven"])
print(f"Fetched {len(merged)} records")

print("Inserting into Railway PostgreSQL...")
inserted = updated = 0
with engine.connect() as conn:
    for _, row in merged.iterrows():
        exists = conn.execute(
            text("SELECT 1 FROM factor_breakeven_inflation WHERE trade_date=:d"),
            {"d": row["date"]}
        ).fetchone()
        if exists:
            conn.execute(
                text("UPDATE factor_breakeven_inflation SET breakeven_rate=:r,treasury_10y=:t,tips_10y=:p WHERE trade_date=:d"),
                {"d": row["date"], "r": float(row["breakeven"]), "t": float(row["value_treasury"]), "p": float(row["value_tips"])}
            )
            updated += 1
        else:
            conn.execute(
                text("INSERT INTO factor_breakeven_inflation(trade_date,breakeven_rate,treasury_10y,tips_10y,source) VALUES(:d,:r,:t,:p,'fred')"),
                {"d": row["date"], "r": float(row["breakeven"]), "t": float(row["value_treasury"]), "p": float(row["value_tips"])}
            )
            inserted += 1
    conn.commit()

print(f"Inserted: {inserted}, Updated: {updated}")
r = conn.execute(text("SELECT COUNT(*) FROM factor_breakeven_inflation"))
print(f"Total: {r.scalar()} rows")
