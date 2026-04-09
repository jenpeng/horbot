export function formatRelativeTime(ms: number): string {
  const now = Date.now();
  const diff = now - ms;
  const absDiff = Math.abs(diff);
  const isPast = diff > 0;
  
  const seconds = Math.floor(absDiff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  const months = Math.floor(days / 30);
  const years = Math.floor(days / 365);
  
  let timeStr: string;
  
  if (seconds < 60) {
    timeStr = '刚刚';
  } else if (minutes < 60) {
    timeStr = `${minutes}分钟${isPast ? '前' : '后'}`;
  } else if (hours < 24) {
    timeStr = `${hours}小时${isPast ? '前' : '后'}`;
  } else if (days < 30) {
    timeStr = `${days}天${isPast ? '前' : '后'}`;
  } else if (months < 12) {
    timeStr = `${months}个月${isPast ? '前' : '后'}`;
  } else {
    timeStr = `${years}年${isPast ? '前' : '后'}`;
  }
  
  return timeStr;
}

export function formatAbsoluteTime(ms: number): string {
  const date = new Date(ms);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');
  
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

export function formatDate(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  
  return `${year}-${month}-${day}`;
}
