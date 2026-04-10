import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useStatusPageData } from './useStatusPageData';
import statusService from '../services/status';
import type { ApiMetricsResponse, LogEntry, MemoryStatsResponse } from '../services/status';
import type { SystemStatus } from '../types';

vi.mock('../services/status', () => ({
  default: {
    getStatus: vi.fn(),
    getLogs: vi.fn(),
    getApiMetrics: vi.fn(),
    getMemoryStats: vi.fn(),
  },
}));

const statusFixture: SystemStatus = {
  status: 'running',
  version: '1.2.3',
  uptime: '1h',
  uptime_seconds: 3600,
  system: {
    cpu_percent: 20,
    memory: {
      total: 1024,
      available: 512,
      used: 512,
      percent: 50,
    },
    disk: {
      total: 2048,
      used: 1024,
      free: 1024,
      percent: 50,
    },
  },
  services: {
    cron: {
      enabled: true,
      jobs_count: 1,
    },
    agent: {
      initialized: true,
    },
  },
  config: {
    workspace: '/tmp/workspace',
  },
};

const logsFixture: LogEntry[] = [{ raw: 'hello', level: 'INFO' }];

const apiMetricsFixture: ApiMetricsResponse = {
  total_count: 1,
  avg_process_time_ms: 12,
  error_count: 0,
  recent_requests: [],
};

const memoryStatsFixture: MemoryStatsResponse = {
  total_entries: 1,
  total_size_kb: 1,
  oldest_entry: null,
  newest_entry: null,
  details: {},
};

describe('useStatusPageData', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    vi.mocked(statusService.getStatus).mockResolvedValue(statusFixture);
    vi.mocked(statusService.getLogs).mockResolvedValue({ logs: logsFixture });
    vi.mocked(statusService.getApiMetrics).mockResolvedValue(apiMetricsFixture);
    vi.mocked(statusService.getMemoryStats).mockResolvedValue(memoryStatsFixture);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('loads all base datasets on mount', async () => {
    const { result } = renderHook(() => useStatusPageData('overview'));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(statusService.getStatus).toHaveBeenCalledTimes(1);
    expect(statusService.getLogs).toHaveBeenCalledTimes(1);
    expect(statusService.getApiMetrics).toHaveBeenCalledTimes(1);
    expect(statusService.getMemoryStats).toHaveBeenCalledTimes(1);
    expect(result.current.status?.version).toBe('1.2.3');
    expect(result.current.logs).toEqual(logsFixture);
  });

  it('refreshes all datasets through the shared page refresh action', async () => {
    const { result } = renderHook(() => useStatusPageData('overview'));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.refreshPage();
    });

    expect(statusService.getStatus).toHaveBeenCalledTimes(2);
    expect(statusService.getLogs).toHaveBeenCalledTimes(2);
    expect(statusService.getApiMetrics).toHaveBeenCalledTimes(2);
    expect(statusService.getMemoryStats).toHaveBeenCalledTimes(2);
  });

  it('polls tab-specific data for api without refetching memory stats', async () => {
    vi.useFakeTimers();
    renderHook(() => useStatusPageData('api'));

    await act(async () => {
      await Promise.resolve();
    });

    expect(statusService.getStatus).toHaveBeenCalledTimes(1);
    expect(statusService.getApiMetrics).toHaveBeenCalledTimes(2);
    expect(statusService.getMemoryStats).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(10000);
      await Promise.resolve();
    });

    expect(statusService.getStatus).toHaveBeenCalledTimes(2);
    expect(statusService.getApiMetrics).toHaveBeenCalledTimes(3);
    expect(statusService.getMemoryStats).toHaveBeenCalledTimes(1);
  });

  it('refetches logs when log filters change on the logs tab', async () => {
    const { result } = renderHook(() => useStatusPageData('logs'));

    await waitFor(() => {
      expect(statusService.getLogs).toHaveBeenCalledTimes(2);
    });

    await act(async () => {
      result.current.setLogLevel('ERROR');
    });

    await waitFor(() => {
      expect(statusService.getLogs).toHaveBeenCalledTimes(3);
    });
    expect(statusService.getLogs).toHaveBeenLastCalledWith({ lines: 100, level: 'ERROR' });

    await act(async () => {
      result.current.setLogLines(200);
    });

    await waitFor(() => {
      expect(statusService.getLogs).toHaveBeenCalledTimes(4);
    });
    expect(statusService.getLogs).toHaveBeenLastCalledWith({ lines: 200, level: 'ERROR' });
  });
});
