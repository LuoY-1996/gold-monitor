import { useEffect, useState, useCallback } from 'react';
import { Row, Col, Card, Statistic, Tag, Progress, Alert, Empty, Spin } from 'antd';
import { ThunderboltOutlined } from '@ant-design/icons';
import { fetchIndicators, type IndicatorDataPoint } from '../api/indicators';
import { fetchPrediction, fetchModelInfo, fetchValuation, type ValuationResult } from '../api/prediction';
import type { PredictionResult, ModelInfo } from '../types/prediction';
import { formatUSD } from '../utils/format';
import PredictionChart from '../components/charts/PredictionChart';

const GOLD_TYPE = 'xau-usd';

function generatePredictionAnalysis(p: PredictionResult): string {
  if (!p || p.status !== 'ok') return '';
  const parts: string[] = [];
  const topFeat = p.feature_contributions?.[0]?.feature || '';

  if (p.consensus === 'strong_up' || p.consensus === 'strong_down') {
    parts.push(`模型在 1/3/5/7 日四个时间维度上达成一致${p.consensus === 'strong_up' ? '看涨' : '看跌'}判断，信号可信度较高。`);
  } else if (p.consensus === 'lean_up' || p.consensus === 'lean_down') {
    parts.push(`多维度投票偏向${p.consensus === 'lean_up' ? '看涨' : '看跌'}但未形成一致，信号存在分歧，建议谨慎参考。`);
  } else {
    parts.push('各时间维度方向不一致，短期走势不明朗，不宜单向押注。');
  }

  if (topFeat) {
    const featNames: Record<string, string> = {
      atr_14: '波动率(ATR)', ma_10: '10日均线', ma_20: '20日均线', ma_60: '60日均线', ma_200: '200日均线',
      close: '当前价格', macd: 'MACD', rsi_14: 'RSI', bb_lower: '布林下轨', bb_middle: '布林中轨',
      usd_cny: '美元/人民币', treasury_10y: '美债收益率', vix: 'VIX', oil: '原油', geo_risk: '地缘风险',
      vol_14d: '波动率', close_div_ma_20: '价格偏离度', rsi_change_14d: 'RSI变化',
    };
    const name = featNames[topFeat] || topFeat;
    parts.push(`当前最关键的驱动因素是「${name}」，其次为技术指标和宏观因子综合作用。`);
  }

  parts.push('模型主要学习历史价格形态+利率+汇率+恐慌指数+原油的组合规律。金融时间序列的短期方向预测本质上高度不确定，预测结果仅供参考。');
  return parts.join('');
}

function generateValuationAnalysis(v: ValuationResult): string {
  if (!v || v.status !== 'ok') return '';
  const parts: string[] = [];
  const gap = v.current_gap_pct || 0;
  const pct = v.current_percentile || 50;

  if (gap > (v.valuation_bands?.overvalued_threshold || 30)) {
    parts.push(`当前金价较宏观公允价值溢价 ${gap.toFixed(0)}%，处于历史 ${pct.toFixed(0)} 分位的高估区间。这意味着以利率、美元、VIX、原油等传统因素衡量，金价被显著推高。`);
  } else if (gap < (v.valuation_bands?.undervalued_threshold || -30)) {
    parts.push(`当前金价低于宏观公允价值 ${Math.abs(gap).toFixed(0)}%，处于历史低估区间。传统宏观因素显示金价有回归公允价值的动力。`);
  } else {
    parts.push(`当前金价与宏观公允价值偏离 ${Math.abs(gap).toFixed(0)}%，处于合理波动范围内，宏观因素基本定价。`);
  }

  // Analyze which drivers are pushing up vs down
  const upDrivers = (v.coefficients || []).filter(c => c.coefficient > 0).map(c => {
    const names: Record<string, string> = { treasury_10y: '美债10Y', usd_cny: '美元/人民币', oil: '原油', vix: 'VIX', cb_purchases: '央行购金', geo_risk: '地缘风险' };
    return names[c.feature] || c.feature;
  });
  const downDrivers = (v.coefficients || []).filter(c => c.coefficient < 0).map(c => {
    const names: Record<string, string> = { treasury_10y: '美债10Y', usd_cny: '美元/人民币', oil: '原油', vix: 'VIX', cb_purchases: '央行购金', geo_risk: '地缘风险' };
    return names[c.feature] || c.feature;
  });

  if (upDrivers.length > 0) parts.push(`推高公允价值的因素：${upDrivers.join('、')}。`);
  if (downDrivers.length > 0) parts.push(`压低公允价值的因素：${downDrivers.join('、')}。`);
  parts.push(`模型解释力 R²=${(v.r2 || 0).toFixed(2)}，说明宏观因素能解释金价约 ${((v.r2 || 0) * 100).toFixed(0)}% 的波动，剩余部分来自央行购金、地缘政治、市场情绪等结构性力量。`);
  return parts.join('');
}

