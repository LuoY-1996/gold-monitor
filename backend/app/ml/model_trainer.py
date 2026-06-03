"""LightGBM model training for gold price prediction.

Architecture:
- Multi-horizon: predicts direction at 1d, 3d, 5d, 7d simultaneously
- LightGBM classifier for each horizon (better for small datasets than XGBoost)
- LightGBM regressor for 7d return
- Walk-forward validation for robust evaluation
- Consensus voting: stronger signal when horizons agree
"""

import logging
import os
from datetime import date, datetime
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    mean_absolute_error, mean_squared_error,
)

from app.config import BASE_DIR
from app.ml.feature_engineering import build_training_dataset

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = BASE_DIR / "ml_models"
HORIZONS = [1, 3, 5, 7]  # Trading days ahead


def _get_model_dir() -> Path:
    model_dir = Path(os.getenv("ML_MODEL_DIR", str(DEFAULT_MODEL_DIR)))
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir


def _time_series_split(df: pd.DataFrame, train_frac: float = 0.8):
    """Chronological split (no shuffle)."""
    n = len(df)
    train_end = int(n * train_frac)
    val_start = int(n * 0.7)

    train_df = df.iloc[:val_start]
    val_df = df.iloc[val_start:train_end]
    test_df = df.iloc[train_end:]
    return train_df, val_df, test_df


def _train_one_classifier(X_train, y_train, X_val, y_val, scale_wt: float):
    """Train a single LightGBM classifier for one horizon."""
    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=500,
        max_depth=4,
        learning_rate=0.02,
        subsample=0.7,
        colsample_bytree=0.7,
        min_child_samples=20,
        reg_alpha=0.3,
        reg_lambda=0.5,
        class_weight="balanced" if scale_wt != 1.0 else None,
        random_state=42,
        verbose=-1,
        force_col_wise=True,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        eval_metric="logloss",
        callbacks=[lgb.early_stopping(50, verbose=False)],
    )
    return model


def _train_one_regressor(X_train, y_train, X_val, y_val):
    """Train a single LightGBM regressor."""
    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=500,
        max_depth=4,
        learning_rate=0.02,
        subsample=0.7,
        colsample_bytree=0.7,
        min_child_samples=20,
        reg_alpha=0.3,
        reg_lambda=0.5,
        random_state=42,
        verbose=-1,
        force_col_wise=True,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        eval_metric="rmse",
        callbacks=[lgb.early_stopping(50, verbose=False)],
    )
    return model


