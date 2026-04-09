import React, { useState, useMemo } from 'react';
import TimelineStep from './TimelineStep';
import type { ExecutionStep } from './TimelineStep';

interface InlineExecutionTimelineProps {
  steps: ExecutionStep[];
}

const InlineExecutionTimeline: React.FC<InlineExecutionTimelineProps> = ({ steps }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!steps || steps.length === 0) {
    return null;
  }

  // Calculate totals - include 'success' status for tool_call steps
  const completedCount = steps.filter(s => s.status === 'completed' || s.status === 'success' || s.status === 'failed').length;
  const isAllCompleted = completedCount === steps.length;
  const hasError = steps.some(s => s.status === 'failed');
  
  // Calculate total execution time
  const totalTime = useMemo(() => {
    return steps.reduce((acc, step) => {
      if (step.details?.executionTime) {
        return acc + step.details.executionTime;
      }
      return acc;
    }, 0);
  }, [steps]);

  // Find current running step
  const runningStepIndex = steps.findIndex(s => s.status === 'running');

  // Keep execution collapsed by default in both running and completed states.
  if (!isExpanded) {
    return (
      <div 
        className="mb-4 px-4 py-3 rounded-2xl bg-white border border-surface-200 shadow-sm cursor-pointer hover:shadow-md hover:border-surface-300 transition-all"
        onClick={() => setIsExpanded(true)}
      >
        <div className="flex items-center gap-3">
          {hasError ? (
            <div className="w-8 h-8 rounded-full bg-semantic-error-light flex items-center justify-center">
              <svg className="w-4 h-4 text-semantic-error" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          ) : (
            <div className="w-8 h-8 rounded-full bg-semantic-success-light flex items-center justify-center">
              <svg className="w-4 h-4 text-semantic-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          )}
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-surface-900">
                {!isAllCompleted
                  ? (runningStepIndex >= 0
                      ? `正在执行: ${steps[runningStepIndex].title}`
                      : `${completedCount}/${steps.length} 步骤`)
                  : (hasError ? `${completedCount} 步骤完成（有错误）` : `${completedCount} 步骤已完成`)}
              </span>
              {totalTime > 0 && isAllCompleted && (
                <span className="text-xs text-surface-500 font-mono">· {totalTime.toFixed(2)}s</span>
              )}
            </div>
            {!isAllCompleted && (
              <div className="mt-1.5 h-1.5 bg-surface-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-primary-500 to-primary-600 rounded-full transition-all duration-500"
                  style={{ width: `${(completedCount / steps.length) * 100}%` }}
                />
              </div>
            )}
            <div className="text-xs text-surface-500 mt-1">{!isAllCompleted ? '默认已收起，点击查看执行过程' : '点击查看详情'}</div>
          </div>
          <svg className="w-5 h-5 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
    );
  }

  // Running or expanded state
  return (
    <div className="mb-4 rounded-2xl bg-white border border-surface-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div 
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-surface-50 transition-colors border-b border-surface-100"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          {isAllCompleted ? (
            hasError ? (
              <div className="w-8 h-8 rounded-full bg-semantic-error-light flex items-center justify-center">
                <svg className="w-4 h-4 text-semantic-error" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            ) : (
              <div className="w-8 h-8 rounded-full bg-semantic-success-light flex items-center justify-center">
                <svg className="w-4 h-4 text-semantic-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            )
          ) : (
            <div className="w-8 h-8 rounded-full bg-primary-500 flex items-center justify-center shadow-lg shadow-primary-500/30">
              <svg className="w-4 h-4 text-white animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            </div>
          )}
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-surface-900">
                {runningStepIndex >= 0 
                  ? `正在执行: ${steps[runningStepIndex].title}`
                  : `${completedCount}/${steps.length} 步骤`}
              </span>
              {totalTime > 0 && isAllCompleted && (
                <span className="text-xs text-surface-500 font-mono">· {totalTime.toFixed(2)}s</span>
              )}
            </div>
            {!isAllCompleted && (
              <div className="mt-1.5 h-1.5 bg-surface-100 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-primary-500 to-primary-600 rounded-full transition-all duration-500"
                  style={{ width: `${(completedCount / steps.length) * 100}%` }}
                />
              </div>
            )}
          </div>
          <svg className={`w-5 h-5 text-surface-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {/* Steps */}
      {isExpanded && (
        <div className="px-3 py-3 bg-surface-50">
          <div className="space-y-1">
            {steps.map((step, index) => (
              <TimelineStep
                key={step.id}
                step={step}
                isLast={index === steps.length - 1}
                isCurrent={index === runningStepIndex}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default InlineExecutionTimeline;