export default function PredictionPage() {
  const [prediction, setPrediction] = useState<PredictionResult | null>(null);
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [indicators, setIndicators] = useState<IndicatorDataPoint[]>([]);
  const [valuation, setValuation] = useState<ValuationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // Load indicators for chart (always — even if model doesn't exist yet)
      try {
        const indData = await fetchIndicators(GOLD_TYPE, 30);
        if (indData?.data?.length > 0) {
          setIndicators(indData.data);
        }
      } catch { /* keep existing indicators */ }

      try {
        const pred = await fetchPrediction(GOLD_TYPE);
        setPrediction(pred);
      } catch (e: any) {
        if (e?.response?.status !== 404) {
          setError('预测接口暂时不可用');
        }
      }

      try {
        const info = await fetchModelInfo(GOLD_TYPE);
        setModelInfo(info);
      } catch { /* no model info — OK */ }

    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Load valuation separately (slow — don't block chart)
  useEffect(() => {
    fetchValuation().then(val => {
      if (val?.status === 'ok') setValuation(val);
    }).catch(() => {});
  }, []);

  return (
    <div>
      <h1 style={{ marginBottom: 24, fontSize: 24, fontWeight: 600 }}>
        <ThunderboltOutlined style={{ marginRight: 8, color: '#722ed1' }} />
        AI 金价预测
        <span style={{ fontSize: 13, color: '#999', fontWeight: 400, marginLeft: 12 }}>
          基于 XGBoost 机器学习 · 7日方向+价格预测 · 仅限国际金价 XAU/USD
        </span>
      </h1>

      {/* Model description — top */}
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="模型说明"
        description="预测基于技术指标（MA/MACD/RSI/布林带）+ 宏观因素（美债10Y、USD/CNY、VIX、原油、地缘风险指数）。采用 LightGBM 多时间维度投票，时序分割训练（无未来信息泄露）。短期方向判断相对可靠，价格点位预测存在一定误差，仅供参考。"
      />

      {/* Error alert */}
      {error && <Alert type="error" message={error} closable onClose={() => setError(null)} style={{ marginBottom: 16 }} />}

      {/* Model info bar */}
      {modelInfo?.training_date && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Row gutter={16} align="middle">
            <Col>
              <Tag color="blue">训练日期: {modelInfo.training_date}</Tag>
              <Tag>{modelInfo.train_samples} / {modelInfo.test_samples} 训练/测试样本</Tag>
              {modelInfo.dir_accuracy != null && (
                <Tag color={modelInfo.dir_accuracy > 0.55 ? 'green' : 'orange'}>
                  方向准确率: {(modelInfo.dir_accuracy * 100).toFixed(1)}%
                </Tag>
              )}
              {modelInfo.feature_count != null && (
                <Tag>{modelInfo.feature_count} 个特征</Tag>
              )}
            </Col>
          </Row>
        </Card>
      )}

      {/* ════════ AI 短期预测 + 宏观估值 — 左右排列 ════════ */}
      <Row gutter={[24, 24]}>
        <Col xs={24} lg={13}>
      <Card
        title="🤖 AI 短期预测"
        style={{ marginBottom: 0, height: '100%' }}
        extra={prediction?.status === 'ok' && (
          <Tag color={prediction.consensus?.includes('up') ? 'red' : prediction.consensus?.includes('down') ? 'green' : 'orange'}>
            {prediction.consensus_label}
          </Tag>
        )}
      >
        {!prediction && !loading ? (
          <Empty description="预测数据加载中..." />
        ) : prediction?.status === 'no_model' ? (
          <Empty description={prediction.message || '模型尚未训练，请联系管理员'} />
        ) : prediction?.status === 'ok' ? (
          <Row gutter={[24, 16]}>
            {/* Left: Chart */}
            <Col xs={24} lg={13}>
              <PredictionChart
                goldType={GOLD_TYPE}
                label="XAU/USD"
                unit="$/oz"
                formatPrice={formatUSD}
                historicalData={indicators}
                prediction={prediction}
                loading={loading}
              />
            </Col>

            {/* Right: Signal + Targets + Features */}
            <Col xs={24} lg={5}>
              {/* AI 综合信号 */}
              <div style={{
                background: prediction.consensus?.includes('up') ? '#fff2f0' :
                            prediction.consensus?.includes('down') ? '#f6ffed' : '#fffbe6',
                borderRadius: 8, padding: 16, marginBottom: 16, textAlign: 'center'
              }}>
                <div style={{ fontSize: 13, color: '#999', marginBottom: 4 }}>AI 综合信号</div>
                <div style={{
                  fontSize: 28, fontWeight: 700,
                  color: prediction.consensus?.includes('up') ? '#cf1322' :
                         prediction.consensus?.includes('down') ? '#3f8600' : '#fa8c16',
                }}>
                  {prediction.consensus === 'strong_up' ? '强烈看涨 ↑↑' :
                   prediction.consensus === 'strong_down' ? '强烈看跌 ↓↓' :
                   prediction.consensus === 'lean_up' ? '偏多 ↑' :
                   prediction.consensus === 'lean_down' ? '偏空 ↓' : '信号分歧'}
                </div>
                <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>
                  {prediction.votes_up}/{prediction.total_horizons} 维度看涨
                </div>
              </div>

              {/* 7日目标 */}
              <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
                <Col span={12}>
                  <Card size="small" style={{ textAlign: 'center', background: '#fafafa' }}>
                    <Statistic title="当前价格" value={prediction.current_close || 0}
                      precision={0} prefix="$" valueStyle={{ fontSize: 20 }} />
                  </Card>
                </Col>
                <Col span={12}>
                  <Card size="small" style={{ textAlign: 'center', background: '#f6ffed' }}>
                    <Statistic title="7日目标价" value={prediction.predicted_price_7d || 0}
                      precision={0} prefix="$" valueStyle={{ fontSize: 20, color: '#52c41a' }} />
                  </Card>
                </Col>
              </Row>

              {/* 收益率 + 置信区间 */}
              <Card size="small" style={{ marginBottom: 16 }}>
                <Row gutter={[12, 8]}>
                  <Col span={12}>
                    <Statistic title="预期收益率" value={prediction.predicted_return_7d_pct || 0}
                      precision={2} suffix="%"
                      valueStyle={{ fontSize: 18, color: (prediction.predicted_return_7d_pct || 0) >= 0 ? '#cf1322' : '#3f8600' }} />
                  </Col>
                  <Col span={12}>
                    <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>置信区间</div>
                    <div style={{ fontSize: 14, color: '#666' }}>
                      {formatUSD(prediction.confidence_low || 0)}<br/>~ {formatUSD(prediction.confidence_high || 0)}
                    </div>
                  </Col>
                </Row>
              </Card>

              {/* 各周期预测 */}
              <Card title="⏱ 多周期方向" size="small" style={{ marginBottom: 16 }}>
                {['1','3','5','7'].map(h => {
                  const hp = prediction.horizon_predictions?.[h];
                  if (!hp) return null;
                  const isUp = hp.direction === 'up';
                  return (
                    <div key={h} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <span style={{ fontSize: 12, fontWeight: 500, width: 24 }}>{h}日</span>
                      <Tag color={isUp ? 'red' : 'green'} style={{ fontSize: 10, margin: 0 }}>
                        {isUp ? '↑ 涨' : '↓ 跌'}
                      </Tag>
                      <Progress percent={Math.round(hp.probability * 100)} size="small"
                        strokeColor={isUp ? '#cf1322' : '#3f8600'}
                        style={{ flex: 1, margin: 0 }} />
                      <span style={{ fontSize: 11, color: '#999', width: 30, textAlign: 'right' }}>
                        {(hp.probability * 100).toFixed(0)}%
                      </span>
                    </div>
                  );
                })}
              </Card>

              {/* 关键驱动因素 */}
              {prediction.feature_contributions.length > 0 && (
                <Card title="🔑 关键驱动" size="small">
                  {prediction.feature_contributions.slice(0, 5).map((f, i) => (
                    <div key={i} style={{ marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: 11, width: 130, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#666' }}>{f.feature}</span>
                      <Progress percent={Math.round(f.importance * 100)} size="small"
                        strokeColor="#722ed1" style={{ flex: 1, margin: 0 }} />
                    </div>
                  ))}
                </Card>
              )}
            </Col>
            {/* Analysis Column */}
            {generatePredictionAnalysis(prediction) && (
              <Col xs={24} lg={6} style={{ display: 'flex' }}>
                <div style={{ padding: '16px', background: '#fffbe6', borderRadius: 8, border: '1px solid #ffe58f', fontSize: 14, color: '#555', lineHeight: 2 }}>
                  <div style={{ fontWeight: 600, marginBottom: 8, color: '#333', fontSize: 15 }}>📝 预测分析</div>
                  {generatePredictionAnalysis(prediction)}
                </div>
              </Col>
            )}
          </Row>
        ) : loading ? (
          <div style={{ textAlign: 'center', padding: 60 }}><Spin /></div>
        ) : null}
      </Card>
        </Col>

        {/* ════════ 宏观估值模块 ════════ */}
        <Col xs={24} lg={11}>
        {valuation && valuation.status === 'ok' && (
          <Card title="🏦 宏观估值分析" style={{ height: '100%' }}>
          <Row gutter={[24, 16]}>
            {/* Left: Stats */}
            <Col xs={24} md={16}>
              <Row gutter={[24, 16]}>
                <Col xs={12} md={8}>
                  <Statistic title="当前金价" value={valuation.current_actual || 0}
                    precision={0} prefix="$" valueStyle={{ fontSize: 28, fontWeight: 700 }} />
                </Col>
                <Col xs={12} md={8}>
                  <Statistic title="宏观公允价值" value={valuation.current_fair_value || 0}
                    precision={0} prefix="$" valueStyle={{ fontSize: 22, color: '#1677ff' }} />
                </Col>
                <Col xs={12} md={8}>
                  <Statistic title="估值偏离" value={valuation.current_gap_pct || 0}
                    precision={1} suffix="%"
                    valueStyle={{
                      fontSize: 28, fontWeight: 700,
                      color: (valuation.current_gap_pct || 0) > (valuation.valuation_bands?.overvalued_threshold || 0)
                        ? '#cf1322' : (valuation.current_gap_pct || 0) < (valuation.valuation_bands?.undervalued_threshold || 0)
                        ? '#3f8600' : '#fa8c16',
                    }} />
                  <div style={{ fontSize: 12, color: '#999' }}>
                    百分位: {valuation.current_percentile}%
                    {(valuation.current_gap_pct || 0) > (valuation.valuation_bands?.overvalued_threshold || 20) ? ' 高估' :
                     (valuation.current_gap_pct || 0) < (valuation.valuation_bands?.undervalued_threshold || -20) ? ' 低估' : ' 合理'}
                  </div>
                </Col>
              </Row>
              <Row style={{ marginTop: 12 }}>
                <Col span={24}>
                  <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>估值驱动因素</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {valuation.coefficients?.map((c) => (
                      <Tag key={c.feature} color={c.coefficient > 0 ? 'red' : 'green'}>
                        {{treasury_10y:'美债10Y', usd_cny:'美元/人民币', oil:'原油', vix:'VIX', cb_purchases:'央行购金', geo_risk:'地缘风险'}[c.feature] || c.feature}
                        : {c.coefficient > 0 ? '↑' : '↓'}{Math.abs(c.coefficient).toFixed(0)}
                      </Tag>
                    ))}
                    <Tag>R²={(valuation.r2 || 0).toFixed(2)}</Tag>
                  </div>
                </Col>
              </Row>
            </Col>
            {/* Right: Analysis */}
            {generateValuationAnalysis(valuation) && (
              <Col xs={24} md={8}>
                <div style={{ padding: '16px', background: '#e6f7ff', borderRadius: 8, border: '1px solid #91d5ff', fontSize: 14, color: '#555', lineHeight: 2 }}>
                  <div style={{ fontWeight: 600, marginBottom: 8, color: '#333', fontSize: 15 }}>📝 估值分析</div>
                  {generateValuationAnalysis(valuation)}
                </div>
              </Col>
            )}
          </Row>
        </Card>
        )}
        </Col>
      </Row>

    </div>
  );
}
