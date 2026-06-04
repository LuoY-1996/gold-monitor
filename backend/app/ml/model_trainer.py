"""Gold price prediction — ensemble model training with hyperparameter tuning.

Architecture (three upgrades over the previous version):
1. Optuna hyperparameter search — finds optimal LightGBM params per dataset
2. TimeSeriesSplit CV — more robust evaluation across market regimes
3. Multi-model ensemble — LightGBM + XGBoost + Random Forest soft voting

Each horizon (1d/3d/5d/7d) gets its own ensemble of 3 classifiers.
The 7d return regressor also gets an ensemble of 3 regressors.
"""

import logging
import os
import warnings
from datetime import date, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

# ── Scikit-learn ──
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    mean_absolute_error, mean_squared_error,
)
from sklearn.model_selection import TimeSeriesSplit

from app.config import BASE_DIR
from app.ml.feature_engineering import build_training_dataset

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning)

DEFAULT_MODEL_DIR = BASE_DIR / "ml_models"
HORIZONS = [1, 3, 5, 7]

# ── Optuna trials ──
_optuna_available = False
try:
    import optuna
    _optuna_available = True
except ImportError:
    logger.warning("optuna not installed; skipping hyperparameter tuning")

# ── Model type labels ──
MODEL_LGB = "lgb"
MODEL_XGB = "xgb"
MODEL_RF = "rf"
ALL_MODEL_TYPES = [MODEL_LGB, MODEL_XGB, MODEL_RF]


# ═══════════════════════════════════════════════════════════════
#  Paths
# ═══════════════════════════════════════════════════════════════

def _get_model_dir() -> Path:
    model_dir = Path(os.getenv("ML_MODEL_DIR", str(DEFAULT_MODEL_DIR)))
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir


# ═══════════════════════════════════════════════════════════════
#  Data splitting
# ═══════════════════════════════════════════════════════════════

def _time_series_split(df: pd.DataFrame, feature_names: list[str]):
    """Chronological train / val / test split (no shuffle)."""
    n = len(df)
    train_end = int(n * 0.8)
    val_start = int(n * 0.7)

    train_df = df.iloc[:val_start].dropna(subset=feature_names)
    val_df = df.iloc[val_start:train_end].dropna(subset=feature_names)
    test_df = df.iloc[train_end:].dropna(subset=feature_names)
    return train_df, val_df, test_df


def _cv_metrics(
    df: pd.DataFrame, feature_names: list[str],
    target_col: str, build_fn, n_splits: int = 5,
) -> list[dict]:
    """Run TimeSeriesSplit CV and return per-fold metrics.

    build_fn(X_train, y_train, X_val, y_val, X_test) → y_pred_test
    Each fold requires ≥100 train samples with both classes present.
    """
    tscv = TimeSeriesSplit(n_splits=n_splits)
    fold_scores = []
    total_folds = 0

    for fold, (train_idx, test_idx) in enumerate(tscv.split(df)):
        total_folds += 1
        train_df = df.iloc[train_idx].dropna(subset=feature_names)
        test_df = df.iloc[test_idx].dropna(subset=feature_names)

        if len(train_df) < 100 or len(test_df) < 20:
            logger.debug(f"[CV] fold {fold}: too small ({len(train_df)}/{len(test_df)}), skipping")
            continue

        X_tr = train_df[feature_names]
        y_tr = train_df[target_col]
        X_te = test_df[feature_names]
        y_te = test_df[target_col]

        # Skip fold if either class is missing in train or test
        if y_tr.nunique() < 2 or y_te.nunique() < 2:
            logger.debug(f"[CV] fold {fold}: only one class present, skipping")
            continue

        # Sub-split train into train/val for early stopping
        split_pt = int(len(X_tr) * 0.85)
        X_tr2, X_val2 = X_tr.iloc[:split_pt], X_tr.iloc[split_pt:]
        y_tr2, y_val2 = y_tr.iloc[:split_pt], y_tr.iloc[split_pt:]

        if len(X_val2) < 10:
            logger.debug(f"[CV] fold {fold}: validation set too small ({len(X_val2)}), skipping")
            continue

        try:
            y_pred = build_fn(X_tr2, y_tr2, X_val2, y_val2, X_te)
            acc = float(accuracy_score(y_te, y_pred))
            fold_scores.append({
                "fold": fold,
                "accuracy": round(acc, 4),
                "n_train": len(X_tr),
                "n_test": len(X_te),
            })
            logger.info(f"[CV] fold {fold}: accuracy={acc:.4f} (train={len(X_tr)}, test={len(X_te)})")
        except Exception as e:
            logger.warning(f"[CV] fold {fold} failed: {type(e).__name__}: {e}")

    if not fold_scores:
        logger.warning(f"[CV] All {total_folds} folds failed — no CV metrics produced")

    return fold_scores


