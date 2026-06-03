import { useEffect, useRef } from 'react';
import { createChart, type IChartApi, type ISeriesApi, type LineData } from 'lightweight-charts';
import type { GoldPricePoint } from '../../types/gold';
import { GOLD_LABELS } from '../../utils/constants';

interface Props {
  goldType: string;
  history: GoldPricePoint[];
  loading: boolean;
  height?: number;
}

export default function PriceLineChart({ goldType, history, loading, height = 400 }: Props) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const lineSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current || history.length === 0) return;

    // Clean up previous chart
    if (chartRef.current) {
      chartRef.current.remove();
    }

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      height,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333',
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      rightPriceScale: {
        borderColor: '#d9d9d9',
        scaleMargins: {
          top: 0.1,
          bottom: 0.1,
        },
      },
      timeScale: {
        borderColor: '#d9d9d9',
        timeVisible: false,
        fixLeftEdge: true,
      },
      crosshair: {
        mode: 0,
      },
    });

    // Add line series
    const lineSeries = chart.addLineSeries({
      color: '#1677ff',
      lineWidth: 2,
      priceFormat: {
        type: 'price',
        precision: 2,
        minMove: 0.01,
      },
    });

    // Convert data to chart format
    const chartData: LineData[] = history
      .filter((p) => p.close > 0)
      .map((p) => ({
        time: p.trade_date as any, // lightweight-charts accepts date string
        value: p.close,
      }));

    lineSeries.setData(chartData);
    chart.timeScale().fitContent();

    chartRef.current = chart;
    lineSeriesRef.current = lineSeries;

    // Cleanup on unmount
    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, [history, height]);

  if (loading) {
    return (
      <div
        style={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#fafafa',
          borderRadius: 8,
        }}
      >
        加载中...
      </div>
    );
  }

  if (history.length === 0) {
    return (
      <div
        style={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#fafafa',
          borderRadius: 8,
          color: '#999',
        }}
      >
        暂无历史数据，请先获取金价数据
      </div>
    );
  }

  return (
    <div>
      <h3 style={{ marginBottom: 12, fontWeight: 500 }}>
        📈 {GOLD_LABELS[goldType] || goldType} — 历史走势
      </h3>
      <div ref={chartContainerRef} style={{ borderRadius: 8, overflow: 'hidden' }} />
    </div>
  );
}
