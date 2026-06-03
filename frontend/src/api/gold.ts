import apiClient from './client';
import type { GoldPriceResponse, GoldRealtime } from '../types/gold';

/** Fetch real-time gold price */
export async function fetchRealtime(goldType: string): Promise<GoldRealtime> {
  const { data } = await apiClient.get<GoldRealtime>(`/gold/${goldType}/realtime`);
  return data;
}

/** Fetch historical gold prices */
export async function fetchHistory(
  goldType: string,
  params?: { start_date?: string; end_date?: string; limit?: number }
): Promise<GoldPriceResponse> {
  const { data } = await apiClient.get<GoldPriceResponse>(`/gold/${goldType}/history`, { params });
  return data;
}

/** Trigger a manual data fetch (for admin/debug) */
export async function triggerFetch(): Promise<{ status: string; results: Record<string, unknown> }> {
  const { data } = await apiClient.post('/gold/fetch');
  return data;
}
