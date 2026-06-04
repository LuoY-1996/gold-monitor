"""Application configuration from environment variables.

Supports both SQLite (local dev) and PostgreSQL (Railway/production).
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv(Path(__file__).parent.parent / ".env")

# Project root
BASE_DIR = Path(__file__).parent.parent

# Database — read DATABASE_URL from env (Railway sets this automatically),
# fallback to SQLite for local development.
_raw_db_url = os.getenv("DATABASE_URL", "")

if _raw_db_url:
    # Production: PostgreSQL from env (Railway gives postgresql://...)
    # SQLAlchemy async engine needs postgresql+asyncpg:// prefix
    if _raw_db_url.startswith("postgresql://"):
        DATABASE_URL = _raw_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif _raw_db_url.startswith("postgresql+asyncpg://"):
        DATABASE_URL = _raw_db_url
    else:
        DATABASE_URL = _raw_db_url
    IS_SQLITE = False
else:
    # Local dev: SQLite
    DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR / 'gold_monitor.db'}"
    IS_SQLITE = True

# FRED API key (optional, for CPI data)
FRED_API_KEY = os.getenv("FRED_API_KEY", "")

# JWT settings (Phase 4)
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8001"))

# CORS — allow both local frontend and Railway domain
_default_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
CORS_ORIGINS = [o.strip() for o in _default_origins.split(",")]

# Data fetching
FETCH_INTERVAL_MINUTES = int(os.getenv("FETCH_INTERVAL_MINUTES", "60"))
