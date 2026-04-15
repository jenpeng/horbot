import { type ReactElement } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ChatPage from './ChatPage';
import { I18nProvider } from '../contexts/I18nContext';
import { ToastProvider } from '../contexts/ToastContext';
import { messages } from '../i18n/messages';
import { ChatStreamError, chatService } from '../services/chat';
import { useConversationStore } from '../stores/conversationStore';
import { ConversationType, type Conversation, type Message } from '../types/conversation';

vi.mock('../components/MessageGroup', () => ({
  default: () => <div data-testid="mock-message-group" />,
}));

vi.mock('../components/MessageExecutionCard', () => ({
  default: () => <div data-testid="mock-message-execution-card" />,
}));

vi.mock('../components/TypingIndicator', () => ({
  default: () => <div data-testid="mock-typing-indicator" />,
}));

vi.mock('../components/MessageInput', () => ({
  default: ({
    agents,
    conversationType,
    onSend,
    sessionStatus,
  }: {
    agents: Array<{ id: string }>;
    conversationType: string;
    onSend?: (message: string, mentionedAgents: string[], files?: unknown[]) => void | Promise<void>;
    sessionStatus?: { message?: string; detailLabel?: string; detailValue?: string } | null;
  }) => (
    <div
      data-testid="mock-message-input"
      data-conversation-type={conversationType}
      data-agent-ids={agents.map((agent) => agent.id).join(',')}
    >
      <button type="button" data-testid="mock-send-button" onClick={() => onSend?.('hello', [], [])}>
        send
      </button>
      {sessionStatus?.message ? <div>{sessionStatus.message}</div> : null}
      {sessionStatus?.detailLabel && sessionStatus?.detailValue ? (
        <div>{`${sessionStatus.detailLabel} ${sessionStatus.detailValue}`}</div>
      ) : null}
    </div>
  ),
}));

const renderWithProviders = (ui: ReactElement) => render(
  <ToastProvider>
    <I18nProvider>{ui}</I18nProvider>
  </ToastProvider>,
);

const createJsonResponse = (data: unknown): Response => ({
  json: async () => data,
} as Response);

class MockWebSocket {
  static OPEN = 1;
  static CLOSED = 3;

  readyState = MockWebSocket.OPEN;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.();
  });

  constructor(_url: string) {
    setTimeout(() => {
      this.onopen?.();
    }, 0);
  }
}

const internalAgent = {
  id: 'agent-a',
  name: 'Agent A',
  description: 'Internal agent',
};

const externalAgent = {
  id: 'partner-agent',
  name: 'Partner Agent',
  description: 'External partner',
  team_enabled: true,
};

const team = {
  id: 'team-a',
  name: 'Team A',
  description: 'Delivery team',
  members: ['agent-a', 'partner-agent'],
};

const seedConversationStore = (conversation: Conversation) => {
  useConversationStore.setState((state) => ({
    ...state,
    conversations: [conversation],
    currentConversationId: conversation.id,
    messages: {},
    typingAgents: {},
  }));
};

const seedConversationMessages = (conversationId: string, messages: Message[]) => {
  useConversationStore.setState((state) => ({
    ...state,
    messages: {
      ...state.messages,
      [conversationId]: messages,
    },
  }));
};

