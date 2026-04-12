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

const getStatusActionIcon = (label?: string) => {
  if (!label) return <Info className="h-4 w-4" strokeWidth={2} />;
  if (label.includes('重试')) return <RotateCcw className="h-4 w-4" strokeWidth={2} />;
  if (label.includes('继续输入')) return <PencilLine className="h-4 w-4" strokeWidth={2} />;
  if (label.includes('停止')) return <Square className="h-4 w-4" strokeWidth={2} />;
  if (label.includes('继续')) return <SendHorizonal className="h-4 w-4" strokeWidth={2} />;
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

const inferDocumentPromptLabel = (attachments: ComposerAttachment[]): string => {
  const names = attachments.map((attachment) => attachment.originalName.toLowerCase());
  const hasPdf = names.some((name) => name.endsWith('.pdf'));
  const hasDocx = names.some((name) => name.endsWith('.docx'));
  const hasPptx = names.some((name) => name.endsWith('.pptx'));
  const hasXlsx = names.some((name) => name.endsWith('.xlsx'));

  const labels = [
    hasPdf ? 'PDF 文档' : null,
    hasDocx ? 'Word 文档' : null,
    hasXlsx ? 'Excel 表格' : null,
    hasPptx ? 'PowerPoint 演示文稿' : null,
  ].filter((label): label is string => Boolean(label));

  if (labels.length === 1) {
    return labels[0];
  }
  if (labels.length === 2) {
    return `${labels[0]}和${labels[1]}`;
  }
  if (labels.length === 3) {
    return `${labels[0]}、${labels[1]}和${labels[2]}`;
  }
  if (labels.length >= 4) {
    return '办公文档附件';
  }
  return '文档附件';
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
): { accepted: File[]; errorMessage?: string } => {
  if (selectedFiles.length === 0) {
    return { accepted: [] };
  }

  if (existingCount + selectedFiles.length > MAX_ATTACHMENT_COUNT) {
    return {
      accepted: [],
      errorMessage: `单次最多保留 ${MAX_ATTACHMENT_COUNT} 个附件，请先移除一部分再继续上传。`,
    };
  }

  const oversized = selectedFiles.find((file) => file.size > MAX_ATTACHMENT_SIZE_BYTES);
  if (oversized) {
    return {
      accepted: [],
      errorMessage: `文件 ${oversized.name} 超过 50 MB，当前不支持上传。`,
    };
  }

  return { accepted: selectedFiles };
};

const revokeObjectPreview = (previewUrl?: string) => {
  if (previewUrl && previewUrl.startsWith('blob:')) {
    URL.revokeObjectURL(previewUrl);
  }
};

const buildAttachmentPreviewText = (attachment: ComposerAttachment): string => {
  const extractedText = attachment.extractedText?.trim();
  if (extractedText) {
    return extractedText.replace(/\s+/g, ' ').slice(0, 140);
  }

  const lowerName = attachment.originalName.toLowerCase();
  if (lowerName.endsWith('.pdf')) return 'PDF 文档已上传，发送后可让 Agent 直接阅读并总结。';
  if (lowerName.endsWith('.docx')) return 'Word 文档已上传，发送后可继续追问段落、摘要或改写。';
  if (lowerName.endsWith('.xlsx')) return 'Excel 表格已上传，发送后可让 Agent 总结表格内容与关键数据。';
  if (lowerName.endsWith('.pptx')) return 'PowerPoint 已上传，发送后可让 Agent 总结每页重点。';
  if (attachment.category === 'audio') return '音频已上传，发送后可让 Agent 转写并分析内容。';
  if (attachment.category === 'image') return '图片已上传，发送后可让 Agent 识别图像内容。';
  return '附件已上传，发送后可让 Agent 继续分析。';
};

const getAttachmentKindLabel = (attachment: ComposerAttachment): string => {
  const lowerName = attachment.originalName.toLowerCase();
  if (attachment.category === 'image') return '图片';
  if (attachment.category === 'audio') return '音频';
  if (lowerName.endsWith('.pdf')) return 'PDF';
  if (lowerName.endsWith('.docx')) return 'Word';
  if (lowerName.endsWith('.xlsx')) return 'Excel';
  if (lowerName.endsWith('.pptx')) return 'PowerPoint';
  if (lowerName.endsWith('.md')) return 'Markdown';
  if (lowerName.endsWith('.txt')) return '文本';
  return '文件';
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

const buildDefaultAttachmentPrompt = (attachments: ComposerAttachment[]): string => {
  if (attachments.length === 0) {
    return '';
  }
  const categories = new Set(attachments.map((attachment) => attachment.category));
  if (categories.has('audio')) {
    return '请先分析我上传的音频内容，并结合其他附件给出结论。';
  }
  if (categories.has('image')) {
    return '请先分析我上传的图片内容，并结合其他附件给出结论。';
  }
  if (categories.has('document')) {
    return `请先分析我上传的${inferDocumentPromptLabel(attachments)}，并告诉我关键信息。`;
  }
  return '请先分析我上传的附件，并告诉我关键信息。';
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
  placeholder = '输入消息...',
  isLoading = false,
  sessionStatus = null,
  focusRequestKey = 0,
  draftPresetText = '',
  draftPresetKey = 0,
}) => {
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
      toast.success(`已添加 ${uploadedFiles.length} 个附件`);
    } catch (error) {
      console.error('Failed to upload files:', error);
      const errorMessage = error instanceof Error ? error.message : '附件上传失败，请重试';
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
      toast.warning('没有可重试的附件');
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
        ? (result.reason instanceof Error ? result.reason.message : '附件上传失败，请重试')
        : '附件上传失败，请重试';
      errorMap.set(attachmentId, reason);
    });

    setAttachments((prev) => prev.map((item) => {
      const uploaded = successMap.get(item.fileId);
      if (uploaded) {
        return {
          fileId: uploaded.file_id,
          filename: uploaded.filename,
          originalName: uploaded.original_name,
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
      toast.success(`已重新上传 ${successMap.size} 个附件`);
    } else if (successMap.size > 0) {
      toast.warning(`已重新上传 ${successMap.size} 个附件，仍有 ${errorMap.size} 个失败`);
    } else {
      toast.error(errorMap.values().next().value || '附件上传失败，请重试');
    }
  }, [toast]);

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
    const validation = validateSelectedFiles(selectedFiles, attachmentsRef.current.length);
    if (validation.errorMessage) {
      toast.error(validation.errorMessage);
      return;
    }
    await uploadAttachments(validation.accepted);
  }, [toast, uploadAttachments]);

  const handlePaste = useCallback((event: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const clipboardFiles = Array.from(event.clipboardData?.files || []);
    if (clipboardFiles.length === 0) {
      return;
    }
    event.preventDefault();
    const validation = validateSelectedFiles(clipboardFiles, attachmentsRef.current.length);
    if (validation.errorMessage) {
      toast.error(validation.errorMessage);
      return;
    }
    void uploadAttachments(validation.accepted);
  }, [toast, uploadAttachments]);

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
    const validation = validateSelectedFiles(droppedFiles, attachmentsRef.current.length);
    if (validation.errorMessage) {
      toast.error(validation.errorMessage);
      return;
    }
    void uploadAttachments(validation.accepted);
  }, [disabled, toast, uploadAttachments]);

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
    const normalizedMessage = trimmedMessage || buildDefaultAttachmentPrompt(readyAttachments);
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
  }, [agents, isTeamChat, message, disabled, hasPendingUploads, mentionedAgents, onSend, readyAttachments]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (showMentionPicker) return;

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend, showMentionPicker]);

  const handleVoiceInputToggle = useCallback(() => {
    if (!speechRecognitionCtor) {
      toast.warning('当前浏览器不支持语音输入');
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
        toast.error(`语音输入失败: ${event.error}`);
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
      toast.error('无法开始语音输入，请稍后重试');
    }
  }, [isRecording, message, speechRecognitionCtor, syncMentionedAgentsFromText, toast]);

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
              <div className="text-sm font-semibold">松开即可上传到当前对话</div>
              <div className="text-xs text-blue-600">支持图片、音频、PDF、Word、Excel、PowerPoint 与文本文件</div>
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
              {isTeamChat ? '团队接力模式' : '单聊模式'}
            </span>
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600 shadow-sm">
              <span className="font-medium text-slate-500">当前会话</span>
              <span className="font-semibold text-slate-700">{conversationName}</span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {hasDraft && !isLoading && (
              <button
                type="button"
                onClick={handleClearDraft}
                className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 transition-colors hover:bg-slate-100"
                aria-label="清空草稿"
                title="清空草稿"
              >
                <Eraser className="h-4 w-4" strokeWidth={2} />
              </button>
            )}
          </div>
        </div>

        {sessionStatus && (
          <div
            data-testid="chat-session-status"
              className={`mt-2 flex flex-wrap items-center justify-between gap-3 rounded-2xl border px-4 py-2.5 text-sm shadow-sm ${
              sessionStatus.tone === 'error'
                ? 'border-red-200 bg-red-50 text-red-900'
                : sessionStatus.tone === 'warning'
                  ? 'border-amber-200 bg-amber-50 text-amber-900'
                  : sessionStatus.tone === 'success'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                    : 'border-sky-200 bg-sky-50 text-sky-900'
            }`}
          >
            <div className="flex min-w-0 items-center gap-2">
              <Info className="h-4 w-4 flex-shrink-0" strokeWidth={2} />
              <span data-testid="chat-session-status-message" className="min-w-0 truncate">{sessionStatus.message}</span>
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
                  aria-label="关闭"
                  title="关闭"
                >
                  <X className="h-4 w-4" strokeWidth={2} />
                </button>
              )}
            </div>
          </div>
        )}

        {sessionStatus?.tone === 'success' && hasDraft && (
          <p className="mt-2 text-xs text-emerald-700">
            当前草稿已保留，可直接发送，或改写后再发送。
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
              <span className="text-xs font-medium text-violet-700">本次将唤起</span>
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
                  <span className="text-xs font-medium text-slate-600">附件</span>
                  <span className="inline-flex items-center rounded-full bg-white px-2 py-0.5 text-[11px] text-slate-500">
                    {attachments.length} 项待发送
                  </span>
                  {readyAttachments.length > 0 && (
                    <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-700">
                      {readyAttachments.length} 个已就绪
                    </span>
                  )}
                  {uploadingCount > 0 && (
                    <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-[11px] text-amber-700">
                      {uploadingCount} 个上传中
                    </span>
                  )}
                  {failedCount > 0 && (
                    <span className="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-[11px] font-medium text-red-700">
                      {failedCount} 个失败
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
                      重试失败项
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={handleClearAttachments}
                    className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600 transition-colors hover:bg-slate-100"
                  >
                    <Trash2 className="h-3.5 w-3.5" strokeWidth={2} />
                    清空附件
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
                          aria-label={`将附件 ${attachment.originalName} 前移`}
                          title="前移"
                          disabled={attachments[0]?.fileId === attachment.fileId}
                        >
                          <ArrowLeft className="h-3 w-3" strokeWidth={2} />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleMoveAttachment(attachment.fileId, 'right')}
                          className="inline-flex h-6 w-6 items-center justify-center rounded-full transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
                          aria-label={`将附件 ${attachment.originalName} 后移`}
                          title="后移"
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
                        aria-label={`重试上传附件 ${attachment.originalName}`}
                        title="重试上传"
                      >
                        <RefreshCcw className="h-3 w-3" strokeWidth={2} />
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => handleRemoveAttachment(attachment.fileId)}
                      className="inline-flex h-6 w-6 items-center justify-center rounded-full transition-colors hover:bg-slate-100"
                      aria-label={`移除附件 ${attachment.originalName}`}
                      title="移除附件"
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
                          {getAttachmentKindLabel(attachment)}
                        </span>
                        <span className="text-[10px] opacity-80">
                          {attachment.uploadState === 'uploading'
                            ? '上传中...'
                            : attachment.errorMessage || formatFileSize(attachment.size)}
                        </span>
                      </div>
                      <div className="mt-1 line-clamp-2 text-[13px] font-medium leading-5">{attachment.originalName}</div>
                    </div>
                  </div>
                  <p className="mt-1.5 line-clamp-1 text-[11px] leading-5 text-slate-500">
                    {buildAttachmentPreviewText(attachment)}
                  </p>
                  {attachment.uploadState === 'error' && (
                    <p className="mt-1 text-[11px] leading-5 text-red-700">
                      上传失败，附件已保留，可直接重试。
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
                    {isTeamChat ? '@ 提及接力' : '直接对话'}
                  </span>
                  {canInterruptAndSend && (
                    <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-1 font-medium text-amber-700">
                      发送前会先停止当前接力
                    </span>
                  )}
                  {hasPendingUploads && (
                    <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-1 font-medium text-amber-700">
                      附件上传中
                    </span>
                  )}
                  {isRecording && (
                    <span className="inline-flex items-center rounded-full bg-rose-100 px-2 py-1 font-medium text-rose-700">
                      语音输入中
                    </span>
                  )}
                </div>
                <span className="px-1 text-xs text-slate-400">
                  {message.trim().length} 字
                  {readyAttachments.length > 0 ? ` · ${readyAttachments.length} 个附件` : ''}
                </span>
              </div>

              <textarea
                ref={textareaRef}
                value={message}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                onPaste={handlePaste}
                placeholder={isTeamChat ? `${placeholder}（输入 @ 可直接提及 Agent）` : placeholder}
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
                    aria-label="添加附件"
                    title="添加附件"
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
                    aria-label={isRecording ? '停止语音输入' : '开始语音输入'}
                    title={speechRecognitionCtor ? (isRecording ? '停止语音输入' : '开始语音输入') : '当前浏览器不支持语音输入'}
                  >
                    {isRecording ? (
                      <Square className="h-4 w-4" strokeWidth={2} />
                    ) : (
                      <Mic className="h-4 w-4" strokeWidth={2} />
                    )}
                  </button>
                  <span className="inline-flex items-center rounded-full border border-slate-200 bg-white px-2 py-1">
                    Enter 发送 / Shift + Enter 换行
                  </span>
                  <span className="inline-flex items-center rounded-full border border-slate-200 bg-white px-2 py-1">
                    Cmd/Ctrl + V 或拖拽上传
                  </span>
                  <span className="inline-flex items-center rounded-full border border-slate-200 bg-white px-2 py-1">
                    最多 10 个，单个 50 MB
                  </span>
                  {isTeamChat && (
                    <span className="inline-flex items-center rounded-full border border-violet-200 bg-violet-50 px-2 py-1 text-violet-700">
                      @ 指定下一棒
                    </span>
                  )}
                </div>
                <span>
                  {hasPendingUploads
                    ? `还有 ${uploadingCount} 个附件正在上传`
                    : failedCount > 0
                      ? `${failedCount} 个附件上传失败，可直接在卡片中重试`
                    : canInterruptAndSend
                      ? '停止当前接力后立即发出新消息'
                      : (isTeamChat ? '支持多 agent 连续接力，也支持发图/发音频/发文件/拖拽上传' : '支持发图、发音频、发文件、拖拽上传与语音输入')}
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
                aria-label={canInterruptAndSend ? '停止并发送' : '发送消息'}
                title={canInterruptAndSend ? '停止并发送' : '发送消息'}
              >
                {canInterruptAndSend ? (
                  <Square className="h-4 w-4" strokeWidth={2} />
                ) : (
                  <SendHorizonal className="h-4 w-4" strokeWidth={2} />
                )}
              </button>
              <span className="text-[11px] text-slate-400">
                {canInterruptAndSend ? '停止后发送' : '发送'}
              </span>
            </div>
          </div>

          <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 rounded-[18px] bg-slate-50 px-3 py-2 text-xs text-slate-500">
            <span>
              {isTeamChat
                ? '建议直接点名 agent，让接力路径更短、更可控；支持上传、粘贴、拖拽图片/音频/办公文件，并在发送前调整顺序。'
                : '可直接上传、粘贴或拖拽图片、音频、PDF、Word、Excel、PowerPoint；只发附件时会自动补一条分析请求。'}
            </span>
            <span>{disabled ? '当前离线' : '聊天已就绪'}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default memo(MessageInput);
