import { useEffect, useRef } from 'react';
import { Copy, ListChecks, PencilLine, Search, X } from 'lucide-react';

type TranslateFn = (key: string, values?: Record<string, string | number>) => string;

interface ConversationWorkbench {
  latestRequest: string;
  stage: string;
  activeAgents: string[];
  fileCount: number;
  executionSteps: number;
  runningSteps: number;
  failedSteps: number;
  toolNames: string[];
}

interface WorkbenchQuickAction {
  id: string;
  label: string;
  prompt: string;
}

interface TaskWorkbenchPopoverProps {
  t: TranslateFn;
  isOpen: boolean;
  isLoading: boolean;
  turnCount: number;
  workbench: ConversationWorkbench;
  quickActions: WorkbenchQuickAction[];
  onToggle: () => void;
  onClose: () => void;
  onUseSummary: () => void;
  onSearchRequest: () => void;
  onCopySummary: () => void;
  onApplyQuickAction: (prompt: string) => void;
}

const TaskWorkbenchPopover = ({
  t,
  isOpen,
  isLoading,
  turnCount,
  workbench,
  quickActions,
  onToggle,
  onClose,
  onUseSummary,
  onSearchRequest,
  onCopySummary,
  onApplyQuickAction,
}: TaskWorkbenchPopoverProps) => {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      const root = rootRef.current;
      if (!root || root.contains(event.target as Node)) {
        return;
      }
      onClose();
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('pointerdown', handlePointerDown);
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        onClick={onToggle}
        className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium shadow-sm transition-colors ${
          isOpen
            ? 'border-sky-200 bg-white text-sky-700'
            : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
        }`}
        data-testid="chat-workbench-trigger"
      >
        <ListChecks className="h-3.5 w-3.5" strokeWidth={2} />
        {t('chat.workbenchTitle')}
      </button>
      {isOpen && (
        <div
          className="absolute right-0 top-full z-20 mt-2 w-[min(92vw,34rem)] rounded-2xl border border-slate-200 bg-white/95 p-3 shadow-xl backdrop-blur"
          data-testid="chat-workbench-panel"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${
                  workbench.failedSteps > 0
                    ? 'bg-red-100 text-red-700'
                    : workbench.runningSteps > 0 || isLoading
                      ? 'bg-sky-100 text-sky-700'
                      : 'bg-emerald-100 text-emerald-700'
                }`}>
                  {workbench.stage}
                </span>
                <span className="text-xs text-slate-500">
                  {t('chat.workbenchTurns', { count: turnCount })} · {t('chat.workbenchFiles', { count: workbench.fileCount })} · {t('chat.workbenchSteps', { count: workbench.executionSteps })}
                </span>
              </div>
              <p className="mt-2 line-clamp-2 text-sm font-medium text-slate-800">
                {t('chat.workbenchLatestRequest', { preview: workbench.latestRequest })}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
              aria-label={t('chat.workbenchCollapse')}
            >
              <X className="h-4 w-4" strokeWidth={2} />
            </button>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onUseSummary}
              className="inline-flex items-center gap-1 rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700 shadow-sm transition-colors hover:bg-sky-100"
            >
              <PencilLine className="h-3.5 w-3.5" strokeWidth={2} />
              {t('chat.workbenchUseSummary')}
            </button>
            <button
              type="button"
              onClick={onSearchRequest}
              className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50"
            >
              <Search className="h-3.5 w-3.5" strokeWidth={2} />
              {t('chat.workbenchSearchRequest')}
            </button>
            <button
              type="button"
              onClick={onCopySummary}
              className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50"
            >
              <Copy className="h-3.5 w-3.5" strokeWidth={2} />
              {t('chat.workbenchCopySummary')}
            </button>
            {quickActions.map((action) => (
              <button
                key={action.id}
                type="button"
                onClick={() => onApplyQuickAction(action.prompt)}
                className="inline-flex items-center rounded-full border border-sky-200 bg-white px-2.5 py-1 text-xs font-semibold text-sky-700 transition hover:bg-sky-50"
              >
                {action.label}
              </button>
            ))}
          </div>
          {(workbench.activeAgents.length > 0 || workbench.toolNames.length > 0) && (
            <div className="mt-3 flex max-w-full flex-wrap gap-2">
              {workbench.activeAgents.slice(0, 4).map((name) => (
                <span key={name} className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600">
                  {name}
                </span>
              ))}
              {workbench.toolNames.slice(0, 4).map((name) => (
                <span key={name} className="rounded-full border border-indigo-100 bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700">
                  {name}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default TaskWorkbenchPopover;