describe('ChatPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    Object.defineProperty(HTMLElement.prototype, 'scrollTo', {
      configurable: true,
      value: vi.fn(),
    });

    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/agents') {
        return Promise.resolve(createJsonResponse({ agents: [internalAgent] }));
      }
      if (url === '/api/external-agents') {
        return Promise.resolve(createJsonResponse({ external_agents: [externalAgent] }));
      }
      if (url === '/api/teams') {
        return Promise.resolve(createJsonResponse({ teams: [team] }));
      }
      if (url === '/api/conversations/dm_partner-agent/messages') {
        return Promise.resolve(createJsonResponse({
          conversation_id: 'dm_partner-agent',
          conversation: {
            id: 'dm_partner-agent',
            type: ConversationType.DM,
            target_id: 'partner-agent',
            name: 'Partner Agent',
            agent_ids: ['partner-agent'],
          },
          messages: [],
        }));
      }
      if (url === '/api/conversations/team_team-a/messages') {
        return Promise.resolve(createJsonResponse({
          conversation_id: 'team_team-a',
          conversation: {
            id: 'team_team-a',
            type: ConversationType.TEAM,
            target_id: 'team-a',
            name: 'Team A',
            agent_ids: ['agent-a', 'partner-agent'],
          },
          messages: [],
        }));
      }
      return Promise.resolve(createJsonResponse({ messages: [] }));
    }));

    vi.stubGlobal('WebSocket', MockWebSocket as unknown as typeof WebSocket);
  });

  it('shows external agents in the direct conversation list with a badge', async () => {
    seedConversationStore({
      id: 'dm_partner-agent',
      type: ConversationType.DM,
      targetId: 'partner-agent',
      name: 'Partner Agent',
      agentIds: ['partner-agent'],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    renderWithProviders(<ChatPage />);

    await waitFor(() => {
      expect(screen.getByText('Partner Agent')).toBeInTheDocument();
    });
    expect(screen.getAllByText(/External|外部/).length).toBeGreaterThan(0);
  });

  it('passes team-enabled external agents to the team message input mention list', async () => {
    seedConversationStore({
      id: 'team_team-a',
      type: ConversationType.TEAM,
      targetId: 'team-a',
      name: 'Team A',
      agentIds: ['agent-a', 'partner-agent'],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    renderWithProviders(<ChatPage />);

    await waitFor(() => {
      expect(screen.getByTestId('mock-message-input')).toBeInTheDocument();
    });

    expect(screen.getByTestId('mock-message-input')).toHaveAttribute(
      'data-agent-ids',
      'agent-a,partner-agent',
    );
  });

  it('provides a localized retry banner message for Chinese chat sessions', () => {
    expect(messages['zh-CN']['chat.sessionRetryLastMessage']).toBe('上一轮请求失败，可重试。');
  });

  it('clears the stale retry banner after a later successful send', async () => {
    const streamChatMock = vi.spyOn(chatService, 'streamChat');
    streamChatMock
      .mockImplementationOnce(async ({ onStateChange }) => {
        onStateChange?.('error');
        throw new ChatStreamError('network failed', 'network');
      })
      .mockImplementationOnce(async ({ onStateChange, onRequestStart, onChunk }) => {
        onStateChange?.('connecting');
        onRequestStart?.('req-success');
        onChunk({
          event: 'request_start',
          agent_id: 'agent-a',
          agent_name: 'Agent A',
          turn_id: 'turn-success',
          message_id: 'msg-success',
        });
        onChunk({
          event: 'content',
          agent_id: 'agent-a',
          turn_id: 'turn-success',
          message_id: 'msg-success',
          content: '好的',
        });
        onChunk({
          event: 'request_end',
          agent_id: 'agent-a',
          agent_name: 'Agent A',
          turn_id: 'turn-success',
          message_id: 'msg-success',
          content: '好的',
        });
        onChunk({ event: 'done' });
      });

    seedConversationStore({
      id: 'dm_agent-a',
      type: ConversationType.DM,
      targetId: 'agent-a',
      name: 'Agent A',
      agentIds: ['agent-a'],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    renderWithProviders(<ChatPage />);

    await waitFor(() => {
      expect(screen.getByTestId('mock-send-button')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('mock-send-button'));

    await waitFor(() => {
      expect(screen.getByText('The previous request failed. You can retry it.')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('mock-send-button'));

    await waitFor(() => {
      expect(screen.queryByText('The previous request failed. You can retry it.')).not.toBeInTheDocument();
    });
  });

  it('suppresses a false timeout banner when the completed reply is already persisted in history', async () => {
    const completedRequestId = 'req-timeout-settled';
    const persistedHistory = [
      {
        id: 'history-user',
        role: 'user',
        content: 'hello',
        timestamp: new Date().toISOString(),
        metadata: {
          turn_id: 'turn-timeout-settled',
          request_id: completedRequestId,
        },
      },
      {
        id: 'history-assistant',
        role: 'assistant',
        content: '最终结果',
        timestamp: new Date().toISOString(),
        metadata: {
          agent_id: 'agent-a',
          agent_name: 'Agent A',
          turn_id: 'turn-timeout-settled',
          request_id: completedRequestId,
        },
      },
    ];

    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/agents') {
        return Promise.resolve(createJsonResponse({ agents: [internalAgent] }));
      }
      if (url === '/api/external-agents') {
        return Promise.resolve(createJsonResponse({ external_agents: [externalAgent] }));
      }
      if (url === '/api/teams') {
        return Promise.resolve(createJsonResponse({ teams: [team] }));
      }
      if (url === '/api/conversations/dm_agent-a/messages') {
        return Promise.resolve(createJsonResponse({
          conversation_id: 'dm_agent-a',
          conversation: {
            id: 'dm_agent-a',
            type: ConversationType.DM,
            target_id: 'agent-a',
            name: 'Agent A',
            agent_ids: ['agent-a'],
          },
          messages: persistedHistory,
        }));
      }
      return Promise.resolve(createJsonResponse({ messages: [] }));
    });

    vi.spyOn(chatService, 'streamChat').mockImplementationOnce(async ({ onStateChange, onRequestStart }) => {
      onStateChange?.('connecting');
      onRequestStart?.(completedRequestId);
      onStateChange?.('timeout');
      throw new ChatStreamError('timed out', 'timeout');
    });

    seedConversationStore({
      id: 'dm_agent-a',
      type: ConversationType.DM,
      targetId: 'agent-a',
      name: 'Agent A',
      agentIds: ['agent-a'],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    renderWithProviders(<ChatPage />);

    await waitFor(() => {
      expect(screen.getByTestId('mock-send-button')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('mock-send-button'));

    await waitFor(() => {
      const conversationMessages = useConversationStore.getState().messages['dm_agent-a'] || [];
      expect(conversationMessages.some((message) => message.content === '最终结果' && !message.isError)).toBe(true);
    });

    expect(screen.queryByText('The previous request failed. You can retry it.')).not.toBeInTheDocument();
  });

  it('surfaces the failed request id in the retry banner and turn badge', async () => {
    const failedRequestId = '150e65af-1406-4945-bd11-69c3b6f327ea';

    vi.spyOn(chatService, 'streamChat').mockImplementationOnce(async ({ onStateChange, onRequestStart }) => {
      onStateChange?.('connecting');
      onRequestStart?.(failedRequestId);
      onStateChange?.('error');
      throw new ChatStreamError('network failed', 'network');
    });

    seedConversationStore({
      id: 'dm_agent-a',
      type: ConversationType.DM,
      targetId: 'agent-a',
      name: 'Agent A',
      agentIds: ['agent-a'],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    renderWithProviders(<ChatPage />);

    await waitFor(() => {
      expect(screen.getByTestId('mock-send-button')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('mock-send-button'));

    await waitFor(() => {
      expect(screen.getByText('The previous request failed. You can retry it.')).toBeInTheDocument();
      expect(screen.getByText(`Request ID ${failedRequestId}`)).toBeInTheDocument();
      expect(screen.getByText('Req 150e65af')).toBeInTheDocument();
    });

    expect(screen.getByTitle(failedRequestId)).toBeInTheDocument();
  });

  it('shows a conversation health warning for oversized chat history', async () => {
    const conversationId = 'dm_agent-a';
    const largeTurnMessages = Array.from({ length: 18 }, (_, index) => ([
      {
        id: `user-${index}`,
        role: 'user' as const,
        content: `需求 ${index} ` + 'a'.repeat(1800),
        timestamp: new Date(Date.now() + index * 1000).toISOString(),
      },
      {
        id: `assistant-${index}`,
        role: 'assistant' as const,
        content: `回复 ${index} ` + 'b'.repeat(1800),
        timestamp: new Date(Date.now() + index * 1000 + 500).toISOString(),
        agentId: 'agent-a',
        agentName: 'Agent A',
      },
    ])).flat();

    seedConversationStore({
      id: conversationId,
      type: ConversationType.DM,
      targetId: 'agent-a',
      name: 'Agent A',
      agentIds: ['agent-a'],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });
    seedConversationMessages(conversationId, largeTurnMessages);

    renderWithProviders(<ChatPage />);

    await waitFor(() => {
      expect(screen.getByTestId('chat-conversation-health')).toBeInTheDocument();
    });

    expect(screen.getByText('Oversized context')).toBeInTheDocument();
    expect(screen.getByText(/Approx .* tokens .* turns/)).toBeInTheDocument();
  });
});
