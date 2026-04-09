export const ConversationType = {
  DM: 'dm',
  TEAM: 'team',
} as const;

export type ConversationType = typeof ConversationType[keyof typeof ConversationType];

export interface Conversation {
  id: string;
  type: ConversationType;
  targetId: string;
  name: string;
  description?: string;
  agentIds: string[];
  createdAt: string;
  updatedAt: string;
  metadata?: Record<string, unknown>;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
  turnId?: string;
  requestId?: string;
  agentId?: string;
  agentName?: string;
  agentAvatar?: string;
  conversationId?: string;
  conversationType?: ConversationType;
  isStreaming?: boolean;
  isThinking?: boolean;
  statusMessage?: string;
  files?: MessageFile[];
  metadata?: Record<string, unknown>;
  isError?: boolean;
  errorKind?: 'provider' | 'network' | 'timeout' | 'stream';
  retryable?: boolean;
  executionSteps?: ExecutionStep[];
  retryPayload?: {
    content: string;
    mentionedAgents: string[];
    files?: MessageFile[];
  };
}

export interface MemorySource {
  category?: string;
  level: string;
  file?: string;
  path?: string;
  title?: string;
  snippet?: string;
  relevance?: number;
  reasons?: string[];
  matched_terms?: string[];
  section_index?: number;
  origin?: string;
  owner_id?: string;
  scope?: string;
  scope_label?: string;
}

export interface MemoryRecall {
  timestamp?: string;
  latency_ms?: number;
  candidates_count?: number;
  selected_count?: number;
  query?: string;
  selected_memory_ids?: string[];
}

export interface ExecutionStep {
  id: string;
  type: string;
  title: string;
  status: 'running' | 'completed' | 'failed' | 'pending' | 'stopped' | 'skipped' | 'error' | 'success';
  timestamp: string;
  details?: Record<string, unknown>;
}

export interface MessageFile {
  fileId: string;
  filename: string;
  originalName: string;
  mimeType: string;
  size: number;
  category: string;
  url: string;
  previewUrl?: string;
  localPreview?: string;
  minimaxFileId?: string;
  extractedText?: string;
}

export interface TypingInfo {
  agentId: string;
  agentName: string;
  conversationId: string;
}

export const AgentStatus = {
  ONLINE: 'online',
  BUSY: 'busy',
  OFFLINE: 'offline',
} as const;

export type AgentStatus = typeof AgentStatus[keyof typeof AgentStatus];

export interface AgentStatusInfo {
  agentId: string;
  agentName: string;
  status: AgentStatus;
  currentTask?: string;
  lastActivity: string;
}

export function createDMConversationId(agentId: string): string {
  return `dm_${agentId}`;
}

export function createTeamConversationId(teamId: string): string {
  return `team_${teamId}`;
}

export function parseConversationId(convId: string): { type: ConversationType; targetId: string } {
  if (convId.startsWith('dm_')) {
    return { type: ConversationType.DM, targetId: convId.substring(3) };
  } else if (convId.startsWith('team_')) {
    return { type: ConversationType.TEAM, targetId: convId.substring(5) };
  }
  throw new Error(`Invalid conversation ID format: ${convId}`);
}

export function conversationIdToSessionKey(convId: string, prefix: string = 'web'): string {
  return `${prefix}:${convId}`;
}

export function sessionKeyToConversationId(sessionKey: string): string {
  if (sessionKey.startsWith('web:')) {
    return sessionKey.substring(4);
  }
  return sessionKey;
}
