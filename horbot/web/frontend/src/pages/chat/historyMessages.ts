import type { ExecutionStep } from '../../types/conversation';
import {
  hasRenderableMessageFiles,
  normalizeMessageFiles,
} from './messageFiles';
import {
  buildHistoryMessageFallbackId,
  cleanHistoryMessageContent,
  parseMessageTimestamp,
} from './historyUtils';
import {
  normalizeAssistantErrorContent,
  normalizeProviderErrorPayload,
} from './streamErrors';
import { attachRetryPayloadsToHistoryMessages, buildMessageMergeKey } from './turns';
import type { AgentInfo, TranslateFn, UIMessage } from './types';

export interface RawConversationHistoryMessage {
  id?: string;
  role: string;
  content: string;
  timestamp?: string;
  metadata?: {
    agent_id?: string;
    agent_name?: string;
    turn_id?: string;
    request_id?: string;
    _provider_error?: unknown;
    _confirmation_required?: boolean;
    confirmation_id?: string;
    tool_name?: string;
    tool_arguments?: Record<string, unknown>;
  };
  files?: unknown[];
  tool_calls?: unknown[];
  execution_steps?: ExecutionStep[];
}

export const mergeConversationHistoryMessages = (
  historyMessages: UIMessage[],
  existingMessages: UIMessage[],
  mergeExecutionSteps: (existingSteps?: ExecutionStep[], incomingSteps?: ExecutionStep[]) => ExecutionStep[],
): UIMessage[] => {
  const mergedMessages = [...historyMessages];
  const indexById = new Map<string, number>();
  const indexBySignature = new Map<string, number>();
  const indexByUserContentRequest = new Map<string, number>();

  const buildUserContentRequestKey = (message: UIMessage): string | null => {
    if (message.role !== 'user') {
      return null;
    }
    const requestOrTurnId = message.requestId || message.turnId;
    if (!requestOrTurnId) {
      return null;
    }
    const compactContent = cleanHistoryMessageContent(message.content || '').replace(/\s+/g, ' ').trim();
    if (!compactContent) {
      return null;
    }
    return JSON.stringify({
      role: 'user',
      content: compactContent,
      requestOrTurnId,
    });
  };

  mergedMessages.forEach((message, index) => {
    indexById.set(message.id, index);
    indexBySignature.set(buildMessageMergeKey(message), index);
    const userContentRequestKey = buildUserContentRequestKey(message);
    if (userContentRequestKey) {
      indexByUserContentRequest.set(userContentRequestKey, index);
    }
  });

  existingMessages.forEach((message) => {
    const signature = buildMessageMergeKey(message);
    const userContentRequestKey = buildUserContentRequestKey(message);
    const existingIndex = indexById.get(message.id)
      ?? indexBySignature.get(signature)
      ?? (userContentRequestKey ? indexByUserContentRequest.get(userContentRequestKey) : undefined);

    if (existingIndex !== undefined) {
      const nextMessage = {
        ...mergedMessages[existingIndex],
        ...message,
        id: mergedMessages[existingIndex].id,
        turnId: message.turnId ?? mergedMessages[existingIndex].turnId,
        requestId: message.requestId ?? mergedMessages[existingIndex].requestId,
        agentId: message.agentId ?? mergedMessages[existingIndex].agentId,
        agentName: message.agentName ?? mergedMessages[existingIndex].agentName,
        timestamp: mergedMessages[existingIndex].timestamp ?? message.timestamp,
        metadata: message.metadata ?? mergedMessages[existingIndex].metadata,
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
      const nextUserContentRequestKey = buildUserContentRequestKey(nextMessage);
      if (nextUserContentRequestKey) {
        indexByUserContentRequest.set(nextUserContentRequestKey, existingIndex);
      }
      return;
    }

    const nextIndex = mergedMessages.length;
    mergedMessages.push(message);
    indexById.set(message.id, nextIndex);
    indexBySignature.set(signature, nextIndex);
    if (userContentRequestKey) {
      indexByUserContentRequest.set(userContentRequestKey, nextIndex);
    }
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
};

export const formatConversationHistoryMessages = (
  rawMessages: RawConversationHistoryMessage[],
  options: {
    directAgents: AgentInfo[];
    mergeExecutionSteps: (existingSteps?: ExecutionStep[], incomingSteps?: ExecutionStep[]) => ExecutionStep[];
    t: TranslateFn;
  },
): UIMessage[] => {
  const { directAgents, mergeExecutionSteps, t } = options;
  const formattedMessages = rawMessages
    .filter((msg) => {
      if (msg.role === 'tool') return false;
      const hasToolCalls = msg.tool_calls && Array.isArray(msg.tool_calls) && msg.tool_calls.length > 0;
      const hasContent = msg.content && msg.content.trim();
      const hasFiles = hasRenderableMessageFiles(msg.files);
      const hasExecutionSteps = msg.execution_steps && Array.isArray(msg.execution_steps) && msg.execution_steps.length > 0;
      if (!hasContent && !hasToolCalls && !hasFiles && !hasExecutionSteps) return false;
      if (msg.content && msg.content.startsWith('Message sent to ')) return false;
      return true;
    })
    .map<UIMessage>((msg) => {
      const agentId = msg.metadata?.agent_id;
      let agentName = msg.metadata?.agent_name;
      if (!agentName || agentName === t('chat.assistantFallback')) {
        const agent = directAgents.find((a) => a.id === agentId);
        if (agent) {
          agentName = agent.name;
        }
      }
      const cleanContent = cleanHistoryMessageContent(msg.content);
      const normalizedError = msg.role === 'assistant'
        ? normalizeAssistantErrorContent(t, cleanContent)
        : { content: cleanContent, isProviderError: false };
      const providerError = normalizeProviderErrorPayload(msg.metadata?._provider_error);
      return {
        id: msg.id || buildHistoryMessageFallbackId(msg),
        role: msg.role as UIMessage['role'],
        content: normalizedError.content,
        timestamp: msg.timestamp,
        turnId: msg.metadata?.turn_id,
        requestId: msg.metadata?.request_id,
        agentId,
        agentName,
        files: normalizeMessageFiles(msg.files),
        executionSteps: mergeExecutionSteps([], msg.execution_steps),
        metadata: msg.metadata,
        isError: Boolean(providerError) || normalizedError.isProviderError,
        errorKind: (providerError || normalizedError.isProviderError) ? ('provider' as const) : undefined,
        retryable: providerError?.retryable ?? normalizedError.isProviderError,
        confirmationId: msg.metadata?._confirmation_required ? msg.metadata.confirmation_id : undefined,
        confirmationHandled: false,
        toolName: msg.metadata?._confirmation_required ? msg.metadata.tool_name : undefined,
        toolArguments: msg.metadata?._confirmation_required ? msg.metadata.tool_arguments : undefined,
      };
    });

  return attachRetryPayloadsToHistoryMessages(formattedMessages);
};
