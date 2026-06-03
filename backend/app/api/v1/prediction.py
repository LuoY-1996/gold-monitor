"""ML prediction & valuation API endpoints."""

from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DBSession
from app.schemas.prediction import (
    PredictionResponse,
    TrainingResultResponse,
    ModelInfoResponse,
)
from app.services import prediction_service
from app.ml.valuation import compute_valuation

router = APIRouter(prefix="/prediction", tags=["Prediction"])


@router.get("/valuation")
async def get_valuation(session: AsyncSession = DBSession):
    """Get macro fair-value valuation for gold.

    Uses Ridge regression on macro factors (rates, dollar, VIX, oil, CB purchases,
    geopolitical risk) to estimate gold's fair value at monthly frequency.
    Returns current valuation gap, percentile, and historical fair value series.
    """
    result = await compute_valuation(session)
    return result


@router.get("/{gold_type}", response_model=PredictionResponse)
async def get_prediction(
    gold_type: str,
    session: AsyncSession = DBSession,
):
    """Get latest gold price prediction for the next 7 trading days.

    gold_type: 'xau-usd' or 'au9999'
    Requires a trained model. Train first via POST /prediction/train/{gold_type}
    """
    # Normalize gold type
    normalized = gold_type.lower().replace("-", "_")
    result = await prediction_service.get_prediction(session, normalized)
    return PredictionResponse(**result)


@router.post("/train/{gold_type}", response_model=TrainingResultResponse)
async def train_model(
    gold_type: str,
    days: int = Query(730, ge=365, le=3650, description="Days of historical data to use"),
    session: AsyncSession = DBSession,
):
    """Train XGBoost model for gold price prediction.

    Uses chronological time-series split (no look-ahead bias).
    Training may take 10-30 seconds depending on data size.
    """
    normalized = gold_type.lower().replace("-", "_")
    result = await prediction_service.train_and_get_result(session, normalized, days)
    return TrainingResultResponse(**result)


@router.get("/{gold_type}/model-info", response_model=ModelInfoResponse)
async def get_model_info(gold_type: str):
    """Get metadata about the latest trained model."""
    normalized = gold_type.lower().replace("-", "_")
    info = await prediction_service.get_model_metadata(normalized)
    if info is None:
        return ModelInfoResponse()
    return ModelInfoResponse(**info)