# ═══════════════════════════════════════════════════════════════
#  Optuna hyperparameter tuning (LightGBM only — biggest impact)
# ═══════════════════════════════════════════════════════════════

def _tune_lightgbm(
    X_train, y_train, X_val, y_val,
    n_trials: int = 25,
) -> dict:
    """Run Optuna to find best LightGBM hyperparameters.

    Returns best params dict. Falls back to defaults if optuna unavailable.
    """
    if not _optuna_available:
        return {}

    # Balance weight for objective function
    scale_pos = (len(y_train) - y_train.sum()) / max(y_train.sum(), 1)
    scale_pos = min(scale_pos, 5.0)

    def objective(trial):
        params = {
            "objective": "binary",
            "n_estimators": trial.suggest_int("n_estimators", 100, 800, step=50),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.1, log=True),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.3, 1.0),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 50),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-4, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-4, 10.0, log=True),
            "min_split_gain": trial.suggest_float("min_split_gain", 0.0, 1.0),
            "class_weight": "balanced",
            "random_state": 42,
            "verbose": -1,
            "force_col_wise": True,
        }

        model = None
        try:
            import lightgbm as lgb
            model = lgb.LGBMClassifier(**params)
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                eval_metric="logloss",
                callbacks=[lgb.early_stopping(30, verbose=False)],
            )
            y_pred = model.predict(X_val)
            return accuracy_score(y_val, y_pred)
        except Exception:
            return 0.0

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    best = study.best_params
    logger.info(f"[Optuna] best params: {best}, best val accuracy: {study.best_value:.4f}")
    return best


# ═══════════════════════════════════════════════════════════════
#  Individual model builders
# ═══════════════════════════════════════════════════════════════

def _build_lgb_classifier(X_train, y_train, X_val, y_val, best_params: dict | None = None):
    """Train a LightGBM classifier with optional tuned params."""
    import lightgbm as lgb

    params = {
        "objective": "binary",
        "n_estimators": 500,
        "max_depth": 4,
        "learning_rate": 0.02,
        "subsample": 0.7,
        "colsample_bytree": 0.7,
        "min_child_samples": 20,
        "reg_alpha": 0.3,
        "reg_lambda": 0.5,
        "class_weight": "balanced",
        "random_state": 42,
        "verbose": -1,
        "force_col_wise": True,
    }
    if best_params:
        params.update(best_params)

    model = lgb.LGBMClassifier(**params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        eval_metric="logloss",
        callbacks=[lgb.early_stopping(30, verbose=False)],
    )
    return model


def _build_xgb_classifier(X_train, y_train, X_val, y_val):
    """Train an XGBoost classifier with balanced weighting."""
    from xgboost import XGBClassifier

    scale_pos = (len(y_train) - y_train.sum()) / max(y_train.sum(), 1)
    scale_pos = min(scale_pos, 5.0)

    model = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.03,
        subsample=0.7,
        colsample_bytree=0.7,
        reg_alpha=0.3,
        reg_lambda=0.5,
        scale_pos_weight=scale_pos,
        random_state=42,
        verbosity=0,
        early_stopping_rounds=30,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )
    return model


def _build_rf_classifier(X_train, y_train, X_val=None, y_val=None):
    """Train a Random Forest classifier."""
    n_up = int(y_train.sum())
    n_down = len(y_train) - n_up
    class_weight = "balanced" if n_up > 0 and n_down > 0 else None

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=10,
        min_samples_split=20,
        class_weight=class_weight,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    return model


