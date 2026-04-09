import api, { getAdminAuthHeaders, resolveApiBase } from './api';
import type { Session, Message } from '../types/models';

export interface SessionListResponse {
  sessions: Session[];
}

export interface CreateSessionResponse {
  session_key: string;
}

export interface MessageHistoryResponse {
  messages: Message[];
}

export interface SendMessageParams {
  content: string;
  session_key: string;
}

export interface StreamEvent {
  event: string;
  type?: string;
  error?: string;
  turn_id?: string;
  message_id?: string;
  agent_index?: number;
  content?: string;
  step_id?: string;
  step_type?: string;
  title?: string;
  status?: string;
  details?: Record<string, unknown>;
  plan?: unknown;
  subtask_id?: string;
  result?: string;
  confirmation_id?: string;
  tool_name?: string;
  tool_arguments?: Record<string, unknown>;
  arguments?: Record<string, unknown>;
  execution_time?: number;
  tool_hint?: boolean;
  agent_id?: string;
  agent_name?: string;
  message?: string;
  [key: string]: unknown;
}

export type StreamState = 'connecting' | 'waiting' | 'receiving' | 'done' | 'error' | 'timeout';

export class ChatStreamError extends Error {
  code: 'aborted' | 'timeout' | 'http' | 'network';
  status?: number;

  constructor(
    message: string,
    code: 'aborted' | 'timeout' | 'http' | 'network',
    status?: number,
  ) {
    super(message);
    this.name = 'ChatStreamError';
    this.code = code;
    this.status = status;
  }
}

export interface StreamChatOptions {
  message: string;
  sessionKey?: string;
  fileIds?: string[];
  webSearch?: boolean;
  files?: UploadedFile[];
  agentId?: string;
  groupChat?: boolean;
  teamId?: string;
  mentionedAgents?: string[];
  conversationId?: string;
  conversationType?: string;
  onChunk: (event: StreamEvent) => void;
  onRequestStart?: (requestId: string) => void;
  onStateChange?: (state: StreamState) => void;
  timeout?: number;
  connectTimeout?: number;
  signal?: AbortSignal;
}

export interface UploadedFile {
  file_id: string;
  filename: string;
  original_name: string;
  mime_type: string;
  size: number;
  category: string;
  url: string;
  preview_url?: string;
  minimax_file_id?: string;
  extracted_text?: string;
}

const resolveFileUrl = (value?: string): string | undefined => {
  if (!value) {
    return undefined;
  }
  if (/^https?:\/\//i.test(value)) {
    return value;
  }
  const apiBase = resolveApiBase();
  if (!apiBase) {
    return value;
  }
  return `${apiBase}${value.startsWith('/') ? value : `/${value}`}`;
};

const normalizeUploadedFile = (file: UploadedFile): UploadedFile => ({
  ...file,
  url: resolveFileUrl(file.url) || file.url,
  preview_url: resolveFileUrl(file.preview_url),
});

export interface StopGenerationParams {
  request_id: string;
}

export interface ConfirmActionParams {
  confirmation_id: string;
  action: 'confirm' | 'cancel';
  session_key: string;
}

