import React, { memo } from 'react';
import TimelineStep from './TimelineStep';
import type { ExecutionStep } from './TimelineStep';

interface ExecutionTimelineProps {
  steps: ExecutionStep[];
  isVisible: boolean;
}

const ExecutionTimeline: React.FC<ExecutionTimelineProps> = memo(({ steps, isVisible }) => {
  if (!isVisible || steps.length === 0) {
    return null;
  }

  return (
    <div className="w-72 flex-shrink-0 bg-surface-900 border-r border-surface-700 overflow-y-auto">
      <div className="p-4">
        <h3 className="text-sm font-semibold text-surface-300 mb-4 flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          执行步骤
        </h3>
        <div className="space-y-0">
          {steps.map((step, index) => (
            <TimelineStep
              key={step.id}
              step={step}
              isLast={index === steps.length - 1}
            />
          ))}
        </div>
      </div>
    </div>
  );
});

ExecutionTimeline.displayName = 'ExecutionTimeline';

export default ExecutionTimeline;