# ── Regressors ──

def _build_lgb_regressor(X_train, y_train, X_val, y_val, best_params: dict | None = None):
    import lightgbm as lgb
    params = {
        "objective": "regression",
        "n_estimators": 500,
        "max_depth": 4,
        "learning_rate": 0.02,
        "subsample": 0.7,
        "colsample_bytree": 0.7,
        "min_child_samples": 20,
        "reg_alpha": 0.3,
        "reg_lambda": 0.5,
        "random_state": 42,
        "verbose": -1,
        "force_col_wise": True,
    }
    if best_params:
        params.update(best_params)

    model = lgb.LGBMRegressor(**params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        eval_metric="rmse",
        callbacks=[lgb.early_stopping(30, verbose=False)],
    )
    return model


def _build_xgb_regressor(X_train, y_train, X_val, y_val):
    from xgboost import XGBRegressor
    model = XGBRegressor(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.03,
        subsample=0.7,
        colsample_bytree=0.7,
        reg_alpha=0.3,
        reg_lambda=0.5,
        random_state=42,
        verbosity=0,
        early_stopping_rounds=30,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )
    return model


def _build_rf_regressor(X_train, y_train, X_val=None, y_val=None):
    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=10,
        min_samples_split=20,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    return model


# ═══════════════════════════════════════════════════════════════
#  Ensemble soft voting
# ═══════════════════════════════════════════════════════════════

def ensemble_predict_classify(ensemble_dict, X) -> tuple[np.ndarray, np.ndarray]:
    """Soft voting: average predicted probabilities across all models.

    Returns (predictions, averaged_probabilities).
    """
    all_probs = []
    for model_type, clf in ensemble_dict.items():
        try:
            probs = clf.predict_proba(X)
        except Exception:
            preds = clf.predict(X)
            probs = np.zeros((len(preds), 2))
            probs[range(len(preds)), preds.astype(int)] = 1
        all_probs.append(probs)

    avg_probs = np.mean(all_probs, axis=0)
    predictions = np.argmax(avg_probs, axis=1)
    return predictions, avg_probs


def ensemble_predict_regress(ensemble_dict, X) -> np.ndarray:
    """Average regression predictions across all models."""
    all_preds = []
    for model_type, reg in ensemble_dict.items():
        all_preds.append(reg.predict(X))
    return np.mean(all_preds, axis=0)


# ═══════════════════════════════════════════════════════════════
#  Main training entry point
# ═══════════════════════════════════════════════════════════════

