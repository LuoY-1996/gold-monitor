"""Verify Railway PostgreSQL data before deployment fix."""
import os
import sys
from datetime import date, timedelta
from sqlalchemy import create_engine, text

URL = os.environ.get("VERIFY_DB_URL", "")
if not URL:
    print("Usage: set VERIFY_DB_URL=<postgresql://...> && python verify_db.py")
    sys.exit(1)

engine = create_engine(URL)
with engine.connect() as conn:
    # Table rows
    r = conn.execute(text(
        "SELECT table_name, (SELECT COUNT(*) FROM information_schema.tables t2 WHERE t2.table_schema='public') "
        "FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
    ))
    tables = list(r)
    print(f"Tables: {len(tables)}")

    total = 0
    for (tname,) in tables:
        pass  # can't use subquery easily this way

    # Simpler approach
    r2 = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"))
    all_tables = [row[0] for row in r2]
    total = 0
    for t in all_tables:
        r = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"'))
        c = r.scalar()
        total += c
        if c > 0:
            r2 = conn.execute(text(f'SELECT MIN(trade_date), MAX(trade_date) FROM "{t}"'))
            try:
                mn, mx = r2.one()
            except Exception:
                mn, mx = '-', '-'
            print(f"  {t}: {c:>5}  |  {mn or '-':>10} -> {mx or '-'}")
        else:
            print(f"  {t}: {c:>5}  |  (empty)")

    print(f"\nTotal records: {total}")

    # Test geo query
    cutoff = (date.today() - timedelta(days=12*30)).isoformat()
    r = conn.execute(
        text("SELECT COUNT(*) FROM geopolitical_events WHERE event_date >= :c"),
        {"c": cutoff}
    )
    print(f"\nGeo events in last 12 months: {r.scalar()}")

    r = conn.execute(
        text("SELECT COUNT(*) FROM geopolitical_events WHERE event_date >= :c"),
        {"c": (date.today() - timedelta(days=24*30)).isoformat()}
    )
    print(f"Geo events in last 24 months: {r.scalar()}")

    print("\nDatabase verification complete.")
