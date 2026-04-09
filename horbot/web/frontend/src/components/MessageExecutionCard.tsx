import React, { memo, useEffect, useMemo, useState } from 'react';
import {
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  LoaderCircle,
  Sparkles,
  Terminal,
  Wrench,
} from 'lucide-react';
import type { ExecutionStep } from '../types/conversation';
import { getStorageItem, setStorageItem } from '../utils/storage';

interface MessageExecutionCardProps {
  steps?: ExecutionStep[];
  isStreaming?: boolean;
}

type ExecutionFilter = 'all' | 'tool' | 'thinking' | 'response';
const EXECUTION_FILTER_STORAGE_KEY = 'horbot.execution-card-filter';

const summarizeText = (value: unknown, maxLength: number = 180): string => {
  if (value === null || value === undefined) {
    return '';
  }

  const raw = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  const normalized = raw.replace(/\s+/g, ' ').trim();
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, Math.max(1, maxLength - 1))}…`;
};

const stringifyValue = (value: unknown): string => {
  if (value === null || value === undefined) {
    return '';
  }
  if (typeof value === 'string') {
    return value;
  }
  return JSON.stringify(value, null, 2);
};

const normalizeDetailText = (value: unknown): string => stringifyValue(value).trim();

const isTerminalTool = (step: ExecutionStep): boolean => {
  const toolName = String(step.details?.toolName || step.details?.tool_name || '').toLowerCase();
  return toolName === 'exec' || toolName === 'shell';
};

const extractTerminalCommand = (step: ExecutionStep): string => {
  const argumentsPayload = step.details?.arguments as Record<string, unknown> | undefined;
  const command = argumentsPayload?.command;
  return typeof command === 'string' ? command.trim() : '';
};

const extractTerminalOutput = (step: ExecutionStep): string => {
  const result = step.details?.result;
  return stringifyValue(result).trim();
};

const getStepTone = (step: ExecutionStep): string => {
  if (step.status === 'error' || step.status === 'failed') {
    return 'border-red-200 bg-red-50 text-red-800';
  }
  if (step.status === 'running' || step.status === 'pending') {
    return 'border-sky-200 bg-sky-50 text-sky-800';
  }
  return 'border-slate-200 bg-white text-slate-700';
};

const getStepIcon = (step: ExecutionStep) => {
  const normalizedType = (step.type || '').toLowerCase();
  if (step.status === 'error' || step.status === 'failed') {
    return <CircleAlert className="h-4 w-4 text-red-500" strokeWidth={2} />;
  }
  if (step.status === 'running' || step.status === 'pending') {
    return <LoaderCircle className="h-4 w-4 animate-spin text-sky-500" strokeWidth={2} />;
  }
  if (normalizedType.includes('thinking')) {
    return <Brain className="h-4 w-4 text-amber-500" strokeWidth={2} />;
  }
  if (normalizedType.includes('tool')) {
    return <Wrench className="h-4 w-4 text-indigo-500" strokeWidth={2} />;
  }
  if (normalizedType.includes('response')) {
    return <Sparkles className="h-4 w-4 text-emerald-500" strokeWidth={2} />;
  }
  return <CheckCircle2 className="h-4 w-4 text-emerald-500" strokeWidth={2} />;
};

const getStepLabel = (step: ExecutionStep): string => {
  const normalizedType = (step.type || '').toLowerCase();
  if (normalizedType.includes('thinking')) {
    return '思考';
  }
  if (normalizedType.includes('tool')) {
    return '工具';
  }
  if (normalizedType.includes('response')) {
    return '回复';
  }
  if (normalizedType.includes('compression')) {
    return '压缩';
  }
  return step.type || '步骤';
};

const getStepFilter = (step: ExecutionStep): ExecutionFilter => {
  const normalizedType = (step.type || '').toLowerCase();
  if (normalizedType.includes('tool')) {
    return 'tool';
  }
  if (normalizedType.includes('thinking')) {
    return 'thinking';
  }
  if (normalizedType.includes('response')) {
    return 'response';
  }
  return 'all';
};

const isThinkingStep = (step: ExecutionStep): boolean => (
  (step.type || '').toLowerCase().includes('thinking')
);

const FILTER_LABELS: Record<ExecutionFilter, string> = {
  all: '全部',
  tool: '工具',
  thinking: '思考',
  response: '回复',
};

const MessageExecutionCard: React.FC<MessageExecutionCardProps> = ({
  steps = [],
  isStreaming = false,
}) => {
  const [expanded, setExpanded] = useState<boolean>(false);
  const [filter, setFilter] = useState<ExecutionFilter>(() => (
    getStorageItem<ExecutionFilter>(EXECUTION_FILTER_STORAGE_KEY, 'all')
  ));

  const summary = useMemo(() => {
    const running = steps.filter((step) => step.status === 'running' || step.status === 'pending').length;
    const failed = steps.filter((step) => step.status === 'error' || step.status === 'failed').length;
    const toolSteps = steps.filter((step) => (step.type || '').toLowerCase().includes('tool')).length;
    const toolNames = Array.from(new Set(
      steps
        .map((step) => String(step.details?.toolName || step.details?.tool_name || '').trim())
        .filter(Boolean),
    ));
    return { running, failed, toolSteps, toolNames };
  }, [steps]);

  const handleExpandedToggle = () => {
    setExpanded((prev) => !prev);
  };

  const availableFilters = useMemo<ExecutionFilter[]>(() => {
    const filters = new Set<ExecutionFilter>(['all']);
    steps.forEach((step) => {
      const stepFilter = getStepFilter(step);
      if (stepFilter !== 'all') {
        filters.add(stepFilter);
      }
    });
    return ['all', 'tool', 'thinking', 'response'].filter((item) => filters.has(item as ExecutionFilter)) as ExecutionFilter[];
  }, [steps]);

  useEffect(() => {
    if (!availableFilters.includes(filter)) {
      setFilter(summary.toolSteps > 0 ? 'tool' : 'all');
    }
  }, [availableFilters, filter, summary.toolSteps]);

  useEffect(() => {
    setStorageItem(EXECUTION_FILTER_STORAGE_KEY, filter);
  }, [filter]);

  const visibleSteps = useMemo(
    () => (filter === 'all' ? steps : steps.filter((step) => getStepFilter(step) === filter)),
    [filter, steps],
  );

  if (steps.length === 0) {
    return null;
  }

  return (
    <div className="mt-0.5 rounded-2xl border border-slate-200/90 bg-slate-50/70 px-3 py-2 shadow-sm">
      <button
        type="button"
        onClick={handleExpandedToggle}
        className="flex w-full items-center justify-between gap-2 text-left"
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center rounded-full bg-white px-2.5 py-0.5 text-[11px] font-semibold text-slate-700 shadow-sm">
              执行过程
            </span>
            <span className="text-[11px] text-slate-500">
              {steps.length} 步
            </span>
            {summary.toolSteps > 0 && (
              <span className="inline-flex items-center rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-medium text-indigo-700">
                工具 {summary.toolSteps}
              </span>
            )}
            {summary.running > 0 && (
              <span className="inline-flex items-center rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-medium text-sky-700">
                进行中 {summary.running}
              </span>
            )}
            {summary.failed > 0 && (
              <span className="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-medium text-red-700">
                失败 {summary.failed}
              </span>
            )}
          </div>
          {summary.toolNames.length > 0 && (
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              {summary.toolNames.slice(0, 4).map((toolName) => (
                <span
                  key={toolName}
                  className="inline-flex items-center rounded-full border border-indigo-200 bg-white px-2 py-0.5 text-[10px] font-medium text-indigo-700"
                >
                  {toolName}
                </span>
              ))}
              {summary.toolNames.length > 4 && (
                <span className="text-[10px] text-slate-400">
                  +{summary.toolNames.length - 4}
                </span>
              )}
            </div>
          )}
          <p className="mt-0.5 text-[11px] text-slate-500">
            {expanded
              ? '已展开完整步骤与工具细节。'
              : (isStreaming || summary.running > 0
                  ? '默认已收起，点击查看执行过程。'
                  : '点击查看思考、工具调用与回复过程。')}
          </p>
        </div>
        <span className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-sm">
          {expanded ? <ChevronDown className="h-4 w-4" strokeWidth={2} /> : <ChevronRight className="h-4 w-4" strokeWidth={2} />}
        </span>
      </button>

      {expanded && (
        <div className="mt-2 space-y-1.5">
          {availableFilters.length > 1 && (
            <div className="flex flex-wrap items-center gap-1">
              {availableFilters.map((item) => (
                <button
                  key={item}
                  type="button"
                  data-testid={`execution-filter-${item}`}
                  onClick={() => setFilter(item)}
                  className={`inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-medium transition-colors ${
                    filter === item
                      ? 'bg-slate-900 text-white'
                      : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-100'
                  }`}
                >
                  {FILTER_LABELS[item]}
                </button>
              ))}
            </div>
          )}

          {visibleSteps.map((step) => {
            const detailToolName = summarizeText(step.details?.toolName || step.details?.tool_name, 64);
            const detailArguments = normalizeDetailText(step.details?.arguments);
            const detailResult = normalizeDetailText(step.details?.result);
            const detailReasoning = normalizeDetailText(
              step.details?.reasoning_content
              ?? step.details?.reasoning
              ?? step.details?.thinking,
            );
            const detailContent = normalizeDetailText(step.details?.content);
            const terminalCommand = extractTerminalCommand(step);
            const terminalOutput = extractTerminalOutput(step);
            const showTerminal = isTerminalTool(step) && (terminalCommand || terminalOutput);
            const isThinking = isThinkingStep(step);
            const showReasoning = !!detailReasoning;
            const showContent = !!detailContent && detailContent !== detailReasoning;
            const showArguments = !!detailArguments;
            const showResult = !!detailResult;

            return (
              <div
                key={step.id}
                className={`rounded-xl border px-3 py-2 ${getStepTone(step)}`}
              >
                <div className="flex flex-wrap items-start gap-2.5">
                  <div className="mt-0.5 flex h-7 w-7 items-center justify-center rounded-full bg-white/80 shadow-sm">
                    {getStepIcon(step)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[13px] font-semibold text-slate-800">
                        {step.title || getStepLabel(step)}
                      </span>
                      <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                        {getStepLabel(step)}
                      </span>
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${
                        step.status === 'error' || step.status === 'failed'
                          ? 'bg-red-100 text-red-700'
                          : step.status === 'running' || step.status === 'pending'
                            ? 'bg-sky-100 text-sky-700'
                            : 'bg-emerald-100 text-emerald-700'
                      }`}>
                        {step.status === 'error' || step.status === 'failed'
                          ? '失败'
                          : step.status === 'running' || step.status === 'pending'
                            ? '进行中'
                            : '完成'}
                      </span>
                      {detailToolName && (
                        <span className="inline-flex items-center rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-medium text-indigo-700">
                          {detailToolName}
                        </span>
                      )}
                    </div>

                    {showTerminal ? (
                      <div className="mt-2 overflow-hidden rounded-xl border border-slate-800 bg-slate-950 text-slate-100 shadow-inner">
                        <div className="flex items-center gap-2 border-b border-slate-800 px-3 py-2 text-[11px] text-slate-300">
                          <Terminal className="h-3.5 w-3.5" strokeWidth={2} />
                          <span>终端执行</span>
                        </div>
                        {terminalCommand && (
                          <div className="border-b border-slate-800 px-3 py-2 font-mono text-[11px] text-emerald-300">
                            $ {terminalCommand}
                          </div>
                        )}
                        {terminalOutput && (
                          <pre className="max-h-48 overflow-auto px-3 py-2 font-mono text-[11px] leading-5 text-slate-200 whitespace-pre-wrap break-words">
                            {terminalOutput}
                          </pre>
                        )}
                      </div>
                    ) : (showReasoning || showContent || showArguments || showResult) && (
                      <div className="mt-1.5 space-y-2 text-[11px] text-slate-600">
                        {showReasoning && (
                          <div className={`overflow-hidden rounded-xl border px-3 py-2 ${
                            isThinking
                              ? 'border-amber-200 bg-amber-50/90 text-amber-950'
                              : 'border-slate-200 bg-white text-slate-700'
                          }`}>
                            <div className="mb-1 text-[10px] font-semibold tracking-wide text-slate-500">
                              {isThinking ? '思考内容' : '阶段内容'}
                            </div>
                            <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words font-sans leading-5">
                              {detailReasoning}
                            </pre>
                          </div>
                        )}
                        {showContent && (
                          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-700">
                            <div className="mb-1 text-[10px] font-semibold tracking-wide text-slate-500">
                              阶段输出
                            </div>
                            <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words font-sans leading-5">
                              {detailContent}
                            </pre>
                          </div>
                        )}
                        {showArguments && (
                          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-700">
                            <div className="mb-1 text-[10px] font-semibold tracking-wide text-slate-500">
                              调用参数
                            </div>
                            <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words font-mono leading-5">
                              {detailArguments}
                            </pre>
                          </div>
                        )}
                        {showResult && (
                          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-700">
                            <div className="mb-1 text-[10px] font-semibold tracking-wide text-slate-500">
                              执行结果
                            </div>
                            <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words font-mono leading-5">
                              {detailResult}
                            </pre>
                          </div>
                        )}
                        {!showReasoning && isThinking && showContent && (
                          <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-800">
                            当前模型没有返回单独的 reasoning 字段，已展示该阶段可见输出。
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
          {visibleSteps.length === 0 && (
            <div className="rounded-xl border border-dashed border-slate-200 bg-white px-3 py-2 text-[11px] text-slate-500">
              当前筛选下没有步骤。
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default memo(MessageExecutionCard);
