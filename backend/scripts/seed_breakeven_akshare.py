"""Try to fetch breakeven inflation data via AKShare (accessible from China)."""
import os, sys
import pandas as pd
from sqlalchemy import create_engine, text

URL = os.environ.get("DATABASE_URL", "")
if not URL:
    print("ERROR: set DATABASE_URL=postgresql://... && python seed_breakeven_akshare.py")
    sys.exit(1)

engine = create_engine(URL)

# Try AKShare US treasury yield data
print("[1/3] Fetching US rate data via AKShare...")
try:
    import akshare as ak
    df_rate = ak.bond_zh_us_rate()
    print(f"  Columns: {list(df_rate.columns)}")
    print(f"  Available rates: {df_rate['rate_name'].unique().tolist()}")
except Exception as e:
    print(f"  FAILED: {e}")
    sys.exit(1)

print("[2/3] Fetching US TIPS yield data via AKShare...")
try:
    import akshare as ak
    df_tips = ak.bond_zh_us_rate()
    df_tips = df_tips[df_tips["rate_name"] == "美国10年期TIPS收益率"]
    df_tips = df_tips.rename(columns={"date": "trade_date", "value": "tips_10y"})
    df_tips["trade_date"] = pd.to_datetime(df_tips["trade_date"]).dt.date
    print(f"  TIPS 10Y: {len(df_tips)} rows ({df_tips['trade_date'].min()} -> {df_tips['trade_date'].max()})")
except Exception as e:
    print(f"  FAILED: {e}")
    sys.exit(1)

print("[3/3] Computing breakeven rate and inserting into PostgreSQL...")
merged = pd.merge(df_tsy, df_tips, on="trade_date", how="inner")
merged["breakeven_rate"] = merged["treasury_10y"] - merged["tips_10y"]
merged = merged.dropna(subset=["breakeven_rate"])
print(f"  Merged: {len(merged)} rows")

inserted = updated = 0
with engine.connect() as conn:
    for _, row in merged.iterrows():
        exists = conn.execute(
            text("SELECT 1 FROM factor_breakeven_inflation WHERE trade_date = :d"),
            {"d": row["trade_date"]}
        ).fetchone()
        if exists:
            conn.execute(
                text("UPDATE factor_breakeven_inflation SET breakeven_rate=:r, treasury_10y=:t, tips_10y=:p WHERE trade_date=:d"),
                {"d": row["trade_date"], "r": float(row["breakeven_rate"]), "t": float(row["treasury_10y"]), "p": float(row["tips_10y"])}
            )
            updated += 1
        else:
            conn.execute(
                text("INSERT INTO factor_breakeven_inflation (trade_date,breakeven_rate,treasury_10y,tips_10y,source) VALUES (:d,:r,:t,:p,'akshare')"),
                {"d": row["trade_date"], "r": float(row["breakeven_rate"]), "t": float(row["treasury_10y"]), "p": float(row["tips_10y"])}
            )
            inserted += 1
    conn.commit()

print(f"  Inserted: {inserted}, Updated: {updated}")
print("Done!")
