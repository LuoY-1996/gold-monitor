import { useEffect, useState, useCallback, useRef } from 'react';
import { Row, Col, Card, Select, Statistic, Tag, Empty, Spin } from 'antd';
import { fetchFactorHistory } from '../api/factors';
import { getGeoRisks, fetchGeoEvents, type GeoEvent } from '../api/geopolitics';
import { getCentralBankPurchases, getYearlyTotals } from '../api/centralBank';

const FACTOR_CONFIG: Record<string, { label: string; unit: string; color: string; note: string }> = {
  oil: { label: '布伦特原油', unit: '$/桶', color: '#d48806', note: '油价→通胀→美联储→金价' },
  usd_cny: { label: '美元/人民币 (DXY 代理)', unit: '', color: '#1677ff', note: '与美元指数高度相关(~0.8)' },
  treasury_10y: { label: '美债10Years收益率', unit: '%', color: '#fa8c16', note: '实际利率核心指标' },
  vix: { label: 'VIX 恐慌指数', unit: '', color: '#722ed1', note: '市场避险情绪' },
};

const FACTOR_ORDER = ['oil', 'usd_cny', 'treasury_10y', 'vix'] as const;

interface FactorPoint { trade_date: string; value: number; }

/** SVG line chart for a factor's historical data — fills container width */
function FactorLineChart({ data, color, unit = '', height = 140 }: { data: FactorPoint[]; color: string; unit?: string; height?: number }) {
  if (data.length < 2) return <div style={{ height, background: '#fafafa', borderRadius: 6 }} />;
  const padL = 50, padR = 15, padT = 14, padB = 30;

  return (
    <svg viewBox={`0 0 800 ${height}`} preserveAspectRatio="xMidYMid meet"
      style={{ display: 'block', width: '100%', height }}>
      {(() => {
        const vals = data.map(d => d.value);
        const minVal = Math.min(...vals), maxVal = Math.max(...vals);
        const range = maxVal - minVal || 1;
        const chartW = 800 - padL - padR, chartH = height - padT - padB;
        const points = vals.map((v, i) => {
          const x = padL + (i / (vals.length - 1)) * chartW;
          const y = padT + chartH * (1 - (v - minVal) / range);
          return `${x},${y}`;
        }).join(' ');
        const fillPath = `${padL},${padT + chartH} ${points} 785,${padT + chartH}`;
        // X-axis labels: pick ~5 evenly spaced dates
        const xLabels: { label: string; x: number }[] = [];
        const step = Math.max(1, Math.floor((data.length - 1) / 5));
        for (let i = 0; i < data.length; i += step) {
          xLabels.push({ label: data[i].trade_date.slice(5), x: padL + (i / (data.length - 1)) * chartW });
        }
        return (
          <>
            <polygon points={fillPath} fill={color} opacity={0.08} />
            <polyline points={points} fill="none" stroke={color} strokeWidth={1.5} />
            {/* Y-axis labels */}
            <text x={padL - 4} y={padT + 4} fontSize={10} fill="#999" textAnchor="end">
              {unit}{maxVal.toFixed(2)}
            </text>
            <text x={padL - 4} y={padT + chartH} fontSize={10} fill="#999" textAnchor="end">
              {unit}{minVal.toFixed(2)}
            </text>
            {/* X-axis labels */}
            {xLabels.map((xl, i) => (
              <text key={i} x={xl.x} y={height - 6} fontSize={9} fill="#999" textAnchor="middle">{xl.label}</text>
            ))}
          </>
        );
      })()}
    </svg>
  );
}

