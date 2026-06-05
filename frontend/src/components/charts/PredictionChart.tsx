import { useRef, useEffect, useState, useCallback } from 'react';
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

function drawChart(
  canvas: HTMLCanvasElement,
  container: HTMLElement,
  historicalData: IndicatorDataPoint[],
  prediction: PredictionResult | null,
  height: number,
  formatPrice: (v: number) => string,
) {
  const w = container.clientWidth;
  if (w < 10) return false;

  const dpr = window.devicePixelRatio || 1;
  canvas.width = w * dpr;
  canvas.height = height * dpr;
  canvas.style.width = w + 'px';
  canvas.style.height = height + 'px';
  const ctx = canvas.getContext('2d')!;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, height);

  const H = height;
  const pad = { top: 30, right: 20, bottom: 40, left: 70 };
  const chartW = w - pad.left - pad.right;
  const chartH = H - pad.top - pad.bottom;

  const closes = historicalData.map(d => d.close).filter(v => v != null && isFinite(v));
  if (closes.length < 2) return false;

  const allVals: number[] = [...closes];
  if (prediction?.predicted_price_7d && isFinite(prediction.predicted_price_7d)) allVals.push(prediction.predicted_price_7d);
  if (prediction?.confidence_low && isFinite(prediction.confidence_low)) allVals.push(prediction.confidence_low);
  if (prediction?.confidence_high && isFinite(prediction.confidence_high)) allVals.push(prediction.confidence_high);
  const yMin = Math.min(...allVals) * 0.995;
  const yMax = Math.max(...allVals) * 1.005;
  const yRange = yMax - yMin || 1;

  const toX = (i: number) => pad.left + (i / (historicalData.length - 1)) * chartW;
  const toY = (v: number) => pad.top + chartH * (1 - (v - yMin) / yRange);

  // Grid
  ctx.strokeStyle = '#f0f0f0';
  ctx.lineWidth = 0.5;
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + (chartH * i) / 4;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(w - pad.right, y); ctx.stroke();
    const val = yMax - (yRange * i) / 4;
    ctx.fillStyle = '#999'; ctx.font = '10px sans-serif'; ctx.textAlign = 'right';
    ctx.fillText(formatPrice(val), pad.left - 8, y + 4);
  }

  // X-axis dates
  ctx.fillStyle = '#999'; ctx.font = '10px sans-serif'; ctx.textAlign = 'center';
  const xSteps = 5;
  for (let i = 0; i <= xSteps; i++) {
    const idx = Math.floor((historicalData.length - 1) * i / xSteps);
    const x = toX(idx);
    ctx.fillText(historicalData[idx].date?.slice(5) || '', x, H - pad.bottom + 16);
  }

  // Price line
  ctx.strokeStyle = '#1677ff'; ctx.lineWidth = 2;
  ctx.beginPath();
  historicalData.forEach((d, i) => {
    const x = toX(i), y = toY(d.close);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Prediction overlay
  if (prediction && prediction.predicted_price_7d) {
    const lastIdx = historicalData.length - 1;
    const lastX = toX(lastIdx);
    const lastY = toY(closes[closes.length - 1]);
    const forecastX = lastX + chartW * 0.08;
    const forecastY = toY(prediction.predicted_price_7d);

    // Today marker
    ctx.strokeStyle = '#d9d9d9'; ctx.lineWidth = 1; ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(lastX, pad.top); ctx.lineTo(lastX, H - pad.bottom); ctx.stroke();
    ctx.setLineDash([]);

    // Confidence band
    if (prediction.confidence_low && prediction.confidence_high) {
      const lowY = toY(prediction.confidence_low);
      const highY = toY(prediction.confidence_high);
      ctx.fillStyle = 'rgba(82,196,26,0.12)';
      ctx.fillRect(lastX, highY, forecastX - lastX, lowY - highY);
      ctx.strokeStyle = 'rgba(82,196,26,0.4)'; ctx.lineWidth = 1;
      ctx.strokeRect(lastX, highY, forecastX - lastX, lowY - highY);
    }

    // Forecast dashed line
    ctx.strokeStyle = '#52c41a'; ctx.lineWidth = 2.5; ctx.setLineDash([6, 3]);
    ctx.beginPath(); ctx.moveTo(lastX, lastY); ctx.lineTo(forecastX, forecastY); ctx.stroke();
    ctx.setLineDash([]);

    // Forecast dot
    ctx.fillStyle = '#52c41a'; ctx.beginPath();
    ctx.arc(forecastX, forecastY, 5, 0, Math.PI * 2); ctx.fill();

    // Direction arrow
    const isUp = prediction.direction === 'up';
    ctx.fillStyle = isUp ? '#cf1322' : '#3f8600';
    ctx.font = 'bold 14px sans-serif'; ctx.textAlign = 'left';
    const arrowLabel = `${isUp ? '↑' : '↓'} ${prediction.predicted_return_7d_pct}% (${(prediction.direction_probability! * 100).toFixed(0)}%)`;
    ctx.fillText(arrowLabel, forecastX + 10, forecastY);

    // Price label
    ctx.font = '12px sans-serif'; ctx.fillStyle = '#52c41a';
    ctx.fillText(formatPrice(prediction.predicted_price_7d), forecastX + 10, forecastY + 18);
  }

  // Labels
  ctx.fillStyle = '#999'; ctx.font = '10px sans-serif'; ctx.textAlign = 'left';
  ctx.fillText('← 历史', pad.left + 4, pad.top - 8);
  if (prediction?.predicted_price_7d) {
    ctx.fillStyle = '#52c41a'; ctx.textAlign = 'right';
    ctx.fillText('预测 →', w - pad.right - 4, pad.top - 8);
  }
  return true;
}

export default function PredictionChart({
  goldType, label, unit, formatPrice,
  historicalData, prediction, loading, height = 420,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [drawn, setDrawn] = useState(false);

  const doDraw = useCallback(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas || historicalData.length < 5) return false;
    const ok = drawChart(canvas, container, historicalData, prediction, height, formatPrice);
    if (ok) setDrawn(true);
    return ok;
  }, [historicalData, prediction, height, formatPrice]);

  useEffect(() => {
    setDrawn(false);
    const container = containerRef.current;
    if (!container || historicalData.length < 5) return;

    // Try immediate draw
    if (doDraw()) return;

    // Fallback: retry after layout settles
    const timer = setTimeout(() => { doDraw(); }, 100);

    // ResizeObserver: redraw when container resizes
    let observer: ResizeObserver | null = null;
    try {
      observer = new ResizeObserver(() => { doDraw(); });
      observer.observe(container);
    } catch { /* ResizeObserver not supported */ }

    return () => {
      clearTimeout(timer);
      if (observer) observer.disconnect();
    };
  }, [doDraw]);

  if (loading) {
    return (
      <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spin />
      </div>
    );
  }

  if (historicalData.length < 5) {
    return (
      <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Empty description={`暂无足够历史数据 (当前 ${historicalData.length} 条)`} />
      </div>
    );
  }

  return (
    <div ref={containerRef} style={{ width: '100%', position: 'relative' }}>
      <canvas ref={canvasRef} style={{ width: '100%', height, display: 'block' }} />
      {!drawn && <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'absolute', top: 0, left: 0, right: 0 }}><Spin tip="绘制图表中..." /></div>}
    </div>
  );
}
