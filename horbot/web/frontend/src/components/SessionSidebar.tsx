import React, { useState, useEffect, useCallback, memo } from 'react';
import { chatService } from '../services';
import ConfirmDialog from './ConfirmDialog';
import type { Session } from '../types';

interface SessionSidebarProps {
  currentSessionKey: string;
  onSelectSession: (sessionKey: string) => void;
  onNewSession: () => void;
  onClose?: () => void;
}

const SessionSidebar: React.FC<SessionSidebarProps> = ({ 
  currentSessionKey, 
  onSelectSession, 
  onNewSession,
  onClose
}) => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingSession, setEditingSession] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState<{ isOpen: boolean; sessionKey: string; sessionTitle: string }>({
    isOpen: false,
    sessionKey: '',
    sessionTitle: '',
  });

  const loadSessions = useCallback(async (): Promise<Session[]> => {
    try {
      const response = await chatService.getSessions();
      const sessionsList = response.sessions || [];
      setSessions(sessionsList);
      return sessionsList;
    } catch (error) {
      console.error('Error loading sessions:', error);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const handleCreateSession = useCallback(async () => {
    try {
      await chatService.createSession();
      await loadSessions();
      onNewSession();
    } catch (error) {
      console.error('Error creating session:', error);
    }
  }, [loadSessions, onNewSession]);

  const handleDeleteSession = (session: Session, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteConfirm({
      isOpen: true,
      sessionKey: session.key,
      sessionTitle: session.title,
    });
  };
  
  const confirmDeleteSession = useCallback(async () => {
    const sessionKey = deleteConfirm.sessionKey;
    setDeleteConfirm({ isOpen: false, sessionKey: '', sessionTitle: '' });
    
    try {
      await chatService.deleteSession(sessionKey);
      const updatedSessions = await loadSessions();
      if (sessionKey === currentSessionKey) {
        if (updatedSessions.length > 0) {
          onSelectSession(updatedSessions[0].key);
        } else {
          handleCreateSession();
        }
      }
    } catch (error) {
      console.error('Error deleting session:', error);
    }
  }, [deleteConfirm.sessionKey, currentSessionKey, loadSessions, onSelectSession, handleCreateSession]);

  const handleStartEdit = (session: Session, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingSession(session.key);
    setEditTitle(session.title);
  };

  const handleSaveEdit = useCallback(async (sessionKey: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!editTitle.trim()) return;
    
    try {
      await chatService.updateSessionTitle(sessionKey, editTitle.trim());
      setEditingSession(null);
      await loadSessions();
    } catch (error) {
      console.error('Error updating session title:', error);
    }
  }, [editTitle, loadSessions]);

  const handleCancelEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingSession(null);
  };

  const formatTime = (timestamp: string) => {
    if (!timestamp) return '';
    
    // Parse timestamp - handle ISO strings and numeric timestamps
    let date: Date;
    
    // Check if it's a pure numeric string (Unix timestamp)
    if (/^\d+$/.test(timestamp)) {
      const numValue = parseInt(timestamp);
      // 10 digits = seconds (Unix timestamp)
      // 13 digits = milliseconds
      if (timestamp.length <= 10) {
        date = new Date(numValue * 1000);
      } else {
        date = new Date(numValue);
      }
    } else {
      // It's an ISO string or other format
      date = new Date(timestamp);
    }
    
    // Check if date is valid
    if (isNaN(date.getTime())) {
      return '';
    }
    
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    
    // Handle future dates
    if (diffMs < 0) {
      return '';
    }
    
    const diffHours = diffMs / (1000 * 60 * 60);
    
    if (diffHours < 1) {
      const diffMins = Math.floor(diffMs / (1000 * 60));
      if (diffMins < 1) {
        return '刚刚';
      }
      return `${diffMins}分钟前`;
    } else if (diffHours < 24) {
      return `${Math.floor(diffHours)}小时前`;
    } else if (diffHours < 24 * 30) {
      const diffDays = Math.floor(diffHours / 24);
      return `${diffDays}天前`;
    } else if (diffHours < 24 * 365) {
      const diffMonths = Math.floor(diffHours / (24 * 30));
      return `${diffMonths}个月前`;
    } else {
      const diffYears = Math.floor(diffHours / (24 * 365));
      return `${diffYears}年前`;
    }
  };

  const totalMessages = sessions.reduce((sum, session) => sum + (session.message_count || 0), 0);

  return (
    <div className="w-[280px] md:w-[280px] bg-white border-r border-surface-300 h-full flex flex-col shadow-2xl md:shadow-none">
      <div className="p-4 md:p-5 border-b border-surface-300">
        <div className="flex justify-between items-center">
          <div>
            <h3 className="font-semibold text-surface-900 text-lg">历史记录</h3>
            <p className="text-xs text-surface-500 mt-0.5">{sessions.length} 个对话</p>
          </div>
          <div className="flex items-center gap-2">
            {onClose && (
              <button
                onClick={onClose}
                className="md:hidden p-2 text-surface-500 hover:text-surface-700 rounded-xl hover:bg-surface-100 transition-colors"
                aria-label="关闭菜单"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
            <button
              onClick={handleCreateSession}
              aria-label="新建对话"
              className="flex items-center gap-2 bg-gradient-to-r from-primary-500 to-accent-purple hover:from-primary-600 hover:to-accent-purple/90 text-white px-4 py-2 rounded-xl transition-all shadow-sm hover:shadow-md hover:scale-105 active:scale-95 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              <span className="text-sm font-medium">新建</span>
            </button>
          </div>
        </div>
      </div>
      
      <div className="flex-1 overflow-y-auto p-3">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-12">
            <div className="flex gap-2">
              {[0, 1, 2].map((i) => (
                <div 
                  key={i} 
                  className="w-2 h-2 bg-primary-500 rounded-full animate-bounce" 
                  style={{ animationDelay: `${i * 150}ms` }}
                ></div>
              ))}
            </div>
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="w-16 h-16 rounded-2xl bg-surface-100 flex items-center justify-center mb-4">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <p className="text-surface-600 mb-3">暂无对话</p>
            <button
              onClick={handleCreateSession}
              className="text-sm text-primary-600 hover:text-primary-700 transition-colors font-medium"
            >
              开始第一次对话
            </button>
          </div>
        ) : (
          <div className="space-y-1.5">
            {sessions.map((session) => (
              <div
                key={session.key}
                onClick={() => onSelectSession(session.key)}
                className={`p-3.5 rounded-xl transition-all duration-200 cursor-pointer group ${
                  currentSessionKey === session.key 
                    ? 'bg-gradient-to-r from-primary-50 to-accent-purple/5 border border-primary-200' 
                    : 'hover:bg-surface-50 border border-transparent'
                }`}
              >
                <div className="flex justify-between items-start">
                  {editingSession === session.key ? (
                    <div className="flex-1">
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onClick={(e) => e.stopPropagation()}
                        className="w-full bg-white border border-surface-300 rounded-xl px-3 py-2 text-sm text-surface-900 mb-2 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
                        autoFocus
                      />
                      <div className="flex space-x-2 text-xs">
                        <button
                          onClick={(e) => handleSaveEdit(session.key, e)}
                          className="px-3 py-1.5 bg-primary-500 hover:bg-primary-600 text-white rounded-lg transition-colors font-medium"
                        >
                          保存
                        </button>
                        <button
                          onClick={(e) => handleCancelEdit(e)}
                          className="px-3 py-1.5 bg-surface-200 hover:bg-surface-300 text-surface-700 rounded-lg transition-colors"
                        >
                          取消
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start">
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-surface-900 truncate text-sm">{session.title}</p>
                          <p className="text-xs text-surface-500 mt-1 flex items-center gap-2">
                            <span className="flex items-center gap-1">
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                              </svg>
                              {session.message_count}
                            </span>
                            <span>·</span>
                            <span>{formatTime(session.created_at)}</span>
                          </p>
                        </div>
                        <div className="flex space-x-0.5 ml-2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={(e) => handleStartEdit(session, e)}
                            className="text-surface-400 hover:text-surface-700 p-1.5 rounded-lg hover:bg-surface-100 transition-colors"
                            title="重命名"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                          <button
                            onClick={(e) => handleDeleteSession(session, e)}
                            className="text-surface-400 hover:text-semantic-error p-1.5 rounded-lg hover:bg-red-50 transition-colors"
                            title="删除"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      
      <ConfirmDialog
        isOpen={deleteConfirm.isOpen}
        title="删除对话"
        message={`确定要删除对话"${deleteConfirm.sessionTitle}"吗？此操作无法撤销。`}
        confirmText="删除"
        cancelText="取消"
        onConfirm={confirmDeleteSession}
        onCancel={() => setDeleteConfirm({ isOpen: false, sessionKey: '', sessionTitle: '' })}
        variant="danger"
      />
      
      <div className="p-4 border-t border-surface-300 bg-surface-50">
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-2 text-surface-600">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <span>共 {totalMessages} 条消息</span>
          </div>
          <div className="flex items-center gap-2 text-surface-600">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            <span>{sessions.length} 个会话</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default memo(SessionSidebar);