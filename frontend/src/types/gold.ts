/** Gold price data point */
export interface GoldPricePoint {
  trade_date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number;
  volume: number | null;
}

/** API response wrapper for gold price history */
export interface GoldPriceResponse {
  gold_type: string;
  count: number;
  data: GoldPricePoint[];
}

/** Real-time gold price */
export interface GoldRealtime {
  gold_type: string;
  available: boolean;
  trade_date: string | null;
  close: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  volume: number | null;
}
