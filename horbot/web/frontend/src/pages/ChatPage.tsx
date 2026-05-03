import React, { Suspense, useDeferredValue, useState, useRef, useEffect, useCallback, useLayoutEffect, useMemo } from 'react';
import {
  ArrowDown,
  Bot,
  CalendarClock,
  ChevronsDown,
  ChevronsUp,
  CirclePlay,
  Globe,
  FolderOpen,
  ListChecks,
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
import { useI18n } from '../contexts/I18nContext';
import { useToast } from '../contexts/ToastContext';
import { resolveApiBase } from '../services/api';
import { useConversationStore } from '../stores/conversationStore';
import { ConversationType, conversationIdToSessionKey, sessionKeyToConversationId } from '../types/conversation';
import type { ExecutionStep, MessageFile } from '../types/conversation';
import { chatService, ChatStreamError } from '../services/chat';
import type { StreamState } from '../services/chat';
import type { ConversationState } from '../stores/conversationStore';
import { createAsyncResourceCache } from '../utils/asyncResourceCache';
import { lazyWithReload } from '../utils/lazyWithReload';
import {
  hasRenderableMessageFiles,
  normalizeMessageFiles,
  serializeMessageFiles,
} from './chat/messageFiles';
import {
  buildConversationMessagesUrl,
  buildConversationSearchUrl,
  buildSearchPreview,
  cleanHistoryMessageContent,
  estimateConversationTokens,
  findHistorySearchMatchIndexByMessageId,
  formatApproxTokenCount,
  normalizeSearchText,
  resolveHistorySearchSince,
} from './chat/historyUtils';
import {
  formatConversationHistoryMessages as formatHistoryMessages,
  mergeConversationHistoryMessages,
  type RawConversationHistoryMessage,
} from './chat/historyMessages';
import {
  normalizeAssistantErrorContent,
  normalizeProviderErrorPayload,
  resolveStreamFailureMessage,
} from './chat/streamErrors';
import {
  finalizeRunningExecutionSteps,
  inferExecutionStepTitle,
  inferExecutionStepType,
  mergeExecutionSteps,
  normalizeExecutionStepStatus,
  updateLatestRunningExecutionStep,
  upsertExecutionStep,
} from './chat/executionSteps';
import {
  buildInterruptSummary,
  buildMessageTurns,
  buildRelayRenderItems,
  buildRequestPreview,
  doesHistoryMessageReplaceStreamEntry,
  findReplacedStreamEntries,
  formatAgentNamesForStatus,
  formatRequestIdBadge,
  getDefaultVisibleRelayGroupIndexes,
  getRelayGroupState,
  getRelayGroupTransition,
  isRelaySegmentStart,
  MAX_VISIBLE_RELAY_GROUPS_WITHOUT_COLLAPSE,
  parseRelayGroupKey,
  resolveTurnRequestId,
} from './chat/turns';
import {
  CONVERSATION_HISTORY_PAGE_SIZE,
  CONVERSATION_HISTORY_SEARCH_CONTEXT,
  CONVERSATION_HISTORY_SEARCH_PAGE_SIZE,
  EMPTY_MESSAGES,
  EMPTY_TYPING_AGENTS,
  TURN_VIRTUALIZATION_ROW_GAP,
  TURN_VIRTUALIZATION_THRESHOLD,
} from './chat/types';
import { useTurnVirtualization } from './chat/useTurnVirtualization';
import type {
  AgentInfo,
  BatonNavigationNotice,
  ChatDirectoryBundle,
  ConversationHealth,
  ConversationHistoryPage,
  ConversationHistoryWindowState,
  ExpandedRelaySegment,
  HistoryLoadMode,
  HistorySearchMatch,
  HistorySearchTimeRange,
  InterruptNotice,
  MessageTurn,
  PendingRelayJump,
  RelayStatusSnapshot,
  RelayTimelineStep,
  RemoteHistorySearchMatch,
  RetryRequest,
  StreamMessageEntry,
  TeamInfo,
  ToolCapability,
  TranslateFn,
  UIMessage,
} from './chat/types';

const chatDirectoryCache = createAsyncResourceCache(
  async (): Promise<ChatDirectoryBundle> => {
    const [agentsResponse, externalAgentsResponse, teamsResponse] = await Promise.all([
      fetch('/api/agents'),
      fetch('/api/external-agents'),
      fetch('/api/teams'),
    ]);

    const [agentsData, externalAgentsData, teamsData] = await Promise.all([
      agentsResponse.json(),
      externalAgentsResponse.json(),
      teamsResponse.json(),
    ]);

    return {
      agents: agentsData.agents || [],
      externalAgents: (externalAgentsData.external_agents || []).map((agent: AgentInfo) => ({
        ...agent,
        external: true,
      })),
      teams: teamsData.teams || [],
    };
  },
  {
    ttlMs: 20_000,
    keyFn: () => 'chat-directory',
  },
);

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

const getCapabilityLabel = (t: TranslateFn, capability: ToolCapability): string => {
  switch (capability.id) {
    case 'files':
      return t('chat.capability.files');
    case 'terminal':
      return t('chat.capability.terminal');
    case 'web':
      return t('chat.capability.web');
    case 'browser':
      return t('chat.capability.browser');
    case 'tasks':
      return t('chat.capability.tasks');
    case 'relay':
      return t('chat.capability.relay');
    case 'mcp':
      return t('chat.capability.mcp');
    default:
      return capability.label;
  }
};

const resolveChatWebSocketUrl = (): string => {
  const apiBase = resolveApiBase();
  if (apiBase) {
    const url = new URL(apiBase);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    url.pathname = '/ws/chat';
    url.search = '';
    url.hash = '';
    return url.toString();
  }

  const url = new URL('/ws/chat', window.location.origin);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  return url.toString();
};

const shouldBootstrapRealtimeStreamEntry = (eventType: string): boolean => (
  eventType === 'thinking'
  || eventType === 'status'
  || eventType === 'progress'
  || eventType === 'content'
  || eventType === 'tool_start'
  || eventType === 'tool_result'
  || eventType === 'step_start'
  || eventType === 'step_complete'
);

const getRealtimeBootstrapStatusMessage = (
  t: TranslateFn,
  eventType: string,
  eventData: Record<string, unknown>,
): string => {
  if (eventType === 'status' && typeof eventData.message === 'string' && eventData.message.trim()) {
    return eventData.message;
  }

  if (eventType === 'thinking') {
    return t('chat.thinking');
  }

  if (eventType === 'tool_start') {
    const toolName = typeof eventData.tool_name === 'string' ? eventData.tool_name : '';
    return toolName ? t('chat.toolRunningNamed', { name: toolName }) : t('chat.toolRunning');
  }

  if (eventType === 'tool_result') {
    const toolName = typeof eventData.tool_name === 'string' ? eventData.tool_name : '';
    return toolName ? t('chat.toolResultNamed', { name: toolName }) : t('chat.toolResult');
  }

  if (eventType === 'step_start' || eventType === 'step_complete') {
    const stepType = typeof eventData.step_type === 'string' ? eventData.step_type : '';
    if (stepType === 'thinking') {
      return t('chat.thinking');
    }
    if (stepType === 'response') {
      return t('chat.replying');
    }
    if (stepType === 'tool_call') {
      return t('chat.toolRunning');
    }
    if (stepType === 'compression') {
      return t('chat.compressingContext');
    }
  }

  return t('chat.streamingInput');
};

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

const HistorySearchPopover = lazyWithReload(
  'HistorySearchPopover',
  () => import('../components/chat/HistorySearchPopover'),
);

const RelayTimelinePanel = lazyWithReload(
  'RelayTimelinePanel',
  () => import('../components/chat/RelayTimelinePanel'),
);

const ChatPage: React.FC = () => {
  const { intlLocale, t } = useI18n();
  const toast = useToast();
  const executionStepFallbackTitle = t('chat.executionStep');
  const [isConversationHeaderCollapsed, setIsConversationHeaderCollapsed] = useState(() => (
    window.localStorage.getItem('horbot.chat.conversationHeaderCollapsed') === 'true'
  ));
  const [isWorkbenchExpanded, setIsWorkbenchExpanded] = useState(() => (
    window.localStorage.getItem('horbot.chat.workbenchExpanded') === 'true'
  ));
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [externalAgents, setExternalAgents] = useState<AgentInfo[]>([]);
  const [teams, setTeams] = useState<TeamInfo[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [historyLoadingState, setHistoryLoadingState] = useState<{
    conversationId: string | null;
    mode: HistoryLoadMode;
  }>({
    conversationId: null,
    mode: 'initial',
  });
  const [historyWindowStateByConversation, setHistoryWindowStateByConversation] = useState<
    Record<string, ConversationHistoryWindowState>
  >({});
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null);
  const [expandedTurnIds, setExpandedTurnIds] = useState<Record<string, boolean>>({});
  const [expandedTimelineTurnIds, setExpandedTimelineTurnIds] = useState<Record<string, boolean>>({});
  const [streamState, setStreamState] = useState<StreamState | null>(null);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [showReconnect, setShowReconnect] = useState(false);
  const [lastFailedRequest, setLastFailedRequest] = useState<RetryRequest | null>(null);
  const [lastFailedTurnId, setLastFailedTurnId] = useState<string | null>(null);
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
  const [historySearchTimeRange, setHistorySearchTimeRange] = useState<HistorySearchTimeRange>('all');
  const [remoteHistorySearchMatches, setRemoteHistorySearchMatches] = useState<RemoteHistorySearchMatch[]>([]);
  const [remoteHistorySearchTotal, setRemoteHistorySearchTotal] = useState(0);
  const [remoteHistorySearchHasMore, setRemoteHistorySearchHasMore] = useState(false);
  const [remoteHistorySearchOffset, setRemoteHistorySearchOffset] = useState(0);
  const [isRemoteHistorySearchLoading, setIsRemoteHistorySearchLoading] = useState(false);
  const [isRemoteHistorySearchLoadingMore, setIsRemoteHistorySearchLoadingMore] = useState(false);
  const [activeRemoteHistoryResultId, setActiveRemoteHistoryResultId] = useState<string | null>(null);
  const [isNearBottom, setIsNearBottom] = useState(true);

  useEffect(() => {
    window.localStorage.setItem(
      'horbot.chat.conversationHeaderCollapsed',
      isConversationHeaderCollapsed ? 'true' : 'false',
    );
  }, [isConversationHeaderCollapsed]);

  useEffect(() => {
    window.localStorage.setItem(
      'horbot.chat.workbenchExpanded',
      isWorkbenchExpanded ? 'true' : 'false',
    );
  }, [isWorkbenchExpanded]);

  const directAgents = useMemo(
    () => [...agents, ...externalAgents],
    [agents, externalAgents],
  );
  
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
  const batonNavigationNoticeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeRequestPayloadRef = useRef<RetryRequest | null>(null);
  const activeTurnIdRef = useRef<string | null>(null);
  const relayGroupRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const historyResultRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const relayHighlightTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const historyLoadPromisesRef = useRef(new Map<string, Promise<void>>());
  const remoteHistorySearchAbortRef = useRef<AbortController | null>(null);
  const pendingHistorySearchJumpRef = useRef<{
    conversationId: string;
    messageId: string;
  } | null>(null);
  const relayHistoryRefreshIntervalsRef = useRef(new Map<string, ReturnType<typeof setInterval>>());
  const relayHistoryRefreshStopTimersRef = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const conversationReconcileTimersRef = useRef(new Map<string, ReturnType<typeof setTimeout>[]>());
  const pendingInitialBottomScrollConversationIdRef = useRef<string | null>(null);
  const pendingHistoryPrependScrollRef = useRef<{
    conversationId: string;
    previousScrollHeight: number;
    previousScrollTop: number;
  } | null>(null);
  const historyWindowStateRef = useRef<Record<string, ConversationHistoryWindowState>>({});
  const currentConversationIdRef = useRef<string | null>(null);
  const chatWebSocketRef = useRef<WebSocket | null>(null);
  const chatWebSocketReconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const subscribedSessionKeysRef = useRef(new Set<string>());
  const websocketEventHandlerRef = useRef<((eventData: Record<string, unknown>) => void) | null>(null);
  const liveConversationStreamsRef = useRef(new Map<string, Map<string, StreamMessageEntry>>());
  const activePrimarySessionKeyRef = useRef<string | null>(null);
  const bottomStickRafRef = useRef<number | null>(null);
  const bottomStickConversationIdRef = useRef<string | null>(null);
  const bottomStickReleaseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const bottomStickDelayedTimersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const relayStatusSnapshotRef = useRef<RelayStatusSnapshot>({
    pendingAgentNames: [],
    activeAgentNames: [],
    activeProcessingAgentName: undefined,
    activeProcessingMessage: null,
  });

  const [interruptNotice, setInterruptNotice] = useState<InterruptNotice | null>(null);
  const [batonNavigationNotice, setBatonNavigationNotice] = useState<BatonNavigationNotice | null>(null);

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

  const dismissBatonNavigationNotice = useCallback(() => {
    setBatonNavigationNotice(null);
    if (batonNavigationNoticeTimerRef.current) {
      clearTimeout(batonNavigationNoticeTimerRef.current);
      batonNavigationNoticeTimerRef.current = null;
    }
  }, []);

  const showBatonNavigationNotice = useCallback((notice: BatonNavigationNotice) => {
    setBatonNavigationNotice(notice);
    if (batonNavigationNoticeTimerRef.current) {
      clearTimeout(batonNavigationNoticeTimerRef.current);
    }
    batonNavigationNoticeTimerRef.current = setTimeout(() => {
      setBatonNavigationNotice(null);
      batonNavigationNoticeTimerRef.current = null;
    }, 4200);
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
      t,
      relayStatusSnapshot.activeProcessingAgentName,
      relayStatusSnapshot.pendingAgentNames,
    );
    setLastInterruptedRequest(interruptedRequest);
    setLastInterruptedTurnId(interruptedTurnId);
    setLastInterruptedMessageId(relayStatusSnapshot.activeProcessingMessage?.id || null);
    await requestStopGeneration();
    await waitForActiveStreamToSettle();
    toast.info(t('chat.relayStoppedToast'), 2200);
    showInterruptNotice(interruptSummary, 'success');
    requestInputFocus();
  }, [
    requestStopGeneration,
    waitForActiveStreamToSettle,
    toast,
    showInterruptNotice,
    requestInputFocus,
    t,
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
      if (bottomStickRafRef.current) {
        window.cancelAnimationFrame(bottomStickRafRef.current);
      }
      if (bottomStickReleaseTimerRef.current) {
        clearTimeout(bottomStickReleaseTimerRef.current);
      }
      bottomStickDelayedTimersRef.current.forEach((timerId) => clearTimeout(timerId));
      bottomStickDelayedTimersRef.current = [];
      if (interruptNoticeTimerRef.current) {
        clearTimeout(interruptNoticeTimerRef.current);
      }
      if (batonNavigationNoticeTimerRef.current) {
        clearTimeout(batonNavigationNoticeTimerRef.current);
      }
      if (relayHighlightTimerRef.current) {
        clearTimeout(relayHighlightTimerRef.current);
      }
      if (chatWebSocketReconnectTimerRef.current) {
        clearTimeout(chatWebSocketReconnectTimerRef.current);
      }
      if (chatWebSocketRef.current) {
        chatWebSocketRef.current.close();
        chatWebSocketRef.current = null;
      }
      relayHistoryRefreshIntervalsRef.current.forEach((intervalId) => clearInterval(intervalId));
      relayHistoryRefreshIntervalsRef.current.clear();
      relayHistoryRefreshStopTimersRef.current.forEach((timeoutId) => clearTimeout(timeoutId));
      relayHistoryRefreshStopTimersRef.current.clear();
      conversationReconcileTimersRef.current.forEach((timerIds) => timerIds.forEach((timerId) => clearTimeout(timerId)));
      conversationReconcileTimersRef.current.clear();
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

  useEffect(() => {
    if (!currentConversation) {
      return;
    }

    const params = new URLSearchParams(window.location.search);
    if (currentConversation.type === ConversationType.TEAM) {
      params.set('team', currentConversation.targetId);
      params.delete('agent');
    } else {
      params.set('agent', currentConversation.targetId);
      params.delete('team');
    }

    const nextSearch = params.toString();
    const nextUrl = `${window.location.pathname}${nextSearch ? `?${nextSearch}` : ''}`;
    window.history.replaceState(null, '', nextUrl);
  }, [currentConversation]);
  
  const currentHistoryWindow = currentConversationId
    ? historyWindowStateByConversation[currentConversationId]
    : undefined;
  const isHistoryLoading = Boolean(
    currentConversationId
    && historyLoadingState.conversationId === currentConversationId
    && historyLoadingState.mode === 'initial',
  );
  const isLoadingOlderHistory = Boolean(
    currentConversationId
    && historyLoadingState.conversationId === currentConversationId
    && historyLoadingState.mode === 'before',
  );
  const isLoadingHistorySearchContext = Boolean(
    currentConversationId
    && historyLoadingState.conversationId === currentConversationId
    && historyLoadingState.mode === 'around',
  );
  const isPartialHistoryLoaded = Boolean(
    currentHistoryWindow?.hasMoreBefore || currentHistoryWindow?.hasMoreAfter,
  );
  const canJumpBackToLatest = Boolean(currentHistoryWindow?.hasMoreAfter);
  
  const generateId = () => Math.random().toString(36).substring(2, 15);

  const mergeLocalizedExecutionSteps = useCallback((
    existingSteps: ExecutionStep[] = [],
    incomingSteps: ExecutionStep[] = [],
  ) => mergeExecutionSteps(existingSteps, incomingSteps, executionStepFallbackTitle), [executionStepFallbackTitle]);

  const upsertLocalizedExecutionStep = useCallback((
    steps: ExecutionStep[] = [],
    step: ExecutionStep,
  ) => upsertExecutionStep(steps, step, executionStepFallbackTitle), [executionStepFallbackTitle]);

  const mergeConversationHistory = useCallback((historyMessages: UIMessage[], existingMessages: UIMessage[]) => {
    return mergeConversationHistoryMessages(
      historyMessages,
      existingMessages,
      mergeLocalizedExecutionSteps,
    );
  }, [mergeLocalizedExecutionSteps]);

  const formatConversationHistoryMessages = useCallback((
    rawMessages: RawConversationHistoryMessage[],
  ): UIMessage[] => {
    return formatHistoryMessages(rawMessages, {
      directAgents,
      mergeExecutionSteps: mergeLocalizedExecutionSteps,
      t,
    });
  }, [directAgents, mergeLocalizedExecutionSteps, t]);

  const getConversationStreamRegistry = useCallback((conversationId: string) => {
    let registry = liveConversationStreamsRef.current.get(conversationId);
    if (!registry) {
      registry = new Map<string, StreamMessageEntry>();
      liveConversationStreamsRef.current.set(conversationId, registry);
    }
    return registry;
  }, []);

  const findPendingStreamEntry = useCallback((registry: Map<string, StreamMessageEntry>, targetAgentId: string) => {
    for (const [key, entry] of registry.entries()) {
      if (entry.agentId === targetAgentId && entry.phase === 'pending') {
        return [key, entry] as const;
      }
    }
    return undefined;
  }, []);

  const clearConversationReconcileTimers = useCallback((convId: string) => {
    const timerIds = conversationReconcileTimersRef.current.get(convId) || [];
    timerIds.forEach((timerId) => clearTimeout(timerId));
    conversationReconcileTimersRef.current.delete(convId);
  }, []);

  const reconcileConversationAfterDone = useCallback((
    convId: string,
    streamEntries?: StreamMessageEntry[],
  ) => {
    const registry = getConversationStreamRegistry(convId);
    const snapshot = streamEntries || Array.from(registry.values());
    const streamAgentIds = new Set<string>();

    snapshot.forEach((entry) => {
      if (entry.agentId) {
        streamAgentIds.add(entry.agentId);
        removeTypingAgent(convId, entry.agentId);
      }
    });

    registry.clear();
    clearConversationReconcileTimers(convId);

    const runReconcile = async () => {
      try {
        const response = await fetch(buildConversationMessagesUrl(convId, {
          limit: CONVERSATION_HISTORY_PAGE_SIZE,
          afterId: historyWindowStateRef.current[convId]?.newestMessageId,
        }), { cache: 'no-store' });
        const data = await response.json();
        let historyMessages = Array.isArray(data.messages)
          ? formatConversationHistoryMessages(data.messages)
          : [];
        let page = (data.page || {}) as ConversationHistoryPage;
        let replacedStreamEntries = findReplacedStreamEntries(historyMessages, snapshot);

        if (snapshot.length > 0 && replacedStreamEntries.length === 0) {
          const latestResponse = await fetch(buildConversationMessagesUrl(convId, {
            limit: CONVERSATION_HISTORY_PAGE_SIZE,
          }), { cache: 'no-store' });
          const latestData = await latestResponse.json();
          const latestHistoryMessages = Array.isArray(latestData.messages)
            ? formatConversationHistoryMessages(latestData.messages)
            : [];
          const latestReplacedStreamEntries = findReplacedStreamEntries(latestHistoryMessages, snapshot);
          if (latestReplacedStreamEntries.length > 0) {
            historyMessages = latestHistoryMessages;
            page = (latestData.page || {}) as ConversationHistoryPage;
            replacedStreamEntries = latestReplacedStreamEntries;
          }
        }

        const hasHistoryReplacement = replacedStreamEntries.length > 0;
        const existingMessages = (getMessages(convId) as UIMessage[]).filter((message) => {
          if (message.role !== 'assistant') {
            return true;
          }
          if (hasHistoryReplacement) {
            const shouldReplaceMessage = replacedStreamEntries.some((entry) => (
              doesHistoryMessageReplaceStreamEntry(message, entry)
            ));
            if (shouldReplaceMessage) {
              return false;
            }
            if (message.metadata?._relay_phase === 'pending') {
              return false;
            }
            if (message.agentId && streamAgentIds.has(message.agentId) && !message.content.trim()) {
              return false;
            }
          }
          return true;
        });
        const nextMessages = mergeConversationHistory(historyMessages, existingMessages);
        setMessages(convId, nextMessages);
        if (currentConversationIdRef.current === convId) {
          armBottomStickForConversation(convId);
          stickConversationToBottom(convId);
        }
        setHistoryWindowStateByConversation((prev) => {
          const previousWindow = prev[convId] || { hasMoreBefore: false, hasMoreAfter: false };
          return {
            ...prev,
            [convId]: {
              oldestMessageId: previousWindow.oldestMessageId || page.oldest_message_id || undefined,
              newestMessageId: page.newest_message_id || previousWindow.newestMessageId || undefined,
              hasMoreBefore: typeof page.has_more_before === 'boolean'
                ? page.has_more_before
                : previousWindow.hasMoreBefore,
              hasMoreAfter: typeof page.has_more_after === 'boolean'
                ? page.has_more_after
                : previousWindow.hasMoreAfter,
              totalMessages: typeof page.total_messages === 'number'
                ? page.total_messages
                : previousWindow.totalMessages,
            },
          };
        });
      } catch (error) {
        console.error('Failed to reconcile conversation after done:', error);
      }
    };

    void runReconcile();

    const timerIds = [250, 1200].map((delay) => window.setTimeout(() => {
      void runReconcile();
    }, delay));
    conversationReconcileTimersRef.current.set(convId, timerIds);
  }, [
    clearConversationReconcileTimers,
    formatConversationHistoryMessages,
    getConversationStreamRegistry,
    getMessages,
    mergeConversationHistory,
    removeTypingAgent,
    setMessages,
    setHistoryWindowStateByConversation,
  ]);
  
  const formatTime = useCallback((timestamp?: string) => {
    if (!timestamp) return '';

    const date = new Date(timestamp);
    const now = new Date();
    const isToday = date.getFullYear() === now.getFullYear()
      && date.getMonth() === now.getMonth()
      && date.getDate() === now.getDate();
    const isSameYear = date.getFullYear() === now.getFullYear();

    const formatter = new Intl.DateTimeFormat(intlLocale, isToday
      ? { hour: '2-digit', minute: '2-digit' }
      : isSameYear
        ? { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }
        : { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });

    return formatter.format(date);
  }, [intlLocale]);
  
  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    const container = chatContainerRef.current;
    if (container) {
      container.scrollTo({
        top: container.scrollHeight,
        behavior,
      });
      return;
    }

    messagesEndRef.current?.scrollIntoView({ behavior, block: 'end' });
  }, []);

  const stickConversationToBottom = useCallback((conversationId: string, remainingFrames: number = 8) => {
    if (bottomStickRafRef.current) {
      window.cancelAnimationFrame(bottomStickRafRef.current);
      bottomStickRafRef.current = null;
    }

    const run = (framesLeft: number) => {
      bottomStickRafRef.current = window.requestAnimationFrame(() => {
        if (currentConversationIdRef.current !== conversationId) {
          bottomStickRafRef.current = null;
          return;
        }

        scrollToBottom('auto');

        if (framesLeft > 1) {
          run(framesLeft - 1);
          return;
        }

        bottomStickRafRef.current = null;
      });
    };

    run(Math.max(1, remainingFrames));
  }, [scrollToBottom]);

  const armBottomStickForConversation = useCallback((conversationId: string) => {
    bottomStickConversationIdRef.current = conversationId;
    if (bottomStickReleaseTimerRef.current) {
      clearTimeout(bottomStickReleaseTimerRef.current);
    }
    bottomStickDelayedTimersRef.current.forEach((timerId) => clearTimeout(timerId));
    bottomStickDelayedTimersRef.current = [250, 900, 1800, 2800].map((delay) => (
      setTimeout(() => {
        if (bottomStickConversationIdRef.current === conversationId) {
          stickConversationToBottom(conversationId, 2);
        }
      }, delay)
    ));
    bottomStickReleaseTimerRef.current = setTimeout(() => {
      if (bottomStickConversationIdRef.current === conversationId) {
        bottomStickConversationIdRef.current = null;
      }
      bottomStickDelayedTimersRef.current.forEach((timerId) => clearTimeout(timerId));
      bottomStickDelayedTimersRef.current = [];
      bottomStickReleaseTimerRef.current = null;
    }, 3000);
  }, [stickConversationToBottom]);

  useEffect(() => {
    currentConversationIdRef.current = currentConversationId;
  }, [currentConversationId]);

  useEffect(() => {
    if (!currentConversationId) {
      return;
    }

    pendingInitialBottomScrollConversationIdRef.current = currentConversationId;
    armBottomStickForConversation(currentConversationId);
    setIsNearBottom(true);
  }, [armBottomStickForConversation, currentConversationId]);

  const applyDirectoryBundle = useCallback((directory: ChatDirectoryBundle) => {
    setAgents(directory.agents);
    setExternalAgents(directory.externalAgents);
    setTeams(directory.teams);
  }, []);

  const loadDirectoryBundle = useCallback(async (options: { force?: boolean } = {}) => {
    const directory = options.force
      ? await chatDirectoryCache.refresh()
      : await chatDirectoryCache.get();
    applyDirectoryBundle(directory);
  }, [applyDirectoryBundle]);

  const refreshAgents = useCallback(async () => {
    try {
      await loadDirectoryBundle({ force: true });
    } catch (error) {
      console.error('Failed to refresh agents:', error);
    }
  }, [loadDirectoryBundle]);
  
  useEffect(() => {
    if (isNearBottom) {
      scrollToBottom();
    }
  }, [messages, isNearBottom, scrollToBottom]);

  useEffect(() => {
    historyWindowStateRef.current = historyWindowStateByConversation;
  }, [historyWindowStateByConversation]);

  useLayoutEffect(() => {
    const pendingAdjustment = pendingHistoryPrependScrollRef.current;
    if (!pendingAdjustment || pendingAdjustment.conversationId !== currentConversationId) {
      return;
    }

    const container = chatContainerRef.current;
    if (!container) {
      pendingHistoryPrependScrollRef.current = null;
      return;
    }

    container.scrollTop = pendingAdjustment.previousScrollTop
      + (container.scrollHeight - pendingAdjustment.previousScrollHeight);
    pendingHistoryPrependScrollRef.current = null;
  }, [currentConversationId, messages]);

  useLayoutEffect(() => {
    if (!currentConversationId) {
      return;
    }
    if (bottomStickConversationIdRef.current !== currentConversationId) {
      return;
    }
    stickConversationToBottom(currentConversationId, 2);
  }, [currentConversationId, stickConversationToBottom]);
  
  useEffect(() => {
    const initialize = async () => {
      try {
        await loadDirectoryBundle();
      } catch (error) {
        console.error('Failed to initialize:', error);
      }
    };

    void initialize();
  }, [loadDirectoryBundle]);

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
    if (directAgents.length === 0) {
      return;
    }

    const params = new URLSearchParams(window.location.search);
    const urlAgentId = params.get('agent');
    const urlTeamId = params.get('team');

    if (!currentConversationId && urlAgentId) {
      const targetAgent = directAgents.find((agent) => agent.id === urlAgentId);
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

    const defaultAgent = directAgents[0];
    if (!defaultAgent) {
      return;
    }

    const conv = getOrCreateDMConversation(defaultAgent.id, defaultAgent.name);
    setCurrentConversation(conv.id);
    setSelectedAgentId(defaultAgent.id);
  }, [directAgents, teams, currentConversationId, getOrCreateDMConversation, getOrCreateTeamConversation, setCurrentConversation]);
  
  const loadConversationHistory = useCallback((
    convId: string,
    options: {
      mode?: HistoryLoadMode;
      aroundId?: string;
      forceRefreshLatest?: boolean;
    } = {},
  ): Promise<void> => {
    const existingRequest = historyLoadPromisesRef.current.get(convId);
    if (existingRequest) {
      if (options.forceRefreshLatest) {
        return existingRequest.then(() => loadConversationHistory(convId, options));
      }
      return existingRequest;
    }

    const mode = options.mode || 'initial';
    const existingMessages = getMessages(convId) as UIMessage[];
    const currentWindow = historyWindowStateRef.current[convId];
    const shouldSnapBackToLatest = Boolean(
      mode === 'initial'
      && !options.forceRefreshLatest
      && currentWindow?.hasMoreAfter,
    );
    const effectiveMode: HistoryLoadMode = mode === 'initial'
      && !options.forceRefreshLatest
      && !shouldSnapBackToLatest
      && existingMessages.length > 0
      && currentWindow?.newestMessageId
      ? 'after'
      : mode;

    if (effectiveMode === 'before' && !currentWindow?.hasMoreBefore) {
      return Promise.resolve();
    }
    if (effectiveMode === 'before' && !currentWindow?.oldestMessageId) {
      return Promise.resolve();
    }
    if (effectiveMode === 'after' && !currentWindow?.newestMessageId) {
      return Promise.resolve();
    }
    if (effectiveMode === 'around' && !options.aroundId) {
      return Promise.resolve();
    }

    if (effectiveMode === 'before' && chatContainerRef.current) {
      pendingHistoryPrependScrollRef.current = {
        conversationId: convId,
        previousScrollHeight: chatContainerRef.current.scrollHeight,
        previousScrollTop: chatContainerRef.current.scrollTop,
      };
    }

    setHistoryLoadingState({
      conversationId: convId,
      mode: effectiveMode,
    });

    const request = (async () => {
      try {
        const response = await fetch(buildConversationMessagesUrl(convId, {
          limit: CONVERSATION_HISTORY_PAGE_SIZE,
          beforeId: effectiveMode === 'before' ? currentWindow?.oldestMessageId : undefined,
          afterId: effectiveMode === 'after' ? currentWindow?.newestMessageId : undefined,
          aroundId: effectiveMode === 'around' ? options.aroundId : undefined,
          contextBefore: effectiveMode === 'around' ? CONVERSATION_HISTORY_SEARCH_CONTEXT : undefined,
          contextAfter: effectiveMode === 'around' ? CONVERSATION_HISTORY_SEARCH_CONTEXT : undefined,
        }), { cache: 'no-store' });
        let data = await response.json();

        if (data.messages && Array.isArray(data.messages)) {
          const latestExistingMessages = getMessages(convId) as UIMessage[];
          let formattedMessages = formatConversationHistoryMessages(data.messages);
          let page = (data.page || {}) as ConversationHistoryPage;

          // If the incremental anchor came from a transient streaming message or
          // an older cached window, the backend cannot find it and returns an
          // empty after-window. Fall back to a fresh latest window so refreshes
          // and module switches never leave the conversation pinned to stale
          // history.
          if (
            effectiveMode === 'after'
            && formattedMessages.length === 0
            && (typeof page.total_messages !== 'number' || page.total_messages > 0)
          ) {
            const latestResponse = await fetch(buildConversationMessagesUrl(convId, {
              limit: CONVERSATION_HISTORY_PAGE_SIZE,
            }), { cache: 'no-store' });
            data = await latestResponse.json();
            formattedMessages = Array.isArray(data.messages)
              ? formatConversationHistoryMessages(data.messages)
              : [];
            page = (data.page || {}) as ConversationHistoryPage;
          }

          const nextMessages = effectiveMode === 'around' || effectiveMode === 'initial'
            ? formattedMessages
            : mergeConversationHistory(formattedMessages, latestExistingMessages);
          setMessages(convId, nextMessages);
          if (effectiveMode === 'after' && currentConversationIdRef.current === convId) {
            armBottomStickForConversation(convId);
            stickConversationToBottom(convId);
          }

          setHistoryWindowStateByConversation((prev) => {
            const previousWindow = prev[convId] || { hasMoreBefore: false, hasMoreAfter: false };
            if (effectiveMode === 'around' || effectiveMode === 'initial') {
              return {
                ...prev,
                [convId]: {
                  oldestMessageId: page.oldest_message_id || undefined,
                  newestMessageId: page.newest_message_id || undefined,
                  hasMoreBefore: Boolean(page.has_more_before),
                  hasMoreAfter: Boolean(page.has_more_after),
                  totalMessages: typeof page.total_messages === 'number'
                    ? page.total_messages
                    : previousWindow.totalMessages,
                },
              };
            }
            return {
              ...prev,
              [convId]: {
                oldestMessageId: effectiveMode === 'after'
                  ? (previousWindow.oldestMessageId || page.oldest_message_id || undefined)
                  : (page.oldest_message_id || previousWindow.oldestMessageId || undefined),
                newestMessageId: page.newest_message_id || previousWindow.newestMessageId || undefined,
                hasMoreBefore: typeof page.has_more_before === 'boolean'
                  ? page.has_more_before
                  : previousWindow.hasMoreBefore,
                hasMoreAfter: effectiveMode === 'before'
                  ? previousWindow.hasMoreAfter
                  : (typeof page.has_more_after === 'boolean'
                    ? page.has_more_after
                    : previousWindow.hasMoreAfter),
                totalMessages: typeof page.total_messages === 'number'
                  ? page.total_messages
                  : previousWindow.totalMessages,
              },
            };
          });
        }
      } catch (error) {
        if (effectiveMode === 'before' && pendingHistoryPrependScrollRef.current?.conversationId === convId) {
          pendingHistoryPrependScrollRef.current = null;
        }
        console.error('Failed to load conversation history:', error);
      } finally {
        historyLoadPromisesRef.current.delete(convId);
        setHistoryLoadingState((currentLoadingState) => (
          currentLoadingState.conversationId === convId
            ? { conversationId: null, mode: 'initial' }
            : currentLoadingState
        ));
        if (pendingInitialBottomScrollConversationIdRef.current === convId) {
          pendingInitialBottomScrollConversationIdRef.current = null;
          armBottomStickForConversation(convId);
          stickConversationToBottom(convId);
        }
      }
    })();

    historyLoadPromisesRef.current.set(convId, request);
    return request;
  }, [
    formatConversationHistoryMessages,
    getMessages,
    mergeConversationHistory,
    armBottomStickForConversation,
    stickConversationToBottom,
    setMessages,
  ]);

  const settleTimedOutRequestFromHistory = useCallback(async (
    convId: string,
    requestId: string,
    streamEntries: StreamMessageEntry[],
  ): Promise<boolean> => {
    const maxAttempts = 4;
    const retryDelayMs = 900;

    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      try {
        const response = await fetch(buildConversationMessagesUrl(convId, {
          limit: CONVERSATION_HISTORY_PAGE_SIZE,
          afterId: historyWindowStateRef.current[convId]?.newestMessageId,
        }), { cache: 'no-store' });
        const data = await response.json();
        const rawMessages: Array<Record<string, unknown>> = Array.isArray(data.messages) ? data.messages : [];
        const matchedAssistantMessage = rawMessages.find((message: Record<string, unknown>) => (
          message
          && typeof message === 'object'
          && (message as { role?: string }).role === 'assistant'
          && typeof (message as { metadata?: { request_id?: string } }).metadata?.request_id === 'string'
          && (message as { metadata?: { request_id?: string } }).metadata?.request_id === requestId
          && (
            (
              typeof (message as { content?: string }).content === 'string'
              && cleanHistoryMessageContent((message as { content?: string }).content || '').trim().length > 0
            )
            || hasRenderableMessageFiles((message as { files?: unknown }).files)
            || (
              Array.isArray((message as { execution_steps?: unknown[] }).execution_steps)
              && (message as { execution_steps?: unknown[] }).execution_steps!.length > 0
            )
          )
        ));

        if (matchedAssistantMessage) {
          reconcileConversationAfterDone(convId, streamEntries);
          return true;
        }
      } catch (historyError) {
        console.error('Failed to confirm timed-out request from history:', historyError);
      }

      if (attempt < maxAttempts - 1) {
        await new Promise((resolve) => {
          window.setTimeout(resolve, retryDelayMs);
        });
      }
    }

    return false;
  }, [reconcileConversationAfterDone]);

  const clearRelayHistoryRefresh = useCallback((convId: string) => {
    const intervalId = relayHistoryRefreshIntervalsRef.current.get(convId);
    if (intervalId) {
      clearInterval(intervalId);
      relayHistoryRefreshIntervalsRef.current.delete(convId);
    }

    const timeoutId = relayHistoryRefreshStopTimersRef.current.get(convId);
    if (timeoutId) {
      clearTimeout(timeoutId);
      relayHistoryRefreshStopTimersRef.current.delete(convId);
    }
  }, []);

  const ensureRelayHistoryRefresh = useCallback((convId: string) => {
    const existingStopTimer = relayHistoryRefreshStopTimersRef.current.get(convId);
    if (existingStopTimer) {
      clearTimeout(existingStopTimer);
    }

    if (!relayHistoryRefreshIntervalsRef.current.has(convId)) {
      const intervalId = window.setInterval(() => {
        void loadConversationHistory(convId);
      }, 1200);
      relayHistoryRefreshIntervalsRef.current.set(convId, intervalId);
    }

    const stopTimerId = window.setTimeout(() => {
      clearRelayHistoryRefresh(convId);
    }, 90000);
    relayHistoryRefreshStopTimersRef.current.set(convId, stopTimerId);
  }, [clearRelayHistoryRefresh, loadConversationHistory]);

  const openDispatchedWebConversation = useCallback((
    dispatchArgs?: Record<string, unknown>,
    options?: { activate?: boolean },
  ) => {
    if (!dispatchArgs) {
      return;
    }
    const activate = options?.activate ?? false;

    const channel = typeof dispatchArgs.channel === 'string' ? dispatchArgs.channel.trim() : '';
    const targetChatId = typeof dispatchArgs.chat_id === 'string' ? dispatchArgs.chat_id.trim() : '';
    if (channel !== 'web' || !targetChatId) {
      return;
    }

    const normalizedConversationId = targetChatId.startsWith('web:')
      ? targetChatId.slice(4)
      : targetChatId;
    if (!normalizedConversationId || normalizedConversationId === currentConversation?.id) {
      return;
    }

    let conversationIdToOpen: string | null = null;

    if (normalizedConversationId.startsWith('team_')) {
      const resolvedTeamId = typeof dispatchArgs.team_id === 'string' && dispatchArgs.team_id.trim()
        ? dispatchArgs.team_id.trim()
        : normalizedConversationId.slice('team_'.length);
      const team = teams.find((item) => item.id === resolvedTeamId);
      if (!team) {
        return;
      }
      const conversation = getOrCreateTeamConversation(
        team.id,
        team.name,
        team.members,
        team.description,
      );
      conversationIdToOpen = conversation.id;
    } else if (normalizedConversationId.startsWith('dm_')) {
      const targetAgentId = normalizedConversationId.slice('dm_'.length);
      const agent = directAgents.find((item) => item.id === targetAgentId);
      if (!agent) {
        return;
      }
      const conversation = getOrCreateDMConversation(agent.id, agent.name);
      conversationIdToOpen = conversation.id;
    }

    if (!conversationIdToOpen) {
      return;
    }

    const sessionKey = conversationIdToSessionKey(conversationIdToOpen);
    subscribedSessionKeysRef.current.add(sessionKey);
    if (chatWebSocketRef.current?.readyState === WebSocket.OPEN) {
      chatWebSocketRef.current.send(JSON.stringify({
        type: 'subscribe',
        session_key: sessionKey,
      }));
    }

    void loadConversationHistory(conversationIdToOpen, { forceRefreshLatest: true });
    ensureRelayHistoryRefresh(conversationIdToOpen);
    if (activate) {
      setCurrentConversation(conversationIdToOpen);
      const sourceConversationName = currentConversation?.name?.trim() || t('chat.currentDirectConversation');
      const destinationConversationName = (
        teams.find((team) => `team_${team.id}` === conversationIdToOpen)?.name
        || directAgents.find((agent) => `dm_${agent.id}` === conversationIdToOpen)?.name
        || conversationIdToOpen
      ).trim();
      showBatonNavigationNotice({
        tone: normalizedConversationId.startsWith('team_') ? 'team' : 'dm',
        message: normalizedConversationId.startsWith('team_')
          ? t('chat.switchedToTeamRelayFrom', { destination: destinationConversationName, source: sourceConversationName })
          : t('chat.switchedToConversation', { destination: destinationConversationName }),
        actionLabel: currentConversation ? t('chat.backToConversation', { source: sourceConversationName }) : undefined,
        actionConversationId: currentConversation?.id,
      });
    }
  }, [
    directAgents,
    currentConversation,
    ensureRelayHistoryRefresh,
    getOrCreateDMConversation,
    getOrCreateTeamConversation,
    loadConversationHistory,
    setCurrentConversation,
    showBatonNavigationNotice,
    t,
    teams,
  ]);

  const applyRealtimeEventToConversation = useCallback((
    conversationId: string,
    eventData: Record<string, unknown>,
  ) => {
    const registry = getConversationStreamRegistry(conversationId);
    const eventType = (eventData.event as string) || (eventData.type as string);
    const agentId = eventData.agent_id as string | undefined;
    const agentName = eventData.agent_name as string | undefined;
    const turnId = eventData.turn_id as string | undefined;
    const messageIdFromEvent = eventData.message_id as string | undefined;
    const incomingExecutionSteps = Array.isArray(eventData.execution_steps)
      ? mergeLocalizedExecutionSteps([], eventData.execution_steps as ExecutionStep[])
      : [];
    const streamKey = messageIdFromEvent || turnId || (agentId ? `${agentId}:${String(eventData.agent_index ?? '0')}` : 'main');
    const streamEntry = registry.get(streamKey);
    const matchedStreamEntry = streamEntry
      || (messageIdFromEvent ? Array.from(registry.values()).find((entry) => entry.messageId === messageIdFromEvent) : undefined)
      || (turnId ? Array.from(registry.values()).find((entry) => entry.turnId === turnId) : undefined)
      || (agentId ? Array.from(registry.values()).find((entry) => entry.agentId === agentId && entry.phase !== 'done') : undefined);
    const existingMessage = (messageId?: string) => (
      messageId ? getMessages(conversationId).find((message) => message.id === messageId) : undefined
    );
    let resolvedStreamEntry = matchedStreamEntry;

    if (eventType === 'agent_start' || eventType === 'request_start') {
      if (!agentId) {
        return;
      }
      const pendingEntryMatch = findPendingStreamEntry(registry, agentId);
      if (streamEntry) {
        streamEntry.phase = 'active';
        if (turnId) {
          streamEntry.turnId = turnId;
        }
        updateMessage(conversationId, streamEntry.messageId, {
          turnId,
          requestId: (eventData.request_id as string | undefined) || undefined,
          agentId,
          agentName,
          isStreaming: true,
          statusMessage: streamEntry.content ? t('chat.streamingInput') : t('chat.batonStarted'),
          metadata: {
            ...(existingMessage(streamEntry.messageId)?.metadata || {}),
            _relay_phase: 'active',
          },
        });
      } else if (pendingEntryMatch) {
        const [pendingKey, pendingEntry] = pendingEntryMatch;
        pendingEntry.phase = 'active';
        pendingEntry.turnId = turnId;
        if (pendingKey !== streamKey) {
          registry.delete(pendingKey);
        }
        registry.set(streamKey, pendingEntry);
        updateMessage(conversationId, pendingEntry.messageId, {
          turnId,
          requestId: (eventData.request_id as string | undefined) || undefined,
          agentId,
          agentName,
          isStreaming: true,
          statusMessage: pendingEntry.content ? t('chat.streamingInput') : t('chat.batonStarted'),
          metadata: {
            ...(existingMessage(pendingEntry.messageId)?.metadata || {}),
            _relay_phase: 'active',
          },
        });
      } else {
        const messageId = messageIdFromEvent || Math.random().toString(36).substring(2, 15);
        registry.set(streamKey, {
          messageId,
          content: '',
          turnId,
          agentId,
          phase: 'active',
          executionSteps: [],
        });
        if (!existingMessage(messageId)) {
          addMessage(conversationId, {
            id: messageId,
            role: 'assistant',
            content: '',
            turnId,
            requestId: (eventData.request_id as string | undefined) || undefined,
            agentId,
            agentName,
            isStreaming: true,
            statusMessage: t('chat.streamingInput'),
            executionSteps: [],
            metadata: { _relay_phase: 'active' },
            timestamp: new Date().toISOString(),
          });
        }
      }
      addTypingAgent(conversationId, agentId);
      return;
    }

    if (eventType === 'agent_mentioned') {
      const mentionedAgentId = eventData.agent_id as string | undefined;
      const mentionedAgentName = eventData.agent_name as string | undefined;
      if (!mentionedAgentId) {
        return;
      }
      const pendingEntryMatch = findPendingStreamEntry(registry, mentionedAgentId);
      if (!pendingEntryMatch) {
        const pendingKey = `pending:${mentionedAgentId}:${Math.random().toString(36).substring(2, 15)}`;
        const messageId = messageIdFromEvent || Math.random().toString(36).substring(2, 15);
        const handoffMode = eventData.handoff_mode as string | undefined;
        const waitingStatus = handoffMode === 'summary'
          ? t('chat.handoffWaitSummary')
          : handoffMode === 'continue'
            ? t('chat.handoffWaitContinue')
            : t('chat.handoffWaitResponse');
        registry.set(pendingKey, {
          messageId,
          content: '',
          turnId,
          agentId: mentionedAgentId,
          phase: 'pending',
          executionSteps: [],
        });
        if (!existingMessage(messageId)) {
          addMessage(conversationId, {
            id: messageId,
            role: 'assistant',
            content: '',
            turnId,
            requestId: (eventData.request_id as string | undefined) || undefined,
            agentId: mentionedAgentId,
            agentName: mentionedAgentName,
            isStreaming: true,
            statusMessage: waitingStatus,
            executionSteps: [],
            metadata: {
              ...((eventData.mentioned_by_name as string | undefined) ? { handoff_from_name: eventData.mentioned_by_name } : {}),
              ...(mentionedAgentName ? { handoff_to_name: mentionedAgentName } : {}),
              ...((eventData.handoff_mode as string | undefined) ? { handoff_mode: eventData.handoff_mode } : {}),
              ...((eventData.handoff_preview as string | undefined) ? { handoff_preview: eventData.handoff_preview } : {}),
              _relay_phase: 'pending',
            },
            timestamp: new Date().toISOString(),
          });
        }
      }
      addTypingAgent(conversationId, mentionedAgentId);
      return;
    }

    if (!resolvedStreamEntry && agentId && shouldBootstrapRealtimeStreamEntry(eventType)) {
      const messageId = messageIdFromEvent || Math.random().toString(36).substring(2, 15);
      resolvedStreamEntry = {
        messageId,
        content: '',
        turnId,
        agentId,
        phase: 'active',
        executionSteps: incomingExecutionSteps,
      };
      registry.set(streamKey, resolvedStreamEntry);
      if (!existingMessage(messageId)) {
        addMessage(conversationId, {
          id: messageId,
          role: 'assistant',
          content: '',
          turnId,
          requestId: (eventData.request_id as string | undefined) || undefined,
          agentId,
          agentName,
          isStreaming: true,
          statusMessage: getRealtimeBootstrapStatusMessage(t, eventType, eventData),
          executionSteps: incomingExecutionSteps,
          metadata: { _relay_phase: 'active' },
          timestamp: new Date().toISOString(),
        });
      }
      addTypingAgent(conversationId, agentId);
    }

    if (!resolvedStreamEntry) {
      if (eventType === 'agent_done' && agentId) {
        const messageId = messageIdFromEvent || Math.random().toString(36).substring(2, 15);
        const normalizedError = normalizeAssistantErrorContent(t, eventData.content as string);
        const providerError = normalizeProviderErrorPayload(eventData.provider_error);
        const eventFiles = normalizeMessageFiles(eventData.files);
        registry.set(streamKey, {
          messageId,
          content: normalizedError.content || '',
          turnId,
          agentId,
          phase: 'done',
          executionSteps: incomingExecutionSteps,
        });
        if (!existingMessage(messageId)) {
          addMessage(conversationId, {
            id: messageId,
            role: 'assistant',
            content: normalizedError.content || '',
            turnId,
            requestId: (eventData.request_id as string | undefined) || undefined,
            agentId,
            agentName,
            isStreaming: false,
            isThinking: false,
            files: eventFiles,
            executionSteps: incomingExecutionSteps,
            metadata: {
              ...(providerError ? { _provider_error: providerError } : {}),
              ...(Array.isArray(eventData.memory_sources) && eventData.memory_sources.length > 0
                ? { _memory_sources: eventData.memory_sources }
                : {}),
              ...(eventData.memory_recall && typeof eventData.memory_recall === 'object'
                ? { _memory_recall: eventData.memory_recall }
                : {}),
            },
            isError: Boolean(providerError) || normalizedError.isProviderError,
            errorKind: (Boolean(providerError) || normalizedError.isProviderError) ? 'provider' : undefined,
            retryable: providerError?.retryable ?? normalizedError.isProviderError,
            timestamp: new Date().toISOString(),
          });
        }
        removeTypingAgent(conversationId, agentId);
        void loadConversationHistory(conversationId);
      }
      return;
    }

    if (eventType === 'thinking') {
      updateMessage(conversationId, resolvedStreamEntry.messageId, {
        executionSteps: resolvedStreamEntry.executionSteps,
        isThinking: true,
        statusMessage: t('chat.thinking'),
      });
      return;
    }

    if (eventType === 'status') {
      updateMessage(conversationId, resolvedStreamEntry.messageId, {
        statusMessage: eventData.message as string,
      });
      return;
    }

    if (eventType === 'progress' || eventType === 'content') {
      if (eventData.tool_hint) {
        return;
      }
      const isSyntheticProgress = Boolean(eventData.synthetic_progress);
      resolvedStreamEntry.content = (eventData.content as string) || '';
      resolvedStreamEntry.phase = 'active';
      resolvedStreamEntry.executionSteps = updateLatestRunningExecutionStep(
        resolvedStreamEntry.executionSteps,
        (step) => (step.type || '').toLowerCase().includes('thinking'),
        {
          reasoning_content: resolvedStreamEntry.content,
          content: resolvedStreamEntry.content,
        },
      );
      updateMessage(conversationId, resolvedStreamEntry.messageId, {
        content: resolvedStreamEntry.content,
        isThinking: isSyntheticProgress,
        executionSteps: resolvedStreamEntry.executionSteps,
      });
      return;
    }

    if (eventType === 'tool_start') {
      const toolName = eventData.tool_name as string | undefined;
      const argumentsPayload = eventData.arguments as Record<string, unknown> | undefined;
      if (toolName === 'message' && argumentsPayload) {
        openDispatchedWebConversation(argumentsPayload);
      }
      resolvedStreamEntry.executionSteps = updateLatestRunningExecutionStep(
        resolvedStreamEntry.executionSteps,
        (step) => (step.type || '').toLowerCase().includes('tool'),
        {
          toolName,
          arguments: argumentsPayload,
        },
      );
      updateMessage(conversationId, resolvedStreamEntry.messageId, {
        executionSteps: resolvedStreamEntry.executionSteps,
        isThinking: false,
        statusMessage: toolName ? t('chat.toolRunningNamed', { name: toolName }) : t('chat.toolRunning'),
      });
      return;
    }

    if (eventType === 'tool_result') {
      const toolName = eventData.tool_name as string | undefined;
      resolvedStreamEntry.executionSteps = updateLatestRunningExecutionStep(
        resolvedStreamEntry.executionSteps,
        (step) => (step.type || '').toLowerCase().includes('tool'),
        {
          toolName,
          result: eventData.result,
          executionTime: eventData.execution_time,
        },
      );
      updateMessage(conversationId, resolvedStreamEntry.messageId, {
        executionSteps: resolvedStreamEntry.executionSteps,
        statusMessage: toolName ? t('chat.toolResultNamed', { name: toolName }) : t('chat.toolResult'),
      });
      return;
    }

    if (eventType === 'step_start') {
      const stepId = (eventData.step_id as string) || Math.random().toString(36).substring(2, 15);
      const stepType = (eventData.step_type as string) || 'step';
      const title = (eventData.title as string) || inferExecutionStepTitle(t, stepType);
      let statusText: string | undefined;
      if (stepType === 'thinking') {
        statusText = t('chat.thinking');
      } else if (stepType === 'response') {
        statusText = t('chat.replying');
      } else if (stepType === 'tool_call') {
        statusText = t('chat.toolRunning');
      } else if (stepType === 'compression') {
        statusText = t('chat.compressingContext');
      }
      resolvedStreamEntry.executionSteps = upsertLocalizedExecutionStep(resolvedStreamEntry.executionSteps, {
        id: stepId,
        type: stepType,
        title,
        status: 'running',
        timestamp: new Date().toISOString(),
      });
      updateMessage(conversationId, resolvedStreamEntry.messageId, {
        executionSteps: resolvedStreamEntry.executionSteps,
        isThinking: stepType === 'thinking',
        statusMessage: statusText,
      });
      return;
    }

    if (eventType === 'step_complete') {
      const stepId = eventData.step_id as string | undefined;
      const status = normalizeExecutionStepStatus(eventData.status as string | undefined);
      const details = eventData.details as Record<string, unknown> | undefined;
      const existingStep = stepId
        ? resolvedStreamEntry.executionSteps.find((step) => step.id === stepId)
        : undefined;
      const mergedDetails = existingStep?.details
        ? { ...existingStep.details, ...(details || {}) }
        : details;
      const resolvedType = inferExecutionStepType(existingStep?.type, mergedDetails);
      const resolvedTitle = inferExecutionStepTitle(t, resolvedType, existingStep?.title, mergedDetails);
      resolvedStreamEntry.executionSteps = upsertLocalizedExecutionStep(resolvedStreamEntry.executionSteps, {
        id: stepId || Math.random().toString(36).substring(2, 15),
        type: resolvedType,
        title: resolvedTitle,
        status,
        timestamp: existingStep?.timestamp || new Date().toISOString(),
        details: mergedDetails,
      });

      let statusMessage: string | undefined;
      let isThinking = false;
      if (resolvedType === 'thinking') {
        statusMessage = status === 'error' || status === 'failed' ? t('chat.thinkingFailed') : t('chat.thinkingDone');
      } else if (resolvedType === 'tool_call') {
        statusMessage = status === 'error' || status === 'failed' ? t('chat.toolFailed') : t('chat.toolDone');
      } else if (resolvedType === 'response') {
        statusMessage = status === 'error' || status === 'failed' ? t('chat.responseFailed') : t('chat.responseDone');
      }

      const responseContent = resolvedType === 'response' && typeof mergedDetails?.content === 'string'
        ? mergedDetails.content
        : undefined;
      if (responseContent) {
        resolvedStreamEntry.content = responseContent;
      }

      updateMessage(conversationId, resolvedStreamEntry.messageId, {
        content: responseContent || resolvedStreamEntry.content,
        executionSteps: resolvedStreamEntry.executionSteps,
        isThinking,
        statusMessage,
      });
      return;
    }

    if (eventType === 'agent_done' || eventType === 'request_end') {
      const currentMessage = existingMessage(resolvedStreamEntry.messageId);
      const normalizedError = normalizeAssistantErrorContent(
        t,
        (eventData.content as string) || resolvedStreamEntry.content,
      );
      const providerError = normalizeProviderErrorPayload(eventData.provider_error);
      const eventFiles = normalizeMessageFiles(eventData.files);
      resolvedStreamEntry.phase = 'done';
      if (normalizedError.content) {
        resolvedStreamEntry.content = normalizedError.content;
      }
      resolvedStreamEntry.executionSteps = mergeLocalizedExecutionSteps(
        resolvedStreamEntry.executionSteps,
        incomingExecutionSteps,
      );
      updateMessage(conversationId, resolvedStreamEntry.messageId, {
        content: resolvedStreamEntry.content,
        isStreaming: false,
        isThinking: false,
        statusMessage: undefined,
        files: eventFiles ?? currentMessage?.files,
        executionSteps: resolvedStreamEntry.executionSteps,
        metadata: {
          ...(currentMessage?.metadata || {}),
          _relay_phase: 'done',
          ...(providerError ? { _provider_error: providerError } : {}),
          ...(Array.isArray(eventData.memory_sources) && eventData.memory_sources.length > 0
            ? { _memory_sources: eventData.memory_sources }
            : {}),
          ...(eventData.memory_recall && typeof eventData.memory_recall === 'object'
            ? { _memory_recall: eventData.memory_recall }
            : {}),
        },
        isError: Boolean(providerError) || normalizedError.isProviderError,
        errorKind: (Boolean(providerError) || normalizedError.isProviderError) ? 'provider' : undefined,
        retryable: providerError?.retryable ?? normalizedError.isProviderError,
      });
      if (agentId || resolvedStreamEntry.agentId) {
        removeTypingAgent(conversationId, agentId || resolvedStreamEntry.agentId);
      }
      void loadConversationHistory(conversationId);
      return;
    }

    if (eventType === 'done') {
      reconcileConversationAfterDone(
        conversationId,
        Array.from(registry.values()),
      );
      return;
    }

    if (eventType === 'error' || eventType === 'agent_error') {
      const normalizedError = normalizeAssistantErrorContent(
        t,
        (eventData.content as string) || (eventData.error as string) || t('chat.genericErrorRetry'),
      );
      resolvedStreamEntry.content = normalizedError.content || t('chat.genericErrorRetry');
      resolvedStreamEntry.phase = 'done';
      resolvedStreamEntry.executionSteps = finalizeRunningExecutionSteps(
        resolvedStreamEntry.executionSteps,
        'error',
        { error: resolvedStreamEntry.content },
      );
      updateMessage(conversationId, resolvedStreamEntry.messageId, {
        content: resolvedStreamEntry.content,
        isStreaming: false,
        isThinking: false,
        statusMessage: undefined,
        executionSteps: resolvedStreamEntry.executionSteps,
        metadata: {
          ...(existingMessage(resolvedStreamEntry.messageId)?.metadata || {}),
          _relay_phase: 'done',
        },
        isError: true,
        errorKind: normalizedError.isProviderError ? 'provider' : 'stream',
        retryable: normalizedError.isProviderError,
      });
      if (agentId || resolvedStreamEntry.agentId) {
        removeTypingAgent(conversationId, agentId || resolvedStreamEntry.agentId);
      }
      return;
    }

    if (eventType === 'stopped') {
      resolvedStreamEntry.phase = 'done';
      resolvedStreamEntry.executionSteps = finalizeRunningExecutionSteps(
        resolvedStreamEntry.executionSteps,
        'stopped',
        { stopped: true },
      );
      updateMessage(conversationId, resolvedStreamEntry.messageId, {
        content: resolvedStreamEntry.content || t('chat.stopped'),
        isStreaming: false,
        isThinking: false,
        statusMessage: undefined,
        executionSteps: resolvedStreamEntry.executionSteps,
        metadata: {
          ...(existingMessage(resolvedStreamEntry.messageId)?.metadata || {}),
          _relay_phase: 'done',
        },
      });
      if (agentId || resolvedStreamEntry.agentId) {
        removeTypingAgent(conversationId, agentId || resolvedStreamEntry.agentId);
      }
    }
  }, [
    addMessage,
    addTypingAgent,
    findPendingStreamEntry,
    getConversationStreamRegistry,
    getMessages,
    loadConversationHistory,
    mergeLocalizedExecutionSteps,
    openDispatchedWebConversation,
    reconcileConversationAfterDone,
    removeTypingAgent,
    t,
    upsertLocalizedExecutionStep,
    updateMessage,
  ]);

  useEffect(() => {
    websocketEventHandlerRef.current = (eventData: Record<string, unknown>) => {
      const sessionKey = typeof eventData.session_key === 'string' ? eventData.session_key : '';
      const dispatchOrigin = typeof eventData.dispatch_origin === 'string' ? eventData.dispatch_origin : '';
      const isSummaryMirror = dispatchOrigin === 'message_tool_summary_mirror';
      if (!sessionKey || (sessionKey === activePrimarySessionKeyRef.current && !isSummaryMirror)) {
        return;
      }

      const conversationId = sessionKeyToConversationId(sessionKey);
      if (!conversationId) {
        return;
      }

      applyRealtimeEventToConversation(conversationId, eventData);
      const sourceSessionKey = typeof eventData.source_session_key === 'string' ? eventData.source_session_key : '';
      if (
        isSummaryMirror
        && sourceSessionKey
        && sourceSessionKey === activePrimarySessionKeyRef.current
      ) {
        const sourceConversationId = sessionKeyToConversationId(sourceSessionKey);
        const sourceConversationName = conversations.find((conversation) => conversation.id === sourceConversationId)?.name || t('chat.teamRelay');
        const destinationConversationName = conversations.find((conversation) => conversation.id === conversationId)?.name || t('chat.directMessage');
        setCurrentConversation(conversationId);
        showBatonNavigationNotice({
          tone: 'dm',
          message: t('chat.returnedToDirectNotice', { name: destinationConversationName }),
          actionLabel: t('chat.reviewSourceConversation', { name: sourceConversationName }),
          actionConversationId: sourceConversationId,
        });
      }
    };
  }, [applyRealtimeEventToConversation, conversations, setCurrentConversation, showBatonNavigationNotice]);

  useEffect(() => {
    let disposed = false;

    const connect = () => {
      if (disposed || chatWebSocketRef.current) {
        return;
      }

      const ws = new WebSocket(resolveChatWebSocketUrl());
      chatWebSocketRef.current = ws;

      ws.onopen = () => {
        subscribedSessionKeysRef.current.forEach((sessionKey) => {
          ws.send(JSON.stringify({
            type: 'subscribe',
            session_key: sessionKey,
          }));
        });
      };

      ws.onmessage = (messageEvent) => {
        try {
          const payload = JSON.parse(messageEvent.data) as Record<string, unknown>;
          if (payload.type === 'subscribed' || payload.type === 'unsubscribed' || payload.type === 'error') {
            return;
          }
          websocketEventHandlerRef.current?.(payload);
        } catch (error) {
          console.error('Failed to parse chat websocket event:', error);
        }
      };

      ws.onerror = () => {
        ws.close();
      };

      ws.onclose = () => {
        if (chatWebSocketRef.current === ws) {
          chatWebSocketRef.current = null;
        }
        if (disposed) {
          return;
        }
        chatWebSocketReconnectTimerRef.current = window.setTimeout(() => {
          chatWebSocketReconnectTimerRef.current = null;
          connect();
        }, 1200);
      };
    };

    connect();

    return () => {
      disposed = true;
      if (chatWebSocketReconnectTimerRef.current) {
        clearTimeout(chatWebSocketReconnectTimerRef.current);
        chatWebSocketReconnectTimerRef.current = null;
      }
      if (chatWebSocketRef.current) {
        chatWebSocketRef.current.close();
        chatWebSocketRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!currentConversationId) {
      return;
    }
    const sessionKey = conversationIdToSessionKey(currentConversationId);
    subscribedSessionKeysRef.current.add(sessionKey);
    if (chatWebSocketRef.current?.readyState === WebSocket.OPEN) {
      chatWebSocketRef.current.send(JSON.stringify({
        type: 'subscribe',
        session_key: sessionKey,
      }));
    }
  }, [currentConversationId]);
  
  useEffect(() => {
    if (currentConversationId) {
      void loadConversationHistory(currentConversationId, { forceRefreshLatest: true });
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
    const agent = directAgents.find(a => a.id === agentId);
    if (agent) {
      const conv = getOrCreateDMConversation(agentId, agent.name);
      setCurrentConversation(conv.id);
      void loadConversationHistory(conv.id, { forceRefreshLatest: true });
      setSelectedAgentId(agentId);
      setSelectedTeamId(null);
    }
  }, [directAgents, getOrCreateDMConversation, loadConversationHistory, setCurrentConversation]);
  
  const handleSelectTeam = useCallback((teamId: string) => {
    const team = teams.find(t => t.id === teamId);
    if (team) {
      const conv = getOrCreateTeamConversation(teamId, team.name, team.members, team.description);
      setCurrentConversation(conv.id);
      void loadConversationHistory(conv.id, { forceRefreshLatest: true });
      setSelectedTeamId(teamId);
      setSelectedAgentId(null);
    }
  }, [teams, getOrCreateTeamConversation, loadConversationHistory, setCurrentConversation]);

  const handleLoadOlderHistory = useCallback(() => {
    if (!currentConversationId || isLoadingOlderHistory) {
      return;
    }
    void loadConversationHistory(currentConversationId, { mode: 'before' });
  }, [currentConversationId, isLoadingOlderHistory, loadConversationHistory]);

  const handleJumpBackToLatestHistory = useCallback(() => {
    if (!currentConversationId || historyLoadingState.conversationId === currentConversationId) {
      return;
    }
    void loadConversationHistory(currentConversationId, {
      mode: 'initial',
      forceRefreshLatest: true,
    });
  }, [currentConversationId, historyLoadingState.conversationId, loadConversationHistory]);

  const fetchRemoteHistorySearch = useCallback(async (
    convId: string,
    query: string,
    options: {
      append?: boolean;
      offset?: number;
      signal?: AbortSignal;
    } = {},
  ) => {
    const since = resolveHistorySearchSince(historySearchTimeRange);
    const response = await fetch(buildConversationSearchUrl(convId, query, {
      limit: CONVERSATION_HISTORY_SEARCH_PAGE_SIZE,
      offset: options.offset,
      since,
    }), options.signal ? { signal: options.signal } : undefined);
    const data = await response.json();
    const nextMatches = Array.isArray(data.matches) ? data.matches as RemoteHistorySearchMatch[] : [];
    setRemoteHistorySearchMatches((prev) => (
      options.append ? [...prev, ...nextMatches] : nextMatches
    ));
    setRemoteHistorySearchTotal(typeof data.total_matches === 'number' ? data.total_matches : 0);
    setRemoteHistorySearchHasMore(Boolean(data.has_more));
    setRemoteHistorySearchOffset(typeof data.next_offset === 'number'
      ? data.next_offset
      : ((options.offset || 0) + nextMatches.length));
  }, [historySearchTimeRange]);

  const handleLoadMoreRemoteHistorySearch = useCallback(async () => {
    if (!currentConversationId || !historySearchQuery.trim() || !remoteHistorySearchHasMore || isRemoteHistorySearchLoadingMore) {
      return;
    }
    setIsRemoteHistorySearchLoadingMore(true);
    try {
      await fetchRemoteHistorySearch(currentConversationId, historySearchQuery.trim(), {
        append: true,
        offset: remoteHistorySearchOffset,
      });
    } catch (error) {
      console.error('Failed to load more full-history search results:', error);
    } finally {
      setIsRemoteHistorySearchLoadingMore(false);
    }
  }, [
    currentConversationId,
    fetchRemoteHistorySearch,
    historySearchQuery,
    isRemoteHistorySearchLoadingMore,
    remoteHistorySearchHasMore,
    remoteHistorySearchOffset,
  ]);

  const handleSelectRemoteHistorySearchMatch = useCallback(async (match: RemoteHistorySearchMatch) => {
    if (!currentConversationId || isLoadingHistorySearchContext) {
      return;
    }
    pendingHistorySearchJumpRef.current = {
      conversationId: currentConversationId,
      messageId: match.message_id,
    };
    setActiveRemoteHistoryResultId(match.message_id);
    await loadConversationHistory(currentConversationId, {
      mode: 'around',
      aroundId: match.message_id,
    });
  }, [currentConversationId, isLoadingHistorySearchContext, loadConversationHistory]);
  
  const handleSendMessage = useCallback(async (
    content: string,
    mentionedAgents: string[],
    files: MessageFile[] = [],
  ) => {
    if (!currentConversation || !content.trim() || !isOnline) return;

    if (activeStreamPromiseRef.current) {
      await requestStopGeneration();
      await waitForActiveStreamToSettle();
      toast.info(t('chat.requestStoppedSwitching'), 2400);
      showInterruptNotice(t('chat.requestStoppedSwitching'), 'info');
    }

    const trimmedContent = content.trim();
    const normalizedFiles = normalizeMessageFiles(files) || [];
    const uploadedFiles = serializeMessageFiles(normalizedFiles);
    const retryRequest: RetryRequest = {
      conversationId: currentConversation.id,
      content: trimmedContent,
      mentionedAgents,
      files: normalizedFiles,
    };
    let requestHadFailure = false;
    const markRequestFailed = () => {
      requestHadFailure = true;
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
    setLastFailedTurnId(null);
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

    if (currentConversation.type === ConversationType.DM && currentConversation.targetId) {
      const pendingAgentId = currentConversation.targetId;
      const pendingMessageId = generateId();
      const pendingKey = `pending:${pendingAgentId}:${pendingMessageId}`;
      const pendingAgentName = directAgents.find((agent) => agent.id === pendingAgentId)?.name || currentConversation.name;

      agentMessages.set(pendingKey, {
        messageId: pendingMessageId,
        content: '',
        turnId: userMessage.id,
        agentId: pendingAgentId,
        phase: 'pending',
        executionSteps: [],
      });

      addMessage(currentConversation.id, {
        id: pendingMessageId,
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
        turnId: userMessage.id,
        agentId: pendingAgentId,
        agentName: pendingAgentName,
        isStreaming: true,
        statusMessage: t('chat.streamingInput'),
        executionSteps: [],
        metadata: {
          _relay_phase: 'pending',
        },
      });
    }

    const localAbortController = new AbortController();
    const requestRef = { id: null as string | null };
    activeRequestPayloadRef.current = retryRequest;
    activeTurnIdRef.current = userMessage.id;
    abortControllerRef.current = localAbortController;
    currentRequestIdRef.current = null;

    const streamPromise = (async () => {
      try {
        const sessionKey = `web:${currentConversation.id}`;
        activePrimarySessionKeyRef.current = sessionKey;
        subscribedSessionKeysRef.current.add(sessionKey);
        if (chatWebSocketRef.current?.readyState === WebSocket.OPEN) {
          chatWebSocketRef.current.send(JSON.stringify({
            type: 'subscribe',
            session_key: sessionKey,
          }));
        }
        
        await chatService.streamChat({
          message: trimmedContent,
          sessionKey,
          files: uploadedFiles,
          conversationId: currentConversation.id,
          conversationType: currentConversation.type,
          agentId: currentConversation.type === ConversationType.DM ? currentConversation.targetId : undefined,
          teamId: currentConversation.type === ConversationType.TEAM ? currentConversation.targetId : undefined,
          groupChat: currentConversation.type === ConversationType.TEAM,
          mentionedAgents,
          timeout: 240000,
          connectTimeout: 15000,
          onStateChange: (state) => {
            setStreamState(state);
            if (state === 'timeout' || state === 'error') {
              markRequestFailed();
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
                  statusMessage: streamEntry.content ? t('chat.streamingInput') : t('chat.batonStarted'),
                  metadata: {
                    ...(getMessages(currentConversation.id).find((message) => message.id === streamEntry.messageId)?.metadata || {}),
                    _relay_phase: 'active',
                  },
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
                  statusMessage: pendingEntry.content ? t('chat.streamingInput') : t('chat.batonStarted'),
                  metadata: {
                    ...(getMessages(currentConversation.id).find((message) => message.id === pendingEntry.messageId)?.metadata || {}),
                    _relay_phase: 'active',
                  },
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
                  statusMessage: t('chat.streamingInput'),
                  executionSteps: [],
                  metadata: { _relay_phase: 'active' },
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
                ? t('chat.handoffWaitSummary')
                : handoffMode === 'continue'
                  ? t('chat.handoffWaitContinue')
                  : t('chat.handoffWaitResponse');
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
                  _relay_phase: 'pending',
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
                statusMessage: t('chat.thinking'),
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
            const isSyntheticProgress = Boolean(eventData.synthetic_progress);
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
                isThinking: isSyntheticProgress,
                executionSteps: agentMsg.executionSteps,
              });
            }
          }
          // 处理工具开始事件
          else if (eventType === 'tool_start') {
            const toolName = eventData.tool_name as string | undefined;
            const argumentsPayload = eventData.arguments as Record<string, unknown> | undefined;
            if (toolName === 'message' && argumentsPayload) {
              const targetChatId = typeof argumentsPayload.chat_id === 'string' ? argumentsPayload.chat_id.trim() : '';
              const shouldActivateRelayConversation = (
                currentConversation.type === ConversationType.DM
                && targetChatId.startsWith('team_')
              );
              openDispatchedWebConversation(argumentsPayload, {
                activate: shouldActivateRelayConversation,
              });
            }
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
                statusMessage: toolName ? t('chat.toolRunningNamed', { name: toolName }) : t('chat.toolRunning'),
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
                statusMessage: toolName ? t('chat.toolResultNamed', { name: toolName }) : t('chat.toolResult'),
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
            const title = (eventData.title as string) || inferExecutionStepTitle(t, stepType);
            if (agentId && matchedStreamEntry) {
              const agentMsg = matchedStreamEntry;
              let statusText: string | undefined;
              if (stepType === 'thinking') {
                statusText = t('chat.thinking');
              } else if (stepType === 'response') {
                statusText = t('chat.replying');
              } else if (stepType === 'tool_call') {
                statusText = t('chat.toolRunning');
              } else if (stepType === 'compression') {
                statusText = t('chat.compressingContext');
              }
              agentMsg.executionSteps = upsertLocalizedExecutionStep(agentMsg.executionSteps, {
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
              const resolvedTitle = inferExecutionStepTitle(t, resolvedType, existingStep?.title, mergedDetails);
              agentMsg.executionSteps = upsertLocalizedExecutionStep(agentMsg.executionSteps, {
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
                  ? t('chat.thinkingFailed')
                  : t('chat.thinkingDone');
              } else if (resolvedType === 'tool_call') {
                statusMessage = status === 'error' || status === 'failed'
                  ? t('chat.toolFailed')
                  : t('chat.toolDone');
              } else if (resolvedType === 'response') {
                statusMessage = status === 'error' || status === 'failed'
                  ? t('chat.responseFailed')
                  : t('chat.responseDone');
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
              const normalizedError = normalizeAssistantErrorContent(t, finalContentFromEvent || agentMsg.content);
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
                markRequestFailed();
                setLastFailedRequest(retryRequest);
                setLastFailedTurnId(userMessage.id);
                setShowReconnect(true);
              }
            }
          }
          // 所有响应完成
          else if (eventType === 'done') {
            setIsLoading(false);
            setStreamState(null);
            if (!requestHadFailure) {
              setShowReconnect(false);
              setLastFailedRequest(null);
              setLastFailedTurnId(null);
            }
            reconcileConversationAfterDone(
              currentConversation.id,
              Array.from(agentMessages.values()),
            );
          }
          // 后端处理失败
          else if (eventType === 'error' || eventType === 'agent_error') {
            const normalizedError = normalizeAssistantErrorContent(
              t,
              (eventData.content as string) || (eventData.error as string) || t('chat.genericErrorRetry'),
            );
            const errorContent = normalizedError.content || t('chat.genericErrorRetry');
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
                requestId: requestRef.id || undefined,
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
                requestId: requestRef.id || undefined,
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
            markRequestFailed();
            setLastFailedRequest(retryRequest);
            setLastFailedTurnId(userMessage.id);
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
                content: agentMsg.content || t('chat.stopped'),
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
              content: (eventData.content as string) || t('chat.discussionStopped'),
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
              content: agentMsg.content || t('chat.stopped'),
              isStreaming: false,
              isThinking: false,
              statusMessage: undefined,
              executionSteps: agentMsg.executionSteps,
            });
            removeTypingAgent(currentConversation.id, agentMsg.agentId);
          });
        } else {
          if (error instanceof ChatStreamError && error.code === 'timeout' && requestRef.id) {
            const settledFromHistory = await settleTimedOutRequestFromHistory(
              currentConversation.id,
              requestRef.id,
              Array.from(agentMessages.values()),
            );
            if (settledFromHistory) {
              setShowReconnect(false);
              setLastFailedRequest(null);
              setLastFailedTurnId(null);
              return;
            }
          }
          console.error('Chat error:', error);
          const failure = resolveStreamFailureMessage(t, error);
          if (agentMessages.size === 0) {
            addMessage(currentConversation.id, {
              id: generateId(),
              role: 'assistant',
              content: failure.content,
              timestamp: new Date().toISOString(),
              requestId: requestRef.id || undefined,
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
              requestId: requestRef.id || undefined,
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
          markRequestFailed();
          setLastFailedRequest(retryRequest);
          setLastFailedTurnId(userMessage.id);
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
        if (activePrimarySessionKeyRef.current === `web:${currentConversation.id}`) {
          activePrimarySessionKeyRef.current = null;
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
        ? directAgents.find((agent) => agent.id === currentConversation.agentIds?.[0])
        : undefined;
      if (currentConversation.type === ConversationType.DM && currentDmAgent && (currentDmAgent.setup_required || currentDmAgent.bootstrap_setup_pending)) {
        void refreshAgents();
      }
    }
  }, [currentConversation, directAgents, addMessage, updateMessage, addTypingAgent, removeTypingAgent, isOnline, requestStopGeneration, waitForActiveStreamToSettle, toast, showInterruptNotice, refreshAgents, openDispatchedWebConversation, reconcileConversationAfterDone, t]);

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
  
  const getAgentName = useCallback((agentId?: string) => {
    if (!agentId) return undefined;
    return directAgents.find(a => a.id === agentId)?.name;
  }, [directAgents]);

  const messageTurns = useMemo(() => buildMessageTurns(messages), [messages]);
  const deferredHistorySearchQuery = useDeferredValue(historySearchQuery);
  const normalizedHistorySearchQuery = useMemo(
    () => normalizeSearchText(deferredHistorySearchQuery),
    [deferredHistorySearchQuery],
  );
  const trimmedHistorySearchQuery = useMemo(
    () => deferredHistorySearchQuery.trim(),
    [deferredHistorySearchQuery],
  );
  const lastFailedTurnRequestId = useMemo(() => {
    if (!lastFailedTurnId) {
      return undefined;
    }
    const failedTurn = messageTurns.find((turn) => turn.userMessage?.id === lastFailedTurnId);
    return failedTurn ? resolveTurnRequestId(failedTurn) : undefined;
  }, [lastFailedTurnId, messageTurns]);
  const historySearchMatches = useMemo<HistorySearchMatch[]>(() => {
    if (!normalizedHistorySearchQuery) {
      return [];
    }

    const matches: HistorySearchMatch[] = [];
    messageTurns.forEach((turn, turnIndex) => {
      if (turn.userMessage) {
        const normalized = normalizeSearchText(turn.userMessage.content);
        if (normalized.includes(normalizedHistorySearchQuery)) {
          matches.push({
            key: `user:${turn.id}`,
            turnId: turn.id,
            role: 'user',
            label: t('chat.historyTurnUserLabel', { turn: turnIndex + 1 }),
            preview: buildSearchPreview(turn.userMessage.content),
            messageIds: [turn.userMessage.id],
          });
        }
      }

      turn.responseGroups.forEach((group, groupIndex) => {
        const content = group
          .map((message) => cleanHistoryMessageContent(message.content || ''))
          .join('\n');
        const normalized = normalizeSearchText(content);
        if (!normalized.includes(normalizedHistorySearchQuery)) {
          return;
        }
        const firstMessage = group[0];
        matches.push({
          key: `${turn.id}:${groupIndex}`,
          turnId: turn.id,
          groupIndex,
          role: 'assistant',
          label: t('chat.historyTurnAssistantLabel', {
            turn: turnIndex + 1,
            name: firstMessage?.agentName || getAgentName(firstMessage?.agentId) || t('chat.assistantFallback'),
          }),
          preview: buildSearchPreview(content),
          messageIds: group.map((message) => message.id),
        });
      });
    });

    return matches;
  }, [getAgentName, messageTurns, normalizedHistorySearchQuery, t]);

  const activeHistoryMatch = historySearchMatches.length > 0
    ? historySearchMatches[Math.min(historySearchIndex, historySearchMatches.length - 1)]
    : null;
  const remoteHistorySearchVisibleMatches = useMemo(
    () => remoteHistorySearchMatches.filter((match) => (
      findHistorySearchMatchIndexByMessageId(historySearchMatches, match.message_id) < 0
    )),
    [historySearchMatches, remoteHistorySearchMatches],
  );

  useEffect(() => {
    setExpandedTurnIds({});
  }, [currentConversation?.id]);

  useEffect(() => {
    setHistorySearchQuery('');
    setHistorySearchIndex(0);
    setIsHistorySearchOpen(false);
    setHistorySearchTimeRange('all');
    setActiveHistoryResultKey(null);
    setRemoteHistorySearchMatches([]);
    setRemoteHistorySearchTotal(0);
    setRemoteHistorySearchHasMore(false);
    setRemoteHistorySearchOffset(0);
    setIsRemoteHistorySearchLoadingMore(false);
    setActiveRemoteHistoryResultId(null);
    remoteHistorySearchAbortRef.current?.abort();
    remoteHistorySearchAbortRef.current = null;
    pendingHistorySearchJumpRef.current = null;
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
    if (!currentConversationId) {
      return undefined;
    }

    if (!trimmedHistorySearchQuery || !isPartialHistoryLoaded) {
      remoteHistorySearchAbortRef.current?.abort();
      remoteHistorySearchAbortRef.current = null;
      setRemoteHistorySearchMatches([]);
      setRemoteHistorySearchTotal(0);
      setRemoteHistorySearchHasMore(false);
      setRemoteHistorySearchOffset(0);
      setIsRemoteHistorySearchLoading(false);
      setIsRemoteHistorySearchLoadingMore(false);
      return undefined;
    }

    const controller = new AbortController();
    remoteHistorySearchAbortRef.current?.abort();
    remoteHistorySearchAbortRef.current = controller;
    setIsRemoteHistorySearchLoading(true);

    const timerId = window.setTimeout(() => {
      void fetchRemoteHistorySearch(currentConversationId, trimmedHistorySearchQuery, {
        signal: controller.signal,
      })
        .then(() => {
          if (controller.signal.aborted) {
            return;
          }
        })
        .catch((error: unknown) => {
          if (controller.signal.aborted) {
            return;
          }
          console.error('Failed to search full conversation history:', error);
          setRemoteHistorySearchMatches([]);
          setRemoteHistorySearchTotal(0);
          setRemoteHistorySearchHasMore(false);
          setRemoteHistorySearchOffset(0);
        })
        .finally(() => {
          if (remoteHistorySearchAbortRef.current === controller) {
            remoteHistorySearchAbortRef.current = null;
          }
          if (!controller.signal.aborted) {
            setIsRemoteHistorySearchLoading(false);
          }
        });
    }, 220);

    return () => {
      window.clearTimeout(timerId);
      controller.abort();
      if (remoteHistorySearchAbortRef.current === controller) {
        remoteHistorySearchAbortRef.current = null;
      }
      setIsRemoteHistorySearchLoading(false);
    };
  }, [currentConversationId, fetchRemoteHistorySearch, isPartialHistoryLoaded, trimmedHistorySearchQuery]);

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
    const pendingJump = pendingHistorySearchJumpRef.current;
    if (!pendingJump || pendingJump.conversationId !== currentConversationId) {
      return;
    }

    const matchIndex = findHistorySearchMatchIndexByMessageId(historySearchMatches, pendingJump.messageId);
    if (matchIndex < 0) {
      return;
    }

    pendingHistorySearchJumpRef.current = null;
    setHistorySearchIndex(matchIndex);
  }, [currentConversationId, historySearchMatches]);

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
  
  const getRelayGroupLabelLocalized = useCallback((group: UIMessage[], index: number): string => {
    const { sourceName, targetName, conversationType, handoffMode } = getRelayGroupTransition(group, getAgentName);
    if (conversationType === 'user_to_agent' && targetName) {
      return t('chat.relayLabelToUser', { name: targetName });
    }
    if (handoffMode === 'summary' && sourceName && targetName) {
      return t('chat.relayLabelSummary', { source: sourceName, target: targetName });
    }
    if (sourceName && targetName && sourceName !== targetName) {
      return t('chat.relayLabelTransfer', { source: sourceName, target: targetName });
    }
    return targetName || t('chat.assistantIndexed', { index: index + 1 });
  }, [getAgentName, t]);

  const getRelayGroupStateDetailLocalized = useCallback((group: UIMessage[]): string => {
    const lastMessage = group[group.length - 1];
    const state = getRelayGroupState(group);
    const { sourceName, targetName, conversationType, handoffMode } = getRelayGroupTransition(group, getAgentName);

    if (state === 'error') {
      return lastMessage.errorKind === 'provider'
        ? t('chat.errorProvider')
        : lastMessage.errorKind === 'timeout'
          ? t('chat.errorTimeout')
          : lastMessage.errorKind === 'network'
            ? t('chat.errorNetwork')
            : t('chat.errorRequestFailed');
    }
    if (state === 'waiting') {
      if (handoffMode === 'summary' && sourceName && targetName) {
        return t('chat.waitSummaryReturn', { name: targetName });
      }
      if (handoffMode === 'continue' && sourceName && targetName) {
        return t('chat.waitContinueDiscussion', { source: sourceName, target: targetName });
      }
      return lastMessage.statusMessage || t('chat.waitRelay');
    }
    if (state === 'active') {
      if (handoffMode === 'summary' && targetName) {
        return t('chat.summaryInProgress', { name: targetName });
      }
      if (sourceName && targetName && sourceName !== targetName) {
        return t('chat.takingPreviousBaton', { source: sourceName, target: targetName });
      }
      return lastMessage.isThinking
        ? t('chat.thinkingShort')
        : (lastMessage.statusMessage || t('chat.statusActive'));
    }
    if (conversationType === 'user_to_agent') {
      return targetName ? t('chat.outputToUser', { name: targetName }) : t('chat.outputToUserFallback');
    }
    if (sourceName && targetName && sourceName !== targetName) {
      return t('chat.handoffReplyDone', { source: sourceName, target: targetName });
    }
    return t('chat.replyDone');
  }, [getAgentName, t]);

  const getRelayTimelineStepsLocalized = useCallback((turn: MessageTurn): RelayTimelineStep[] => {
    const assistantGroups = turn.responseGroups.filter((group) => group[0]?.role === 'assistant');
    return assistantGroups.map((group, index) => {
      const firstMessage = group[0];
      return {
        key: `${turn.id}:${firstMessage.id}:${index}`,
        label: getRelayGroupLabelLocalized(group, index),
        state: getRelayGroupState(group),
        detail: getRelayGroupStateDetailLocalized(group),
        isFinal: index === assistantGroups.length - 1,
        groupIndex: index,
      };
    });
  }, [getRelayGroupLabelLocalized, getRelayGroupStateDetailLocalized]);

  const formatCollapsedRelayLabelsLocalized = useCallback((labels: string[]): string => {
    if (labels.length === 0) {
      return t('chat.collapsedRelayNone');
    }
    if (labels.length === 1) {
      return t('chat.collapsedRelaySingle', { label: labels[0] });
    }
    if (labels.length === 2) {
      return t('chat.collapsedRelayDouble', { first: labels[0], second: labels[1] });
    }
    return t('chat.collapsedRelayMany', { first: labels[0], second: labels[1], count: labels.length });
  }, [t]);

  const streamStateLabels = useMemo<Partial<Record<StreamState, string>>>(() => ({
    connecting: t('chat.streamStateConnecting'),
    waiting: t('chat.streamStateWaiting'),
    receiving: t('chat.streamStateReceiving'),
    timeout: t('chat.streamStateTimeout'),
    error: t('chat.streamStateError'),
  }), [t]);

  const formatAgentNamesForStatusLocalized = useCallback((names: string[]): string => {
    return formatAgentNamesForStatus(t, names);
  }, [t]);

  const buildRequestPreviewLocalized = useCallback((content: string, maxLength = 18) => (
    buildRequestPreview(t, content, maxLength)
  ), [t]);

  const defaultOnboardingChecklist = useMemo(() => ([
    t('chat.defaultChecklistResponsibility'),
    t('chat.defaultChecklistOutputStyle'),
    t('chat.defaultChecklistRiskBoundary'),
    t('chat.defaultChecklistCollaboration'),
  ]), [t]);

  const defaultStarterPrompts = useMemo(() => ([
    t('chat.defaultStarterPrompt1'),
    t('chat.defaultStarterPrompt2'),
    t('chat.defaultStarterPrompt3'),
  ]), [t]);

  const currentDirectAgent = useMemo(() => {
    if (currentConversation?.type !== ConversationType.DM) {
      return selectedAgentId ? directAgents.find((agent) => agent.id === selectedAgentId) : undefined;
    }
    const conversationAgentId = currentConversation.agentIds?.[0];
    return directAgents.find((agent) => agent.id === conversationAgentId) || (selectedAgentId ? directAgents.find((agent) => agent.id === selectedAgentId) : undefined);
  }, [directAgents, currentConversation, selectedAgentId]);

  const currentTeamMembers = useMemo(() => {
    if (currentConversation?.type !== ConversationType.TEAM) {
      return [];
    }

    const liveTeam = teams.find((team) => team.id === currentConversation.targetId);
    const memberIds = liveTeam?.members || currentConversation.agentIds || [];
    return directAgents.filter((agent) => memberIds.includes(agent.id));
  }, [currentConversation, directAgents, teams]);

  const currentTeamMentionableAgents = useMemo(() => {
    if (currentConversation?.type !== ConversationType.TEAM) {
      return [];
    }

    return currentTeamMembers;
  }, [currentConversation?.type, currentTeamMembers]);

  const currentDirectAgentProfilePreset = useMemo(
    () => getAgentProfilePreset(t, currentDirectAgent?.profile),
    [currentDirectAgent?.profile, t],
  );

  const currentDirectAgentPermissionPreset = useMemo(
    () => getAgentPermissionPreset(t, currentDirectAgent?.tool_permission_profile),
    [currentDirectAgent?.tool_permission_profile, t],
  );

  const currentDirectOnboardingChecklist = useMemo(
    () => currentDirectAgentProfilePreset?.onboardingChecklist || defaultOnboardingChecklist,
    [currentDirectAgentProfilePreset, defaultOnboardingChecklist],
  );

  const currentDirectStarterPrompts = useMemo(
    () => currentDirectAgentProfilePreset?.starterPrompts || defaultStarterPrompts,
    [currentDirectAgentProfilePreset, defaultStarterPrompts],
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
    ? t('chat.currentConversationSummaryTeam', { count: currentTeamMembers.length })
    : currentDirectAgentProfilePreset
      ? t('chat.currentConversationSummaryDirectProfile', { label: currentDirectAgentProfilePreset.label })
      : t('chat.currentConversationSummaryDirect');
  const conversationWorkbench = useMemo(() => {
    const latestTurn = [...messageTurns].reverse().find((turn) => turn.userMessage || turn.assistantMessages.length > 0);
    const latestUserMessage = latestTurn?.userMessage || [...messages].reverse().find((message) => message.role === 'user');
    const executionSteps = latestTurn?.assistantMessages.flatMap((message) => message.executionSteps || []) || [];
    const runningSteps = executionSteps.filter((step) => step.status === 'running' || step.status === 'pending').length;
    const failedSteps = executionSteps.filter((step) => step.status === 'failed' || step.status === 'error').length;
    const completedSteps = executionSteps.filter((step) => (
      step.status === 'completed' || step.status === 'success' || step.status === 'skipped' || step.status === 'stopped'
    )).length;
    const toolNames = Array.from(new Set(
      executionSteps
        .map((step) => String(step.details?.toolName || step.details?.tool_name || '').trim())
        .filter(Boolean),
    ));
    const fileCount = messages.reduce((total, message) => total + (message.files?.length || 0), 0);
    const activeStreamingCount = messages.filter((message) => message.role === 'assistant' && message.isStreaming).length;
    const activeAgents = currentConversation?.type === ConversationType.TEAM
      ? currentTeamMembers.map((agent) => agent.name)
      : currentDirectAgent
        ? [currentDirectAgent.name]
        : [];
    const lastUpdatedAt = [...messages].reverse().find((message) => message.timestamp)?.timestamp;
    const stage = isLoading || activeStreamingCount > 0
      ? t('chat.workbenchStageRunning')
      : failedSteps > 0 || latestTurn?.hasError
        ? t('chat.workbenchStageNeedsReview')
        : latestTurn?.assistantMessages.length
          ? t('chat.workbenchStageDone')
          : t('chat.workbenchStageReady');

    return {
      latestRequest: latestUserMessage?.content
        ? buildRequestPreviewLocalized(latestUserMessage.content, 64)
        : t('chat.workbenchNoRequest'),
      stage,
      activeAgents,
      fileCount,
      executionSteps: executionSteps.length,
      runningSteps,
      failedSteps,
      completedSteps,
      toolNames,
      relayCount: latestTurn?.relayCount || 0,
      lastUpdatedAt,
    };
  }, [
    buildRequestPreviewLocalized,
    currentConversation?.type,
    currentDirectAgent,
    currentTeamMembers,
    isLoading,
    messageTurns,
    messages,
    t,
  ]);
  const currentConversationHealth = useMemo<ConversationHealth | null>(() => {
    const turnCount = messageTurns.length;
    const approxTokens = estimateConversationTokens(messages);

    if (approxTokens >= 16000 || turnCount >= 24) {
      return {
        tone: 'danger',
        approxTokens,
        turnCount,
      };
    }

    if (approxTokens >= 10000 || turnCount >= 16) {
      return {
        tone: 'warning',
        approxTokens,
        turnCount,
      };
    }

    return null;
  }, [messageTurns.length, messages]);

  const shouldVirtualizeTurns = useMemo(() => (
    messageTurns.length >= TURN_VIRTUALIZATION_THRESHOLD
    && !historySearchQuery.trim()
    && !activeHistoryResultKey
    && !activeRemoteHistoryResultId
    && !pendingRelayJump
    && !highlightedRelayGroupKey
    && !isLoadingHistorySearchContext
  ), [
    activeHistoryResultKey,
    activeRemoteHistoryResultId,
    highlightedRelayGroupKey,
    historySearchQuery,
    isLoadingHistorySearchContext,
    messageTurns.length,
    pendingRelayJump,
  ]);

  const {
    turnListContainerRef,
    turnHeightVersion,
    turnVirtualizationMetrics,
    visibleVirtualizedTurnIndexes,
    registerVirtualizedTurnElement,
  } = useTurnVirtualization({
    messageTurns,
    shouldVirtualizeTurns,
    scrollContainerRef: chatContainerRef,
    currentConversationId,
    currentConversationType: currentConversation?.type,
    canJumpBackToLatest,
    currentConversationHealth,
    hasMoreBefore: currentHistoryWindow?.hasMoreBefore,
    onNearBottomChange: setIsNearBottom,
  });

  useLayoutEffect(() => {
    if (!currentConversationId) {
      return;
    }
    if (bottomStickConversationIdRef.current !== currentConversationId) {
      return;
    }
    stickConversationToBottom(currentConversationId, 2);
  }, [currentConversationId, stickConversationToBottom, turnHeightVersion]);

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
      if (message.metadata?._relay_phase !== 'pending') {
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
        message: t('chat.sessionOffline'),
      };
    }

    if (showReconnect && canRetryCurrentConversation) {
      return {
        tone: 'warning',
        message: t('chat.sessionRetryLastMessage'),
        detailLabel: lastFailedTurnRequestId ? t('chat.requestIdLabel') : undefined,
        detailValue: lastFailedTurnRequestId,
        actionLabel: t('chat.retryLastMessage'),
        onAction: handleRetryLastRequest,
        dismissible: true,
        onDismiss: () => {
          setShowReconnect(false);
          setLastFailedTurnId(null);
        },
      };
    }

    if (showReconnect) {
      return {
        tone: 'warning',
        message: t('chat.sessionDisconnected'),
        dismissible: true,
        onDismiss: () => setShowReconnect(false),
      };
    }

    if (interruptNotice) {
      const resumeActionLabel = canResumeInterruptedRequest && lastInterruptedRequest
        ? t('chat.resumeRequest', { preview: buildRequestPreviewLocalized(lastInterruptedRequest.content) })
        : undefined;
      return {
        tone: interruptNotice.tone,
        message: interruptNotice.message,
        actionLabel: interruptNotice.tone === 'success' && canResumeInterruptedRequest
          ? resumeActionLabel
          : (interruptNotice.tone === 'success' ? t('chat.continueInput') : undefined),
        onAction: interruptNotice.tone === 'success'
          ? (canResumeInterruptedRequest ? handleResumeInterruptedRequest : requestInputFocus)
          : undefined,
        secondaryActionLabel: interruptNotice.tone === 'success' && canResumeInterruptedRequest ? t('chat.continueInput') : undefined,
        onSecondaryAction: interruptNotice.tone === 'success' && canResumeInterruptedRequest ? requestInputFocus : undefined,
        dismissible: true,
        onDismiss: dismissInterruptNotice,
      };
    }

    if (isLoading && streamState && streamStateLabels[streamState]) {
      const pendingAgentLabel = formatAgentNamesForStatusLocalized(relayStatusSnapshot.pendingAgentNames);
      const activeAgentLabel = relayStatusSnapshot.activeProcessingAgentName
        || formatAgentNamesForStatusLocalized(relayStatusSnapshot.activeAgentNames);
      const stopActionLabel = currentConversation?.type === ConversationType.TEAM
        ? t('chat.stopRelay')
        : t('chat.stopGeneration');

      if (pendingAgentLabel && activeAgentLabel) {
        return {
          tone: 'info',
          message: t('chat.sessionProcessingWithPending', { active: activeAgentLabel, pending: pendingAgentLabel }),
          actionLabel: stopActionLabel,
          onAction: handleStopGeneration,
          actionTone: 'danger',
        };
      }

      if (pendingAgentLabel) {
        return {
          tone: 'info',
          message: t('chat.sessionPendingOnly', { pending: pendingAgentLabel }),
          actionLabel: stopActionLabel,
          onAction: handleStopGeneration,
          actionTone: 'danger',
        };
      }

      if (relayStatusSnapshot.activeProcessingMessage?.isThinking && activeAgentLabel) {
        return {
          tone: 'info',
          message: t('chat.sessionThinking', { active: activeAgentLabel }),
          actionLabel: stopActionLabel,
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
          message: t('chat.sessionStatusRaw', { active: activeAgentLabel, status: rawStatusMessage }),
          actionLabel: stopActionLabel,
          onAction: handleStopGeneration,
          actionTone: 'danger',
        };
      }

      if (activeAgentLabel) {
        return {
          tone: 'info',
          message: currentConversation?.type === ConversationType.TEAM
            ? t('chat.sessionTeamProcessing', { active: activeAgentLabel })
            : t('chat.sessionDirectProcessing', { active: activeAgentLabel }),
          actionLabel: stopActionLabel,
          onAction: handleStopGeneration,
          actionTone: 'danger',
        };
      }

      return {
        tone: streamState === 'error' || streamState === 'timeout' ? 'warning' : 'info',
        message: streamStateLabels[streamState] as string,
        actionLabel: stopActionLabel,
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
    lastFailedTurnRequestId,
    interruptNotice,
    canResumeInterruptedRequest,
    lastInterruptedRequest,
    handleResumeInterruptedRequest,
    dismissInterruptNotice,
    requestInputFocus,
    isLoading,
    streamState,
    streamStateLabels,
    relayStatusSnapshot,
    currentConversation?.type,
    handleStopGeneration,
    formatAgentNamesForStatusLocalized,
    t,
  ]);

  const renderTurnCard = useCallback((turn: MessageTurn, actualTurnIndex: number) => {
    const participantNames = turn.participantAgentIds
      .map((agentId) => getAgentName(agentId))
      .filter(Boolean) as string[];
    const isTeamTurn = currentConversation?.type === ConversationType.TEAM;
    const isInterruptedTurn = canResumeInterruptedRequest && lastInterruptedTurnId === turn.id;
    const relayTimelineSteps = isTeamTurn
      ? getRelayTimelineStepsLocalized(turn)
      : [];
    const isTimelineExpanded = relayTimelineSteps.length > 0
      ? (expandedTimelineTurnIds[turn.id] ?? false)
      : false;
    const finalResponseGroup = turn.responseGroups.at(-1);
    const finalResponderName = finalResponseGroup?.[0]
      ? (finalResponseGroup[0].agentName || getAgentName(finalResponseGroup[0].agentId) || t('chat.assistantFallback'))
      : undefined;
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
      getRelayGroupLabelLocalized,
    );
    const hiddenRelayCount = relayRenderItems.reduce(
      (total, item) => total + (item.type === 'summary' ? item.hiddenCount : 0),
      0,
    );
    const inspectedStep = highlightedGroupIndex !== null && highlightedGroupIndex >= 0
      ? (relayTimelineSteps.find((step) => step.groupIndex === highlightedGroupIndex) || null)
      : null;
    const turnRetryPending = Boolean(
      showReconnect
      && canRetryCurrentConversation
      && lastFailedTurnId
      && turn.userMessage?.id === lastFailedTurnId,
    );
    const turnRequestId = resolveTurnRequestId(turn);
    const turnRequestBadge = formatRequestIdBadge(turnRequestId);

    return (
      <section
        key={turn.id}
        data-testid="chat-turn-card"
        data-turn-id={turn.id}
        data-expanded={isExpanded ? 'true' : 'false'}
        className={`rounded-[22px] border px-3 py-2.5 shadow-sm ${
          turnRetryPending
            ? 'border-amber-200 bg-amber-50/60'
            : turn.hasError
              ? 'border-red-200 bg-red-50/60'
              : 'border-slate-200 bg-white'
        }`}
      >
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
              {t('chat.turnLabel', { turn: actualTurnIndex + 1 })}
            </span>
            {isTeamTurn && (
              <span className="inline-flex items-center rounded-full bg-violet-100 px-2.5 py-1 text-xs font-medium text-violet-700">
                {turn.relayCount > 1 ? t('chat.relayCount', { count: turn.relayCount }) : t('chat.singleResponse')}
              </span>
            )}
            {turn.hasError && (
              <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${
                turnRetryPending
                  ? 'bg-amber-100 text-amber-800'
                  : 'bg-red-100 text-red-700'
              }`}>
                {turnRetryPending ? t('chat.turnRetryPending') : t('chat.turnHasFailure')}
              </span>
            )}
            {turn.hasError && turnRequestId && turnRequestBadge && (
              <span
                title={turnRequestId}
                className={`inline-flex items-center rounded-full border px-2 py-1 font-mono text-[11px] font-medium ${
                  turnRetryPending
                    ? 'border-amber-200 bg-white text-amber-800'
                    : 'border-red-200 bg-white text-red-700'
                }`}
              >
                {t('chat.requestIdBadge', { id: turnRequestBadge })}
              </span>
            )}
            {isInterruptedTurn && (
              <span className="inline-flex items-center rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-700">
                {t('chat.turnInterrupted')}
              </span>
            )}
          </div>
          {participantNames.length > 0 && (
            <span className="text-xs text-slate-500">
              {t('chat.responders', { names: participantNames.join(' · ') })}
            </span>
          )}
        </div>

        {isInterruptedTurn && (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-emerald-200 bg-emerald-50/80 px-4 py-3">
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2 text-xs text-emerald-800">
                <span className="inline-flex items-center rounded-full bg-white px-2.5 py-1 font-semibold shadow-sm">
                  {t('chat.interruptResumeBadge')}
                </span>
                <span>{t('chat.interruptResumeHint')}</span>
              </div>
              {turn.userMessage?.content && (
                <p className="text-sm text-emerald-900">
                  {t('chat.lastRequest', { preview: buildRequestPreviewLocalized(turn.userMessage.content, 40) })}
                </p>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <ChatIconButton
                label={t('chat.resumeFromHere')}
                dataTestId="chat-turn-resume"
                onClick={() => void handleResumeInterruptedRequest()}
                tone="success"
                icon={<CirclePlay className="h-4 w-4" strokeWidth={2} />}
              />
              <ChatIconButton
                label={t('chat.continueInput')}
                onClick={requestInputFocus}
                tone="success"
                icon={<PencilLine className="h-4 w-4" strokeWidth={2} />}
              />
            </div>
          </div>
        )}

        {(relayTimelineSteps.length > 0 || (isCollapsibleRelay && allowRelayCollapse)) && (
          <Suspense fallback={null}>
            <RelayTimelinePanel
              relayTimelineSteps={relayTimelineSteps}
              isTimelineExpanded={isTimelineExpanded}
              turnRetryPending={turnRetryPending}
              finalResponderName={finalResponderName}
              highlightedGroupIndex={highlightedGroupIndex}
              pendingJumpGroupIndex={pendingJumpGroupIndex}
              onToggleTimeline={() => toggleTimelineExpanded(turn.id)}
              onJumpToRelayStep={(groupIndex) => jumpToRelayStep(turn.id, groupIndex)}
              showRelaySummary={isCollapsibleRelay && allowRelayCollapse}
              participantCount={participantNames.length}
              inspectedStep={inspectedStep}
              isExpanded={isExpanded}
              hiddenRelayCount={hiddenRelayCount}
              onToggleTurnExpanded={() => toggleTurnExpanded(turn.id)}
            />
          </Suspense>
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
                            {t('chat.collapsedStableRelay', { count: item.hiddenCount })}
                          </span>
                          <span>
                            {t('chat.batonRange', { start: item.startIndex + 1, end: item.endIndex + 1 })}
                          </span>
                        </div>
                        <p className="text-sm text-slate-600">
                          {formatCollapsedRelayLabelsLocalized(item.labels)}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <ChatIconButton
                          label={t('chat.expandRelaySegment')}
                          dataTestId="chat-turn-expand-segment"
                          onClick={() => toggleRelaySegmentExpanded(turn.id, item.startIndex, item.endIndex)}
                          className="group-hover:border-slate-400"
                          icon={<ChevronsDown className="h-4 w-4" strokeWidth={2} />}
                        />
                        <ChatIconButton
                          label={t('chat.expandFullRelay')}
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
                (allSteps, message) => mergeLocalizedExecutionSteps(allSteps, message.executionSteps),
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
                            {t('chat.expandedSegment')}
                          </span>
                          <span>
                            {t('chat.batonRange', { start: expandedSegmentAtStart.startIndex + 1, end: expandedSegmentAtStart.endIndex + 1 })}
                          </span>
                        </div>
                        <p className="text-sm text-slate-600">
                          {t('chat.expandedSegmentHint')}
                        </p>
                      </div>
                      <ChatIconButton
                        label={t('chat.collapseRelaySegment')}
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
                        showRetryPending={turnRetryPending}
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
  }, [
    activeHistoryResultKey,
    buildRequestPreviewLocalized,
    canResumeInterruptedRequest,
    canRetryCurrentConversation,
    currentConversation?.type,
    expandedRelaySegments,
    expandedTimelineTurnIds,
    expandedTurnIds,
    formatCollapsedRelayLabelsLocalized,
    formatTime,
    getAgentName,
    getDefaultVisibleRelayGroupIndexes,
    getRelayGroupLabelLocalized,
    getRelayTimelineStepsLocalized,
    handleResumeInterruptedRequest,
    handleRetryMessage,
    highlightedRelayGroupKey,
    highlightedRelayLocation,
    jumpToRelayStep,
    lastFailedTurnId,
    lastInterruptedMessageId,
    lastInterruptedTurnId,
    mergeLocalizedExecutionSteps,
    pendingRelayJump,
    requestInputFocus,
    showReconnect,
    t,
    toggleRelaySegmentExpanded,
    toggleTimelineExpanded,
    toggleTurnExpanded,
  ]);
  
  return (
    <div className="flex h-full min-h-full overflow-hidden">
      <div className="hidden w-64 min-h-0 flex-shrink-0 flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="p-4 border-b border-slate-200">
          <h2 className="font-semibold text-slate-800">{t('chat.sectionTitle')}</h2>
        </div>
        
        <div className="flex-1 overflow-y-auto p-2">
          <div className="mb-4">
            <h3 className="px-2 py-1 text-xs font-medium text-slate-500 uppercase tracking-wider">{t('chat.directSection')}</h3>
            <div className="space-y-1 mt-1">
              {directAgents.map((agent) => {
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
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium truncate">{agent.name}</p>
                        {agent.external && (
                          <span className="inline-flex items-center rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-sky-700">
                            {t('chat.externalBadge')}
                          </span>
                        )}
                      </div>
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
              <h3 className="px-2 py-1 text-xs font-medium text-slate-500 uppercase tracking-wider">{t('chat.teamSection')}</h3>
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
                        <p className="text-xs text-slate-500">{t('chat.teamMembers', { count: team.members.length })}</p>
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
            <div
              className="relative z-20 flex shrink-0 items-center justify-between overflow-visible border-b border-slate-200 bg-white px-4 py-2"
              data-testid="chat-conversation-header"
            >
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  {currentConversation.type === ConversationType.TEAM ? (
                    <div className="h-7 w-7 rounded-full bg-gradient-to-br from-violet-400 to-violet-600 flex items-center justify-center text-white">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                      </svg>
                    </div>
                  ) : (
                    <div className="h-7 w-7 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white font-semibold text-sm">
                      {currentConversation.name.charAt(0).toUpperCase()}
                    </div>
                  )}
                  <div className="min-w-0">
                    <h2 className="truncate font-semibold text-slate-800">{currentConversation.name}</h2>
                    <div
                      data-testid="chat-conversation-header-details"
                      aria-hidden={isConversationHeaderCollapsed}
                      className={`absolute left-0 right-0 top-full z-30 border-b border-slate-200 bg-white px-4 pb-3 pt-0 transition-[opacity,transform,visibility] duration-200 ease-out ${
                        isConversationHeaderCollapsed
                          ? 'invisible -translate-y-1 opacity-0 pointer-events-none'
                          : 'visible translate-y-0 opacity-100'
                      }`}
                    >
                      <div className="ml-[3rem] min-w-0">
                        <p className="text-xs text-slate-500">
                          {currentConversation.type === ConversationType.TEAM
                            ? t('chat.teamHeaderDescription', { count: currentTeamMembers.length })
                            : currentDirectAgent?.external
                              ? t('chat.externalHeaderDescription')
                            : currentDirectAgentProfilePreset
                              ? `${currentDirectAgentProfilePreset.label} · ${currentDirectAgentProfilePreset.summary}`
                              : t('chat.directHeaderDescription')}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          {currentConversation.type !== ConversationType.TEAM && currentDirectAgentProfilePreset && (
                            <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold ${currentDirectAgentProfilePreset.accent}`}>
                              {t('chat.profileBadge')} · {currentDirectAgentProfilePreset.label}
                            </span>
                          )}
                          {currentConversation.type !== ConversationType.TEAM && currentDirectAgent?.external && (
                            <span className="inline-flex items-center rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-[11px] font-semibold text-sky-700">
                              {t('chat.externalBadge')}
                            </span>
                          )}
                          {currentConversation.type !== ConversationType.TEAM && currentDirectAgentPermissionPreset && (
                            <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold ${currentDirectAgentPermissionPreset.accent}`}>
                              {t('chat.permissionBadge')} · {currentDirectAgentPermissionPreset.label}
                            </span>
                          )}
                          {currentConversationCapabilities.length > 0 && (
                            <>
                              <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                                {t('chat.availableCapabilities')}
                              </span>
                              {currentConversationCapabilities.slice(0, 6).map((capability) => {
                                const Icon = getCapabilityIcon(capability.id);
                                const capabilityLabel = getCapabilityLabel(t, capability);
                                return (
                                  <span
                                    key={capability.id}
                                    title={capability.description || capabilityLabel}
                                    className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium ${getCapabilityTone(capability.id)}`}
                                  >
                                    <Icon className="h-3.5 w-3.5" />
                                    {capabilityLabel}
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
                </div>
              </div>
              <div className="relative hidden shrink-0 self-end md:flex md:flex-row md:items-center md:justify-end md:gap-2">
                <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-medium shadow-sm ${
                  currentConversation.type === ConversationType.TEAM
                    ? 'bg-violet-100 text-violet-700'
                    : 'bg-blue-100 text-blue-700'
                }`}>
                  {currentConversation.type === ConversationType.TEAM ? t('chat.teamRelay') : t('chat.directMessage')}
                </span>
                {messages.length > 0 && (
                  <div className="relative">
                      <button
                        type="button"
                        onClick={() => setIsHistorySearchOpen((prev) => !prev)}
                      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium shadow-sm transition-colors ${
                        isHistorySearchOpen || historySearchQuery
                          ? 'border-sky-200 bg-white text-sky-700'
                          : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      <Search className="h-3.5 w-3.5" strokeWidth={2} />
                      {t('chat.historySearch')}
                      {historySearchMatches.length > 0 && (
                        <span className="inline-flex min-w-6 items-center justify-center rounded-full bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700">
                          {historySearchIndex + 1}/{historySearchMatches.length}
                        </span>
                      )}
                    </button>

                    {(isHistorySearchOpen || historySearchQuery) && (
                      <Suspense fallback={null}>
                        <HistorySearchPopover
                          t={t}
                          messageTurnsCount={messageTurns.length}
                          historySearchInputRef={historySearchInputRef}
                          historySearchQuery={historySearchQuery}
                          setHistorySearchQuery={setHistorySearchQuery}
                          setHistorySearchIndex={setHistorySearchIndex}
                          setActiveHistoryResultKey={setActiveHistoryResultKey}
                          setActiveRemoteHistoryResultId={setActiveRemoteHistoryResultId}
                          onClose={() => setIsHistorySearchOpen(false)}
                          isPartialHistoryLoaded={isPartialHistoryLoaded}
                          historySearchTimeRange={historySearchTimeRange}
                          setHistorySearchTimeRange={setHistorySearchTimeRange}
                          handleHistorySearchMove={handleHistorySearchMove}
                          historySearchMatchesCount={historySearchMatches.length}
                          historySearchIndex={historySearchIndex}
                          activeHistoryMatch={activeHistoryMatch}
                          remoteHistorySearchTotal={remoteHistorySearchTotal}
                          isRemoteHistorySearchLoading={isRemoteHistorySearchLoading}
                          remoteHistorySearchVisibleMatches={remoteHistorySearchVisibleMatches}
                          getAgentName={getAgentName}
                          formatTime={formatTime}
                          activeRemoteHistoryResultId={activeRemoteHistoryResultId}
                          handleSelectRemoteHistorySearchMatch={handleSelectRemoteHistorySearchMatch}
                          isLoadingHistorySearchContext={isLoadingHistorySearchContext}
                          remoteHistorySearchHasMore={remoteHistorySearchHasMore}
                          handleLoadMoreRemoteHistorySearch={handleLoadMoreRemoteHistorySearch}
                          isRemoteHistorySearchLoadingMore={isRemoteHistorySearchLoadingMore}
                        />
                      </Suspense>
                    )}
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => setIsConversationHeaderCollapsed((prev) => !prev)}
                  className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50"
                  aria-label={isConversationHeaderCollapsed ? t('chat.expandHeader') : t('chat.collapseHeader')}
                  title={isConversationHeaderCollapsed ? t('chat.expandHeader') : t('chat.collapseHeader')}
                  data-testid="chat-header-collapse-toggle"
                >
                  {isConversationHeaderCollapsed ? (
                    <ChevronsDown className="h-3.5 w-3.5" strokeWidth={2} />
                  ) : (
                    <ChevronsUp className="h-3.5 w-3.5" strokeWidth={2} />
                  )}
                  {isConversationHeaderCollapsed ? t('chat.expandHeader') : t('chat.collapseHeader')}
                </button>
              </div>
            </div>
            {batonNavigationNotice && (
              <div className={`shrink-0 border-b px-4 py-2.5 ${
                batonNavigationNotice.tone === 'team'
                  ? 'border-violet-200 bg-violet-50/80'
                  : 'border-sky-200 bg-sky-50/80'
              }`}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                      batonNavigationNotice.tone === 'team'
                        ? 'bg-violet-100 text-violet-700'
                        : 'bg-sky-100 text-sky-700'
                    }`}>
                      {batonNavigationNotice.tone === 'team' ? t('chat.teamSwitchNotice') : t('chat.dmSwitchNotice')}
                    </span>
                    <p className="min-w-0 text-sm text-slate-700">{batonNavigationNotice.message}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {batonNavigationNotice.actionLabel && batonNavigationNotice.actionConversationId && (
                      <button
                        type="button"
                        onClick={() => {
                          setCurrentConversation(batonNavigationNotice.actionConversationId as string);
                          dismissBatonNavigationNotice();
                        }}
                        className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50"
                      >
                        {batonNavigationNotice.actionLabel}
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={dismissBatonNavigationNotice}
                      className="inline-flex h-7 w-7 items-center justify-center rounded-full text-slate-400 transition hover:bg-white hover:text-slate-600"
                      aria-label={t('chat.closeBatonNotice')}
                    >
                      <X className="h-3.5 w-3.5" strokeWidth={2} />
                    </button>
                  </div>
                </div>
              </div>
            )}
            
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
                        {t('chat.loadHistory')}
                      </p>
                    </div>
                  ) : currentConversation.type !== ConversationType.TEAM && (currentDirectAgent?.setup_required || currentDirectAgent?.bootstrap_setup_pending) ? (
                    <div className="w-full max-w-2xl rounded-[28px] border border-accent-orange/30 bg-white px-6 py-6 text-left shadow-sm">
                      <div className="inline-flex rounded-full bg-accent-orange/10 px-3 py-1 text-xs font-semibold text-accent-orange">
                        {t('chat.onboardingBadge')}
                      </div>
                      <h3 className="mt-4 text-lg font-semibold text-slate-900">{t('chat.onboardingTitle', { name: currentDirectAgent.name })}</h3>
                      <p className="mt-2 text-sm text-slate-600">
                        {currentDirectAgent?.setup_required
                          ? t('chat.onboardingDescriptionSetupRequired')
                          : t('chat.onboardingDescriptionReady')}
                      </p>
                      {currentDirectAgentProfilePreset && (
                        <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold ${currentDirectAgentProfilePreset.accent}`}>
                              {t('chat.profileBadge')} · {currentDirectAgentProfilePreset.label}
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
                            {t('chat.goManageAgents')}
                          </a>
                        )}
                        <button
                          onClick={() => applyInputDraftPreset(currentDirectStarterPrompts[0] || t('chat.onboardingDefaultPrompt'))}
                          className="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                        >
                          {currentDirectAgent?.setup_required ? t('chat.onboardingPrepare') : t('chat.onboardingStart')}
                        </button>
                      </div>
                      <div className="mt-4 rounded-2xl bg-slate-50 px-4 py-3 text-xs text-slate-600">
                        <div className="font-semibold text-slate-700">{t('chat.onboardingChecklist')}</div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {currentDirectOnboardingChecklist.map((item) => (
                            <span key={item} className="rounded-full border border-slate-200 bg-white px-2.5 py-1">
                              {item}
                            </span>
                          ))}
                        </div>
                        <div className="mt-3 font-semibold text-slate-700">{t('chat.onboardingOpeners')}</div>
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
                      <p className="text-lg font-medium">{t('chat.startConversationTitle')}</p>
                      <p className="text-sm mt-1">
                        {currentConversation.type === ConversationType.TEAM
                          ? t('chat.startConversationDescriptionTeam')
                          : t('chat.startConversationDescriptionDirect')}
                      </p>
                      {currentConversation.type !== ConversationType.TEAM && currentDirectAgentProfilePreset && (
                        <div className="mt-4 max-w-2xl rounded-[24px] border border-slate-200 bg-white px-4 py-4 text-left shadow-sm">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold ${currentDirectAgentProfilePreset.accent}`}>
                              {t('chat.profileBadge')} · {currentDirectAgentProfilePreset.label}
                            </span>
                            <span className="text-xs text-slate-500">{currentDirectAgentProfilePreset.summary}</span>
                          </div>
                          <div className="mt-3 text-xs font-semibold text-slate-700">{t('chat.onboardingOpeners')}</div>
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
                          {t('chat.startConversationCapabilityHint', { name: currentDirectAgent.name })}
                        </p>
                      )}
                    </>
                  )}
                </div>
              ) : (
                <>
                  <div className="rounded-[28px] border border-slate-200 bg-white px-4 py-3 shadow-sm">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                            <ListChecks className="h-3.5 w-3.5" strokeWidth={2} />
                            {t('chat.workbenchTitle')}
                          </span>
                          <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${
                            conversationWorkbench.failedSteps > 0
                              ? 'bg-red-100 text-red-700'
                              : conversationWorkbench.runningSteps > 0 || isLoading
                                ? 'bg-sky-100 text-sky-700'
                                : 'bg-emerald-100 text-emerald-700'
                          }`}>
                            {conversationWorkbench.stage}
                          </span>
                          <span className="text-sm text-slate-600">{currentConversationSummary}</span>
                        </div>
                        <p className="mt-2 truncate text-sm font-medium text-slate-800">
                          {t('chat.workbenchLatestRequest', { preview: conversationWorkbench.latestRequest })}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                          <span>{t('chat.workbenchTurns', { count: messageTurns.length })}</span>
                          <span>{t('chat.workbenchFiles', { count: conversationWorkbench.fileCount })}</span>
                          <span>{t('chat.workbenchSteps', { count: conversationWorkbench.executionSteps })}</span>
                          {conversationWorkbench.relayCount > 1 && (
                            <span>{t('chat.workbenchRelays', { count: conversationWorkbench.relayCount })}</span>
                          )}
                          {conversationWorkbench.lastUpdatedAt && (
                            <span>{t('chat.workbenchUpdated', { time: formatTime(conversationWorkbench.lastUpdatedAt) })}</span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => setIsWorkbenchExpanded((prev) => !prev)}
                          className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50"
                          aria-expanded={isWorkbenchExpanded}
                        >
                          {isWorkbenchExpanded ? (
                            <ChevronsUp className="h-3.5 w-3.5" strokeWidth={2} />
                          ) : (
                            <ChevronsDown className="h-3.5 w-3.5" strokeWidth={2} />
                          )}
                          {isWorkbenchExpanded ? t('chat.workbenchCollapse') : t('chat.workbenchExpand')}
                        </button>
                      </div>
                    </div>
                    {isWorkbenchExpanded && (
                      <div className="mt-3 space-y-3" data-testid="chat-workbench-details">
                        <div className="flex max-w-full flex-wrap gap-2">
                          {conversationWorkbench.activeAgents.slice(0, 4).map((name) => (
                            <span key={name} className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600">
                              {name}
                            </span>
                          ))}
                          {conversationWorkbench.toolNames.slice(0, 4).map((name) => (
                            <span key={name} className="rounded-full border border-indigo-100 bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700">
                              {name}
                            </span>
                          ))}
                        </div>
                        {conversationWorkbench.executionSteps > 0 && (
                          <div className="grid gap-2 sm:grid-cols-3">
                            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2">
                              <div className="text-lg font-semibold text-slate-900">{conversationWorkbench.completedSteps}</div>
                              <div className="text-xs text-slate-500">{t('chat.workbenchStepsDone')}</div>
                            </div>
                            <div className="rounded-2xl border border-sky-200 bg-sky-50 px-3 py-2">
                              <div className="text-lg font-semibold text-sky-800">{conversationWorkbench.runningSteps}</div>
                              <div className="text-xs text-sky-600">{t('chat.workbenchStepsRunning')}</div>
                            </div>
                            <div className="rounded-2xl border border-red-200 bg-red-50 px-3 py-2">
                              <div className="text-lg font-semibold text-red-700">{conversationWorkbench.failedSteps}</div>
                              <div className="text-xs text-red-600">{t('chat.workbenchStepsFailed')}</div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                    {currentConversation.type === ConversationType.TEAM && (
                      <p className="mt-2 text-xs text-slate-500">
                        {t('chat.teamRelayHint')}
                      </p>
                    )}
                    {currentConversationHealth && (
                      <div
                        data-testid="chat-conversation-health"
                        className={`mt-3 rounded-2xl border px-3 py-2 ${
                          currentConversationHealth.tone === 'danger'
                            ? 'border-amber-300 bg-amber-50/90'
                            : 'border-sky-200 bg-sky-50/90'
                        }`}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${
                            currentConversationHealth.tone === 'danger'
                              ? 'bg-amber-100 text-amber-900'
                              : 'bg-sky-100 text-sky-800'
                          }`}>
                            {currentConversationHealth.tone === 'danger'
                              ? t('chat.contextHealthBadgeDanger')
                              : t('chat.contextHealthBadgeWarning')}
                          </span>
                          <span className="text-xs text-slate-700">
                            {t('chat.contextHealthStats', {
                              tokens: formatApproxTokenCount(currentConversationHealth.approxTokens),
                              turns: currentConversationHealth.turnCount,
                            })}
                          </span>
                        </div>
                        <p className="mt-2 text-xs text-slate-600">
                          {t('chat.contextHealthHint')}
                        </p>
                      </div>
                    )}
                  </div>

                  {canJumpBackToLatest && (
                    <div className="flex justify-center">
                      <button
                        type="button"
                        onClick={handleJumpBackToLatestHistory}
                        disabled={historyLoadingState.conversationId === currentConversationId}
                        className="inline-flex items-center gap-2 rounded-full border border-sky-200 bg-sky-50 px-4 py-2 text-xs font-medium text-sky-700 shadow-sm transition hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <ArrowDown className="h-3.5 w-3.5" strokeWidth={2} />
                        {t('chat.jumpBackToLatest')}
                      </button>
                    </div>
                  )}

                  {currentHistoryWindow?.hasMoreBefore && (
                    <div className="flex justify-center">
                      <button
                        type="button"
                        onClick={handleLoadOlderHistory}
                        disabled={isLoadingOlderHistory}
                        className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-medium text-slate-600 shadow-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <ChevronsUp className="h-3.5 w-3.5" strokeWidth={2} />
                        {isLoadingOlderHistory ? t('chat.loadingOlderHistory') : t('chat.loadOlderHistory')}
                      </button>
                    </div>
                  )}

                  <div
                    ref={turnListContainerRef}
                    className={shouldVirtualizeTurns ? 'relative' : 'space-y-3'}
                    style={shouldVirtualizeTurns
                      ? { height: `${turnVirtualizationMetrics.totalHeight}px` }
                      : undefined}
                  >
                    {shouldVirtualizeTurns
                      ? visibleVirtualizedTurnIndexes.map((turnIndex) => {
                          const turn = messageTurns[turnIndex];
                          if (!turn) {
                            return null;
                          }

                          return (
                            <div
                              key={turn.id}
                              ref={(node) => registerVirtualizedTurnElement(turn.id, node)}
                              data-turn-id={turn.id}
                              style={{
                                position: 'absolute',
                                top: `${turnVirtualizationMetrics.rowOffsets[turnIndex]}px`,
                                left: 0,
                                right: 0,
                                paddingBottom: `${TURN_VIRTUALIZATION_ROW_GAP}px`,
                              }}
                            >
                              {renderTurnCard(turn, turnIndex)}
                            </div>
                          );
                        })
                      : messageTurns.map((turn, turnIndex) => renderTurnCard(turn, turnIndex))}
                  </div>
                  
                    <TypingIndicator
                    agentNames={typingAgents
                      .map((id: string) => directAgents.find(a => a.id === id)?.name)
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
                  onClick={() => scrollToBottom()}
                  className="absolute bottom-4 right-4 inline-flex items-center gap-1 rounded-full border border-sky-200 bg-white/95 px-3 py-2 text-xs font-medium text-sky-700 shadow-lg backdrop-blur transition hover:-translate-y-0.5 hover:bg-sky-50"
                >
                  <ArrowDown className="h-3.5 w-3.5" strokeWidth={2} />
                  {t('chat.scrollToBottom')}
                </button>
              )}
            </div>
            
            <div className="relative shrink-0">
              <MessageInput
                conversationType={currentConversation.type}
                conversationName={currentConversation.name}
                agents={currentConversation.type === ConversationType.TEAM ? currentTeamMentionableAgents : directAgents}
                onSend={handleSendMessage}
                disabled={!isOnline}
                isLoading={isLoading}
                sessionStatus={sessionStatus}
                focusRequestKey={inputFocusRequestKey}
                draftPresetText={inputDraftPreset.text}
                draftPresetKey={inputDraftPreset.key}
                placeholder={
                  !isOnline ? t('chat.placeholderOffline') :
                  currentConversation.type === ConversationType.TEAM
                    ? t('chat.placeholderTeam')
                    : currentDirectAgentProfilePreset
                      ? t('chat.placeholderDirectHint', { name: currentConversation.name || 'Agent', hint: currentDirectAgentProfilePreset.placeholderHint })
                      : t('chat.placeholderDirect', { name: currentConversation.name || 'Agent' })
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
            <p className="text-xl font-medium">{t('chat.selectConversationTitle')}</p>
            <p className="text-sm mt-2">{t('chat.selectConversationDescription')}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatPage;
