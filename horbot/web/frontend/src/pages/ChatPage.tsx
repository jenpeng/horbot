import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import {
  ArrowDown,
  Bot,
  CalendarClock,
  ChevronsDown,
  ChevronsUp,
  CirclePlay,
  Globe,
  FoldVertical,
  FolderOpen,
  Network,
  PencilLine,
  Search,
  TerminalSquare,
  UnfoldVertical,
  X,
} from 'lucide-react';
import MessageGroup from '../components/MessageGroup';
import MessageExecutionCard from '../components/MessageExecutionCard';
import MessageInput from '../components/MessageInput';
import type { SessionStatus } from '../components/MessageInput';
import { getAgentPermissionPreset, getAgentProfilePreset } from '../constants';
import TypingIndicator from '../components/TypingIndicator';
import { useToast } from '../contexts/ToastContext';
import { resolveApiBase } from '../services/api';
import { useConversationStore } from '../stores/conversationStore';
import { ConversationType } from '../types/conversation';
import type { ExecutionStep, MessageFile } from '../types/conversation';
import { chatService, ChatStreamError } from '../services/chat';
import type { StreamState, UploadedFile } from '../services/chat';
import type { ConversationState } from '../stores/conversationStore';

interface AgentInfo {
  id: string;
  name: string;
  description?: string;
  profile?: string;
  is_main?: boolean;
  setup_required?: boolean;
  bootstrap_setup_pending?: boolean;
  runtime_capabilities?: ToolCapability[];
  runtime_capability_labels?: string[];
  tool_permission_profile?: string;
  mcp_servers?: string[];
}

interface ToolCapability {
  id: string;
  label: string;
  description?: string;
  enabled: boolean;
  source?: string;
  tools?: string[];
}

interface TeamInfo {
  id: string;
  name: string;
  members: string[];
  description?: string;
}

interface UIMessage {
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
  retryPayload?: {
    content: string;
    mentionedAgents: string[];
    files?: MessageFile[];
  };
}

interface ProviderErrorInfo {
  error_code?: string;
  error_kind?: string;
  remediation?: string[];
  retryable?: boolean;
}

interface StreamMessageEntry {
  messageId: string;
  content: string;
  turnId?: string;
  agentId: string;
  phase: 'pending' | 'active' | 'done';
  executionSteps: ExecutionStep[];
}

interface RetryRequest {
  conversationId: string;
  content: string;
  mentionedAgents: string[];
  files?: MessageFile[];
}

interface MessageTurn {
  id: string;
  userMessage?: UIMessage;
  assistantMessages: UIMessage[];
  responseGroups: UIMessage[][];
  hasError: boolean;
  relayCount: number;
  participantAgentIds: string[];
}

interface MessageTurnAccumulator extends MessageTurn {
  requestIds: Set<string>;
}

interface InterruptNotice {
  tone: 'info' | 'warning' | 'success';
  message: string;
}

interface RelayStatusSnapshot {
  pendingAgentNames: string[];
  activeAgentNames: string[];
  activeProcessingAgentName?: string;
  activeProcessingMessage: UIMessage | null;
}

interface RelayTimelineStep {
  key: string;
  label: string;
  state: 'waiting' | 'active' | 'done' | 'error';
  detail: string;
  isFinal: boolean;
  groupIndex: number;
}

interface PendingRelayJump {
  turnId: string;
  groupIndex: number;
}

interface ExpandedRelaySegment {
  startIndex: number;
  endIndex: number;
}

interface HistorySearchMatch {
  key: string;
  turnId: string;
  groupIndex?: number;
  role: 'user' | 'assistant';
  label: string;
  preview: string;
}

type RelayGroupState = RelayTimelineStep['state'];

interface RelayRenderGroupItem {
  type: 'group';
  key: string;
  group: UIMessage[];
  groupIndex: number;
}

interface RelayRenderSummaryItem {
  type: 'summary';
  key: string;
  hiddenCount: number;
  startIndex: number;
  endIndex: number;
  labels: string[];
}

type RelayRenderItem = RelayRenderGroupItem | RelayRenderSummaryItem;

const EMPTY_MESSAGES: UIMessage[] = [];
const EMPTY_TYPING_AGENTS: string[] = [];

const FRIENDLY_PROVIDER_ERROR_MESSAGES = new Set([
  '模型服务鉴权失败，请检查配置。',
  '当前模型或接口不存在，请检查配置。',
  '模型服务当前负载较高，请稍后重试。',
  '模型服务响应超时，请稍后重试。',
  '模型服务连接失败，请稍后重试。',
  '模型服务返回异常，请稍后重试。',
  '模型服务暂时不可用，请稍后重试。',
]);

const getCapabilityIcon = (capabilityId: string) => {
  switch (capabilityId) {
    case 'files':
      return FolderOpen;
    case 'terminal':
      return TerminalSquare;
    case 'web':
      return Search;
    case 'browser':
      return Globe;
    case 'tasks':
      return CalendarClock;
    case 'relay':
      return Bot;
    case 'mcp':
      return Network;
    default:
      return Bot;
  }
};

const getCapabilityTone = (capabilityId: string): string => {
  switch (capabilityId) {
    case 'files':
      return 'border-amber-200 bg-amber-50 text-amber-700';
    case 'terminal':
      return 'border-slate-200 bg-slate-100 text-slate-700';
    case 'web':
      return 'border-cyan-200 bg-cyan-50 text-cyan-700';
    case 'browser':
      return 'border-sky-200 bg-sky-50 text-sky-700';
    case 'tasks':
      return 'border-emerald-200 bg-emerald-50 text-emerald-700';
    case 'relay':
      return 'border-violet-200 bg-violet-50 text-violet-700';
    case 'mcp':
      return 'border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700';
    default:
      return 'border-slate-200 bg-slate-50 text-slate-700';
  }
};

const DEFAULT_DM_ONBOARDING_CHECKLIST = [
  '主要职责和适用场景',
  '默认输出结构与语气',
  '风险边界与需要确认的事项',
  '与其他 Agent 的协作方式',
];

const DEFAULT_DM_STARTER_PROMPTS = [
  '请先介绍一下你之后会负责什么、默认会如何组织回答，以及哪些事情需要我先明确。',
  '先和我约定你的工作边界：什么事情你会直接执行，什么事情你会先回来确认。',
  '请先总结你的默认协作方式，包括收到任务后如何理解需求、如何输出结果、如何暴露不确定性。',
];

const isFriendlyProviderErrorMessage = (content?: string): boolean => {
  const normalized = content?.trim();
  return !!normalized && FRIENDLY_PROVIDER_ERROR_MESSAGES.has(normalized);
};

const normalizeAssistantErrorContent = (content?: string): {
  content: string;
  isProviderError: boolean;
} => {
  const normalized = content?.trim() || '';
  if (!normalized) {
    return { content: '', isProviderError: false };
  }
  if (isFriendlyProviderErrorMessage(normalized)) {
    return { content: normalized, isProviderError: true };
  }

  const lower = normalized.toLowerCase();
  if (
    lower.includes('invalid response object') ||
    lower.includes('received_args=') ||
    lower.includes('openaiexception') ||
    lower.includes('modelresponse(') ||
    lower.includes('error calling llm') ||
    lower.includes('litellm.')
  ) {
    return { content: '模型服务返回异常，请稍后重试。', isProviderError: true };
  }
  if (
    lower.includes('unauthorized') ||
    lower.includes('invalid api key') ||
    lower.includes('incorrect api key') ||
    lower.includes('forbidden')
  ) {
    return { content: '模型服务鉴权失败，请检查配置。', isProviderError: true };
  }
  if (lower.includes('model not found') || lower.includes('404')) {
    return { content: '当前模型或接口不存在，请检查配置。', isProviderError: true };
  }
  if (
    lower.includes('rate limit') ||
    lower.includes('too many requests') ||
    lower.includes('overloaded') ||
    lower.includes('负载较高')
  ) {
    return { content: '模型服务当前负载较高，请稍后重试。', isProviderError: true };
  }
  if (
    lower.includes('timeout') ||
    lower.includes('timed out') ||
    lower.includes('readtimeout') ||
    lower.includes('connecttimeout')
  ) {
    return { content: '模型服务响应超时，请稍后重试。', isProviderError: true };
  }

  return { content: normalized, isProviderError: false };
};

const normalizeProviderErrorPayload = (value: unknown): ProviderErrorInfo | null => {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const item = value as Record<string, unknown>;
  return {
    error_code: typeof item.error_code === 'string' ? item.error_code : undefined,
    error_kind: typeof item.error_kind === 'string' ? item.error_kind : undefined,
    remediation: Array.isArray(item.remediation)
      ? item.remediation.filter((entry): entry is string => typeof entry === 'string' && entry.trim().length > 0)
      : undefined,
    retryable: typeof item.retryable === 'boolean' ? item.retryable : undefined,
  };
};

const resolveStreamFailureMessage = (error: unknown): {
  content: string;
  errorKind: 'network' | 'timeout' | 'stream';
} => {
  if (error instanceof ChatStreamError) {
    if (error.code === 'timeout') {
      return {
        content: '请求超时，模型暂时没有返回结果，请重试。',
        errorKind: 'timeout',
      };
    }
    if (error.code === 'http') {
      return {
        content: '服务请求失败，请稍后重试。',
        errorKind: 'stream',
      };
    }
  }

  return {
    content: '网络或服务连接异常，请重试。',
    errorKind: 'network',
  };
};

const cleanHistoryMessageContent = (content: string): string => {
  if (!content) return content;

  const messageFromPattern = /<message\s+from="[^"]*">\s*([\s\S]*?)\s*<\/message>/;
  const match = content.match(messageFromPattern);
  if (match) {
    return match[1].trim();
  }

  return content;
};

const buildHistoryMessageFallbackId = (msg: {
  role: string;
  content: string;
  timestamp?: string;
  metadata?: { agent_id?: string; agent_name?: string; turn_id?: string; request_id?: string };
}): string => {
  const source = JSON.stringify({
    role: msg.role || '',
    content: cleanHistoryMessageContent(msg.content || ''),
    timestamp: msg.timestamp || '',
    agentId: msg.metadata?.agent_id || '',
    agentName: msg.metadata?.agent_name || '',
    turnId: msg.metadata?.turn_id || '',
    requestId: msg.metadata?.request_id || '',
  });

  let hash = 0;
  for (let i = 0; i < source.length; i += 1) {
    hash = ((hash << 5) - hash + source.charCodeAt(i)) | 0;
  }
  return `legacy-${Math.abs(hash).toString(36)}`;
};

