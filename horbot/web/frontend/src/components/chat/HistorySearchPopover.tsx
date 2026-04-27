import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type RefObject,
} from 'react';
import { Search, X } from 'lucide-react';

interface HistorySearchMatchSummary {
  label: string;
  preview: string;
}

interface RemoteHistorySearchMatch {
  message_id: string;
  role: 'user' | 'assistant';
  preview: string;
  timestamp?: string;
  agent_id?: string;
  agent_name?: string;
}

type HistorySearchTimeRange = 'all' | '7d' | '30d';
type TranslateFn = (key: string, values?: Record<string, string | number>) => string;

interface HistorySearchPopoverProps {
  t: TranslateFn;
  messageTurnsCount: number;
  historySearchInputRef: RefObject<HTMLInputElement | null>;
  historySearchQuery: string;
  setHistorySearchQuery: (value: string) => void;
  setHistorySearchIndex: (value: number) => void;
  setActiveHistoryResultKey: (value: string | null) => void;
  setActiveRemoteHistoryResultId: (value: string | null) => void;
  onClose: () => void;
  isPartialHistoryLoaded: boolean;
  historySearchTimeRange: HistorySearchTimeRange;
  setHistorySearchTimeRange: (value: HistorySearchTimeRange) => void;
  handleHistorySearchMove: (direction: 'prev' | 'next') => void;
  historySearchMatchesCount: number;
  historySearchIndex: number;
  activeHistoryMatch: HistorySearchMatchSummary | null;
  remoteHistorySearchTotal: number;
  isRemoteHistorySearchLoading: boolean;
  remoteHistorySearchVisibleMatches: RemoteHistorySearchMatch[];
  getAgentName: (agentId?: string) => string | undefined;
  formatTime: (timestamp?: string) => string;
  activeRemoteHistoryResultId: string | null;
  handleSelectRemoteHistorySearchMatch: (match: RemoteHistorySearchMatch) => void | Promise<void>;
  isLoadingHistorySearchContext: boolean;
  remoteHistorySearchHasMore: boolean;
  handleLoadMoreRemoteHistorySearch: () => void | Promise<void>;
  isRemoteHistorySearchLoadingMore: boolean;
}

const REMOTE_RESULTS_ROW_HEIGHT = 80;
const REMOTE_RESULTS_ROW_GAP = 8;
const REMOTE_RESULTS_OVERSCAN = 4;
const REMOTE_RESULTS_MAX_VIEWPORT_HEIGHT = 320;

