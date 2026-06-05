"""Fetch breakeven inflation via urllib (works from China) and seed Railway PG."""
import os, sys, urllib.request, ssl, csv, io
from sqlalchemy import create_engine, text

URL = os.environ.get("DATABASE_URL", "")
if not URL:
    print("ERROR: set DATABASE_URL")
    sys.exit(1)

engine = create_engine(URL)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
headers = {"User-Agent": "Mozilla/5.0"}

def fetch_fred(series_id):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd=2015-01-01&coed=2026-06-05"
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, timeout=30, context=ctx)
    text = resp.read().decode()
    reader = csv.reader(io.StringIO(text))
    rows = []
    for i, row in enumerate(reader):
        if i == 0:
            continue  # header
        if len(row) >= 2 and row[1] and row[1] != ".":
            rows.append((row[0], float(row[1])))
    return rows

print("Fetching TIPS (DFII10)...")
tips = dict(fetch_fred("DFII10"))
print(f"  {len(tips)} points")

print("Fetching 10Y Treasury (DGS10)...")
tsy = dict(fetch_fred("DGS10"))
print(f"  {len(tsy)} points")

dates = sorted(set(tips.keys()) & set(tsy.keys()))
print(f"Computing breakeven for {len(dates)} common dates...")

inserted = updated = 0
with engine.connect() as conn:
    for d in dates:
        t10 = tsy[d]
        t = tips[d]
        be = t10 - t
        exists = conn.execute(
            text("SELECT 1 FROM factor_breakeven_inflation WHERE trade_date=:d"),
            {"d": d[:10]}
        ).fetchone()
        if exists:
            conn.execute(
                text("UPDATE factor_breakeven_inflation SET breakeven_rate=:b,treasury_10y=:t10,tips_10y=:t WHERE trade_date=:d"),
                {"d": d[:10], "b": be, "t10": t10, "t": t}
            )
            updated += 1
        else:
            conn.execute(
                text("INSERT INTO factor_breakeven_inflation(trade_date,breakeven_rate,treasury_10y,tips_10y,source) VALUES(:d,:b,:t10,:t,'fred')"),
                {"d": d[:10], "b": be, "t10": t10, "t": t}
            )
            inserted += 1
    conn.commit()

print(f"Inserted: {inserted}, Updated: {updated}")
r = conn.execute(text("SELECT COUNT(*) FROM factor_breakeven_inflation"))
print(f"Total: {r.scalar()} rows")
