export const ServiceStatus = {
  RUNNING: 'running',
  STOPPED: 'stopped',
  ERROR: 'error',
  INITIALIZING: 'initializing',
} as const;

export const TaskStatus = {
  OK: 'ok',
  ERROR: 'error',
  PENDING: 'pending',
  RUNNING: 'running',
  CANCELLED: 'cancelled',
} as const;

export const LogLevel = {
  DEBUG: 'DEBUG',
  INFO: 'INFO',
  WARNING: 'WARNING',
  ERROR: 'ERROR',
  CRITICAL: 'CRITICAL',
} as const;

export const LOG_LEVELS = Object.values(LogLevel);

export const ScheduleKind = {
  EVERY: 'every',
  CRON: 'cron',
  AT: 'at',
} as const;
