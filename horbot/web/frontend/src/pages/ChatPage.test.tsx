import { type ReactElement } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ChatPage from './ChatPage';
import { I18nProvider } from '../contexts/I18nContext';
import { ToastProvider } from '../contexts/ToastContext';
import zhCNMessages from '../i18n/locales/zh-CN';
import { ChatStreamError, chatService } from '../services/chat';
import taskWorkspacesService from '../services/taskWorkspaces';
import { useConversationStore } from '../stores/conversationStore';
import { ConversationType, type Conversation, type Message } from '../types/conversation';

const messageGroupMock = vi.fn((_props: unknown) => <div data-testid="mock-message-group" />);

vi.mock('../components/MessageGroup', () => ({
  default: (props: unknown) => messageGroupMock(props),
}));

vi.mock('../components/MessageExecutionCard', () => ({
  default: () => <div data-testid="mock-message-execution-card" />,
}));

vi.mock('../components/TypingIndicator', () => ({
  default: () => <div data-testid="mock-typing-indicator" />,
}));

vi.mock('../services/taskWorkspaces', () => ({
  default: {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn(),
    update: vi.fn(),
    listFiles: vi.fn().mockResolvedValue({
      task_id: '',
      cwd: '',
      exists: false,
      files: [],
      truncated: false,
    }),
    listChanges: vi.fn().mockResolvedValue({
      task_id: '',
      cwd: '',
      available: true,
      reason: null,
      changes: [],
      truncated: false,
    }),
  },
}));

