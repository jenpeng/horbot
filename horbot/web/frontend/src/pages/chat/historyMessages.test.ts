import { describe, expect, it } from 'vitest';
import type { ExecutionStep } from '../../types/conversation';
import { mergeConversationHistoryMessages } from './historyMessages';
import type { UIMessage } from './types';

const mergeExecutionSteps = (
  existing: ExecutionStep[] = [],
  incoming: ExecutionStep[] = [],
) => [...existing, ...incoming];

describe('mergeConversationHistoryMessages', () => {
  it('replaces an optimistic user message with the persisted history user message for the same request', () => {
    const historyMessages: UIMessage[] = [
      {
        id: 'persisted-user',
        role: 'user',
        content: '你好',
        timestamp: '2026-05-07T15:53:38.379Z',
        turnId: 'turn-1',
        requestId: 'request-1',
      },
      {
        id: 'persisted-assistant',
        role: 'assistant',
        content: '你好！有什么可以帮你的吗？',
        timestamp: '2026-05-07T15:53:41.983Z',
        turnId: 'turn-1',
        requestId: 'request-1',
        agentId: 'main',
      },
    ];
    const existingMessages: UIMessage[] = [
      {
        id: 'optimistic-user',
        role: 'user',
        content: '你好',
        timestamp: '2026-05-07T15:53:36.000Z',
        turnId: 'turn-1',
        requestId: 'request-1',
      },
    ];

    const merged = mergeConversationHistoryMessages(historyMessages, existingMessages, mergeExecutionSteps);

    expect(merged.filter((message) => message.role === 'user' && message.content === '你好')).toHaveLength(1);
    expect(merged[0]).toMatchObject({
      id: 'persisted-user',
      role: 'user',
      content: '你好',
      turnId: 'turn-1',
      requestId: 'request-1',
    });
    expect(merged).toHaveLength(2);
  });

  it('replaces a markerless optimistic user message with the nearby persisted history user message', () => {
    const historyMessages: UIMessage[] = [
      {
        id: 'persisted-user',
        role: 'user',
        content: '你好',
        timestamp: '2026-05-09T17:15:06.129Z',
        turnId: 'turn-1',
        requestId: 'request-1',
      },
      {
        id: 'persisted-assistant',
        role: 'assistant',
        content: '你好呀！',
        timestamp: '2026-05-09T17:15:07.983Z',
        turnId: 'turn-1',
        requestId: 'request-1',
        agentId: 'main',
      },
    ];
    const existingMessages: UIMessage[] = [
      {
        id: 'optimistic-user',
        role: 'user',
        content: '你好',
        timestamp: '2026-05-09T17:15:05.000Z',
      },
    ];

    const merged = mergeConversationHistoryMessages(historyMessages, existingMessages, mergeExecutionSteps);

    expect(merged.filter((message) => message.role === 'user' && message.content === '你好')).toHaveLength(1);
    expect(merged[0]).toMatchObject({
      id: 'persisted-user',
      role: 'user',
      content: '你好',
      turnId: 'turn-1',
      requestId: 'request-1',
    });
    expect(merged).toHaveLength(2);
  });
});
