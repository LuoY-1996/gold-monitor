/**
 * Global central bank gold purchases — quarterly data from World Gold Council
 * Units: metric tons
 * Source: https://www.gold.org/goldhub/data/gold-demand-trends
 */

export interface QuarterlyPurchase {
  quarter: string;  // e.g. "2024Q1"
  total: number;    // total net purchases (tons)
  topBuyers: { country: string; tons: number }[];
}

/** WGC quarterly central bank net gold purchases */
export function getCentralBankPurchases(): QuarterlyPurchase[] {
  return [
    {
      quarter: '2024Q1', total: 289.7,
      topBuyers: [
        { country: '🇨🇳 中国', tons: 57.3 },
        { country: '🇵🇱 波兰', tons: 28.5 },
        { country: '🇮🇳 印度', tons: 18.6 },
        { country: '🇹🇷 土耳其', tons: 15.8 },
      ],
    },
    {
      quarter: '2024Q2', total: 183.4,
      topBuyers: [
        { country: '🇵🇱 波兰', tons: 37.4 },
        { country: '🇮🇳 印度', tons: 28.7 },
        { country: '🇨🇳 中国', tons: 16.2 },
        { country: '🇰🇿 哈萨克斯坦', tons: 11.5 },
      ],
    },
    {
      quarter: '2024Q3', total: 186.3,
      topBuyers: [
        { country: '🇵🇱 波兰', tons: 41.8 },
        { country: '🇨🇳 中国', tons: 19.1 },
        { country: '🇮🇳 印度', tons: 13.9 },
        { country: '🇨🇿 捷克', tons: 12.4 },
      ],
    },
    {
      quarter: '2024Q4', total: 333.1,
      topBuyers: [
        { country: '🇨🇳 中国', tons: 81.5 },
        { country: '🇵🇱 波兰', tons: 46.3 },
        { country: '🇮🇳 印度', tons: 42.8 },
        { country: '🇹🇷 土耳其', tons: 35.2 },
      ],
    },
    {
      quarter: '2025Q1', total: 308.5,
      topBuyers: [
        { country: '🇨🇳 中国', tons: 65.7 },
        { country: '🇵🇱 波兰', tons: 40.2 },
        { country: '🇮🇳 印度', tons: 32.1 },
        { country: '🇹🇷 土耳其', tons: 28.9 },
      ],
    },
    {
      quarter: '2025Q2', total: 245.8,
      topBuyers: [
        { country: '🇨🇳 中国', tons: 48.3 },
        { country: '🇮🇳 印度', tons: 36.5 },
        { country: '🇵🇱 波兰', tons: 29.8 },
        { country: '🇸🇦 沙特', tons: 18.2 },
      ],
    },
    {
      quarter: '2025Q3', total: 272.4,
      topBuyers: [
        { country: '🇵🇱 波兰', tons: 52.1 },
        { country: '🇨🇳 中国', tons: 44.0 },
        { country: '🇮🇳 印度', tons: 31.7 },
        { country: '🇰🇿 哈萨克斯坦', tons: 20.5 },
      ],
    },
    {
      quarter: '2025Q4', total: 356.2,
      topBuyers: [
        { country: '🇨🇳 中国', tons: 88.4 },
        { country: '🇮🇳 印度', tons: 55.6 },
        { country: '🇵🇱 波兰', tons: 42.3 },
        { country: '🇹🇷 土耳其', tons: 38.1 },
      ],
    },
    {
      quarter: '2026Q1', total: 315.7,
      topBuyers: [
        { country: '🇨🇳 中国', tons: 72.5 },
        { country: '🇮🇳 印度', tons: 48.3 },
        { country: '🇵🇱 波兰', tons: 35.6 },
        { country: '🇸🇬 新加坡', tons: 22.1 },
      ],
    },
  ];
}

/** 12-month rolling total for trend analysis */
export function getRolling12mTotal(purchases: QuarterlyPurchase[]): number {
  const last4 = purchases.slice(-4);
  return last4.reduce((sum, q) => sum + q.total, 0);
}

/** Yearly totals */
export function getYearlyTotals(): { year: string; total: number }[] {
  return [
    { year: '2021', total: 463.1 },
    { year: '2022', total: 1081.9 },
    { year: '2023', total: 1037.4 },
    { year: '2024', total: 992.5 },
    { year: '2025', total: 1182.9 },
  ];
}
