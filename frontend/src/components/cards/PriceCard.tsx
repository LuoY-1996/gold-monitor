import { Card, Statistic, Spin } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import type { GoldRealtime } from '../../types/gold';
import { GOLD_LABELS, GOLD_UNITS } from '../../utils/constants';
import { formatUSD, formatCNY } from '../../utils/format';

interface Props {
  goldType: string;
  realtime: GoldRealtime | null;
  loading: boolean;
}

export default function PriceCard({ goldType, realtime, loading }: Props) {
  const isXau = goldType === 'xau_usd';
  const formatPrice = isXau ? formatUSD : formatCNY;

  if (loading) {
    return (
      <Card title={GOLD_LABELS[goldType] || goldType}>
        <Spin size="default" />
      </Card>
    );
  }

  if (!realtime || !realtime.available || realtime.close == null) {
    return (
      <Card title={GOLD_LABELS[goldType] || goldType}>
        <div style={{ color: '#999' }}>暂无数据，请先获取金价</div>
      </Card>
    );
  }

  const prevClose = realtime.open ?? realtime.close;
  const change = realtime.close - prevClose;
  const changePercent = prevClose ? ((change / prevClose) * 100).toFixed(2) : '0.00';
  const isUp = change >= 0;

  return (
    <Card
      title={
        <span style={{ fontSize: 16, fontWeight: 500 }}>
          🪙 {GOLD_LABELS[goldType] || goldType}
        </span>
      }
      style={{ minWidth: 280 }}
    >
      <Statistic
        value={realtime.close}
        precision={2}
        prefix={isXau ? '$' : '¥'}
        valueStyle={{
          color: isUp ? '#cf1322' : '#3f8600',
          fontSize: 32,
          fontWeight: 700,
        }}
        suffix={
          <span style={{ fontSize: 14, color: '#888' }}>
            {GOLD_UNITS[goldType]}
          </span>
        }
      />
      <div style={{ marginTop: 8, display: 'flex', gap: 16, fontSize: 13, color: '#666' }}>
        <span>
          涨跌:{' '}
          <span style={{ color: isUp ? '#cf1322' : '#3f8600', fontWeight: 600 }}>
            {isUp ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
            {isXau ? formatUSD(Math.abs(change)) : formatCNY(Math.abs(change))}
            ({isUp ? '+' : ''}{changePercent}%)
          </span>
        </span>
        {realtime.high && (
          <span>
            最高: {formatPrice(realtime.high)}
          </span>
        )}
        {realtime.low && (
          <span>
            最低: {formatPrice(realtime.low)}
          </span>
        )}
      </div>
      <div style={{ marginTop: 4, fontSize: 11, color: '#aaa' }}>
        更新时间: {realtime.trade_date}
      </div>
    </Card>
  );
}