export const chatService = {
  getSessions: async (): Promise<SessionListResponse> => {
    const response = await api.get<SessionListResponse>('/api/chat/sessions');
    return response.data;
  },

  getSession: async (sessionKey: string): Promise<Session> => {
    const response = await api.get<Session>(`/api/chat/sessions/${sessionKey}`);
    return response.data;
  },

  createSession: async (data?: { title?: string }): Promise<CreateSessionResponse> => {
    const response = await api.post<CreateSessionResponse>('/api/chat/sessions', data);
    return response.data;
  },

  updateSession: async (sessionKey: string, data: { title?: string }): Promise<Session> => {
    const response = await api.put<Session>(`/api/chat/sessions/${sessionKey}`, data);
    return response.data;
  },

  deleteSession: async (sessionKey: string): Promise<void> => {
    await api.delete(`/api/chat/sessions/${sessionKey}`);
  },

  updateSessionTitle: async (sessionKey: string, title: string): Promise<Session> => {
    const response = await api.put<Session>(`/api/chat/sessions/${sessionKey}`, null, {
      params: { title },
    });
    return response.data;
  },

  getMessages: async (sessionKey: string, agentId?: string): Promise<MessageHistoryResponse> => {
    const params: Record<string, string> = { session_key: sessionKey };
    if (agentId) {
      params.agent_id = agentId;
    }
    const response = await api.get<MessageHistoryResponse>('/api/chat/history', {
      params,
    });
    return response.data;
  },

  sendMessage: async (params: SendMessageParams): Promise<Message> => {
    const response = await api.post<Message>('/api/chat/message', params);
    return response.data;
  },

  uploadFiles: async (files: File[]): Promise<UploadedFile[]> => {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
    });

    const response = await api.post<UploadedFile[]>('/api/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response.data.map(normalizeUploadedFile);
  },

  deleteUploadedFile: async (fileId: string): Promise<void> => {
    await api.delete(`/api/files/${fileId}`);
  },

  streamChat: async (options: StreamChatOptions): Promise<void> => {
    const { 
      message, 
      sessionKey, 
      fileIds, 
      webSearch, 
      files, 
      agentId, 
      groupChat, 
      teamId, 
      mentionedAgents, 
      conversationId,
      conversationType,
      onChunk, 
      onRequestStart, 
      onStateChange,
      timeout = 120000,
      connectTimeout = 15000,
      signal 
    } = options;

    onStateChange?.('connecting');

    const controller = new AbortController();
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    let timeoutReason: 'connect' | 'inactivity' | null = null;

    const clearStreamTimeout = () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
    };

    const armStreamTimeout = (delay: number, reason: 'connect' | 'inactivity') => {
      clearStreamTimeout();
      timeoutId = setTimeout(() => {
        timeoutReason = reason;
        controller.abort();
      }, delay);
    };

    armStreamTimeout(connectTimeout, 'connect');

    const abortHandler = () => {
      clearStreamTimeout();
      controller.abort();
    };
    
    if (signal) {
      signal.addEventListener('abort', abortHandler);
    }

    try {
      const apiBase = resolveApiBase();
      const streamUrl = apiBase ? `${apiBase}/api/chat/stream` : '/api/chat/stream';

      const response = await fetch(streamUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAdminAuthHeaders(),
        },
        body: JSON.stringify({
          content: message,
          session_key: sessionKey,
          file_ids: fileIds || [],
          web_search: webSearch || false,
          files: files || [],
          agent_id: agentId || null,
          group_chat: groupChat || false,
          team_id: teamId || null,
          mentioned_agents: mentionedAgents || [],
          conversation_id: conversationId || null,
          conversation_type: conversationType || null,
        }),
        signal: controller.signal,
      });

      clearStreamTimeout();

      if (!response.ok) {
        onStateChange?.('error');
        throw new ChatStreamError(
          `HTTP error! status: ${response.status}`,
          'http',
          response.status,
        );
      }

      onStateChange?.('waiting');
      armStreamTimeout(timeout, 'inactivity');

      const requestId = response.headers.get('X-Request-Id');
      if (requestId && onRequestStart) {
        onRequestStart(requestId);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        onStateChange?.('error');
        throw new Error('No reader available');
      }

      const decoder = new TextDecoder();
      let buffer = '';
      let hasReceivedData = false;

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            clearStreamTimeout();
            onStateChange?.('done');
            break;
          }

          armStreamTimeout(timeout, 'inactivity');

          if (!hasReceivedData) {
            hasReceivedData = true;
            onStateChange?.('receiving');
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6)) as StreamEvent;
                onChunk(data);
              } catch (e) {
                console.error('Failed to parse SSE data:', line, e);
              }
            }
          }
        }
        
        if (buffer.startsWith('data: ')) {
          try {
            const data = JSON.parse(buffer.slice(6)) as StreamEvent;
            onChunk(data);
          } catch (e) {
            console.error('Failed to parse SSE data:', buffer, e);
          }
        }
      } finally {
        reader.releaseLock();
      }
    } catch (error: unknown) {
      clearStreamTimeout();
      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          if (signal?.aborted) {
            onStateChange?.('done');
            throw new ChatStreamError('Chat stream aborted by user', 'aborted');
          } else {
            if (timeoutReason === 'connect') {
              console.warn('Chat stream connection timed out before headers were received');
            } else if (timeoutReason === 'inactivity') {
              console.warn('Chat stream timed out due to inactivity');
            }
            onStateChange?.('timeout');
            throw new ChatStreamError('Chat stream timed out', 'timeout');
          }
        }
        if (error instanceof ChatStreamError) {
          throw error;
        }
        onStateChange?.('error');
        throw new ChatStreamError(error.message || 'Chat stream failed', 'network');
      }
      onStateChange?.('error');
      throw new ChatStreamError('Chat stream failed', 'network');
    } finally {
      if (signal) {
        signal.removeEventListener('abort', abortHandler);
      }
      clearStreamTimeout();
    }
  },

  stopGeneration: async (params: StopGenerationParams): Promise<void> => {
    await api.post('/api/chat/stop', params);
  },

  confirmAction: async (params: ConfirmActionParams): Promise<void> => {
    await api.post('/api/chat/confirm', params);
  },
};

export default chatService;
