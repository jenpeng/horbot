import React, { memo } from 'react';
import MarkdownRenderer from './MarkdownRenderer';
import ConfirmationButtons from './ConfirmationButtons';
import InlineExecutionTimeline from './InlineExecutionTimeline';
import ExecutionPlan from './ExecutionPlan';
import type { ExecutionStep } from './TimelineStep';
import type { Plan } from './ExecutionPlan';

export interface UploadedFile {
  file_id: string;
  filename: string;
  original_name: string;
  mime_type: string;
  size: number;
  category: string;
  url: string;
  preview_url?: string;
}

export interface ChatMessageProps {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
  isStreaming?: boolean;
  confirmationId?: string;
  toolName?: string;
  toolArguments?: Record<string, unknown>;
  confirmationHandled?: boolean;
  executionSteps?: ExecutionStep[];
  plan?: Plan;
  isLoadingPlan?: boolean;
  isLast?: boolean;
  copiedMessageId?: string | null;
  confirmingMessageId?: string | null;
  editingMessageId?: string | null;
  editContent?: string;
  files?: UploadedFile[];
  agent_id?: string;
  agents?: AgentInfo[];
  onCopy: (messageId: string, content: string) => void;
  onEdit: (messageId: string, content: string) => void;
  onSaveEdit: (messageId: string) => void;
  onCancelEdit: () => void;
  onSetEditContent: (content: string) => void;
  onConfirm: (confirmationId: string) => void;
  onCancel: (confirmationId: string) => void;
  onRegenerate?: (messageId: string) => void;
  onPlanConfirmed?: (plan: Plan) => void;
  onPlanCancelled?: (plan: Plan) => void;
  formatTime: (timestamp?: string) => string;
  searchQuery?: string;
}

interface AgentInfo {
  id: string;
  name: string;
  description: string;
  model: string;
  provider: string;
  capabilities: string[];
  teams: string[];
  is_main: boolean;
}

// Agent 头像颜色映射
const getAgentColor = (agentId: string): { bg: string; border: string; text: string; borderAccent: string } => {
  const colors = [
    { bg: 'bg-gradient-to-br from-purple-400 to-purple-600', border: 'border-purple-200', text: 'text-white', borderAccent: 'border-l-purple-500' },
    { bg: 'bg-gradient-to-br from-emerald-400 to-emerald-600', border: 'border-emerald-200', text: 'text-white', borderAccent: 'border-l-emerald-500' },
    { bg: 'bg-gradient-to-br from-orange-400 to-orange-600', border: 'border-orange-200', text: 'text-white', borderAccent: 'border-l-orange-500' },
    { bg: 'bg-gradient-to-br from-cyan-400 to-cyan-600', border: 'border-cyan-200', text: 'text-white', borderAccent: 'border-l-cyan-500' },
    { bg: 'bg-gradient-to-br from-pink-400 to-pink-600', border: 'border-pink-200', text: 'text-white', borderAccent: 'border-l-pink-500' },
    { bg: 'bg-gradient-to-br from-indigo-400 to-indigo-600', border: 'border-indigo-200', text: 'text-white', borderAccent: 'border-l-indigo-500' },
  ];
  
  const index = Math.abs(agentId.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)) % colors.length;
  return colors[index];
};

