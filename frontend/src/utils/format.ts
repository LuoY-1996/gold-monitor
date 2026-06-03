import dayjs from 'dayjs';

/** Format a number as currency (USD) */
export function formatUSD(value: number): string {
  return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** Format a number as CNY */
export function formatCNY(value: number): string {
  return `¥${value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** Format a price change as percentage with color indicator */
export function formatChange(current: number, previous: number): { text: string; isPositive: boolean; isZero: boolean } {
  if (previous === 0) return { text: '0.00%', isPositive: true, isZero: true };
  const change = ((current - previous) / previous) * 100;
  return {
    text: `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`,
    isPositive: change >= 0,
    isZero: change === 0,
  };
}

/** Format a date string for display */
export function formatDate(dateStr: string): string {
  return dayjs(dateStr).format('YYYY-MM-DD');
}

/** Format a date string as relative (e.g. "2小时前") */
export function formatRelativeTime(dateStr: string): string {
  // Simple implementation using dayjs
  const now = dayjs();
  const date = dayjs(dateStr);
  const hours = now.diff(date, 'hour');
  if (hours < 1) return '刚刚';
  if (hours < 24) return `${hours}小时前`;
  return `${now.diff(date, 'day')}天前`;
}
