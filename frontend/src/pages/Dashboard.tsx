import { useEffect, useState, useCallback } from 'react';
import { Row, Col, message, Card, Spin, Statistic, Button } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { useGoldStore } from '../store/useGoldStore';
import PriceCard from '../components/cards/PriceCard';
import { REFRESH_INTERVAL } from '../utils/constants';
import { fetchGoldPremium, type GoldPremium } from '../api/forex';

export default function Dashboard() {
  const {
    xauRealtime,
    auRealtime,
    fetchAll,
  } = useGoldStore();

  const [refreshing, setRefreshing] = useState(false);
  const [premium, setPremium] = useState<GoldPremium | null>(null);

  const loadData = useCallback(async () => {
    setRefreshing(true);
    try {
      await fetchAll();
      const p = await fetchGoldPremium();
      setPremium(p);
    } catch {
      message.error('获取数据失败，请检查后端服务是否启动');
    } finally {
      setRefreshing(false);
    }
  }, [fetchAll]);

  useEffect(() => { loadData(); }, [loadData]);
  useEffect(() => {
    const interval = setInterval(loadData, REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, [loadData]);

  return (
    <div>
      <h1 style={{ marginBottom: 24, fontSize: 24, fontWeight: 600 }}>
        🪙 实时金价
        <span style={{ fontSize: 13, color: '#999', fontWeight: 400, marginLeft: 12 }}>
          每 20 分钟自动刷新
        </span>
        <Button
          icon={<ReloadOutlined spin={refreshing} />}
          onClick={loadData}
          loading={refreshing}
          size="small"
          style={{ marginLeft: 12 }}
        >
          手动刷新
        </Button>
      </h1>

      {/* Price Cards */}
      <Row gutter={[24, 24]} style={{ marginBottom: 24 }}>
        <Col xs={24} md={12}>
          <PriceCard goldType="xau_usd" realtime={xauRealtime} loading={refreshing && !xauRealtime} />
        </Col>
        <Col xs={24} md={12}>
          <PriceCard goldType="au9999" realtime={auRealtime} loading={refreshing && !auRealtime} />
        </Col>
      </Row>

      {/* Premium + Forex — side by side */}
      {premium && premium.premium_pct !== null && (
        <Row gutter={[24, 24]} style={{ marginBottom: 0 }}>
          <Col xs={24} lg={16}>
            <Card title="📊 国内外金价溢价分析" style={{ height: '100%' }}>
              <Row gutter={[16, 12]}>
                <Col xs={12} sm={6}>
                  <Statistic title="国际金价 (折算)" value={premium.theoretical_au9999 ?? 0}
                    precision={2} prefix="¥" suffix="/克" valueStyle={{ fontSize: 20 }} />
                  <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>
                    = {premium.xau_usd.toFixed(0)} × {premium.usd_cny.toFixed(4)} ÷ 31.1
                  </div>
                </Col>
                <Col xs={12} sm={6}>
                  <Statistic title="国内金价" value={premium.au9999}
                    precision={2} prefix="¥" suffix="/克" valueStyle={{ fontSize: 20 }} />
                </Col>
                <Col xs={12} sm={6}>
                  <Statistic title="溢价" value={premium.premium_pct}
                    precision={2} suffix="%"
                    valueStyle={{ fontSize: 26, fontWeight: 700,
                      color: premium.premium_pct >= 0 ? '#cf1322' : '#3f8600' }} />
                  <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>
                    {premium.premium_pct >= 0 ? '国内溢价' : '国内折价'}
                    {Math.abs(premium.premium_pct) < 1 ? ' (正常)' : ' (关注)'}
                  </div>
                </Col>
                <Col xs={12} sm={6}>
                  <Statistic title="价差" value={premium.au9999 - (premium.theoretical_au9999 ?? 0)}
                    precision={2} prefix="¥" suffix="/克" valueStyle={{ fontSize: 20 }} />
                </Col>
              </Row>
            </Card>
          </Col>
          <Col xs={24} lg={8}>
            <Card title="💱 美元/人民币" style={{ height: '100%' }}>
              <Statistic title="当前汇率" value={premium.usd_cny} precision={4}
                valueStyle={{ fontSize: 30, fontWeight: 700, color: '#1677ff' }}
                suffix={<span style={{ fontSize: 12, color: '#888' }}>USD/CNY</span>} />
              {premium.implied_rate && (
                <div style={{ marginTop: 12, fontSize: 13 }}>
                  金价隐含汇率: <strong>{premium.implied_rate}</strong>
                  <span style={{ marginLeft: 8, fontSize: 12, color: (premium.implied_rate > premium.usd_cny) ? '#cf1322' : '#3f8600' }}>
                    ({(premium.implied_rate > premium.usd_cny) ? '人民币低估' : '人民币高估'})
                  </span>
                </div>
              )}
            </Card>
          </Col>
        </Row>
      )}

    </div>
  );
}