const ChatMessage: React.FC<ChatMessageProps> = memo(({
  id,
  role,
  content,
  timestamp,
  isStreaming,
  confirmationId,
  toolName,
  toolArguments,
  confirmationHandled,
  executionSteps,
  plan,
  isLoadingPlan,
  isLast,
  copiedMessageId,
  confirmingMessageId,
  editingMessageId,
  editContent,
  files,
  agent_id,
  agents = [],
  onCopy,
  onEdit,
  onSaveEdit,
  onCancelEdit,
  onSetEditContent,
  onConfirm,
  onCancel,
  onRegenerate,
  onPlanConfirmed,
  onPlanCancelled,
  formatTime,
  searchQuery,
}) => {
  const highlightText = (text: string, query: string) => {
    if (!query) return text;
    
    const parts = text.split(new RegExp(`(${query})`, 'gi'));
    return parts.map((part, i) => 
      part.toLowerCase() === query.toLowerCase() 
        ? <mark key={i} className="bg-primary-300 text-surface-900 px-0.5 rounded">{part}</mark>
        : part
    );
  };

  const getFileIcon = (category: string) => {
    switch (category) {
      case 'image':
        return (
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        );
      case 'video':
        return (
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
        );
      case 'audio':
        return (
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
          </svg>
        );
      case 'document':
        return (
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        );
      default:
        return (
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
          </svg>
        );
    }
  };

  const renderFilePreview = (file: UploadedFile) => {
    if (file.category === 'image') {
      return (
        <div className="relative group">
          <img 
            src={file.url} 
            alt={file.original_name}
            className="w-20 h-20 object-cover rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
            onClick={() => window.open(file.url, '_blank')}
          />
          <div className="absolute bottom-1 right-1 bg-black/50 text-white text-xs px-1.5 py-0.5 rounded">
            {file.size > 1024 * 1024 
              ? `${(file.size / (1024 * 1024)).toFixed(1)}MB` 
              : `${(file.size / 1024).toFixed(0)}KB`}
          </div>
        </div>
      );
    }
    
    return (
      <div className="flex items-center gap-2 bg-white/10 rounded-lg p-2 min-w-[140px]">
        <div className="w-10 h-10 flex items-center justify-center bg-white/20 rounded">
          {getFileIcon(file.category)}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs text-white truncate">{file.original_name}</p>
          <p className="text-xs text-white/70">
            {file.size > 1024 * 1024 
              ? `${(file.size / (1024 * 1024)).toFixed(1)}MB` 
              : `${(file.size / 1024).toFixed(0)}KB`}
          </p>
        </div>
      </div>
    );
  };

  if (role === 'user') {
    return (
      <div className="flex justify-end max-w-[85%] md:max-w-[70%] ml-auto group">
        <div className="flex flex-col items-end">
          {editingMessageId === id ? (
            <div className="bg-white rounded-2xl p-4 border border-surface-300 shadow-lg">
              <textarea
                value={editContent}
                onChange={(e) => onSetEditContent(e.target.value)}
                className="w-full bg-surface-50 border border-surface-300 rounded-xl px-4 py-3 text-surface-900 focus:outline-none focus:ring-2 focus:ring-primary-500/50 resize-none placeholder-surface-500"
                rows={3}
                placeholder="编辑您的消息..."
              />
              <div className="flex justify-end gap-3 mt-3">
                <button
                  onClick={onCancelEdit}
                  className="px-4 py-2 text-sm text-surface-600 hover:text-surface-900 transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={() => onSaveEdit(id)}
                  className="px-4 py-2 text-sm bg-gradient-to-r from-primary-500 to-primary-600 hover:from-primary-600 hover:to-primary-700 text-white rounded-xl transition-all shadow-sm"
                >
                  保存并发送
                </button>
              </div>
            </div>
          ) : (
            <div className="relative">
              <div className="relative bg-gradient-to-br from-primary-500 to-primary-600 rounded-[16px_16px_4px_16px] shadow-sm overflow-hidden">
                {/* 文件预览 */}
                {files && files.length > 0 && (
                  <div className="flex flex-wrap gap-2 p-3 pb-0">
                    {files.map((file) => (
                      <div key={file.file_id}>
                        {renderFilePreview(file)}
                      </div>
                    ))}
                  </div>
                )}
                {/* 消息文本 */}
                <div className="px-5 py-3.5">
                  <p className="text-white whitespace-pre-wrap leading-relaxed">{searchQuery ? highlightText(content, searchQuery) : content}</p>
                </div>
              </div>
            </div>
          )}
          {timestamp && !editingMessageId && (
            <div className="flex items-center justify-end gap-2 mt-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
              <span className="text-xs text-surface-500">{formatTime(timestamp)}</span>
              <button
                onClick={() => onCopy(id, content)}
                className="text-xs text-surface-500 hover:text-surface-700 px-2 py-1 rounded-lg hover:bg-surface-200 transition-colors flex items-center gap-1"
                title="复制"
              >
                {copiedMessageId === id ? (
                  <>
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5 text-semantic-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <span className="text-semantic-success">已复制</span>
                  </>
                ) : (
                  <>
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    <span>复制</span>
                  </>
                )}
              </button>
              <button
                onClick={() => onEdit(id, content)}
                className="text-xs text-surface-500 hover:text-surface-700 px-2 py-1 rounded-lg hover:bg-surface-200 transition-colors flex items-center gap-1"
                title="编辑"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
                <span>编辑</span>
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  // 获取当前 Agent 信息
  const currentAgent = agent_id ? agents.find(a => a.id === agent_id) : null;
  const agentColor = currentAgent ? getAgentColor(currentAgent.id) : null;
  
  return (
    <div className="flex gap-3 max-w-[85%] md:max-w-[70%]">
      <div className="flex-shrink-0">
        <div className="relative">
          {currentAgent ? (
            <div className={`w-9 h-9 rounded-xl shadow-md flex items-center justify-center ${agentColor?.bg} ${agentColor?.text} font-semibold text-sm`}>
              {currentAgent.name.charAt(0).toUpperCase()}
            </div>
          ) : (
            <img 
              src="/logo.png" 
              alt="Logo" 
              className="w-9 h-9 rounded-xl shadow-md object-cover"
            />
          )}
          <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-semantic-success rounded-full border-2 border-white" />
        </div>
      </div>
      <div className="flex-1 min-w-0 relative group">
        {/* Agent 名称标签 */}
        {currentAgent && (
          <div className="flex items-center gap-2 mb-1.5">
            <span className={`text-sm font-semibold ${agentColor?.borderAccent.replace('border-l-', 'text-')}`}>
              {currentAgent.name}
            </span>
            {timestamp && (
              <span className="text-xs text-surface-400">{formatTime(timestamp)}</span>
            )}
          </div>
        )}
        
        {isLoadingPlan && !plan && (
          <div className="mb-4 px-5 py-4 rounded-2xl bg-white border border-surface-200 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
                <svg className="w-5 h-5 text-primary-600 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
              </div>
              <div>
                <div className="text-sm font-medium text-surface-900">正在分析任务并生成执行计划...</div>
                <div className="text-xs text-surface-500 mt-0.5">请稍候，AI 正在思考最佳执行方案</div>
              </div>
            </div>
          </div>
        )}

        {plan && (
          <ExecutionPlan 
            plan={plan}
            onConfirmed={onPlanConfirmed}
            onCancelled={onPlanCancelled}
          />
        )}

        {executionSteps && executionSteps.length > 0 && (
          <InlineExecutionTimeline steps={executionSteps} />
        )}

        <div className={`bg-surface-50 rounded-[16px_16px_16px_4px] px-5 py-4 break-words shadow-sm border-l-4 ${agentColor?.borderAccent || 'border-l-transparent'}`}>
          <div className="prose max-w-none break-words word-wrap
            prose-headings:text-surface-900
            prose-h1:text-2xl prose-h1:font-bold prose-h1:mb-4 prose-h1:mt-6 prose-h1:pb-2 prose-h1:border-b prose-h1:border-surface-300
            prose-h2:text-xl prose-h2:font-semibold prose-h2:mb-3 prose-h2:mt-5
            prose-h3:text-lg prose-h3:font-medium prose-h3:mb-2 prose-h3:mt-4
            prose-p:text-surface-900 prose-p:leading-relaxed prose-p:mb-4 prose-p:break-words
            prose-a:text-primary-600 prose-a:no-underline hover:prose-a:text-primary-700 hover:prose-a:underline
            prose-strong:text-surface-900 prose-strong:font-semibold
            prose-em:text-surface-700
            prose-ul:text-surface-900 prose-ul:my-3 prose-li:my-1
            prose-ol:text-surface-900 prose-ol:my-3
            prose-blockquote:border-l-4 prose-blockquote:border-primary-500 prose-blockquote:bg-white prose-blockquote:py-1 prose-blockquote:px-4 prose-blockquote:my-4 prose-blockquote:rounded-r prose-blockquote:not-italic prose-blockquote:text-surface-700
            prose-hr:border-surface-300 prose-hr:my-6
            prose-table:overflow-hidden prose-table:rounded-xl prose-table:border prose-table:border-surface-300
            prose-th:bg-white prose-th:text-surface-900 prose-th:font-semibold prose-th:px-4 prose-th:py-2 prose-th:text-left prose-th:border prose-th:border-surface-300
            prose-td:text-surface-700 prose-td:px-4 prose-td:py-2 prose-td:border prose-td:border-surface-300
            prose-img:rounded-xl prose-img:max-w-full
          ">
            <MarkdownRenderer content={content} />
          </div>
          {isStreaming && (
            <span className="inline-block w-2 h-5 bg-primary-500 rounded-full animate-pulse ml-1" />
          )}
        </div>
        {confirmationId && !confirmationHandled && (
          <ConfirmationButtons
            confirmationId={confirmationId}
            toolName={toolName || 'unknown'}
            toolArguments={toolArguments || {}}
            onConfirm={onConfirm}
            onCancel={onCancel}
            disabled={confirmingMessageId === confirmationId}
          />
        )}
        {!isStreaming && (
          <div className="flex items-center justify-between mt-1.5 opacity-0 group-hover:opacity-100 transition-all duration-200">
            {!currentAgent && timestamp && (
              <div className="text-xs text-surface-500">
                {formatTime(timestamp)}
              </div>
            )}
            {content && !confirmationId && (
              <div className="flex items-center gap-1">
                <button
                  onClick={() => onCopy(id, content)}
                  className="text-xs text-surface-500 hover:text-surface-700 px-3 py-1.5 rounded-lg hover:bg-surface-100 transition-all flex items-center gap-1.5 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
                  title="复制"
                  aria-label="复制消息"
                >
                  {copiedMessageId === id ? (
                    <>
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-semantic-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      <span className="text-semantic-success">已复制</span>
                    </>
                  ) : (
                    <>
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                      <span>复制</span>
                    </>
                  )}
                </button>
                {isLast && onRegenerate && (
                  <button
                    onClick={() => onRegenerate(id)}
                    className="text-xs text-surface-500 hover:text-surface-700 px-3 py-1.5 rounded-lg hover:bg-surface-100 transition-all flex items-center gap-1.5 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
                    title="重新生成此回复"
                    aria-label="重新生成回复"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    <span>重新生成</span>
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
});

ChatMessage.displayName = 'ChatMessage';

export default ChatMessage;
