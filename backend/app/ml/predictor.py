"""Gold price prediction inference — multi-horizon ensemble with consensus voting.

Supports both the new ensemble format (LightGBM + XGBoost + RandomForest)
and legacy single-model format via auto-conversion in load_model().
"""

import logging
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.model_trainer import load_model, HORIZONS, ensemble_predict_classify, ensemble_predict_regress
from app.ml.feature_engineering import build_training_dataset, get_latest_features

logger = logging.getLogger(__name__)


async def predict(
    session: AsyncSession,
    gold_type: str = "xau_usd",
) -> dict:
    """Generate multi-horizon predictions with ensemble consensus voting.

    Returns:
        dict with per-horizon predictions + consensus + signal strength
    """
    # 1. Load model
    model_pkg = load_model(gold_type)
    if model_pkg is None:
        return {
            "status": "no_model",
            "gold_type": gold_type,
            "message": "No trained model found. Train first via POST /prediction/train",
        }

    ensemble_classifiers = model_pkg.get("ensemble_classifiers", {})
    ensemble_regressors = model_pkg.get("ensemble_regressors", {})
    feature_names = model_pkg["feature_names"]

    if not ensemble_classifiers:
        return {
            "status": "error",
            "gold_type": gold_type,
            "message": "Model package has no ensemble classifiers",
        }

    # 2. Build current features
    df, _ = await build_training_dataset(session, gold_type, days=365)
    if df.empty:
        return {"status": "error", "gold_type": gold_type, "message": "No data available"}

    latest = get_latest_features(df, feature_names)
    if latest.empty:
        return {"status": "error", "gold_type": gold_type, "message": "Cannot extract features"}

    X_current = latest[feature_names].values

    # 3. Predict direction for each horizon using ensemble
    horizon_predictions = {}
    votes_up = 0
    total_h = 0

    for h in HORIZONS:
        if h not in ensemble_classifiers:
            continue
        ensemble = ensemble_classifiers[h]
        if not ensemble:
            continue

        direction, probs = ensemble_predict_classify(ensemble, X_current)
        direction_val = int(direction[0])
        prob_val = float(probs[0][direction_val])

        horizon_predictions[str(h)] = {
            "direction": "up" if direction_val == 1 else "down",
            "probability": round(prob_val, 4),
        }
        if direction_val == 1:
            votes_up += 1
        total_h += 1

    # 4. Consensus
    if total_h >= 3:
        if votes_up >= 3:
            consensus = "strong_up"
            consensus_label = "一致看涨"
        elif votes_up <= 1:
            consensus = "strong_down"
            consensus_label = "一致看跌"
        elif votes_up == 2:
            consensus = "lean_up"
            consensus_label = "偏多"
        else:
            consensus = "mixed"
            consensus_label = "分歧"
    else:
        consensus = "unknown"
        consensus_label = "数据不足"

    # 5. 7d price regression (ensemble)
    current_close = float(df.iloc[-1]["close"])
    pred_return = float(ensemble_predict_regress(ensemble_regressors, X_current)[0])
    predicted_price = round(current_close * (1 + pred_return), 2)

    recent_vol = float(df["ret_1d"].tail(30).std())
    ci_half = 2 * recent_vol * np.sqrt(7)
    confidence_low = round(current_close * (1 + pred_return - ci_half), 2)
    confidence_high = round(current_close * (1 + pred_return + ci_half), 2)

    # 6. Feature contributions (use LightGBM from 7d ensemble if available)
    feature_contributions = []
    try:
        lgb_7d = ensemble_classifiers.get(7, {}).get("lgb")
        if lgb_7d is not None:
            imp = lgb_7d.feature_importances_
            top_idx = np.argsort(imp)[-5:][::-1]
            feature_contributions = [
                {"feature": feature_names[i], "importance": round(float(imp[i]), 4)}
                for i in top_idx
            ]
    except Exception:
        pass

    return {
        "status": "ok",
        "gold_type": gold_type,
        "model_trained": model_pkg.get("training_date"),
        "current_date": date.today().isoformat(),
        "current_close": current_close,
        # Legacy fields (backward compat)
        "direction": "up" if consensus in ("strong_up", "lean_up") else "down",
        "direction_probability": round(votes_up / max(total_h, 1), 4),
        "predicted_return_7d_pct": round(pred_return * 100, 2),
        "predicted_price_7d": predicted_price,
        "confidence_low": confidence_low,
        "confidence_high": confidence_high,
        # Multi-horizon fields
        "horizon_predictions": horizon_predictions,
        "consensus": consensus,
        "consensus_label": consensus_label,
        "votes_up": votes_up,
        "total_horizons": total_h,
        "feature_contributions": feature_contributions,
    }
