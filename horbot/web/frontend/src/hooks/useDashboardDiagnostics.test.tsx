import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useDashboardDiagnostics } from './useDashboardDiagnostics';
import { diagnosticsService } from '../services';
import type { ConfigCheckResultData } from '../components/ConfigCheckResult';
import type { FixResult, MemoryData } from '../services/diagnostics';

vi.mock('../services', () => ({
  diagnosticsService: {
    validateConfig: vi.fn(),
    getGatewayDiagnostics: vi.fn(),
    getEnvironment: vi.fn(),
    getMemory: vi.fn(),
    runFix: vi.fn(),
  },
}));

const configFixture: ConfigCheckResultData = {
  status: 'passed',
  errors: [],
  warnings: [],
  info: [],
};

const memoryFixture: MemoryData = {
  total_entries: 4,
  total_size_kb: 12,
  oldest_entry: null,
  newest_entry: null,
  details: {},
};

const fixFixture: FixResult = {
  fixed: [{ issue: 'config', message: 'updated' }],
  failed: [],
  suggestions: [],
};

describe('useDashboardDiagnostics', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('alert', vi.fn());
    vi.mocked(diagnosticsService.validateConfig).mockResolvedValue(configFixture);
    vi.mocked(diagnosticsService.getGatewayDiagnostics).mockResolvedValue({
      channels: [],
      overall_status: 'healthy',
    });
    vi.mocked(diagnosticsService.getEnvironment).mockResolvedValue({
      python_version: '3.11',
      os_info: {
        system: 'macOS',
        release: '14',
        version: '14.0',
        machine: 'arm64',
      },
      dependencies: [],
      resources: {
        disk: { used: 1, total: 2, percent: 50 },
        memory: { used: 1, total: 2, percent: 50 },
        cpu: 20,
      },
      workspace: {
        path: '/tmp/workspace',
        exists: true,
        writable: true,
      },
    });
    vi.mocked(diagnosticsService.getMemory).mockResolvedValue(memoryFixture);
    vi.mocked(diagnosticsService.runFix).mockResolvedValue(fixFixture);
  });

  it('loads a diagnostic modal and stores the fetched result', async () => {
    const { result } = renderHook(() => useDashboardDiagnostics());

    await act(async () => {
      const handled = await result.current.openSkillDiagnostic('config-check');
      expect(handled).toBe(true);
    });

    expect(diagnosticsService.validateConfig).toHaveBeenCalledTimes(1);
    expect(result.current.activeModal).toBe('config-check');
    expect(result.current.modalLoading).toBe(false);
    expect(result.current.modalError).toBeNull();
    expect(result.current.configCheckData).toEqual(configFixture);
  });

  it('surfaces fallback errors for failed diagnostic loaders', async () => {
    vi.mocked(diagnosticsService.getMemory).mockRejectedValueOnce('network down');
    const { result } = renderHook(() => useDashboardDiagnostics());

    await act(async () => {
      const handled = await result.current.openSkillDiagnostic('memory-manager');
      expect(handled).toBe(true);
    });

    expect(result.current.activeModal).toBe('memory-manager');
    expect(result.current.modalLoading).toBe(false);
    expect(result.current.memoryData).toBeNull();
    expect(result.current.modalError).toBe('获取内存信息失败');
  });

  it('runs the one-click fix flow and exposes the result modal', async () => {
    const { result } = renderHook(() => useDashboardDiagnostics());

    await act(async () => {
      const handled = await result.current.openSkillDiagnostic('one-click-fix');
      expect(handled).toBe(true);
    });
    expect(result.current.showFixConfirm).toBe(true);

    await act(async () => {
      await result.current.confirmFix();
    });

    await waitFor(() => {
      expect(result.current.fixLoading).toBe(false);
    });

    expect(diagnosticsService.runFix).toHaveBeenCalledTimes(1);
    expect(result.current.showFixConfirm).toBe(false);
    expect(result.current.activeModal).toBe('fix-result');
    expect(result.current.fixResult).toEqual(fixFixture);
  });

  it('alerts on fix failure and keeps the confirm dialog open', async () => {
    vi.mocked(diagnosticsService.runFix).mockRejectedValueOnce(new Error('fix failed'));
    const { result } = renderHook(() => useDashboardDiagnostics());

    await act(async () => {
      await result.current.openSkillDiagnostic('one-click-fix');
    });

    await act(async () => {
      await result.current.confirmFix();
    });

    expect(globalThis.alert).toHaveBeenCalledWith('fix failed');
    expect(result.current.fixLoading).toBe(false);
    expect(result.current.showFixConfirm).toBe(true);
    expect(result.current.activeModal).toBeNull();
    expect(result.current.fixResult).toBeNull();
  });
});
