import apiClient from './client';

export interface IndicatorDataPoint {
  date: string;
  close: number;
  ma_5: number | null;
  ma_10: number | null;
  ma_20: number | null;
  ma_60: number | null;
  ma_200: number | null;
  macd: number | null;
  macd_signal: number | null;
  macd_histogram: number | null;
  rsi_14: number | null;
  bb_upper: number | null;
  bb_middle: number | null;
  bb_lower: number | null;
  bb_width: number | null;
  atr_14: number | null;
}

export interface IndicatorResponse {
  status: string;
  gold_type: string;
  count: number;
  data: IndicatorDataPoint[];
}

export interface TrendSignal {
  indicator: string;
  signal: string;
  desc: string;
}

export interface TrendSignalsResponse {
  status: string;
  date: string;
  close: number;
  overall_trend: string;
  signals: TrendSignal[];
}

export async function fetchIndicators(goldType: string, days?: number): Promise<IndicatorResponse> {
  const { data } = await apiClient.get<IndicatorResponse>(`/indicators/${goldType}`, {
    params: { days: days ?? 365 },
  });
  return data;
}

export async function fetchTrendSignals(goldType: string, days?: number): Promise<TrendSignalsResponse> {
  const { data } = await apiClient.get<TrendSignalsResponse>(`/indicators/${goldType}/signals`, {
    params: { days: days ?? 365 },
  });
  return data;
}
