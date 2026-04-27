import React, { memo, useState, useRef, useCallback, useEffect } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  FileAudio2,
  FileImage,
  FileText,
  Eraser,
  Info,
  LoaderCircle,
  Mic,
  PencilLine,
  Paperclip,
  RefreshCcw,
  RotateCcw,
  SendHorizonal,
  Square,
  Trash2,
  Upload,
  X,
} from 'lucide-react';
import { useI18n } from '../contexts/I18nContext';
import { useToast } from '../contexts/ToastContext';
import { chatService, type UploadedFile } from '../services/chat';
import { ConversationType, type MessageFile } from '../types/conversation';
import MentionPicker from './MentionPicker';

interface AgentInfo {
  id: string;
  name: string;
}

export interface SessionStatus {
  tone: 'info' | 'warning' | 'error' | 'success';
  message: string;
  detailLabel?: string;
  detailValue?: string;
  actionLabel?: string;
  onAction?: () => void | Promise<void>;
  actionTone?: 'neutral' | 'danger';
  secondaryActionLabel?: string;
  onSecondaryAction?: () => void | Promise<void>;
  secondaryActionTone?: 'neutral' | 'danger';
  dismissible?: boolean;
  onDismiss?: () => void;
}

interface MessageInputProps {
  conversationType: ConversationType;
  conversationName: string;
  agents: AgentInfo[];
  onSend: (message: string, mentionedAgents: string[], files?: MessageFile[]) => void | Promise<void>;
  disabled?: boolean;
  placeholder?: string;
  isLoading?: boolean;
  sessionStatus?: SessionStatus | null;
  focusRequestKey?: number;
  draftPresetText?: string;
  draftPresetKey?: number;
}

interface ComposerAttachment extends MessageFile {
  uploadState?: 'uploading' | 'ready' | 'error';
  errorMessage?: string;
  sourceFile?: File;
}

type BrowserSpeechRecognitionResult = {
  isFinal?: boolean;
  length: number;
  [index: number]: { transcript?: string };
};

type BrowserSpeechRecognitionEvent = Event & {
  resultIndex: number;
  results: ArrayLike<BrowserSpeechRecognitionResult>;
};

type BrowserSpeechRecognitionErrorEvent = Event & {
  error?: string;
};

