import apiClient from './client';

export interface UsdCnyRealtime {
  available: boolean;
  trade_date: string | null;
  close: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
}

export interface GoldPremium {
  xau_usd: number;
  au9999: number;
  usd_cny: number;
  implied_rate: number | null;
  theoretical_au9999: number | null;
  premium_pct: number | null;
}

export async function fetchUsdCnyRealtime(): Promise<UsdCnyRealtime> {
  const { data } = await apiClient.get<UsdCnyRealtime>('/forex/usd-cny/realtime');
  return data;
}

export interface UsdCnyHistoryPoint {
  trade_date: string;
  close: number;
}

export interface UsdCnyHistoryResponse {
  count: number;
  data: UsdCnyHistoryPoint[];
}

export async function fetchUsdCnyHistory(limit = 90): Promise<UsdCnyHistoryResponse> {
  const { data } = await apiClient.get<UsdCnyHistoryResponse>('/forex/usd-cny/history', {
    params: { limit },
  });
  return data;
}

export async function fetchGoldPremium(): Promise<GoldPremium> {
  const { data } = await apiClient.get<GoldPremium>('/forex/premium');
  return data;
}
