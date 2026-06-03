"""FastAPI dependency injection utilities."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

# Re-export for convenience
DBSession = Depends(get_db)