async def train_model(
    session: AsyncSession,
    gold_type: str = "xau_usd",
    days: int = 2555,
    tune: bool = True,
) -> dict:
    """Train ensemble models for gold price prediction.

    Args:
        session: DB session
        gold_type: 'xau_usd' or 'au9999'
        days: days of history to include
        tune: whether to run Optuna hyperparameter search

    Returns:
        dict with training metrics per horizon, ensemble + CV metrics
    """
    # ── 1. Build dataset ──
    df, feature_names = await build_training_dataset(session, gold_type, days)
    if df.empty or len(feature_names) == 0:
        return {"status": "error", "message": "No training data available"}
    if len(df) < 200:
        return {"status": "error", "message": f"Need ≥200 valid rows, got {len(df)}"}

    logger.info(f"Training dataset: {len(df)} rows, {len(feature_names)} features")

    # ── 2. Train / val / test split ──
    train_df, val_df, test_df = _time_series_split(df, feature_names)
    X_train, X_val, X_test = (
        train_df[feature_names], val_df[feature_names], test_df[feature_names],
    )

    logger.info(f"Split: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}")

    # ── 3. Optuna hyperparameter tuning ──
    best_params = {}
    if tune and _optuna_available and len(X_val) >= 30:
        logger.info("[Optuna] Searching for best LightGBM params…")
        best_params = _tune_lightgbm(X_train, train_df["target_dir_7d"], X_val, val_df["target_dir_7d"])
    elif tune and not _optuna_available:
        logger.info("[Optuna] Not available — using default parameters")

    # ── 4. Train ensemble classifiers for each horizon ──
    ensemble_classifiers = {}
    horizon_results = {}
    all_y_pred = {}  # for consensus voting

    for h in HORIZONS:
        target_col = f"target_dir_{h}d"
        if target_col not in df.columns:
            continue

        y_train = train_df[target_col].dropna()
        y_val = val_df[target_col].dropna()
        y_test = test_df[target_col].dropna()

        idx_train, idx_val, idx_test = y_train.index, y_val.index, y_test.index

        # Build each model type
        ensemble = {}

        # LightGBM
        ensemble[MODEL_LGB] = _build_lgb_classifier(
            X_train.loc[idx_train], y_train,
            X_val.loc[idx_val], y_val,
            best_params,
        )

        # XGBoost
        try:
            ensemble[MODEL_XGB] = _build_xgb_classifier(
                X_train.loc[idx_train], y_train,
                X_val.loc[idx_val], y_val,
            )
        except Exception as e:
            logger.warning(f"[{h}d] XGBoost failed: {e}")

        # Random Forest
        try:
            ensemble[MODEL_RF] = _build_rf_classifier(
                X_train.loc[idx_train], y_train,
            )
        except Exception as e:
            logger.warning(f"[{h}d] RandomForest failed: {e}")

        ensemble_classifiers[h] = ensemble

        # Evaluate ensemble on test set
        y_pred, _ = ensemble_predict_classify(ensemble, X_test.loc[idx_test])
        all_y_pred[h] = pd.Series(y_pred, index=idx_test)

        # Per-model metrics for comparison
        model_metrics = {}
        for mtype, clf in ensemble.items():
            try:
                mp = clf.predict(X_test.loc[idx_test])
                model_metrics[mtype] = round(float(accuracy_score(y_test, mp)), 4)
            except Exception:
                pass

        horizon_results[h] = {
            "ensemble_accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
            "ensemble_precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
            "ensemble_recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
            "ensemble_f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
            "n_train": len(y_train),
            "n_test": len(y_test),
            "up_ratio": round(float(y_train.mean()), 3),
            "per_model_acc": model_metrics,
        }

    # ── 5. Train ensemble regressors (7d return) ──
    y_train_ret = train_df["target_ret_7d"].dropna()
    y_val_ret = val_df["target_ret_7d"].dropna()
    y_test_ret = test_df["target_ret_7d"].dropna()

    ensemble_regressors = {}

    # LightGBM regressor
    ensemble_regressors[MODEL_LGB] = _build_lgb_regressor(
        X_train.loc[y_train_ret.index], y_train_ret,
        X_val.loc[y_val_ret.index], y_val_ret,
        {k: v for k, v in best_params.items() if k != "class_weight"},
    )

    # XGBoost regressor
    try:
        ensemble_regressors[MODEL_XGB] = _build_xgb_regressor(
            X_train.loc[y_train_ret.index], y_train_ret,
            X_val.loc[y_val_ret.index], y_val_ret,
        )
    except Exception as e:
        logger.warning(f"[reg] XGBoost failed: {e}")

    # Random Forest regressor
    try:
        ensemble_regressors[MODEL_RF] = _build_rf_regressor(
            X_train.loc[y_train_ret.index], y_train_ret,
        )
    except Exception as e:
        logger.warning(f"[reg] RandomForest failed: {e}")

    y_pred_ret = ensemble_predict_regress(ensemble_regressors, X_test.loc[y_test_ret.index])

    ret_metrics = {
        "mae_pct": round(float(mean_absolute_error(y_test_ret, y_pred_ret)) * 100, 4),
        "rmse_pct": round(float(np.sqrt(mean_squared_error(y_test_ret, y_pred_ret))) * 100, 4),
    }

    # ── 6. Consensus voting ──
    common_idx = None
    for h in HORIZONS:
        if h in all_y_pred:
            common_idx = (set(all_y_pred[h].index) if common_idx is None
                          else common_idx & set(all_y_pred[h].index))
    common_idx = sorted(common_idx) if common_idx else []

    if len(common_idx) >= 10:
        consensus_df = pd.DataFrame(index=common_idx)
        for h in HORIZONS:
            if h in all_y_pred:
                consensus_df[f"pred_{h}d"] = all_y_pred[h].loc[common_idx]
        consensus_df["votes_up"] = consensus_df.sum(axis=1)
        consensus_df["strong_up"] = (consensus_df["votes_up"] >= 3).astype(int)
        consensus_df["strong_down"] = (consensus_df["votes_up"] <= 1).astype(int)
        consensus_df["actual"] = test_df.loc[common_idx, "target_dir_7d"]

        strong_mask = (consensus_df["strong_up"] == 1) | (consensus_df["strong_down"] == 1)
        strong_preds = consensus_df.loc[strong_mask, "strong_up"]
        strong_actual = consensus_df.loc[strong_mask, "actual"]

        consensus_metrics = {
            "strong_signal_pct": round(len(strong_preds) / max(len(consensus_df), 1) * 100, 1),
            "strong_accuracy": (round(float(accuracy_score(strong_actual, strong_preds)), 4)
                                if len(strong_preds) > 5 else None),
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

    # ── 7. Cross-validation scores (extra robustness check) ──
    cv_scores = []
    try:
        cv_scores = _cv_metrics(
            df.dropna(subset=feature_names + ["target_dir_7d"]),
            feature_names, "target_dir_7d",
            lambda X_tr, y_tr, X_v, y_v, X_te: ensemble_predict_classify(
                _quick_ensemble(X_tr, y_tr, X_v, y_v), X_te
            )[0],
            n_splits=min(5, len(df) // 150),
        )
    except Exception as e:
        logger.warning(f"[CV] failed: {e}")

    cv_avg_acc = (round(float(np.mean([s["accuracy"] for s in cv_scores])), 4)
                  if cv_scores else None)

    # ── 8. Feature importance (from LightGBM 7d) ──
    if MODEL_LGB in ensemble_classifiers.get(7, {}):
        lgb_7d = ensemble_classifiers[7][MODEL_LGB]
        importance = sorted(
            zip(feature_names, lgb_7d.feature_importances_),
            key=lambda x: x[1], reverse=True,
        )
        top_features = [{"feature": f, "importance": round(float(imp), 4)}
                        for f, imp in importance[:20]]
    else:
        top_features = []

    # ── 9. Persist model ──
    model_dir = _get_model_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = model_dir / f"{gold_type}_model_{timestamp}.joblib"

    model_package = {
        "ensemble_classifiers": ensemble_classifiers,
        "ensemble_regressors": ensemble_regressors,
        "feature_names": feature_names,
        "horizons": HORIZONS,
        "gold_type": gold_type,
        "training_date": date.today().isoformat(),
        "train_samples": len(train_df),
        "val_samples": len(val_df),
        "test_samples": len(test_df),
        "horizon_results": horizon_results,
        "ret_metrics": ret_metrics,
        "consensus_metrics": consensus_metrics,
        "cv_scores": cv_scores,
        "cv_avg_accuracy": cv_avg_acc,
        "top_features": top_features,
        "best_params": best_params,
        "train_date_range": f"{df.iloc[0]['trade_date']} → {df.iloc[-1]['trade_date']}",
    }

    joblib.dump(model_package, model_path)
    latest_path = model_dir / f"{gold_type}_model_latest.joblib"
    joblib.dump(model_package, latest_path)

    logger.info(f"Model saved to {model_path}")
    logger.info(f"Ensemble 7d accuracy: {horizon_results.get(7, {}).get('ensemble_accuracy')}, "
                f"CV avg: {cv_avg_acc}")

    # Return a summary compatible with the API schema
    h7 = horizon_results.get(7, {})
    return {
        "status": "success",
        "gold_type": gold_type,
        "model_path": str(model_path),
        # Primary ensemble metrics (7d horizon)
        "direction_accuracy": h7.get("ensemble_accuracy"),
        "direction_precision": h7.get("ensemble_precision"),
        "direction_recall": h7.get("ensemble_recall"),
        "direction_f1": h7.get("ensemble_f1"),
        "price_mae_pct": ret_metrics["mae_pct"],
        "price_rmse_pct": ret_metrics["rmse_pct"],
        "consensus_strong_pct": consensus_metrics["strong_signal_pct"],
        "consensus_accuracy": consensus_metrics["strong_accuracy"],
        "feature_importance": top_features[:10],
        "train_samples": len(train_df),
        "val_samples": len(val_df),
        "test_samples": len(test_df),
        "train_date_range": f"{df.iloc[0]['trade_date']} → {df.iloc[-1]['trade_date']}",
        # Extra info
        "cv_avg_accuracy": cv_avg_acc,
        "per_model_accuracy": h7.get("per_model_acc"),
        "tuning_method": "optuna" if (tune and best_params) else "default",
    }


def _quick_ensemble(X_train, y_train, X_val, y_val) -> dict:
    """Build a quick 3-model ensemble for CV evaluation (no tuning)."""
    ensemble = {}
    try:
        import lightgbm as lgb
        ensemble[MODEL_LGB] = _build_lgb_classifier(X_train, y_train, X_val, y_val)
    except Exception:
        pass
    try:
        ensemble[MODEL_XGB] = _build_xgb_classifier(X_train, y_train, X_val, y_val)
    except Exception:
        pass
    try:
        ensemble[MODEL_RF] = _build_rf_classifier(X_train, y_train)
    except Exception:
        pass
    return ensemble


# ═══════════════════════════════════════════════════════════════
#  Model loading
# ═══════════════════════════════════════════════════════════════

def load_model(gold_type: str = "xau_usd") -> dict | None:
    """Load the latest model package.

    Supports both the new ensemble format and the legacy single-model format.
    """
    model_dir = _get_model_dir()
    latest_path = model_dir / f"{gold_type}_model_latest.joblib"
    if not latest_path.exists():
        return None
    try:
        pkg = joblib.load(latest_path)
        # Normalize legacy format to ensemble format
        if "classifiers" in pkg and "ensemble_classifiers" not in pkg:
            pkg = _convert_legacy_to_ensemble(pkg)
        return pkg
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return None


def _convert_legacy_to_ensemble(pkg: dict) -> dict:
    """Convert a legacy single-model package to the ensemble format."""
    logger.info("Converting legacy model to ensemble format")
    old_clfs = pkg.get("classifiers", {})
    old_reg = pkg.get("regressor")

    ensemble_clfs = {}
    for h, clf in old_clfs.items():
        ensemble_clfs[h] = {MODEL_LGB: clf}

    ensemble_regs = {}
    if old_reg is not None:
        ensemble_regs[MODEL_LGB] = old_reg

    pkg["ensemble_classifiers"] = ensemble_clfs
    pkg["ensemble_regressors"] = ensemble_regs
    return pkg


def get_model_info(gold_type: str = "xau_usd") -> dict | None:
    """Get model metadata without loading the full model."""
    model_dir = _get_model_dir()
    latest_path = model_dir / f"{gold_type}_model_latest.joblib"
    if not latest_path.exists():
        return None
    try:
        pkg = joblib.load(latest_path)
        h7 = pkg.get("horizon_results", {}).get(7, {})
        return {
            "gold_type": pkg.get("gold_type"),
            "training_date": pkg.get("training_date"),
            "train_samples": pkg.get("train_samples"),
            "test_samples": pkg.get("test_samples"),
            "dir_accuracy": h7.get("ensemble_accuracy") or h7.get("accuracy"),
            "rmse_pct": pkg.get("ret_metrics", {}).get("rmse_pct"),
            "consensus_pct": pkg.get("consensus_metrics", {}).get("strong_signal_pct"),
            "train_date_range": pkg.get("train_date_range"),
            "feature_count": len(pkg.get("feature_names", [])),
            "top_features": pkg.get("top_features", [])[:5],
            "file_size_mb": round(latest_path.stat().st_size / (1024 * 1024), 2),
            "cv_avg_accuracy": pkg.get("cv_avg_accuracy"),
            "ensemble_types": list(pkg.get("ensemble_classifiers", {}).get(7, {}).keys()),
        }
    except Exception as e:
        logger.error(f"Failed to read model info: {e}")
        return None
