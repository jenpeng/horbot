import { ChatStreamError } from '../../services/chat';
import type { ProviderErrorInfo, TranslateFn } from './types';

export const isFriendlyProviderErrorMessage = (
  t: TranslateFn,
  content?: string,
): boolean => {
  const normalized = content?.trim();
  if (!normalized) {
    return false;
  }

  const friendlyMessages = new Set([
    t('chat.providerAuthError'),
    t('chat.providerModelMissing'),
    t('chat.providerBusy'),
    t('chat.providerTimeout'),
    t('chat.providerConnectionFailed'),
    t('chat.providerResponseInvalid'),
    t('chat.providerUnavailable'),
  ]);
  return friendlyMessages.has(normalized);
};

export const normalizeAssistantErrorContent = (
  t: TranslateFn,
  content?: string,
): {
  content: string;
  isProviderError: boolean;
} => {
  const normalized = content?.trim() || '';
  if (!normalized) {
    return { content: '', isProviderError: false };
  }
  if (isFriendlyProviderErrorMessage(t, normalized)) {
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
    return { content: t('chat.providerResponseInvalid'), isProviderError: true };
  }
  if (
    lower.includes('unauthorized') ||
    lower.includes('invalid api key') ||
    lower.includes('incorrect api key') ||
    lower.includes('forbidden')
  ) {
    return { content: t('chat.providerAuthError'), isProviderError: true };
  }
  if (lower.includes('model not found') || lower.includes('404')) {
    return { content: t('chat.providerModelMissing'), isProviderError: true };
  }
  if (
    lower.includes('rate limit') ||
    lower.includes('too many requests') ||
    lower.includes('overloaded') ||
    lower.includes('负载较高')
  ) {
    return { content: t('chat.providerBusy'), isProviderError: true };
  }
  if (
    lower.includes('timeout') ||
    lower.includes('timed out') ||
    lower.includes('readtimeout') ||
    lower.includes('connecttimeout')
  ) {
    return { content: t('chat.providerTimeout'), isProviderError: true };
  }

  return { content: normalized, isProviderError: false };
};

export const normalizeProviderErrorPayload = (value: unknown): ProviderErrorInfo | null => {
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

export const resolveStreamFailureMessage = (
  t: TranslateFn,
  error: unknown,
): {
  content: string;
  errorKind: 'network' | 'timeout' | 'stream';
} => {
  if (error instanceof ChatStreamError) {
    if (error.code === 'timeout') {
      return {
        content: t('chat.streamTimeoutMessage'),
        errorKind: 'timeout',
      };
    }
    if (error.code === 'http') {
      return {
        content: t('chat.streamHttpErrorMessage'),
        errorKind: 'stream',
      };
    }
  }

  return {
    content: t('chat.streamNetworkErrorMessage'),
    errorKind: 'network',
  };
};
