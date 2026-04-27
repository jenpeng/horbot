import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import HistorySearchPopover from './HistorySearchPopover';

const t = (key: string, values?: Record<string, string | number>) => {
  if (key === 'chat.historySearchLoadedResults') {
    return `loaded ${values?.count ?? 0}`;
  }
  if (key === 'chat.historySearchAllHistory') {
    return `all ${values?.count ?? 0}`;
  }
  if (key === 'chat.historySearchTurns') {
    return `turns ${values?.count ?? 0}`;
  }
  return key;
};

const buildRemoteMatches = (count: number) => Array.from({ length: count }, (_, index) => ({
  message_id: `remote-${index}`,
  role: 'assistant' as const,
  preview: `preview ${index} `.repeat(4),
  timestamp: `2026-04-26T10:${String(index % 60).padStart(2, '0')}:00Z`,
  agent_id: 'agent-a',
  agent_name: 'Agent A',
}));

describe('HistorySearchPopover', () => {
  it('window-renders remote full-history results instead of mounting the entire list', () => {
    render(
      <HistorySearchPopover
        t={t}
        messageTurnsCount={80}
        historySearchInputRef={{ current: null }}
        historySearchQuery="needle"
        setHistorySearchQuery={vi.fn()}
        setHistorySearchIndex={vi.fn()}
        setActiveHistoryResultKey={vi.fn()}
        setActiveRemoteHistoryResultId={vi.fn()}
        onClose={vi.fn()}
        isPartialHistoryLoaded
        historySearchTimeRange="all"
        setHistorySearchTimeRange={vi.fn()}
        handleHistorySearchMove={vi.fn()}
        historySearchMatchesCount={3}
        historySearchIndex={0}
        activeHistoryMatch={{ label: 'loaded', preview: 'loaded preview' }}
        remoteHistorySearchTotal={200}
        isRemoteHistorySearchLoading={false}
        remoteHistorySearchVisibleMatches={buildRemoteMatches(120)}
        getAgentName={() => 'Agent A'}
        formatTime={() => '10:00'}
        activeRemoteHistoryResultId={null}
        handleSelectRemoteHistorySearchMatch={vi.fn()}
        isLoadingHistorySearchContext={false}
        remoteHistorySearchHasMore
        handleLoadMoreRemoteHistorySearch={vi.fn()}
        isRemoteHistorySearchLoadingMore={false}
      />,
    );

    expect(screen.getAllByTestId('history-search-remote-result').length).toBeLessThan(30);
    expect(screen.getByRole('button', { name: 'chat.historySearchLoadMore' })).toBeInTheDocument();
  });

  it('updates the rendered window when the remote results viewport scrolls', () => {
    render(
      <HistorySearchPopover
        t={t}
        messageTurnsCount={80}
        historySearchInputRef={{ current: null }}
        historySearchQuery="needle"
        setHistorySearchQuery={vi.fn()}
        setHistorySearchIndex={vi.fn()}
        setActiveHistoryResultKey={vi.fn()}
        setActiveRemoteHistoryResultId={vi.fn()}
        onClose={vi.fn()}
        isPartialHistoryLoaded
        historySearchTimeRange="all"
        setHistorySearchTimeRange={vi.fn()}
        handleHistorySearchMove={vi.fn()}
        historySearchMatchesCount={3}
        historySearchIndex={0}
        activeHistoryMatch={{ label: 'loaded', preview: 'loaded preview' }}
        remoteHistorySearchTotal={200}
        isRemoteHistorySearchLoading={false}
        remoteHistorySearchVisibleMatches={buildRemoteMatches(120)}
        getAgentName={() => 'Agent A'}
        formatTime={() => '10:00'}
        activeRemoteHistoryResultId={null}
        handleSelectRemoteHistorySearchMatch={vi.fn()}
        isLoadingHistorySearchContext={false}
        remoteHistorySearchHasMore={false}
        handleLoadMoreRemoteHistorySearch={vi.fn()}
        isRemoteHistorySearchLoadingMore={false}
      />,
    );

    expect(screen.queryByText(/preview 50/)).not.toBeInTheDocument();

    const viewport = screen.getByTestId('history-search-remote-results-viewport');
    Object.defineProperty(viewport, 'scrollTop', {
      configurable: true,
      value: 4000,
      writable: true,
    });

    fireEvent.scroll(viewport);

    expect(screen.getByText(/preview 50/)).toBeInTheDocument();
  });
});
