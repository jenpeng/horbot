import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import StatusPage from './StatusPage';
import { useStatusPageData } from '../hooks';
import type { MemoryStatsResponse, ApiMetricsResponse } from '../services/status';
import type { SystemStatus } from '../types';

vi.mock('../hooks', async () => {
  const actual = await vi.importActual<typeof import('../hooks')>('../hooks');
  return {
    ...actual,
    useStatusPageData: vi.fn(),
  };
});

const statusFixture: SystemStatus = {
  status: 'running',
  version: '1.2.3',
  uptime: '1h',
  uptime_seconds: 3600,
  system: {
    cpu_percent: 20,
    memory: {
      total: 8 * 1024 * 1024 * 1024,
      available: 4 * 1024 * 1024 * 1024,
      used: 4 * 1024 * 1024 * 1024,
      percent: 50,
    },
    disk: {
      total: 16 * 1024 * 1024 * 1024,
      used: 8 * 1024 * 1024 * 1024,
      free: 8 * 1024 * 1024 * 1024,
      percent: 50,
    },
  },
  services: {
    cron: {
      enabled: true,
      jobs_count: 2,
      next_wake_at_ms: 1712700000000,
    },
    agent: {
      initialized: true,
    },
  },
  config: {
    workspace: '/tmp/workspace',
    model: 'gpt-test',
    provider: 'openai',
  },
};

const memoryStatsFixture: MemoryStatsResponse = {
  total_entries: 10,
  total_size_kb: 12.5,
  oldest_entry: null,
  newest_entry: null,
  details: {
    metrics: {
      recall: {
        count: 4,
        avg_latency_ms: 100,
        max_latency_ms: 150,
        avg_candidates_count: 2,
        last_selected_memory_ids: ['m1'],
        last_samples: [],
      },
      consolidation: {
        count: 1,
        success_count: 1,
        failure_count: 0,
        avg_latency_ms: 200,
        max_latency_ms: 200,
        last_latency_ms: 200,
        last_status: 'success',
        last_samples: [],
      },
      growth: {
        current_entries: 10,
        current_size_bytes: 1024,
        history: [],
        last_delta_entries: 1,
        last_delta_bytes: 128,
      },
    },
  },
};

const apiMetricsFixture: ApiMetricsResponse = {
  total_count: 5,
  avg_process_time_ms: 120,
  error_count: 0,
  recent_requests: [
    {
      timestamp: '2026-04-10T01:00:00Z',
      method: 'GET',
      url: '/api/status',
      status_code: 200,
      process_time_ms: 30,
      client_ip: '127.0.0.1',
    },
  ],
};

describe('StatusPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useStatusPageData).mockImplementation(() => ({
      status: statusFixture,
      logs: [{ raw: 'hello log', level: 'INFO' }],
      apiMetrics: apiMetricsFixture,
      memoryStats: memoryStatsFixture,
      isLoading: false,
      error: null,
      logLevel: '',
      logLines: 100,
      setLogLevel: vi.fn(),
      setLogLines: vi.fn(),
      refreshPage: vi.fn(),
      fetchStatus: vi.fn(),
      fetchLogs: vi.fn(),
      fetchApiMetrics: vi.fn(),
      fetchMemoryStats: vi.fn(),
    }));
  });

  it('switches between status tabs and renders the selected panel', () => {
    render(<StatusPage />);

    expect(screen.getByRole('tab', { name: 'Overview' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByText('Memory Recall')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'Api' }));
    expect(screen.getByText('API Request Metrics')).toBeInTheDocument();
    expect(screen.getByText('/api/status')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'Logs' }));
    expect(screen.getByText('System Logs')).toBeInTheDocument();
    expect(screen.getByText('hello log')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'Services' }));
    expect(screen.getByText('Cron Service')).toBeInTheDocument();
    expect(screen.getByText('AI Agent')).toBeInTheDocument();
  });

  it('retries status loading from the error banner', () => {
    const refreshPage = vi.fn();
    vi.mocked(useStatusPageData).mockImplementation(() => ({
      status: statusFixture,
      logs: [],
      apiMetrics: apiMetricsFixture,
      memoryStats: memoryStatsFixture,
      isLoading: false,
      error: 'Failed to fetch system status',
      logLevel: '',
      logLines: 100,
      setLogLevel: vi.fn(),
      setLogLines: vi.fn(),
      refreshPage,
      fetchStatus: vi.fn(),
      fetchLogs: vi.fn(),
      fetchApiMetrics: vi.fn(),
      fetchMemoryStats: vi.fn(),
    }));

    render(<StatusPage />);

    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(refreshPage).toHaveBeenCalledTimes(1);
  });
});
