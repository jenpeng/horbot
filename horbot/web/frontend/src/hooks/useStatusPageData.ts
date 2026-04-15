import { useEffect, useState } from 'react';
import statusService from '../services/status';
import type { SystemStatus } from '../types';
import type { LogEntry, ApiMetricsResponse, MemoryStatsResponse } from '../services/status';
import { createAsyncResourceCache } from '../utils/asyncResourceCache';

const statusCache = createAsyncResourceCache(
  () => statusService.getStatus(),
  {
    ttlMs: 10_000,
    keyFn: () => 'status',
  },
);

const apiMetricsCache = createAsyncResourceCache(
  () => statusService.getApiMetrics(100),
  {
    ttlMs: 10_000,
    keyFn: () => 'api-metrics',
  },
);

const memoryStatsCache = createAsyncResourceCache(
  () => statusService.getMemoryStats(),
  {
    ttlMs: 10_000,
    keyFn: () => 'memory-stats',
  },
);

const logsCache = createAsyncResourceCache(
  (lines: number, level: string) => statusService.getLogs(level ? { lines, level } : { lines }),
  {
    ttlMs: 10_000,
    keyFn: (lines: number, level: string) => `logs:${lines}:${level || 'all'}`,
  },
);

export const useStatusPageData = (activeTab: 'overview' | 'resources' | 'services' | 'api' | 'logs') => {
  const [status, setStatus] = useState<SystemStatus | null>(statusCache.peek() ?? null);
  const [logs, setLogs] = useState<LogEntry[]>(logsCache.peek(100, '')?.logs || []);
  const [apiMetrics, setApiMetrics] = useState<ApiMetricsResponse | null>(apiMetricsCache.peek() ?? null);
  const [memoryStats, setMemoryStats] = useState<MemoryStatsResponse | null>(memoryStatsCache.peek() ?? null);
  const [isLoading, setIsLoading] = useState(() => !statusCache.peek());
  const [error, setError] = useState<string | null>(null);
  const [logLevel, setLogLevel] = useState<string>('');
  const [logLines, setLogLines] = useState<number>(100);

  const fetchStatus = async (options: { force?: boolean } = {}) => {
    try {
      const response = options.force ? await statusCache.refresh() : await statusCache.get();
      setStatus(response);
      setError(null);
    } catch (err) {
      setError('Failed to fetch system status');
      console.error('Error fetching status:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchLogs = async (options: { force?: boolean } = {}) => {
    try {
      const response = options.force
        ? await logsCache.refresh(logLines, logLevel)
        : await logsCache.get(logLines, logLevel);
      setLogs(response.logs || []);
    } catch (err) {
      console.error('Error fetching logs:', err);
    }
  };

  const fetchApiMetrics = async (options: { force?: boolean } = {}) => {
    try {
      const response = options.force ? await apiMetricsCache.refresh() : await apiMetricsCache.get();
      setApiMetrics(response);
    } catch (err) {
      console.error('Error fetching API metrics:', err);
    }
  };

  const fetchMemoryStats = async (options: { force?: boolean } = {}) => {
    try {
      const response = options.force ? await memoryStatsCache.refresh() : await memoryStatsCache.get();
      setMemoryStats(response);
    } catch (err) {
      console.error('Error fetching memory stats:', err);
    }
  };

  const refreshPage = async () => {
    const tasks: Promise<unknown>[] = [fetchStatus({ force: true })];
    if (activeTab === 'logs') {
      tasks.push(fetchLogs({ force: true }));
    }
    if (activeTab === 'api') {
      tasks.push(fetchApiMetrics({ force: true }));
    }
    if (activeTab === 'overview' || activeTab === 'resources') {
      tasks.push(fetchMemoryStats({ force: true }));
    }
    await Promise.all(tasks);
  };

  useEffect(() => {
    const hasCachedStatus = Boolean(statusCache.peek());
    setIsLoading(!hasCachedStatus);

    void (async () => {
      await fetchStatus();
      if (activeTab === 'logs') {
        await fetchLogs();
      }
      if (activeTab === 'api') {
        await fetchApiMetrics();
      }
      if (activeTab === 'overview' || activeTab === 'resources') {
        await fetchMemoryStats();
      }
    })();

    const interval = window.setInterval(() => {
      void fetchStatus();
      if (activeTab === 'api') {
        void fetchApiMetrics();
      }
      if (activeTab === 'overview' || activeTab === 'resources') {
        void fetchMemoryStats();
      }
    }, 10000);

    return () => window.clearInterval(interval);
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === 'logs') {
      void fetchLogs();
    } else if (activeTab === 'api') {
      void fetchApiMetrics();
    }
  }, [logLevel, logLines, activeTab]);

  return {
    status,
    logs,
    apiMetrics,
    memoryStats,
    isLoading,
    error,
    logLevel,
    logLines,
    setLogLevel,
    setLogLines,
    refreshPage,
    fetchStatus,
    fetchLogs,
    fetchApiMetrics,
    fetchMemoryStats,
  };
};
