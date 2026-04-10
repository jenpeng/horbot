import { useEffect, useState } from 'react';
import statusService from '../services/status';
import type { SystemStatus } from '../types';
import type { LogEntry, ApiMetricsResponse, MemoryStatsResponse } from '../services/status';

export const useStatusPageData = (activeTab: 'overview' | 'resources' | 'services' | 'api' | 'logs') => {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [apiMetrics, setApiMetrics] = useState<ApiMetricsResponse | null>(null);
  const [memoryStats, setMemoryStats] = useState<MemoryStatsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [logLevel, setLogLevel] = useState<string>('');
  const [logLines, setLogLines] = useState<number>(100);

  const fetchStatus = async () => {
    try {
      const response = await statusService.getStatus();
      setStatus(response);
      setError(null);
    } catch (err) {
      setError('Failed to fetch system status');
      console.error('Error fetching status:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchLogs = async () => {
    try {
      const params: { lines: number; level?: string } = { lines: logLines };
      if (logLevel) {
        params.level = logLevel;
      }
      const response = await statusService.getLogs(params);
      setLogs(response.logs || []);
    } catch (err) {
      console.error('Error fetching logs:', err);
    }
  };

  const fetchApiMetrics = async () => {
    try {
      const response = await statusService.getApiMetrics(100);
      setApiMetrics(response);
    } catch (err) {
      console.error('Error fetching API metrics:', err);
    }
  };

  const fetchMemoryStats = async () => {
    try {
      const response = await statusService.getMemoryStats();
      setMemoryStats(response);
    } catch (err) {
      console.error('Error fetching memory stats:', err);
    }
  };

  const refreshPage = async () => {
    await Promise.all([
      fetchStatus(),
      fetchLogs(),
      fetchApiMetrics(),
      fetchMemoryStats(),
    ]);
  };

  useEffect(() => {
    void refreshPage();

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
