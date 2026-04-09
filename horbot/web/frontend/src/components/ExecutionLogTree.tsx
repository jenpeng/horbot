import React, { useState } from 'react';

export interface LogEntry {
  timestamp: number;
  type: 'thinking' | 'tool_call' | 'tool_result' | 'completion';
  content: string;
  metadata?: {
    tool_name?: string;
    arguments?: any;
    result?: string;
    error?: string;
  };
}

export interface StepExecutionLog {
  stepId: string;
  stepTitle: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  executionTime: number;
  logs: LogEntry[];
}

interface ExecutionLogTreeProps {
  logs: StepExecutionLog[];
  totalSteps?: number;
  completedSteps?: number;
}

const ExecutionLogTree: React.FC<ExecutionLogTreeProps> = ({ 
  logs
}) => {
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());
  const [expandedLogTypes, setExpandedLogTypes] = useState<Set<string>>(new Set());

  const toggleStep = (stepId: string) => {
    const newExpanded = new Set(expandedSteps);
    if (newExpanded.has(stepId)) {
      newExpanded.delete(stepId);
    } else {
      newExpanded.add(stepId);
    }
    setExpandedSteps(newExpanded);
  };

  const toggleLogType = (key: string) => {
    const newExpanded = new Set(expandedLogTypes);
    if (newExpanded.has(key)) {
      newExpanded.delete(key);
    } else {
      newExpanded.add(key);
    }
    setExpandedLogTypes(newExpanded);
  };

  const formatTime = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleTimeString();
  };

  const formatDuration = (seconds: number) => {
    if (seconds < 1) {
      return `${(seconds * 1000).toFixed(0)}ms`;
    }
    return `${seconds.toFixed(2)}s`;
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <span className="text-green-400">✓</span>;
      case 'failed':
        return <span className="text-red-400">✗</span>;
      case 'running':
        return <span className="text-blue-400 animate-pulse">▶</span>;
      default:
        return <span className="text-gray-400">○</span>;
    }
  };

  const getLogTypeIcon = (type: string) => {
    switch (type) {
      case 'thinking':
        return <span className="text-yellow-400">💭</span>;
      case 'tool_call':
        return <span className="text-blue-400">🔧</span>;
      case 'tool_result':
        return <span className="text-green-400">📄</span>;
      case 'completion':
        return <span className="text-purple-400">✓</span>;
      default:
        return <span className="text-gray-400">•</span>;
    }
  };

  const getLogTypeLabel = (type: string) => {
    switch (type) {
      case 'thinking':
        return '思考';
      case 'tool_call':
        return '工具调用';
      case 'tool_result':
        return '工具结果';
      case 'completion':
        return '完成';
      default:
        return type;
    }
  };

  // Group logs by type for each step
  const groupLogsByType = (logs: LogEntry[]) => {
    const groups: { [key: string]: LogEntry[] } = {};
    logs.forEach(log => {
      if (!groups[log.type]) {
        groups[log.type] = [];
      }
      groups[log.type].push(log);
    });
    return groups;
  };

  return (
    <div className="execution-log-tree">
      {/* Steps */}
      <div className="space-y-2">
        {logs.map((stepLog, index) => {
          const isExpanded = expandedSteps.has(stepLog.stepId);
          const logGroups = groupLogsByType(stepLog.logs);

          return (
            <div 
              key={stepLog.stepId} 
              className="step-item border border-gray-700 rounded-lg overflow-hidden"
            >
              {/* Step Header */}
              <button
                onClick={() => toggleStep(stepLog.stepId)}
                className="w-full flex items-center gap-3 p-3 bg-gray-800 hover:bg-gray-750 transition-colors text-left"
              >
                <span className="flex-shrink-0">
                  {getStatusIcon(stepLog.status)}
                </span>
                <span className="flex-shrink-0 text-xs text-gray-500 w-6">
                  {index + 1}
                </span>
                <span className="flex-1 text-sm text-gray-200 truncate">
                  {stepLog.stepTitle}
                </span>
                <span className="text-xs text-gray-500">
                  {formatDuration(stepLog.executionTime)}
                </span>
                <span className="text-xs text-gray-400">
                  {isExpanded ? '▼' : '▶'}
                </span>
              </button>

              {/* Step Details */}
              {isExpanded && (
                <div className="step-details bg-gray-850 p-3 space-y-2">
                  {Object.entries(logGroups).map(([logType, typeLogs]) => {
                    const groupKey = `${stepLog.stepId}-${logType}`;
                    const isGroupExpanded = expandedLogTypes.has(groupKey);

                    return (
                      <div 
                        key={logType} 
                        className="log-group border-l-2 border-gray-600 pl-3"
                      >
                        <button
                          onClick={() => toggleLogType(groupKey)}
                          className="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-300"
                        >
                          {getLogTypeIcon(logType)}
                          <span>{getLogTypeLabel(logType)}</span>
                          <span className="text-gray-500">({typeLogs.length})</span>
                          <span>{isGroupExpanded ? '▼' : '▶'}</span>
                        </button>

                        {isGroupExpanded && (
                          <div className="mt-2 space-y-1">
                            {typeLogs.map((log, logIndex) => (
                              <div 
                                key={logIndex}
                                className="log-entry text-xs bg-gray-800 rounded p-2"
                              >
                                <div className="flex items-center gap-2 text-gray-500 mb-1">
                                  <span>{formatTime(log.timestamp)}</span>
                                </div>
                                <div className="text-gray-300 whitespace-pre-wrap">
                                  {log.content}
                                </div>
                                {log.metadata && (
                                  <div className="mt-2 p-2 bg-gray-900 rounded text-gray-400">
                                    {log.metadata.tool_name && (
                                      <div className="mb-1">
                                        <span className="text-gray-500">工具: </span>
                                        <span className="text-blue-400">{log.metadata.tool_name}</span>
                                      </div>
                                    )}
                                    {log.metadata.arguments && (
                                      <div className="mb-1">
                                        <span className="text-gray-500">参数: </span>
                                        <pre className="mt-1 p-1 bg-gray-800 rounded text-xs overflow-x-auto">
                                          {JSON.stringify(log.metadata.arguments, null, 2)}
                                        </pre>
                                      </div>
                                    )}
                                    {log.metadata.result && (
                                      <div>
                                        <span className="text-gray-500">结果: </span>
                                        <pre className="mt-1 p-1 bg-gray-800 rounded text-xs overflow-x-auto max-h-32 overflow-y-auto">
                                          {log.metadata.result}
                                        </pre>
                                      </div>
                                    )}
                                    {log.metadata.error && (
                                      <div className="text-red-400">
                                        <span className="text-gray-500">错误: </span>
                                        {log.metadata.error}
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}

                  {stepLog.logs.length === 0 && (
                    <div className="text-xs text-gray-500 italic">
                      暂无执行日志
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {logs.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          等待执行...
        </div>
      )}
    </div>
  );
};

export default ExecutionLogTree;