const HistorySearchPopover = ({
  t,
  messageTurnsCount,
  historySearchInputRef,
  historySearchQuery,
  setHistorySearchQuery,
  setHistorySearchIndex,
  setActiveHistoryResultKey,
  setActiveRemoteHistoryResultId,
  onClose,
  isPartialHistoryLoaded,
  historySearchTimeRange,
  setHistorySearchTimeRange,
  handleHistorySearchMove,
  historySearchMatchesCount,
  historySearchIndex,
  activeHistoryMatch,
  remoteHistorySearchTotal,
  isRemoteHistorySearchLoading,
  remoteHistorySearchVisibleMatches,
  getAgentName,
  formatTime,
  activeRemoteHistoryResultId,
  handleSelectRemoteHistorySearchMatch,
  isLoadingHistorySearchContext,
  remoteHistorySearchHasMore,
  handleLoadMoreRemoteHistorySearch,
  isRemoteHistorySearchLoadingMore,
}: HistorySearchPopoverProps) => {
  const remoteResultsScrollRef = useRef<HTMLDivElement>(null);
  const [remoteResultsScrollTop, setRemoteResultsScrollTop] = useState(0);

  const remoteResultsViewportHeight = useMemo(
    () => Math.min(
      REMOTE_RESULTS_MAX_VIEWPORT_HEIGHT,
      remoteHistorySearchVisibleMatches.length * (REMOTE_RESULTS_ROW_HEIGHT + REMOTE_RESULTS_ROW_GAP),
    ),
    [remoteHistorySearchVisibleMatches.length],
  );

  const remoteResultsMetrics = useMemo(() => {
    const itemSize = REMOTE_RESULTS_ROW_HEIGHT + REMOTE_RESULTS_ROW_GAP;
    const totalHeight = remoteHistorySearchVisibleMatches.length === 0
      ? 0
      : (remoteHistorySearchVisibleMatches.length * itemSize) - REMOTE_RESULTS_ROW_GAP;

    return {
      itemSize,
      totalHeight,
    };
  }, [remoteHistorySearchVisibleMatches.length]);

  const visibleRemoteResults = useMemo(() => {
    if (remoteHistorySearchVisibleMatches.length === 0) {
      return [];
    }

    const startIndex = Math.max(
      0,
      Math.floor(remoteResultsScrollTop / remoteResultsMetrics.itemSize) - REMOTE_RESULTS_OVERSCAN,
    );
    const viewportEnd = remoteResultsScrollTop + Math.max(1, remoteResultsViewportHeight);
    const endIndex = Math.min(
      remoteHistorySearchVisibleMatches.length - 1,
      Math.ceil(viewportEnd / remoteResultsMetrics.itemSize) + REMOTE_RESULTS_OVERSCAN,
    );

    const items: Array<{ match: RemoteHistorySearchMatch; index: number }> = [];
    for (let index = startIndex; index <= endIndex; index += 1) {
      const match = remoteHistorySearchVisibleMatches[index];
      if (match) {
        items.push({ match, index });
      }
    }
    return items;
  }, [
    remoteHistorySearchVisibleMatches,
    remoteResultsMetrics.itemSize,
    remoteResultsScrollTop,
    remoteResultsViewportHeight,
  ]);

  const handleRemoteResultsScroll = useCallback(() => {
    const container = remoteResultsScrollRef.current;
    if (!container) {
      return;
    }
    setRemoteResultsScrollTop(container.scrollTop);
  }, []);

  useEffect(() => {
    const container = remoteResultsScrollRef.current;
    if (!container) {
      setRemoteResultsScrollTop(0);
      return;
    }

    container.scrollTop = 0;
    setRemoteResultsScrollTop(0);
  }, [historySearchQuery, historySearchTimeRange]);

  return (
    <div className="absolute right-0 top-full z-20 mt-2 w-[min(92vw,32rem)] rounded-2xl border border-slate-200 bg-white/95 p-3 shadow-xl backdrop-blur">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-800">{t('chat.historySearchSession')}</div>
          <div className="text-[11px] text-slate-400">{t('chat.historySearchTurns', { count: messageTurnsCount })}</div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="inline-flex h-8 w-8 items-center justify-center rounded-full text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
          aria-label={t('chat.closeSearch')}
        >
          <X className="h-4 w-4" strokeWidth={2} />
        </button>
      </div>

      <div className="mt-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" strokeWidth={2} />
          <input
            ref={historySearchInputRef}
            value={historySearchQuery}
            onChange={(event) => {
              setHistorySearchQuery(event.target.value);
              setHistorySearchIndex(0);
              setActiveRemoteHistoryResultId(null);
            }}
            placeholder={t('chat.historySearchPlaceholder')}
            className="h-11 w-full rounded-xl border border-slate-200 bg-slate-50 pl-10 pr-10 text-sm text-slate-700 outline-none transition focus:border-sky-300 focus:bg-white focus:ring-2 focus:ring-sky-100"
          />
          {historySearchQuery && (
            <button
              type="button"
              onClick={() => {
                setHistorySearchQuery('');
                setHistorySearchIndex(0);
                setActiveHistoryResultKey(null);
                setActiveRemoteHistoryResultId(null);
              }}
              className="absolute right-2 top-1/2 inline-flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full text-slate-400 transition hover:bg-slate-200 hover:text-slate-600"
              aria-label={t('chat.searchClear')}
            >
              <X className="h-3.5 w-3.5" strokeWidth={2} />
            </button>
          )}
        </div>
      </div>

      {isPartialHistoryLoaded && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {(['all', '7d', '30d'] as HistorySearchTimeRange[]).map((range) => (
            <button
              key={range}
              type="button"
              onClick={() => setHistorySearchTimeRange(range)}
              className={`rounded-full border px-3 py-1.5 text-[11px] font-medium transition ${
                historySearchTimeRange === range
                  ? 'border-sky-300 bg-sky-50 text-sky-700'
                  : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
              }`}
            >
              {range === 'all'
                ? t('chat.historySearchRangeAll')
                : range === '7d'
                  ? t('chat.historySearchRange7d')
                  : t('chat.historySearchRange30d')}
            </button>
          ))}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => handleHistorySearchMove('prev')}
          disabled={historySearchMatchesCount === 0}
          className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {t('chat.previousResult')}
        </button>
        <button
          type="button"
          onClick={() => handleHistorySearchMove('next')}
          disabled={historySearchMatchesCount === 0}
          className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {t('chat.nextResult')}
        </button>
        {historySearchMatchesCount > 0 && (
          <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700">
            {historySearchIndex + 1} / {historySearchMatchesCount}
          </span>
        )}
      </div>

      {isPartialHistoryLoaded && (
        <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] leading-5 text-amber-700">
          {t('chat.historySearchLoadedOnly')}
        </p>
      )}

      {historySearchQuery && (
        <div className="mt-3 space-y-3">
          <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
            <div className="flex items-center justify-between gap-3">
              <div className="text-xs font-semibold text-slate-700">
                {t('chat.historySearchLoadedResults', { count: historySearchMatchesCount })}
              </div>
              {activeHistoryMatch && (
                <span className="text-[11px] text-slate-500">
                  {activeHistoryMatch.label}
                </span>
              )}
            </div>
            {activeHistoryMatch ? (
              <p className="mt-2 text-xs leading-5 text-slate-500">
                {activeHistoryMatch.preview}
              </p>
            ) : (
              <p className="mt-2 text-xs leading-5 text-slate-400">
                {t('chat.historySearchNoLoadedResults')}
              </p>
            )}
          </div>

          {isPartialHistoryLoaded && (
            <div className="rounded-xl border border-sky-200 bg-sky-50/70 p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold text-sky-900">
                    {t('chat.historySearchAllHistory', { count: remoteHistorySearchTotal })}
                  </div>
                  <p className="mt-1 text-[11px] leading-5 text-sky-700">
                    {t('chat.historySearchAllHistoryHint')}
                  </p>
                </div>
                {isRemoteHistorySearchLoading && (
                  <span className="text-[11px] font-medium text-sky-700">
                    {t('chat.historySearchSearchingAllHistory')}
                  </span>
                )}
              </div>

              {remoteHistorySearchVisibleMatches.length > 0 ? (
                <div className="mt-3 space-y-2">
                  <div
                    ref={remoteResultsScrollRef}
                    data-testid="history-search-remote-results-viewport"
                    onScroll={handleRemoteResultsScroll}
                    className="overflow-y-auto rounded-xl"
                    style={{ maxHeight: `${REMOTE_RESULTS_MAX_VIEWPORT_HEIGHT}px`, height: `${remoteResultsViewportHeight}px` }}
                  >
                    <div
                      className="relative"
                      style={{ height: `${remoteResultsMetrics.totalHeight}px` }}
                    >
                      {visibleRemoteResults.map(({ match, index }) => {
                        const resultLabel = match.role === 'user'
                          ? t('common.user')
                          : (match.agent_name || getAgentName(match.agent_id) || t('chat.assistantFallback'));
                        const isActive = activeRemoteHistoryResultId === match.message_id;

                        return (
                          <div
                            key={match.message_id}
                            style={{
                              position: 'absolute',
                              top: `${index * remoteResultsMetrics.itemSize}px`,
                              left: 0,
                              right: 0,
                              height: `${REMOTE_RESULTS_ROW_HEIGHT}px`,
                            }}
                          >
                            <button
                              type="button"
                              data-testid="history-search-remote-result"
                              onClick={() => {
                                void handleSelectRemoteHistorySearchMatch(match);
                              }}
                              disabled={isLoadingHistorySearchContext}
                              className={`block h-full w-full rounded-xl border px-3 py-2 text-left transition ${
                                isActive
                                  ? 'border-sky-300 bg-white shadow-sm'
                                  : 'border-sky-100 bg-white/80 hover:border-sky-200 hover:bg-white'
                              } disabled:cursor-not-allowed disabled:opacity-60`}
                            >
                              <div className="flex items-center justify-between gap-3">
                                <span className="truncate text-xs font-semibold text-slate-700">{resultLabel}</span>
                                <span className="shrink-0 text-[11px] text-slate-400">
                                  {match.timestamp ? formatTime(match.timestamp) : t('chat.historySearchJumpToResult')}
                                </span>
                              </div>
                              <p
                                className="mt-1 text-xs leading-5 text-slate-500"
                                style={{
                                  display: '-webkit-box',
                                  overflow: 'hidden',
                                  WebkitBoxOrient: 'vertical',
                                  WebkitLineClamp: 2,
                                }}
                              >
                                {match.preview}
                              </p>
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  {remoteHistorySearchHasMore && (
                    <button
                      type="button"
                      onClick={() => {
                        void handleLoadMoreRemoteHistorySearch();
                      }}
                      disabled={isRemoteHistorySearchLoadingMore}
                      className="w-full rounded-xl border border-sky-200 bg-white px-3 py-2 text-xs font-medium text-sky-700 transition hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {isRemoteHistorySearchLoadingMore
                        ? t('chat.historySearchLoadingMore')
                        : t('chat.historySearchLoadMore')}
                    </button>
                  )}
                  {remoteHistorySearchTotal > remoteHistorySearchVisibleMatches.length && (
                    <p className="text-[11px] text-sky-700">
                      {t('chat.historySearchMoreResults', {
                        count: remoteHistorySearchTotal - remoteHistorySearchVisibleMatches.length,
                      })}
                    </p>
                  )}
                </div>
              ) : !isRemoteHistorySearchLoading ? (
                <p className="mt-3 text-xs leading-5 text-sky-700">
                  {remoteHistorySearchTotal > 0
                    ? t('chat.historySearchAllResultsAlreadyLoaded')
                    : t('chat.historySearchNoFullResults')}
                </p>
              ) : null}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default HistorySearchPopover;
