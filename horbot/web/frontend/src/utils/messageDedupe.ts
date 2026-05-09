type MessageMetadata = Record<string, unknown> | undefined;

export interface DedupeMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
  turnId?: string;
  requestId?: string;
  files?: unknown[];
  metadata?: MessageMetadata;
}

const USER_DUPLICATE_MARKER_WINDOW_MS = 15 * 1000;
const USER_DUPLICATE_LOCAL_WINDOW_MS = 3 * 1000;

const normalizeContent = (content: string | undefined): string => (
  (content || '').replace(/\s+/g, ' ').trim()
);

const parseTimestamp = (timestamp?: string): number | null => {
  if (!timestamp) {
    return null;
  }
  const parsed = Date.parse(timestamp);
  return Number.isNaN(parsed) ? null : parsed;
};

const getMetadataString = (metadata: MessageMetadata, key: string): string => {
  const value = metadata?.[key];
  return typeof value === 'string' ? value : '';
};

const resolveRequestId = (message: DedupeMessage): string => (
  message.requestId || getMetadataString(message.metadata, 'request_id')
);

const resolveTurnId = (message: DedupeMessage): string => (
  message.turnId || getMetadataString(message.metadata, 'turn_id')
);

const hasRequestMarker = (message: DedupeMessage): boolean => (
  Boolean(resolveRequestId(message) || resolveTurnId(message))
);

const buildFilesSignature = (files?: unknown[]): string => {
  if (!Array.isArray(files) || files.length === 0) {
    return '';
  }

  return JSON.stringify(files.map((file) => {
    const payload = file && typeof file === 'object' ? file as Record<string, unknown> : {};
    return {
      fileId: typeof payload.fileId === 'string' ? payload.fileId : '',
      originalName: typeof payload.originalName === 'string' ? payload.originalName : '',
      filename: typeof payload.filename === 'string' ? payload.filename : '',
      size: typeof payload.size === 'number' ? payload.size : 0,
      url: typeof payload.url === 'string' ? payload.url : '',
    };
  }));
};

const hasSameRequestMarker = (left: DedupeMessage, right: DedupeMessage): boolean => {
  const leftRequestId = resolveRequestId(left);
  const rightRequestId = resolveRequestId(right);
  if (leftRequestId && rightRequestId && leftRequestId === rightRequestId) {
    return true;
  }

  const leftTurnId = resolveTurnId(left);
  const rightTurnId = resolveTurnId(right);
  return Boolean(leftTurnId && rightTurnId && leftTurnId === rightTurnId);
};

const hasConflictingRequestMarkers = (left: DedupeMessage, right: DedupeMessage): boolean => {
  const leftRequestId = resolveRequestId(left);
  const rightRequestId = resolveRequestId(right);
  if (leftRequestId && rightRequestId && leftRequestId !== rightRequestId) {
    return true;
  }

  const leftTurnId = resolveTurnId(left);
  const rightTurnId = resolveTurnId(right);
  return Boolean(leftTurnId && rightTurnId && leftTurnId !== rightTurnId);
};

const getTimestampDelta = (left: DedupeMessage, right: DedupeMessage): number | null => {
  const leftTimestamp = parseTimestamp(left.timestamp);
  const rightTimestamp = parseTimestamp(right.timestamp);
  if (leftTimestamp === null || rightTimestamp === null) {
    return null;
  }
  return Math.abs(leftTimestamp - rightTimestamp);
};

export const areDuplicateUserMessages = (left: DedupeMessage, right: DedupeMessage): boolean => {
  if (left.role !== 'user' || right.role !== 'user') {
    return false;
  }

  const leftContent = normalizeContent(left.content);
  const rightContent = normalizeContent(right.content);
  const leftFilesSignature = buildFilesSignature(left.files);
  const rightFilesSignature = buildFilesSignature(right.files);
  if (!leftContent && !leftFilesSignature) {
    return false;
  }
  if (leftContent !== rightContent || leftFilesSignature !== rightFilesSignature) {
    return false;
  }
  if (hasConflictingRequestMarkers(left, right)) {
    return false;
  }
  if (hasSameRequestMarker(left, right)) {
    return true;
  }

  const timestampDelta = getTimestampDelta(left, right);
  if (timestampDelta === null) {
    return false;
  }

  if (hasRequestMarker(left) || hasRequestMarker(right)) {
    return timestampDelta <= USER_DUPLICATE_MARKER_WINDOW_MS;
  }

  return timestampDelta <= USER_DUPLICATE_LOCAL_WINDOW_MS;
};

const scoreMessage = (message: DedupeMessage): number => {
  let score = 0;
  if (resolveRequestId(message)) score += 8;
  if (resolveTurnId(message)) score += 8;
  if (message.timestamp) score += 2;
  if (Array.isArray(message.files) && message.files.length > 0) score += 1;
  if (normalizeContent(message.content)) score += 1;
  return score;
};

const mergeMessages = <T extends DedupeMessage>(
  current: T,
  incoming: T,
  preferIncoming: boolean,
): T => {
  const currentScore = scoreMessage(current);
  const incomingScore = scoreMessage(incoming);
  const preferred = preferIncoming || incomingScore > currentScore ? incoming : current;
  const fallback = preferred === incoming ? current : incoming;

  return {
    ...fallback,
    ...preferred,
    id: preferred.id,
    content: preferred.content || fallback.content,
    timestamp: preferred.timestamp || fallback.timestamp,
    turnId: preferred.turnId || fallback.turnId,
    requestId: preferred.requestId || fallback.requestId,
    files: preferred.files || fallback.files,
    metadata: {
      ...(fallback.metadata || {}),
      ...(preferred.metadata || {}),
    },
  };
};

const findDuplicateUserIndex = <T extends DedupeMessage>(messages: T[], incoming: T): number => {
  if (incoming.role !== 'user') {
    return -1;
  }

  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (areDuplicateUserMessages(messages[index], incoming)) {
      return index;
    }
  }
  return -1;
};

export const normalizeConversationMessages = <T extends DedupeMessage>(messages: T[]): T[] => {
  if (messages.length < 2) {
    return messages;
  }

  let changed = false;
  const normalized: T[] = [];
  const indexById = new Map<string, number>();

  messages.forEach((message) => {
    const idIndex = indexById.get(message.id);
    if (idIndex !== undefined) {
      normalized[idIndex] = mergeMessages(normalized[idIndex], message, true);
      changed = true;
      return;
    }

    const duplicateUserIndex = findDuplicateUserIndex(normalized, message);
    if (duplicateUserIndex !== -1) {
      const previousId = normalized[duplicateUserIndex].id;
      normalized[duplicateUserIndex] = mergeMessages(normalized[duplicateUserIndex], message, false);
      if (normalized[duplicateUserIndex].id !== previousId) {
        indexById.delete(previousId);
        indexById.set(normalized[duplicateUserIndex].id, duplicateUserIndex);
      }
      changed = true;
      return;
    }

    indexById.set(message.id, normalized.length);
    normalized.push(message);
  });

  return changed ? normalized : messages;
};
