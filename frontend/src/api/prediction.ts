import apiClient from './client';
import type { PredictionResult, TrainingResult, ModelInfo } from '../types/prediction';

/** Get latest prediction for a gold type */
export async function fetchPrediction(goldType: string): Promise<PredictionResult> {
  const { data } = await apiClient.get<PredictionResult>(`/prediction/${goldType}`);
  return data;
}

/** Train a new model */
export async function trainModel(
  goldType: string,
  days = 730
): Promise<TrainingResult> {
  const { data } = await apiClient.post<TrainingResult>(
    `/prediction/train/${goldType}`,
    null,
    { params: { days } }
  );
  return data;
}

/** Get model metadata */
export async function fetchModelInfo(goldType: string): Promise<ModelInfo> {
  const { data } = await apiClient.get<ModelInfo>(`/prediction/${goldType}/model-info`);
  return data;
}

export interface ValuationResult {
  status: string;
  message?: string;
  r2: number | null;
  features_used: string[];
  coefficients: { feature: string; coefficient: number }[];
  current_fair_value: number | null;
  current_actual: number | null;
  current_gap_pct: number | null;
  current_percentile: number | null;
  valuation_bands: {
    overvalued_threshold: number;
    undervalued_threshold: number;
    extreme_overvalued: number;
    extreme_undervalued: number;
  } | null;
  fair_value_history: Record<string, number>;
  actual_history: Record<string, number>;
  gap_history: Record<string, number>;
}

/** Get macro fair-value valuation */
export async function fetchValuation(): Promise<ValuationResult> {
  const { data } = await apiClient.get<ValuationResult>('/prediction/valuation');
  return data;
}
