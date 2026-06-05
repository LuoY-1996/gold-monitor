"""Fetch breakeven inflation data from FRED in small chunks."""
import os, sys, http.client, csv, io
from sqlalchemy import create_engine, text

URL = os.environ.get("DATABASE_URL", "")
if not URL:
    print("ERROR: set DATABASE_URL")
    sys.exit(1)

engine = create_engine(URL)

def fetch_fred(series_id, start, end):
    conn = http.client.HTTPSConnection("fred.stlouisfed.org", timeout=60)
    path = f"/graph/fredgraph.csv?id={series_id}&cosd={start}&coed={end}"
    conn.request("GET", path, headers={"User-Agent": "Mozilla/5.0"})
    resp = conn.getresponse()
    text = resp.read().decode()
    conn.close()
    reader = csv.reader(io.StringIO(text))
    result = {}
    for i, row in enumerate(reader):
        if i == 0:
            continue
        if len(row) >= 2 and row[1] and row[1] != ".":
            result[row[0]] = float(row[1])
    return result

# Fetch in yearly chunks to avoid connection resets
years = [(y, y+1) for y in range(2015, 2026)]
tips_all = {}
tsy_all = {}
for y, y1 in years:
    cs = f"{y}-01-01"
    ce = f"{y1}-01-01"
    print(f"  {cs}...", end="", flush=True)
    try:
        t = fetch_fred("DFII10", cs, ce)
        tips_all.update(t)
        s = fetch_fred("DGS10", cs, ce)
        tsy_all.update(s)
        print(f" TIPS:{len(t)} 10Y:{len(s)}")
    except Exception as e:
        print(f" FAILED: {type(e).__name__}")
        # Retry once
        try:
            t = fetch_fred("DFII10", cs, ce)
            tips_all.update(t)
            s = fetch_fred("DGS10", cs, ce)
            tsy_all.update(s)
            print(f"  retry OK: TIPS:{len(t)} 10Y:{len(s)}")
        except Exception as e2:
            print(f"  retry FAILED: {e2}")

print(f"\nTotal: TIPS={len(tips_all)}, 10Y={len(tsy_all)}")

dates = sorted(set(tips_all.keys()) & set(tsy_all.keys()))
print(f"Merged: {len(dates)} common dates")

inserted = updated = 0
with engine.connect() as conn:
    for d in dates:
        be = tsy_all[d] - tips_all[d]
        exists = conn.execute(
            text("SELECT 1 FROM factor_breakeven_inflation WHERE trade_date=:d"),
            {"d": d[:10]}
        ).fetchone()
        if exists:
            conn.execute(
                text("UPDATE factor_breakeven_inflation SET breakeven_rate=:b,treasury_10y=:t10,tips_10y=:t WHERE trade_date=:d"),
                {"d": d[:10], "b": be, "t10": tsy_all[d], "t": tips_all[d]}
            )
            updated += 1
        else:
            conn.execute(
                text("INSERT INTO factor_breakeven_inflation(trade_date,breakeven_rate,treasury_10y,tips_10y,source) VALUES(:d,:b,:t10,:t,'fred')"),
                {"d": d[:10], "b": be, "t10": tsy_all[d], "t": tips_all[d]}
            )
            inserted += 1
    conn.commit()

print(f"Inserted: {inserted}, Updated: {updated}")
r = conn.execute(text("SELECT COUNT(*) FROM factor_breakeven_inflation"))
print(f"Total: {r.scalar()} rows")
