import type { ReactNode } from 'react';
import { ChevronsDown, ChevronsUp, FoldVertical, UnfoldVertical } from 'lucide-react';
import { useI18n } from '../../contexts/I18nContext';

interface RelayTimelineStep {
  key: string;
  label: string;
  state: 'waiting' | 'active' | 'done' | 'error';
  detail: string;
  isFinal: boolean;
  groupIndex: number;
}

interface RelayTimelinePanelProps {
  relayTimelineSteps: RelayTimelineStep[];
  isTimelineExpanded: boolean;
  turnRetryPending: boolean;
  finalResponderName?: string;
  highlightedGroupIndex: number | null;
  pendingJumpGroupIndex: number | null;
  onToggleTimeline: () => void;
  onJumpToRelayStep: (groupIndex: number) => void;
  showRelaySummary: boolean;
  participantCount: number;
  inspectedStep: RelayTimelineStep | null;
  isExpanded: boolean;
  hiddenRelayCount: number;
  onToggleTurnExpanded: () => void;
}

const IconButton = ({
  label,
  icon,
  onClick,
  tone = 'neutral',
  dataTestId,
}: {
  label: string;
  icon: ReactNode;
  onClick: () => void;
  tone?: 'neutral' | 'violet';
  dataTestId?: string;
}) => (
  <button
    type="button"
    onClick={onClick}
    title={label}
    aria-label={label}
    data-testid={dataTestId}
    className={`inline-flex h-9 w-9 items-center justify-center rounded-full border transition-colors ${
      tone === 'violet'
        ? 'border-violet-200 bg-white text-violet-700 hover:bg-violet-100'
        : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
    }`}
  >
    {icon}
  </button>
);

