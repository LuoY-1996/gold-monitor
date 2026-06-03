/** Gold types available in the system */
export const GOLD_TYPES = {
  XAU_USD: 'xau_usd',
  AU9999: 'au9999',
} as const;

export type GoldType = (typeof GOLD_TYPES)[keyof typeof GOLD_TYPES];

/** Display names for gold types */
export const GOLD_LABELS: Record<string, string> = {
  xau_usd: '国际金价 (XAU/USD)',
  au9999: '上海金 (Au99.99)',
};

/** Currency/unit per gold type */
export const GOLD_UNITS: Record<string, string> = {
  xau_usd: '美元/盎司',
  au9999: '元/克',
};

/** API refresh interval in milliseconds */
export const REFRESH_INTERVAL = 1_200_000; // 20 minutes