interface BrowserSpeechRecognition {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: BrowserSpeechRecognitionEvent) => void) | null;
  onerror: ((event: BrowserSpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

type BrowserWindow = Window & typeof globalThis & {
  SpeechRecognition?: new () => BrowserSpeechRecognition;
  webkitSpeechRecognition?: new () => BrowserSpeechRecognition;
};

type TranslateFn = (key: string, values?: Record<string, number | string>) => string;

const getStatusActionIcon = (label?: string) => {
  if (!label) return <Info className="h-4 w-4" strokeWidth={2} />;
  const normalized = label.toLowerCase();
  if (label.includes('重试') || normalized.includes('retry')) return <RotateCcw className="h-4 w-4" strokeWidth={2} />;
  if (label.includes('继续输入') || normalized.includes('continue input')) return <PencilLine className="h-4 w-4" strokeWidth={2} />;
  if (label.includes('停止') || normalized.includes('stop')) return <Square className="h-4 w-4" strokeWidth={2} />;
  if (label.includes('继续') || normalized.includes('continue')) return <SendHorizonal className="h-4 w-4" strokeWidth={2} />;
  return <Info className="h-4 w-4" strokeWidth={2} />;
};

const ACCEPTED_UPLOAD_TYPES = [
  'image/*',
  'image/jpeg',
  'image/png',
  'image/gif',
  'image/webp',
  'audio/*',
  'audio/mpeg',
  'audio/wav',
  'audio/mp4',
  'audio/x-m4a',
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/plain',
  'text/markdown',
  '.pdf',
  '.docx',
  '.pptx',
  '.xlsx',
  '.txt',
  '.md',
  '.jpg',
  '.jpeg',
  '.png',
  '.gif',
  '.webp',
  '.mp3',
  '.wav',
  '.m4a',
].join(',');

const MAX_ATTACHMENT_SIZE_BYTES = 50 * 1024 * 1024;
const MAX_ATTACHMENT_COUNT = 10;

const inferAttachmentCategory = (file: File): ComposerAttachment['category'] => {
  const mimeType = (file.type || '').toLowerCase();
  const extension = file.name.toLowerCase().split('.').pop() || '';

  if (mimeType.startsWith('image/') || ['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(extension)) {
    return 'image';
  }
  if (mimeType.startsWith('audio/') || ['mp3', 'wav', 'm4a'].includes(extension)) {
    return 'audio';
  }
  if (
    mimeType === 'application/pdf'
    || mimeType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    || mimeType === 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    || mimeType === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    || mimeType === 'text/plain'
    || mimeType === 'text/markdown'
    || ['pdf', 'docx', 'pptx', 'xlsx', 'txt', 'md'].includes(extension)
  ) {
    return 'document';
  }
  return 'document';
};

const formatFileSize = (size: number): string => {
  if (size >= 1024 * 1024) {
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  }
  if (size >= 1024) {
    return `${Math.round(size / 1024)} KB`;
  }
  return `${size} B`;
};

const validateSelectedFiles = (
  selectedFiles: File[],
  existingCount: number,
  t: TranslateFn,
): { accepted: File[]; errorMessage?: string } => {
  if (selectedFiles.length === 0) {
    return { accepted: [] };
  }

  if (existingCount + selectedFiles.length > MAX_ATTACHMENT_COUNT) {
    return {
      accepted: [],
      errorMessage: t('messageInput.maxAttachmentsError', { count: MAX_ATTACHMENT_COUNT }),
    };
  }

  const oversized = selectedFiles.find((file) => file.size > MAX_ATTACHMENT_SIZE_BYTES);
  if (oversized) {
    return {
      accepted: [],
      errorMessage: t('messageInput.fileTooLargeError', { name: oversized.name }),
    };
  }

  return { accepted: selectedFiles };
};

const revokeObjectPreview = (previewUrl?: string) => {
  if (previewUrl && previewUrl.startsWith('blob:')) {
    URL.revokeObjectURL(previewUrl);
  }
};

const buildAttachmentPreviewText = (attachment: ComposerAttachment, t: TranslateFn): string => {
  const extractedText = attachment.extractedText?.trim();
  if (extractedText) {
    return extractedText.replace(/\s+/g, ' ').slice(0, 140);
  }

  const lowerName = attachment.originalName.toLowerCase();
  if (lowerName.endsWith('.pdf')) return t('messageInput.preview.pdf');
  if (lowerName.endsWith('.docx')) return t('messageInput.preview.docx');
  if (lowerName.endsWith('.xlsx')) return t('messageInput.preview.xlsx');
  if (lowerName.endsWith('.pptx')) return t('messageInput.preview.pptx');
  if (attachment.category === 'audio') return t('messageInput.preview.audio');
  if (attachment.category === 'image') return t('messageInput.preview.image');
  return t('messageInput.preview.default');
};

const getAttachmentKindLabel = (attachment: ComposerAttachment, t: TranslateFn): string => {
  const lowerName = attachment.originalName.toLowerCase();
  if (attachment.category === 'image') return t('messageInput.kind.image');
  if (attachment.category === 'audio') return t('messageInput.kind.audio');
  if (lowerName.endsWith('.pdf')) return 'PDF';
  if (lowerName.endsWith('.docx')) return 'Word';
  if (lowerName.endsWith('.xlsx')) return 'Excel';
  if (lowerName.endsWith('.pptx')) return 'PowerPoint';
  if (lowerName.endsWith('.md')) return 'Markdown';
  if (lowerName.endsWith('.txt')) return t('messageInput.kind.text');
  return t('messageInput.kind.file');
};

const createPendingAttachment = (file: File, index: number): ComposerAttachment => {
  const category = inferAttachmentCategory(file);
  const localPreview = category === 'image' || category === 'audio'
    ? URL.createObjectURL(file)
    : undefined;

  return {
    fileId: `pending-${Date.now()}-${index}`,
    filename: file.name,
    originalName: file.name,
    mimeType: file.type || 'application/octet-stream',
    size: file.size,
    category,
    url: '',
    localPreview,
    uploadState: 'uploading',
    sourceFile: file,
  };
};

const getAttachmentIcon = (attachment: ComposerAttachment) => {
  if (attachment.uploadState === 'uploading') {
    return <LoaderCircle className="h-4 w-4 animate-spin" strokeWidth={2} />;
  }
  if (attachment.category === 'image') {
    return <FileImage className="h-4 w-4" strokeWidth={2} />;
  }
  if (attachment.category === 'audio') {
    return <FileAudio2 className="h-4 w-4" strokeWidth={2} />;
  }
  return <FileText className="h-4 w-4" strokeWidth={2} />;
};

const buildDefaultAttachmentPrompt = (attachments: ComposerAttachment[], t: TranslateFn): string => {
  if (attachments.length === 0) {
    return '';
  }
  const categories = new Set(attachments.map((attachment) => attachment.category));
  if (categories.has('audio')) {
    return t('messageInput.defaultPrompt.audio');
  }
  if (categories.has('image')) {
    return t('messageInput.defaultPrompt.image');
  }
  if (categories.has('document')) {
    return t('messageInput.defaultPrompt.document');
  }
  return t('messageInput.defaultPrompt.default');
};

const getMentionedAgentIdsFromText = (value: string, agents: AgentInfo[]): string[] => (
  agents
    .map((agent) => ({
      id: agent.id,
      index: value.indexOf(`@${agent.name}`),
    }))
    .filter((item) => item.index >= 0)
    .sort((left, right) => left.index - right.index)
    .map((item) => item.id)
);

const MessageInput: React.FC<MessageInputProps> = ({
  conversationType,
  conversationName,
  agents,
  onSend,
  disabled = false,
  placeholder = '',
  isLoading = false,
  sessionStatus = null,
  focusRequestKey = 0,
  draftPresetText = '',
  draftPresetKey = 0,
}) => {
  const { t } = useI18n();
  const toast = useToast();
  const [message, setMessage] = useState('');
  const [attachments, setAttachments] = useState<ComposerAttachment[]>([]);
  const [showMentionPicker, setShowMentionPicker] = useState(false);
  const [mentionFilter, setMentionFilter] = useState('');
  const [mentionPosition, setMentionPosition] = useState({ top: 0, left: 0 });
  const [mentionedAgents, setMentionedAgents] = useState<string[]>([]);
  const [mentionStartIndex, setMentionStartIndex] = useState(-1);
  const [isRecording, setIsRecording] = useState(false);
  const [isDragActive, setIsDragActive] = useState(false);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const speechBaseMessageRef = useRef('');
  const attachmentsRef = useRef<ComposerAttachment[]>([]);
  const dragDepthRef = useRef(0);

  const isTeamChat = conversationType === ConversationType.TEAM;
  const hasDraft = !!message.trim() || attachments.length > 0;
  const canInterruptAndSend = isLoading && hasDraft;
  const uploadingCount = attachments.filter((attachment) => attachment.uploadState === 'uploading').length;
  const readyAttachments = attachments.filter((attachment) => attachment.uploadState === 'ready');
  const failedAttachments = attachments.filter((attachment) => attachment.uploadState === 'error');
  const hasPendingUploads = uploadingCount > 0;
  const failedCount = failedAttachments.length;
  const speechRecognitionCtor = typeof window === 'undefined'
    ? undefined
    : ((window as BrowserWindow).SpeechRecognition || (window as BrowserWindow).webkitSpeechRecognition);
  const resolvedPlaceholder = placeholder || t('messageInput.defaultPlaceholder');

  const syncMentionedAgentsFromText = useCallback((value: string) => {
    if (!isTeamChat) {
      if (mentionedAgents.length > 0) {
        setMentionedAgents([]);
      }
      return;
    }
    const nextMentioned = getMentionedAgentIdsFromText(value, agents);
    setMentionedAgents((prev) => {
      if (prev.length === nextMentioned.length && prev.every((agentId, index) => agentId === nextMentioned[index])) {
        return prev;
      }
      return nextMentioned;
    });
  }, [agents, isTeamChat, mentionedAgents.length]);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    const cursorPos = e.target.selectionStart || 0;

    setMessage(value);
    syncMentionedAgentsFromText(value);

    if (isTeamChat) {
      const lastAtIndex = value.lastIndexOf('@', cursorPos);
      if (lastAtIndex !== -1) {
        const textAfterAt = value.substring(lastAtIndex + 1, cursorPos);
        const hasSpaceAfterAt = textAfterAt.includes(' ');

        if (!hasSpaceAfterAt) {
          setMentionStartIndex(lastAtIndex);
          setMentionFilter(textAfterAt);
          setShowMentionPicker(true);

          if (containerRef.current) {
            const containerRect = containerRef.current.getBoundingClientRect();
            setMentionPosition({
              top: -8,
              left: Math.max(16, Math.min(100, containerRect.width - 240)),
            });
          }
        } else {
          setShowMentionPicker(false);
        }
      } else {
        setShowMentionPicker(false);
      }
    }
  }, [isTeamChat, syncMentionedAgentsFromText]);

  const handleMentionSelect = useCallback((agent: AgentInfo) => {
    if (mentionStartIndex === -1) return;

    const beforeMention = message.substring(0, mentionStartIndex);
    const afterCursor = message.substring(textareaRef.current?.selectionStart || 0);
    const newMessage = `${beforeMention}@${agent.name} ${afterCursor}`;

    setMessage(newMessage);
    setMentionedAgents(getMentionedAgentIdsFromText(newMessage, agents));
    setShowMentionPicker(false);
    setMentionStartIndex(-1);

    if (textareaRef.current) {
      const newCursorPos = beforeMention.length + agent.name.length + 2;
      textareaRef.current.focus();
      setTimeout(() => {
        textareaRef.current?.setSelectionRange(newCursorPos, newCursorPos);
      }, 0);
    }
  }, [agents, message, mentionStartIndex]);

  const handleRemoveMention = useCallback((agentId: string) => {
    const agent = agents.find((item) => item.id === agentId);
    if (!agent) return;

    const nextMessage = message
      .replaceAll(`@${agent.name} `, '')
      .replaceAll(`@${agent.name}`, '')
      .replace(/\s{2,}/g, ' ')
      .trimStart();

    setMessage(nextMessage);
    setMentionedAgents((prev) => prev.filter((item) => item !== agentId));
    setShowMentionPicker(false);
    textareaRef.current?.focus();
  }, [agents, message]);

  const handleRemoveAttachment = useCallback((attachmentId: string) => {
    setAttachments((prev) => {
      const target = prev.find((item) => item.fileId === attachmentId);
      if (target?.uploadState === 'ready') {
        void chatService.deleteUploadedFile(attachmentId).catch((error) => {
          console.error('Failed to delete uploaded file:', error);
        });
      }
      revokeObjectPreview(target?.localPreview);
      return prev.filter((item) => item.fileId !== attachmentId);
    });
  }, []);

  const handleMoveAttachment = useCallback((attachmentId: string, direction: 'left' | 'right') => {
    setAttachments((prev) => {
      const currentIndex = prev.findIndex((item) => item.fileId === attachmentId);
      if (currentIndex === -1) return prev;

      const nextIndex = direction === 'left' ? currentIndex - 1 : currentIndex + 1;
      if (nextIndex < 0 || nextIndex >= prev.length) {
        return prev;
      }

      const next = [...prev];
      const [target] = next.splice(currentIndex, 1);
      next.splice(nextIndex, 0, target);
      return next;
    });
  }, []);

  const handleClearAttachments = useCallback(() => {
    attachmentsRef.current.forEach((attachment) => {
      if (attachment.uploadState === 'ready') {
        void chatService.deleteUploadedFile(attachment.fileId).catch((error) => {
          console.error('Failed to delete uploaded file:', error);
        });
      }
      revokeObjectPreview(attachment.localPreview);
    });
    setAttachments([]);
  }, []);

  const uploadAttachments = useCallback(async (selectedFiles: File[]) => {
    if (selectedFiles.length === 0) {
      return;
    }

    const pendingAttachments = selectedFiles.map((file, index) => createPendingAttachment(file, index));

    setAttachments((prev) => [...prev, ...pendingAttachments]);

    try {
      const uploadedFiles = await chatService.uploadFiles(selectedFiles);
      const uploadedMap = uploadedFiles.map((file, index) => ({
        fileId: file.file_id,
        filename: file.filename,
        originalName: file.original_name,
        storedFilename: file.stored_filename,
        mimeType: file.mime_type,
        size: file.size,
        category: file.category,
        url: file.url,
        previewUrl: file.preview_url,
        localPreview: pendingAttachments[index]?.localPreview,
        minimaxFileId: file.minimax_file_id,
        extractedText: file.extracted_text,
        uploadState: 'ready' as const,
      }));

      setAttachments((prev) => {
        const pendingIds = new Set(prev.map((item) => item.fileId));
        const retainedUploads = uploadedMap.filter((_, index) => pendingIds.has(pendingAttachments[index].fileId));
        return [
          ...prev.filter((item) => !pendingAttachments.some((pending) => pending.fileId === item.fileId)),
          ...retainedUploads,
        ];
      });
      toast.success(t('messageInput.attachmentsAdded', { count: uploadedFiles.length }));
    } catch (error) {
      console.error('Failed to upload files:', error);
      const errorMessage = error instanceof Error ? error.message : t('messageInput.uploadFailed');
      setAttachments((prev) => prev.map((item) => (
        pendingAttachments.some((pending) => pending.fileId === item.fileId)
          ? {
              ...item,
              uploadState: 'error',
              errorMessage,
            }
          : item
      )));
      toast.error(errorMessage);
    }
  }, [toast]);

  const retryAttachments = useCallback(async (attachmentIds: string[]) => {
    const targets = attachmentsRef.current.filter((attachment) => (
      attachmentIds.includes(attachment.fileId)
      && attachment.uploadState === 'error'
      && attachment.sourceFile
    ));

    if (targets.length === 0) {
      toast.warning(t('messageInput.retryNone'));
      return;
    }

    setAttachments((prev) => prev.map((item) => (
      attachmentIds.includes(item.fileId)
        ? {
            ...item,
            uploadState: 'uploading',
            errorMessage: undefined,
          }
        : item
    )));

    const results = await Promise.allSettled(targets.map(async (attachment) => {
      const uploaded = await chatService.uploadFiles([attachment.sourceFile as File]);
      return {
        attachmentId: attachment.fileId,
        uploaded: uploaded[0],
      };
    }));

    const successMap = new Map<string, UploadedFile>();
    const errorMap = new Map<string, string>();

    results.forEach((result, index) => {
      const attachmentId = targets[index]?.fileId;
      if (!attachmentId) return;

      if (result.status === 'fulfilled' && result.value.uploaded) {
        successMap.set(attachmentId, result.value.uploaded);
        return;
      }

      const reason = result.status === 'rejected'
        ? (result.reason instanceof Error ? result.reason.message : t('messageInput.uploadFailed'))
        : t('messageInput.uploadFailed');
      errorMap.set(attachmentId, reason);
    });

    setAttachments((prev) => prev.map((item) => {
      const uploaded = successMap.get(item.fileId);
      if (uploaded) {
        return {
          fileId: uploaded.file_id,
          filename: uploaded.filename,
          originalName: uploaded.original_name,
          storedFilename: uploaded.stored_filename,
          mimeType: uploaded.mime_type,
          size: uploaded.size,
          category: uploaded.category as ComposerAttachment['category'],
          url: uploaded.url,
          previewUrl: uploaded.preview_url,
          localPreview: item.localPreview,
          minimaxFileId: uploaded.minimax_file_id,
          extractedText: uploaded.extracted_text,
          uploadState: 'ready' as const,
          sourceFile: item.sourceFile,
        };
      }

      const nextErrorMessage = errorMap.get(item.fileId);
      if (nextErrorMessage) {
        return {
          ...item,
          uploadState: 'error',
          errorMessage: nextErrorMessage,
        };
      }

      return item;
    }));

    if (errorMap.size === 0) {
      toast.success(t('messageInput.retrySuccess', { count: successMap.size }));
    } else if (successMap.size > 0) {
      toast.warning(t('messageInput.retryPartial', { success: successMap.size, failed: errorMap.size }));
    } else {
      toast.error(errorMap.values().next().value || t('messageInput.uploadFailed'));
    }
  }, [t, toast]);

  const handleRetryAttachment = useCallback(async (attachmentId: string) => {
    await retryAttachments([attachmentId]);
  }, [retryAttachments]);

  const handleRetryFailedAttachments = useCallback(async () => {
    await retryAttachments(
      attachmentsRef.current
        .filter((attachment) => attachment.uploadState === 'error')
        .map((attachment) => attachment.fileId),
    );
  }, [retryAttachments]);

  const handleFileSelection = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files || []);
    event.target.value = '';
    const validation = validateSelectedFiles(selectedFiles, attachmentsRef.current.length, t);
    if (validation.errorMessage) {
      toast.error(validation.errorMessage);
      return;
    }
    await uploadAttachments(validation.accepted);
  }, [t, toast, uploadAttachments]);

  const handlePaste = useCallback((event: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const clipboardFiles = Array.from(event.clipboardData?.files || []);
    if (clipboardFiles.length === 0) {
      return;
    }
    event.preventDefault();
    const validation = validateSelectedFiles(clipboardFiles, attachmentsRef.current.length, t);
    if (validation.errorMessage) {
      toast.error(validation.errorMessage);
      return;
    }
    void uploadAttachments(validation.accepted);
  }, [t, toast, uploadAttachments]);

  const handleDragEnter = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    if (disabled || !Array.from(event.dataTransfer?.types || []).includes('Files')) {
      return;
    }
    event.preventDefault();
    dragDepthRef.current += 1;
    setIsDragActive(true);
  }, [disabled]);

  const handleDragOver = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    if (disabled || !Array.from(event.dataTransfer?.types || []).includes('Files')) {
      return;
    }
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
    setIsDragActive(true);
  }, [disabled]);

  const handleDragLeave = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    if (disabled || !Array.from(event.dataTransfer?.types || []).includes('Files')) {
      return;
    }
    event.preventDefault();
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) {
      setIsDragActive(false);
    }
  }, [disabled]);

  const handleDrop = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    if (disabled || !Array.from(event.dataTransfer?.types || []).includes('Files')) {
      return;
    }
    event.preventDefault();
    dragDepthRef.current = 0;
    setIsDragActive(false);
    const droppedFiles = Array.from(event.dataTransfer.files || []);
    const validation = validateSelectedFiles(droppedFiles, attachmentsRef.current.length, t);
    if (validation.errorMessage) {
      toast.error(validation.errorMessage);
      return;
    }
    void uploadAttachments(validation.accepted);
  }, [disabled, t, toast, uploadAttachments]);

  const handleClearDraft = useCallback(() => {
    recognitionRef.current?.stop();
    setIsRecording(false);
    attachmentsRef.current.forEach((attachment) => {
      if (attachment.uploadState === 'ready') {
        void chatService.deleteUploadedFile(attachment.fileId).catch((error) => {
          console.error('Failed to delete uploaded file:', error);
        });
      }
      revokeObjectPreview(attachment.localPreview);
    });
    setMessage('');
    setMentionedAgents([]);
    setShowMentionPicker(false);
    setMentionStartIndex(-1);
    setAttachments([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.focus();
    }
  }, []);

  const handleSend = useCallback(() => {
    const trimmedMessage = message.trim();
    const normalizedMessage = trimmedMessage || buildDefaultAttachmentPrompt(readyAttachments, t);
    if ((!normalizedMessage && readyAttachments.length === 0) || disabled || hasPendingUploads) return;
    const orderedMentionedAgents = isTeamChat
      ? getMentionedAgentIdsFromText(normalizedMessage, agents)
      : mentionedAgents;

    recognitionRef.current?.stop();
    setIsRecording(false);
    onSend(normalizedMessage, orderedMentionedAgents, readyAttachments);
    attachments.forEach((attachment) => revokeObjectPreview(attachment.localPreview));
    setMessage('');
    setMentionedAgents([]);
    setShowMentionPicker(false);
    setAttachments([]);

    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [agents, disabled, hasPendingUploads, isTeamChat, mentionedAgents, message, onSend, readyAttachments, t]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (showMentionPicker) return;

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend, showMentionPicker]);

  const handleVoiceInputToggle = useCallback(() => {
    if (!speechRecognitionCtor) {
      toast.warning(t('messageInput.browserSpeechUnsupported'));
      return;
    }

    if (isRecording) {
      recognitionRef.current?.stop();
      return;
    }

    const recognition = recognitionRef.current || new speechRecognitionCtor();
    recognition.lang = 'zh-CN';
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (event: BrowserSpeechRecognitionEvent) => {
      let transcript = '';
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        const segment = result?.[0]?.transcript || '';
        transcript += segment;
      }
      const nextMessage = `${speechBaseMessageRef.current}${transcript}`.trim();
      setMessage(nextMessage);
      syncMentionedAgentsFromText(nextMessage);
    };

    recognition.onerror = (event: BrowserSpeechRecognitionErrorEvent) => {
      setIsRecording(false);
      if (event.error && event.error !== 'no-speech') {
        toast.error(t('messageInput.voiceInputFailedWithReason', { reason: event.error }));
      }
    };

    recognition.onend = () => {
      setIsRecording(false);
    };

    recognitionRef.current = recognition;
    speechBaseMessageRef.current = message ? `${message}${message.endsWith('\n') ? '' : '\n'}` : '';
    try {
      setIsRecording(true);
      recognition.start();
    } catch (error) {
      console.error('Failed to start speech recognition:', error);
      setIsRecording(false);
      toast.error(t('messageInput.voiceInputStartFailed'));
    }
  }, [isRecording, message, speechRecognitionCtor, syncMentionedAgentsFromText, t, toast]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowMentionPicker(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    attachmentsRef.current = attachments;
  }, [attachments]);

  useEffect(() => {
    if (!disabled) {
      return;
    }
    dragDepthRef.current = 0;
    setIsDragActive(false);
  }, [disabled]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [message]);

  useEffect(() => {
    if (disabled) {
      return;
    }
    textareaRef.current?.focus();
  }, [disabled, focusRequestKey]);

  useEffect(() => {
    if (!draftPresetText) {
      return;
    }

    setMessage(draftPresetText);
    syncMentionedAgentsFromText(draftPresetText);
    setShowMentionPicker(false);
    setMentionStartIndex(-1);

    if (textareaRef.current && !disabled) {
      textareaRef.current.focus();
      const cursorPosition = draftPresetText.length;
      textareaRef.current.setSelectionRange(cursorPosition, cursorPosition);
    }
  }, [disabled, draftPresetKey, draftPresetText, syncMentionedAgentsFromText]);

  useEffect(() => () => {
    recognitionRef.current?.stop();
    attachmentsRef.current.forEach((attachment) => revokeObjectPreview(attachment.localPreview));
  }, []);

  return (
    <div
      ref={containerRef}
      className="relative border-t border-slate-200 bg-[radial-gradient(circle_at_top,_rgba(191,219,254,0.24),_transparent_36%),linear-gradient(180deg,_rgba(248,250,252,0.96),_rgba(255,255,255,1))]"
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {isDragActive && !disabled && (
        <div
          data-testid="composer-drag-overlay"
          className="pointer-events-none absolute inset-3 z-20 flex items-center justify-center rounded-[28px] border-2 border-dashed border-blue-300 bg-blue-50/90 backdrop-blur-sm"
        >
          <div className="flex flex-col items-center gap-2 text-center text-blue-700">
            <span className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-white shadow-sm">
              <Upload className="h-6 w-6" strokeWidth={2} />
            </span>
            <div className="space-y-1">
              <div className="text-sm font-semibold">{t('messageInput.dragUploadTitle')}</div>
              <div className="text-xs text-blue-600">{t('messageInput.dragUploadBody')}</div>
            </div>
          </div>
        </div>
      )}

      {showMentionPicker && (
        <MentionPicker
          agents={agents}
          position={mentionPosition}
          onSelect={handleMentionSelect}
          onClose={() => setShowMentionPicker(false)}
          filter={mentionFilter}
        />
      )}

      <div className="border-b border-slate-200/70 bg-white/80 px-4 py-2.5 backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold shadow-sm ${
              isTeamChat
                ? 'border-violet-200 bg-violet-50 text-violet-700'
                : 'border-blue-200 bg-blue-50 text-blue-700'
            }`}>
              {isTeamChat ? t('messageInput.teamRelayMode') : t('messageInput.directMode')}
            </span>
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600 shadow-sm">
              <span className="font-medium text-slate-500">{t('messageInput.currentConversation')}</span>
              <span className="font-semibold text-slate-700">{conversationName}</span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {hasDraft && !isLoading && (
              <button
                type="button"
                onClick={handleClearDraft}
                className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 transition-colors hover:bg-slate-100"
                aria-label={t('messageInput.clearDraft')}
                title={t('messageInput.clearDraft')}
              >
                <Eraser className="h-4 w-4" strokeWidth={2} />
              </button>
            )}
          </div>
        </div>

        {sessionStatus && (
          <div
            data-testid="chat-session-status"
              className={`mt-2 flex flex-wrap items-start justify-between gap-3 rounded-2xl border px-4 py-2.5 text-sm shadow-sm ${
              sessionStatus.tone === 'error'
                ? 'border-red-200 bg-red-50 text-red-900'
                : sessionStatus.tone === 'warning'
                  ? 'border-amber-200 bg-amber-50 text-amber-900'
                  : sessionStatus.tone === 'success'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                    : 'border-sky-200 bg-sky-50 text-sky-900'
            }`}
          >
            <div className="flex min-w-0 items-start gap-2">
              <Info className="mt-0.5 h-4 w-4 flex-shrink-0" strokeWidth={2} />
              <div className="min-w-0">
                <div data-testid="chat-session-status-message" className="min-w-0 truncate">
                  {sessionStatus.message}
                </div>
                {sessionStatus.detailValue && (
                  <div
                    data-testid="chat-session-status-detail"
                    className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-current/80"
                  >
                    {sessionStatus.detailLabel && (
                      <span className="font-medium">{sessionStatus.detailLabel}</span>
                    )}
                    <code className="max-w-full overflow-hidden text-ellipsis whitespace-nowrap rounded bg-white/70 px-1.5 py-0.5 font-mono text-[11px]">
                      {sessionStatus.detailValue}
                    </code>
                  </div>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {sessionStatus.actionLabel && sessionStatus.onAction && (
                <button
                  type="button"
                  onClick={sessionStatus.onAction}
                  className={`inline-flex h-8 w-8 items-center justify-center rounded-full transition-colors ${
                    sessionStatus.actionTone === 'danger'
                      ? 'border border-red-200 bg-red-50 text-red-700 hover:bg-red-100'
                      : 'bg-white text-current hover:bg-white/80'
                  }`}
                  title={sessionStatus.actionLabel}
                  aria-label={sessionStatus.actionLabel}
                >
                  {getStatusActionIcon(sessionStatus.actionLabel)}
                </button>
              )}
              {sessionStatus.secondaryActionLabel && sessionStatus.onSecondaryAction && (
                <button
                  type="button"
                  onClick={sessionStatus.onSecondaryAction}
                  className={`inline-flex h-8 w-8 items-center justify-center rounded-full transition-colors ${
                    sessionStatus.secondaryActionTone === 'danger'
                      ? 'border border-red-200 bg-red-50 text-red-700 hover:bg-red-100'
                      : 'bg-white text-current hover:bg-white/80'
                  }`}
                  title={sessionStatus.secondaryActionLabel}
                  aria-label={sessionStatus.secondaryActionLabel}
                >
                  {getStatusActionIcon(sessionStatus.secondaryActionLabel)}
                </button>
              )}
              {sessionStatus.dismissible && sessionStatus.onDismiss && (
                <button
                  type="button"
                  onClick={sessionStatus.onDismiss}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:bg-white/50"
                  aria-label={t('common.close')}
                  title={t('common.close')}
                >
                  <X className="h-4 w-4" strokeWidth={2} />
                </button>
              )}
            </div>
          </div>
        )}

        {sessionStatus?.tone === 'success' && hasDraft && (
          <p className="mt-2 text-xs text-emerald-700">
            {t('messageInput.draftPreserved')}
          </p>
        )}
      </div>

      <div className="p-2.5">
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          multiple
          accept={ACCEPTED_UPLOAD_TYPES}
          onChange={handleFileSelection}
        />
        <div className="rounded-[28px] border border-slate-200 bg-white p-2.5 shadow-[0_18px_40px_rgba(15,23,42,0.08)]">
          {mentionedAgents.length > 0 && (
            <div className="mb-3 flex flex-wrap items-center gap-2 rounded-[22px] border border-violet-200 bg-violet-50/80 px-3 py-2">
              <span className="text-xs font-medium text-violet-700">{t('messageInput.willMention')}</span>
              {mentionedAgents.map((agentId) => {
                const agent = agents.find((item) => item.id === agentId);
                return agent ? (
                  <button
                    key={agentId}
                    type="button"
                    onClick={() => handleRemoveMention(agentId)}
                    className="inline-flex items-center gap-1 rounded-full border border-violet-200 bg-white px-2.5 py-1 text-xs font-medium text-violet-700 transition-colors hover:bg-violet-100"
                  >
                    <span>@{agent.name}</span>
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                ) : null;
              })}
            </div>
          )}

          {attachments.length > 0 && (
            <div className="mb-2 rounded-[18px] border border-slate-200 bg-slate-50/90 px-2.5 py-2">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-medium text-slate-600">{t('messageInput.attachments')}</span>
                  <span className="inline-flex items-center rounded-full bg-white px-2 py-0.5 text-[11px] text-slate-500">
                    {t('messageInput.pendingSendCount', { count: attachments.length })}
                  </span>
                  {readyAttachments.length > 0 && (
                    <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-700">
                      {t('messageInput.readyCount', { count: readyAttachments.length })}
                    </span>
                  )}
                  {uploadingCount > 0 && (
                    <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-[11px] text-amber-700">
                      {t('messageInput.uploadingCount', { count: uploadingCount })}
                    </span>
                  )}
                  {failedCount > 0 && (
                    <span className="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-[11px] font-medium text-red-700">
                      {t('messageInput.failedCount', { count: failedCount })}
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  {failedCount > 0 && (
                    <button
                      type="button"
                      onClick={() => void handleRetryFailedAttachments()}
                      className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-white px-2.5 py-1 text-[11px] font-medium text-red-700 transition-colors hover:bg-red-50"
                    >
                      <RefreshCcw className="h-3.5 w-3.5" strokeWidth={2} />
                      {t('messageInput.retryFailed')}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={handleClearAttachments}
                    className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600 transition-colors hover:bg-slate-100"
                  >
                    <Trash2 className="h-3.5 w-3.5" strokeWidth={2} />
                    {t('messageInput.clearAttachments')}
                  </button>
                </div>
              </div>
              <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
              {attachments.map((attachment) => (
                <div
                  key={attachment.fileId}
                  className={`group relative w-[184px] shrink-0 rounded-[18px] border px-2.5 py-2.5 text-xs shadow-sm transition-colors ${
                    attachment.uploadState === 'error'
                      ? 'border-red-200 bg-red-50 text-red-700'
                      : attachment.uploadState === 'uploading'
                        ? 'border-amber-200 bg-amber-50 text-amber-700'
                        : 'border-slate-200 bg-white text-slate-700'
                  }`}
                >
                  <div className="absolute right-1.5 top-1.5 flex items-center gap-1 rounded-full bg-white/90 px-1 py-1 opacity-100 shadow-sm transition-opacity md:opacity-0 md:group-hover:opacity-100">
                    {attachments.length > 1 && (
                      <>
                        <button
                          type="button"
                          onClick={() => handleMoveAttachment(attachment.fileId, 'left')}
                          className="inline-flex h-6 w-6 items-center justify-center rounded-full transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
                          aria-label={t('messageInput.moveAttachmentLeft', { name: attachment.originalName })}
                          title={t('messageInput.moveLeft')}
                          disabled={attachments[0]?.fileId === attachment.fileId}
                        >
                          <ArrowLeft className="h-3 w-3" strokeWidth={2} />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleMoveAttachment(attachment.fileId, 'right')}
                          className="inline-flex h-6 w-6 items-center justify-center rounded-full transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
                          aria-label={t('messageInput.moveAttachmentRight', { name: attachment.originalName })}
                          title={t('messageInput.moveRight')}
                          disabled={attachments[attachments.length - 1]?.fileId === attachment.fileId}
                        >
                          <ArrowRight className="h-3 w-3" strokeWidth={2} />
                        </button>
                      </>
                    )}
                    {attachment.uploadState === 'error' && (
                      <button
                        type="button"
                        onClick={() => void handleRetryAttachment(attachment.fileId)}
                        className="inline-flex h-6 w-6 items-center justify-center rounded-full text-red-700 transition-colors hover:bg-red-100"
                        aria-label={t('messageInput.retryAttachment', { name: attachment.originalName })}
                        title={t('messageInput.retryUpload')}
                      >
                        <RefreshCcw className="h-3 w-3" strokeWidth={2} />
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => handleRemoveAttachment(attachment.fileId)}
                      className="inline-flex h-6 w-6 items-center justify-center rounded-full transition-colors hover:bg-slate-100"
                      aria-label={t('messageInput.removeAttachment', { name: attachment.originalName })}
                      title={t('messageInput.removeAttachmentShort')}
                    >
                      <X className="h-3 w-3" strokeWidth={2} />
                    </button>
                  </div>
                  <div className="flex items-start gap-2.5 pr-8">
                    {attachment.category === 'image' && (attachment.localPreview || attachment.previewUrl) ? (
                      <img
                        src={attachment.localPreview || attachment.previewUrl}
                        alt={attachment.originalName}
                        className="h-12 w-12 rounded-2xl object-cover"
                      />
                    ) : (
                      <span className="inline-flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-2xl bg-slate-100">
                        {getAttachmentIcon(attachment)}
                      </span>
                    )}
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="inline-flex items-center rounded-full bg-slate-900 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                          #{attachments.findIndex((item) => item.fileId === attachment.fileId) + 1}
                        </span>
                        <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-500">
                          {getAttachmentKindLabel(attachment, t)}
                        </span>
                        <span className="text-[10px] opacity-80">
                          {attachment.uploadState === 'uploading'
                            ? t('messageInput.uploading')
                            : attachment.errorMessage || formatFileSize(attachment.size)}
                        </span>
                      </div>
                      <div className="mt-1 line-clamp-2 text-[13px] font-medium leading-5">{attachment.originalName}</div>
                    </div>
                  </div>
                  <p className="mt-1.5 line-clamp-1 text-[11px] leading-5 text-slate-500">
                    {buildAttachmentPreviewText(attachment, t)}
                  </p>
                  {attachment.uploadState === 'error' && (
                    <p className="mt-1 text-[11px] leading-5 text-red-700">
                      {t('messageInput.uploadRetained')}
                    </p>
                  )}
                </div>
              ))}
              </div>
            </div>
          )}

          <div className="flex items-end gap-3">
            <div className="flex-1 rounded-[24px] border border-slate-200 bg-slate-50/80 px-3 py-2.5 transition-colors focus-within:border-blue-300 focus-within:bg-white focus-within:shadow-[0_0_0_4px_rgba(59,130,246,0.10)]">
              <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2 px-1">
                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <span className={`inline-flex items-center rounded-full px-2 py-1 font-medium ${
                    isTeamChat ? 'bg-violet-100 text-violet-700' : 'bg-blue-100 text-blue-700'
                  }`}>
                    {isTeamChat ? t('messageInput.modeMentionRelay') : t('messageInput.modeDirectChat')}
                  </span>
                  {canInterruptAndSend && (
                    <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-1 font-medium text-amber-700">
                      {t('messageInput.stopCurrentRelayBeforeSend')}
                    </span>
                  )}
                  {hasPendingUploads && (
                    <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-1 font-medium text-amber-700">
                      {t('messageInput.attachmentsUploading')}
                    </span>
                  )}
                  {isRecording && (
                    <span className="inline-flex items-center rounded-full bg-rose-100 px-2 py-1 font-medium text-rose-700">
                      {t('messageInput.voiceRecording')}
                    </span>
                  )}
                </div>
                <span className="px-1 text-xs text-slate-400">
                  {t('messageInput.characterCount', { count: message.trim().length })}
                  {readyAttachments.length > 0 ? ` · ${t('messageInput.attachmentCount', { count: readyAttachments.length })}` : ''}
                </span>
              </div>

              <textarea
                ref={textareaRef}
                value={message}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                onPaste={handlePaste}
                placeholder={isTeamChat ? `${resolvedPlaceholder} (${t('messageInput.inlineMentionHint')})` : resolvedPlaceholder}
                disabled={disabled}
                rows={1}
                className="w-full resize-none bg-transparent px-1 py-1 text-[15px] leading-7 text-slate-800 outline-none placeholder:text-slate-400 disabled:cursor-not-allowed disabled:opacity-50"
              />

              <div className="mt-2 flex flex-wrap items-center justify-between gap-2 px-1 text-xs text-slate-500">
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={disabled || hasPendingUploads}
                    className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
                    aria-label={t('messageInput.addAttachment')}
                    title={t('messageInput.addAttachment')}
                  >
                    <Paperclip className="h-4 w-4" strokeWidth={2} />
                  </button>
                  <button
                    type="button"
                    onClick={handleVoiceInputToggle}
                    disabled={disabled}
                    className={`inline-flex h-9 w-9 items-center justify-center rounded-full border transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                      isRecording
                        ? 'border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100'
                        : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-100'
                    }`}
                    aria-label={isRecording ? t('messageInput.stopVoiceInput') : t('messageInput.startVoiceInput')}
                    title={speechRecognitionCtor ? (isRecording ? t('messageInput.stopVoiceInput') : t('messageInput.startVoiceInput')) : t('messageInput.browserSpeechUnsupported')}
                  >
                    {isRecording ? (
                      <Square className="h-4 w-4" strokeWidth={2} />
                    ) : (
                      <Mic className="h-4 w-4" strokeWidth={2} />
                    )}
                  </button>
                  <span className="inline-flex items-center rounded-full border border-slate-200 bg-white px-2 py-1">
                    {t('messageInput.shortcutEnter')}
                  </span>
                  <span className="inline-flex items-center rounded-full border border-slate-200 bg-white px-2 py-1">
                    {t('messageInput.shortcutPaste')}
                  </span>
                  <span className="inline-flex items-center rounded-full border border-slate-200 bg-white px-2 py-1">
                    {t('messageInput.shortcutLimit', { count: MAX_ATTACHMENT_COUNT })}
                  </span>
                  {isTeamChat && (
                    <span className="inline-flex items-center rounded-full border border-violet-200 bg-violet-50 px-2 py-1 text-violet-700">
                      {t('messageInput.shortcutNextBaton')}
                    </span>
                  )}
                </div>
                <span>
                  {hasPendingUploads
                    ? t('messageInput.uploadingRemaining', { count: uploadingCount })
                    : failedCount > 0
                      ? t('messageInput.failedUploadHint', { count: failedCount })
                    : canInterruptAndSend
                      ? t('messageInput.stopAndSendHint')
                      : (isTeamChat ? t('messageInput.teamSupportHint') : t('messageInput.directSupportHint'))}
                </span>
              </div>
            </div>

            <div className="flex flex-col items-center gap-2">
              <button
                type="button"
                onClick={handleSend}
                disabled={disabled || (!message.trim() && readyAttachments.length === 0) || hasPendingUploads}
                className={`inline-flex h-14 w-14 items-center justify-center rounded-2xl text-sm font-semibold text-white shadow-sm transition-all disabled:cursor-not-allowed disabled:bg-slate-300 ${
                  canInterruptAndSend
                    ? 'bg-amber-500 hover:bg-amber-600'
                    : 'bg-blue-500 hover:bg-blue-600'
                }`}
                aria-label={canInterruptAndSend ? t('messageInput.stopAndSend') : t('messageInput.sendMessage')}
                title={canInterruptAndSend ? t('messageInput.stopAndSend') : t('messageInput.sendMessage')}
              >
                {canInterruptAndSend ? (
                  <Square className="h-4 w-4" strokeWidth={2} />
                ) : (
                  <SendHorizonal className="h-4 w-4" strokeWidth={2} />
                )}
              </button>
              <span className="text-[11px] text-slate-400">
                {canInterruptAndSend ? t('messageInput.afterStopSend') : t('messageInput.send')}
              </span>
            </div>
          </div>

          <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 rounded-[18px] bg-slate-50 px-3 py-2 text-xs text-slate-500">
            <span>
              {isTeamChat
                ? t('messageInput.teamFooterHint')
                : t('messageInput.directFooterHint')}
            </span>
            <span>{disabled ? t('messageInput.offline') : t('messageInput.ready')}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default memo(MessageInput);
