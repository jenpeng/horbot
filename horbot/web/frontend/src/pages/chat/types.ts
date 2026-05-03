import type { ExecutionStep, MessageFile } from '../../types/conversation';

export interface AgentInfo {
  id: string;
  name: string;
  description?: string;
  external?: boolean;
  team_enabled?: boolean;
  profile?: string;
  is_main?: boolean;
  setup_required?: boolean;
  bootstrap_setup_pending?: boolean;
  runtime_capabilities?: ToolCapability[];
  runtime_capability_labels?: string[];
  tool_permission_profile?: string;
  mcp_servers?: string[];
}

export interface ToolCapability {
  id: string;
  label: string;
  description?: string;
  enabled: boolean;
  source?: string;
  tools?: string[];
}

export interface TeamInfo {
  id: string;
  name: string;
  members: string[];
  description?: string;
}

export interface ChatDirectoryBundle {
  agents: AgentInfo[];
  externalAgents: AgentInfo[];
  teams: TeamInfo[];
}

export interface UIMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
  turnId?: string;
  requestId?: string;
  isStreaming?: boolean;
  isThinking?: boolean;
  statusMessage?: string;
  agentId?: string;
  agentName?: string;
  files?: MessageFile[];
  executionSteps?: ExecutionStep[];
  metadata?: Record<string, unknown>;
  isError?: boolean;
  errorKind?: 'provider' | 'network' | 'timeout' | 'stream';
  retryable?: boolean;
  confirmationId?: string;
  confirmationHandled?: boolean;
  toolName?: string;
  toolArguments?: Record<string, unknown>;
  retryPayload?: {
    content: string;
    mentionedAgents: string[];
    files?: MessageFile[];
  };
}

export interface ProviderErrorInfo {
  error_code?: string;
  error_kind?: string;
  remediation?: string[];
  retryable?: boolean;
}

export interface StreamMessageEntry {
  messageId: string;
  content: string;
  turnId?: string;
  agentId: string;
  phase: 'pending' | 'active' | 'done';
  executionSteps: ExecutionStep[];
}

export interface RetryRequest {
  conversationId: string;
  content: string;
  mentionedAgents: string[];
  files?: MessageFile[];
}

export interface MessageTurn {
  id: string;
  userMessage?: UIMessage;
  assistantMessages: UIMessage[];
  responseGroups: UIMessage[][];
  hasError: boolean;
  relayCount: number;
  participantAgentIds: string[];
}

export interface MessageTurnAccumulator extends MessageTurn {
  requestIds: Set<string>;
}

export interface InterruptNotice {
  tone: 'info' | 'warning' | 'success';
  message: string;
}

export interface BatonNavigationNotice {
  tone: 'team' | 'dm';
  message: string;
  actionLabel?: string;
  actionConversationId?: string;
}

export interface RelayStatusSnapshot {
  pendingAgentNames: string[];
  activeAgentNames: string[];
  activeProcessingAgentName?: string;
  activeProcessingMessage: UIMessage | null;
}

export interface RelayTimelineStep {
  key: string;
  label: string;
  state: 'waiting' | 'active' | 'done' | 'error';
  detail: string;
  isFinal: boolean;
  groupIndex: number;
}

export interface PendingRelayJump {
  turnId: string;
  groupIndex: number;
}

export interface ExpandedRelaySegment {
  startIndex: number;
  endIndex: number;
}

export interface HistorySearchMatch {
  key: string;
  turnId: string;
  groupIndex?: number;
  role: 'user' | 'assistant';
  label: string;
  preview: string;
  messageIds: string[];
}

export interface RemoteHistorySearchMatch {
  message_id: string;
  turn_id?: string;
  request_id?: string;
  role: 'user' | 'assistant';
  preview: string;
  timestamp?: string;
  agent_id?: string;
  agent_name?: string;
}

export type HistorySearchTimeRange = 'all' | '7d' | '30d';

export type HistoryLoadMode = 'initial' | 'before' | 'after' | 'around';

export interface ConversationHistoryWindowState {
  oldestMessageId?: string;
  newestMessageId?: string;
  hasMoreBefore: boolean;
  hasMoreAfter: boolean;
  totalMessages?: number;
}

export interface ConversationHistoryPage {
  oldest_message_id?: string | null;
  newest_message_id?: string | null;
  has_more_before?: boolean;
  has_more_after?: boolean;
  returned_messages?: number;
  total_messages?: number;
}

export type RelayGroupState = RelayTimelineStep['state'];

export interface ConversationHealth {
  tone: 'warning' | 'danger';
  approxTokens: number;
  turnCount: number;
}

export interface RelayRenderGroupItem {
  type: 'group';
  key: string;
  group: UIMessage[];
  groupIndex: number;
}

export interface RelayRenderSummaryItem {
  type: 'summary';
  key: string;
  hiddenCount: number;
  startIndex: number;
  endIndex: number;
  labels: string[];
}

export type RelayRenderItem = RelayRenderGroupItem | RelayRenderSummaryItem;
export type TranslateFn = (key: string, values?: Record<string, number | string>) => string;

export const EMPTY_MESSAGES: UIMessage[] = [];
export const EMPTY_TYPING_AGENTS: string[] = [];
export const CONVERSATION_HISTORY_PAGE_SIZE = 80;
export const CONVERSATION_HISTORY_SEARCH_PAGE_SIZE = 20;
export const CONVERSATION_HISTORY_SEARCH_CONTEXT = 20;
export const TURN_VIRTUALIZATION_THRESHOLD = 40;
export const TURN_VIRTUALIZATION_ESTIMATED_HEIGHT = 360;
export const TURN_VIRTUALIZATION_OVERSCAN = 4;
export const TURN_VIRTUALIZATION_ROW_GAP = 12;