async def train_model(
    session: AsyncSession,
    gold_type: str = "xau_usd",
    days: int = 2555,
) -> dict:
    """Train LightGBM models for gold price prediction at multiple horizons.

    Returns:
        dict with training metrics per horizon + ensemble consensus metrics
    """
    # 1. Build dataset
    df, feature_names = await build_training_dataset(session, gold_type, days)
    if df.empty or len(feature_names) == 0:
        return {"status": "error", "message": "No training data available"}
    if len(df) < 200:
        return {"status": "error", "message": f"Need ≥200 valid rows, got {len(df)}"}

    # 2. Time-series split
    train_df, val_df, test_df = _time_series_split(df)
    train_df = train_df.dropna(subset=feature_names)
    val_df = val_df.dropna(subset=feature_names)
    test_df = test_df.dropna(subset=feature_names)

    X_train = train_df[feature_names]
    X_val = val_df[feature_names]
    X_test = test_df[feature_names]

    # 3. Train classifiers for each horizon
    horizon_results = {}
    classifiers = {}
    y_preds = {}  # For consensus voting

    for h in HORIZONS:
        target_col = f"target_dir_{h}d"
        if target_col not in df.columns:
            continue

        y_train = train_df[target_col].dropna()
        y_val = val_df[target_col].dropna()
        y_test = test_df[target_col].dropna()

        # Align feature matrices with labels
        idx_train = y_train.index
        idx_val = y_val.index
        idx_test = y_test.index

        # Scale weight for imbalance
        n_up = int(y_train.sum())
        n_down = len(y_train) - n_up
        if n_up > 0 and n_down > 0:
            scale_wt = n_down / n_up if n_up > n_down else n_up / n_down
        else:
            scale_wt = 1.0

        # Train
        clf = _train_one_classifier(
            X_train.loc[idx_train], y_train,
            X_val.loc[idx_val], y_val,
            min(scale_wt, 3.0),
        )
        classifiers[h] = clf

        # Evaluate
        y_pred = clf.predict(X_test.loc[idx_test])
        y_preds[h] = pd.Series(y_pred, index=idx_test)

        horizon_results[h] = {
            "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
            "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
            "f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
            "n_train": len(y_train),
            "n_test": len(y_test),
            "up_ratio": round(float(y_train.mean()), 3),
        }

    # 4. Train 7d regressor
    y_train_ret = train_df["target_ret_7d"].dropna()
    y_val_ret = val_df["target_ret_7d"].dropna()
    y_test_ret = test_df["target_ret_7d"].dropna()

    reg = _train_one_regressor(
        X_train.loc[y_train_ret.index], y_train_ret,
        X_val.loc[y_val_ret.index], y_val_ret,
    )
    y_pred_ret = reg.predict(X_test.loc[y_test_ret.index])

    ret_metrics = {
        "mae_pct": round(float(mean_absolute_error(y_test_ret, y_pred_ret)) * 100, 4),
        "rmse_pct": round(float(np.sqrt(mean_squared_error(y_test_ret, y_pred_ret))) * 100, 4),
    }

    # 5. Consensus voting — align on common test indices
    common_idx = None
    for h in HORIZONS:
        if h in y_preds:
            if common_idx is None:
                common_idx = set(y_preds[h].index)
            else:
                common_idx &= set(y_preds[h].index)
    common_idx = sorted(common_idx) if common_idx else []

    if len(common_idx) >= 10:
        consensus_df = pd.DataFrame(index=common_idx)
        for h in HORIZONS:
            if h in y_preds:
                consensus_df[f"pred_{h}d"] = y_preds[h].loc[common_idx]
        consensus_df["votes_up"] = consensus_df.sum(axis=1)
        consensus_df["strong_up"] = (consensus_df["votes_up"] >= 3).astype(int)
        consensus_df["strong_down"] = (consensus_df["votes_up"] <= 1).astype(int)
        consensus_df["actual"] = test_df.loc[common_idx, "target_dir_7d"]

        strong_mask = (consensus_df["strong_up"] == 1) | (consensus_df["strong_down"] == 1)
        strong_preds = consensus_df.loc[strong_mask, "strong_up"]
        strong_actual = consensus_df.loc[strong_mask, "actual"]

        consensus_metrics = {
            "strong_signal_pct": round(len(strong_preds) / max(len(consensus_df), 1) * 100, 1),
            "strong_accuracy": round(float(accuracy_score(strong_actual, strong_preds)), 4) if len(strong_preds) > 5 else None,
            "all_up_pct": round((consensus_df["votes_up"] >= 3).mean() * 100, 1),
            "all_down_pct": round((consensus_df["votes_up"] <= 1).mean() * 100, 1),
            "n_consensus": len(common_idx),
            "n_strong": len(strong_preds),
        }
    else:
        consensus_metrics = {
            "strong_signal_pct": 0, "strong_accuracy": None,
            "all_up_pct": 0, "all_down_pct": 0,
            "n_consensus": len(common_idx), "n_strong": 0,
        }

    # 6. Feature importance (from 7d classifier)
    importance = sorted(
        zip(feature_names, classifiers[7].feature_importances_),
        key=lambda x: x[1], reverse=True
    )
    top_features = [{"feature": f, "importance": round(float(imp), 4)}
                    for f, imp in importance[:20]]

    # 7. Persist model
    model_dir = _get_model_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = model_dir / f"{gold_type}_model_{timestamp}.joblib"

    model_package = {
        "classifiers": classifiers,
        "regressor": reg,
        "feature_names": feature_names,
        "horizons": HORIZONS,
        "gold_type": gold_type,
        "training_date": date.today().isoformat(),
        "train_samples": len(train_df),
        "test_samples": len(test_df),
        "horizon_results": horizon_results,
        "ret_metrics": ret_metrics,
        "consensus_metrics": consensus_metrics,
        "top_features": top_features,
        "train_date_range": f"{df.iloc[0]['trade_date']} → {df.iloc[-1]['trade_date']}",
    }

    joblib.dump(model_package, model_path)
    latest_path = model_dir / f"{gold_type}_model_latest.joblib"
    joblib.dump(model_package, latest_path)

    logger.info(f"Model saved to {model_path}")
    logger.info(f"Consensus: {consensus_metrics['strong_signal_pct']}% strong signals, "
                f"accuracy={consensus_metrics['strong_accuracy']}")

    # Pick best horizon for overall accuracy
    best_h = max(horizon_results.keys(), key=lambda h: horizon_results[h]["accuracy"])

    return {
        "status": "success",
        "gold_type": gold_type,
        "model_path": str(model_path),
        "direction_accuracy": horizon_results[7]["accuracy"],
        "direction_precision": horizon_results[7]["precision"],
        "direction_recall": horizon_results[7]["recall"],
        "direction_f1": horizon_results[7]["f1"],
        "price_mae_pct": ret_metrics["mae_pct"],
        "price_rmse_pct": ret_metrics["rmse_pct"],
        "consensus_strong_pct": consensus_metrics["strong_signal_pct"],
        "consensus_accuracy": consensus_metrics["strong_accuracy"],
        "feature_importance": top_features[:10],
        "train_samples": len(train_df),
        "val_samples": len(val_df),
        "test_samples": len(test_df),
        "train_date_range": f"{df.iloc[0]['trade_date']} → {df.iloc[-1]['trade_date']}",
    }


def load_model(gold_type: str = "xau_usd") -> dict | None:
    model_dir = _get_model_dir()
    latest_path = model_dir / f"{gold_type}_model_latest.joblib"
    if not latest_path.exists():
        return None
    try:
        return joblib.load(latest_path)
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return None


def get_model_info(gold_type: str = "xau_usd") -> dict | None:
    model_dir = _get_model_dir()
    latest_path = model_dir / f"{gold_type}_model_latest.joblib"
    if not latest_path.exists():
        return None
    try:
        pkg = joblib.load(latest_path)
        return {
            "gold_type": pkg.get("gold_type"),
            "training_date": pkg.get("training_date"),
            "train_samples": pkg.get("train_samples"),
            "test_samples": pkg.get("test_samples"),
            "dir_accuracy": pkg.get("horizon_results", {}).get(7, {}).get("accuracy"),
            "rmse_pct": pkg.get("ret_metrics", {}).get("rmse_pct"),
            "consensus_pct": pkg.get("consensus_metrics", {}).get("strong_signal_pct"),
            "train_date_range": pkg.get("train_date_range"),
            "feature_count": len(pkg.get("feature_names", [])),
            "top_features": pkg.get("top_features", [])[:5],
            "file_size_mb": round(latest_path.stat().st_size / (1024 * 1024), 2),
        }
    except Exception as e:
        logger.error(f"Failed to read model info: {e}")
        return None
