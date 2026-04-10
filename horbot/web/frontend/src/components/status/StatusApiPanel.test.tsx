import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import StatusApiPanel from './StatusApiPanel';
import type { ApiMetricsResponse } from '../../services/status';

describe('StatusApiPanel', () => {
  it('shows an empty state when there are no recent requests', () => {
    const apiMetrics: ApiMetricsResponse = {
      total_count: 0,
      avg_process_time_ms: 0,
      error_count: 0,
      recent_requests: [],
    };

    render(<StatusApiPanel apiMetrics={apiMetrics} />);

    expect(screen.getByText('No recent requests')).toBeInTheDocument();
    expect(screen.getByText('API samples will appear here after the backend receives requests.')).toBeInTheDocument();
  });

  it('renders request metrics and request rows when data exists', () => {
    const apiMetrics: ApiMetricsResponse = {
      total_count: 8,
      avg_process_time_ms: 123,
      error_count: 1,
      recent_requests: [
        {
          timestamp: '2026-04-10T09:00:00Z',
          method: 'POST',
          url: '/api/chat',
          status_code: 500,
          process_time_ms: 456,
          client_ip: '127.0.0.1',
        },
      ],
    };

    render(<StatusApiPanel apiMetrics={apiMetrics} />);

    expect(screen.getByText('8')).toBeInTheDocument();
    expect(screen.getByText('123 ms')).toBeInTheDocument();
    expect(screen.getByText('/api/chat')).toBeInTheDocument();
    expect(screen.getByText('POST')).toBeInTheDocument();
    expect(screen.getByText('500')).toBeInTheDocument();
  });
});
