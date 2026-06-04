import sys, os, sqlite3, psycopg2
from datetime import date, datetime

DB = r"D:\claude软件\金价监测\backend\gold_monitor.db"
PG_URL = os.environ.get("PG_URL")
if not PG_URL:
    print("ERROR: Set PG_URL env var")
    sys.exit(1)

pg = psycopg2.connect(PG_URL)
pg.autocommit = True
cur = pg.cursor()

sq = sqlite3.connect(DB)
sq.row_factory = sqlite3.Row

# Create tables & import data
for t, sql in sq.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"):
    # Get columns from SQLite
    cur2 = sq.execute(f'SELECT * FROM "{t}" LIMIT 0')
    col_info = [(d[0], d[1]) for d in cur2.description]
    col_names = [c[0] for c in col_info]
    print(f"\n  {t}: {len(col_info)} columns -> ", end="")

    # Create table in PG
    type_map = {"INT": "INTEGER", "REAL": "DOUBLE PRECISION", "FLOAT": "DOUBLE PRECISION",
                "DOUBLE": "DOUBLE PRECISION"}
    pg_cols = [f'"{cn}" {next((v for k,v in type_map.items() if ct and k in ct.upper()), "TEXT")}' for cn, ct in col_info]
    try:
        cur.execute(f'CREATE TABLE IF NOT EXISTS "{t}" ({", ".join(pg_cols)})')
    except Exception as e:
        print(f"CREATE FAILED: {e}")
        continue

    # Import data
    rows = sq.execute(f'SELECT * FROM "{t}"').fetchall()
    if not rows:
        print("0 rows (empty)")
        continue

    pg.autocommit = False
    ok = 0
    for row in rows:
        d = {k: (str(v) if isinstance(v, (date, datetime)) else v) for k, v in dict(row).items()}
        plc = ", ".join([f"%({c})s" for c in col_names])
        cn = ", ".join([f'"{c}"' for c in col_names])
        try:
            cur.execute(f'INSERT INTO "{t}" ({cn}) VALUES ({plc}) ON CONFLICT DO NOTHING', d)
            if cur.rowcount > 0: ok += 1
        except Exception:
            pg.rollback()
    pg.commit()
    pg.autocommit = True
    print(f"{ok}/{len(rows)} rows")

sq.close(); cur.close(); pg.close()
print("\nDONE!")
