import { resolveApiBase } from '../../services/api';
import type { UploadedFile } from '../../services/chat';
import type { MessageFile } from '../../types/conversation';

export const toAbsoluteApiUrl = (value?: string): string | undefined => {
  if (!value) {
    return undefined;
  }
  if (/^https?:\/\//i.test(value)) {
    return value;
  }
  const apiBase = resolveApiBase();
  if (!apiBase) {
    return value;
  }
  return `${apiBase}${value.startsWith('/') ? value : `/${value}`}`;
};

export const normalizeMessageFile = (value: unknown): MessageFile | null => {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const file = value as Record<string, unknown>;
  const fileId = typeof file.fileId === 'string'
    ? file.fileId
    : typeof file.file_id === 'string'
      ? file.file_id
      : '';

  if (!fileId) {
    return null;
  }

  const url = typeof file.url === 'string' ? file.url : '';
  const previewUrlValue = typeof file.previewUrl === 'string'
    ? file.previewUrl
    : typeof file.preview_url === 'string'
      ? file.preview_url
      : undefined;

  return {
    fileId,
    filename: typeof file.filename === 'string' ? file.filename : '',
    originalName: typeof file.originalName === 'string'
      ? file.originalName
      : typeof file.original_name === 'string'
        ? file.original_name
        : '',
    storedFilename: typeof file.storedFilename === 'string'
      ? file.storedFilename
      : typeof file.stored_filename === 'string'
        ? file.stored_filename
        : undefined,
    mimeType: typeof file.mimeType === 'string'
      ? file.mimeType
      : typeof file.mime_type === 'string'
        ? file.mime_type
        : 'application/octet-stream',
    size: typeof file.size === 'number' ? file.size : 0,
    category: typeof file.category === 'string' ? file.category : 'document',
    url: toAbsoluteApiUrl(url) || url,
    previewUrl: toAbsoluteApiUrl(previewUrlValue),
    localPreview: typeof file.localPreview === 'string' ? file.localPreview : undefined,
    minimaxFileId: typeof file.minimaxFileId === 'string'
      ? file.minimaxFileId
      : typeof file.minimax_file_id === 'string'
        ? file.minimax_file_id
        : undefined,
    extractedText: typeof file.extractedText === 'string'
      ? file.extractedText
      : typeof file.extracted_text === 'string'
        ? file.extracted_text
        : undefined,
  };
};

export const normalizeMessageFiles = (value: unknown): MessageFile[] | undefined => {
  if (!Array.isArray(value)) {
    return undefined;
  }
  const files = value
    .map((item) => normalizeMessageFile(item))
    .filter((item): item is MessageFile => !!item);
  return files.length > 0 ? files : undefined;
};

export const hasRenderableMessageFiles = (value: unknown): boolean => {
  const files = normalizeMessageFiles(value);
  return Boolean(files && files.length > 0);
};

export const serializeMessageFiles = (files?: MessageFile[]): UploadedFile[] | undefined => {
  if (!files || files.length === 0) {
    return undefined;
  }
  return files.map((file) => ({
    file_id: file.fileId,
    filename: file.filename,
    original_name: file.originalName,
    stored_filename: file.storedFilename,
    mime_type: file.mimeType,
    size: file.size,
    category: file.category,
    url: file.url,
    preview_url: file.previewUrl,
    minimax_file_id: file.minimaxFileId,
    extracted_text: file.extractedText,
  }));
};
