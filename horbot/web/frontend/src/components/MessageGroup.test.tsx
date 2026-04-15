import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import MessageGroup from './MessageGroup';
import { I18nProvider } from '../contexts/I18nContext';
import { ToastProvider } from '../contexts/ToastContext';
import type { Message } from '../types/conversation';

vi.mock('./MarkdownRenderer', () => ({
  default: ({ content }: { content: string }) => <div>{content}</div>,
}));

const renderWithProviders = (message: Message) => render(
  <MemoryRouter>
    <ToastProvider>
      <I18nProvider>
        <MessageGroup
          messages={[message]}
          agentName="Agent A"
          isUser={false}
          formatTime={() => '10:00'}
        />
      </I18nProvider>
    </ToastProvider>
  </MemoryRouter>,
);

describe('MessageGroup', () => {
  it('shows provider diagnostics for assistant error messages', () => {
    renderWithProviders({
      id: 'msg-1',
      role: 'assistant',
      content: '模型服务响应超时，请稍后重试。',
      requestId: 'req-timeout-1',
      timestamp: new Date().toISOString(),
      isError: true,
      errorKind: 'provider',
      metadata: {
        request_id: 'req-timeout-1',
        _provider_error: {
          error_code: 'PROVIDER_TIMEOUT',
          error_kind: 'timeout',
          provider: 'openrouter',
          model: 'gpt-4.1',
          status_code: 504,
          remediation: ['先重试一次。'],
        },
      },
    });

    expect(screen.getByTestId('message-provider-diagnostics')).toBeInTheDocument();
    expect(screen.getByText('req-timeout-1')).toBeInTheDocument();
    expect(screen.getByText('PROVIDER_TIMEOUT')).toBeInTheDocument();
    expect(screen.getByText('timeout')).toBeInTheDocument();
    expect(screen.getByText('openrouter')).toBeInTheDocument();
    expect(screen.getByText('gpt-4.1')).toBeInTheDocument();
    expect(screen.getByText('504')).toBeInTheDocument();
  });
});
