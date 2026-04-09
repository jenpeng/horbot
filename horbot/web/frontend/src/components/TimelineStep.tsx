import React, { useState } from 'react';

export interface TopicSegment {
  topic: string;
  start_idx: number;
  end_idx: number;
  message_count: number;
  summary: string;
}

export interface StepDetails {
  toolName?: string;
  arguments?: Record<string, unknown>;
  result?: string;
  executionTime?: number;
  thinking?: string;
  content?: string;
  originalTokens?: number;
  compressedTokens?: number;
  reductionPercent?: number;
  topics?: TopicSegment[];
}

export interface ExecutionStep {
  id: string;
  type: 'thinking' | 'tool_call' | 'response' | 'message' | 'compression';
  title: string;
  status: 'pending' | 'running' | 'completed' | 'skipped' | 'failed' | 'stopped' | 'error' | 'success';
  details?: StepDetails;
  timestamp: string;
  isCollapsed?: boolean;
}

interface TimelineStepProps {
  step: ExecutionStep;
  isLast?: boolean;
  isCurrent?: boolean;
}

const TimelineStep: React.FC<TimelineStepProps> = ({ step, isLast = false, isCurrent = false }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const statusIcons = {
    pending: (
      <div className="w-5 h-5 rounded-full border-2 border-surface-400 bg-surface-100 flex items-center justify-center">
        <div className="w-2 h-2 rounded-full bg-surface-400" />
      </div>
    ),
    running: (
      <div className="w-5 h-5 rounded-full bg-primary-500 flex items-center justify-center shadow-lg shadow-primary-500/30">
        <svg className="w-3 h-3 text-white animate-spin" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
      </div>
    ),
    completed: (
      <div className="w-5 h-5 rounded-full bg-semantic-success flex items-center justify-center shadow-md shadow-semantic-success/20">
        <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
        </svg>
      </div>
    ),
    success: (
      <div className="w-5 h-5 rounded-full bg-semantic-success flex items-center justify-center shadow-md shadow-semantic-success/20">
        <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
        </svg>
      </div>
    ),
    skipped: (
      <div className="w-5 h-5 rounded-full border-2 border-surface-400 bg-surface-100 flex items-center justify-center">
        <svg className="w-3 h-3 text-surface-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
        </svg>
      </div>
    ),
    failed: (
      <div className="w-5 h-5 rounded-full bg-semantic-error flex items-center justify-center shadow-md shadow-semantic-error/20">
        <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </div>
    ),
    error: (
      <div className="w-5 h-5 rounded-full bg-semantic-error flex items-center justify-center shadow-md shadow-semantic-error/20">
        <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </div>
    ),
    stopped: (
      <div className="w-5 h-5 rounded-full bg-semantic-warning flex items-center justify-center shadow-md shadow-semantic-warning/20">
        <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
        </svg>
      </div>
    ),
  };

  const typeIcons = {
    thinking: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
    ),
    tool_call: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
    response: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    ),
    message: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
      </svg>
    ),
    compression: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
      </svg>
    ),
  };

  const hasDetails = step.details && (
    step.details.toolName ||
    step.details.arguments ||
    step.details.result ||
    step.details.thinking ||
    step.details.content ||
    step.details.originalTokens !== undefined ||
    (step.details.topics && step.details.topics.length > 0)
  );

  const executionTime = step.details?.executionTime;

  const getStatusColor = () => {
    switch (step.status) {
      case 'error':
      case 'failed':
        return 'text-semantic-error';
      case 'stopped':
        return 'text-semantic-warning';
      case 'success':
      case 'completed':
        return 'text-semantic-success';
      case 'running':
        return 'text-primary-600';
      default:
        return 'text-surface-600';
    }
  };

  const getBgColor = () => {
    if (isCurrent && step.status === 'running') {
      return 'bg-primary-50 border-l-2 border-primary-500';
    }
    return '';
  };

  return (
    <div className={`relative flex items-start gap-3 py-2 px-3 rounded-lg transition-all ${getBgColor()}`}>
      {/* Timeline line */}
      {!isLast && (
        <div className="absolute left-[22px] top-9 w-0.5 h-[calc(100%-20px)] bg-gradient-to-b from-surface-300 to-surface-200" />
      )}

      {/* Status icon */}
      <div className="relative z-10 flex-shrink-0 flex items-center justify-center">
        {statusIcons[step.status]}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div
          className={`flex items-center gap-2 text-sm cursor-pointer group transition-all ${
            getStatusColor()
          } ${step.status === 'running' ? 'animate-pulse' : ''}`}
          onClick={() => hasDetails && setIsExpanded(!isExpanded)}
        >
          <span className={`${step.status === 'running' ? 'text-primary-600' : 'text-surface-500'}`}>
            {typeIcons[step.type]}
          </span>
          <span className={`truncate font-medium ${step.status === 'running' ? 'text-surface-900' : ''}`}>
            {step.title}
          </span>
          {executionTime !== undefined && executionTime > 0 && (
            <span className="text-xs text-surface-500 ml-auto font-mono">{executionTime.toFixed(2)}s</span>
          )}
          {hasDetails && (
            <svg
              className={`w-4 h-4 text-surface-400 transition-transform group-hover:text-surface-600 ${isExpanded ? 'rotate-180' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          )}
        </div>

        {/* Expanded details */}
        {isExpanded && step.details && (
          <div className="mt-2 p-3 rounded-lg bg-surface-100 border border-surface-200 text-xs space-y-2">
            {step.details.thinking && (
              <div>
                <span className="text-surface-600 font-medium">思考过程:</span>
                <pre className="mt-1 p-2 rounded bg-white text-surface-700 overflow-x-auto whitespace-pre-wrap border border-surface-200">
                  {step.details.thinking}
                </pre>
              </div>
            )}

            {step.details.toolName && (
              <div className="flex items-center gap-2">
                <span className="text-surface-600 font-medium">工具:</span>
                <span className="font-mono text-primary-600 bg-primary-50 px-2 py-0.5 rounded">{step.details.toolName}</span>
              </div>
            )}

            {step.details.arguments && Object.keys(step.details.arguments).length > 0 && (
              <div>
                <span className="text-surface-600 font-medium">参数:</span>
                <pre className="mt-1 p-2 rounded bg-white text-surface-600 overflow-x-auto border border-surface-200">
                  {JSON.stringify(step.details.arguments, null, 2)}
                </pre>
              </div>
            )}

            {step.details.result && (
              <div>
                <span className="text-surface-600 font-medium">结果:</span>
                <pre className={`mt-1 p-2 rounded overflow-x-auto max-h-32 border ${step.status === 'failed' 
                    ? 'bg-semantic-error-light text-semantic-error border-semantic-error/30' 
                    : 'bg-white text-surface-600 border-surface-200'
                }`}>
                  {step.details.result.length > 300
                    ? step.details.result.slice(0, 300) + '...'
                    : step.details.result}
                </pre>
              </div>
            )}

            {step.details.content && (
              <div>
                <span className="text-surface-600 font-medium">消息内容:</span>
                <pre className="mt-1 p-2 rounded bg-white text-surface-700 overflow-x-auto whitespace-pre-wrap border border-surface-200">
                  {step.details.content.length > 500
                    ? step.details.content.slice(0, 500) + '...'
                    : step.details.content}
                </pre>
              </div>
            )}

            {step.details.originalTokens !== undefined && step.details.compressedTokens !== undefined && (
              <div className="space-y-1">
                <div className="flex items-center gap-4">
                  <span className="text-surface-600 font-medium">原始 Token:</span>
                  <span className="font-mono text-surface-700">{step.details.originalTokens.toLocaleString()}</span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-surface-600 font-medium">压缩后 Token:</span>
                  <span className="font-mono text-semantic-success">{step.details.compressedTokens.toLocaleString()}</span>
                </div>
                {step.details.reductionPercent !== undefined && (
                  <div className="flex items-center gap-4">
                    <span className="text-surface-600 font-medium">节省比例:</span>
                    <span className="font-mono text-primary-600 bg-primary-50 px-2 py-0.5 rounded">
                      {step.details.reductionPercent.toFixed(1)}%
                    </span>
                  </div>
                )}
              </div>
            )}

            {step.details.topics && step.details.topics.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-surface-600 font-medium">话题分段:</span>
                  <span className="text-xs text-surface-500">({step.details.topics.length} 个话题)</span>
                </div>
                <div className="space-y-1">
                  {step.details.topics.map((topic, idx) => (
                    <div key={idx} className="flex items-center gap-2 p-2 rounded bg-white border border-surface-200">
                      <span className="text-xs font-mono text-surface-400">#{idx + 1}</span>
                      <span className="px-2 py-0.5 rounded text-xs font-medium bg-primary-50 text-primary-700">
                        {topic.topic.toUpperCase()}
                      </span>
                      <span className="text-xs text-surface-500">
                        {topic.message_count} 条消息
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default TimelineStep;
