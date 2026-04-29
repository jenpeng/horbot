import type { ExecutionStep } from '../../types/conversation';
import type { TranslateFn } from './types';

export const normalizeExecutionStepStatus = (status?: string): ExecutionStep['status'] => {
  switch (status) {
    case 'running':
    case 'completed':
    case 'failed':
    case 'pending':
    case 'stopped':
    case 'skipped':
    case 'error':
    case 'success':
      return status;
    default:
      return 'completed';
  }
};

export const inferExecutionStepType = (
  fallbackType?: string,
  details?: Record<string, unknown>,
): string => {
  if (fallbackType) {
    return fallbackType;
  }
  if (details?.toolName || details?.tool_name) {
    return 'tool_call';
  }
  if (typeof details?.thinking === 'string') {
    return 'thinking';
  }
  if (typeof details?.content === 'string') {
    return 'response';
  }
  return 'step';
};

export const inferExecutionStepTitle = (
  t: TranslateFn,
  type?: string,
  title?: string,
  details?: Record<string, unknown>,
): string => {
  if (title) {
    return title;
  }

  const normalizedType = (type || '').toLowerCase();
  const toolName = typeof details?.toolName === 'string'
    ? details.toolName
    : (typeof details?.tool_name === 'string' ? details.tool_name : '');

  if (normalizedType.includes('tool') && toolName) {
    return t('chat.executionToolNamed', { name: toolName });
  }
  if (normalizedType.includes('thinking')) {
    return t('chat.executionThinking');
  }
  if (normalizedType.includes('response')) {
    return t('chat.executionResponding');
  }
  if (normalizedType.includes('compression')) {
    return t('chat.executionCompressing');
  }
  return t('chat.executionStep');
};

export const mergeExecutionSteps = (
  existingSteps: ExecutionStep[] = [],
  incomingSteps: ExecutionStep[] = [],
  fallbackTitle = 'Step',
): ExecutionStep[] => {
  if (incomingSteps.length === 0) {
    return existingSteps;
  }
  if (existingSteps.length === 0) {
    return incomingSteps;
  }

  const mergedSteps = [...existingSteps];
  const indexById = new Map<string, number>();
  mergedSteps.forEach((step, index) => {
    indexById.set(step.id, index);
  });

  incomingSteps.forEach((step) => {
    const existingIndex = indexById.get(step.id);
    if (existingIndex === undefined) {
      indexById.set(step.id, mergedSteps.length);
      mergedSteps.push(step);
      return;
    }

    const previous = mergedSteps[existingIndex];
    mergedSteps[existingIndex] = {
      ...previous,
      ...step,
      type: inferExecutionStepType(step.type || previous.type, step.details || previous.details),
      title: step.title || previous.title || fallbackTitle,
      status: normalizeExecutionStepStatus(step.status || previous.status),
      timestamp: previous.timestamp || step.timestamp,
      details: step.details ?? previous.details,
    };
  });

  return mergedSteps;
};

export const upsertExecutionStep = (
  steps: ExecutionStep[] = [],
  step: ExecutionStep,
  fallbackTitle = 'Step',
): ExecutionStep[] => mergeExecutionSteps(steps, [{
  ...step,
  type: inferExecutionStepType(step.type, step.details),
  title: step.title || fallbackTitle,
  status: normalizeExecutionStepStatus(step.status),
}], fallbackTitle);

export const updateLatestRunningExecutionStep = (
  steps: ExecutionStep[] = [],
  matcher: (step: ExecutionStep) => boolean,
  detailUpdates: Record<string, unknown>,
  nextStatus?: ExecutionStep['status'],
): ExecutionStep[] => {
  const nextSteps = [...steps];
  for (let index = nextSteps.length - 1; index >= 0; index -= 1) {
    const step = nextSteps[index];
    if ((step.status === 'running' || step.status === 'pending') && matcher(step)) {
      nextSteps[index] = {
        ...step,
        status: nextStatus ?? step.status,
        details: {
          ...(step.details || {}),
          ...detailUpdates,
        },
      };
      return nextSteps;
    }
  }
  return steps;
};

export const finalizeRunningExecutionSteps = (
  steps: ExecutionStep[] = [],
  status: ExecutionStep['status'],
  detailUpdates: Record<string, unknown> = {},
): ExecutionStep[] => steps.map((step) => {
  if (step.status !== 'running' && step.status !== 'pending') {
    return step;
  }
  return {
    ...step,
    status,
    details: {
      ...(step.details || {}),
      ...detailUpdates,
    },
  };
});