function QuarterChart() {
  const purchases = getCentralBankPurchases().slice(-12);
  const values = purchases.map(q => q.total);
  const labels = purchases.map(q => q.quarter.slice(2));
  const maxVal = Math.max(...values), minVal = Math.min(...values), range = maxVal - minVal || 1;
  const W = 800, H = 150, padL = 40, padR = 15, padT = 20, padB = 24;
  const chartW = W - padL - padR, chartH = H - padT - padB;
  const points = values.map((v, i) => {
    const x = padL + (i / (values.length - 1)) * chartW;
    const y = padT + chartH * (1 - (v - minVal) / range);
    return `${x},${y}`;
  }).join(' ');
  const fillPath = `${padL},${padT + chartH} ${points} ${padL + chartW},${padT + chartH}`;
  const yLabels = [Math.round(minVal), Math.round(minVal + range / 2), Math.round(maxVal)];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet"
      style={{ display: 'block', width: '100%', height: H }}>
      {yLabels.map((v, i) => {
        const y = padT + chartH * (1 - (v - minVal) / range);
        return (
          <g key={i}>
            <line x1={padL} y1={y} x2={padL + chartW} y2={y} stroke="#f0f0f0" strokeWidth={0.5} />
            <text x={padL - 2} y={y + 4} fontSize={10} fill="#999" textAnchor="end">{v}</text>
          </g>
        );
      })}
      <polygon points={fillPath} fill="rgba(22,119,255,0.1)" />
      <polyline points={points} fill="none" stroke="#1677ff" strokeWidth={2} />
      {values.map((v, i) => {
        const x = padL + (i / (values.length - 1)) * chartW;
        const y = padT + chartH * (1 - (v - minVal) / range);
        return (
          <g key={i}>
            <circle cx={x} cy={y} r={3.5} fill="#1677ff" />
            <text x={x} y={H - 6} fontSize={9} fill="#999" textAnchor="middle">{labels[i]}</text>
            {i % 2 === 0 && (
              <text x={x} y={y - 8} fontSize={10} fill="#333" textAnchor="middle" fontWeight={500}>{v.toFixed(0)}</text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

function YearChart() {
  const data = getYearlyTotals();
  const values = data.map(y => y.total), labels = data.map(y => y.year);
  const maxVal = Math.max(...values), minVal = 0, range = maxVal - minVal || 1;
  const W = 800, H = 150, padL = 40, padR = 15, padT = 20, padB = 24;
  const chartW = W - padL - padR, chartH = H - padT - padB;
  const points = values.map((v, i) => {
    const x = padL + (i / (values.length - 1)) * chartW;
    const y = padT + chartH * (1 - (v - minVal) / range);
    return `${x},${y}`;
  }).join(' ');
  const fillPath = `${padL},${padT + chartH} ${points} ${padL + chartW},${padT + chartH}`;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet"
      style={{ display: 'block', width: '100%', height: H }}>
      <line x1={padL} y1={padT + chartH} x2={padL + chartW} y2={padT + chartH} stroke="#f0f0f0" strokeWidth={0.5} />
      <polygon points={fillPath} fill="rgba(250,140,22,0.1)" />
      <polyline points={points} fill="none" stroke="#fa8c16" strokeWidth={2} />
      {values.map((v, i) => {
        const x = padL + (i / (values.length - 1)) * chartW;
        const y = padT + chartH * (1 - (v - minVal) / range);
        return (
          <g key={i}>
            <circle cx={x} cy={y} r={4} fill="#fa8c16" />
            <text x={x} y={H - 6} fontSize={10} fill="#999" textAnchor="middle">{labels[i]}</text>
            <text x={x} y={y - 8} fontSize={10} fill="#333" textAnchor="middle" fontWeight={600}>{v.toFixed(0)}</text>
          </g>
        );
      })}
    </svg>
  );
}

export default function FactorAnalysis() {
  const [goldType, setGoldType] = useState('au9999');
  const [factorData, setFactorData] = useState<Record<string, { value: number; date: string }>>({});
  const [loading, setLoading] = useState(false);
  const [timelineRange, setTimelineRange] = useState<'3m' | '6m' | '1y'>('3m');
  const [geoEvents, setGeoEvents] = useState<GeoEvent[]>([]);
  const [factorHistory, setFactorHistory] = useState<Record<string, FactorPoint[]>>({});

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // Load factor latest values + history
      const latest: Record<string, any> = {};
      const hist: Record<string, FactorPoint[]> = {};
      for (const factor of ['oil', 'vix', 'usd_cny', 'treasury_10y'] as const) {
        try {
          const r = await fetchFactorHistory(factor, { limit: 365 });
          if (r.data.length > 0) {
            const last = r.data[r.data.length - 1];
            latest[factor] = { value: last.value, date: last.trade_date };
            hist[factor] = r.data.map((d: any) => ({ trade_date: d.trade_date, value: d.value }));
          }
        } catch { /* factor not available yet */ }
      }
      setFactorData(latest);
      setFactorHistory(hist);

      // Load geopolitical events
      const months = timelineRange === '3m' ? 3 : timelineRange === '6m' ? 6 : 12;
      try {
        const events = await fetchGeoEvents(months);
        setGeoEvents(events);
      } catch { /* keep existing events */ }
    } catch {
      console.error('Failed to load factor data');
    } finally {
      setLoading(false);
    }
  }, [goldType, timelineRange]);

  useEffect(() => { loadData(); }, [loadData]);

  const events = geoEvents;

  if (loading) {
    return (
      <div>
        <h1 style={{ marginBottom: 24, fontSize: 24, fontWeight: 600 }}>📊 影响因素分析</h1>
        <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>
      </div>
    );
  }

  return (
    <div>
      <h1 style={{ marginBottom: 24, fontSize: 24, fontWeight: 600 }}>
        📊 影响因素分析
      </h1>

      <Row gutter={[24, 24]}>
        {/* Left Column — Key Events Timeline */}
        <Col xs={24} lg={8}>
          <Card title="📅 金价关键事件时间线" size="small"
            extra={
              <Select value={timelineRange} onChange={setTimelineRange} size="small" style={{ width: 100 }}>
                <Select.Option value="3m">近3个月</Select.Option>
                <Select.Option value="6m">近6个月</Select.Option>
                <Select.Option value="1y">近1年</Select.Option>
              </Select>
            }>
            <div style={{ marginBottom: 12, padding: '8px 12px', background: '#fafafa', borderRadius: 6, fontSize: 11 }}>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 6 }}>
                <span style={{ color: '#999' }}>金价方向：</span>
                <Tag color="red" style={{ fontSize: 10, margin: 0 }}>↑ 利多</Tag>
                <Tag color="green" style={{ fontSize: 10, margin: 0 }}>↓ 利空</Tag>
                <Tag style={{ fontSize: 10, margin: 0 }}>→ 中性</Tag>
              </div>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <span style={{ color: '#999' }}>事件类别：</span>
                <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#1677ff' }} /> 美联储
                <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#cf1322' }} /> 地缘
                <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#fa8c16' }} /> 经济
                <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#722ed1' }} /> 中国
                <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#333' }} /> 市场
              </div>
            </div>
            <div style={{ position: 'relative', paddingLeft: 8 }}>
              {events.map((event, i) => (
                <div key={i} style={{
                  position: 'relative',
                  paddingBottom: i < events.length - 1 ? 20 : 0,
                  paddingLeft: 20,
                  borderLeft: i < events.length - 1 ? '2px solid #e8e8e8' : 'none',
                }}>
                  <div style={{
                    position: 'absolute',
                    left: -6,
                    top: 4,
                    width: 12,
                    height: 12,
                    borderRadius: '50%',
                    background:
                      event.category === 'fed' ? '#1677ff' :
                      event.category === 'geopolitics' ? '#cf1322' :
                      event.category === 'economy' ? '#fa8c16' :
                      event.category === 'china' ? '#722ed1' : '#333',
                  }} />
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                    <Tag style={{ fontSize: 10 }} color={
                      event.category === 'fed' ? 'blue' :
                      event.category === 'geopolitics' ? 'red' :
                      event.category === 'economy' ? 'orange' :
                      event.category === 'china' ? 'purple' : 'default'
                    }>
                      {{fed:'美联储',geopolitics:'地缘',economy:'经济',china:'中国',market:'市场'}[event.category] || event.category}
                    </Tag>
                    <span style={{ fontSize: 11, color: '#999' }}>{event.date}</span>
                  </div>
                  <div style={{ fontWeight: 600, fontSize: 14, marginTop: 2 }}>
                    {event.title}
                    <Tag
                      color={event.direction > 0 ? 'red' : event.direction < 0 ? 'green' : 'default'}
                      style={{ marginLeft: 6, fontSize: 10 }}
                    >
                      金价{event.direction > 0 ? '↑' : event.direction < 0 ? '↓' : '→'}
                    </Tag>
                  </div>
                  <div style={{ fontSize: 13, color: '#666' }}>{event.description}</div>
                </div>
              ))}
            </div>
          </Card>
        </Col>

        {/* Right Column — Factors + Geo Risks */}
        <Col xs={24} lg={16}>
          {/* Factor Analysis: 2 per row */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>📈 宏观因素分析</div>
            <Row gutter={[16, 16]}>
              {FACTOR_ORDER.map(key => {
                const val = factorData[key];
                const hist = factorHistory[key];
                const cfg = FACTOR_CONFIG[key];
                const desc: Record<string, { up: string; down: string }> = {
                  oil: { up: '金价 ↑', down: '油价涨→通胀预期↑→利好黄金；但高油价若持续，可能迫使美联储加息' },
                  usd_cny: { up: '国内金价 ↑', down: '人民币贬值→国内黄金自然上涨，与 DXY 高度相关(~0.8)' },
                  treasury_10y: { up: '金价 ↓', down: '利率↑→持有黄金机会成本↑，利空黄金。反之利率↓则利多' },
                  vix: { up: '金价 ↑', down: '恐慌↑→避险资金涌入黄金。VIX 飙升往往伴随金价跳涨' },
                };
                return (
                  <Col xs={24} sm={12} key={key}>
                    <Card size="small">
                      <Row gutter={[16, 8]} align="middle" style={{ marginBottom: 10 }}>
                        <Col span={24}>
                          {val ? (
                            <Statistic title={cfg.label} value={val.value}
                              precision={key === 'usd_cny' ? 4 : 2} suffix={cfg.unit}
                              valueStyle={{ color: cfg.color, fontSize: 22 }} />
                          ) : (
                            <div style={{ color: '#999', fontSize: 12 }}>暂无数据</div>
                          )}
                        </Col>
                      </Row>
                      <div style={{ fontSize: 12, lineHeight: 1.6, color: '#666', marginBottom: 10 }}>
                        <span style={{ color: '#cf1322' }}>↑</span> {desc[key].up}<br/>
                        <span style={{ color: '#999' }}>{desc[key].down}</span>
                      </div>
                      {hist && hist.length >= 2 ? (
                        <FactorLineChart data={hist} color={cfg.color} unit={cfg.unit} height={110} />
                      ) : (
                        <div style={{ height: 60, background: '#fafafa', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ccc', fontSize: 12 }}>
                          走势数据积累中...
                        </div>
                      )}
                    </Card>
                  </Col>
                );
              })}
            </Row>
          </div>

          {/* Central Bank Purchases */}
          <Card title="🏦 全球央行购金量" size="small" style={{ marginBottom: 16 }}>
            <Row gutter={[24, 16]}>
              <Col xs={24} sm={12}>
                <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>各季度净购入量（吨）</div>
                <QuarterChart />
              </Col>
              <Col xs={24} sm={12}>
                <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>年度总购金量趋势</div>
                <YearChart />
              </Col>
            </Row>
            <div style={{ fontSize: 11, color: '#999', marginTop: 12 }}>
              💡 央行购金是金价长期上涨最重要的结构性支撑。2022年后全球央行年购金量突破1000吨，是2020年前的两倍以上。
            </div>
          </Card>

          {/* Geopolitics Risk Cards */}
          <Card title="🌍 地缘政治风险" size="small">
            <Row gutter={[16, 16]}>
              {getGeoRisks().map((risk) => (
                <Col xs={24} sm={8} key={risk.region}>
                  <Card size="small" style={{ background: '#fafafa' }}>
                    <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 8 }}>
                      {risk.label}
                    </div>
                    <Tag color={risk.riskLevel === 'high' ? 'red' : risk.riskLevel === 'medium' ? 'orange' : 'default'}>
                      风险等级: {risk.riskLevel === 'high' ? '⚠️ 高' : risk.riskLevel === 'medium' ? '⚡ 中' : '低'}
                    </Tag>
                    <div style={{ fontSize: 12, color: '#666', marginTop: 8 }}>
                      状态: {risk.status}
                    </div>
                    <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                      最新: {risk.latestEvent}
                    </div>
                    <div style={{ fontSize: 12, color: '#cf1322', marginTop: 4, fontWeight: 500 }}>
                      → {risk.goldImpact}
                    </div>
                  </Card>
                </Col>
              ))}
            </Row>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
