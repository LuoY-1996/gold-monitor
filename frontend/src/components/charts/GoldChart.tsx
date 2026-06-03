import { useEffect, useRef, useState } from 'react';
import { Card, Radio, Spin, Empty } from 'antd';
import type { IndicatorDataPoint } from '../../api/indicators';

interface Props {
  goldType: string;
  title: string;
  data: IndicatorDataPoint[];
  loading: boolean;
  height?: number;
}

type ChartView = 'price' | 'macd' | 'rsi';

export default function GoldChart({ goldType, title, data, loading, height = 500 }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [view, setView] = useState<ChartView>('price');

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // HiDPI support
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = height + 'px';
    ctx.scale(dpr, dpr);

    const W = rect.width;
    const H = height;
    ctx.clearRect(0, 0, W, H);

    // Get data range
    const validData = data.filter(d => d.close > 0);
    if (validData.length < 2) return;

    // Chart margins
    const margin = { top: 20, right: 60, bottom: 40, left: 70 };
    const chartW = W - margin.left - margin.right;
    const chartH = H - margin.top - margin.bottom;

    // Draw functions
    const drawLine = (values: (number | null)[], color: string, width = 1, dash: number[] = []) => {
      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.setLineDash(dash);
      let started = false;
      for (let i = 0; i < validData.length; i++) {
        const val = values[i];
        if (val == null) { started = false; continue; }
        const x = margin.left + (i / (validData.length - 1)) * chartW;
        const y = margin.top + chartH * (1 - val);
        if (!started) { ctx.moveTo(x, y); started = true; }
        else { ctx.lineTo(x, y); }
      }
      ctx.stroke();
      ctx.setLineDash([]);
    };

    const getYRange = (series: (number | null)[], padding = 0.1) => {
      const vals = series.filter(v => v != null) as number[];
      if (vals.length === 0) return { min: 0, max: 1 };
      const min = Math.min(...vals);
      const max = Math.max(...vals);
      const range = max - min || 1;
      return { min: min - range * padding, max: max + range * padding };
    };

    const drawGrid = (yMin: number, yMax: number) => {
      ctx.strokeStyle = '#f0f0f0';
      ctx.lineWidth = 0.5;
      const steps = 5;
      for (let i = 0; i <= steps; i++) {
        const y = margin.top + (chartH * i) / steps;
        ctx.beginPath();
        ctx.moveTo(margin.left, y);
        ctx.lineTo(W - margin.right, y);
        ctx.stroke();

        const val = yMax - ((yMax - yMin) * i) / steps;
        ctx.fillStyle = '#999';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(val.toFixed(2), margin.left - 8, y + 4);
      }
    };

    const drawDateLabels = () => {
      ctx.fillStyle = '#999';
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'center';
      const step = Math.max(1, Math.floor(validData.length / 6));
      for (let i = 0; i < validData.length; i += step) {
        const x = margin.left + (i / (validData.length - 1)) * chartW;
        ctx.fillText(validData[i].date?.slice(5) || '', x, H - margin.bottom + 16);
      }
    };

    // --- Price Chart ---
    if (view === 'price') {
      const closes = validData.map(d => d.close);
      const ma5 = validData.map(d => d.ma_5);
      const ma20 = validData.map(d => d.ma_20);
      const ma60 = validData.map(d => d.ma_60);
      const bbUpper = validData.map(d => d.bb_upper);
      const bbLower = validData.map(d => d.bb_lower);

      const allPriceVals = [...closes, ...ma5.filter(v => v), ...ma20.filter(v => v), ...ma60.filter(v => v), ...bbUpper.filter(v => v), ...bbLower.filter(v => v)];
      const yRange = getYRange(allPriceVals as number[]);
      const normalize = (v: number) => (v - yRange.min) / (yRange.max - yRange.min);

      drawGrid(yRange.min, yRange.max);
      drawDateLabels();

      // Bollinger bands
      drawLine(bbUpper.map(v => v != null ? normalize(v) : null), 'rgba(24,144,255,0.5)', 1.5);
      drawLine(bbLower.map(v => v != null ? normalize(v) : null), 'rgba(24,144,255,0.5)', 1.5);

      // Fill between Bollinger
      ctx.fillStyle = 'rgba(24,144,255,0.1)';
      ctx.beginPath();
      let started = false;
      const topPoints: [number, number][] = [];
      const botPoints: [number, number][] = [];
      for (let i = 0; i < validData.length; i++) {
        const x = margin.left + (i / (validData.length - 1)) * chartW;
        if (bbUpper[i] != null) topPoints.push([x, margin.top + chartH * (1 - normalize(bbUpper[i]!))]);
        if (bbLower[i] != null) botPoints.push([x, margin.top + chartH * (1 - normalize(bbLower[i]!))]);
      }
      if (topPoints.length > 0) {
        ctx.moveTo(topPoints[0][0], topPoints[0][1]);
        for (const p of topPoints) ctx.lineTo(p[0], p[1]);
        for (let i = botPoints.length - 1; i >= 0; i--) ctx.lineTo(botPoints[i][0], botPoints[i][1]);
        ctx.closePath();
        ctx.fill();
      }

      // Price line
      drawLine(closes.map(v => normalize(v)), '#1677ff', 2);
      // MAs
      drawLine(ma5.map(v => v != null ? normalize(v) : null), '#ff7a45', 1.5);
      drawLine(ma20.map(v => v != null ? normalize(v) : null), '#9254de', 1.5);
      drawLine(ma60.map(v => v != null ? normalize(v) : null), '#13c2c2', 1);

      // Legend
      const legend = [
        { label: '收盘价', color: '#1677ff' },
        { label: 'MA5', color: '#ff7a45' },
        { label: 'MA20', color: '#9254de' },
        { label: 'MA60', color: '#13c2c2' },
        { label: 'Bollinger', color: 'rgba(24,144,255,0.5)' },
      ];
      ctx.font = '12px sans-serif';
      let lx = margin.left;
      for (const item of legend) {
        ctx.fillStyle = item.color;
        ctx.fillRect(lx, 8, 12, 12);
        ctx.fillStyle = '#333';
        ctx.textAlign = 'left';
        ctx.fillText(item.label, lx + 16, 18);
        lx += ctx.measureText(item.label).width + 28;
      }
    }

    // --- MACD Chart ---
    if (view === 'macd') {
      const macdVals = validData.map(d => d.macd);
      const signalVals = validData.map(d => d.macd_signal);
      const histVals = validData.map(d => d.macd_histogram);
      const allVals = [...macdVals.filter(v => v), ...signalVals.filter(v => v), ...histVals.filter(v => v)];
      const yRange = getYRange(allVals as number[]);
      const normalize = (v: number) => (v - yRange.min) / (yRange.max - yRange.min);

      drawGrid(yRange.min, yRange.max);
      drawDateLabels();

      // Histogram bars
      for (let i = 0; i < validData.length; i++) {
        if (histVals[i] == null) continue;
        const x = margin.left + (i / (validData.length - 1)) * chartW;
        const val = normalize(histVals[i]!);
        const zeroY = margin.top + chartH * (1 - normalize(0));
        const barY = margin.top + chartH * (1 - val);
        ctx.fillStyle = histVals[i]! >= 0 ? 'rgba(207,19,34,0.6)' : 'rgba(63,134,0,0.6)';
        ctx.fillRect(x - 1, Math.min(zeroY, barY), 2, Math.abs(barY - zeroY));
      }

      // Zero line
      const zeroY = margin.top + chartH * (1 - normalize(0));
      ctx.strokeStyle = '#d9d9d9';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(margin.left, zeroY);
      ctx.lineTo(W - margin.right, zeroY);
      ctx.stroke();

      drawLine(macdVals.map(v => v != null ? normalize(v) : null), '#1677ff', 2);
      drawLine(signalVals.map(v => v != null ? normalize(v) : null), '#ff7a45', 1);

      // Legend
      ctx.fillStyle = '#1677ff'; ctx.fillRect(margin.left, 8, 12, 12);
      ctx.fillStyle = '#333'; ctx.textAlign = 'left'; ctx.fillText('MACD', margin.left + 16, 18);
      ctx.fillStyle = '#ff7a45'; ctx.fillRect(margin.left + 80, 8, 12, 12);
      ctx.fillText('Signal', margin.left + 96, 18);
    }

    // --- RSI Chart ---
    if (view === 'rsi') {
      const rsiVals = validData.map(d => d.rsi_14);
      const yRange = { min: 0, max: 100 };

      drawGrid(yRange.min, yRange.max);
      drawDateLabels();

      const normalize = (v: number) => (v - yRange.min) / (yRange.max - yRange.min);

      // Overbought/oversold lines
      [70, 30].forEach(level => {
        const y = margin.top + chartH * (1 - normalize(level));
        ctx.strokeStyle = 'rgba(0,0,0,0.15)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(margin.left, y);
        ctx.lineTo(W - margin.right, y);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = '#999';
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(level.toString(), margin.left - 8, y + 4);
      });

      // RSI fill area (between 30 and 70)
      ctx.fillStyle = 'rgba(22,119,255,0.05)';
      ctx.beginPath();
      ctx.moveTo(margin.left, margin.top + chartH * (1 - normalize(30)));
      ctx.lineTo(W - margin.right, margin.top + chartH * (1 - normalize(30)));
      ctx.lineTo(W - margin.right, margin.top + chartH * (1 - normalize(70)));
      ctx.lineTo(margin.left, margin.top + chartH * (1 - normalize(70)));
      ctx.closePath();
      ctx.fill();

      drawLine(rsiVals.map(v => v != null ? normalize(v) : null), '#722ed1', 2);

      ctx.fillStyle = '#722ed1'; ctx.fillRect(margin.left, 8, 12, 12);
      ctx.fillStyle = '#333'; ctx.textAlign = 'left'; ctx.fillText('RSI(14)', margin.left + 16, 18);
    }

  }, [data, view, height]);

  return (
    <Card
      title={title}
      extra={
        <Radio.Group value={view} onChange={e => setView(e.target.value)} size="small" optionType="button">
          <Radio.Button value="price">K线/均线</Radio.Button>
          <Radio.Button value="macd">MACD</Radio.Button>
          <Radio.Button value="rsi">RSI</Radio.Button>
        </Radio.Group>
      }
    >
      {loading ? (
        <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Spin />
        </div>
      ) : data.length === 0 ? (
        <Empty description="暂无数据" style={{ padding: 40 }} />
      ) : (
        <canvas ref={canvasRef} style={{ width: '100%', height }} />
      )}
    </Card>
  );
}
