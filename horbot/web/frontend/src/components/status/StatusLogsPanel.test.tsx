import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import StatusLogsPanel from './StatusLogsPanel';

describe('StatusLogsPanel', () => {
  it('shows the empty state when no logs are available', () => {
    render(
      <StatusLogsPanel
        logs={[]}
        logLevel=""
        logLines={100}
        setLogLevel={vi.fn()}
        setLogLines={vi.fn()}
        fetchLogs={vi.fn()}
      />,
    );

    expect(screen.getByText('No logs available')).toBeInTheDocument();
    expect(screen.getByText('Logs will appear here after the backend emits runtime output.')).toBeInTheDocument();
  });

  it('forwards filter changes and refresh actions', () => {
    const setLogLevel = vi.fn();
    const setLogLines = vi.fn();
    const fetchLogs = vi.fn();

    render(
      <StatusLogsPanel
        logs={[{ raw: 'warn line', level: 'WARNING' }]}
        logLevel="WARNING"
        logLines={200}
        setLogLevel={setLogLevel}
        setLogLines={setLogLines}
        fetchLogs={fetchLogs}
      />,
    );

    fireEvent.change(screen.getByLabelText('Filter by log level'), {
      target: { value: 'ERROR' },
    });
    fireEvent.change(screen.getByLabelText('Number of log lines'), {
      target: { value: '500' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }));

    expect(setLogLevel).toHaveBeenCalledWith('ERROR');
    expect(setLogLines).toHaveBeenCalledWith(500);
    expect(fetchLogs).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Filtered: WARNING')).toBeInTheDocument();
    expect(screen.getByText('warn line')).toBeInTheDocument();
  });
});