const RelayTimelinePanel = ({
  relayTimelineSteps,
  isTimelineExpanded,
  turnRetryPending,
  finalResponderName,
  highlightedGroupIndex,
  pendingJumpGroupIndex,
  onToggleTimeline,
  onJumpToRelayStep,
  showRelaySummary,
  participantCount,
  inspectedStep,
  isExpanded,
  hiddenRelayCount,
  onToggleTurnExpanded,
}: RelayTimelinePanelProps) => {
  const { t } = useI18n();

  const relayTimelineCompletedCount = relayTimelineSteps.filter((step) => step.state === 'done').length;
  const relayTimelineActiveCount = relayTimelineSteps.filter((step) => step.state === 'active').length;
  const relayTimelineWaitingCount = relayTimelineSteps.filter((step) => step.state === 'waiting').length;
  const relayTimelineFailedCount = relayTimelineSteps.filter((step) => step.state === 'error').length;
  const activeRelayStep = relayTimelineSteps.find((step) => step.state === 'active');
  const waitingRelayStep = relayTimelineSteps.find((step) => step.state === 'waiting');
  const batonHeadline = activeRelayStep
    ? t('chat.timelineHeadlineActive', { label: activeRelayStep.label })
    : waitingRelayStep
      ? t('chat.timelineHeadlineWaiting', { label: waitingRelayStep.label })
      : finalResponderName
        ? t('chat.timelineHeadlineFinal', { name: finalResponderName })
        : t('chat.timelineHeadlineDone');
  const batonDetail = activeRelayStep
    ? activeRelayStep.detail
    : waitingRelayStep
      ? waitingRelayStep.detail
      : relayTimelineFailedCount > 0
        ? t('chat.timelineDetailFailed')
        : t('chat.timelineDetailIdle');

  const relayStateLabel = (state: RelayTimelineStep['state']) => {
    switch (state) {
      case 'active':
        return t('chat.statusActive');
      case 'waiting':
        return t('chat.statusWaiting');
      case 'error':
        return t('chat.statusFailed');
      default:
        return t('chat.statusDone');
    }
  };

  return (
    <>
      {relayTimelineSteps.length > 0 && (
        <div className="mb-4 rounded-3xl border border-slate-200 bg-slate-50/80 px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
              <span className="inline-flex items-center rounded-full bg-white px-2.5 py-1 font-semibold text-slate-700 shadow-sm">
                {t('chat.timelineTitle')}
              </span>
              <span>{t('chat.timelineHint')}</span>
            </div>
            <IconButton
              label={isTimelineExpanded ? t('chat.timelineCollapse') : t('chat.timelineExpand')}
              dataTestId="chat-turn-timeline-toggle"
              onClick={onToggleTimeline}
              icon={isTimelineExpanded
                ? <ChevronsUp className="h-4 w-4" strokeWidth={2} />
                : <ChevronsDown className="h-4 w-4" strokeWidth={2} />}
            />
          </div>
          {!isTimelineExpanded ? (
            <div
              className="mt-3 space-y-3"
              data-testid="chat-turn-timeline"
              data-collapsed="true"
            >
              <div className={`rounded-2xl border px-3 py-3 shadow-sm ${
                activeRelayStep
                  ? 'border-sky-200 bg-sky-50/90'
                  : waitingRelayStep
                    ? 'border-amber-200 bg-amber-50/90'
                    : relayTimelineFailedCount > 0
                      ? (turnRetryPending ? 'border-amber-200 bg-amber-50/90' : 'border-red-200 bg-red-50/90')
                      : 'border-emerald-200 bg-emerald-50/90'
              }`}>
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="inline-flex items-center rounded-full bg-white px-2.5 py-1 font-semibold text-slate-700 shadow-sm">
                    {t('chat.liveBaton')}
                  </span>
                  <span className={`inline-flex items-center rounded-full px-2.5 py-1 font-medium ${
                    activeRelayStep
                      ? 'bg-sky-100 text-sky-700'
                      : waitingRelayStep
                        ? 'bg-amber-100 text-amber-700'
                        : relayTimelineFailedCount > 0
                          ? (turnRetryPending ? 'bg-amber-100 text-amber-800' : 'bg-red-100 text-red-700')
                          : 'bg-emerald-100 text-emerald-700'
                  }`}>
                    {activeRelayStep
                      ? t('chat.statusActive')
                      : waitingRelayStep
                        ? t('chat.statusWaiting')
                        : relayTimelineFailedCount > 0
                          ? (turnRetryPending ? t('chat.timelineRetryPending') : t('chat.timelineHasFailure'))
                          : t('chat.statusDone')}
                  </span>
                  <span className="inline-flex items-center rounded-full bg-white/80 px-2.5 py-1 font-medium text-slate-600">
                    {t('chat.totalBatons', { count: relayTimelineSteps.length })}
                  </span>
                  {activeRelayStep && waitingRelayStep && (
                    <span className="inline-flex items-center rounded-full bg-white/80 px-2.5 py-1 font-medium text-slate-600">
                      {t('chat.nextBaton', { label: waitingRelayStep.label })}
                    </span>
                  )}
                </div>
                <p className="mt-2 text-sm font-semibold text-slate-800">
                  {batonHeadline}
                </p>
                <p className="mt-1 text-xs leading-5 text-slate-600">
                  {batonDetail}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {relayTimelineSteps.map((step, timelineIdx) => (
                  <button
                    key={`${step.key}:collapsed`}
                    type="button"
                    title={t('chat.jumpToBaton', { index: timelineIdx + 1, label: step.label })}
                    aria-label={t('chat.jumpToBaton', { index: timelineIdx + 1, label: step.label })}
                    onClick={() => onJumpToRelayStep(step.groupIndex)}
                    className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-medium shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md ${
                      step.state === 'error'
                        ? 'border-red-200 bg-red-50 text-red-700'
                        : step.state === 'active'
                          ? 'border-sky-200 bg-sky-50 text-sky-700'
                          : step.state === 'waiting'
                            ? 'border-amber-200 bg-amber-50 text-amber-700'
                            : 'border-emerald-200 bg-emerald-50 text-emerald-700'
                    }`}
                  >
                    <span className={`inline-block h-2 w-2 rounded-full ${
                      step.state === 'error'
                        ? 'bg-red-500'
                        : step.state === 'active'
                          ? 'animate-pulse bg-sky-500'
                          : step.state === 'waiting'
                            ? 'bg-amber-500'
                            : 'bg-emerald-500'
                    }`} />
                    <span>{t('chat.batonLabel', { index: timelineIdx + 1 })}</span>
                    <span className="max-w-[14rem] truncate">{step.label}</span>
                  </button>
                ))}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {relayTimelineCompletedCount > 0 && (
                  <span className="inline-flex items-center rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-700">
                    {t('chat.completedCount', { count: relayTimelineCompletedCount })}
                  </span>
                )}
                {relayTimelineActiveCount > 0 && (
                  <span className="inline-flex items-center rounded-full bg-sky-100 px-2.5 py-1 text-xs font-medium text-sky-700">
                    {t('chat.activeCount', { count: relayTimelineActiveCount })}
                  </span>
                )}
                {relayTimelineWaitingCount > 0 && (
                  <span className="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-700">
                    {t('chat.waitingCount', { count: relayTimelineWaitingCount })}
                  </span>
                )}
                {relayTimelineFailedCount > 0 && (
                  <span className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-1 text-xs font-medium text-red-700">
                    {t('chat.failedCount', { count: relayTimelineFailedCount })}
                  </span>
                )}
                {finalResponderName && (
                  <span className="text-xs text-slate-500">
                    {t('chat.finalOutput', { name: finalResponderName })}
                  </span>
                )}
              </div>
            </div>
          ) : (
            <div
              className="mt-3 flex flex-wrap items-center gap-2"
              data-testid="chat-turn-timeline"
            >
              {relayTimelineSteps.map((step, timelineIdx) => {
                const isStepActive = highlightedGroupIndex === step.groupIndex
                  || pendingJumpGroupIndex === step.groupIndex;

                return (
                  <div key={step.key} className="contents">
                    <button
                      type="button"
                      data-testid="chat-turn-timeline-step"
                      title={t('chat.jumpToBaton', { index: timelineIdx + 1, label: step.label })}
                      aria-label={t('chat.jumpToBaton', { index: timelineIdx + 1, label: step.label })}
                      onClick={() => onJumpToRelayStep(step.groupIndex)}
                      className={`min-w-[144px] max-w-[220px] rounded-2xl border px-3 py-2 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md ${
                        step.state === 'error'
                          ? 'border-red-200 bg-red-50'
                          : step.state === 'active'
                            ? 'border-sky-200 bg-sky-50'
                            : step.state === 'waiting'
                              ? 'border-amber-200 bg-amber-50'
                              : 'border-emerald-200 bg-emerald-50'
                      } ${
                        isStepActive
                          ? 'ring-2 ring-sky-300 ring-offset-2 -translate-y-0.5 shadow-md'
                          : 'hover:ring-1 hover:ring-slate-300'
                      }`}
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-semibold text-slate-700">
                          {t('chat.batonLabel', { index: timelineIdx + 1 })}
                        </span>
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${
                            step.state === 'error'
                              ? 'bg-red-100 text-red-700'
                              : step.state === 'active'
                                ? 'bg-sky-100 text-sky-700'
                                : step.state === 'waiting'
                                  ? 'bg-amber-100 text-amber-700'
                                  : 'bg-emerald-100 text-emerald-700'
                          }`}
                        >
                          {step.state === 'error'
                            ? t('chat.statusFailed')
                            : step.state === 'active'
                              ? t('chat.statusActive')
                              : step.state === 'waiting'
                                ? t('chat.statusWaiting')
                                : t('chat.statusDone')}
                        </span>
                        {step.isFinal && (
                          <span className="inline-flex items-center rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600">
                            {t('chat.finalOutputBadge')}
                          </span>
                        )}
                      </div>
                      <p className="mt-2 text-sm font-medium text-slate-800">
                        {step.label}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {step.detail}
                      </p>
                    </button>
                    {timelineIdx < relayTimelineSteps.length - 1 && (
                      <div className="hidden h-px w-6 bg-slate-300 md:block" />
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {showRelaySummary && (
        <div className="mb-4 rounded-3xl border border-violet-200 bg-violet-50/70 px-4 py-3 transition-all hover:border-violet-300 hover:bg-violet-50 hover:shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2 text-xs text-violet-700">
                <span className="inline-flex items-center rounded-full bg-white px-2.5 py-1 font-semibold text-violet-700 shadow-sm">
                  {t('chat.relaySummaryTitle')}
                </span>
                {finalResponderName && (
                  <span>{t('chat.finalReply', { name: finalResponderName })}</span>
                )}
                <span>{t('chat.participantCount', { count: participantCount })}</span>
                {inspectedStep && (
                  <span className="inline-flex items-center rounded-full bg-sky-100 px-2.5 py-1 font-medium text-sky-700 ring-1 ring-sky-200">
                    {t('chat.inspectingStep', { index: inspectedStep.groupIndex + 1 })}
                  </span>
                )}
              </div>
              <p className="text-sm text-slate-600">
                {inspectedStep
                  ? t('chat.inspectedStepDetail', {
                      index: inspectedStep.groupIndex + 1,
                      label: inspectedStep.label,
                      state: relayStateLabel(inspectedStep.state),
                    })
                  : isExpanded
                    ? t('chat.relayExpandedDetail')
                    : hiddenRelayCount > 0
                      ? t('chat.relayCollapsedDetail', { count: hiddenRelayCount })
                      : t('chat.relayAllVisible')}
              </p>
            </div>
            <IconButton
              label={isExpanded ? t('chat.collapseRelayProcess') : t('chat.expandRelayProcess')}
              dataTestId="chat-turn-toggle"
              onClick={onToggleTurnExpanded}
              tone="violet"
              icon={isExpanded
                ? <FoldVertical className="h-4 w-4" strokeWidth={2} />
                : <UnfoldVertical className="h-4 w-4" strokeWidth={2} />}
            />
          </div>
        </div>
      )}
    </>
  );
};

export default RelayTimelinePanel;
