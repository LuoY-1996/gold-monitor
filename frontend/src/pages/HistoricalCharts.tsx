import { useEffect, useState, useCallback } from 'react';
import { Row, Col, Select, Card, Statistic, Tag } from 'antd';
import GoldChart from '../components/charts/GoldChart';
import { fetchIndicators, fetchTrendSignals, type IndicatorDataPoint, type TrendSignalsResponse } from '../api/indicators';
import { GOLD_LABELS } from '../utils/constants';

const GOLD_TYPES = [
  { key: 'xau_usd', label: GOLD_LABELS.xau_usd, unit: '$' },
  { key: 'au9999', label: GOLD_LABELS.au9999, unit: '¥' },
];

export default function HistoricalCharts() {
  const [days, setDays] = useState(365);
  const [dataMap, setDataMap] = useState<Record<string, IndicatorDataPoint[]>>({});
  const [signalsMap, setSignalsMap] = useState<Record<string, TrendSignalsResponse | null>>({});
  const [loading, setLoading] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const results = await Promise.all(
        GOLD_TYPES.map(async (gt) => {
          const [indData, sigData] = await Promise.all([
            fetchIndicators(gt.key, days),
            fetchTrendSignals(gt.key, days),
          ]);
          return { key: gt.key, indicators: indData.data || [], signals: sigData };
        })
      );
      const newDataMap: Record<string, IndicatorDataPoint[]> = {};
      const newSignalsMap: Record<string, TrendSignalsResponse | null> = {};
      for (const r of results) {
        newDataMap[r.key] = r.indicators;
        newSignalsMap[r.key] = r.signals;
      }
      setDataMap(newDataMap);
      setSignalsMap(newSignalsMap);
    } catch {
      console.error('Failed to load indicator data');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => { loadData(); }, [loadData]);

  const signalColor = (signal: string) => {
    switch (signal) {
      case 'bullish': case 'oversold': return 'red';
      case 'bearish': case 'overbought': return 'green';
      default: return 'default';
    }
  };

  return (
    <div>
      <h1 style={{ marginBottom: 24, fontSize: 24, fontWeight: 600 }}>
        📈 历史走势与技术指标
      </h1>

      {/* Controls */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col>
            <span style={{ marginRight: 8, color: '#666' }}>时间范围:</span>
            <Select value={days} onChange={setDays} style={{ width: 120 }}>
              <Select.Option value={90}>近3个月</Select.Option>
              <Select.Option value={180}>近半年</Select.Option>
              <Select.Option value={365}>近1年</Select.Option>
              <Select.Option value={730}>近2年</Select.Option>
            </Select>
          </Col>
          <Col>
            <span style={{ fontSize: 12, color: '#999' }}>
              * 国际金价历史数据由上海金 + 汇率推导，走势方向一致
            </span>
          </Col>
        </Row>
      </Card>

      {/* Charts for both gold types */}
      {GOLD_TYPES.map((gt) => {
        const indicators = dataMap[gt.key] || [];
        const signals = signalsMap[gt.key];

        return (
          <div key={gt.key} style={{ marginBottom: 24 }}>
            <GoldChart
              goldType={gt.key}
              title={`${gt.label} — 技术分析`}
              data={indicators}
              loading={loading}
              height={420}
            />

            {/* Trend Signals */}
            {signals && signals.status === 'ok' && (
              <Card title="📊 技术信号详情" size="small" style={{ marginTop: 8 }}>
                <Row gutter={[16, 8]}>
                  <Col xs={24} sm={4}>
                    <Statistic
                      title="最新收盘价"
                      value={signals.close}
                      precision={2}
                      prefix={gt.unit}
                      valueStyle={{ fontSize: 20 }}
                    />
                  </Col>
                  <Col xs={24} sm={4}>
                    <Tag
                      color={signals.overall_trend === '偏多' ? 'red' : signals.overall_trend === '偏空' ? 'green' : 'default'}
                      style={{ fontSize: 14, padding: '4px 12px', marginTop: 8 }}
                    >
                      综合: {signals.overall_trend}
                    </Tag>
                  </Col>
                  {signals.signals.map((s, i) => (
                    <Col xs={12} sm={3} key={i}>
                      <Card size="small" style={{ background: '#fafafa' }}>
                        <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 12 }}>{s.indicator}</div>
                        <Tag color={signalColor(s.signal)}>{s.signal}</Tag>
                        <div style={{ fontSize: 11, color: '#666', marginTop: 4 }}>{s.desc}</div>
                      </Card>
                    </Col>
                  ))}
                </Row>
              </Card>
            )}
          </div>
        );
      })}

      {/* Data summary */}
      <div style={{ marginTop: 8, textAlign: 'center', fontSize: 12, color: '#999' }}>
        点击图表上方按钮切换 K线/均线 | MACD | RSI 视图
      </div>
    </div>
  );
}
