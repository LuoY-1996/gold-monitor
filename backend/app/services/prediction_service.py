"""Prediction service — bridges API and ML module."""

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.predictor import predict
from app.ml.model_trainer import train_model, get_model_info

logger = logging.getLogger(__name__)

# Simple in-memory training lock to prevent concurrent training
_training_lock: dict[str, bool] = {}


async def get_prediction(session: AsyncSession, gold_type: str) -> dict:
    """Get latest prediction for a gold type."""
    return await predict(session, gold_type)


async def train_and_get_result(
    session: AsyncSession,
    gold_type: str,
    days: int = 730,
) -> dict:
    """Train model and return metrics. Prevents concurrent training."""
    if _training_lock.get(gold_type):
        return {
            "status": "conflict",
            "message": f"Training already in progress for {gold_type}. Please wait.",
        }

    _training_lock[gold_type] = True
    try:
        result = await train_model(session, gold_type, days)
        return result
    finally:
        _training_lock[gold_type] = False


async def get_model_metadata(gold_type: str) -> dict | None:
    """Get model metadata without loading the full model."""
    return get_model_info(gold_type)
