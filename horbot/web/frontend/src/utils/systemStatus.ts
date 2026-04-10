import { formatBytes as formatBytesBase } from './format';

export const formatUptime = (seconds: number): string => {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  const parts: string[] = [];
  if (days > 0) {
    parts.push(`${days}d`);
  }
  if (hours > 0) {
    parts.push(`${hours}h`);
  }
  if (minutes > 0) {
    parts.push(`${minutes}m`);
  }

  return parts.join(' ') || '0m';
};

export const getProgressColor = (percent: number): string => {
  if (percent < 50) {
    return 'from-accent-emerald to-accent-teal';
  }
  if (percent <= 80) {
    return 'from-accent-yellow to-accent-orange';
  }
  return 'from-accent-red to-accent-orange';
};

export const formatSystemBytes = (bytes: number): string => formatBytesBase(bytes);
