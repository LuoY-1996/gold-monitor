"""Check geopolitical events count in Railway PostgreSQL."""
import os, psycopg2

pg = psycopg2.connect(os.environ["PG_URL"])
cur = pg.cursor()
cur.execute("SELECT COUNT(*), MIN(event_date), MAX(event_date) FROM geopolitical_events")
row = cur.fetchone()
print(f"Events: {row[0]} rows, {row[1]} → {row[2]}")

cur.execute("SELECT event_date, title, category FROM geopolitical_events ORDER BY event_date DESC LIMIT 5")
print("\nLatest 5 events:")
for r in cur.fetchall():
    print(f"  {r[0]}: [{r[2]}] {r[1]}")

cur.close()
pg.close()
