import { useMemo } from 'react';
import { Spin, Empty } from 'antd';
import type { IndicatorDataPoint } from '../../api/indicators';
import type { PredictionResult } from '../../types/prediction';

interface Props {
  goldType: string;
  label: string;
  unit: string;
  formatPrice: (v: number) => string;
  historicalData: IndicatorDataPoint[];
  prediction: PredictionResult | null;
  loading: boolean;
  height?: number;
}

const W = 800, H = 420, padL = 70, padR = 20, padT = 30, padB = 40;
const chartW = W - padL - padR, chartH = H - padT - padB;

export default function PredictionChart({
  formatPrice,
  historicalData, prediction, loading, height = 420,
}: Props) {
  const parts = useMemo(() => {
    if (historicalData.length < 2) return null;
    const closes = historicalData.map(d => d.close).filter(v => v != null && isFinite(v));
    if (closes.length < 2) return null;

    const allVals = [...closes];
    if (prediction?.predicted_price_7d && isFinite(prediction.predicted_price_7d)) allVals.push(prediction.predicted_price_7d);
    if (prediction?.confidence_low && isFinite(prediction.confidence_low)) allVals.push(prediction.confidence_low);
    if (prediction?.confidence_high && isFinite(prediction.confidence_high)) allVals.push(prediction.confidence_high);
    const yMin = Math.min(...allVals) * 0.995;
    const yMax = Math.max(...allVals) * 1.005;
    const yRange = yMax - yMin || 1;

    const toX = (i: number) => padL + (i / (historicalData.length - 1)) * chartW;
    const toY = (v: number) => padT + chartH * (1 - (v - yMin) / yRange);
    const linePoints = closes.map((v, i) => `${toX(i)},${toY(v)}`).join(' ');
    const fillPath = `${padL},${padT + chartH} ${linePoints} ${padL + chartW},${padT + chartH}`;

    const el: React.ReactElement[] = [];
    for (let i = 0; i <= 4; i++) {
      const y = padT + (chartH * i) / 4;
      const val = yMax - (yRange * i) / 4;
      el.push(<line key={`g${i}`} x1={padL} y1={y} x2={padL + chartW} y2={y} stroke="#f0f0f0" strokeWidth={0.5} />);
      el.push(<text key={`yl${i}`} x={padL - 8} y={y + 4} fontSize={10} fill="#999" textAnchor="end">{formatPrice(val)}</text>);
    }
    for (let i = 0; i <= 5; i++) {
      const idx = Math.floor((historicalData.length - 1) * i / 5);
      const x = toX(idx);
      el.push(<text key={`xl${i}`} x={x} y={H - padB + 16} fontSize={10} fill="#999" textAnchor="middle">{historicalData[idx].date?.slice(5) || ''}</text>);
    }

    el.push(<polygon key="fill" points={fillPath} fill="rgba(22,119,255,0.06)" />);
    el.push(<polyline key="line" points={linePoints} fill="none" stroke="#1677ff" strokeWidth={2} />);

    // Prediction
    if (prediction?.predicted_price_7d) {
      const lastX = toX(historicalData.length - 1);
      const lastY = toY(closes[closes.length - 1]);
      const fX = lastX + chartW * 0.08;
      const fY = toY(prediction.predicted_price_7d);

      el.push(<line key="t1" x1={lastX} y1={padT} x2={lastX} y2={padT + chartH} stroke="#d9d9d9" strokeWidth={1} strokeDasharray="4 4" />);
      if (prediction.confidence_low && prediction.confidence_high) {
        const ly = toY(prediction.confidence_low), hy = toY(prediction.confidence_high);
        el.push(<rect key="ci" x={lastX} y={hy} width={fX - lastX} height={ly - hy} fill="rgba(82,196,26,0.12)" stroke="rgba(82,196,26,0.4)" strokeWidth={1} />);
      }
      el.push(<line key="fl" x1={lastX} y1={lastY} x2={fX} y2={fY} stroke="#52c41a" strokeWidth={2.5} strokeDasharray="6 3" />);
      el.push(<circle key="fd" cx={fX} cy={fY} r={5} fill="#52c41a" />);

      const up = prediction.direction === 'up';
      el.push(<text key="la" x={fX + 10} y={fY} fontSize={14} fontWeight="bold" fill={up ? '#cf1322' : '#3f8600'}>{up ? '↑' : '↓'} {prediction.predicted_return_7d_pct}% ({(prediction.direction_probability! * 100).toFixed(0)}%)</text>);
      el.push(<text key="lp" x={fX + 10} y={fY + 18} fontSize={12} fill="#52c41a">{formatPrice(prediction.predicted_price_7d)}</text>);
    }

    el.push(<text key="hl" x={padL + 4} y={padT - 8} fontSize={10} fill="#999">历史</text>);
    if (prediction?.predicted_price_7d) {
      el.push(<text key="fl2" x={padL + chartW - 4} y={padT - 8} fontSize={10} fill="#52c41a" textAnchor="end">预测</text>);
    }
    return el;
  }, [historicalData, prediction, formatPrice]);

  if (loading) return <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Spin /></div>;
  if (historicalData.length < 5) return <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Empty description={`暂无足够历史数据 (${historicalData.length} 条)`} /></div>;
  if (!parts) return <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Spin tip="计算中..." /></div>;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet"
      style={{ width: '100%', height, display: 'block' }}>
      {parts}
    </svg>
  );
}
