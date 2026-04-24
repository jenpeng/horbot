import { fireEvent, render, screen, within } from '@testing-library/react';
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

  it('shows a direct processing bubble when a streaming assistant has status but no content', () => {
    renderWithProviders({
      id: 'msg-streaming-direct',
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      isStreaming: true,
      statusMessage: 'Streaming',
    });

    expect(screen.getByTestId('message-streaming-status-bubble')).toBeInTheDocument();
    expect(screen.getByText('Streaming')).toBeInTheDocument();
    expect(screen.queryByText('Team relay')).not.toBeInTheDocument();
  });

  it('detaches image attachments into a compact bubble when message also has text', () => {
    renderWithProviders({
      id: 'msg-2',
      role: 'assistant',
      content: '这里是配图说明文字。',
      timestamp: new Date().toISOString(),
      files: [
        {
          fileId: 'file-1',
          filename: 'pony-neon-rain.jpg',
          originalName: 'pony-neon-rain.jpg',
          mimeType: 'image/jpeg',
          size: 108544,
          category: 'image',
          url: '/uploads/pony-neon-rain.jpg',
          previewUrl: '/uploads/pony-neon-rain.jpg',
        },
      ],
    });

    expect(screen.getByTestId('message-detached-image-bubble')).toBeInTheDocument();
    expect(screen.getByTestId('message-file-open-preview')).toBeInTheDocument();
    expect(screen.getByText('这里是配图说明文字。')).toBeInTheDocument();
  });

  it('renders multiple images in a compact grid', () => {
    renderWithProviders({
      id: 'msg-3',
      role: 'assistant',
      content: '这是多图结果。',
      timestamp: new Date().toISOString(),
      files: [
        {
          fileId: 'file-1',
          filename: 'a.jpg',
          originalName: 'a.jpg',
          mimeType: 'image/jpeg',
          size: 120000,
          category: 'image',
          url: '/uploads/a.jpg',
          previewUrl: '/uploads/a.jpg',
        },
        {
          fileId: 'file-2',
          filename: 'b.jpg',
          originalName: 'b.jpg',
          mimeType: 'image/jpeg',
          size: 130000,
          category: 'image',
          url: '/uploads/b.jpg',
          previewUrl: '/uploads/b.jpg',
        },
      ],
    });

    expect(screen.getByTestId('message-detached-image-bubble')).toBeInTheDocument();
    expect(screen.getByTestId('message-file-image-grid')).toBeInTheDocument();
    expect(screen.getAllByTestId('message-file-open-preview')).toHaveLength(2);
  });

  it('collapses more than four images into a 2x2 grid with overflow badge', () => {
    renderWithProviders({
      id: 'msg-4',
      role: 'assistant',
      content: '这是五张图。',
      timestamp: new Date().toISOString(),
      files: [
        {
          fileId: 'file-1',
          filename: 'a-very-long-image-name-01.jpg',
          originalName: 'a-very-long-image-name-01.jpg',
          mimeType: 'image/jpeg',
          size: 120000,
          category: 'image',
          url: '/uploads/a1.jpg',
          previewUrl: '/uploads/a1.jpg',
        },
        {
          fileId: 'file-2',
          filename: 'a-very-long-image-name-02.jpg',
          originalName: 'a-very-long-image-name-02.jpg',
          mimeType: 'image/jpeg',
          size: 120000,
          category: 'image',
          url: '/uploads/a2.jpg',
          previewUrl: '/uploads/a2.jpg',
        },
        {
          fileId: 'file-3',
          filename: 'a-very-long-image-name-03.jpg',
          originalName: 'a-very-long-image-name-03.jpg',
          mimeType: 'image/jpeg',
          size: 120000,
          category: 'image',
          url: '/uploads/a3.jpg',
          previewUrl: '/uploads/a3.jpg',
        },
        {
          fileId: 'file-4',
          filename: 'a-very-long-image-name-04.jpg',
          originalName: 'a-very-long-image-name-04.jpg',
          mimeType: 'image/jpeg',
          size: 120000,
          category: 'image',
          url: '/uploads/a4.jpg',
          previewUrl: '/uploads/a4.jpg',
        },
        {
          fileId: 'file-5',
          filename: 'a-very-long-image-name-05.jpg',
          originalName: 'a-very-long-image-name-05.jpg',
          mimeType: 'image/jpeg',
          size: 120000,
          category: 'image',
          url: '/uploads/a5.jpg',
          previewUrl: '/uploads/a5.jpg',
        },
      ],
    });

    expect(screen.getByTestId('message-file-image-grid')).toBeInTheDocument();
    expect(screen.getAllByTestId('message-file-open-preview')).toHaveLength(4);
    expect(screen.getByTestId('message-file-image-overflow')).toHaveTextContent('+1');
  });

  it('supports previous and next navigation in image preview modal', () => {
    renderWithProviders({
      id: 'msg-5',
      role: 'assistant',
      content: '这是可切换预览。',
      timestamp: new Date().toISOString(),
      files: [
        {
          fileId: 'file-1',
          filename: 'first.jpg',
          originalName: 'first.jpg',
          mimeType: 'image/jpeg',
          size: 120000,
          category: 'image',
          url: '/uploads/first.jpg',
          previewUrl: '/uploads/first.jpg',
        },
        {
          fileId: 'file-2',
          filename: 'second.jpg',
          originalName: 'second.jpg',
          mimeType: 'image/jpeg',
          size: 130000,
          category: 'image',
          url: '/uploads/second.jpg',
          previewUrl: '/uploads/second.jpg',
        },
      ],
    });

    fireEvent.click(screen.getAllByTestId('message-file-open-preview')[0]);
    const previewModal = screen.getByTestId('message-file-preview-modal');
    expect(previewModal).toBeInTheDocument();
    expect(within(previewModal).getByText('1 / 2')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'first.jpg' })).toBeInTheDocument();

    fireEvent.click(within(previewModal).getByTestId('message-file-preview-next'));
    expect(screen.getByRole('heading', { name: 'second.jpg' })).toBeInTheDocument();
    expect(within(previewModal).getByText('2 / 2')).toBeInTheDocument();

    fireEvent.click(within(previewModal).getByTestId('message-file-preview-prev'));
    expect(screen.getByRole('heading', { name: 'first.jpg' })).toBeInTheDocument();
  });

  it('renders a thumbnail strip in the preview modal for multi-image messages', () => {
    renderWithProviders({
      id: 'msg-6',
      role: 'assistant',
      content: '这是多图缩略条。',
      timestamp: new Date().toISOString(),
      files: [
        {
          fileId: 'file-1',
          filename: 'first.jpg',
          originalName: 'first.jpg',
          mimeType: 'image/jpeg',
          size: 120000,
          category: 'image',
          url: '/uploads/first.jpg',
          previewUrl: '/uploads/first.jpg',
        },
        {
          fileId: 'file-2',
          filename: 'second.jpg',
          originalName: 'second.jpg',
          mimeType: 'image/jpeg',
          size: 130000,
          category: 'image',
          url: '/uploads/second.jpg',
          previewUrl: '/uploads/second.jpg',
        },
        {
          fileId: 'file-3',
          filename: 'third.jpg',
          originalName: 'third.jpg',
          mimeType: 'image/jpeg',
          size: 140000,
          category: 'image',
          url: '/uploads/third.jpg',
          previewUrl: '/uploads/third.jpg',
        },
      ],
    });

    fireEvent.click(screen.getAllByTestId('message-file-open-preview')[0]);
    const previewModal = screen.getByTestId('message-file-preview-modal');
    expect(within(previewModal).getByTestId('message-file-preview-thumbnails')).toBeInTheDocument();

    const thumbnails = within(previewModal).getAllByTestId('message-file-preview-thumbnail');
    expect(thumbnails).toHaveLength(3);
    expect(thumbnails[0]).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(thumbnails[1]);
    expect(screen.getByRole('heading', { name: 'second.jpg' })).toBeInTheDocument();
    expect(within(previewModal).getByText('2 / 3')).toBeInTheDocument();
    expect(thumbnails[1]).toHaveAttribute('aria-pressed', 'true');
  });

  it('renders PDF attachments inside the preview modal instead of relying on a new tab', () => {
    const { container } = renderWithProviders({
      id: 'msg-7',
      role: 'assistant',
      content: '这是 PDF 预览。',
      timestamp: new Date().toISOString(),
      files: [
        {
          fileId: 'file-pdf',
          filename: 'report.pdf',
          originalName: 'report.pdf',
          mimeType: 'application/pdf',
          size: 245760,
          category: 'document',
          url: '/api/files/file-pdf',
        },
      ],
    });

    fireEvent.click(screen.getByTestId('message-file-open-preview'));
    const previewModal = screen.getByTestId('message-file-preview-modal');
    const iframe = container.querySelector('iframe[src^="/api/files/file-pdf/preview?v="]');

    expect(previewModal).toBeInTheDocument();
    expect(iframe).toBeInTheDocument();
  });

  it('renders Word attachments in the preview modal with the inline preview endpoint', () => {
    const { container } = renderWithProviders({
      id: 'msg-8',
      role: 'assistant',
      content: '这是 Word 预览。',
      timestamp: new Date().toISOString(),
      files: [
        {
          fileId: 'file-docx',
          filename: 'proposal.docx',
          originalName: 'proposal.docx',
          mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          size: 163840,
          category: 'document',
          url: '/api/files/file-docx',
          extractedText: 'fallback text should not be the main preview path',
        },
      ],
    });

    fireEvent.click(screen.getByTestId('message-file-open-preview'));
    const previewModal = screen.getByTestId('message-file-preview-modal');
    const iframe = container.querySelector('iframe[src^="/api/files/file-docx/preview?v="]');

    expect(previewModal).toBeInTheDocument();
    expect(iframe).toBeInTheDocument();
  });

  it('renders PowerPoint attachments in the preview modal with the inline preview endpoint', () => {
    const { container } = renderWithProviders({
      id: 'msg-9',
      role: 'assistant',
      content: '这是 PowerPoint 预览。',
      timestamp: new Date().toISOString(),
      files: [
        {
          fileId: 'file-pptx',
          filename: 'deck.pptx',
          originalName: 'deck.pptx',
          mimeType: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
          size: 524288,
          category: 'document',
          url: '/api/files/file-pptx',
        },
      ],
    });

    fireEvent.click(screen.getByTestId('message-file-open-preview'));
    const previewModal = screen.getByTestId('message-file-preview-modal');
    const iframe = container.querySelector('iframe[src^="/api/files/file-pptx/preview?v="]');

    expect(previewModal).toBeInTheDocument();
    expect(iframe).toBeInTheDocument();
  });
});
