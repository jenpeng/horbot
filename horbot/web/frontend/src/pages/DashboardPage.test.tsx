import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DashboardPage from './DashboardPage';
import { useDashboardDiagnostics, useDashboardSummary } from '../hooks';

const navigateMock = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock('../hooks', async () => {
  const actual = await vi.importActual<typeof import('../hooks')>('../hooks');
  return {
    ...actual,
    useDashboardSummary: vi.fn(),
    useDashboardDiagnostics: vi.fn(),
  };
});

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    navigateMock.mockReset();
    vi.mocked(useDashboardDiagnostics).mockReturnValue({
      activeModal: null,
      modalLoading: false,
      modalError: null,
      configCheckData: null,
      gatewayDiagnosticsData: null,
      environmentData: null,
      memoryData: null,
      fixLoading: false,
      showFixConfirm: false,
      fixResult: null,
      openSkillDiagnostic: vi.fn().mockResolvedValue(false),
      closeModal: vi.fn(),
      confirmFix: vi.fn(),
      cancelFix: vi.fn(),
    });
    vi.mocked(useDashboardSummary).mockReturnValue({
      dashboardSummary: null,
      isLoading: false,
      error: null,
      refreshSummary: vi.fn(),
      systemStatus: {
        status: 'running',
        version: '1.2.3',
        uptime: '1h',
        uptime_seconds: 3600,
        system: {
          cpu_percent: 10,
          memory: { total: 1024, available: 512, used: 512, percent: 50 },
          disk: { total: 2048, used: 1024, free: 1024, percent: 50 },
        },
        services: {
          cron: { enabled: true, jobs_count: 1 },
          agent: { initialized: true },
        },
        config: { workspace: '/tmp/workspace' },
      },
      channelStatusList: [],
      channelCounts: {
        total: 0,
        enabled: 0,
        online: 0,
        disabled: 0,
        misconfigured: 0,
      },
      recentActivities: [],
      dashboardAlerts: [],
    });
  });

  it('uses refreshSummary when retrying from the error state', () => {
    const refreshSummary = vi.fn();
    vi.mocked(useDashboardSummary).mockReturnValue({
      dashboardSummary: null,
      isLoading: false,
      error: 'Failed to load data',
      refreshSummary,
      systemStatus: null,
      channelStatusList: [],
      channelCounts: {
        total: 0,
        enabled: 0,
        online: 0,
        disabled: 0,
        misconfigured: 0,
      },
      recentActivities: [],
      dashboardAlerts: [],
    });

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(refreshSummary).toHaveBeenCalledTimes(1);
  });

  it('routes navigation skills through navigate and stops on diagnostic skills', async () => {
    const openSkillDiagnostic = vi.fn()
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce(false);

    vi.mocked(useDashboardDiagnostics).mockReturnValue({
      activeModal: null,
      modalLoading: false,
      modalError: null,
      configCheckData: null,
      gatewayDiagnosticsData: null,
      environmentData: null,
      memoryData: null,
      fixLoading: false,
      showFixConfirm: false,
      fixResult: null,
      openSkillDiagnostic,
      closeModal: vi.fn(),
      confirmFix: vi.fn(),
      cancelFix: vi.fn(),
    });

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByText('Config Check'));
    await waitFor(() => {
      expect(openSkillDiagnostic).toHaveBeenCalledWith('config-check');
    });
    expect(navigateMock).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText('System Info'));
    await waitFor(() => {
      expect(openSkillDiagnostic).toHaveBeenCalledWith('system-info');
    });
    expect(navigateMock).toHaveBeenCalledWith('/status');
  });
});
