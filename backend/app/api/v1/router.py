"""Aggregate all v1 API routers."""

from fastapi import APIRouter
from app.api.v1.gold import router as gold_router
from app.api.v1.forex import router as forex_router
from app.api.v1.indicators import router as indicators_router
from app.api.v1.factors import router as factors_router
from app.api.v1.geopolitics import router as geopolitics_router
from app.api.v1.prediction import router as prediction_router

api_router = APIRouter()
api_router.include_router(gold_router)
api_router.include_router(forex_router)
api_router.include_router(indicators_router)
api_router.include_router(factors_router)
api_router.include_router(geopolitics_router)
api_router.include_router(prediction_router)
