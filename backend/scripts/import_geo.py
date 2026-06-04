"""Import geopolitical events from SQLite to PostgreSQL."""
import os, sqlite3, psycopg2

PG_URL = os.environ.get("PG_URL")
if not PG_URL:
    print("ERROR: Set PG_URL environment variable first")
    print('  export PG_URL="postgresql://..."')
    exit(1)

DB = r"D:\claude软件\金价监测\backend\gold_monitor.db"

sq = sqlite3.connect(DB)
sq.row_factory = sqlite3.Row
rows = sq.execute("SELECT * FROM geopolitical_events").fetchall()
print(f"SQLite: {len(rows)} events")

pg = psycopg2.connect(PG_URL)
cur = pg.cursor()
pg.autocommit = False

ok = 0
for r in rows:
    d = dict(r)
    try:
        cur.execute(
            """INSERT INTO geopolitical_events
            (event_date, title, description, impact, direction, category, risk_regions, source_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING""",
            (
                str(d["event_date"]),
                d["title"],
                d.get("description"),
                d["impact"],
                d["direction"],
                d["category"],
                d.get("risk_regions"),
                d.get("source_url"),
            ),
        )
        if cur.rowcount > 0:
            ok += 1
    except Exception as e:
        pg.rollback()
        print(f"Error: {e}")

pg.commit()
print(f"Imported: {ok} events")
cur.close()
pg.close()
sq.close()
