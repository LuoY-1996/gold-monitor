"""Verify Railway PostgreSQL data."""
import os, sys
from sqlalchemy import create_engine, text

URL = os.environ.get("VERIFY_DB_URL", "")
if not URL:
    print("Usage: set VERIFY_DB_URL=<postgresql://...> && python verify_db.py")
    sys.exit(1)

engine = create_engine(URL)
with engine.connect() as conn:
    r = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"))
    for t in [row[0] for row in r]:
        c = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
        print(f"  {t}: {c}")
