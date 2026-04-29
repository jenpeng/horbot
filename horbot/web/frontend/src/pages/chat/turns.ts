import { cleanHistoryMessageContent, parseMessageTimestamp } from './historyUtils';
import type {
  ExpandedRelaySegment,
  MessageTurn,
  MessageTurnAccumulator,
  PendingRelayJump,
  RelayGroupState,
  RelayRenderItem,
  StreamMessageEntry,
  TranslateFn,
  UIMessage,
} from './types';

export const buildMessageMergeKey = (message: Pick<
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

export const doesHistoryMessageReplaceStreamEntry = (
  message: Pick<UIMessage, 'id' | 'turnId' | 'agentId'>,
  streamEntry: Pick<StreamMessageEntry, 'messageId' | 'turnId' | 'agentId'>,
): boolean => {
  if (message.id === streamEntry.messageId) {
    return true;
  }
  if (!streamEntry.turnId || !message.turnId || message.turnId !== streamEntry.turnId) {
    return false;
  }
  if (!streamEntry.agentId) {
    return true;
  }
  return message.agentId === streamEntry.agentId;
};

export const findReplacedStreamEntries = (
  historyMessages: UIMessage[],
  streamEntries: StreamMessageEntry[],
): StreamMessageEntry[] => {
  if (historyMessages.length === 0 || streamEntries.length === 0) {
    return [];
  }

  return streamEntries.filter((streamEntry) => (
    historyMessages.some((message) => doesHistoryMessageReplaceStreamEntry(message, streamEntry))
  ));
};

export const groupMessagesBySpeaker = (messages: UIMessage[]): UIMessage[][] => {
  if (messages.length === 0) return [];

  const groups: UIMessage[][] = [];
  let currentGroup: UIMessage[] = [messages[0]];

  for (let i = 1; i < messages.length; i += 1) {
    const current = messages[i];
    const previous = currentGroup[currentGroup.length - 1];
    const sameRole = current.role === previous.role;
    const sameAgent = current.agentId === previous.agentId;
    const currentRequestId = current.requestId || '';
    const previousRequestId = previous.requestId || '';
    const sameRequest = !currentRequestId || !previousRequestId || currentRequestId === previousRequestId;
    if (sameRole && sameAgent && sameRequest) {
      currentGroup.push(current);
    } else {
      groups.push(currentGroup);
      currentGroup = [current];
    }
  }

  groups.push(currentGroup);
  return groups;
};

export const resolveTurnRequestId = (turn: MessageTurn): string | undefined => (
  [...turn.assistantMessages].reverse().find((message) => !!message.requestId)?.requestId
  || turn.userMessage?.requestId
);

export const formatRequestIdBadge = (requestId?: string): string => (
  requestId ? requestId.slice(0, 8) : ''
);

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

export const buildMessageTurns = (messages: UIMessage[]): MessageTurn[] => {
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

export const attachRetryPayloadsToHistoryMessages = (messages: UIMessage[]): UIMessage[] => {
  const turns = buildMessageTurns(messages);
  const retryPayloadByMessageId = new Map<string, NonNullable<UIMessage['retryPayload']>>();

  turns.forEach((turn) => {
    if (!turn.userMessage) {
      return;
    }

    const retryPayload = {
      content: turn.userMessage.content,
      mentionedAgents: [] as string[],
      files: turn.userMessage.files,
    };

    turn.assistantMessages.forEach((message) => {
      if (message.isError && message.retryable) {
        retryPayloadByMessageId.set(message.id, retryPayload);
      }
    });
  });

  return messages.map((message) => {
    const retryPayload = retryPayloadByMessageId.get(message.id);
    if (!retryPayload || message.retryPayload) {
      return message;
    }
    return {
      ...message,
      retryPayload,
    };
  });
};

export const parseRelayGroupKey = (value: string | null): PendingRelayJump | null => {
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

export const getRelayGroupState = (group: UIMessage[]): RelayGroupState => {
  if (group.some((message) => message.isError)) {
    return 'error';
  }
  if (group.some((message) => message.metadata?._relay_phase === 'pending')) {
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

export const getRelayGroupTransition = (
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

export const MAX_VISIBLE_RELAY_GROUPS_WITHOUT_COLLAPSE = 4;

export const getDefaultVisibleRelayGroupIndexes = (
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

export const buildRelayRenderItems = (
  groups: UIMessage[][],
  visibleIndexes: Set<number>,
  getGroupLabel: (group: UIMessage[], index: number) => string,
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
      const label = getGroupLabel(groups[groupIndex], groupIndex);
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

export const isRelaySegmentStart = (
  segments: ExpandedRelaySegment[],
  groupIndex: number,
): ExpandedRelaySegment | null => {
  return segments.find((segment) => segment.startIndex === groupIndex) || null;
};

export const formatAgentNamesForStatus = (
  t: TranslateFn,
  names: string[],
): string => {
  if (names.length === 0) return '';
  if (names.length === 1) return names[0];
  if (names.length === 2) return t('chat.agentNamesTwo', { first: names[0], second: names[1] });
  return t('chat.agentNamesMany', { first: names[0], count: names.length });
};

export const buildInterruptSummary = (
  t: TranslateFn,
  activeAgentName?: string,
  pendingAgentNames: string[] = [],
): string => {
  if (activeAgentName && pendingAgentNames.length > 0) {
    return t('chat.interruptSummaryActivePending', {
      active: activeAgentName,
      pending: formatAgentNamesForStatus(t, pendingAgentNames),
    });
  }
  if (activeAgentName) {
    return t('chat.interruptSummaryActive', { active: activeAgentName });
  }
  if (pendingAgentNames.length > 0) {
    return t('chat.interruptSummaryPending', {
      pending: formatAgentNamesForStatus(t, pendingAgentNames),
    });
  }
  return t('chat.interruptSummaryGeneric');
};

export const buildRequestPreview = (
  t: TranslateFn,
  content: string,
  maxLength = 18,
): string => {
  const normalized = content.replace(/\s+/g, ' ').trim();
  if (!normalized) {
    return t('chat.requestPreviewFallback');
  }
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, Math.max(1, maxLength - 1))}…`;
};
