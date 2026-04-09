import React, { useState, useEffect, useCallback } from 'react';

interface SubagentInfo {
  id: string;
  label: string;
  task: string;
  status: string;
  started_at: number;
  running_seconds: number;
  session_key: string | null;
  origin: {
    channel: string;
    chat_id: string;
  };
}

interface SubagentMonitorProps {
  sessionKey?: string;
  onSubagentChange?: () => void;
}

const SubagentMonitor: React.FC<SubagentMonitorProps> = ({ sessionKey, onSubagentChange }) => {
  const [subagents, setSubagents] = useState<SubagentInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [isExpanded, setIsExpanded] = useState(true);

  const fetchSubagents = useCallback(async () => {
    try {
      const url = sessionKey 
        ? `/api/subagents?session_key=${encodeURIComponent(sessionKey)}`
        : '/api/subagents';
      const response = await fetch(url);
      if (response.ok) {
        const data = await response.json();
        setSubagents(data.subagents || []);
      }
    } catch (error) {
      console.error('Failed to fetch subagents:', error);
    }
  }, [sessionKey]);

  useEffect(() => {
    fetchSubagents();
    const interval = setInterval(fetchSubagents, 5000);
    return () => clearInterval(interval);
  }, [fetchSubagents]);

  const cancelSubagent = async (taskId: string) => {
    setLoading(true);
    try {
      const response = await fetch(`/api/subagents/${taskId}/cancel`, {
        method: 'POST',
      });
      if (response.ok) {
        await fetchSubagents();
        onSubagentChange?.();
      }
    } catch (error) {
      console.error('Failed to cancel subagent:', error);
    } finally {
      setLoading(false);
    }
  };

  const cancelAllSubagents = async () => {
    setLoading(true);
    try {
      const url = sessionKey
        ? `/api/subagents/cancel-all?session_key=${encodeURIComponent(sessionKey)}`
        : '/api/subagents/cancel-all';
      const response = await fetch(url, {
        method: 'POST',
      });
      if (response.ok) {
        await fetchSubagents();
        onSubagentChange?.();
      }
    } catch (error) {
      console.error('Failed to cancel all subagents:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatRunningTime = (seconds: number): string => {
    if (seconds < 60) {
      return `${Math.floor(seconds)}秒`;
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60);
      const secs = Math.floor(seconds % 60);
      return `${minutes}分${secs}秒`;
    } else {
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      return `${hours}小时${minutes}分`;
    }
  };

  if (subagents.length === 0) {
    return null;
  }

  return (
    <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg mb-4">
      <div 
        className="flex items-center justify-between p-3 cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          <span className="text-yellow-600 dark:text-yellow-400">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </span>
          <span className="font-medium text-yellow-800 dark:text-yellow-200">
            子代理监控 ({subagents.length} 个运行中)
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              cancelAllSubagents();
            }}
            disabled={loading}
            className="px-3 py-1 text-sm bg-red-500 hover:bg-red-600 text-white rounded disabled:opacity-50"
          >
            终止所有
          </button>
          <svg 
            className={`w-5 h-5 text-yellow-600 dark:text-yellow-400 transform transition-transform ${isExpanded ? 'rotate-180' : ''}`}
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
      
      {isExpanded && (
        <div className="border-t border-yellow-200 dark:border-yellow-800 p-3">
          <div className="space-y-2">
            {subagents.map((subagent) => (
              <div 
                key={subagent.id}
                className="flex items-center justify-between bg-white dark:bg-gray-800 rounded p-3 border border-yellow-100 dark:border-yellow-900"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                      {subagent.status}
                    </span>
                    <span className="font-medium text-gray-900 dark:text-gray-100 truncate">
                      {subagent.label}
                    </span>
                  </div>
                  <div className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    <span className="font-mono text-xs">ID: {subagent.id}</span>
                    <span className="mx-2">•</span>
                    <span>运行时间: {formatRunningTime(subagent.running_seconds)}</span>
                  </div>
                  <div className="mt-1 text-xs text-gray-400 dark:text-gray-500 truncate">
                    任务: {subagent.task}
                  </div>
                </div>
                <button
                  onClick={() => cancelSubagent(subagent.id)}
                  disabled={loading}
                  className="ml-3 px-3 py-1.5 text-sm bg-red-500 hover:bg-red-600 text-white rounded disabled:opacity-50 flex items-center gap-1"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  终止
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default SubagentMonitor;
