export interface HorizonPrediction {
  direction: 'up' | 'down';
  probability: number;
}

/** ML prediction result */
export interface PredictionResult {
  status: string;
  gold_type: string;
  model_trained: string | null;
  message: string | null;
  current_date: string | null;
  current_close: number | null;
  direction: 'up' | 'down' | null;
  direction_probability: number | null;
  predicted_return_7d_pct: number | null;
  predicted_price_7d: number | null;
  confidence_low: number | null;
  confidence_high: number | null;
  horizon_predictions: Record<string, HorizonPrediction>;
  consensus: string | null;
  consensus_label: string | null;
  votes_up: number | null;
  total_horizons: number | null;
  feature_contributions: { feature: string; importance: number }[];
}

/** Model training result */
export interface TrainingResult {
  status: string;
  gold_type: string | null;
  message: string | null;
  model_path: string | null;
  direction_accuracy: number | null;
  direction_precision: number | null;
  direction_recall: number | null;
  direction_f1: number | null;
  price_mae_pct: number | null;
  price_rmse_pct: number | null;
  consensus_strong_pct: number | null;
  consensus_accuracy: number | null;
  feature_importance: { feature: string; importance: number }[];
  train_samples: number | null;
  test_samples: number | null;
  train_date_range: string | null;
}

/** Model metadata */
export interface ModelInfo {
  gold_type: string | null;
  training_date: string | null;
  train_samples: number | null;
  test_samples: number | null;
  dir_accuracy: number | null;
  rmse_pct: number | null;
  consensus_pct: number | null;
  train_date_range: string | null;
  feature_count: number | null;
  top_features: { feature: string; importance: number }[];
  file_size_mb: number | null;
}