const toAbsoluteApiUrl = (value?: string): string | undefined => {
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

const normalizeMessageFile = (value: unknown): MessageFile | null => {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const file = value as Record<string, unknown>;
  const fileId = typeof file.fileId === 'string'
    ? file.fileId
    : typeof file.file_id === 'string'
      ? file.file_id
      : '';

  if (!fileId) {
    return null;
  }

  const url = typeof file.url === 'string' ? file.url : '';
  const previewUrlValue = typeof file.previewUrl === 'string'
    ? file.previewUrl
    : typeof file.preview_url === 'string'
      ? file.preview_url
      : undefined;

  return {
    fileId,
    filename: typeof file.filename === 'string' ? file.filename : '',
    originalName: typeof file.originalName === 'string'
      ? file.originalName
      : typeof file.original_name === 'string'
        ? file.original_name
        : '',
    mimeType: typeof file.mimeType === 'string'
      ? file.mimeType
      : typeof file.mime_type === 'string'
        ? file.mime_type
        : 'application/octet-stream',
    size: typeof file.size === 'number' ? file.size : 0,
    category: typeof file.category === 'string' ? file.category : 'document',
    url: toAbsoluteApiUrl(url) || url,
    previewUrl: toAbsoluteApiUrl(previewUrlValue),
    localPreview: typeof file.localPreview === 'string' ? file.localPreview : undefined,
    minimaxFileId: typeof file.minimaxFileId === 'string'
      ? file.minimaxFileId
      : typeof file.minimax_file_id === 'string'
        ? file.minimax_file_id
        : undefined,
    extractedText: typeof file.extractedText === 'string'
      ? file.extractedText
      : typeof file.extracted_text === 'string'
        ? file.extracted_text
        : undefined,
  };
};

const normalizeMessageFiles = (value: unknown): MessageFile[] | undefined => {
  if (!Array.isArray(value)) {
    return undefined;
  }
  const files = value
    .map((item) => normalizeMessageFile(item))
    .filter((item): item is MessageFile => !!item);
  return files.length > 0 ? files : undefined;
};

const serializeMessageFiles = (files?: MessageFile[]): UploadedFile[] | undefined => {
  if (!files || files.length === 0) {
    return undefined;
  }
  return files.map((file) => ({
    file_id: file.fileId,
    filename: file.filename,
    original_name: file.originalName,
    mime_type: file.mimeType,
    size: file.size,
    category: file.category,
    url: file.url,
    preview_url: file.previewUrl,
    minimax_file_id: file.minimaxFileId,
    extracted_text: file.extractedText,
  }));
};

const buildMessageMergeKey = (message: Pick<
  UIMessage,
  'role' | 'content' | 'timestamp' | 'agentId' | 'agentName' | 'turnId' | 'requestId'
>): string => {
  const compactContent = cleanHistoryMessageContent(message.content || '').replace(/\s+/g, ' ').trim();
  return JSON.stringify({
    role: message.role,
    content: compactContent,
    timestamp: message.timestamp || '',
    agentId: message.agentId || '',
    agentName: message.agentName || '',
    turnId: message.turnId || '',
    requestId: message.requestId || '',
  });
};

const groupMessagesBySpeaker = (messages: UIMessage[]): UIMessage[][] => {
  if (messages.length === 0) return [];

  const groups: UIMessage[][] = [];
  let currentGroup: UIMessage[] = [messages[0]];

  for (let i = 1; i < messages.length; i += 1) {
    const current = messages[i];
    const previous = currentGroup[currentGroup.length - 1];
    if (current.role === previous.role && current.agentId === previous.agentId) {
      currentGroup.push(current);
    } else {
      groups.push(currentGroup);
      currentGroup = [current];
    }
  }

  groups.push(currentGroup);
  return groups;
};

const parseMessageTimestamp = (timestamp?: string): number | null => {
  if (!timestamp) {
    return null;
  }

  const value = Date.parse(timestamp);
  return Number.isNaN(value) ? null : value;
};

const normalizeSearchText = (value?: string): string => (
  (value || '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
);

const buildSearchPreview = (value?: string, maxLength: number = 96): string => {
  const normalized = (value || '').replace(/\s+/g, ' ').trim();
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, Math.max(1, maxLength - 1))}…`;
};

const hasLegacyTimeBoundary = (
  currentTurn: MessageTurnAccumulator,
  message: UIMessage,
): boolean => {
  if (message.requestId || currentTurn.assistantMessages.length === 0) {
    return false;
  }

  const hasAssistantRequestIds = currentTurn.assistantMessages.some((item) => !!item.requestId);
  if (hasAssistantRequestIds) {
    return false;
  }

  const previousAssistant = currentTurn.assistantMessages[currentTurn.assistantMessages.length - 1];
  const previousTimestamp = parseMessageTimestamp(previousAssistant.timestamp);
  const currentTimestamp = parseMessageTimestamp(message.timestamp);
  if (previousTimestamp === null || currentTimestamp === null) {
    return false;
  }

  const timeDelta = currentTimestamp - previousTimestamp;
  return timeDelta < 0 || timeDelta > 2 * 60 * 1000;
};

const buildMessageTurns = (messages: UIMessage[]): MessageTurn[] => {
  const turns: MessageTurn[] = [];
  let currentTurn: MessageTurnAccumulator | null = null;

  const finalizeTurn = (turn: MessageTurnAccumulator | null) => {
    if (!turn) {
      return;
    }

    turn.responseGroups = groupMessagesBySpeaker(turn.assistantMessages);
    turn.relayCount = turn.responseGroups.filter((group) => group[0]?.role === 'assistant').length;
    turns.push({
      id: turn.id,
      userMessage: turn.userMessage,
      assistantMessages: turn.assistantMessages,
      responseGroups: turn.responseGroups,
      hasError: turn.hasError,
      relayCount: turn.relayCount,
      participantAgentIds: turn.participantAgentIds,
    });
  };

  const createTurn = (message: UIMessage): MessageTurnAccumulator => ({
    id: message.requestId || message.turnId || message.id,
    userMessage: message.role === 'user' ? message : undefined,
    assistantMessages: message.role === 'assistant' ? [message] : [],
    responseGroups: [],
    hasError: !!message.isError,
    relayCount: 0,
    participantAgentIds: message.agentId ? [message.agentId] : [],
    requestIds: new Set(message.requestId ? [message.requestId] : []),
  });

  for (const message of messages) {
    if (message.role === 'user') {
      finalizeTurn(currentTurn);
      currentTurn = createTurn(message);
      continue;
    }

    if (!currentTurn) {
      currentTurn = createTurn(message);
      continue;
    }

    const shouldSplitOnRequestBoundary = Boolean(
      currentTurn.userMessage &&
      message.requestId &&
      currentTurn.assistantMessages.length > 0 &&
      currentTurn.requestIds.size > 0 &&
      !currentTurn.requestIds.has(message.requestId),
    );

    if (shouldSplitOnRequestBoundary) {
      finalizeTurn(currentTurn);
      currentTurn = createTurn(message);
      continue;
    }

    if (hasLegacyTimeBoundary(currentTurn, message)) {
      finalizeTurn(currentTurn);
      currentTurn = createTurn(message);
      continue;
    }

    currentTurn.assistantMessages.push(message);
    currentTurn.hasError = currentTurn.hasError || !!message.isError;
    if (message.requestId) {
      currentTurn.requestIds.add(message.requestId);
    }
    if (message.agentId && !currentTurn.participantAgentIds.includes(message.agentId)) {
      currentTurn.participantAgentIds.push(message.agentId);
    }
  }

  finalizeTurn(currentTurn);

  return turns;
};

const parseRelayGroupKey = (value: string | null): PendingRelayJump | null => {
  if (!value) return null;
  const separatorIndex = value.lastIndexOf(':');
  if (separatorIndex <= 0) {
    return null;
  }

  const turnId = value.slice(0, separatorIndex);
  const groupIndex = Number.parseInt(value.slice(separatorIndex + 1), 10);
  if (Number.isNaN(groupIndex)) {
    return null;
  }

  return { turnId, groupIndex };
};

const getRelayGroupState = (group: UIMessage[]): RelayGroupState => {
  if (group.some((message) => message.isError)) {
    return 'error';
  }
  if (group.some((message) => !!message.statusMessage?.includes('等待响应'))) {
    return 'waiting';
  }
  if (group.some((message) => message.isStreaming || message.isThinking)) {
    return 'active';
  }
  return 'done';
};

const getMessageMetadataString = (message: UIMessage, key: string): string | undefined => {
  const value = message.metadata?.[key];
  return typeof value === 'string' && value.trim().length > 0 ? value : undefined;
};

const getRelayGroupTransition = (
  group: UIMessage[],
  getAgentName: (agentId?: string) => string | undefined,
): {
  sourceName?: string;
  targetName?: string;
  conversationType?: string;
  handoffMode?: string;
} => {
  const firstMessage = group[0];
  return {
    sourceName: getMessageMetadataString(firstMessage, 'handoff_from_name')
      || getMessageMetadataString(firstMessage, 'source_name'),
    targetName: firstMessage.agentName
      || getMessageMetadataString(firstMessage, 'handoff_to_name')
      || getMessageMetadataString(firstMessage, 'target_name')
      || getAgentName(firstMessage.agentId),
    conversationType: getMessageMetadataString(firstMessage, 'conversation_type'),
    handoffMode: getMessageMetadataString(firstMessage, 'handoff_mode'),
  };
};

const getRelayGroupStateDetail = (group: UIMessage[]): string => {
  const lastMessage = group[group.length - 1];
  const state = getRelayGroupState(group);
  const { sourceName, targetName, conversationType, handoffMode } = getRelayGroupTransition(group, () => undefined);

  if (state === 'error') {
    return lastMessage.errorKind === 'provider'
      ? '模型异常'
      : lastMessage.errorKind === 'timeout'
        ? '请求超时'
        : lastMessage.errorKind === 'network'
          ? '网络异常'
          : '请求失败';
  }
  if (state === 'waiting') {
    if (handoffMode === 'summary' && sourceName && targetName) {
      return `等待 ${targetName} 接棒并回到用户总结`;
    }
    if (handoffMode === 'continue' && sourceName && targetName) {
      return `等待 ${targetName} 承接 ${sourceName} 的下一轮讨论`;
    }
    return lastMessage.statusMessage || '等待接力';
  }
  if (state === 'active') {
    if (handoffMode === 'summary' && targetName) {
      return `${targetName} 正在汇总结论`;
    }
    if (sourceName && targetName && sourceName !== targetName) {
      return `${targetName} 正在承接 ${sourceName} 的上一棒`;
    }
    return lastMessage.isThinking
      ? '思考中'
      : (lastMessage.statusMessage || '处理中');
  }
  if (conversationType === 'user_to_agent') {
    return targetName ? `${targetName} 已面向用户完成输出` : '已面向用户完成输出';
  }
  if (sourceName && targetName && sourceName !== targetName) {
    return `${targetName} 已完成对 ${sourceName} 的交接回复`;
  }
  return '已完成回复';
};

const getRelayGroupLabel = (
  group: UIMessage[],
  index: number,
  getAgentName: (agentId?: string) => string | undefined,
): string => {
  const { sourceName, targetName, conversationType, handoffMode } = getRelayGroupTransition(group, getAgentName);
  if (conversationType === 'user_to_agent' && targetName) {
    return `${targetName} -> 用户`;
  }
  if (handoffMode === 'summary' && sourceName && targetName) {
    return `${sourceName} -> ${targetName}（总结）`;
  }
  if (sourceName && targetName && sourceName !== targetName) {
    return `${sourceName} -> ${targetName}`;
  }
  return targetName || `助手 ${index + 1}`;
};

const MAX_VISIBLE_RELAY_GROUPS_WITHOUT_COLLAPSE = 4;

const getDefaultVisibleRelayGroupIndexes = (
  turn: MessageTurn,
  options: {
    highlightedGroupIndex?: number | null;
    pendingJumpGroupIndex?: number | null;
    interruptedGroupIndex?: number | null;
  } = {},
): Set<number> => {
  const visibleIndexes = new Set<number>();
  const lastIndex = turn.responseGroups.length - 1;

  if (turn.responseGroups.length <= MAX_VISIBLE_RELAY_GROUPS_WITHOUT_COLLAPSE) {
    turn.responseGroups.forEach((_, groupIndex) => {
      visibleIndexes.add(groupIndex);
    });
  }

  if (lastIndex >= 0) {
    visibleIndexes.add(lastIndex);
  }

  turn.responseGroups.forEach((group, groupIndex) => {
    const state = getRelayGroupState(group);
    if (state === 'error' || state === 'active' || state === 'waiting') {
      visibleIndexes.add(groupIndex);
    }
  });

  if (options.highlightedGroupIndex !== undefined && options.highlightedGroupIndex !== null && options.highlightedGroupIndex >= 0) {
    visibleIndexes.add(options.highlightedGroupIndex);
  }
  if (options.pendingJumpGroupIndex !== undefined && options.pendingJumpGroupIndex !== null && options.pendingJumpGroupIndex >= 0) {
    visibleIndexes.add(options.pendingJumpGroupIndex);
  }
  if (options.interruptedGroupIndex !== undefined && options.interruptedGroupIndex !== null && options.interruptedGroupIndex >= 0) {
    visibleIndexes.add(options.interruptedGroupIndex);
  }

  return visibleIndexes;
};

const buildRelayRenderItems = (
  groups: UIMessage[][],
  visibleIndexes: Set<number>,
  getAgentName: (agentId?: string) => string | undefined,
): RelayRenderItem[] => {
  const items: RelayRenderItem[] = [];

  let groupIndex = 0;
  while (groupIndex < groups.length) {
    if (visibleIndexes.has(groupIndex)) {
      items.push({
        type: 'group',
        key: `group:${groupIndex}:${groups[groupIndex][0]?.id || groupIndex}`,
        group: groups[groupIndex],
        groupIndex,
      });
      groupIndex += 1;
      continue;
    }

    const startIndex = groupIndex;
    const labels: string[] = [];

    while (groupIndex < groups.length && !visibleIndexes.has(groupIndex)) {
      const label = getRelayGroupLabel(groups[groupIndex], groupIndex, getAgentName);
      if (!labels.includes(label)) {
        labels.push(label);
      }
      groupIndex += 1;
    }

    const endIndex = groupIndex - 1;
    items.push({
      type: 'summary',
      key: `summary:${startIndex}-${endIndex}`,
      hiddenCount: endIndex - startIndex + 1,
      startIndex,
      endIndex,
      labels,
    });
  }

  return items;
};

const isRelaySegmentStart = (
  segments: ExpandedRelaySegment[],
  groupIndex: number,
): ExpandedRelaySegment | null => {
  return segments.find((segment) => segment.startIndex === groupIndex) || null;
};

const formatCollapsedRelayLabels = (labels: string[]): string => {
  if (labels.length === 0) {
    return '这些棒次已稳定完成。';
  }
  if (labels.length === 1) {
    return `由 ${labels[0]} 完成稳定转交。`;
  }
  if (labels.length === 2) {
    return `由 ${labels[0]} 到 ${labels[1]} 完成稳定转交。`;
  }
  return `由 ${labels[0]}、${labels[1]} 等 ${labels.length} 棒完成稳定转交。`;
};

const getRelayTimelineSteps = (
  turn: MessageTurn,
  getAgentName: (agentId?: string) => string | undefined,
): RelayTimelineStep[] => {
  const assistantGroups = turn.responseGroups.filter((group) => group[0]?.role === 'assistant');

  return assistantGroups.map((group, index) => {
    const firstMessage = group[0];
    const label = getRelayGroupLabel(group, index, getAgentName);
    return {
      key: `${turn.id}:${firstMessage.id}:${index}`,
      label,
      state: getRelayGroupState(group),
      detail: getRelayGroupStateDetail(group),
      isFinal: index === assistantGroups.length - 1,
      groupIndex: index,
    };
  });
};

const STREAM_STATE_LABELS: Partial<Record<StreamState, string>> = {
  connecting: '正在连接模型',
  waiting: '等待首字返回',
  receiving: '生成中',
  timeout: '请求超时',
  error: '请求失败',
};

const formatAgentNamesForStatus = (names: string[]): string => {
  if (names.length === 0) return '';
  if (names.length === 1) return names[0];
  if (names.length === 2) return `${names[0]} 和 ${names[1]}`;
  return `${names[0]} 等 ${names.length} 个 Agent`;
};

const buildInterruptSummary = (activeAgentName?: string, pendingAgentNames: string[] = []): string => {
  if (activeAgentName && pendingAgentNames.length > 0) {
    return `本轮已中断，停止于 ${activeAgentName}，原本准备交给 ${formatAgentNamesForStatus(pendingAgentNames)}。可继续发送新消息。`;
  }
  if (activeAgentName) {
    return `本轮已中断，停止于 ${activeAgentName}。可继续发送新消息。`;
  }
  if (pendingAgentNames.length > 0) {
    return `本轮已中断，已取消发给 ${formatAgentNamesForStatus(pendingAgentNames)} 的后续接力。可继续发送新消息。`;
  }
  return '本轮已中断，可继续发送新消息。';
};

const buildRequestPreview = (content: string, maxLength = 18): string => {
  const normalized = content.replace(/\s+/g, ' ').trim();
  if (!normalized) {
    return '上一条';
  }
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, Math.max(1, maxLength - 1))}…`;
};

const normalizeExecutionStepStatus = (status?: string): ExecutionStep['status'] => {
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

const inferExecutionStepType = (
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

const inferExecutionStepTitle = (
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
    return `执行 ${toolName}`;
  }
  if (normalizedType.includes('thinking')) {
    return '思考中...';
  }
  if (normalizedType.includes('response')) {
    return '生成回复';
  }
  if (normalizedType.includes('compression')) {
    return '上下文压缩中...';
  }
  return '执行步骤';
};

const mergeExecutionSteps = (
  existingSteps: ExecutionStep[] = [],
  incomingSteps: ExecutionStep[] = [],
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
      title: inferExecutionStepTitle(step.type || previous.type, step.title || previous.title, step.details || previous.details),
      status: normalizeExecutionStepStatus(step.status || previous.status),
      timestamp: previous.timestamp || step.timestamp,
      details: step.details ?? previous.details,
    };
  });

  return mergedSteps;
};

const upsertExecutionStep = (
  steps: ExecutionStep[] = [],
  step: ExecutionStep,
): ExecutionStep[] => mergeExecutionSteps(steps, [{
  ...step,
  type: inferExecutionStepType(step.type, step.details),
  title: inferExecutionStepTitle(step.type, step.title, step.details),
  status: normalizeExecutionStepStatus(step.status),
}]);

