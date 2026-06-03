"""Pydantic schemas for prediction API responses."""

from pydantic import BaseModel


class FeatureContribution(BaseModel):
    feature: str
    importance: float


class HorizonPrediction(BaseModel):
    direction: str  # "up" or "down"
    probability: float


class PredictionResponse(BaseModel):
    status: str
    gold_type: str
    model_trained: str | None = None
    message: str | None = None
    current_date: str | None = None
    current_close: float | None = None
    # 7d summary (backward compat)
    direction: str | None = None
    direction_probability: float | None = None
    predicted_return_7d_pct: float | None = None
    predicted_price_7d: float | None = None
    confidence_low: float | None = None
    confidence_high: float | None = None
    # Multi-horizon
    horizon_predictions: dict[str, HorizonPrediction] = {}
    consensus: str | None = None  # "strong_up" | "strong_down" | "lean_up" | "lean_down" | "mixed"
    consensus_label: str | None = None  # "一致看涨" | "一致看跌" | "偏多" | "偏空" | "分歧"
    votes_up: int | None = None
    total_horizons: int | None = None
    feature_contributions: list[FeatureContribution] = []


class FeatureImportanceItem(BaseModel):
    feature: str
    importance: float


class TrainingResultResponse(BaseModel):
    status: str
    gold_type: str | None = None
    message: str | None = None
    model_path: str | None = None
    direction_accuracy: float | None = None
    direction_precision: float | None = None
    direction_recall: float | None = None
    direction_f1: float | None = None
    price_mae_pct: float | None = None
    price_rmse_pct: float | None = None
    consensus_strong_pct: float | None = None
    consensus_accuracy: float | None = None
    feature_importance: list[FeatureImportanceItem] = []
    train_samples: int | None = None
    val_samples: int | None = None
    test_samples: int | None = None
    train_date_range: str | None = None


class ModelInfoResponse(BaseModel):
    gold_type: str | None = None
    training_date: str | None = None
    train_samples: int | None = None
    test_samples: int | None = None
    dir_accuracy: float | None = None
    rmse_pct: float | None = None
    consensus_pct: float | None = None
    train_date_range: str | None = None
    feature_count: int | None = None
    top_features: list[FeatureImportanceItem] = []
    file_size_mb: float | None = None
