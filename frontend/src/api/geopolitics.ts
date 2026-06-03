/** Key events affecting gold prices — fetched from backend API */

import apiClient from './client';

export interface GeoEvent {
  id: number;
  date: string;
  title: string;
  description: string | null;
  impact: number;       // 1=low, 2=medium, 3=high
  direction: number;    // +1=利多, -1=利空, 0=中性
  category: 'fed' | 'geopolitics' | 'economy' | 'china' | 'market';
  risk_regions: string[];
  source_url: string | null;
}

export interface GeoRiskIndex {
  trade_date: string;
  risk_score: number;
  event_intensity: number;
  active_conflicts: number;
  news_sentiment: number | null;
  news_headline_count: number | null;
  regional_scores: Record<string, number> | null;
}

/** Fetch geopolitical events from backend */
export async function fetchGeoEvents(months = 3): Promise<GeoEvent[]> {
  const { data } = await apiClient.get<GeoEvent[]>('/geo/events', {
    params: { months },
  });
  return data;
}

/** Fetch geopolitical risk index history */
export async function fetchGeoRisk(params?: {
  start_date?: string;
  end_date?: string;
  limit?: number;
}): Promise<GeoRiskIndex[]> {
  const { data } = await apiClient.get<GeoRiskIndex[]>('/geo/risk', { params });
  return data;
}

/** Fetch latest geopolitical risk score */
export async function fetchLatestGeoRisk(): Promise<GeoRiskIndex | null> {
  const { data } = await apiClient.get<GeoRiskIndex | null>('/geo/risk/latest');
  return data;
}

/** Legacy: getGeoRisks for static regional risk display */
export function getGeoRisks() {
  return [
    {
      region: 'russia_ukraine',
      label: '🇷🇺🇺🇦 俄乌冲突',
      status: '持续中（2022.2至今）',
      riskLevel: 'high' as const,
      latestEvent: '2026.01：和谈陷入僵局，领土分歧严重，战线持续',
      goldImpact: '长期冲突推高全球避险需求，持续支撑金价',
    },
    {
      region: 'us_israel_iran',
      label: '🇺🇸🇮🇱🇮🇷 美以伊对峙',
      status: '持续升级（2023.10至今）',
      riskLevel: 'high' as const,
      latestEvent: '2026.06：美国追加对伊全面制裁，霍尔木兹局势紧张',
      goldImpact: '中东全面战争风险是当前金价最大上行驱动力之一',
    },
    {
      region: 'us_china',
      label: '🇺🇸🇨🇳 中美博弈',
      status: '持续紧张（2018至今）',
      riskLevel: 'high' as const,
      latestEvent: '2026年：关税战延续、科技封锁加深、台海南海军事对峙常态化',
      goldImpact: '全球两大经济体脱钩推高系统性风险，利好黄金长期需求',
    },
  ];
}

/** Legacy: getGeoEvents — use fetchGeoEvents() for live data */
export function getGeoEvents(): GeoEvent[] {
  return [];
}
