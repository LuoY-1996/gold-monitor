"""Fix table column types on Railway PostgreSQL (TEXT->DATE/FLOAT)."""
import os, sys
from sqlalchemy import create_engine, text

URL = os.environ.get("DATABASE_URL", "")
if not URL:
    print("Usage: set DATABASE_URL=postgresql://... && python fix_table_types.py")
    sys.exit(1)

engine = create_engine(URL)

FIXES = {
    "factor_breakeven_inflation": {
        "trade_date": "DATE",
        "breakeven_rate": "DOUBLE PRECISION",
        "treasury_10y": "DOUBLE PRECISION",
        "tips_10y": "DOUBLE PRECISION",
    },
    "factor_gold_etf": {
        "trade_date": "DATE",
        "holdings_tons": "DOUBLE PRECISION",
        "close_price": "DOUBLE PRECISION",
    },
}

with engine.connect() as conn:
    for table, columns in FIXES.items():
        print(f"\nChecking {table}...")
        for col, target_type in columns.items():
            result = conn.execute(text(f"""
                SELECT data_type FROM information_schema.columns
                WHERE table_name='{table}' AND column_name='{col}'
            """))
            row = result.fetchone()
            if row:
                current_type = row[0]
                if current_type.upper() != target_type and current_type.upper() != target_type.replace("DOUBLE PRECISION", "numeric"):
                    print(f"  {col}: {current_type} -> {target_type}")
                    conn.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" TYPE {target_type} USING "{col}"::{target_type}'))
                    conn.commit()
                    print("    ... fixed")
                else:
                    print(f"  {col}: {current_type} (correct)")
            else:
                print(f"  {col}: column not found")

print("\n✅ Fix complete")
