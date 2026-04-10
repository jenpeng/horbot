import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { useDashboardSummary } from './useDashboardSummary';
import { statusService } from '../services';
import type { DashboardSummary } from '../types';

vi.mock('../services', async () => {
  const actual = await vi.importActual<typeof import('../services')>('../services');
  return {
    ...actual,
    statusService: {
      ...actual.statusService,
      getDashboardSummary: vi.fn(),
    },
  };
});

const summaryFixture: DashboardSummary = {
  generated_at: '2026-04-10T00:00:00Z',
  system_status: {
    status: 'running',
    version: '1.2.3',
    uptime: '1h',
    uptime_seconds: 3600,
    system: {
      cpu_percent: 25,
      memory: { total: 1024, available: 512, used: 512, percent: 50 },
      disk: { total: 2048, used: 1024, free: 1024, percent: 50 },
    },
    services: {
      cron: { enabled: true, jobs_count: 2 },
      agent: { initialized: true },
    },
    config: {
      workspace: '/tmp/workspace',
      model: 'gpt-test',
      provider: 'openai',
    },
  },
  provider: {
    name: 'openai',
    configured: true,
  },
  channels: {
    items: [
      {
        name: 'wechat',
        display_name: 'WeChat',
        enabled: true,
        configured: true,
        status: 'online',
        status_label: '就绪',
        reason: null,
        missing_fields: [],
      },
      {
        name: 'slack',
        display_name: 'Slack',
        enabled: true,
        configured: false,
        status: 'error',
        status_label: '配置缺失',
        reason: '缺少 token',
        missing_fields: ['token'],
      },
      {
        name: 'discord',
        display_name: 'Discord',
        enabled: false,
        configured: true,
        status: 'disabled',
        status_label: '已禁用',
        reason: '当前通道未启用',
        missing_fields: [],
      },
    ],
    counts: {
      total: 3,
      enabled: 2,
      online: 1,
      disabled: 1,
      misconfigured: 1,
    },
  },
  recent_activities: [],
  alerts: [],
};

describe('useDashboardSummary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(statusService.getDashboardSummary).mockResolvedValue(summaryFixture);
  });

  it('loads dashboard summary and exposes derived channel counts', async () => {
    const { result } = renderHook(() => useDashboardSummary());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(statusService.getDashboardSummary).toHaveBeenCalledTimes(1);
    expect(result.current.systemStatus?.version).toBe('1.2.3');
    expect(result.current.channelCounts).toEqual(summaryFixture.channels.counts);
    expect(result.current.channelStatusList).toHaveLength(3);
  });

  it('refreshes summary without reloading the page', async () => {
    const refreshedSummary: DashboardSummary = {
      ...summaryFixture,
      system_status: {
        ...summaryFixture.system_status,
        version: '1.2.4',
      },
    };

    vi.mocked(statusService.getDashboardSummary)
      .mockResolvedValueOnce(summaryFixture)
      .mockResolvedValueOnce(refreshedSummary);

    const { result } = renderHook(() => useDashboardSummary());

    await waitFor(() => {
      expect(result.current.systemStatus?.version).toBe('1.2.3');
    });

    await act(async () => {
      result.current.refreshSummary();
    });

    await waitFor(() => {
      expect(result.current.systemStatus?.version).toBe('1.2.4');
    });
    expect(statusService.getDashboardSummary).toHaveBeenCalledTimes(2);
  });
});
