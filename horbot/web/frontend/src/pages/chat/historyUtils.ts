import type { HistorySearchMatch, HistorySearchTimeRange, UIMessage } from './types';

export const resolveHistorySearchSince = (range: HistorySearchTimeRange): string | undefined => {
  if (range === 'all') {
    return undefined;
  }
  const days = range === '7d' ? 7 : 30;
  return new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();
};

export const cleanHistoryMessageContent = (content: string): string => {
  if (!content) return content;

  const messageFromPattern = /<message\s+from="[^"]*">\s*([\s\S]*?)\s*<\/message>/gi;
  return content.replace(
    messageFromPattern,
    (fullMatch: string, innerContent: string, offset: number, source: string) => {
      const remaining = source.slice(offset + fullMatch.length).trim();
      return `${innerContent.trim()}${remaining ? '\n\n' : ''}`;
    },
  ).trim();
};

export const buildHistoryMessageFallbackId = (msg: {
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

export const buildConversationMessagesUrl = (
  conversationId: string,
  options: {
    limit?: number;
    beforeId?: string;
    afterId?: string;
    aroundId?: string;
    contextBefore?: number;
    contextAfter?: number;
  } = {},
): string => {
  const params = new URLSearchParams();
  if (options.limit) {
    params.set('limit', String(options.limit));
  }
  if (options.beforeId) {
    params.set('before_id', options.beforeId);
  }
  if (options.afterId) {
    params.set('after_id', options.afterId);
  }
  if (options.aroundId) {
    params.set('around_id', options.aroundId);
  }
  if (typeof options.contextBefore === 'number') {
    params.set('context_before', String(options.contextBefore));
  }
  if (typeof options.contextAfter === 'number') {
    params.set('context_after', String(options.contextAfter));
  }

  const query = params.toString();
  return `/api/conversations/${conversationId}/messages${query ? `?${query}` : ''}`;
};

export const buildConversationSearchUrl = (
  conversationId: string,
  query: string,
  options: {
    limit?: number;
    offset?: number;
    since?: string;
  } = {},
): string => {
  const params = new URLSearchParams();
  params.set('q', query);
  if (options.limit) {
    params.set('limit', String(options.limit));
  }
  if (typeof options.offset === 'number' && options.offset > 0) {
    params.set('offset', String(options.offset));
  }
  if (options.since) {
    params.set('since', options.since);
  }
  return `/api/conversations/${conversationId}/search?${params.toString()}`;
};

export const parseMessageTimestamp = (timestamp?: string): number | null => {
  if (!timestamp) {
    return null;
  }

  const value = Date.parse(timestamp);
  return Number.isNaN(value) ? null : value;
};

export const normalizeSearchText = (value?: string): string => (
  (value || '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
);

export const buildSearchPreview = (value?: string, maxLength: number = 96): string => {
  const normalized = (value || '').replace(/\s+/g, ' ').trim();
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, Math.max(1, maxLength - 1))}…`;
};

export const findHistorySearchMatchIndexByMessageId = (
  matches: HistorySearchMatch[],
  messageId: string,
): number => matches.findIndex((match) => match.messageIds.includes(messageId));

export const estimateConversationTokens = (messages: UIMessage[]): number => {
  const totalChars = messages.reduce((sum, message) => (
    sum + cleanHistoryMessageContent(message.content || '').length
  ), 0);
  return Math.ceil(totalChars / 4);
};

export const formatApproxTokenCount = (count: number): string => (
  count >= 1000 ? `${Math.round(count / 1000)}k` : `${count}`
);

export const findTurnVirtualRangeIndex = (offsets: number[], target: number): number => {
  let low = 0;
  let high = offsets.length - 1;
  let bestIndex = 0;

  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    if (offsets[mid] <= target) {
      bestIndex = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }

  return bestIndex;
};
