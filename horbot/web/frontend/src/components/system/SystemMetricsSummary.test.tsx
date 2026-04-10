import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import SystemMetricsSummary from './SystemMetricsSummary';
import type { SystemStatus } from '../../types';

const systemStatusFixture: SystemStatus = {
  status: 'running',
  version: '1.2.3',
  uptime: '1h',
  uptime_seconds: 3720,
  system: {
    cpu_percent: 33.3,
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
    cron: { enabled: true, jobs_count: 2 },
    agent: { initialized: true },
  },
  config: {
    workspace: '/tmp/workspace',
  },
};

describe('SystemMetricsSummary', () => {
  it('renders shared system status metrics', () => {
    render(
      <SystemMetricsSummary
        systemStatus={systemStatusFixture}
        compact
        showStatus
        showUptime
      />,
    );

    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(screen.getByText('33.3%')).toBeInTheDocument();
    expect(screen.getAllByText('50%')).toHaveLength(2);
    expect(screen.getByText('1h 2m')).toBeInTheDocument();
  });
});
