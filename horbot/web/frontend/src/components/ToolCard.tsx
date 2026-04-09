import React, { useState } from 'react';

interface ToolCardProps {
  toolName: string;
  arguments: Record<string, unknown>;
  status: 'loading' | 'success' | 'error';
  result?: string;
  executionTime?: number;
}

const toolIcons: Record<string, string> = {
  read_file: '📄',
  write_file: '✏️',
  edit_file: '📝',
  list_dir: '📁',
  exec: '⚡',
  web_search: '🔍',
  web_fetch: '🌐',
  default: '🔧',
};

const ToolCard: React.FC<ToolCardProps> = ({
  toolName,
  arguments: args,
  status,
  result,
  executionTime,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const icon = toolIcons[toolName] || toolIcons.default;
  
  const statusColors = {
    loading: 'border-blue-500 bg-blue-500/10',
    success: 'border-green-500 bg-green-500/10',
    error: 'border-red-500 bg-red-500/10',
  };

  const statusIcons = {
    loading: (
      <svg className="animate-spin h-4 w-4 text-blue-400" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
      </svg>
    ),
    success: (
      <svg className="h-4 w-4 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      </svg>
    ),
    error: (
      <svg className="h-4 w-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      </svg>
    ),
  };

  return (
    <div className={`rounded-lg border ${statusColors[status]} mb-2 overflow-hidden`}>
      <div 
        className="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-secondary-700/50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">{icon}</span>
          <span className="font-mono text-sm font-medium text-gray-200">{toolName}</span>
          {status === 'loading' && (
            <span className="text-xs text-blue-400 ml-2">执行中...</span>
          )}
          {status === 'success' && executionTime && (
            <span className="text-xs text-gray-500 ml-2">{executionTime.toFixed(2)}s</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {statusIcons[status]}
          <svg 
            className={`h-4 w-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} 
            fill="none" 
            viewBox="0 0 24 24" 
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
      
      {isExpanded && (
        <div className="px-3 py-2 border-t border-secondary-700 bg-secondary-800/50">
          <div className="mb-2">
            <p className="text-xs text-gray-500 mb-1">参数:</p>
            <pre className="text-xs text-gray-300 bg-secondary-900/50 rounded p-2 overflow-x-auto">
              {JSON.stringify(args, null, 2)}
            </pre>
          </div>
          
          {result && (
            <div>
              <p className="text-xs text-gray-500 mb-1">结果:</p>
              <pre className={`text-xs rounded p-2 overflow-x-auto max-h-40 ${
                status === 'error' ? 'text-red-300 bg-red-900/20' : 'text-gray-300 bg-secondary-900/50'
              }`}>
                {result.length > 500 ? result.slice(0, 500) + '...' : result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ToolCard;
