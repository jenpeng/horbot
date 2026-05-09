import { describe, expect, it } from 'vitest';
import { normalizeConversationMessages } from './messageDedupe';
import type { Message } from '../types/conversation';

describe('normalizeConversationMessages', () => {
  it('collapses a local optimistic user message and its persisted history copy', () => {
    const messages: Message[] = [
      {
        id: 'local-user',
        role: 'user',
        content: '你好',
        timestamp: '2026-05-09T17:15:05.000Z',
      },
      {
        id: 'persisted-user',
        role: 'user',
        content: '你好',
        timestamp: '2026-05-09T17:15:06.129Z',
        turnId: 'turn-1',
        requestId: 'request-1',
        metadata: {
          turn_id: 'turn-1',
          request_id: 'request-1',
        },
      },
      {
        id: 'assistant',
        role: 'assistant',
        content: '你好呀！',
        timestamp: '2026-05-09T17:15:07.000Z',
        turnId: 'turn-1',
        requestId: 'request-1',
      },
    ];

    const normalized = normalizeConversationMessages(messages);

    expect(normalized).toHaveLength(2);
    expect(normalized[0]).toMatchObject({
      id: 'persisted-user',
      role: 'user',
      content: '你好',
      turnId: 'turn-1',
      requestId: 'request-1',
    });
  });

  it('keeps intentional repeated user messages when there is no shared marker and enough time passes', () => {
    const messages: Message[] = [
      {
        id: 'first',
        role: 'user',
        content: '你好',
        timestamp: '2026-05-09T17:15:00.000Z',
      },
      {
        id: 'second',
        role: 'user',
        content: '你好',
        timestamp: '2026-05-09T17:15:10.000Z',
      },
    ];

    expect(normalizeConversationMessages(messages)).toHaveLength(2);
  });

  it('keeps same text messages with different attachments separate', () => {
    const messages: Message[] = [
      {
        id: 'first',
        role: 'user',
        content: '分析这个文件',
        timestamp: '2026-05-09T17:15:00.000Z',
        files: [
          {
            fileId: 'file-a',
            filename: 'a.pptx',
            originalName: 'a.pptx',
            mimeType: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            size: 100,
            category: 'document',
            url: '/uploads/a.pptx',
          },
        ],
      },
      {
        id: 'second',
        role: 'user',
        content: '分析这个文件',
        timestamp: '2026-05-09T17:15:01.000Z',
        files: [
          {
            fileId: 'file-b',
            filename: 'b.pptx',
            originalName: 'b.pptx',
            mimeType: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            size: 100,
            category: 'document',
            url: '/uploads/b.pptx',
          },
        ],
      },
    ];

    expect(normalizeConversationMessages(messages)).toHaveLength(2);
  });
});