vi.mock('../components/MessageInput', () => ({
  default: ({
    agents,
    conversationType,
    onSend,
    sessionStatus,
    draftPresetText,
  }: {
    agents: Array<{ id: string }>;
    conversationType: string;
    onSend?: (message: string, mentionedAgents: string[], files?: unknown[]) => void | Promise<void>;
    sessionStatus?: { message?: string; detailLabel?: string; detailValue?: string } | null;
    draftPresetText?: string;
  }) => (
    <div
      data-testid="mock-message-input"
      data-conversation-type={conversationType}
      data-agent-ids={agents.map((agent) => agent.id).join(',')}
      data-draft-preset={draftPresetText || ''}
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
  static instances: MockWebSocket[] = [];

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
    MockWebSocket.instances.push(this);
    setTimeout(() => {
      this.onopen?.();
    }, 0);
  }

  emitMessage(payload: Record<string, unknown>) {
    this.onmessage?.({ data: JSON.stringify(payload) });
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

describe('ChatPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    messageGroupMock.mockClear();
    MockWebSocket.instances = [];
    window.localStorage.clear();
    Object.defineProperty(HTMLElement.prototype, 'scrollTo', {
      configurable: true,
      value: vi.fn(),
    });
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: vi.fn(),
    });
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
    vi.mocked(taskWorkspacesService.list).mockResolvedValue([]);
    vi.mocked(taskWorkspacesService.create).mockReset();
    vi.mocked(taskWorkspacesService.update).mockReset();
    vi.mocked(taskWorkspacesService.listFiles).mockResolvedValue({
      task_id: '',
      cwd: '',
      exists: false,
      files: [],
      truncated: false,
    });
    vi.mocked(taskWorkspacesService.listChanges).mockResolvedValue({
      task_id: '',
      cwd: '',
      available: true,
      reason: null,
      changes: [],
      truncated: false,
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
      if (url.startsWith('/api/conversations/dm_partner-agent/messages')) {
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
      if (url.startsWith('/api/conversations/team_team-a/messages')) {
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
      expect(screen.getAllByText('Partner Agent').length).toBeGreaterThan(0);
      expect(screen.getAllByText(/External|外部/).length).toBeGreaterThan(0);
    });
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

  it('collapses the conversation header and persists the preference', async () => {
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

    const toggle = await screen.findByTestId('chat-header-collapse-toggle');

    expect(screen.getByText(/适合直接问答|Best for direct Q&A/)).toBeInTheDocument();

    fireEvent.click(toggle);

    expect(window.localStorage.getItem('horbot.chat.conversationHeaderCollapsed')).toBe('true');
    expect(screen.getByTestId('chat-conversation-header-details')).toHaveAttribute('aria-hidden', 'true');
    expect(screen.getByRole('button', { name: /展开|Expand/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /展开|Expand/ }));

    expect(window.localStorage.getItem('horbot.chat.conversationHeaderCollapsed')).toBe('false');
    expect(screen.getByTestId('chat-conversation-header-details')).toHaveAttribute('aria-hidden', 'false');
    expect(screen.getByText(/适合直接问答|Best for direct Q&A/)).toBeInTheDocument();
  });

  it('sticks to the bottom after initial history load completes', async () => {
    const conversationId = 'dm_agent-a';
    const scrollToMock = vi.fn();
    Object.defineProperty(HTMLElement.prototype, 'scrollTo', {
      configurable: true,
      value: scrollToMock,
    });

    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/agents') {
        return Promise.resolve(createJsonResponse({ agents: [internalAgent] }));
      }
      if (url === '/api/external-agents') {
        return Promise.resolve(createJsonResponse({ external_agents: [] }));
      }
      if (url === '/api/teams') {
        return Promise.resolve(createJsonResponse({ teams: [] }));
      }
      if (url.startsWith(`/api/conversations/${conversationId}/messages`)) {
        return Promise.resolve(createJsonResponse({
          conversation_id: conversationId,
          conversation: {
            id: conversationId,
            type: ConversationType.DM,
            target_id: 'agent-a',
            name: 'Agent A',
            agent_ids: ['agent-a'],
          },
          messages: [
            {
              id: 'user-1',
              role: 'user',
              content: 'hello',
              timestamp: new Date(Date.now() - 60_000).toISOString(),
            },
            {
              id: 'assistant-1',
              role: 'assistant',
              content: 'world',
              timestamp: new Date().toISOString(),
              metadata: {
                agent_id: 'agent-a',
                agent_name: 'Agent A',
              },
            },
          ],
          page: {
            oldest_message_id: 'user-1',
            newest_message_id: 'assistant-1',
            has_more_before: false,
            has_more_after: false,
            total_messages: 2,
          },
        }));
      }
      return Promise.resolve(createJsonResponse({ messages: [] }));
    });

    seedConversationStore({
      id: conversationId,
      type: ConversationType.DM,
      targetId: 'agent-a',
      name: 'Agent A',
      agentIds: ['agent-a'],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    renderWithProviders(<ChatPage />);

    await waitFor(() => {
      expect(scrollToMock).toHaveBeenCalled();
    });

    expect(scrollToMock.mock.calls.some(([arg]) => (
      typeof arg === 'object'
      && arg !== null
      && 'top' in arg
      && typeof (arg as { top?: number }).top === 'number'
    ))).toBe(true);
  });

  it('summarizes the current task workbench from loaded messages without extra model output', async () => {
    const conversationId = 'dm_agent-a';
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/agents') {
        return Promise.resolve(createJsonResponse({ agents: [internalAgent] }));
      }
      if (url === '/api/external-agents') {
        return Promise.resolve(createJsonResponse({ external_agents: [] }));
      }
      if (url === '/api/teams') {
        return Promise.resolve(createJsonResponse({ teams: [] }));
      }
      if (url.startsWith(`/api/conversations/${conversationId}/messages`)) {
        return Promise.resolve(createJsonResponse({
          conversation_id: conversationId,
          conversation: {
            id: conversationId,
            type: ConversationType.DM,
            target_id: 'agent-a',
            name: 'Agent A',
            agent_ids: ['agent-a'],
          },
          messages: [
            {
              id: 'user-task',
              role: 'user',
              content: 'Create a clean PPT summary',
              timestamp: new Date(Date.now() - 60_000).toISOString(),
              files: [
                {
                  fileId: 'file-1',
                  filename: 'brief.pptx',
                  originalName: 'brief.pptx',
                  mimeType: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                  size: 128,
                  category: 'office',
                  url: '/api/files/file-1',
                },
              ],
            },
            {
              id: 'assistant-task',
              role: 'assistant',
              content: 'Created the summary.',
              timestamp: new Date().toISOString(),
              execution_steps: [
                {
                  id: 'step-1',
                  type: 'tool_call',
                  title: 'Run officecli',
                  status: 'success',
                  timestamp: new Date().toISOString(),
                  details: { toolName: 'officecli' },
                },
              ],
              metadata: {
                agent_id: 'agent-a',
                agent_name: 'Agent A',
              },
            },
          ],
        }));
      }
      return Promise.resolve(createJsonResponse({ messages: [] }));
    });

    seedConversationStore({
      id: conversationId,
      type: ConversationType.DM,
      targetId: 'agent-a',
      name: 'Agent A',
      agentIds: ['agent-a'],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    renderWithProviders(<ChatPage />);

    expect(await screen.findByRole('button', { name: /Task Workbench|任务工作台/ })).toBeInTheDocument();
    expect(screen.queryByTestId('chat-workbench-panel')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Task Workbench|任务工作台/ }));
    expect(screen.getByTestId('chat-workbench-panel')).toBeInTheDocument();
    expect(screen.getByText(/Latest request: Create a clean PPT summary|最近请求：Create a clean PPT summary/)).toBeInTheDocument();
    expect(screen.getByText(/1 files|1 个文件/)).toBeInTheDocument();
    expect(screen.getByText(/1 execution steps|1 个执行步骤/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Copy summary|复制摘要/ }));
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining('officecli'));
    });
    fireEvent.click(screen.getByRole('button', { name: /Use summary|填入摘要/ }));
    expect(screen.getByTestId('mock-message-input')).toHaveAttribute(
      'data-draft-preset',
      expect.stringMatching(/Task Workbench|任务工作台/),
    );
    fireEvent.click(screen.getByRole('button', { name: /Search request|搜索请求/ }));
    const historySearchInput = await screen.findByPlaceholderText(/Type keywords|输入关键词/);
    expect(historySearchInput).toHaveValue('Create a clean PPT summary');
    expect(screen.queryByTestId('chat-workbench-panel')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Task Workbench|任务工作台/ }));
    expect(screen.getByText('officecli')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Review files|梳理附件/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Review files|梳理附件/ }));
    expect(screen.getByTestId('mock-message-input')).toHaveAttribute(
      'data-draft-preset',
      expect.stringMatching(/attached files|附件/),
    );
  });

  it('keeps assistant history messages that only contain image files', async () => {
    const remoteUrl = 'https://image.pollinations.ai/prompt/pony?seed=7';
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/agents') {
        return Promise.resolve(createJsonResponse({ agents: [internalAgent] }));
      }
      if (url === '/api/external-agents') {
        return Promise.resolve(createJsonResponse({ external_agents: [] }));
      }
      if (url === '/api/teams') {
        return Promise.resolve(createJsonResponse({ teams: [] }));
      }
      if (url.startsWith('/api/conversations/dm_agent-a/messages')) {
        return Promise.resolve(createJsonResponse({
          conversation_id: 'dm_agent-a',
          conversation: {
            id: 'dm_agent-a',
            type: ConversationType.DM,
            target_id: 'agent-a',
            name: 'Agent A',
            agent_ids: ['agent-a'],
          },
          messages: [
            {
              id: 'assistant-image-only',
              role: 'assistant',
              content: '',
              timestamp: new Date().toISOString(),
              files: [
                {
                  file_id: 'remote-image-1',
                  filename: 'pony-7.png',
                  original_name: 'pony-7.png',
                  mime_type: 'image/png',
                  size: 0,
                  category: 'image',
                  url: remoteUrl,
                  preview_url: remoteUrl,
                },
              ],
              metadata: {
                agent_id: 'agent-a',
                agent_name: 'Agent A',
              },
            },
          ],
        }));
      }
      return Promise.resolve(createJsonResponse({ messages: [] }));
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
      expect(messageGroupMock).toHaveBeenCalled();
    });

    const messageGroupCalls = messageGroupMock.mock.calls as Array<[unknown]>;
    const matchedCall = messageGroupCalls.find(([props]) => {
      const messages = (props as { messages?: Message[] }).messages || [];
      return messages.some((message) => message.id === 'assistant-image-only');
    });

    expect(matchedCall).toBeTruthy();
    const renderedMessages = ((matchedCall?.[0] as { messages?: Message[] })?.messages || []);
    const assistantMessage = renderedMessages.find((message) => message.id === 'assistant-image-only');
    expect(assistantMessage?.files?.[0]?.previewUrl).toBe(remoteUrl);
    expect(assistantMessage?.content).toBe('');
  });

  it('keeps assistant history messages that only contain execution steps', async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/agents') {
        return Promise.resolve(createJsonResponse({ agents: [internalAgent] }));
      }
      if (url === '/api/external-agents') {
        return Promise.resolve(createJsonResponse({ external_agents: [] }));
      }
      if (url === '/api/teams') {
        return Promise.resolve(createJsonResponse({ teams: [] }));
      }
      if (url.startsWith('/api/conversations/dm_agent-a/messages')) {
        return Promise.resolve(createJsonResponse({
          conversation_id: 'dm_agent-a',
          conversation: {
            id: 'dm_agent-a',
            type: ConversationType.DM,
            target_id: 'agent-a',
            name: 'Agent A',
            agent_ids: ['agent-a'],
          },
          messages: [
            {
              id: 'assistant-exec-only',
              role: 'assistant',
              content: '',
              timestamp: new Date().toISOString(),
              execution_steps: [
                {
                  id: 'step-restore',
                  type: 'tool_call',
                  title: '执行 exec',
                  status: 'success',
                  timestamp: new Date().toISOString(),
                  details: {
                    toolName: 'exec',
                  },
                },
              ],
              metadata: {
                agent_id: 'agent-a',
                agent_name: 'Agent A',
              },
            },
          ],
        }));
      }
      return Promise.resolve(createJsonResponse({ messages: [] }));
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
      expect(messageGroupMock).toHaveBeenCalled();
    });

    const messageGroupCalls = messageGroupMock.mock.calls as Array<[unknown]>;
    const matchedCall = messageGroupCalls.find(([props]) => {
      const messages = (props as { messages?: Message[] }).messages || [];
      return messages.some((message) => message.id === 'assistant-exec-only');
    });

    expect(matchedCall).toBeTruthy();
    const renderedMessages = ((matchedCall?.[0] as { messages?: Message[] })?.messages || []);
    const assistantMessage = renderedMessages.find((message) => message.id === 'assistant-exec-only');
    expect(assistantMessage?.executionSteps?.[0]?.id).toBe('step-restore');
    expect(assistantMessage?.content).toBe('');
  });

  it('provides a localized retry banner message for Chinese chat sessions', () => {
    expect(zhCNMessages['chat.sessionRetryLastMessage']).toBe('上一轮请求失败，可重试。');
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
      if (url.startsWith('/api/conversations/dm_agent-a/messages')) {
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

  it('keeps assistant content after </message> wrappers when loading history', async () => {
    const conversationId = 'dm_agent-a';
    const mixedAssistantContent = '<message from="Agent A">\n我先给你做一个清单。\n</message>## 结果\n- A\n- B';

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
      if (url.startsWith(`/api/conversations/${conversationId}/messages`)) {
        return Promise.resolve(createJsonResponse({
          conversation_id: conversationId,
          conversation: {
            id: conversationId,
            type: ConversationType.DM,
            target_id: 'agent-a',
            name: 'Agent A',
            agent_ids: ['agent-a'],
          },
          messages: [
            {
              id: 'history-user',
              role: 'user',
              content: 'hello',
              timestamp: new Date().toISOString(),
            },
            {
              id: 'history-assistant',
              role: 'assistant',
              content: mixedAssistantContent,
              timestamp: new Date().toISOString(),
              metadata: {
                agent_id: 'agent-a',
                agent_name: 'Agent A',
                turn_id: 'turn-mixed',
                request_id: 'req-mixed',
              },
            },
          ],
        }));
      }
      return Promise.resolve(createJsonResponse({ messages: [] }));
    });

    seedConversationStore({
      id: conversationId,
      type: ConversationType.DM,
      targetId: 'agent-a',
      name: 'Agent A',
      agentIds: ['agent-a'],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    renderWithProviders(<ChatPage />);

    await waitFor(() => {
      const conversationMessages = useConversationStore.getState().messages[conversationId] || [];
      expect(conversationMessages.some((message) => message.role === 'assistant')).toBe(true);
    });

    const conversationMessages = useConversationStore.getState().messages[conversationId] || [];
    const assistantMessage = conversationMessages.find((message) => message.role === 'assistant');
    expect(assistantMessage?.content).toContain('我先给你做一个清单。');
    expect(assistantMessage?.content).toContain('## 结果');
    expect(assistantMessage?.content).toContain('- A');
  });

  it('retries a provider error restored from history when the message retry action is clicked', async () => {
    const conversationId = 'dm_agent-a';
    const streamChatMock = vi.spyOn(chatService, 'streamChat').mockImplementation(async ({ onStateChange, onRequestStart, onChunk }) => {
      onStateChange?.('connecting');
      onRequestStart?.('req-retry-from-history');
      onChunk({
        event: 'request_start',
        agent_id: 'agent-a',
        agent_name: 'Agent A',
        turn_id: 'turn-retry-history',
        message_id: 'assistant-retry-history',
      });
      onChunk({
        event: 'content',
        agent_id: 'agent-a',
        turn_id: 'turn-retry-history',
        message_id: 'assistant-retry-history',
        content: 'retry ok',
      });
      onChunk({
        event: 'request_end',
        agent_id: 'agent-a',
        agent_name: 'Agent A',
        turn_id: 'turn-retry-history',
        message_id: 'assistant-retry-history',
        content: 'retry ok',
      });
      onChunk({ event: 'done' });
    });

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
      if (url.startsWith(`/api/conversations/${conversationId}/messages`)) {
        return Promise.resolve(createJsonResponse({
          conversation_id: conversationId,
          conversation: {
            id: conversationId,
            type: ConversationType.DM,
            target_id: 'agent-a',
            name: 'Agent A',
            agent_ids: ['agent-a'],
          },
          messages: [
            {
              id: 'history-user-retry',
              role: 'user',
              content: 'retry me',
              timestamp: new Date().toISOString(),
            },
            {
              id: 'history-assistant-retry',
              role: 'assistant',
              content: '模型服务当前负载较高，请稍后重试。',
              timestamp: new Date().toISOString(),
              metadata: {
                agent_id: 'agent-a',
                agent_name: 'Agent A',
                turn_id: 'turn-retry-history',
                request_id: 'req-history-failed',
                _provider_error: {
                  error_code: 'PROVIDER_RATE_LIMITED',
                  error_kind: 'rate_limit',
                  retryable: true,
                },
              },
            },
          ],
        }));
      }
      return Promise.resolve(createJsonResponse({ messages: [] }));
    });

    seedConversationStore({
      id: conversationId,
      type: ConversationType.DM,
      targetId: 'agent-a',
      name: 'Agent A',
      agentIds: ['agent-a'],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    renderWithProviders(<ChatPage />);

    await waitFor(() => {
      expect(messageGroupMock).toHaveBeenCalled();
    });

    const messageGroupCalls = messageGroupMock.mock.calls as Array<[unknown]>;
    const matchedCall = messageGroupCalls.find(([props]) => {
      const messages = (props as { messages?: Message[] }).messages || [];
      return messages.some((message) => message.id === 'history-assistant-retry');
    });

    expect(matchedCall).toBeTruthy();
    const props = matchedCall?.[0] as {
      messages?: Message[];
      onRetryMessage?: (message: Message) => void | Promise<void>;
    };
    const retryMessage = props.messages?.find((message) => message.id === 'history-assistant-retry');
    expect(retryMessage?.retryPayload?.content).toBe('retry me');

    await act(async () => {
      await props.onRetryMessage?.(retryMessage as Message);
    });

    await waitFor(() => {
      expect(streamChatMock).toHaveBeenCalled();
    });
    expect(streamChatMock.mock.calls.at(-1)?.[0]?.message).toBe('retry me');
  });

  it('keeps execution steps visible when streaming steps arrive before request_start', async () => {
    let resolveStream: (() => void) | null = null;
    vi.spyOn(chatService, 'streamChat').mockImplementation(async ({ onStateChange, onChunk }) => {
      onStateChange?.('connecting');
      onChunk({
        event: 'step_start',
        agent_id: 'agent-a',
        agent_name: 'Agent A',
        turn_id: 'turn-step-first',
        step_id: 'step-thinking-first',
        step_type: 'thinking',
        title: 'Thinking',
      });
      onChunk({
        event: 'progress',
        agent_id: 'agent-a',
        agent_name: 'Agent A',
        turn_id: 'turn-step-first',
        content: 'analyzing',
        synthetic_progress: true,
      });

      await new Promise<void>((resolve) => {
        resolveStream = () => {
          onChunk({
            event: 'request_start',
            agent_id: 'agent-a',
            agent_name: 'Agent A',
            turn_id: 'turn-step-first',
            message_id: 'assistant-step-first',
          });
          onChunk({
            event: 'request_end',
            agent_id: 'agent-a',
            agent_name: 'Agent A',
            turn_id: 'turn-step-first',
            message_id: 'assistant-step-first',
            content: 'done',
          });
          onChunk({ event: 'done' });
          resolve();
        };
      });
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
      const streamingAssistant = conversationMessages.find((message) => (
        message.role === 'assistant'
        && message.agentId === 'agent-a'
        && message.isStreaming
      ));
      expect(streamingAssistant?.executionSteps?.some((step) => step.id === 'step-thinking-first')).toBe(true);
    });

    const finishStream = resolveStream as (() => void) | null;
    if (finishStream) {
      finishStream();
    }
  });

  it('keeps execution steps visible when websocket steps arrive before agent_start', async () => {
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
      expect(screen.getByTestId('mock-message-input')).toBeInTheDocument();
    });

    const socket = MockWebSocket.instances[0];
    expect(socket).toBeTruthy();

    act(() => {
      socket.emitMessage({
        session_key: 'web:dm_agent-a',
        event: 'step_start',
        agent_id: 'agent-a',
        agent_name: 'Agent A',
        turn_id: 'turn-ws-step-first',
        step_id: 'step-ws-thinking',
        step_type: 'thinking',
        title: 'Thinking',
      });
      socket.emitMessage({
        session_key: 'web:dm_agent-a',
        event: 'progress',
        agent_id: 'agent-a',
        agent_name: 'Agent A',
        turn_id: 'turn-ws-step-first',
        content: 'analyzing websocket work',
        synthetic_progress: true,
      });
    });

    await waitFor(() => {
      const conversationMessages = useConversationStore.getState().messages['dm_agent-a'] || [];
      const streamingAssistant = conversationMessages.find((message) => (
        message.role === 'assistant'
        && message.agentId === 'agent-a'
        && message.isStreaming
      ));
      expect(streamingAssistant?.executionSteps?.some((step) => step.id === 'step-ws-thinking')).toBe(true);
      expect(streamingAssistant?.content).toBe('analyzing websocket work');
    });
  });

  it('keeps the latest persisted assistant bubble after reconcile falls back from an empty incremental page', async () => {
    const conversationId = 'dm_agent-a';
    const requestId = 'req-reconcile-fallback';
    const turnId = 'turn-reconcile-fallback';
    const persistedAssistantMessage = {
      id: 'history-assistant-final',
      role: 'assistant',
      content: '我已恢复第 7 页。现在读取',
      timestamp: new Date().toISOString(),
      execution_steps: [
        {
          id: 'step-restore',
          type: 'tool_call',
          title: '执行 exec',
          status: 'success',
          timestamp: new Date().toISOString(),
          details: {
            toolName: 'exec',
          },
        },
      ],
      metadata: {
        agent_id: 'agent-a',
        agent_name: 'Agent A',
        turn_id: turnId,
        request_id: requestId,
      },
    };

    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/agents') {
        return Promise.resolve(createJsonResponse({ agents: [internalAgent] }));
      }
      if (url === '/api/external-agents') {
        return Promise.resolve(createJsonResponse({ external_agents: [] }));
      }
      if (url === '/api/teams') {
        return Promise.resolve(createJsonResponse({ teams: [] }));
      }
      if (url === `/api/conversations/${conversationId}/messages?limit=80&after_id=history-assistant-final`) {
        return Promise.resolve(createJsonResponse({
          conversation_id: conversationId,
          messages: [],
          page: {
            oldest_message_id: 'history-user-final',
            newest_message_id: 'history-assistant-final',
            has_more_before: false,
            has_more_after: false,
            total_messages: 2,
          },
        }));
      }
      if (url.startsWith(`/api/conversations/${conversationId}/messages`)) {
        return Promise.resolve(createJsonResponse({
          conversation_id: conversationId,
          conversation: {
            id: conversationId,
            type: ConversationType.DM,
            target_id: 'agent-a',
            name: 'Agent A',
            agent_ids: ['agent-a'],
          },
          messages: [
            {
              id: 'history-user-final',
              role: 'user',
              content: 'hello',
              timestamp: new Date().toISOString(),
              metadata: {
                turn_id: turnId,
                request_id: requestId,
              },
            },
            persistedAssistantMessage,
          ],
          page: {
            oldest_message_id: 'history-user-final',
            newest_message_id: 'history-assistant-final',
            has_more_before: false,
            has_more_after: false,
            total_messages: 2,
          },
        }));
      }
      return Promise.resolve(createJsonResponse({ messages: [] }));
    });

    vi.spyOn(chatService, 'streamChat').mockImplementationOnce(async ({ onStateChange, onRequestStart, onChunk }) => {
      onStateChange?.('connecting');
      onRequestStart?.(requestId);
      onChunk({
        event: 'request_start',
        agent_id: 'agent-a',
        agent_name: 'Agent A',
        turn_id: turnId,
        message_id: 'stream-assistant-final',
      });
      onChunk({
        event: 'step_start',
        agent_id: 'agent-a',
        agent_name: 'Agent A',
        turn_id: turnId,
        message_id: 'stream-assistant-final',
        step_id: 'step-restore',
        step_type: 'tool_call',
        title: '执行 exec',
      });
      onChunk({
        event: 'step_complete',
        agent_id: 'agent-a',
        agent_name: 'Agent A',
        turn_id: turnId,
        message_id: 'stream-assistant-final',
        step_id: 'step-restore',
        step_type: 'tool_call',
        status: 'success',
        details: {
          toolName: 'exec',
        },
      });
      onChunk({
        event: 'request_end',
        agent_id: 'agent-a',
        agent_name: 'Agent A',
        turn_id: turnId,
        message_id: 'stream-assistant-final',
        content: '我已恢复第 7 页。现在读取',
      });
      onChunk({ event: 'done' });
    });

    seedConversationStore({
      id: conversationId,
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
      const conversationMessages = useConversationStore.getState().messages[conversationId] || [];
      const latestAssistant = conversationMessages.find((message) => message.id === 'history-assistant-final');
      expect(latestAssistant?.content).toBe('我已恢复第 7 页。现在读取');
      expect(latestAssistant?.executionSteps?.[0]?.id).toBe('step-restore');
    });
  });

  it('renders confirmation-required stream events as actionable message state', async () => {
    const conversationId = 'dm_agent-a';
    vi.spyOn(chatService, 'streamChat').mockImplementationOnce(async ({ onStateChange, onRequestStart, onChunk }) => {
      onStateChange?.('connecting');
      onRequestStart?.('req-confirm');
      onChunk({
        event: 'request_start',
        agent_id: 'agent-a',
        agent_name: 'Agent A',
        turn_id: 'turn-confirm',
        message_id: 'assistant-confirm',
      });
      onChunk({
        event: 'confirmation_required',
        agent_id: 'agent-a',
        agent_name: 'Agent A',
        turn_id: 'turn-confirm',
        message_id: 'assistant-confirm',
        content: '需要确认后执行命令。',
        confirmation_id: 'conf-1234',
        tool_name: 'exec',
        tool_arguments: { command: 'python3 script.py' },
      });
      onChunk({ event: 'done' });
    });

    seedConversationStore({
      id: conversationId,
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
      const conversationMessages = useConversationStore.getState().messages[conversationId] || [];
      const confirmationMessage = conversationMessages.find((message) => message.confirmationId === 'conf-1234');
      expect(confirmationMessage?.confirmationId).toBe('conf-1234');
      expect(confirmationMessage?.toolName).toBe('exec');
      expect(confirmationMessage?.toolArguments).toEqual({ command: 'python3 script.py' });
      expect(confirmationMessage?.isStreaming).toBe(false);
    });
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
      if (url.startsWith(`/api/conversations/${conversationId}/messages`)) {
        return Promise.resolve(createJsonResponse({
          conversation_id: conversationId,
          conversation: {
            id: conversationId,
            type: ConversationType.DM,
            target_id: 'agent-a',
            name: 'Agent A',
            agent_ids: ['agent-a'],
          },
          messages: largeTurnMessages,
          page: {
            oldest_message_id: 'user-0',
            newest_message_id: 'assistant-17',
            has_more_before: false,
            has_more_after: false,
            total_messages: largeTurnMessages.length,
          },
        }));
      }
      return Promise.resolve(createJsonResponse({ messages: [] }));
    });

    seedConversationStore({
      id: conversationId,
      type: ConversationType.DM,
      targetId: 'agent-a',
      name: 'Agent A',
      agentIds: ['agent-a'],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    renderWithProviders(<ChatPage />);

    await waitFor(() => {
      expect(screen.getByTestId('chat-conversation-health')).toBeInTheDocument();
    });

    expect(screen.getByText('Oversized context')).toBeInTheDocument();
    expect(screen.getByText(/Approx .* tokens .* turns/)).toBeInTheDocument();
  });

  it('queries the server-side full-history search when the loaded window is partial', async () => {
    const conversationId = 'dm_agent-a';

    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/agents') {
        return Promise.resolve(createJsonResponse({ agents: [internalAgent] }));
      }
      if (url === '/api/external-agents') {
        return Promise.resolve(createJsonResponse({ external_agents: [] }));
      }
      if (url === '/api/teams') {
        return Promise.resolve(createJsonResponse({ teams: [] }));
      }
      if (url.startsWith(`/api/conversations/${conversationId}/messages`)) {
        return Promise.resolve(createJsonResponse({
          conversation_id: conversationId,
          conversation: {
            id: conversationId,
            type: ConversationType.DM,
            target_id: 'agent-a',
            name: 'Agent A',
            agent_ids: ['agent-a'],
          },
          messages: [
            {
              id: 'recent-user',
              role: 'user',
              content: 'recent question',
              timestamp: new Date().toISOString(),
            },
            {
              id: 'recent-assistant',
              role: 'assistant',
              content: 'recent answer',
              timestamp: new Date().toISOString(),
              metadata: {
                agent_id: 'agent-a',
                agent_name: 'Agent A',
                turn_id: 'turn-recent',
                request_id: 'req-recent',
              },
            },
          ],
          page: {
            oldest_message_id: 'recent-user',
            newest_message_id: 'recent-assistant',
            has_more_before: true,
            has_more_after: false,
            total_messages: 120,
          },
        }));
      }
      if (url.startsWith(`/api/conversations/${conversationId}/search`)) {
        if (url.includes('offset=20')) {
          return Promise.resolve(createJsonResponse({
            conversation_id: conversationId,
            matches: [
              {
                message_id: 'older-assistant-2',
                role: 'assistant',
                preview: 'legacy needle result page 2',
                agent_id: 'agent-a',
                agent_name: 'Agent A',
                timestamp: new Date().toISOString(),
              },
            ],
            total_matches: 2,
            has_more: false,
            next_offset: null,
          }));
        }
        return Promise.resolve(createJsonResponse({
          conversation_id: conversationId,
          matches: [
            {
              message_id: 'older-assistant-1',
              role: 'assistant',
              preview: 'legacy needle result page 1',
              agent_id: 'agent-a',
              agent_name: 'Agent A',
              timestamp: new Date().toISOString(),
            },
          ],
          total_matches: 2,
          has_more: true,
          next_offset: 20,
        }));
      }
      return Promise.resolve(createJsonResponse({ messages: [] }));
    });

    seedConversationStore({
      id: conversationId,
      type: ConversationType.DM,
      targetId: 'agent-a',
      name: 'Agent A',
      agentIds: ['agent-a'],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    renderWithProviders(<ChatPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Search History' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Search History' }));
    const historySearchInput = await screen.findByPlaceholderText('Type keywords to quickly locate messages');
    fireEvent.change(historySearchInput, {
      target: { value: 'legacy needle' },
    });

    await waitFor(() => {
      expect(vi.mocked(fetch).mock.calls.some(([request]) => {
        const url = String(request);
        return url.startsWith(`/api/conversations/${conversationId}/search`)
          && url.includes('q=legacy+needle')
          && url.includes('limit=20');
      })).toBe(true);
    });

    fireEvent.click(screen.getByRole('button', { name: 'Last 7 days' }));

    await waitFor(() => {
      expect(vi.mocked(fetch).mock.calls.some(([request]) => {
        const url = String(request);
        return url.startsWith(`/api/conversations/${conversationId}/search`)
          && url.includes('q=legacy+needle')
          && url.includes('since=');
      })).toBe(true);
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Load more full-history results' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Load more full-history results' }));

    await waitFor(() => {
      expect(vi.mocked(fetch).mock.calls.some(([request]) => {
        const url = String(request);
        return url.startsWith(`/api/conversations/${conversationId}/search`)
          && url.includes('offset=20');
      })).toBe(true);
    });
  });

  it('loads around the selected full-history result and jumps to it', async () => {
    const conversationId = 'dm_agent-a';
    const scrollIntoViewMock = vi.spyOn(HTMLElement.prototype, 'scrollIntoView');

    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/agents') {
        return Promise.resolve(createJsonResponse({ agents: [internalAgent] }));
      }
      if (url === '/api/external-agents') {
        return Promise.resolve(createJsonResponse({ external_agents: [] }));
      }
      if (url === '/api/teams') {
        return Promise.resolve(createJsonResponse({ teams: [] }));
      }
      if (url.includes('around_id=old-assistant')) {
        return Promise.resolve(createJsonResponse({
          conversation_id: conversationId,
          conversation: {
            id: conversationId,
            type: ConversationType.DM,
            target_id: 'agent-a',
            name: 'Agent A',
            agent_ids: ['agent-a'],
          },
          messages: [
            {
              id: 'old-user',
              role: 'user',
              content: 'Where is the legacy note?',
              timestamp: new Date(Date.now() - 60_000).toISOString(),
            },
            {
              id: 'old-assistant',
              role: 'assistant',
              content: 'legacy keyword answer',
              timestamp: new Date(Date.now() - 59_000).toISOString(),
              metadata: {
                agent_id: 'agent-a',
                agent_name: 'Agent A',
                turn_id: 'turn-legacy',
                request_id: 'req-legacy',
              },
            },
          ],
          page: {
            oldest_message_id: 'old-user',
            newest_message_id: 'old-assistant',
            has_more_before: true,
            has_more_after: true,
            total_messages: 120,
          },
        }));
      }
      if (url.startsWith(`/api/conversations/${conversationId}/messages`)) {
        return Promise.resolve(createJsonResponse({
          conversation_id: conversationId,
          conversation: {
            id: conversationId,
            type: ConversationType.DM,
            target_id: 'agent-a',
            name: 'Agent A',
            agent_ids: ['agent-a'],
          },
          messages: [
            {
              id: 'recent-user',
              role: 'user',
              content: 'recent question',
              timestamp: new Date().toISOString(),
            },
            {
              id: 'recent-assistant',
              role: 'assistant',
              content: 'recent answer',
              timestamp: new Date().toISOString(),
              metadata: {
                agent_id: 'agent-a',
                agent_name: 'Agent A',
                turn_id: 'turn-recent',
                request_id: 'req-recent',
              },
            },
          ],
          page: {
            oldest_message_id: 'recent-user',
            newest_message_id: 'recent-assistant',
            has_more_before: true,
            has_more_after: false,
            total_messages: 120,
          },
        }));
      }
      if (url.startsWith(`/api/conversations/${conversationId}/search`)) {
        return Promise.resolve(createJsonResponse({
          conversation_id: conversationId,
          matches: [
            {
              message_id: 'old-assistant',
              role: 'assistant',
              preview: 'legacy keyword answer',
              agent_id: 'agent-a',
              agent_name: 'Agent A',
              timestamp: new Date(Date.now() - 59_000).toISOString(),
            },
          ],
          total_matches: 1,
        }));
      }
      return Promise.resolve(createJsonResponse({ messages: [] }));
    });

    seedConversationStore({
      id: conversationId,
      type: ConversationType.DM,
      targetId: 'agent-a',
      name: 'Agent A',
      agentIds: ['agent-a'],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    renderWithProviders(<ChatPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Search History' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Search History' }));
    const historySearchInput = await screen.findByPlaceholderText('Type keywords to quickly locate messages');
    fireEvent.change(historySearchInput, {
      target: { value: 'legacy' },
    });

    await waitFor(() => {
      expect(screen.getByText('legacy keyword answer')).toBeInTheDocument();
    });

    const previousScrollCalls = scrollIntoViewMock.mock.calls.length;
    fireEvent.click(screen.getByText('legacy keyword answer'));

    await waitFor(() => {
      expect(vi.mocked(fetch).mock.calls.some(([request]) => {
        const url = String(request);
        return url.startsWith(`/api/conversations/${conversationId}/messages`)
          && url.includes('around_id=old-assistant')
          && url.includes('context_before=20')
          && url.includes('context_after=20');
      })).toBe(true);
    });

    await waitFor(() => {
      const conversationMessages = useConversationStore.getState().messages[conversationId] || [];
      expect(conversationMessages.some((message) => message.id === 'old-assistant')).toBe(true);
    });

    await waitFor(() => {
      expect(scrollIntoViewMock.mock.calls.length).toBeGreaterThan(previousScrollCalls);
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Back to latest messages' })).toBeInTheDocument();
    });

    const latestFetchCountBeforeJump = vi.mocked(fetch).mock.calls.filter(([request]) => {
      const url = String(request);
      return url.startsWith(`/api/conversations/${conversationId}/messages`)
        && !url.includes('around_id=')
        && !url.includes('before_id=')
        && !url.includes('after_id=');
    }).length;

    fireEvent.click(screen.getByRole('button', { name: 'Back to latest messages' }));

    await waitFor(() => {
      const latestFetchCount = vi.mocked(fetch).mock.calls.filter(([request]) => {
        const url = String(request);
        return url.startsWith(`/api/conversations/${conversationId}/messages`)
          && !url.includes('around_id=')
          && !url.includes('before_id=')
          && !url.includes('after_id=');
      }).length;
      expect(latestFetchCount).toBeGreaterThan(latestFetchCountBeforeJump);
    });

    await waitFor(() => {
      const conversationMessages = useConversationStore.getState().messages[conversationId] || [];
      expect(conversationMessages.some((message) => message.id === 'recent-assistant')).toBe(true);
    });
  });

  it('refreshes back to the latest history window when a partial window receives newer chat activity', async () => {
    const conversationId = 'dm_agent-a';
    let latestWindowRequestCount = 0;

    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/agents') {
        return Promise.resolve(createJsonResponse({ agents: [internalAgent] }));
      }
      if (url === '/api/external-agents') {
        return Promise.resolve(createJsonResponse({ external_agents: [] }));
      }
      if (url === '/api/teams') {
        return Promise.resolve(createJsonResponse({ teams: [] }));
      }
      if (url.startsWith(`/api/conversations/${conversationId}/messages`)) {
        if (url.includes('after_id=old-assistant')) {
          return Promise.resolve(createJsonResponse({
            conversation_id: conversationId,
            conversation: {
              id: conversationId,
              type: ConversationType.DM,
              target_id: 'agent-a',
              name: 'Agent A',
              agent_ids: ['agent-a'],
            },
            messages: [
              {
                id: 'mid-user',
                role: 'user',
                content: 'middle history question',
                timestamp: new Date(Date.now() - 15_000).toISOString(),
              },
              {
                id: 'mid-assistant',
                role: 'assistant',
                content: 'middle history answer',
                timestamp: new Date(Date.now() - 14_000).toISOString(),
                metadata: {
                  agent_id: 'agent-a',
                  agent_name: 'Agent A',
                },
              },
            ],
            page: {
              oldest_message_id: 'old-user',
              newest_message_id: 'mid-assistant',
              has_more_before: true,
              has_more_after: true,
              total_messages: 140,
            },
          }));
        }

        latestWindowRequestCount += 1;
        if (latestWindowRequestCount === 1) {
          return Promise.resolve(createJsonResponse({
            conversation_id: conversationId,
            conversation: {
              id: conversationId,
              type: ConversationType.DM,
              target_id: 'agent-a',
              name: 'Agent A',
              agent_ids: ['agent-a'],
            },
            messages: [
              {
                id: 'old-user',
                role: 'user',
                content: 'old history question',
                timestamp: new Date(Date.now() - 90_000).toISOString(),
              },
              {
                id: 'old-assistant',
                role: 'assistant',
                content: 'old history answer',
                timestamp: new Date(Date.now() - 89_000).toISOString(),
                metadata: {
                  agent_id: 'agent-a',
                  agent_name: 'Agent A',
                  turn_id: 'turn-old',
                  request_id: 'req-old',
                },
              },
            ],
            page: {
              oldest_message_id: 'old-user',
              newest_message_id: 'old-assistant',
              has_more_before: true,
              has_more_after: true,
              total_messages: 140,
            },
          }));
        }

        return Promise.resolve(createJsonResponse({
          conversation_id: conversationId,
          conversation: {
            id: conversationId,
            type: ConversationType.DM,
            target_id: 'agent-a',
            name: 'Agent A',
            agent_ids: ['agent-a'],
          },
          messages: [
            {
              id: 'recent-user',
              role: 'user',
              content: 'recent question',
              timestamp: new Date(Date.now() - 2_000).toISOString(),
            },
            {
              id: 'recent-assistant',
              role: 'assistant',
              content: 'recent answer',
              timestamp: new Date(Date.now() - 1_000).toISOString(),
              metadata: {
                agent_id: 'agent-a',
                agent_name: 'Agent A',
                turn_id: 'turn-recent',
                request_id: 'req-recent',
              },
            },
          ],
          page: {
            oldest_message_id: 'recent-user',
            newest_message_id: 'recent-assistant',
            has_more_before: true,
            has_more_after: false,
            total_messages: 142,
          },
        }));
      }
      return Promise.resolve(createJsonResponse({ messages: [] }));
    });

    seedConversationStore({
      id: conversationId,
      type: ConversationType.DM,
      targetId: 'agent-a',
      name: 'Agent A',
      agentIds: ['agent-a'],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    renderWithProviders(<ChatPage />);

    await waitFor(() => {
      const conversationMessages = useConversationStore.getState().messages[conversationId] || [];
      expect(conversationMessages.some((message) => message.id === 'old-assistant')).toBe(true);
    });

    const socket = MockWebSocket.instances[0];
    expect(socket).toBeTruthy();

    act(() => {
      socket.emitMessage({
        session_key: 'web:dm_agent-a',
        event: 'request_end',
        agent_id: 'agent-a',
        agent_name: 'Agent A',
        turn_id: 'turn-live',
        message_id: 'assistant-live',
        content: 'live answer',
      });
    });

    await waitFor(() => {
      const conversationMessages = useConversationStore.getState().messages[conversationId] || [];
      expect(conversationMessages.some((message) => message.id === 'recent-assistant')).toBe(true);
    });

    expect(vi.mocked(fetch).mock.calls.some(([request]) => {
      const url = String(request);
      return url.startsWith(`/api/conversations/${conversationId}/messages`)
        && url.includes('after_id=old-assistant');
    })).toBe(false);
  });

  it('queues a forced latest refresh instead of reusing an in-flight stale history request', async () => {
    const conversationId = 'dm_agent-a';
    let resolveInitialHistory: (() => void) | null = null;
    let historyRequestCount = 0;

    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/agents') {
        return Promise.resolve(createJsonResponse({ agents: [internalAgent] }));
      }
      if (url === '/api/external-agents') {
        return Promise.resolve(createJsonResponse({ external_agents: [] }));
      }
      if (url === '/api/teams') {
        return Promise.resolve(createJsonResponse({ teams: [] }));
      }
      if (url.startsWith(`/api/conversations/${conversationId}/messages`)) {
        historyRequestCount += 1;
        if (historyRequestCount === 1) {
          return new Promise<Response>((resolve) => {
            resolveInitialHistory = () => resolve(createJsonResponse({
              conversation_id: conversationId,
              messages: [
                {
                  id: 'stale-assistant',
                  role: 'assistant',
                  content: 'stale history answer',
                  timestamp: new Date(Date.now() - 60_000).toISOString(),
                  metadata: {
                    agent_id: 'agent-a',
                    agent_name: 'Agent A',
                  },
                },
              ],
              page: {
                oldest_message_id: 'stale-assistant',
                newest_message_id: 'stale-assistant',
                has_more_before: true,
                has_more_after: true,
                total_messages: 120,
              },
            }));
          });
        }

        return Promise.resolve(createJsonResponse({
          conversation_id: conversationId,
          messages: [
            {
              id: 'latest-assistant',
              role: 'assistant',
              content: 'latest history answer',
              timestamp: new Date().toISOString(),
              metadata: {
                agent_id: 'agent-a',
                agent_name: 'Agent A',
              },
            },
          ],
          page: {
            oldest_message_id: 'latest-assistant',
            newest_message_id: 'latest-assistant',
            has_more_before: true,
            has_more_after: false,
            total_messages: 121,
          },
        }));
      }
      return Promise.resolve(createJsonResponse({ messages: [] }));
    });

    seedConversationStore({
      id: conversationId,
      type: ConversationType.DM,
      targetId: 'agent-a',
      name: 'Agent A',
      agentIds: ['agent-a'],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    renderWithProviders(<ChatPage />);

    await waitFor(() => {
      expect(historyRequestCount).toBe(1);
    });

    const agentButton = screen.getAllByRole('button').find((button) => (
      button.textContent?.includes('Agent A')
    ));
    expect(agentButton).toBeTruthy();
    fireEvent.click(agentButton as HTMLButtonElement);

    act(() => {
      resolveInitialHistory?.();
    });

    await waitFor(() => {
      expect(historyRequestCount).toBeGreaterThan(1);
    });

    await waitFor(() => {
      const conversationMessages = useConversationStore.getState().messages[conversationId] || [];
      expect(conversationMessages.some((message) => message.id === 'latest-assistant')).toBe(true);
    });
  });

  it('creates and selects a task workspace from the task context strip', async () => {
    const conversationId = 'dm_agent-a';
    const createdTask = {
      id: 'tw_test',
      title: 'Create launch deck',
      agent_id: 'agent-a',
      conversation_id: conversationId,
      session_key: 'web:dm_agent-a',
      status: 'ready',
      cwd: '/tmp/horbot/task-workspaces/dm_agent-a',
      workspace_mode: 'conversation',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      metadata: { source: 'test' },
    };

    vi.mocked(taskWorkspacesService.create).mockResolvedValue(createdTask);
    vi.mocked(taskWorkspacesService.update).mockResolvedValue({
      ...createdTask,
      status: 'done',
      updated_at: new Date().toISOString(),
    });
    vi.mocked(taskWorkspacesService.listFiles).mockResolvedValue({
      task_id: 'tw_test',
      cwd: createdTask.cwd,
      exists: true,
      files: [
        {
          path: 'outline.md',
          name: 'outline.md',
          kind: 'file',
          size: 128,
          modified_at: new Date().toISOString(),
        },
      ],
      truncated: false,
    });
    vi.mocked(taskWorkspacesService.listChanges).mockResolvedValue({
      task_id: 'tw_test',
      cwd: createdTask.cwd,
      available: true,
      reason: null,
      changes: [
        {
          status: 'M',
          path: 'outline.md',
          summary: 'M outline.md',
        },
      ],
      truncated: false,
    });

    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/agents') {
        return Promise.resolve(createJsonResponse({ agents: [internalAgent] }));
      }
      if (url === '/api/external-agents') {
        return Promise.resolve(createJsonResponse({ external_agents: [] }));
      }
      if (url === '/api/teams') {
        return Promise.resolve(createJsonResponse({ teams: [] }));
      }
      if (url.startsWith(`/api/conversations/${conversationId}/messages`)) {
        return Promise.resolve(createJsonResponse({
          conversation_id: conversationId,
          conversation: {
            id: conversationId,
            type: ConversationType.DM,
            target_id: 'agent-a',
            name: 'Agent A',
            agent_ids: ['agent-a'],
          },
          messages: [
            {
              id: 'user-1',
              role: 'user',
              content: 'Create launch deck',
              timestamp: new Date().toISOString(),
            },
          ],
        }));
      }
      return Promise.resolve(createJsonResponse({ messages: [] }));
    });

    seedConversationStore({
      id: conversationId,
      type: ConversationType.DM,
      targetId: 'agent-a',
      name: 'Agent A',
      agentIds: ['agent-a'],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    renderWithProviders(<ChatPage />);

    await waitFor(() => {
      expect(screen.getByText(/新建任务|New task/)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/新建任务|New task/));

    await waitFor(() => {
      expect(screen.getByTestId('chat-task-inspector')).toBeInTheDocument();
      expect(screen.getByText(/任务列表|Task list/)).toBeInTheDocument();
      expect(screen.getAllByText('Create launch deck').length).toBeGreaterThan(0);
      expect(screen.getAllByText('/tmp/horbot/task-workspaces/dm_agent-a').length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getByText(/变更|Changes/));

    await waitFor(() => {
      expect(screen.getByText('outline.md')).toBeInTheDocument();
      expect(screen.getByText('M outline.md')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/标记完成|Mark done/));

    await waitFor(() => {
      expect(taskWorkspacesService.update).toHaveBeenCalledWith('tw_test', { status: 'done' });
    });

    expect(taskWorkspacesService.create).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Create launch deck',
      agent_id: 'agent-a',
      conversation_id: conversationId,
      session_key: 'web:dm_agent-a',
      workspace_mode: 'conversation',
    }));
  });

  it('passes the selected task workspace context when sending chat', async () => {
    const conversationId = 'dm_agent-a';
    const selectedTask = {
      id: 'tw_selected',
      title: 'Selected task',
      agent_id: 'agent-a',
      conversation_id: conversationId,
      session_key: 'web:dm_agent-a',
      status: 'ready',
      cwd: '/tmp/horbot/task-workspaces/selected',
      workspace_mode: 'conversation',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      metadata: {},
    };
    const streamChatMock = vi.spyOn(chatService, 'streamChat').mockImplementation(async ({ onStateChange, onRequestStart, onChunk }) => {
      onStateChange?.('connecting');
      onRequestStart?.('req-task-context');
      onChunk({
        event: 'request_start',
        agent_id: 'agent-a',
        agent_name: 'Agent A',
        turn_id: 'turn-task-context',
        message_id: 'assistant-task-context',
      });
      onChunk({
        event: 'request_end',
        agent_id: 'agent-a',
        agent_name: 'Agent A',
        turn_id: 'turn-task-context',
        message_id: 'assistant-task-context',
        content: 'done',
      });
      onChunk({ event: 'done' });
    });

    vi.mocked(taskWorkspacesService.list).mockResolvedValue([selectedTask]);
    vi.mocked(taskWorkspacesService.listFiles).mockResolvedValue({
      task_id: selectedTask.id,
      cwd: selectedTask.cwd,
      exists: true,
      files: [],
      truncated: false,
    });
    vi.mocked(taskWorkspacesService.listChanges).mockResolvedValue({
      task_id: selectedTask.id,
      cwd: selectedTask.cwd,
      available: true,
      reason: null,
      changes: [],
      truncated: false,
    });

    seedConversationStore({
      id: conversationId,
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
      expect(taskWorkspacesService.list).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByTestId('mock-send-button'));

    await waitFor(() => {
      expect(streamChatMock).toHaveBeenCalled();
    });

    expect(streamChatMock.mock.calls.at(-1)?.[0]).toEqual(expect.objectContaining({
      taskWorkspaceId: 'tw_selected',
      taskWorkspaceCwd: '/tmp/horbot/task-workspaces/selected',
    }));

    const conversationMessages = useConversationStore.getState().messages[conversationId] || [];
    const userMessage = conversationMessages.find((message) => message.role === 'user' && message.content === 'hello');
    expect(userMessage?.metadata).toEqual(expect.objectContaining({
      task_workspace_id: 'tw_selected',
      task_workspace_cwd: '/tmp/horbot/task-workspaces/selected',
    }));
  });
});