const updateLatestRunningExecutionStep = (
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

const finalizeRunningExecutionSteps = (
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

const ChatIconButton: React.FC<{
  label: string;
  icon: React.ReactNode;
  onClick: () => void | Promise<void>;
  tone?: 'neutral' | 'danger' | 'success' | 'violet';
  className?: string;
  dataTestId?: string;
}> = ({ label, icon, onClick, tone = 'neutral', className = '', dataTestId }) => (
  <button
    type="button"
    onClick={onClick}
    title={label}
    aria-label={label}
    data-testid={dataTestId}
    className={`inline-flex h-9 w-9 items-center justify-center rounded-full border transition-colors ${
      tone === 'danger'
        ? 'border-red-200 bg-white text-red-700 hover:bg-red-50'
        : tone === 'success'
          ? 'border-emerald-200 bg-white text-emerald-800 hover:bg-emerald-50'
          : tone === 'violet'
            ? 'border-violet-200 bg-white text-violet-700 hover:bg-violet-100'
            : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
    } ${className}`}
  >
    {icon}
  </button>
);

const ChatPage: React.FC = () => {
  const toast = useToast();
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [teams, setTeams] = useState<TeamInfo[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [historyLoadingConversationId, setHistoryLoadingConversationId] = useState<string | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null);
  const [expandedTurnIds, setExpandedTurnIds] = useState<Record<string, boolean>>({});
  const [expandedTimelineTurnIds, setExpandedTimelineTurnIds] = useState<Record<string, boolean>>({});
  const [streamState, setStreamState] = useState<StreamState | null>(null);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [showReconnect, setShowReconnect] = useState(false);
  const [lastFailedRequest, setLastFailedRequest] = useState<RetryRequest | null>(null);
  const [lastInterruptedRequest, setLastInterruptedRequest] = useState<RetryRequest | null>(null);
  const [lastInterruptedTurnId, setLastInterruptedTurnId] = useState<string | null>(null);
  const [lastInterruptedMessageId, setLastInterruptedMessageId] = useState<string | null>(null);
  const [inputFocusRequestKey, setInputFocusRequestKey] = useState(0);
  const [inputDraftPreset, setInputDraftPreset] = useState({ key: 0, text: '' });
  const [pendingRelayJump, setPendingRelayJump] = useState<PendingRelayJump | null>(null);
  const [highlightedRelayGroupKey, setHighlightedRelayGroupKey] = useState<string | null>(null);
  const [activeHistoryResultKey, setActiveHistoryResultKey] = useState<string | null>(null);
  const [expandedRelaySegments, setExpandedRelaySegments] = useState<Record<string, ExpandedRelaySegment[]>>({});
  const [historySearchQuery, setHistorySearchQuery] = useState('');
  const [historySearchIndex, setHistorySearchIndex] = useState(0);
  const [isHistorySearchOpen, setIsHistorySearchOpen] = useState(false);
  const [isNearBottom, setIsNearBottom] = useState(true);
  
  const currentConversationId = useConversationStore((state: ConversationState) => state.currentConversationId);
  const conversations = useConversationStore((state: ConversationState) => state.conversations);
  const messageMap = useConversationStore((state: ConversationState) => state.messages);
  const typingAgentMap = useConversationStore((state: ConversationState) => state.typingAgents);
  const getMessages = useConversationStore((state: ConversationState) => state.getMessages);
  const addMessage = useConversationStore((state: ConversationState) => state.addMessage);
  const updateMessage = useConversationStore((state: ConversationState) => state.updateMessage);
  const setMessages = useConversationStore((state: ConversationState) => state.setMessages);
  const addTypingAgent = useConversationStore((state: ConversationState) => state.addTypingAgent);
  const removeTypingAgent = useConversationStore((state: ConversationState) => state.removeTypingAgent);
  const getOrCreateDMConversation = useConversationStore((state: ConversationState) => state.getOrCreateDMConversation);
  const getOrCreateTeamConversation = useConversationStore((state: ConversationState) => state.getOrCreateTeamConversation);
  const setCurrentConversation = useConversationStore((state: ConversationState) => state.setCurrentConversation);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const historySearchInputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const currentRequestIdRef = useRef<string | null>(null);
  const activeStreamPromiseRef = useRef<Promise<void> | null>(null);
  const interruptNoticeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeRequestPayloadRef = useRef<RetryRequest | null>(null);
  const activeTurnIdRef = useRef<string | null>(null);
  const relayGroupRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const historyResultRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const relayHighlightTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const historyLoadPromisesRef = useRef(new Map<string, Promise<void>>());
  const relayStatusSnapshotRef = useRef<RelayStatusSnapshot>({
    pendingAgentNames: [],
    activeAgentNames: [],
    activeProcessingAgentName: undefined,
    activeProcessingMessage: null,
  });

  const [interruptNotice, setInterruptNotice] = useState<InterruptNotice | null>(null);

  const showInterruptNotice = useCallback((message: string, tone: InterruptNotice['tone'] = 'info') => {
    setInterruptNotice({ message, tone });
    if (interruptNoticeTimerRef.current) {
      clearTimeout(interruptNoticeTimerRef.current);
    }
    interruptNoticeTimerRef.current = setTimeout(() => {
      setInterruptNotice(null);
      interruptNoticeTimerRef.current = null;
    }, 5000);
  }, []);

  const dismissInterruptNotice = useCallback(() => {
    setInterruptNotice(null);
    if (interruptNoticeTimerRef.current) {
      clearTimeout(interruptNoticeTimerRef.current);
      interruptNoticeTimerRef.current = null;
    }
  }, []);

  const requestInputFocus = useCallback(() => {
    setInputFocusRequestKey((prev) => prev + 1);
  }, []);

  const applyInputDraftPreset = useCallback((text: string) => {
    setInputDraftPreset((prev) => ({ key: prev.key + 1, text }));
    requestInputFocus();
  }, [requestInputFocus]);

  const waitForActiveStreamToSettle = useCallback(async () => {
    const activeStream = activeStreamPromiseRef.current;
    if (!activeStream) return;
    try {
      await activeStream;
    } catch {
      // Stop path may reject with an abort error. Nothing else to do here.
    }
  }, []);

  const requestStopGeneration = useCallback(async () => {
    const controller = abortControllerRef.current;
    const requestId = currentRequestIdRef.current;

    if (requestId) {
      currentRequestIdRef.current = null;
      try {
        await chatService.stopGeneration({ request_id: requestId });
      } catch (error) {
        console.error('Failed to stop generation on server:', error);
      }
    }

    if (controller && !controller.signal.aborted) {
      controller.abort();
    }

    setIsLoading(false);
    setStreamState(null);
  }, []);

  const handleStopGeneration = useCallback(async () => {
    if (!activeStreamPromiseRef.current) return;
    const interruptedRequest = activeRequestPayloadRef.current;
    const interruptedTurnId = activeTurnIdRef.current;
    const relayStatusSnapshot = relayStatusSnapshotRef.current;
    const interruptSummary = buildInterruptSummary(
      relayStatusSnapshot.activeProcessingAgentName,
      relayStatusSnapshot.pendingAgentNames,
    );
    setLastInterruptedRequest(interruptedRequest);
    setLastInterruptedTurnId(interruptedTurnId);
    setLastInterruptedMessageId(relayStatusSnapshot.activeProcessingMessage?.id || null);
    await requestStopGeneration();
    await waitForActiveStreamToSettle();
    toast.info('已停止当前接力。', 2200);
    showInterruptNotice(interruptSummary, 'success');
    requestInputFocus();
  }, [
    requestStopGeneration,
    waitForActiveStreamToSettle,
    toast,
    showInterruptNotice,
    requestInputFocus,
  ]);

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      if (showReconnect && !lastFailedRequest) {
        setShowReconnect(false);
      }
    };
    const handleOffline = () => {
      setIsOnline(false);
      if (isLoading) {
        handleStopGeneration();
      }
    };
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [isLoading, showReconnect, handleStopGeneration, lastFailedRequest]);

  useEffect(() => {
    setInterruptNotice(null);
    setPendingRelayJump(null);
    setHighlightedRelayGroupKey(null);
    setExpandedRelaySegments({});
    setExpandedTimelineTurnIds({});
    if (interruptNoticeTimerRef.current) {
      clearTimeout(interruptNoticeTimerRef.current);
      interruptNoticeTimerRef.current = null;
    }
  }, [currentConversationId]);

  useEffect(() => {
    return () => {
      if (interruptNoticeTimerRef.current) {
        clearTimeout(interruptNoticeTimerRef.current);
      }
      if (relayHighlightTimerRef.current) {
        clearTimeout(relayHighlightTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const handleEscapeStop = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.key !== 'Escape') {
        return;
      }
      if (event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) {
        return;
      }
      if (!activeStreamPromiseRef.current) {
        return;
      }

      event.preventDefault();
      void handleStopGeneration();
    };

    document.addEventListener('keydown', handleEscapeStop);
    return () => document.removeEventListener('keydown', handleEscapeStop);
  }, [handleStopGeneration]);

  const currentConversation = useMemo(() => {
    if (!currentConversationId) {
      return null;
    }
    return conversations.find((conversation) => conversation.id === currentConversationId) || null;
  }, [conversations, currentConversationId]);
  const messages = currentConversationId ? (messageMap[currentConversationId] || EMPTY_MESSAGES) : EMPTY_MESSAGES;
  const typingAgents = currentConversationId ? (typingAgentMap[currentConversationId] || EMPTY_TYPING_AGENTS) : EMPTY_TYPING_AGENTS;
  
  const isHistoryLoading = !!currentConversationId && historyLoadingConversationId === currentConversationId;
  
  const generateId = () => Math.random().toString(36).substring(2, 15);

  const mergeConversationHistory = useCallback((historyMessages: UIMessage[], existingMessages: UIMessage[]) => {
    const mergedMessages = [...historyMessages];
    const indexById = new Map<string, number>();
    const indexBySignature = new Map<string, number>();

    mergedMessages.forEach((message, index) => {
      indexById.set(message.id, index);
      indexBySignature.set(buildMessageMergeKey(message), index);
    });

    existingMessages.forEach((message) => {
      const signature = buildMessageMergeKey(message);
      const existingIndex = indexById.get(message.id) ?? indexBySignature.get(signature);

      if (existingIndex !== undefined) {
        const nextMessage = {
          ...mergedMessages[existingIndex],
          ...message,
          files: message.files ?? mergedMessages[existingIndex].files,
          executionSteps: mergeExecutionSteps(
            mergedMessages[existingIndex].executionSteps,
            message.executionSteps,
          ),
          retryPayload: message.retryPayload ?? mergedMessages[existingIndex].retryPayload,
        };
        mergedMessages[existingIndex] = nextMessage;
        indexById.set(nextMessage.id, existingIndex);
        indexBySignature.set(buildMessageMergeKey(nextMessage), existingIndex);
        return;
      }

      const nextIndex = mergedMessages.length;
      mergedMessages.push(message);
      indexById.set(message.id, nextIndex);
      indexBySignature.set(signature, nextIndex);
    });

    return mergedMessages
      .map((message, index) => ({ message, index }))
      .sort((left, right) => {
        const leftTimestamp = parseMessageTimestamp(left.message.timestamp);
        const rightTimestamp = parseMessageTimestamp(right.message.timestamp);

        if (leftTimestamp === null && rightTimestamp === null) {
          return left.index - right.index;
        }
        if (leftTimestamp === null) {
          return 1;
        }
        if (rightTimestamp === null) {
          return -1;
        }
        if (leftTimestamp === rightTimestamp) {
          return left.index - right.index;
        }
        return leftTimestamp - rightTimestamp;
      })
      .map((entry) => entry.message);
  }, []);
  
  const formatTime = (timestamp?: string) => {
    if (!timestamp) return '';
    
    const date = new Date(timestamp);
    const now = new Date();
    const isToday = date.getFullYear() === now.getFullYear() && 
                    date.getMonth() === now.getMonth() && 
                    date.getDate() === now.getDate();
    
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const timeStr = `${hours}:${minutes}`;
    
    if (isToday) return timeStr;
    
    const month = date.getMonth() + 1;
    const day = date.getDate();
    const isSameYear = date.getFullYear() === now.getFullYear();
    
    return isSameYear ? `${month}月${day}日 ${timeStr}` : `${date.getFullYear()}年${month}月${day}日 ${timeStr}`;
  };
  
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    const container = chatContainerRef.current;
    if (!container) {
      return;
    }

    const updateScrollState = () => {
      const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
      setIsNearBottom(distanceFromBottom < 120);
    };

    updateScrollState();
    container.addEventListener('scroll', updateScrollState, { passive: true });
    return () => container.removeEventListener('scroll', updateScrollState);
  }, [currentConversationId]);

  const refreshAgents = useCallback(async () => {
    try {
      const response = await fetch('/api/agents');
      const payload = await response.json();
      if (payload.agents) {
        setAgents(payload.agents);
      }
    } catch (error) {
      console.error('Failed to refresh agents:', error);
    }
  }, []);
  
  useEffect(() => {
    if (isNearBottom) {
      scrollToBottom();
    }
  }, [messages, isNearBottom, scrollToBottom]);
  
  useEffect(() => {
    const initialize = async () => {
      try {
        const [agentsResponse, teamsResponse] = await Promise.all([
          fetch('/api/agents'),
          fetch('/api/teams'),
        ]);
        const [agentsData, teamsData] = await Promise.all([
          agentsResponse.json(),
          teamsResponse.json(),
        ]);

        if (agentsData.agents) {
          setAgents(agentsData.agents);
        }
        if (teamsData.teams) {
          setTeams(teamsData.teams);
        }
      } catch (error) {
        console.error('Failed to initialize:', error);
      }
    };

    void initialize();
  }, []);

  useEffect(() => {
    const handleKeydown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'f') {
        event.preventDefault();
        setIsHistorySearchOpen(true);
      }
      if (event.key === 'Escape') {
        if (historySearchQuery) {
          setHistorySearchQuery('');
          setHistorySearchIndex(0);
          setActiveHistoryResultKey(null);
          return;
        }
        if (isHistorySearchOpen) {
          setIsHistorySearchOpen(false);
        }
      }
    };

    window.addEventListener('keydown', handleKeydown);
    return () => window.removeEventListener('keydown', handleKeydown);
  }, [historySearchQuery, isHistorySearchOpen]);

  useEffect(() => {
    if (!isHistorySearchOpen) {
      return;
    }
    const frame = window.requestAnimationFrame(() => {
      historySearchInputRef.current?.focus();
      historySearchInputRef.current?.select();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [isHistorySearchOpen]);

  useEffect(() => {
    if (agents.length === 0) {
      return;
    }

    const params = new URLSearchParams(window.location.search);
    const urlAgentId = params.get('agent');
    const urlTeamId = params.get('team');

    if (!currentConversationId && urlAgentId) {
      const targetAgent = agents.find((agent) => agent.id === urlAgentId);
      if (targetAgent) {
        setSelectedAgentId(targetAgent.id);
        setSelectedTeamId(null);
        const conv = getOrCreateDMConversation(targetAgent.id, targetAgent.name);
        setCurrentConversation(conv.id);
        return;
      }
    }

    if (!currentConversationId && urlTeamId) {
      const targetTeam = teams.find((team) => team.id === urlTeamId);
      if (targetTeam) {
        setSelectedTeamId(targetTeam.id);
        setSelectedAgentId(null);
        const conv = getOrCreateTeamConversation(targetTeam.id, targetTeam.name, targetTeam.members, targetTeam.description);
        setCurrentConversation(conv.id);
        return;
      }
    }

    if (currentConversationId) {
      return;
    }

    const defaultAgent = agents[0];
    if (!defaultAgent) {
      return;
    }

    const conv = getOrCreateDMConversation(defaultAgent.id, defaultAgent.name);
    setCurrentConversation(conv.id);
    setSelectedAgentId(defaultAgent.id);
  }, [agents, teams, currentConversationId, getOrCreateDMConversation, getOrCreateTeamConversation, setCurrentConversation]);
  
  const loadConversationHistory = useCallback((convId: string) => {
    const existingRequest = historyLoadPromisesRef.current.get(convId);
    if (existingRequest) {
      return existingRequest;
    }

    setHistoryLoadingConversationId(convId);

    const request = (async () => {
      try {
        const response = await fetch(`/api/conversations/${convId}/messages`);
        const data = await response.json();
        
        if (data.messages && Array.isArray(data.messages)) {
          const formattedMessages: UIMessage[] = data.messages
            .filter((msg: { role: string; content: string; tool_calls?: unknown[] }) => {
              if (msg.role === 'tool') return false;
              const hasToolCalls = msg.tool_calls && Array.isArray(msg.tool_calls) && msg.tool_calls.length > 0;
              const hasContent = msg.content && msg.content.trim();
              if (!hasContent && !hasToolCalls) return false;
              if (msg.content && msg.content.startsWith('Message sent to ')) return false;
              return true;
            })
            .map((msg: { id?: string; role: string; content: string; timestamp?: string; metadata?: { agent_id?: string; agent_name?: string; turn_id?: string; request_id?: string; _provider_error?: unknown }; files?: unknown[]; execution_steps?: ExecutionStep[] }) => {
              const agentId = msg.metadata?.agent_id;
              let agentName = msg.metadata?.agent_name;
              if (!agentName || agentName === 'Assistant') {
                const agent = agents.find(a => a.id === agentId);
                if (agent) {
                  agentName = agent.name;
                }
              }
              const cleanContent = cleanHistoryMessageContent(msg.content);
              const normalizedError = msg.role === 'assistant'
                ? normalizeAssistantErrorContent(cleanContent)
                : { content: cleanContent, isProviderError: false };
              const providerError = normalizeProviderErrorPayload(msg.metadata?._provider_error);
              return {
                id: msg.id || buildHistoryMessageFallbackId(msg),
                role: msg.role,
                content: normalizedError.content,
                timestamp: msg.timestamp,
                turnId: msg.metadata?.turn_id,
                requestId: msg.metadata?.request_id,
                agentId: agentId,
                agentName: agentName,
                files: normalizeMessageFiles(msg.files),
                executionSteps: mergeExecutionSteps([], msg.execution_steps),
                metadata: msg.metadata,
                isError: Boolean(providerError) || normalizedError.isProviderError,
                errorKind: (providerError || normalizedError.isProviderError) ? 'provider' : undefined,
                retryable: providerError?.retryable ?? normalizedError.isProviderError,
              };
            });
          setMessages(convId, mergeConversationHistory(formattedMessages, getMessages(convId) as UIMessage[]));
        }
      } catch (error) {
        console.error('Failed to load conversation history:', error);
      } finally {
        historyLoadPromisesRef.current.delete(convId);
        setHistoryLoadingConversationId((currentLoadingConvId) => (
          currentLoadingConvId === convId ? null : currentLoadingConvId
        ));
      }
    })();

    historyLoadPromisesRef.current.set(convId, request);
    return request;
  }, [setMessages, agents, getMessages, mergeConversationHistory]);
  
  useEffect(() => {
    if (currentConversationId) {
      void loadConversationHistory(currentConversationId);
    }
  }, [currentConversationId, loadConversationHistory]);

  useEffect(() => {
    if (!currentConversation) {
      setSelectedAgentId(null);
      setSelectedTeamId(null);
      return;
    }

    if (currentConversation.type === ConversationType.TEAM) {
      setSelectedTeamId(currentConversation.targetId);
      setSelectedAgentId(null);
      return;
    }

    setSelectedAgentId(currentConversation.targetId);
    setSelectedTeamId(null);
  }, [currentConversation]);
  
  const handleSelectAgent = useCallback((agentId: string) => {
    const agent = agents.find(a => a.id === agentId);
    if (agent) {
      const conv = getOrCreateDMConversation(agentId, agent.name);
      setCurrentConversation(conv.id);
      void loadConversationHistory(conv.id);
      setSelectedAgentId(agentId);
      setSelectedTeamId(null);
    }
  }, [agents, getOrCreateDMConversation, loadConversationHistory, setCurrentConversation]);
  
  const handleSelectTeam = useCallback((teamId: string) => {
    const team = teams.find(t => t.id === teamId);
    if (team) {
      const conv = getOrCreateTeamConversation(teamId, team.name, team.members, team.description);
      setCurrentConversation(conv.id);
      void loadConversationHistory(conv.id);
      setSelectedTeamId(teamId);
      setSelectedAgentId(null);
    }
  }, [teams, getOrCreateTeamConversation, loadConversationHistory, setCurrentConversation]);
  
  const handleSendMessage = useCallback(async (
    content: string,
    mentionedAgents: string[],
    files: MessageFile[] = [],
  ) => {
    if (!currentConversation || !content.trim() || !isOnline) return;

    if (activeStreamPromiseRef.current) {
      await requestStopGeneration();
      await waitForActiveStreamToSettle();
      toast.info('已停止上一轮接力，正在切换到新请求。', 2400);
      showInterruptNotice('已停止上一轮接力，正在切换到新请求。', 'info');
    }

    const trimmedContent = content.trim();
    const normalizedFiles = normalizeMessageFiles(files) || [];
    const uploadedFiles = serializeMessageFiles(normalizedFiles);
    const fileIds = uploadedFiles
      ?.map((file) => file.minimax_file_id)
      .filter((value): value is string => typeof value === 'string' && value.length > 0);
    const retryRequest: RetryRequest = {
      conversationId: currentConversation.id,
      content: trimmedContent,
      mentionedAgents,
      files: normalizedFiles,
    };
    
    const userMessage: UIMessage = {
      id: generateId(),
      role: 'user',
      content: trimmedContent,
      timestamp: new Date().toISOString(),
      files: normalizedFiles,
    };
    
    addMessage(currentConversation.id, userMessage);
    setIsLoading(true);
    setStreamState('connecting');
    setShowReconnect(false);
    setLastFailedRequest(null);
    setLastInterruptedRequest(null);
    setLastInterruptedTurnId(null);
    setLastInterruptedMessageId(null);
    
    const agentMessages = new Map<string, StreamMessageEntry>();

    const findPendingEntry = (targetAgentId: string): [string, StreamMessageEntry] | undefined => {
      for (const [key, entry] of agentMessages.entries()) {
        if (entry.agentId === targetAgentId && entry.phase === 'pending') {
          return [key, entry];
        }
      }
      return undefined;
    };

    const localAbortController = new AbortController();
    const requestRef = { id: null as string | null };
    activeRequestPayloadRef.current = retryRequest;
    activeTurnIdRef.current = userMessage.id;
    abortControllerRef.current = localAbortController;
    currentRequestIdRef.current = null;

    const streamPromise = (async () => {
      try {
        const sessionKey = `web:${currentConversation.id}`;
        
        await chatService.streamChat({
          message: trimmedContent,
          sessionKey,
          files: uploadedFiles,
          fileIds,
          conversationId: currentConversation.id,
          conversationType: currentConversation.type,
          agentId: currentConversation.type === ConversationType.DM ? currentConversation.targetId : undefined,
          teamId: currentConversation.type === ConversationType.TEAM ? currentConversation.targetId : undefined,
          groupChat: currentConversation.type === ConversationType.TEAM,
          mentionedAgents,
          timeout: 120000,
          connectTimeout: 15000,
          onStateChange: (state) => {
            setStreamState(state);
            if (state === 'timeout' || state === 'error') {
              setShowReconnect(true);
            }
          },
          onRequestStart: (requestId) => {
            requestRef.id = requestId;
            currentRequestIdRef.current = requestId;
          },
          onChunk: (event) => {
          const eventData = event as unknown as Record<string, unknown>;
          const eventType = (eventData.event as string) || (eventData.type as string);
          const agentId = eventData.agent_id as string | undefined;
          const turnId = eventData.turn_id as string | undefined;
          const messageIdFromEvent = eventData.message_id as string | undefined;
          const streamKey = messageIdFromEvent || turnId || (agentId ? `${agentId}:${String(eventData.agent_index ?? '0')}` : 'main');
          const streamEntry = agentMessages.get(streamKey);
          const matchedStreamEntry = streamEntry
            || (messageIdFromEvent ? Array.from(agentMessages.values()).find((entry) => entry.messageId === messageIdFromEvent) : undefined)
            || (turnId ? Array.from(agentMessages.values()).find((entry) => entry.turnId === turnId) : undefined)
            || (agentId ? Array.from(agentMessages.values()).find((entry) => entry.agentId === agentId && entry.phase !== 'done') : undefined);
          
          // Agent 开始响应 - 为每个 Agent 创建独立的消息
          if (eventType === 'agent_start' || eventType === 'request_start') {
            const agentName = eventData.agent_name as string;
            if (agentId) {
              const pendingEntryMatch = findPendingEntry(agentId);
              if (streamEntry) {
                streamEntry.phase = 'active';
                if (turnId) {
                  streamEntry.turnId = turnId;
                }
                updateMessage(currentConversation.id, streamEntry.messageId, {
                  turnId,
                  requestId: requestRef.id || undefined,
                  agentId,
                  agentName,
                  isStreaming: true,
                  statusMessage: streamEntry.content ? '正在输入...' : '已接棒，开始处理...',
                });
              } else if (pendingEntryMatch) {
                const [pendingKey, pendingEntry] = pendingEntryMatch;
                pendingEntry.phase = 'active';
                pendingEntry.turnId = turnId;
                if (pendingKey !== streamKey) {
                  agentMessages.delete(pendingKey);
                }
                agentMessages.set(streamKey, pendingEntry);
                updateMessage(currentConversation.id, pendingEntry.messageId, {
                  turnId,
                  requestId: requestRef.id || undefined,
                  agentId,
                  agentName,
                  isStreaming: true,
                  statusMessage: pendingEntry.content ? '正在输入...' : '已接棒，开始处理...',
                });
              } else {
                const messageId = messageIdFromEvent || generateId();
                const newMessage: UIMessage = {
                  id: messageId,
                  role: 'assistant',
                  content: '',
                  turnId: turnId,
                  requestId: requestRef.id || undefined,
                  agentId: agentId,
                  agentName: agentName,
                  isStreaming: true,
                  statusMessage: '正在输入...',
                  executionSteps: [],
                  metadata: {},
                };
                agentMessages.set(streamKey, {
                  messageId,
                  content: '',
                  turnId,
                  agentId,
                  phase: 'active',
                  executionSteps: [],
                });
                addMessage(currentConversation.id, newMessage);
              }
            }
            if (agentId) {
              addTypingAgent(currentConversation.id, agentId);
            }
          }
          // 处理 agent_mentioned 事件 - 当一个 agent 提到另一个 agent 时
          else if (eventType === 'agent_mentioned') {
            const mentionedAgentId = eventData.agent_id as string;
            const mentionedAgentName = eventData.agent_name as string;
            const mentionedByName = eventData.mentioned_by_name as string | undefined;
            const handoffMode = eventData.handoff_mode as string | undefined;
            const handoffPreview = eventData.handoff_preview as string | undefined;
            const pendingEntryMatch = mentionedAgentId ? findPendingEntry(mentionedAgentId) : undefined;
            if (mentionedAgentId && !pendingEntryMatch) {
              const pendingKey = `pending:${mentionedAgentId}:${generateId()}`;
              const messageId = messageIdFromEvent || generateId();
              const waitingStatus = handoffMode === 'summary'
                ? '已收到交棒，等待回来总结'
                : handoffMode === 'continue'
                  ? '已收到交棒，等待继续下一轮'
                  : '已被提及，等待响应...';
              const newMessage: UIMessage = {
                id: messageId,
                role: 'assistant',
                content: '',
                turnId: turnId,
                requestId: requestRef.id || undefined,
                agentId: mentionedAgentId,
                agentName: mentionedAgentName,
                isStreaming: true,
                statusMessage: waitingStatus,
                executionSteps: [],
                metadata: {
                  ...(mentionedByName ? { handoff_from_name: mentionedByName } : {}),
                  handoff_to_name: mentionedAgentName,
                  ...(handoffMode ? { handoff_mode: handoffMode } : {}),
                  ...(handoffPreview ? { handoff_preview: handoffPreview } : {}),
                },
              };
              agentMessages.set(pendingKey, {
                messageId,
                content: '',
                turnId,
                agentId: mentionedAgentId,
                phase: 'pending',
                executionSteps: [],
              });
              addMessage(currentConversation.id, newMessage);
              addTypingAgent(currentConversation.id, mentionedAgentId);
            }
          }
          // 处理 thinking 事件 - 显示思考过程
          else if (eventType === 'thinking') {
            if (agentId && matchedStreamEntry) {
              const agentMsg = matchedStreamEntry;
              updateMessage(currentConversation.id, agentMsg.messageId, {
                executionSteps: agentMsg.executionSteps,
                isThinking: true,
                statusMessage: '正在思考...',
              });
            }
          }
          // 处理 status 事件 - 显示状态更新
          else if (eventType === 'status') {
            const statusMessage = eventData.message as string;
            if (agentId && matchedStreamEntry) {
              const agentMsg = matchedStreamEntry;
              updateMessage(currentConversation.id, agentMsg.messageId, {
                statusMessage: statusMessage,
              });
            }
          }
          // 处理流式文本内容（后端当前发送 progress 快照）
          else if (eventType === 'progress' || eventType === 'content') {
            const isToolHint = eventData.tool_hint as boolean;
            const content = eventData.content as string;
            // 如果是 tool_hint，不直接显示在消息内容中
            if (matchedStreamEntry && !isToolHint) {
              const agentMsg = matchedStreamEntry;
              agentMsg.content = content || '';
              agentMsg.phase = 'active';
              agentMsg.executionSteps = updateLatestRunningExecutionStep(
                agentMsg.executionSteps,
                (step) => (step.type || '').toLowerCase().includes('thinking'),
                {
                  reasoning_content: content,
                  content,
                },
              );
              updateMessage(currentConversation.id, agentMsg.messageId, {
                content: agentMsg.content,
                isThinking: false,
                executionSteps: agentMsg.executionSteps,
              });
            }
          }
          // 处理工具开始事件
          else if (eventType === 'tool_start') {
            const toolName = eventData.tool_name as string | undefined;
            const argumentsPayload = eventData.arguments as Record<string, unknown> | undefined;
            if (agentId && matchedStreamEntry) {
              const agentMsg = matchedStreamEntry;
              agentMsg.executionSteps = updateLatestRunningExecutionStep(
                agentMsg.executionSteps,
                (step) => (step.type || '').toLowerCase().includes('tool'),
                {
                  toolName,
                  arguments: argumentsPayload,
                },
              );
              updateMessage(currentConversation.id, agentMsg.messageId, {
                executionSteps: agentMsg.executionSteps,
                isThinking: false,
                statusMessage: toolName ? `正在执行工具: ${toolName}` : '正在执行工具...',
              });
            }
          }
          // 处理工具结果事件
          else if (eventType === 'tool_result') {
            const toolName = eventData.tool_name as string | undefined;
            const result = eventData.result as string | undefined;
            const executionTime = eventData.execution_time as number | undefined;
            if (agentId && matchedStreamEntry) {
              const agentMsg = matchedStreamEntry;
              agentMsg.executionSteps = updateLatestRunningExecutionStep(
                agentMsg.executionSteps,
                (step) => (step.type || '').toLowerCase().includes('tool'),
                {
                  toolName,
                  result,
                  executionTime,
                },
              );
              updateMessage(currentConversation.id, agentMsg.messageId, {
                executionSteps: agentMsg.executionSteps,
                statusMessage: toolName ? `${toolName} 已返回结果` : '工具执行已返回结果',
              });
            }
          }
          else if (eventType === 'memory_sources') {
            const sources = Array.isArray(eventData.sources) ? eventData.sources : [];
            const recall = eventData.recall && typeof eventData.recall === 'object' ? eventData.recall as Record<string, unknown> : undefined;
            if (agentId && matchedStreamEntry) {
              const agentMsg = matchedStreamEntry;
              const existingMessage = getMessages(currentConversation.id).find((message) => message.id === agentMsg.messageId);
              updateMessage(currentConversation.id, agentMsg.messageId, {
                metadata: {
                  ...(existingMessage?.metadata || {}),
                  _memory_sources: sources,
                  ...(recall ? { _memory_recall: recall } : {}),
                },
              });
            }
          }
          // 处理 step_start 事件 - 显示步骤开始
          else if (eventType === 'step_start') {
            const stepId = (eventData.step_id as string) || generateId();
            const stepType = (eventData.step_type as string) || 'step';
            const title = (eventData.title as string) || inferExecutionStepTitle(stepType);
            if (agentId && matchedStreamEntry) {
              const agentMsg = matchedStreamEntry;
              let statusText: string | undefined;
              if (stepType === 'thinking') {
                statusText = '正在思考...';
              } else if (stepType === 'response') {
                statusText = '正在回复...';
              } else if (stepType === 'tool_call') {
                statusText = '正在执行工具...';
              } else if (stepType === 'compression') {
                statusText = '正在压缩上下文...';
              }
              agentMsg.executionSteps = upsertExecutionStep(agentMsg.executionSteps, {
                id: stepId,
                type: stepType,
                title,
                status: 'running',
                timestamp: new Date().toISOString(),
              });
              updateMessage(currentConversation.id, agentMsg.messageId, {
                executionSteps: agentMsg.executionSteps,
                isThinking: stepType === 'thinking',
                statusMessage: statusText,
              });
            }
          }
          // 处理 step_complete 事件 - 显示步骤完成结果
          else if (eventType === 'step_complete') {
            const stepId = eventData.step_id as string | undefined;
            const status = normalizeExecutionStepStatus(eventData.status as string | undefined);
            const details = eventData.details as Record<string, unknown> | undefined;
            if (agentId && matchedStreamEntry) {
              const agentMsg = matchedStreamEntry;
              const existingStep = stepId
                ? agentMsg.executionSteps.find((step) => step.id === stepId)
                : undefined;
              const mergedDetails = existingStep?.details
                ? { ...existingStep.details, ...(details || {}) }
                : details;
              const resolvedType = inferExecutionStepType(existingStep?.type, mergedDetails);
              const resolvedTitle = inferExecutionStepTitle(resolvedType, existingStep?.title, mergedDetails);
              agentMsg.executionSteps = upsertExecutionStep(agentMsg.executionSteps, {
                id: stepId || generateId(),
                type: resolvedType,
                title: resolvedTitle,
                status,
                timestamp: existingStep?.timestamp || new Date().toISOString(),
                details: mergedDetails,
              });

              let statusMessage: string | undefined;
              let isThinking = false;
              if (resolvedType === 'thinking') {
                statusMessage = status === 'error' || status === 'failed'
                  ? '思考阶段失败'
                  : '思考完成，准备回复...';
              } else if (resolvedType === 'tool_call') {
                statusMessage = status === 'error' || status === 'failed'
                  ? '工具执行失败'
                  : '工具执行完成';
              } else if (resolvedType === 'response') {
                statusMessage = status === 'error' || status === 'failed'
                  ? '回复生成失败'
                  : '回复已生成';
              }

              const responseContent = resolvedType === 'response' && typeof mergedDetails?.content === 'string'
                ? mergedDetails.content
                : undefined;
              if (responseContent) {
                agentMsg.content = responseContent;
              }

              updateMessage(currentConversation.id, agentMsg.messageId, {
                content: responseContent || agentMsg.content,
                executionSteps: agentMsg.executionSteps,
                isThinking,
                statusMessage,
              });
            }
          }
          // 处理 agent_done 事件
          else if (eventType === 'agent_done' || eventType === 'request_end') {
            const finalContentFromEvent = eventData.content as string;
            if (matchedStreamEntry) {
              const agentMsg = matchedStreamEntry;
              const existingMessage = getMessages(currentConversation.id).find((message) => message.id === agentMsg.messageId);
              const normalizedError = normalizeAssistantErrorContent(finalContentFromEvent || agentMsg.content);
              const finalContent = normalizedError.content;
              const providerError = normalizeProviderErrorPayload(eventData.provider_error);
              const isProviderError = Boolean(providerError) || normalizedError.isProviderError;
              agentMsg.phase = 'done';
              if (finalContent) {
                agentMsg.content = finalContent;
              }
              updateMessage(currentConversation.id, agentMsg.messageId, {
                content: finalContent,
                isStreaming: false,
                isThinking: false,
                statusMessage: undefined,
                executionSteps: agentMsg.executionSteps,
                metadata: {
                  ...(existingMessage?.metadata || {}),
                  ...(providerError ? { _provider_error: providerError } : {}),
                  ...(Array.isArray(eventData.memory_sources) && eventData.memory_sources.length > 0
                    ? { _memory_sources: eventData.memory_sources }
                    : {}),
                  ...(eventData.memory_recall && typeof eventData.memory_recall === 'object'
                    ? { _memory_recall: eventData.memory_recall }
                    : {}),
                },
                isError: isProviderError,
                errorKind: isProviderError ? 'provider' : undefined,
                retryable: providerError?.retryable ?? isProviderError,
                retryPayload: isProviderError
                  ? {
                      content: retryRequest.content,
                      mentionedAgents: retryRequest.mentionedAgents,
                      files: retryRequest.files,
                    }
                  : undefined,
              });
              removeTypingAgent(currentConversation.id, agentId || agentMsg.agentId);
              if (isProviderError) {
                setLastFailedRequest(retryRequest);
                setShowReconnect(true);
              }
            }
          }
          // 所有响应完成
          else if (eventType === 'done') {
            // 所有消息已完成，不需要额外操作
          }
          // 后端处理失败
          else if (eventType === 'error' || eventType === 'agent_error') {
            const normalizedError = normalizeAssistantErrorContent(
              (eventData.content as string) || (eventData.error as string) || '抱歉，发生了错误。请重试。',
            );
            const errorContent = normalizedError.content || '抱歉，发生了错误。请重试。';
            const errorKind = normalizedError.isProviderError ? 'provider' : 'stream';
            const resolvedAgentId = agentId || 'main';
            if (!streamEntry) {
              const messageId = messageIdFromEvent || generateId();
              agentMessages.set(streamKey, {
                messageId,
                content: errorContent,
                turnId,
                agentId: resolvedAgentId,
                phase: 'done',
                executionSteps: [],
              });
              addMessage(currentConversation.id, {
                id: messageId,
                role: 'assistant',
                content: errorContent,
                turnId,
                agentId: resolvedAgentId,
                agentName: undefined,
                isStreaming: false,
                isThinking: false,
                timestamp: new Date().toISOString(),
                isError: true,
                errorKind: errorKind,
                retryable: true,
                executionSteps: [],
                retryPayload: {
                  content: retryRequest.content,
                  mentionedAgents: retryRequest.mentionedAgents,
                  files: retryRequest.files,
                },
              });
            } else {
              const agentMsg = streamEntry;
              agentMsg.content = errorContent;
              agentMsg.phase = 'done';
              agentMsg.executionSteps = finalizeRunningExecutionSteps(
                agentMsg.executionSteps,
                'error',
                { error: errorContent },
              );
              updateMessage(currentConversation.id, agentMsg.messageId, {
                content: errorContent,
                isStreaming: false,
                isThinking: false,
                statusMessage: undefined,
                executionSteps: agentMsg.executionSteps,
                isError: true,
                errorKind: errorKind,
                retryable: true,
                retryPayload: {
                  content: retryRequest.content,
                  mentionedAgents: retryRequest.mentionedAgents,
                  files: retryRequest.files,
                },
              });
            }
            removeTypingAgent(currentConversation.id, resolvedAgentId);
            setLastFailedRequest(retryRequest);
            setShowReconnect(true);
          }
          // 用户手动停止或服务端终止
          else if (eventType === 'stopped') {
            agentMessages.forEach((agentMsg) => {
              agentMsg.phase = 'done';
              agentMsg.executionSteps = finalizeRunningExecutionSteps(
                agentMsg.executionSteps,
                'stopped',
                { stopped: true },
              );
              updateMessage(currentConversation.id, agentMsg.messageId, {
                content: agentMsg.content || '已停止生成。',
                isStreaming: false,
                isThinking: false,
                statusMessage: undefined,
                executionSteps: agentMsg.executionSteps,
              });
              removeTypingAgent(currentConversation.id, agentMsg.agentId);
            });
          }
          // 讨论停止
          else if (eventType === 'discussion_stopped') {
            const systemMessage: UIMessage = {
              id: generateId(),
              role: 'assistant',
              content: (eventData.content as string) || '讨论已停止。你可以继续发送消息开始新的对话。',
              isStreaming: false,
              timestamp: new Date().toISOString(),
            };
            addMessage(currentConversation.id, systemMessage);
          }
          },
          signal: localAbortController.signal,
        });
      } catch (error: unknown) {
        if (error instanceof ChatStreamError && error.code === 'aborted') {
          agentMessages.forEach((agentMsg) => {
            agentMsg.phase = 'done';
            agentMsg.executionSteps = finalizeRunningExecutionSteps(
              agentMsg.executionSteps,
              'stopped',
              { stopped: true },
            );
            updateMessage(currentConversation.id, agentMsg.messageId, {
              content: agentMsg.content || '已停止生成。',
              isStreaming: false,
              isThinking: false,
              statusMessage: undefined,
              executionSteps: agentMsg.executionSteps,
            });
            removeTypingAgent(currentConversation.id, agentMsg.agentId);
          });
        } else {
          console.error('Chat error:', error);
          const failure = resolveStreamFailureMessage(error);
          if (agentMessages.size === 0) {
            addMessage(currentConversation.id, {
              id: generateId(),
              role: 'assistant',
              content: failure.content,
              timestamp: new Date().toISOString(),
              isStreaming: false,
              isThinking: false,
              isError: true,
              errorKind: failure.errorKind,
              retryable: true,
              executionSteps: [],
              retryPayload: {
                content: retryRequest.content,
                mentionedAgents: retryRequest.mentionedAgents,
                files: retryRequest.files,
              },
            });
          }
          agentMessages.forEach((agentMsg) => {
            agentMsg.phase = 'done';
            agentMsg.executionSteps = finalizeRunningExecutionSteps(
              agentMsg.executionSteps,
              'error',
              { error: failure.content },
            );
            updateMessage(currentConversation.id, agentMsg.messageId, {
              content: agentMsg.content || failure.content,
              isStreaming: false,
              isThinking: false,
              statusMessage: undefined,
              executionSteps: agentMsg.executionSteps,
              isError: true,
              errorKind: failure.errorKind,
              retryable: true,
              retryPayload: {
                content: retryRequest.content,
                mentionedAgents: retryRequest.mentionedAgents,
                files: retryRequest.files,
              },
            });
            removeTypingAgent(currentConversation.id, agentMsg.agentId);
          });
          setLastFailedRequest(retryRequest);
          setShowReconnect(true);
        }
      } finally {
        setIsLoading(false);
        setStreamState(null);
        if (activeRequestPayloadRef.current === retryRequest) {
          activeRequestPayloadRef.current = null;
        }
        if (activeTurnIdRef.current === userMessage.id) {
          activeTurnIdRef.current = null;
        }
        if (abortControllerRef.current === localAbortController) {
          abortControllerRef.current = null;
        }
        if (!requestRef.id || currentRequestIdRef.current === requestRef.id) {
          currentRequestIdRef.current = null;
        }
      }
    })();

    activeStreamPromiseRef.current = streamPromise;
    try {
      await streamPromise;
    } finally {
      if (activeStreamPromiseRef.current === streamPromise) {
        activeStreamPromiseRef.current = null;
      }
      const currentDmAgent = currentConversation.type === ConversationType.DM
        ? agents.find((agent) => agent.id === currentConversation.agentIds?.[0])
        : undefined;
      if (currentConversation.type === ConversationType.DM && currentDmAgent && (currentDmAgent.setup_required || currentDmAgent.bootstrap_setup_pending)) {
        void refreshAgents();
      }
    }
  }, [currentConversation, agents, addMessage, updateMessage, addTypingAgent, removeTypingAgent, isOnline, requestStopGeneration, waitForActiveStreamToSettle, toast, showInterruptNotice, refreshAgents]);

  const handleRetryLastRequest = useCallback(async () => {
    if (!currentConversation || !lastFailedRequest || isLoading) return;
    if (lastFailedRequest.conversationId !== currentConversation.id) return;
    await handleSendMessage(lastFailedRequest.content, lastFailedRequest.mentionedAgents, lastFailedRequest.files);
  }, [currentConversation, lastFailedRequest, isLoading, handleSendMessage]);

  const handleRetryMessage = useCallback(async (message: UIMessage) => {
    if (!message.retryPayload || isLoading) return;
    await handleSendMessage(message.retryPayload.content, message.retryPayload.mentionedAgents, message.retryPayload.files);
  }, [handleSendMessage, isLoading]);

  const handleResumeInterruptedRequest = useCallback(async () => {
    if (!currentConversation || !lastInterruptedRequest || isLoading) return;
    if (lastInterruptedRequest.conversationId !== currentConversation.id) return;
    dismissInterruptNotice();
    await handleSendMessage(lastInterruptedRequest.content, lastInterruptedRequest.mentionedAgents, lastInterruptedRequest.files);
  }, [currentConversation, lastInterruptedRequest, isLoading, dismissInterruptNotice, handleSendMessage]);
  
  const messageTurns = useMemo(() => buildMessageTurns(messages), [messages]);
  const historySearchMatches = useMemo<HistorySearchMatch[]>(() => {
    const query = normalizeSearchText(historySearchQuery);
    if (!query) {
      return [];
    }

    const matches: HistorySearchMatch[] = [];
    messageTurns.forEach((turn, turnIndex) => {
      if (turn.userMessage) {
        const normalized = normalizeSearchText(turn.userMessage.content);
        if (normalized.includes(query)) {
          matches.push({
            key: `user:${turn.id}`,
            turnId: turn.id,
            role: 'user',
            label: `第 ${turnIndex + 1} 轮 · 你的消息`,
            preview: buildSearchPreview(turn.userMessage.content),
          });
        }
      }

      turn.responseGroups.forEach((group, groupIndex) => {
        const content = group
          .map((message) => cleanHistoryMessageContent(message.content || ''))
          .join('\n');
        const normalized = normalizeSearchText(content);
        if (!normalized.includes(query)) {
          return;
        }
        const firstMessage = group[0];
        matches.push({
          key: `${turn.id}:${groupIndex}`,
          turnId: turn.id,
          groupIndex,
          role: 'assistant',
          label: `第 ${turnIndex + 1} 轮 · ${firstMessage?.agentName || getAgentName(firstMessage?.agentId) || '助手'}`,
          preview: buildSearchPreview(content),
        });
      });
    });

    return matches;
  }, [historySearchQuery, messageTurns]);

  const activeHistoryMatch = historySearchMatches.length > 0
    ? historySearchMatches[Math.min(historySearchIndex, historySearchMatches.length - 1)]
    : null;

  useEffect(() => {
    setExpandedTurnIds({});
  }, [currentConversation?.id]);

  useEffect(() => {
    setHistorySearchQuery('');
    setHistorySearchIndex(0);
    setIsHistorySearchOpen(false);
    setActiveHistoryResultKey(null);
  }, [currentConversation?.id]);

  useEffect(() => {
    if (historySearchMatches.length === 0) {
      setHistorySearchIndex(0);
      setActiveHistoryResultKey(null);
      return;
    }
    if (historySearchIndex >= historySearchMatches.length) {
      setHistorySearchIndex(0);
    }
  }, [historySearchMatches, historySearchIndex]);

  useEffect(() => {
    if (!activeHistoryMatch) {
      return;
    }

    setActiveHistoryResultKey(activeHistoryMatch.key);
    setExpandedTurnIds((prev) => (
      prev[activeHistoryMatch.turnId]
        ? prev
        : { ...prev, [activeHistoryMatch.turnId]: true }
    ));

    const frame = window.requestAnimationFrame(() => {
      historyResultRefs.current[activeHistoryMatch.key]?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [activeHistoryMatch]);

  useEffect(() => {
    if (currentConversation?.type !== ConversationType.TEAM || messageTurns.length === 0) {
      return;
    }

    setExpandedTimelineTurnIds((prev) => {
      let changed = false;
      const next = { ...prev };

      messageTurns.forEach((turn) => {
        if (turn.responseGroups.length === 0 || next[turn.id] !== undefined) {
          return;
        }
        next[turn.id] = false;
        changed = true;
      });

      return changed ? next : prev;
    });
  }, [currentConversation?.type, messageTurns]);

  useEffect(() => {
    if (currentConversation?.type !== ConversationType.TEAM || messageTurns.length === 0) {
      return;
    }

    setExpandedTurnIds((prev) => {
      let changed = false;
      const next = { ...prev };

      messageTurns.forEach((turn) => {
        const isCollapsible = turn.relayCount > 1;
        if (!isCollapsible || next[turn.id] !== undefined) {
          return;
        }

        // Team history should load fully by default so stable relay steps are not
        // mistaken for missing history. Users can still collapse a turn manually.
        next[turn.id] = true;
        changed = true;
      });

      return changed ? next : prev;
    });
  }, [currentConversation?.type, messageTurns]);

  const toggleTurnExpanded = useCallback((turnId: string) => {
    setExpandedTurnIds((prev) => ({
      ...prev,
      [turnId]: !prev[turnId],
    }));
    setExpandedRelaySegments((prev) => {
      if (!prev[turnId]?.length) {
        return prev;
      }
      return {
        ...prev,
        [turnId]: [],
      };
    });
  }, []);

  const toggleRelaySegmentExpanded = useCallback((turnId: string, startIndex: number, endIndex: number) => {
    const isExpandedSegment = expandedRelaySegments[turnId]?.some(
      (segment) => segment.startIndex === startIndex && segment.endIndex === endIndex,
    );

    setExpandedRelaySegments((prev) => {
      const currentSegments = prev[turnId] || [];
      const exists = currentSegments.some((segment) => segment.startIndex === startIndex && segment.endIndex === endIndex);
      const nextSegments = exists
        ? currentSegments.filter((segment) => !(segment.startIndex === startIndex && segment.endIndex === endIndex))
        : [...currentSegments, { startIndex, endIndex }];

      return {
        ...prev,
        [turnId]: nextSegments,
      };
    });

    if (!isExpandedSegment) {
      setPendingRelayJump({ turnId, groupIndex: startIndex });
    }
  }, [expandedRelaySegments]);

  const jumpToRelayStep = useCallback((turnId: string, groupIndex: number) => {
    setPendingRelayJump({ turnId, groupIndex });
  }, []);

  const toggleTimelineExpanded = useCallback((turnId: string) => {
    setExpandedTimelineTurnIds((prev) => ({
      ...prev,
      [turnId]: !(prev[turnId] ?? true),
    }));
  }, []);

  useEffect(() => {
    if (!pendingRelayJump) {
      return;
    }

    const targetKey = `${pendingRelayJump.turnId}:${pendingRelayJump.groupIndex}`;
    const targetElement = relayGroupRefs.current[targetKey];
    if (!targetElement) {
      return;
    }

    targetElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setHighlightedRelayGroupKey(targetKey);
    setPendingRelayJump(null);

    if (relayHighlightTimerRef.current) {
      clearTimeout(relayHighlightTimerRef.current);
    }
    relayHighlightTimerRef.current = setTimeout(() => {
      setHighlightedRelayGroupKey((current) => (current === targetKey ? null : current));
      relayHighlightTimerRef.current = null;
    }, 2200);
  }, [pendingRelayJump, expandedTurnIds, messageTurns]);
  
  const getAgentName = (agentId?: string) => {
    if (!agentId) return undefined;
    return agents.find(a => a.id === agentId)?.name;
  };

  const currentDirectAgent = useMemo(() => {
    if (currentConversation?.type !== ConversationType.DM) {
      return selectedAgentId ? agents.find((agent) => agent.id === selectedAgentId) : undefined;
    }
    const conversationAgentId = currentConversation.agentIds?.[0];
    return agents.find((agent) => agent.id === conversationAgentId) || (selectedAgentId ? agents.find((agent) => agent.id === selectedAgentId) : undefined);
  }, [agents, currentConversation, selectedAgentId]);

  const currentTeamMembers = useMemo(() => {
    if (currentConversation?.type !== ConversationType.TEAM) {
      return [];
    }

    const liveTeam = teams.find((team) => team.id === currentConversation.targetId);
    const memberIds = liveTeam?.members || currentConversation.agentIds || [];
    return agents.filter((agent) => memberIds.includes(agent.id));
  }, [agents, currentConversation, teams]);

  const currentDirectAgentProfilePreset = useMemo(
    () => getAgentProfilePreset(currentDirectAgent?.profile),
    [currentDirectAgent?.profile],
  );

  const currentDirectAgentPermissionPreset = useMemo(
    () => getAgentPermissionPreset(currentDirectAgent?.tool_permission_profile),
    [currentDirectAgent?.tool_permission_profile],
  );

  const currentDirectOnboardingChecklist = useMemo(
    () => currentDirectAgentProfilePreset?.onboardingChecklist || DEFAULT_DM_ONBOARDING_CHECKLIST,
    [currentDirectAgentProfilePreset],
  );

  const currentDirectStarterPrompts = useMemo(
    () => currentDirectAgentProfilePreset?.starterPrompts || DEFAULT_DM_STARTER_PROMPTS,
    [currentDirectAgentProfilePreset],
  );

  const currentConversationCapabilities = useMemo<ToolCapability[]>(() => {
    if (!currentConversation) {
      return [];
    }

    const capabilityMap = new Map<string, ToolCapability>();
    const relevantAgents = currentConversation.type === ConversationType.TEAM
      ? currentTeamMembers
      : (currentDirectAgent ? [currentDirectAgent] : []);

    relevantAgents.forEach((agent) => {
      (agent.runtime_capabilities || []).forEach((capability) => {
        if (!capability.enabled) {
          return;
        }
        const existing = capabilityMap.get(capability.id);
        if (!existing) {
          capabilityMap.set(capability.id, {
            ...capability,
            tools: [...(capability.tools || [])],
          });
          return;
        }
        const mergedTools = Array.from(new Set([...(existing.tools || []), ...(capability.tools || [])]));
        capabilityMap.set(capability.id, { ...existing, tools: mergedTools });
      });
    });

    return Array.from(capabilityMap.values());
  }, [currentConversation, currentDirectAgent, currentTeamMembers]);

  const canRetryCurrentConversation = !!(
    currentConversation &&
    lastFailedRequest &&
    lastFailedRequest.conversationId === currentConversation.id
  );

  const canResumeInterruptedRequest = !!(
    currentConversation &&
    lastInterruptedRequest &&
    lastInterruptedRequest.conversationId === currentConversation.id
  );

  const highlightedRelayLocation = useMemo(
    () => parseRelayGroupKey(highlightedRelayGroupKey),
    [highlightedRelayGroupKey],
  );

  const currentConversationSummary = currentConversation?.type === ConversationType.TEAM
    ? `当前为团队接力会话，共 ${currentTeamMembers.length} 个成员。`
    : currentDirectAgentProfilePreset
      ? `当前为单聊会话，已按“${currentDirectAgentProfilePreset.label}”画像进入对话。`
      : '当前为单聊会话，消息会直接发给所选 Agent。';

  const handleHistorySearchMove = useCallback((direction: 'prev' | 'next') => {
    if (historySearchMatches.length === 0) {
      return;
    }
    setHistorySearchIndex((prev) => {
      if (direction === 'prev') {
        return (prev - 1 + historySearchMatches.length) % historySearchMatches.length;
      }
      return (prev + 1) % historySearchMatches.length;
    });
  }, [historySearchMatches.length]);

  const activeStreamingMessages = useMemo(
    () => messages.filter((message) => message.role === 'assistant' && message.isStreaming),
    [messages],
  );

  const relayStatusSnapshot = useMemo<RelayStatusSnapshot>(() => {
    const pendingAgentIds = new Set<string>();
    const pendingAgentNames: string[] = [];

    activeStreamingMessages.forEach((message) => {
      if (!message.statusMessage?.includes('等待响应')) {
        return;
      }

      const resolvedAgentName = message.agentName || getAgentName(message.agentId);
      if (!resolvedAgentName) {
        return;
      }

      const pendingKey = message.agentId || resolvedAgentName;
      if (!pendingAgentIds.has(pendingKey)) {
        pendingAgentIds.add(pendingKey);
        pendingAgentNames.push(resolvedAgentName);
      }
    });

    const activeProcessingMessage = [...activeStreamingMessages]
      .reverse()
      .find((message) => {
        const resolvedAgentName = message.agentName || getAgentName(message.agentId);
        if (!resolvedAgentName) {
          return false;
        }
        const pendingKey = message.agentId || resolvedAgentName;
        return !pendingAgentIds.has(pendingKey);
      });

    const activeAgentNames: string[] = [];
    typingAgents.forEach((agentId: string) => {
      if (pendingAgentIds.has(agentId)) {
        return;
      }
      const resolvedAgentName = getAgentName(agentId);
      if (resolvedAgentName && !activeAgentNames.includes(resolvedAgentName)) {
        activeAgentNames.push(resolvedAgentName);
      }
    });

    const activeProcessingAgentName = activeProcessingMessage
      ? (activeProcessingMessage.agentName || getAgentName(activeProcessingMessage.agentId))
      : activeAgentNames[0];

    return {
      pendingAgentNames,
      activeAgentNames,
      activeProcessingAgentName,
      activeProcessingMessage: activeProcessingMessage || null,
    };
  }, [activeStreamingMessages, getAgentName, typingAgents]);
  relayStatusSnapshotRef.current = relayStatusSnapshot;

  const sessionStatus = useMemo<SessionStatus | null>(() => {
    if (!isOnline) {
      return {
        tone: 'error',
        message: '网络已断开，当前无法发送消息。',
      };
    }

    if (showReconnect && canRetryCurrentConversation) {
      return {
        tone: 'warning',
        message: '本次响应失败，可重试上一条。',
        actionLabel: '重试上一条',
        onAction: handleRetryLastRequest,
        dismissible: true,
        onDismiss: () => setShowReconnect(false),
      };
    }

    if (showReconnect) {
      return {
        tone: 'warning',
        message: '连接已中断。',
        dismissible: true,
        onDismiss: () => setShowReconnect(false),
      };
    }

    if (interruptNotice) {
      const resumeActionLabel = canResumeInterruptedRequest && lastInterruptedRequest
        ? `继续：${buildRequestPreview(lastInterruptedRequest.content)}`
        : undefined;
      return {
        tone: interruptNotice.tone,
        message: interruptNotice.message,
        actionLabel: interruptNotice.tone === 'success' && canResumeInterruptedRequest
          ? resumeActionLabel
          : (interruptNotice.tone === 'success' ? '继续输入' : undefined),
        onAction: interruptNotice.tone === 'success'
          ? (canResumeInterruptedRequest ? handleResumeInterruptedRequest : requestInputFocus)
          : undefined,
        secondaryActionLabel: interruptNotice.tone === 'success' && canResumeInterruptedRequest ? '继续输入' : undefined,
        onSecondaryAction: interruptNotice.tone === 'success' && canResumeInterruptedRequest ? requestInputFocus : undefined,
        dismissible: true,
        onDismiss: dismissInterruptNotice,
      };
    }

    if (isLoading && streamState && STREAM_STATE_LABELS[streamState]) {
      const pendingAgentLabel = formatAgentNamesForStatus(relayStatusSnapshot.pendingAgentNames);
      const activeAgentLabel = relayStatusSnapshot.activeProcessingAgentName
        || formatAgentNamesForStatus(relayStatusSnapshot.activeAgentNames);

      if (pendingAgentLabel && activeAgentLabel) {
        return {
          tone: 'info',
          message: `${activeAgentLabel} 正在处理，已唤起 ${pendingAgentLabel} 待接力。按 Esc 可停止。`,
          actionLabel: currentConversation?.type === ConversationType.TEAM ? '停止接力' : '停止生成',
          onAction: handleStopGeneration,
          actionTone: 'danger',
        };
      }

      if (pendingAgentLabel) {
        return {
          tone: 'info',
          message: `已唤起 ${pendingAgentLabel}，等待接力。按 Esc 可停止。`,
          actionLabel: currentConversation?.type === ConversationType.TEAM ? '停止接力' : '停止生成',
          onAction: handleStopGeneration,
          actionTone: 'danger',
        };
      }

      if (relayStatusSnapshot.activeProcessingMessage?.isThinking && activeAgentLabel) {
        return {
          tone: 'info',
          message: `${activeAgentLabel} 正在思考... 按 Esc 可停止。`,
          actionLabel: currentConversation?.type === ConversationType.TEAM ? '停止接力' : '停止生成',
          onAction: handleStopGeneration,
          actionTone: 'danger',
        };
      }

      if (
        relayStatusSnapshot.activeProcessingMessage?.statusMessage &&
        !relayStatusSnapshot.activeProcessingMessage.content &&
        activeAgentLabel
      ) {
        const rawStatusMessage = relayStatusSnapshot.activeProcessingMessage.statusMessage;
        return {
          tone: 'info',
          message: rawStatusMessage.startsWith('正在')
            ? `${activeAgentLabel} ${rawStatusMessage}，按 Esc 可停止。`
            : `${activeAgentLabel}：${rawStatusMessage}，按 Esc 可停止。`,
          actionLabel: currentConversation?.type === ConversationType.TEAM ? '停止接力' : '停止生成',
          onAction: handleStopGeneration,
          actionTone: 'danger',
        };
      }

      if (activeAgentLabel) {
        return {
          tone: 'info',
          message: currentConversation?.type === ConversationType.TEAM
            ? `${activeAgentLabel} 正在接力处理中。按 Esc 可停止。`
            : `${activeAgentLabel} 正在生成回复。按 Esc 可停止。`,
          actionLabel: currentConversation?.type === ConversationType.TEAM ? '停止接力' : '停止生成',
          onAction: handleStopGeneration,
          actionTone: 'danger',
        };
      }

      return {
        tone: streamState === 'error' || streamState === 'timeout' ? 'warning' : 'info',
        message: `${STREAM_STATE_LABELS[streamState]}${streamState === 'error' || streamState === 'timeout' ? '' : '，按 Esc 可停止。'}`,
        actionLabel: currentConversation?.type === ConversationType.TEAM ? '停止接力' : '停止生成',
        onAction: handleStopGeneration,
        actionTone: 'danger',
      };
    }

    return null;
  }, [
    isOnline,
    showReconnect,
    canRetryCurrentConversation,
    handleRetryLastRequest,
    interruptNotice,
    canResumeInterruptedRequest,
    lastInterruptedRequest,
    handleResumeInterruptedRequest,
    dismissInterruptNotice,
    requestInputFocus,
    isLoading,
    streamState,
    relayStatusSnapshot,
    currentConversation?.type,
    handleStopGeneration,
  ]);
  
  return (
    <div className="flex h-full min-h-full overflow-hidden">
      <div className="hidden w-64 min-h-0 flex-shrink-0 flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="p-4 border-b border-slate-200">
          <h2 className="font-semibold text-slate-800">对话</h2>
        </div>
        
        <div className="flex-1 overflow-y-auto p-2">
          <div className="mb-4">
            <h3 className="px-2 py-1 text-xs font-medium text-slate-500 uppercase tracking-wider">私信</h3>
            <div className="space-y-1 mt-1">
              {agents.map((agent) => {
                const isSelected = selectedAgentId === agent.id;
                return (
                  <button
                    key={agent.id}
                    onClick={() => handleSelectAgent(agent.id)}
                    className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-colors ${
                      isSelected 
                        ? 'bg-blue-50 text-blue-700' 
                        : 'text-slate-700 hover:bg-slate-100'
                    }`}
                  >
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white text-sm font-medium">
                      {agent.name.charAt(0).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{agent.name}</p>
                      {agent.description && (
                        <p className="text-xs text-slate-500 truncate">{agent.description}</p>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
          
          {teams.length > 0 && (
            <div>
              <h3 className="px-2 py-1 text-xs font-medium text-slate-500 uppercase tracking-wider">团队</h3>
              <div className="space-y-1 mt-1">
                {teams.map((team) => {
                  const isSelected = selectedTeamId === team.id;
                  return (
                    <button
                      key={team.id}
                      onClick={() => handleSelectTeam(team.id)}
                      className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-colors ${
                        isSelected 
                          ? 'bg-blue-50 text-blue-700' 
                          : 'text-slate-700 hover:bg-slate-100'
                      }`}
                    >
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-400 to-violet-600 flex items-center justify-center text-white">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                        </svg>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{team.name}</p>
                        <p className="text-xs text-slate-500">{team.members.length} 个成员</p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
      
      <div className="flex min-h-0 flex-1 min-w-0 flex-col bg-white">
        {currentConversation ? (
          <>
            <div className="flex shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  {currentConversation.type === ConversationType.TEAM ? (
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-400 to-violet-600 flex items-center justify-center text-white">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                      </svg>
                    </div>
                  ) : (
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white font-semibold text-sm">
                      {currentConversation.name.charAt(0).toUpperCase()}
                    </div>
                  )}
                  <div className="min-w-0">
                    <h2 className="truncate font-semibold text-slate-800">{currentConversation.name}</h2>
                    <p className="text-xs text-slate-500">
                      {currentConversation.type === ConversationType.TEAM
                        ? `${currentTeamMembers.length} 个成员 · 可直接 @agent 接力`
                        : currentDirectAgentProfilePreset
                          ? `${currentDirectAgentProfilePreset.label} · ${currentDirectAgentProfilePreset.summary}`
                          : '适合直接问答与配置确认'}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      {currentConversation.type !== ConversationType.TEAM && currentDirectAgentProfilePreset && (
                        <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold ${currentDirectAgentProfilePreset.accent}`}>
                          协作画像 · {currentDirectAgentProfilePreset.label}
                        </span>
                      )}
                      {currentConversation.type !== ConversationType.TEAM && currentDirectAgentPermissionPreset && (
                        <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold ${currentDirectAgentPermissionPreset.accent}`}>
                          权限 · {currentDirectAgentPermissionPreset.label}
                        </span>
                      )}
                      {currentConversationCapabilities.length > 0 && (
                        <>
                          <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                            可用能力
                          </span>
                          {currentConversationCapabilities.slice(0, 6).map((capability) => {
                            const Icon = getCapabilityIcon(capability.id);
                            return (
                              <span
                                key={capability.id}
                                title={capability.description || capability.label}
                                className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium ${getCapabilityTone(capability.id)}`}
                              >
                                <Icon className="h-3.5 w-3.5" />
                                {capability.label}
                              </span>
                            );
                          })}
                          {currentConversationCapabilities.length > 6 && (
                            <span className="text-[11px] text-slate-400">
                              +{currentConversationCapabilities.length - 6}
                            </span>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>
              <div className="relative hidden shrink-0 md:flex md:flex-col md:items-end md:gap-2">
                <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${
                  currentConversation.type === ConversationType.TEAM
                    ? 'bg-violet-100 text-violet-700'
                    : 'bg-blue-100 text-blue-700'
                }`}>
                  {currentConversation.type === ConversationType.TEAM ? '团队接力' : '单聊'}
                </span>
                {messages.length > 0 && (
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setIsHistorySearchOpen((prev) => !prev)}
                      className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-medium shadow-sm transition-colors ${
                        isHistorySearchOpen || historySearchQuery
                          ? 'border-sky-200 bg-white text-sky-700'
                          : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      <Search className="h-3.5 w-3.5" strokeWidth={2} />
                      查找历史
                      {historySearchMatches.length > 0 && (
                        <span className="inline-flex min-w-6 items-center justify-center rounded-full bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700">
                          {historySearchIndex + 1}/{historySearchMatches.length}
                        </span>
                      )}
                    </button>

                    {(isHistorySearchOpen || historySearchQuery) && (
                      <div className="absolute right-0 top-full z-20 mt-2 w-[min(92vw,32rem)] rounded-2xl border border-slate-200 bg-white/95 p-3 shadow-xl backdrop-blur">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <div className="text-sm font-semibold text-slate-800">查找当前会话</div>
                            <div className="text-[11px] text-slate-400">共 {messageTurns.length} 轮，快捷键 Cmd/Ctrl + F</div>
                          </div>
                          <button
                            type="button"
                            onClick={() => setIsHistorySearchOpen(false)}
                            className="inline-flex h-8 w-8 items-center justify-center rounded-full text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
                            aria-label="关闭查找"
                          >
                            <X className="h-4 w-4" strokeWidth={2} />
                          </button>
                        </div>

                        <div className="mt-3">
                          <div className="relative">
                            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" strokeWidth={2} />
                            <input
                              ref={historySearchInputRef}
                              value={historySearchQuery}
                              onChange={(event) => {
                                setHistorySearchQuery(event.target.value);
                                setHistorySearchIndex(0);
                              }}
                              placeholder="输入关键词，快速定位聊天记录"
                              className="h-11 w-full rounded-xl border border-slate-200 bg-slate-50 pl-10 pr-10 text-sm text-slate-700 outline-none transition focus:border-sky-300 focus:bg-white focus:ring-2 focus:ring-sky-100"
                            />
                            {historySearchQuery && (
                              <button
                                type="button"
                                onClick={() => {
                                  setHistorySearchQuery('');
                                  setHistorySearchIndex(0);
                                  setActiveHistoryResultKey(null);
                                }}
                                className="absolute right-2 top-1/2 inline-flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full text-slate-400 transition hover:bg-slate-200 hover:text-slate-600"
                                aria-label="清空搜索"
                              >
                                <X className="h-3.5 w-3.5" strokeWidth={2} />
                              </button>
                            )}
                          </div>
                        </div>

                        <div className="mt-3 flex flex-wrap items-center gap-2">
                          <button
                            type="button"
                            onClick={() => handleHistorySearchMove('prev')}
                            disabled={historySearchMatches.length === 0}
                            className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            上一个
                          </button>
                          <button
                            type="button"
                            onClick={() => handleHistorySearchMove('next')}
                            disabled={historySearchMatches.length === 0}
                            className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            下一个
                          </button>
                          {historySearchMatches.length > 0 && (
                            <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700">
                              {historySearchIndex + 1} / {historySearchMatches.length}
                            </span>
                          )}
                        </div>

                        {activeHistoryMatch && (
                          <p className="mt-3 rounded-xl bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-500">
                            <span className="font-medium text-slate-700">{activeHistoryMatch.label}</span>
                            {' · '}
                            {activeHistoryMatch.preview}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
            
            <div className="relative min-h-0 flex-1">
              <div
                ref={chatContainerRef}
                className="min-h-0 h-full overflow-y-auto bg-slate-50 px-3 py-3 space-y-3"
              >
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-slate-400">
                  {isHistoryLoading ? (
                    <div
                      data-testid="chat-history-loading"
                      className="w-full max-w-2xl space-y-4 rounded-[28px] border border-slate-200 bg-white/80 px-5 py-6 shadow-sm"
                    >
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 animate-pulse rounded-2xl bg-slate-200" />
                        <div className="space-y-2">
                          <div className="h-3 w-32 animate-pulse rounded-full bg-slate-200" />
                          <div className="h-3 w-48 animate-pulse rounded-full bg-slate-100" />
                        </div>
                      </div>
                      <div className="space-y-3">
                        <div className="h-16 animate-pulse rounded-3xl bg-slate-100" />
                        <div className="ml-auto h-14 w-3/4 animate-pulse rounded-3xl bg-blue-100/70" />
                        <div className="h-16 w-5/6 animate-pulse rounded-3xl bg-slate-100" />
                      </div>
                      <p className="text-sm text-slate-500">
                        正在加载这段会话的历史消息...
                      </p>
                    </div>
                  ) : currentConversation.type !== ConversationType.TEAM && (currentDirectAgent?.setup_required || currentDirectAgent?.bootstrap_setup_pending) ? (
                    <div className="w-full max-w-2xl rounded-[28px] border border-accent-orange/30 bg-white px-6 py-6 text-left shadow-sm">
                      <div className="inline-flex rounded-full bg-accent-orange/10 px-3 py-1 text-xs font-semibold text-accent-orange">
                        首次私聊引导
                      </div>
                      <h3 className="mt-4 text-lg font-semibold text-slate-900">{currentDirectAgent.name} 还没有完成首次配置</h3>
                      <p className="mt-2 text-sm text-slate-600">
                        {currentDirectAgent?.setup_required
                          ? '先在多 Agent 管理里为它选择 provider 和 model，然后回到这里，用第一轮私聊继续约定职责、语气和协作边界。'
                          : '模型已经可用，但这位 Agent 的专属档案还处于首次引导阶段。建议先用一轮私聊明确职责、语气、边界和协作方式。'}
                      </p>
                      {currentDirectAgentProfilePreset && (
                        <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold ${currentDirectAgentProfilePreset.accent}`}>
                              协作画像 · {currentDirectAgentProfilePreset.label}
                            </span>
                            <span className="text-xs text-slate-500">{currentDirectAgentProfilePreset.summary}</span>
                          </div>
                          <p className="mt-2 text-xs text-slate-500">{currentDirectAgentProfilePreset.detail}</p>
                        </div>
                      )}
                      <div className="mt-4 flex flex-wrap gap-2">
                        {currentDirectAgent?.setup_required && (
                          <a
                            href="/teams"
                            className="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800"
                          >
                            去多 Agent 管理
                          </a>
                        )}
                        <button
                          onClick={() => applyInputDraftPreset(currentDirectStarterPrompts[0] || '开始完善配置吧，请先带我完成第一轮引导，逐步确认职责、语气、边界和协作方式。')}
                          className="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                        >
                          {currentDirectAgent?.setup_required ? '先准备引导问题' : '开始首轮引导'}
                        </button>
                      </div>
                      <div className="mt-4 rounded-2xl bg-slate-50 px-4 py-3 text-xs text-slate-600">
                        <div className="font-semibold text-slate-700">建议第一轮先确认</div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {currentDirectOnboardingChecklist.map((item) => (
                            <span key={item} className="rounded-full border border-slate-200 bg-white px-2.5 py-1">
                              {item}
                            </span>
                          ))}
                        </div>
                        <div className="mt-3 font-semibold text-slate-700">快捷开场</div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {currentDirectStarterPrompts.map((prompt) => (
                            <button
                              key={prompt}
                              type="button"
                              onClick={() => applyInputDraftPreset(prompt)}
                              className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1.5 text-left text-xs text-slate-700 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
                            >
                              {prompt}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="w-16 h-16 rounded-full bg-slate-200 flex items-center justify-center mb-4">
                        <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                        </svg>
                      </div>
                      <p className="text-lg font-medium">开始对话</p>
                      <p className="text-sm mt-1">
                        {currentConversation.type === ConversationType.TEAM
                          ? '发送消息，团队成员将回复你'
                          : '发送消息开始与 Agent 对话'}
                      </p>
                      {currentConversation.type !== ConversationType.TEAM && currentDirectAgentProfilePreset && (
                        <div className="mt-4 max-w-2xl rounded-[24px] border border-slate-200 bg-white px-4 py-4 text-left shadow-sm">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold ${currentDirectAgentProfilePreset.accent}`}>
                              协作画像 · {currentDirectAgentProfilePreset.label}
                            </span>
                            <span className="text-xs text-slate-500">{currentDirectAgentProfilePreset.summary}</span>
                          </div>
                          <div className="mt-3 text-xs font-semibold text-slate-700">推荐开场</div>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {currentDirectStarterPrompts.map((prompt) => (
                              <button
                                key={prompt}
                                type="button"
                                onClick={() => applyInputDraftPreset(prompt)}
                                className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-left text-xs text-slate-700 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
                              >
                                {prompt}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                      {currentConversationCapabilities.length > 0 && (
                        <div className="mt-4 flex max-w-2xl flex-wrap items-center justify-center gap-2">
                          {currentConversationCapabilities.slice(0, 6).map((capability) => {
                            const Icon = getCapabilityIcon(capability.id);
                            return (
                              <span
                                key={capability.id}
                                title={capability.description || capability.label}
                                className={`inline-flex items-center gap-1 rounded-full border px-3 py-1.5 text-xs font-medium ${getCapabilityTone(capability.id)}`}
                              >
                                <Icon className="h-3.5 w-3.5" />
                                {capability.label}
                              </span>
                            );
                          })}
                        </div>
                      )}
                      {currentConversation.type !== ConversationType.TEAM && currentDirectAgent && (
                        <p className="mt-3 max-w-2xl text-center text-xs text-slate-500">
                          例如可以直接让 {currentDirectAgent.name} 打开网页、安排提醒、读取文件或执行终端命令。
                        </p>
                      )}
                    </>
                  )}
                </div>
              ) : (
                <>
                  <div className="rounded-[28px] border border-slate-200 bg-white px-4 py-3 shadow-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                        会话概览
                      </span>
                      <span className="text-sm text-slate-600">{currentConversationSummary}</span>
                    </div>
                    {currentConversation.type === ConversationType.TEAM && (
                      <p className="mt-2 text-xs text-slate-500">
                        建议直接在输入框里使用 <code>@AgentName</code> 指定下一棒，由界面按回合展示接力过程。
                      </p>
                    )}
                  </div>

                  {messageTurns.map((turn, idx) => {
                    const participantNames = turn.participantAgentIds
                      .map((agentId) => getAgentName(agentId))
                      .filter(Boolean) as string[];
                    const isTeamTurn = currentConversation.type === ConversationType.TEAM;
                    const isInterruptedTurn = canResumeInterruptedRequest && lastInterruptedTurnId === turn.id;
                    const relayTimelineSteps = isTeamTurn
                      ? getRelayTimelineSteps(turn, getAgentName)
                      : [];
                    const isTimelineExpanded = relayTimelineSteps.length > 0
                      ? (expandedTimelineTurnIds[turn.id] ?? false)
                      : false;
                    const relayTimelineCompletedCount = relayTimelineSteps.filter((step) => step.state === 'done').length;
                    const relayTimelineActiveCount = relayTimelineSteps.filter((step) => step.state === 'active').length;
                    const relayTimelineWaitingCount = relayTimelineSteps.filter((step) => step.state === 'waiting').length;
                    const relayTimelineFailedCount = relayTimelineSteps.filter((step) => step.state === 'error').length;
                    const isCollapsibleRelay = isTeamTurn && turn.relayCount > 1;
                    const allowRelayCollapse = turn.relayCount > MAX_VISIBLE_RELAY_GROUPS_WITHOUT_COLLAPSE;
                    const isExpanded = isCollapsibleRelay
                      ? (expandedTurnIds[turn.id] ?? false)
                      : true;
                    const highlightedGroupIndex = highlightedRelayLocation?.turnId === turn.id
                      ? highlightedRelayLocation.groupIndex
                      : null;
                    const pendingJumpGroupIndex = pendingRelayJump?.turnId === turn.id
                      ? pendingRelayJump.groupIndex
                      : null;
                    const interruptedGroupIndex = isInterruptedTurn && lastInterruptedMessageId
                      ? turn.responseGroups.findIndex((group) => group.some((message) => message.id === lastInterruptedMessageId))
                      : -1;
                    const manualExpandedSegments = expandedRelaySegments[turn.id] || [];
                    const defaultVisibleRelayGroupIndexes = getDefaultVisibleRelayGroupIndexes(turn, {
                          highlightedGroupIndex,
                          pendingJumpGroupIndex,
                          interruptedGroupIndex,
                        });
                    const visibleRelayGroupIndexes = !allowRelayCollapse
                      ? new Set(turn.responseGroups.map((_, groupIndex) => groupIndex))
                      : isExpanded
                      ? new Set(turn.responseGroups.map((_, groupIndex) => groupIndex))
                      : (() => {
                          const nextIndexes = new Set(defaultVisibleRelayGroupIndexes);
                          manualExpandedSegments.forEach((segment) => {
                            for (let index = segment.startIndex; index <= segment.endIndex; index += 1) {
                              nextIndexes.add(index);
                            }
                          });
                          return nextIndexes;
                        })();
                    const relayRenderItems = buildRelayRenderItems(
                      turn.responseGroups,
                      visibleRelayGroupIndexes,
                      getAgentName,
                    );
                    const hiddenRelayCount = relayRenderItems.reduce(
                      (total, item) => total + (item.type === 'summary' ? item.hiddenCount : 0),
                      0,
                    );
                    const finalResponseGroup = turn.responseGroups.at(-1);
                    const finalResponderName = finalResponseGroup?.[0]
                      ? (finalResponseGroup[0].agentName || getAgentName(finalResponseGroup[0].agentId) || '助手')
                      : undefined;
                    const inspectedStep = highlightedGroupIndex !== null && highlightedGroupIndex >= 0
                      ? relayTimelineSteps.find((step) => step.groupIndex === highlightedGroupIndex)
                      : null;

                    return (
                      <section
                        key={`${turn.id}-${idx}`}
                        data-testid="chat-turn-card"
                        data-turn-id={turn.id}
                        data-expanded={isExpanded ? 'true' : 'false'}
                        className={`rounded-[22px] border px-3 py-2.5 shadow-sm ${
                          turn.hasError
                            ? 'border-red-200 bg-red-50/60'
                            : 'border-slate-200 bg-white'
                        }`}
                      >
                        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                              第 {idx + 1} 轮
                            </span>
                            {isTeamTurn && (
                              <span className="inline-flex items-center rounded-full bg-violet-100 px-2.5 py-1 text-xs font-medium text-violet-700">
                                {turn.relayCount > 1 ? `接力 ${turn.relayCount} 棒` : '单轮响应'}
                              </span>
                            )}
                            {turn.hasError && (
                              <span className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-1 text-xs font-medium text-red-700">
                                本轮出现失败
                              </span>
                            )}
                            {isInterruptedTurn && (
                              <span className="inline-flex items-center rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-700">
                                本轮在这里被中断
                              </span>
                            )}
                          </div>
                          {participantNames.length > 0 && (
                            <span className="text-xs text-slate-500">
                              响应者: {participantNames.join(' · ')}
                            </span>
                          )}
                        </div>

                        {isInterruptedTurn && (
                          <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-emerald-200 bg-emerald-50/80 px-4 py-3">
                            <div className="space-y-1">
                              <div className="flex flex-wrap items-center gap-2 text-xs text-emerald-800">
                                <span className="inline-flex items-center rounded-full bg-white px-2.5 py-1 font-semibold shadow-sm">
                                  中断恢复
                                </span>
                                <span>你可以直接续跑这一轮，或回到输入框改写后再发。</span>
                              </div>
                              {turn.userMessage?.content && (
                                <p className="text-sm text-emerald-900">
                                  上次请求: {buildRequestPreview(turn.userMessage.content, 40)}
                                </p>
                              )}
                            </div>
                            <div className="flex flex-wrap items-center gap-2">
                              <ChatIconButton
                                label="从这里继续"
                                dataTestId="chat-turn-resume"
                                onClick={() => void handleResumeInterruptedRequest()}
                                tone="success"
                                icon={<CirclePlay className="h-4 w-4" strokeWidth={2} />}
                              />
                              <ChatIconButton
                                label="继续输入"
                                onClick={requestInputFocus}
                                tone="success"
                                icon={<PencilLine className="h-4 w-4" strokeWidth={2} />}
                              />
                            </div>
                          </div>
                        )}

                        {relayTimelineSteps.length > 0 && (
                          <div className="mb-4 rounded-3xl border border-slate-200 bg-slate-50/80 px-4 py-3">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
                                <span className="inline-flex items-center rounded-full bg-white px-2.5 py-1 font-semibold text-slate-700 shadow-sm">
                                  接力时间线
                                </span>
                                <span>按棒次查看当前轮次的等待、处理中、完成与失败状态。</span>
                              </div>
                              <ChatIconButton
                                label={isTimelineExpanded ? '折叠接力时间线' : '展开接力时间线'}
                                dataTestId="chat-turn-timeline-toggle"
                                onClick={() => toggleTimelineExpanded(turn.id)}
                                icon={isTimelineExpanded
                                  ? <ChevronsUp className="h-4 w-4" strokeWidth={2} />
                                  : <ChevronsDown className="h-4 w-4" strokeWidth={2} />}
                              />
                            </div>
                            {!isTimelineExpanded ? (
                              <div
                                className="mt-3 flex flex-wrap items-center gap-2"
                                data-testid="chat-turn-timeline"
                                data-collapsed="true"
                              >
                                <span className="inline-flex items-center rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-700 shadow-sm">
                                  共 {relayTimelineSteps.length} 棒
                                </span>
                                {relayTimelineCompletedCount > 0 && (
                                  <span className="inline-flex items-center rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-700">
                                    已完成 {relayTimelineCompletedCount}
                                  </span>
                                )}
                                {relayTimelineActiveCount > 0 && (
                                  <span className="inline-flex items-center rounded-full bg-sky-100 px-2.5 py-1 text-xs font-medium text-sky-700">
                                    处理中 {relayTimelineActiveCount}
                                  </span>
                                )}
                                {relayTimelineWaitingCount > 0 && (
                                  <span className="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-700">
                                    等待中 {relayTimelineWaitingCount}
                                  </span>
                                )}
                                {relayTimelineFailedCount > 0 && (
                                  <span className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-1 text-xs font-medium text-red-700">
                                    失败 {relayTimelineFailedCount}
                                  </span>
                                )}
                                {finalResponderName && (
                                  <span className="text-xs text-slate-500">
                                    最终输出: {finalResponderName}
                                  </span>
                                )}
                              </div>
                            ) : (
                              <div
                                className="mt-3 flex flex-wrap items-center gap-2"
                                data-testid="chat-turn-timeline"
                              >
                                {relayTimelineSteps.map((step, timelineIdx) => {
                                  const isStepActive = highlightedGroupIndex === step.groupIndex
                                    || pendingJumpGroupIndex === step.groupIndex;

                                  return (
                                    <React.Fragment key={step.key}>
                                      <button
                                        type="button"
                                        data-testid="chat-turn-timeline-step"
                                        title={`定位到第 ${timelineIdx + 1} 棒：${step.label}`}
                                        aria-label={`定位到第 ${timelineIdx + 1} 棒：${step.label}`}
                                        onClick={() => jumpToRelayStep(turn.id, step.groupIndex)}
                                        className={`min-w-[144px] max-w-[220px] rounded-2xl border px-3 py-2 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md ${
                                          step.state === 'error'
                                            ? 'border-red-200 bg-red-50'
                                            : step.state === 'active'
                                              ? 'border-sky-200 bg-sky-50'
                                              : step.state === 'waiting'
                                                ? 'border-amber-200 bg-amber-50'
                                                : 'border-emerald-200 bg-emerald-50'
                                        } ${
                                          isStepActive
                                            ? 'ring-2 ring-sky-300 ring-offset-2 -translate-y-0.5 shadow-md'
                                            : 'hover:ring-1 hover:ring-slate-300'
                                        }`}
                                      >
                                        <div className="flex flex-wrap items-center gap-2">
                                          <span className="text-xs font-semibold text-slate-700">
                                            第 {timelineIdx + 1} 棒
                                          </span>
                                          <span
                                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${
                                              step.state === 'error'
                                                ? 'bg-red-100 text-red-700'
                                                : step.state === 'active'
                                                  ? 'bg-sky-100 text-sky-700'
                                                  : step.state === 'waiting'
                                                    ? 'bg-amber-100 text-amber-700'
                                                    : 'bg-emerald-100 text-emerald-700'
                                            }`}
                                          >
                                            {step.state === 'error'
                                              ? '失败'
                                              : step.state === 'active'
                                                ? '处理中'
                                                : step.state === 'waiting'
                                                  ? '等待中'
                                                  : '已完成'}
                                          </span>
                                          {step.isFinal && (
                                            <span className="inline-flex items-center rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600">
                                              最终输出
                                            </span>
                                          )}
                                        </div>
                                        <p className="mt-2 text-sm font-medium text-slate-800">
                                          {step.label}
                                        </p>
                                        <p className="mt-1 text-xs text-slate-500">
                                          {step.detail}
                                        </p>
                                      </button>
                                      {timelineIdx < relayTimelineSteps.length - 1 && (
                                        <div className="hidden h-px w-6 bg-slate-300 md:block" />
                                      )}
                                    </React.Fragment>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        )}

                        {isCollapsibleRelay && allowRelayCollapse && (
                          <div className="mb-4 rounded-3xl border border-violet-200 bg-violet-50/70 px-4 py-3 transition-all hover:border-violet-300 hover:bg-violet-50 hover:shadow-sm">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <div className="space-y-1">
                                <div className="flex flex-wrap items-center gap-2 text-xs text-violet-700">
                                  <span className="inline-flex items-center rounded-full bg-white px-2.5 py-1 font-semibold text-violet-700 shadow-sm">
                                    团队接力摘要
                                  </span>
                                  {finalResponderName && (
                                    <span>最终回复: {finalResponderName}</span>
                                  )}
                                  <span>参与成员: {participantNames.length}</span>
                                  {inspectedStep && (
                                    <span className="inline-flex items-center rounded-full bg-sky-100 px-2.5 py-1 font-medium text-sky-700 ring-1 ring-sky-200">
                                      正在查看第 {inspectedStep.groupIndex + 1} 棒
                                    </span>
                                  )}
                                </div>
                                <p className="text-sm text-slate-600">
                                  {inspectedStep
                                    ? `你当前定位在第 ${inspectedStep.groupIndex + 1} 棒，来自 ${inspectedStep.label}，状态为${inspectedStep.state === 'error' ? '失败' : inspectedStep.state === 'active' ? '处理中' : inspectedStep.state === 'waiting' ? '等待中' : '已完成'}。`
                                    : isExpanded
                                      ? '当前已展开完整接力过程，适合排查中间棒次的转交与失败点。'
                                      : hiddenRelayCount > 0
                                        ? `当前默认保留关键棒次，已折叠 ${hiddenRelayCount} 段稳定接力过程。`
                                        : '当前所有关键棒次都已直接展示，无需额外展开。'}
                                </p>
                              </div>
                              <ChatIconButton
                                label={isExpanded ? '收起接力过程' : '展开接力过程'}
                                dataTestId="chat-turn-toggle"
                                onClick={() => toggleTurnExpanded(turn.id)}
                                tone="violet"
                                icon={isExpanded
                                  ? <FoldVertical className="h-4 w-4" strokeWidth={2} />
                                  : <UnfoldVertical className="h-4 w-4" strokeWidth={2} />}
                              />
                            </div>
                          </div>
                        )}

                        <div className="space-y-3">
                          {turn.userMessage && (
                            <div
                              ref={(node) => {
                                historyResultRefs.current[`user:${turn.id}`] = node;
                              }}
                              className={`ml-auto max-w-[84%] scroll-mt-24 rounded-2xl border border-slate-200 bg-slate-50/80 px-1.5 py-1 ${
                                activeHistoryResultKey === `user:${turn.id}` ? 'ring-2 ring-sky-300 ring-offset-2' : ''
                              }`}
                            >
                              <MessageGroup
                                messages={[turn.userMessage]}
                                isUser
                                formatTime={formatTime}
                              />
                            </div>
                          )}

                          <div className="space-y-3">
                            {relayRenderItems.map((item) => {
                              if (item.type === 'summary') {
                                return (
                                  <div
                                    key={item.key}
                                    data-testid="chat-turn-collapsed-summary"
                                    data-turn-id={turn.id}
                                    data-start-index={String(item.startIndex)}
                                    data-end-index={String(item.endIndex)}
                                    data-hidden-count={String(item.hiddenCount)}
                                    className="group rounded-3xl border border-dashed border-slate-300 bg-slate-100/70 px-4 py-3 transition-all hover:border-slate-400 hover:bg-white hover:shadow-sm"
                                  >
                                    <div className="flex flex-wrap items-center justify-between gap-3">
                                      <div className="space-y-1">
                                        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
                                          <span className="inline-flex items-center rounded-full bg-white px-2.5 py-1 font-semibold text-slate-700 shadow-sm">
                                            已折叠 {item.hiddenCount} 棒稳定转交
                                          </span>
                                          <span>
                                            第 {item.startIndex + 1} 到 {item.endIndex + 1} 棒
                                          </span>
                                        </div>
                                        <p className="text-sm text-slate-600">
                                          {formatCollapsedRelayLabels(item.labels)}
                                        </p>
                                      </div>
                                      <div className="flex items-center gap-2">
                                        <ChatIconButton
                                          label="展开这一段接力过程"
                                          dataTestId="chat-turn-expand-segment"
                                          onClick={() => toggleRelaySegmentExpanded(turn.id, item.startIndex, item.endIndex)}
                                          className="group-hover:border-slate-400"
                                          icon={<ChevronsDown className="h-4 w-4" strokeWidth={2} />}
                                        />
                                        <ChatIconButton
                                          label="展开完整接力过程"
                                          onClick={() => toggleTurnExpanded(turn.id)}
                                          className="group-hover:border-slate-400"
                                          icon={<UnfoldVertical className="h-4 w-4" strokeWidth={2} />}
                                        />
                                      </div>
                                    </div>
                                  </div>
                                );
                              }

                              const firstMsg = item.group[0];
                              const agentName = firstMsg.agentName || getAgentName(firstMsg.agentId);
                              const relayGroupKey = `${turn.id}:${item.groupIndex}`;
                              const isHighlighted = highlightedRelayGroupKey === relayGroupKey;
                              const expandedSegmentAtStart = !isExpanded
                                ? isRelaySegmentStart(manualExpandedSegments, item.groupIndex)
                                : null;
                              const groupExecutionSteps = item.group.reduce<ExecutionStep[]>(
                                (allSteps, message) => mergeExecutionSteps(allSteps, message.executionSteps),
                                [],
                              );

                              return (
                                <div key={item.key} className="space-y-2">
                                  {expandedSegmentAtStart && (
                                    <div
                                      data-testid="chat-turn-expanded-segment"
                                      className="flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-sky-200 bg-sky-50/80 px-4 py-3 shadow-sm ring-1 ring-sky-200/70"
                                    >
                                      <div className="space-y-1">
                                        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
                                          <span className="inline-flex items-center rounded-full bg-white px-2.5 py-1 font-semibold text-sky-700 shadow-sm">
                                            已展开这一段
                                          </span>
                                          <span>
                                            第 {expandedSegmentAtStart.startIndex + 1} 到 {expandedSegmentAtStart.endIndex + 1} 棒
                                          </span>
                                        </div>
                                        <p className="text-sm text-slate-600">
                                          当前只补充展示这段稳定转交，并已自动定位到这一段的起始棒次；其余非关键棒次仍保持折叠。
                                        </p>
                                      </div>
                                      <ChatIconButton
                                        label="收起这一段接力过程"
                                        onClick={() => toggleRelaySegmentExpanded(
                                          turn.id,
                                          expandedSegmentAtStart.startIndex,
                                          expandedSegmentAtStart.endIndex,
                                        )}
                                        icon={<ChevronsUp className="h-4 w-4" strokeWidth={2} />}
                                      />
                                    </div>
                                  )}

                                  <div className="flex justify-start">
                                  <div
                                    ref={(node) => {
                                      relayGroupRefs.current[relayGroupKey] = node;
                                      historyResultRefs.current[relayGroupKey] = node;
                                    }}
                                    data-testid="chat-turn-group"
                                    data-turn-id={turn.id}
                                    data-group-index={String(item.groupIndex)}
                                    data-highlighted={isHighlighted ? 'true' : 'false'}
                                    className={`max-w-[84%] scroll-mt-24 rounded-2xl border px-1.5 py-1 ${
                                      firstMsg.isError
                                        ? 'border-red-200 bg-red-50/50'
                                        : 'border-slate-200 bg-slate-50/70'
                                    } ${
                                      isHighlighted || activeHistoryResultKey === relayGroupKey
                                        ? 'ring-2 ring-sky-300 ring-offset-2'
                                        : ''
                                    }`}
                                  >
                                    <MessageGroup
                                      messages={item.group}
                                      agentName={agentName}
                                      agentId={firstMsg.agentId}
                                      isUser={false}
                                      formatTime={formatTime}
                                      onRetryMessage={(message) => handleRetryMessage(message as UIMessage)}
                                    >
                                      <MessageExecutionCard
                                        steps={groupExecutionSteps}
                                        isStreaming={item.group.some((message) => message.isStreaming)}
                                      />
                                    </MessageGroup>
                                  </div>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      </section>
                    );
                  })}
                  
                  <TypingIndicator
                    agentNames={typingAgents
                      .map((id: string) => agents.find(a => a.id === id)?.name)
                      .filter(Boolean) as string[]
                    }
                  />
                  
                  <div ref={messagesEndRef} />
                </>
              )}
              </div>
              {!isNearBottom && (
                <button
                  type="button"
                  onClick={scrollToBottom}
                  className="absolute bottom-4 right-4 inline-flex items-center gap-1 rounded-full border border-sky-200 bg-white/95 px-3 py-2 text-xs font-medium text-sky-700 shadow-lg backdrop-blur transition hover:-translate-y-0.5 hover:bg-sky-50"
                >
                  <ArrowDown className="h-3.5 w-3.5" strokeWidth={2} />
                  回到底部
                </button>
              )}
            </div>
            
            <div className="relative shrink-0">
              <MessageInput
                conversationType={currentConversation.type}
                conversationName={currentConversation.name}
                agents={currentConversation.type === ConversationType.TEAM ? currentTeamMembers : agents}
                onSend={handleSendMessage}
                disabled={!isOnline}
                isLoading={isLoading}
                sessionStatus={sessionStatus}
                focusRequestKey={inputFocusRequestKey}
                draftPresetText={inputDraftPreset.text}
                draftPresetKey={inputDraftPreset.key}
                placeholder={
                  !isOnline ? '网络已断开，请检查网络连接' :
                  currentConversation.type === ConversationType.TEAM
                    ? '发送消息到团队... (使用 @ 提及 Agent)'
                    : currentDirectAgentProfilePreset
                      ? `给 ${currentConversation.name || 'Agent'} 发送消息，例如：${currentDirectAgentProfilePreset.placeholderHint}`
                      : `给 ${currentConversation.name || 'Agent'} 发送消息...`
                }
              />
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-slate-400 bg-slate-50">
            <div className="w-20 h-20 rounded-full bg-slate-200 flex items-center justify-center mb-4">
              <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <p className="text-xl font-medium">选择一个对话</p>
            <p className="text-sm mt-2">从左侧选择一个 Agent 或团队开始对话</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatPage;
