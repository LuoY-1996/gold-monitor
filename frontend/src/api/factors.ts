import apiClient from './client';

export interface FactorDataPoint {
  trade_date: string;
  value: number | null;
}

export interface FactorResponse {
  factor_type: string;
  count: number;
  data: FactorDataPoint[];
}

export interface CorrelationItem {
  factor: string;
  label: string;
  pearson_correlation: number;
  rolling_corr_60d: number | null;
  data_points: number;
}

export interface CorrelationResponse {
  status: string;
  gold_type: string;
  factors: string[];
  correlations: CorrelationItem[];
}

export async function fetchFactorHistory(
  factorType: string,
  params?: { limit?: number }
): Promise<FactorResponse> {
  const { data } = await apiClient.get<FactorResponse>(`/factors/${factorType}`, { params });
  return data;
}

export async function fetchCorrelation(
  goldType: string,
  days?: number
): Promise<CorrelationResponse> {
  const { data } = await apiClient.get<CorrelationResponse>(`/factors/correlation/${goldType}`, {
    params: { days: days ?? 365 },
  });
  return data;
}
