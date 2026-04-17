import React, { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowUpRight, BookMarked, ChevronDown, Copy, FileAudio2, FileImage, FileText, RotateCcw } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useToast } from '../contexts/ToastContext';
import { useI18n } from '../contexts/I18nContext';
import MarkdownRenderer from './MarkdownRenderer';
import { Modal, ModalFooter } from './ui';
import type { MemoryRecall, MemorySource, Message, MessageFile } from '../types/conversation';

interface MessageGroupProps {
  messages: Message[];
  agentName?: string;
  agentId?: string;
  isUser: boolean;
  formatTime: (timestamp?: string) => string;
  onRetryMessage?: (message: Message) => void;
  showRetryPending?: boolean;
  children?: React.ReactNode;
}

type AttachmentFile = MessageFile;
type TranslateFn = (key: string, values?: Record<string, string | number>) => string;

const AVATAR_COLORS = [
  'from-blue-500 to-cyan-500',
  'from-emerald-500 to-teal-500',
  'from-orange-500 to-amber-500',
  'from-fuchsia-500 to-pink-500',
  'from-indigo-500 to-violet-500',
];

const getAvatarColor = (id: string): string => {
  const index = Math.abs(
    id.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
  ) % AVATAR_COLORS.length;
  return AVATAR_COLORS[index];
};

const stripMessageTags = (content: string): string => {
  if (!content) return content;
  return content
    .replace(/<message\s+from="[^"]*"(?:\s+to="[^"]*")?>\s*/gi, '')
    .replace(/<\/message>\s*/gi, '')
    .trim();
};

const coerceMemorySources = (value: unknown): MemorySource[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is Record<string, unknown> => !!item && typeof item === 'object')
    .map((item) => ({
      category: typeof item.category === 'string' ? item.category : undefined,
      level: typeof item.level === 'string' ? item.level : 'L2',
      file: typeof item.file === 'string' ? item.file : undefined,
      path: typeof item.path === 'string' ? item.path : undefined,
      title: typeof item.title === 'string' ? item.title : undefined,
      snippet: typeof item.snippet === 'string' ? item.snippet : undefined,
      relevance: typeof item.relevance === 'number' ? item.relevance : undefined,
      reasons: Array.isArray(item.reasons) ? item.reasons.filter((reason): reason is string => typeof reason === 'string') : [],
      matched_terms: Array.isArray(item.matched_terms) ? item.matched_terms.filter((term): term is string => typeof term === 'string') : [],
      section_index: typeof item.section_index === 'number' ? item.section_index : undefined,
      origin: typeof item.origin === 'string' ? item.origin : undefined,
      owner_id: typeof item.owner_id === 'string' ? item.owner_id : undefined,
      scope: typeof item.scope === 'string' ? item.scope : undefined,
      scope_label: typeof item.scope_label === 'string' ? item.scope_label : undefined,
    }));
};

const coerceMemoryRecall = (value: unknown): MemoryRecall | null => {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const item = value as Record<string, unknown>;
  return {
    timestamp: typeof item.timestamp === 'string' ? item.timestamp : undefined,
    latency_ms: typeof item.latency_ms === 'number' ? item.latency_ms : undefined,
    candidates_count: typeof item.candidates_count === 'number' ? item.candidates_count : undefined,
    selected_count: typeof item.selected_count === 'number' ? item.selected_count : undefined,
    query: typeof item.query === 'string' ? item.query : undefined,
    selected_memory_ids: Array.isArray(item.selected_memory_ids) ? item.selected_memory_ids.filter((entry): entry is string => typeof entry === 'string') : undefined,
  };
};

const coerceProviderRemediation = (value: unknown): string[] => {
  if (!value || typeof value !== 'object') {
    return [];
  }
  const remediation = (value as Record<string, unknown>).remediation;
  if (!Array.isArray(remediation)) {
    return [];
  }
  return remediation.filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
};

const coerceProviderDiagnostic = (value: unknown): {
  errorCode?: string;
  errorKind?: string;
  provider?: string;
  model?: string;
  statusCode?: number;
} | null => {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const item = value as Record<string, unknown>;
  return {
    errorCode: typeof item.error_code === 'string' ? item.error_code : undefined,
    errorKind: typeof item.error_kind === 'string' ? item.error_kind : undefined,
    provider: typeof item.provider === 'string' ? item.provider : undefined,
    model: typeof item.model === 'string' ? item.model : undefined,
    statusCode: typeof item.status_code === 'number' ? item.status_code : undefined,
  };
};

const getErrorKindMeta = (t: TranslateFn): Record<NonNullable<Message['errorKind']>, { label: string; tone: string }> => ({
  provider: { label: t('messageGroup.errorKind.provider'), tone: 'bg-amber-100 text-amber-800 border-amber-200' },
  network: { label: t('messageGroup.errorKind.network'), tone: 'bg-sky-100 text-sky-800 border-sky-200' },
  timeout: { label: t('messageGroup.errorKind.timeout'), tone: 'bg-orange-100 text-orange-800 border-orange-200' },
  stream: { label: t('messageGroup.errorKind.stream'), tone: 'bg-red-100 text-red-800 border-red-200' },
});

const getMemoryCategoryMeta = (category: string | undefined, t: TranslateFn): { label: string; tone: string } => {
  switch ((category || '').toLowerCase()) {
    case 'reflection':
      return { label: t('messageGroup.memoryCategory.reflection'), tone: 'bg-violet-50 text-violet-700' };
    case 'team':
      return { label: t('messageGroup.memoryCategory.team'), tone: 'bg-emerald-50 text-emerald-700' };
    case 'recent':
      return { label: t('messageGroup.memoryCategory.recent'), tone: 'bg-blue-50 text-blue-700' };
    case 'long_term':
      return { label: t('messageGroup.memoryCategory.longTerm'), tone: 'bg-cyan-50 text-cyan-700' };
    default:
      return { label: category || t('messageGroup.memoryCategory.default'), tone: 'bg-slate-100 text-slate-700' };
  }
};

const getOriginMeta = (source: MemorySource, t: TranslateFn): { label: string; tone: string } | null => {
  if (source.origin === 'team_shared' || source.category === 'team') {
    return { label: t('messageGroup.origin.team', { owner: source.owner_id || '' }).trim(), tone: 'bg-emerald-50 text-emerald-700' };
  }
  if (source.category === 'reflection') {
    return { label: t('messageGroup.origin.reflect'), tone: 'bg-violet-50 text-violet-700' };
  }
  if (source.origin) {
    return { label: source.origin, tone: 'bg-slate-100 text-slate-700' };
  }
  return null;
};

const rankReason = (reason: string): number => {
  if (reason.includes('关键词')) return 0;
  if (reason.includes('团队') || reason.includes('交接') || reason.includes('阻塞')) return 1;
  if (reason.includes('策略') || reason.includes('观察')) return 2;
  return 3;
};

const sortReasons = (reasons: string[] = []): string[] =>
  [...reasons].sort((a, b) => rankReason(a) - rankReason(b) || a.localeCompare(b, 'zh-CN'));

const previewSnippet = (snippet?: string, maxChars: number = 132): { preview: string; expanded: boolean } => {
  if (!snippet) {
    return { preview: '', expanded: false };
  }
  if (snippet.length <= maxChars) {
    return { preview: snippet, expanded: false };
  }
  return { preview: `${snippet.slice(0, maxChars).trimEnd()}...`, expanded: true };
};

const getSourceFileName = (source: MemorySource | null): string => {
  if (!source) {
    return '';
  }
  const raw = source.file || source.path || '';
  const normalized = raw.split(/[\\/]/).pop() || raw;
  return normalized.trim().toLowerCase();
};

const getSourceTypeDescription = (source: MemorySource | null, t: TranslateFn): string => {
  if (!source) {
    return '';
  }
  const fileName = getSourceFileName(source);
  if (source.category === 'team') {
    return t('messageGroup.sourceType.team');
  }
  if (fileName === 'soul.md') {
    return t('messageGroup.sourceType.soul');
  }
  if (fileName === 'user.md') {
    return t('messageGroup.sourceType.user');
  }
  if (fileName === 'reflection.md' || source.category === 'reflection') {
    return t('messageGroup.sourceType.reflection');
  }
  if (fileName === 'memory.md' || fileName === 'history.md') {
    return t('messageGroup.sourceType.memory');
  }
  return t('messageGroup.sourceType.default');
};

const buildMemorySummaryText = (source: MemorySource | null, t: TranslateFn): string => {
  if (!source) {
    return '';
  }
  const lines = [
    `${t('messageGroup.summary.title')}: ${source.title || source.file || t('messageGroup.unnamedMemory')}`,
    `${t('messageGroup.summary.level')}: ${source.level}`,
    ...(source.category ? [`${t('messageGroup.summary.category')}: ${source.category}`] : []),
    ...(source.scope_label ? [`${t('messageGroup.summary.scope')}: ${source.scope_label}`] : []),
    ...(source.owner_id ? [`${t('messageGroup.summary.owner')}: ${source.owner_id}`] : []),
    ...(source.reasons?.length ? [`${t('messageGroup.summary.reasons')}: ${sortReasons(source.reasons).join(' / ')}`] : []),
    ...(source.matched_terms?.length ? [`${t('messageGroup.summary.matchedTerms')}: ${source.matched_terms.join(', ')}`] : []),
    ...(source.snippet ? [`${t('messageGroup.summary.snippet')}: ${source.snippet}`] : []),
  ];
  return lines.join('\n');
};

const buildMemoryContextText = (source: MemorySource | null): string => {
  if (!source) {
    return '';
  }
  return [
    '[Memory Reference Context]',
    `source_title=${source.title || source.file || 'unknown'}`,
    `source_level=${source.level}`,
    `source_category=${source.category || 'memory'}`,
    `source_scope=${source.scope_label || source.scope || 'n/a'}`,
    `source_owner=${source.owner_id || 'n/a'}`,
    `source_path=${source.path || source.file || 'n/a'}`,
    `reasons=${sortReasons(source.reasons).join(' | ') || 'n/a'}`,
    `matched_terms=${source.matched_terms?.join(', ') || 'n/a'}`,
    'snippet:',
    source.snippet || 'n/a',
  ].join('\n');
};

const buildMemoryHandoffText = (source: MemorySource | null, t: TranslateFn): string => {
  if (!source) {
    return '';
  }
  return [
    '[Relay Handoff]',
    `${t('messageGroup.handoff.continueFrom')}: ${source.title || source.file || 'unknown'}`,
    `${t('messageGroup.handoff.level')}: ${source.level}`,
    `${t('messageGroup.handoff.category')}: ${source.category || 'memory'}`,
    `${t('messageGroup.handoff.scope')}: ${source.scope_label || source.scope || 'n/a'}`,
    `${t('messageGroup.handoff.owner')}: ${source.owner_id || 'n/a'}`,
    `${t('messageGroup.handoff.reasons')}: ${sortReasons(source.reasons).join(' / ') || 'n/a'}`,
    `${t('messageGroup.handoff.matchedTerms')}: ${source.matched_terms?.join(', ') || 'n/a'}`,
    `${t('messageGroup.handoff.path')}: ${source.path || source.file || 'n/a'}`,
    `${t('messageGroup.handoff.referenceSnippet')}:`,
    source.snippet || 'n/a',
    `${t('messageGroup.handoff.pleaseOutput')}:`,
    `1. ${t('messageGroup.handoff.output1')}`,
    `2. ${t('messageGroup.handoff.output2')}`,
    `3. ${t('messageGroup.handoff.output3')}`,
  ].join('\n');
};

const formatFileSize = (size: number): string => {
  if (!Number.isFinite(size) || size <= 0) {
    return '';
  }
  if (size >= 1024 * 1024) {
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  }
  if (size >= 1024) {
    return `${Math.round(size / 1024)} KB`;
  }
  return `${size} B`;
};

const getFileKindLabel = (file: NonNullable<Message['files']>[number], t: TranslateFn): string => {
  const name = file.originalName.toLowerCase();
  if (file.category === 'image') return t('messageGroup.fileKind.image');
  if (file.category === 'audio') return t('messageGroup.fileKind.audio');
  if (name.endsWith('.pdf')) return 'PDF';
  if (name.endsWith('.docx')) return 'Word';
  if (name.endsWith('.xlsx')) return 'Excel';
  if (name.endsWith('.pptx')) return 'PowerPoint';
  if (name.endsWith('.md')) return t('messageGroup.fileKind.markdown');
  if (name.endsWith('.txt')) return t('messageGroup.fileKind.text');
  return t('messageGroup.fileKind.file');
};

const getFilePreviewText = (file: NonNullable<Message['files']>[number], t: TranslateFn): string => {
  const extractedText = file.extractedText?.trim();
  if (extractedText) {
    return extractedText.replace(/\s+/g, ' ').slice(0, 160);
  }
  if (file.category === 'audio') {
    return t('messageGroup.filePreview.audio');
  }
  if (file.category === 'image') {
    return t('messageGroup.filePreview.image');
  }
  return t('messageGroup.filePreview.default');
};

const isPdfFile = (file: AttachmentFile): boolean =>
  file.mimeType === 'application/pdf' || file.originalName.toLowerCase().endsWith('.pdf');

const isInlineOfficePreviewFile = (file: AttachmentFile): boolean => {
  const name = file.originalName.toLowerCase();
  return name.endsWith('.docx') || name.endsWith('.pptx');
};

const isOfficeFile = (file: AttachmentFile): boolean => {
  const name = file.originalName.toLowerCase();
  return name.endsWith('.docx') || name.endsWith('.xlsx') || name.endsWith('.pptx');
};

const isLocalUploadedFileUrl = (value: string): boolean =>
  /\/api\/files\/[^/?#]+$/i.test(value);

const buildDerivedPreviewUrl = (value: string): string => {
  if (!value || value.endsWith('/preview') || !isLocalUploadedFileUrl(value)) {
    return value;
  }
  return `${value}/preview`;
};

const getFilePreviewUrl = (file: AttachmentFile): string => {
  if (file.localPreview) {
    return file.localPreview;
  }
  if (file.previewUrl) {
    return file.previewUrl;
  }
  const rawUrl = file.url || '';
  if (!rawUrl) {
    return '';
  }
  if (isPdfFile(file) || isInlineOfficePreviewFile(file)) {
    return buildDerivedPreviewUrl(rawUrl);
  }
  return rawUrl;
};

const isTextLikeFile = (file: AttachmentFile): boolean =>
  file.mimeType.startsWith('text/')
  || file.mimeType === 'application/json'
  || file.mimeType === 'application/xml'
  || file.originalName.toLowerCase().endsWith('.md')
  || file.originalName.toLowerCase().endsWith('.txt');

const getFilePreviewModalSize = (file: AttachmentFile | null): 'lg' | 'full' => {
  if (!file) {
    return 'lg';
  }
  return file.category === 'image' || isPdfFile(file) || isInlineOfficePreviewFile(file) ? 'full' : 'lg';
};

const renderFilePreviewContent = (file: AttachmentFile, t: TranslateFn): React.ReactNode => {
  const previewUrl = getFilePreviewUrl(file);
  const extractedText = file.extractedText?.trim();

  if (file.category === 'image' && previewUrl) {
    return (
      <div className="flex justify-center rounded-3xl bg-slate-100 p-3">
        <img
          src={previewUrl}
          alt={file.originalName}
          className="max-h-[72vh] w-auto max-w-full rounded-2xl object-contain shadow-sm"
        />
      </div>
    );
  }

  if (file.category === 'audio' && previewUrl) {
    return (
      <div className="space-y-4">
        <div className="rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-700">
            <FileAudio2 className="h-4 w-4" strokeWidth={2} />
            <span className="truncate">{file.originalName}</span>
          </div>
          <audio controls className="w-full" autoPlay>
            <source src={previewUrl} type={file.mimeType} />
          </audio>
        </div>
        {extractedText ? (
          <div>
            <div className="mb-2 text-sm font-semibold text-slate-800">{t('messageGroup.filePreview.transcript')}</div>
            <pre className="max-h-[40vh] overflow-auto rounded-2xl border border-slate-200 bg-white px-4 py-3 whitespace-pre-wrap break-words text-sm text-slate-700">
              {extractedText}
            </pre>
          </div>
        ) : null}
      </div>
    );
  }

  if (isPdfFile(file) && previewUrl) {
    return (
      <iframe
        src={previewUrl}
        title={file.originalName}
        className="h-[72vh] w-full rounded-2xl border border-slate-200 bg-white"
      />
    );
  }

  if (isInlineOfficePreviewFile(file) && previewUrl) {
    return (
      <iframe
        src={previewUrl}
        title={file.originalName}
        className="h-[72vh] w-full rounded-2xl border border-slate-200 bg-white"
      />
    );
  }

  if ((isOfficeFile(file) || isTextLikeFile(file)) && extractedText) {
    return (
      <div className="space-y-3">
        {isOfficeFile(file) && (
          <div className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            {t('messageGroup.filePreview.officeNotice')}
          </div>
        )}
        <pre className="max-h-[68vh] overflow-auto rounded-2xl border border-slate-200 bg-white px-4 py-3 whitespace-pre-wrap break-words text-sm text-slate-700">
          {extractedText}
        </pre>
      </div>
    );
  }

  if (isTextLikeFile(file) && previewUrl) {
    return (
      <iframe
        src={previewUrl}
        title={file.originalName}
        className="h-[68vh] w-full rounded-2xl border border-slate-200 bg-white"
      />
    );
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-600">
      {t('messageGroup.filePreview.unsupported')}
    </div>
  );
};

const MessageGroup: React.FC<MessageGroupProps> = ({
  messages,
  agentName,
  agentId,
  isUser,
  formatTime,
  onRetryMessage,
  showRetryPending = false,
  children,
}) => {
  const { t } = useI18n();
  const toast = useToast();
  const navigate = useNavigate();
  const avatarColor = agentId ? getAvatarColor(agentId) : 'from-blue-500 to-cyan-500';
  const [inspectedSource, setInspectedSource] = useState<MemorySource | null>(null);
  const [previewedFile, setPreviewedFile] = useState<AttachmentFile | null>(null);
  const errorKindMeta = useMemo(() => getErrorKindMeta(t), [t]);
  const previewableImageFiles = useMemo(
    () => messages.flatMap((message) => (
      (message.files || []).filter((file) => file.category === 'image' && Boolean(getFilePreviewUrl(file)))
    )),
    [messages]
  );
  const previewedImageIndex = useMemo(
    () => (
      previewedFile
      && previewedFile.category === 'image'
      ? previewableImageFiles.findIndex((file) => file.fileId === previewedFile.fileId)
      : -1
    ),
    [previewableImageFiles, previewedFile]
  );
  const canPreviewPreviousImage = previewedImageIndex > 0;
  const canPreviewNextImage = previewedImageIndex >= 0 && previewedImageIndex < previewableImageFiles.length - 1;

  const inspectedSourceOrigin = useMemo(() => {
    if (!inspectedSource) {
      return null;
    }
    return getOriginMeta(inspectedSource, t);
  }, [inspectedSource, t]);

  const handleCopy = useCallback(async (message: Message) => {
    try {
      await navigator.clipboard.writeText(stripMessageTags(message.content || ''));
      toast.success(t('messageGroup.toast.messageCopied'));
    } catch (error) {
      console.error('Failed to copy message:', error);
      toast.error(t('messageGroup.toast.copyFailed'));
    }
  }, [t, toast]);

  const handleOpenMemorySource = useCallback((source: MemorySource) => {
    setInspectedSource(source);
  }, []);

  const handleOpenFilePreview = useCallback((file: AttachmentFile) => {
    const previewUrl = getFilePreviewUrl(file);
    if (!previewUrl && !file.extractedText?.trim()) {
      toast.error(t('messageGroup.toast.previewUnavailable'));
      return;
    }
    setPreviewedFile(file);
  }, [t, toast]);

  const handleOpenOriginalFile = useCallback(() => {
    if (!previewedFile) {
      return;
    }
    const targetUrl = previewedFile.url || getFilePreviewUrl(previewedFile);
    if (!targetUrl) {
      toast.error(t('messageGroup.toast.noOriginalFile'));
      return;
    }
    window.open(targetUrl, '_blank', 'noopener,noreferrer');
  }, [previewedFile, t, toast]);

  const handlePreviewPreviousImage = useCallback(() => {
    if (!canPreviewPreviousImage) {
      return;
    }
    setPreviewedFile(previewableImageFiles[previewedImageIndex - 1] || null);
  }, [canPreviewPreviousImage, previewableImageFiles, previewedImageIndex]);

  const handlePreviewNextImage = useCallback(() => {
    if (!canPreviewNextImage) {
      return;
    }
    setPreviewedFile(previewableImageFiles[previewedImageIndex + 1] || null);
  }, [canPreviewNextImage, previewableImageFiles, previewedImageIndex]);

  const handleSelectPreviewImage = useCallback((index: number) => {
    setPreviewedFile(previewableImageFiles[index] || null);
  }, [previewableImageFiles]);

  useEffect(() => {
    if (previewedImageIndex < 0) {
      return undefined;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'ArrowLeft' && canPreviewPreviousImage) {
        event.preventDefault();
        setPreviewedFile(previewableImageFiles[previewedImageIndex - 1] || null);
      } else if (event.key === 'ArrowRight' && canPreviewNextImage) {
        event.preventDefault();
        setPreviewedFile(previewableImageFiles[previewedImageIndex + 1] || null);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [canPreviewNextImage, canPreviewPreviousImage, previewableImageFiles, previewedImageIndex]);

  const handleNavigateToSource = useCallback(() => {
    if (!inspectedSource) {
      return;
    }
    const sourceFileName = getSourceFileName(inspectedSource);
    if (inspectedSource.category === 'team' && inspectedSource.owner_id) {
      const focus =
        inspectedSource.scope === 'shared_constraints'
          ? 'team-workspace'
          : inspectedSource.scope === 'team_decisions'
            ? 'team-members'
            : 'team-collaboration';
      navigate(`/teams?team=${encodeURIComponent(inspectedSource.owner_id)}&focus=${focus}`);
      setInspectedSource(null);
      return;
    }
    if (agentId) {
      let focus = 'agent-runtime';
      if (sourceFileName === 'soul.md') {
        focus = 'agent-file-soul';
      } else if (sourceFileName === 'user.md') {
        focus = 'agent-file-user';
      } else if (sourceFileName === 'reflection.md' || inspectedSource.category === 'reflection') {
        focus = 'agent-summary';
      } else if (sourceFileName === 'memory.md' || sourceFileName === 'history.md') {
        focus = 'agent-runtime';
      }
      navigate(`/teams?agent=${encodeURIComponent(agentId)}&focus=${focus}`);
      setInspectedSource(null);
    }
  }, [agentId, inspectedSource, navigate]);

  const handleOpenSourceChat = useCallback(() => {
    if (!inspectedSource) {
      return;
    }
    if (inspectedSource.category === 'team' && inspectedSource.owner_id) {
      navigate(`/chat?team=${encodeURIComponent(inspectedSource.owner_id)}`);
      setInspectedSource(null);
      return;
    }
    if (agentId) {
      navigate(`/chat?agent=${encodeURIComponent(agentId)}`);
      setInspectedSource(null);
    }
  }, [agentId, inspectedSource, navigate]);

  const handleCopySourcePath = useCallback(async () => {
    if (!inspectedSource) {
      return;
    }
    const pathText = inspectedSource.path || inspectedSource.file;
    if (!pathText) {
      toast.error(t('messageGroup.toast.noSourcePath'));
      return;
    }
    try {
      await navigator.clipboard.writeText(pathText);
      toast.success(t('messageGroup.toast.sourcePathCopied'));
    } catch (error) {
      console.error('Failed to copy source path:', error);
      toast.error(t('messageGroup.toast.copySourcePathFailed'));
    }
  }, [inspectedSource, t, toast]);

  const handleCopySourceSummary = useCallback(async () => {
    const content = buildMemorySummaryText(inspectedSource, t);
    if (!content) {
      toast.error(t('messageGroup.toast.noSummary'));
      return;
    }
    try {
      await navigator.clipboard.writeText(content);
      toast.success(t('messageGroup.toast.summaryCopied'));
    } catch (error) {
      console.error('Failed to copy source summary:', error);
      toast.error(t('messageGroup.toast.copySummaryFailed'));
    }
  }, [inspectedSource, t, toast]);

  const handleCopySourceContext = useCallback(async () => {
    const content = buildMemoryContextText(inspectedSource);
    if (!content) {
      toast.error(t('messageGroup.toast.noContext'));
      return;
    }
    try {
      await navigator.clipboard.writeText(content);
      toast.success(t('messageGroup.toast.contextCopied'));
    } catch (error) {
      console.error('Failed to copy source context:', error);
      toast.error(t('messageGroup.toast.copyContextFailed'));
    }
  }, [inspectedSource, t, toast]);

  const handleCopySourceHandoff = useCallback(async () => {
    const content = buildMemoryHandoffText(inspectedSource, t);
    if (!content) {
      toast.error(t('messageGroup.toast.noHandoff'));
      return;
    }
    try {
      await navigator.clipboard.writeText(content);
      toast.success(t('messageGroup.toast.handoffCopied'));
    } catch (error) {
      console.error('Failed to copy source handoff:', error);
      toast.error(t('messageGroup.toast.copyHandoffFailed'));
    }
  }, [inspectedSource, t, toast]);

  const inspectedSourceTargetLabel = useMemo(() => {
    if (!inspectedSource) {
      return '';
    }
    if (inspectedSource.category === 'team' && inspectedSource.owner_id) {
      return t('messageGroup.navigate.teamManagement');
    }
    if (agentId) {
      return t('messageGroup.navigate.agentManagement');
    }
    return '';
  }, [agentId, inspectedSource, t]);

  const inspectedSourceChatLabel = useMemo(() => {
    if (!inspectedSource) {
      return '';
    }
    if (inspectedSource.category === 'team' && inspectedSource.owner_id) {
      return t('messageGroup.navigate.teamChat');
    }
    if (agentId) {
      return t('messageGroup.navigate.agentChat');
    }
    return '';
  }, [agentId, inspectedSource, t]);

  const renderMessageFiles = useCallback((files?: Message['files'], isUserMessage?: boolean) => {
    if (!files || files.length === 0) {
      return null;
    }

    const imageFiles = files.filter((file) => file.category === 'image' && Boolean(file.localPreview || file.previewUrl || file.url));
    const otherFiles = files.filter((file) => !imageFiles.some((entry) => entry.fileId === file.fileId));
    const hasImageGrid = imageFiles.length > 1;
    const maxGridImages = 4;
    const visibleImageFiles = hasImageGrid ? imageFiles.slice(0, maxGridImages) : imageFiles;
    const hiddenImageCount = hasImageGrid ? Math.max(0, imageFiles.length - visibleImageFiles.length) : 0;

    return (
      <div className="inline-flex max-w-full flex-col gap-2 align-top" data-testid="message-file-list">
        {imageFiles.length > 0 && (
          <div
            className={hasImageGrid ? 'grid grid-cols-2 gap-2' : 'inline-flex max-w-full'}
            data-testid={hasImageGrid ? 'message-file-image-grid' : 'message-file-image-single'}
          >
            {visibleImageFiles.map((file, imageIndex) => {
              const previewUrl = file.localPreview || file.previewUrl || file.url;
              const cardTone = isUserMessage
                ? 'border-white/30 bg-white/15 text-white'
                : 'border-slate-200 bg-slate-50 text-slate-700';
              const showOverflowBadge = hiddenImageCount > 0 && imageIndex === visibleImageFiles.length - 1;
              const sizeLabel = formatFileSize(file.size);
              return (
                <button
                  key={file.fileId}
                  type="button"
                  onClick={() => handleOpenFilePreview(file)}
                  data-testid="message-file-open-preview"
                  className={`relative flex w-28 flex-col overflow-hidden rounded-2xl border ${cardTone} text-left shadow-sm transition-opacity hover:opacity-90`}
                >
                  <img
                    src={previewUrl}
                    alt={file.originalName}
                    className="h-28 w-28 object-cover"
                  />
                  {showOverflowBadge && (
                    <div
                      className="absolute inset-x-0 top-0 flex h-28 items-center justify-center bg-slate-950/50 text-base font-semibold text-white backdrop-blur-[1px]"
                      data-testid="message-file-image-overflow"
                    >
                      +{hiddenImageCount}
                    </div>
                  )}
                  <div className="min-h-[3.4rem] px-3 py-2 text-[11px]">
                    <div className="line-clamp-2 min-h-[2rem] font-medium leading-4">{file.originalName}</div>
                    {sizeLabel ? (
                      <div className={isUserMessage ? 'text-white/75' : 'text-slate-500'}>{sizeLabel}</div>
                    ) : null}
                  </div>
                </button>
              );
            })}
          </div>
        )}

        {otherFiles.length > 0 && (
          <div className="inline-flex max-w-full flex-wrap gap-2">
            {otherFiles.map((file) => {
              const cardTone = isUserMessage
                ? 'border-white/30 bg-white/15 text-white'
                : 'border-slate-200 bg-slate-50 text-slate-700';
              const sizeLabel = formatFileSize(file.size);
              if (file.category === 'audio' && file.url) {
                return (
                  <button
                    key={file.fileId}
                    type="button"
                    onClick={() => handleOpenFilePreview(file)}
                    data-testid="message-file-open-preview"
                    className={`min-w-[220px] rounded-2xl border px-3 py-3 text-left shadow-sm transition-opacity hover:opacity-90 ${cardTone}`}
                  >
                    <div className="mb-2 flex items-center gap-2 text-xs font-medium">
                      <FileAudio2 className="h-4 w-4" strokeWidth={2} />
                      <span className="truncate">{file.originalName}</span>
                    </div>
                    <div className={`rounded-2xl border px-3 py-3 text-xs ${isUserMessage ? 'border-white/20 bg-white/10 text-white/85' : 'border-slate-200 bg-white text-slate-500'}`}>
                      {t('messageGroup.filePreview.playAudio')}
                    </div>
                    {sizeLabel ? (
                      <div className={`mt-2 text-[11px] ${isUserMessage ? 'text-white/75' : 'text-slate-500'}`}>
                        {sizeLabel}
                      </div>
                    ) : null}
                  </button>
                );
              }

              return (
                <button
                  key={file.fileId}
                  type="button"
                  onClick={() => handleOpenFilePreview(file)}
                  data-testid="message-file-open-preview"
                  className={`flex min-w-[220px] max-w-[320px] flex-col items-start gap-3 rounded-2xl border px-3 py-3 text-left shadow-sm transition-colors hover:bg-white/20 ${cardTone}`}
                >
                  <div className="flex w-full items-start gap-3">
                    <span className={`inline-flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-2xl ${isUserMessage ? 'bg-white/15' : 'bg-white'}`}>
                      {file.category === 'image' ? <FileImage className="h-4 w-4" strokeWidth={2} /> : <FileText className="h-4 w-4" strokeWidth={2} />}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className={`mb-1 inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${isUserMessage ? 'bg-white/15 text-white/90' : 'bg-slate-200 text-slate-600'}`}>
                        {getFileKindLabel(file, t)}
                      </span>
                      <span className="block truncate text-sm font-medium">{file.originalName}</span>
                      {sizeLabel ? (
                        <span className={`block text-[11px] ${isUserMessage ? 'text-white/75' : 'text-slate-500'}`}>
                          {sizeLabel}
                        </span>
                      ) : null}
                    </span>
                  </div>
                  <p className={`line-clamp-4 text-[12px] leading-5 ${isUserMessage ? 'text-white/80' : 'text-slate-500'}`}>
                    {getFilePreviewText(file, t)}
                  </p>
                </button>
              );
            })}
          </div>
        )}
      </div>
    );
  }, [handleOpenFilePreview, t]);

  const renderMessage = (message: Message, index: number) => {
    const showAvatar = index === 0;
    const showTimestamp = index === messages.length - 1;
    const isErrorMessage = !isUser && !!message.isError;
    const errorMeta = message.errorKind ? errorKindMeta[message.errorKind] : null;
    const providerRemediation = !isUser ? coerceProviderRemediation(message.metadata?._provider_error) : [];
    const providerDiagnostic = !isUser ? coerceProviderDiagnostic(message.metadata?._provider_error) : null;
    const requestId = !isUser
      ? (message.requestId || (typeof message.metadata?.request_id === 'string' ? message.metadata.request_id : ''))
      : '';
    const cleanedContent = stripMessageTags(message.content);
    const memorySources = !isUser ? coerceMemorySources(message.metadata?._memory_sources) : [];
    const memoryRecall = !isUser ? coerceMemoryRecall(message.metadata?._memory_recall) : null;
    const memorySummaryLabel = memorySources.length > 0
      ? t('messageGroup.memorySummary.references', { count: memorySources.length })
      : t('messageGroup.memorySummary.recall');
    const shouldRenderMarkdown = !isUser && !message.isStreaming && !isErrorMessage && !!cleanedContent.trim();
    const handoffFromName = !isUser && typeof message.metadata?.handoff_from_name === 'string'
      ? message.metadata.handoff_from_name
      : '';
    const handoffMode = !isUser && typeof message.metadata?.handoff_mode === 'string'
      ? message.metadata.handoff_mode
      : '';
    const handoffPreview = !isUser && typeof message.metadata?.handoff_preview === 'string'
      ? message.metadata.handoff_preview
      : '';
    const relayStatusLabel = handoffFromName
      ? `${handoffFromName} -> ${agentName || t('messageGroup.assistant')}`
      : t('messageGroup.relay.relayingWithAgent', { name: agentName || t('messageGroup.assistant') });
    const relayStatusTone = handoffMode === 'summary'
      ? 'border-emerald-200 bg-emerald-50/80 text-emerald-800'
      : handoffMode === 'continue'
        ? 'border-sky-200 bg-sky-50/80 text-sky-800'
        : 'border-violet-200 bg-violet-50/80 text-violet-800';
    const compactStreamingTone = handoffFromName || handoffMode
      ? relayStatusTone
      : 'border-slate-200 bg-slate-50/90 text-slate-700';
    const shouldShowCompactStreamingStatus = !isUser && message.isStreaming && !!message.statusMessage && !!message.content;
    const imageFiles = (message.files || []).filter((file) => file.category === 'image' && Boolean(file.localPreview || file.previewUrl || file.url));
    const nonImageFiles = (message.files || []).filter((file) => !imageFiles.some((entry) => entry.fileId === file.fileId));
    const shouldDetachImageBubble = imageFiles.length > 0 && (!message.isStreaming && (Boolean(cleanedContent.trim()) || nonImageFiles.length > 0));
    const inlineFiles = shouldDetachImageBubble ? nonImageFiles : message.files;
    const detachedImageBubble = shouldDetachImageBubble ? renderMessageFiles(imageFiles, isUser) : null;

    return (
      <div
        key={message.id}
        className={`group/message-row flex gap-1.5 ${isUser ? 'flex-row-reverse' : 'flex-row'} ${index > 0 ? 'mt-0.5' : ''}`}
      >
        {showAvatar ? (
          <div className={`flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-br ${isUser ? 'from-blue-500 to-cyan-500' : avatarColor} text-[10px] font-semibold text-white shadow-sm`}>
            {isUser ? t('common.user').charAt(0) : (agentName ? agentName.charAt(0).toUpperCase() : '?')}
          </div>
        ) : (
          <div className="w-6 flex-shrink-0" />
        )}

        <div className={`flex min-w-0 max-w-full flex-col ${isUser ? 'items-end' : 'items-start'}`}>
          {showAvatar && (
            <div className={`mb-0.5 flex items-center gap-1.5 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
              <span className="text-[12px] font-semibold text-slate-800">
                {isUser ? t('common.user') : agentName || t('messageGroup.assistant')}
              </span>
              {showTimestamp && message.timestamp && (
                <span className="text-[10px] text-slate-400">
                  {formatTime(message.timestamp)}
                </span>
              )}
            </div>
          )}

          {message.statusMessage && !message.content && (
            <div className={`w-fit max-w-full rounded-2xl border px-3 py-2 shadow-sm sm:max-w-[36rem] ${relayStatusTone}`}>
              <div className="flex flex-wrap items-center gap-2 text-[11px] font-medium">
                <span className="inline-flex items-center rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-semibold text-slate-700">
                  {t('messageGroup.relay.teamRelay')}
                </span>
                <span>{relayStatusLabel}</span>
                {handoffMode === 'summary' && (
                  <span className="inline-flex items-center rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
                    {t('messageGroup.relay.returnSummary')}
                  </span>
                )}
                {handoffMode === 'continue' && (
                  <span className="inline-flex items-center rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-medium text-sky-700">
                    {t('messageGroup.relay.continueNext')}
                  </span>
                )}
              </div>
              <div className="mt-1.5 flex items-center gap-2 text-[12px] leading-5">
                <span>{message.statusMessage}</span>
                <span className="inline-block h-3.5 w-1.5 animate-pulse rounded-full bg-current" />
              </div>
              {handoffPreview && (
                <p className="mt-1 text-[11px] leading-4 text-slate-500">
                  {t('messageGroup.relay.currentSubtask')}: {handoffPreview}
                </p>
              )}
            </div>
          )}

          {shouldShowCompactStreamingStatus && (
            <div className={`mb-1 inline-flex max-w-full items-center gap-2 rounded-full border px-2.5 py-1 text-[11px] font-medium shadow-sm ${compactStreamingTone}`}>
              <span className="inline-flex items-center rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-semibold text-slate-700">
                {handoffFromName || handoffMode ? t('messageGroup.relay.teamRelay') : t('messageGroup.relay.processing')}
              </span>
              <span className="truncate">{message.statusMessage}</span>
              <span className="inline-block h-3.5 w-1.5 flex-shrink-0 animate-pulse rounded-full bg-current" />
            </div>
          )}

          {detachedImageBubble && (
            <div
              className={`mb-1.5 w-fit min-w-0 max-w-full rounded-2xl px-1.5 py-1.5 shadow-sm sm:max-w-[42rem] ${
                isUser
                  ? 'rounded-tr-md bg-blue-500 text-white'
                  : 'rounded-tl-md border border-slate-200 bg-white text-slate-800'
              }`}
              data-testid="message-detached-image-bubble"
            >
              {detachedImageBubble}
            </div>
          )}

          <div
            className={`w-fit min-w-0 max-w-full rounded-2xl px-2.5 py-1.5 text-[13px] shadow-sm sm:max-w-[42rem] ${
              isUser
                ? 'rounded-tr-md bg-blue-500 text-white'
                : isErrorMessage
                  ? 'rounded-tl-md border border-red-200 bg-red-50 text-red-900'
                  : 'rounded-tl-md border border-slate-200 bg-white text-slate-800'
            } ${message.statusMessage && !message.content ? 'hidden' : ''}`}
          >
            {isErrorMessage && (
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-red-700">
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v3m0 4h.01M10.29 3.86l-7.5 13A1 1 0 003.66 18h16.68a1 1 0 00.87-1.5l-7.5-13a1 1 0 00-1.74 0z" />
                  </svg>
                  <span>{t('messageGroup.requestFailed')}</span>
                </div>
                {errorMeta && (
                  <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${errorMeta.tone}`}>
                    {errorMeta.label}
                  </span>
                )}
                {showRetryPending && message.retryable && (
                  <span className="inline-flex items-center rounded-full border border-amber-200 bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-800">
                    {t('messageGroup.retryAvailable')}
                  </span>
                )}
              </div>
            )}

            {message.isStreaming ? (
              <div className="flex items-center gap-1 whitespace-pre-wrap break-words leading-[1.55]">
                <div className="min-w-0">
                  {inlineFiles && inlineFiles.length > 0 && (
                    <div className="mb-2">
                      {renderMessageFiles(inlineFiles, isUser)}
                    </div>
                  )}
                  <span>{cleanedContent}</span>
                </div>
                <span className="inline-block h-4 w-1.5 animate-pulse rounded-full bg-current" />
              </div>
            ) : (
              <div className="min-w-0 whitespace-pre-wrap break-words leading-[1.55]">
                {inlineFiles && inlineFiles.length > 0 && (
                  <div className="mb-2">
                    {renderMessageFiles(inlineFiles, isUser)}
                  </div>
                )}
                {shouldRenderMarkdown ? (
                  <MarkdownRenderer
                    content={cleanedContent}
                    theme="light"
                    className="[&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
                  />
                ) : (
                  cleanedContent
                )}
              </div>
            )}

            {isErrorMessage && providerRemediation.length > 0 && (
              <div className="mt-3 rounded-2xl border border-red-100 bg-white/70 px-3 py-2">
                <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-red-600">{t('messageGroup.remediationTitle')}</div>
                <ul className="space-y-1 text-xs leading-5 text-red-800">
                  {providerRemediation.map((item, remediationIndex) => (
                    <li key={`${message.id}-remediation-${remediationIndex}`}>• {item}</li>
                  ))}
                </ul>
              </div>
            )}

            {isErrorMessage && (requestId || providerDiagnostic?.errorCode || providerDiagnostic?.errorKind || providerDiagnostic?.provider || providerDiagnostic?.model || typeof providerDiagnostic?.statusCode === 'number') && (
              <div className="mt-3 rounded-2xl border border-red-100 bg-white/70 px-3 py-2" data-testid="message-provider-diagnostics">
                <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-red-600">
                  {t('messageGroup.diagnosticsTitle')}
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs leading-5 text-red-900">
                  {requestId && (
                    <span className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-red-50 px-2 py-0.5">
                      <span className="font-medium text-red-700">{t('messageGroup.diagnosticsRequestId')}</span>
                      <code className="font-mono text-[11px]">{requestId}</code>
                    </span>
                  )}
                  {providerDiagnostic?.errorCode && (
                    <span className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-red-50 px-2 py-0.5">
                      <span className="font-medium text-red-700">{t('messageGroup.diagnosticsErrorCode')}</span>
                      <code className="font-mono text-[11px]">{providerDiagnostic.errorCode}</code>
                    </span>
                  )}
                  {providerDiagnostic?.errorKind && (
                    <span className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-red-50 px-2 py-0.5">
                      <span className="font-medium text-red-700">{t('messageGroup.diagnosticsErrorKind')}</span>
                      <code className="font-mono text-[11px]">{providerDiagnostic.errorKind}</code>
                    </span>
                  )}
                  {providerDiagnostic?.provider && (
                    <span className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-red-50 px-2 py-0.5">
                      <span className="font-medium text-red-700">{t('messageGroup.diagnosticsProvider')}</span>
                      <code className="font-mono text-[11px]">{providerDiagnostic.provider}</code>
                    </span>
                  )}
                  {providerDiagnostic?.model && (
                    <span className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-red-50 px-2 py-0.5">
                      <span className="font-medium text-red-700">{t('messageGroup.diagnosticsModel')}</span>
                      <code className="font-mono text-[11px]">{providerDiagnostic.model}</code>
                    </span>
                  )}
                  {typeof providerDiagnostic?.statusCode === 'number' && (
                    <span className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-red-50 px-2 py-0.5">
                      <span className="font-medium text-red-700">{t('messageGroup.diagnosticsStatusCode')}</span>
                      <code className="font-mono text-[11px]">{providerDiagnostic.statusCode}</code>
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>

          {children && index === messages.length - 1 && (
            <div className="mt-0.5 w-full max-w-full sm:max-w-[42rem]">{children}</div>
          )}

          {!isUser && (memorySources.length > 0 || memoryRecall) && index === messages.length - 1 && (
            <details className="mt-1.5 w-full max-w-full rounded-2xl border border-slate-200 bg-slate-50/80 px-3 py-2 text-slate-700 shadow-sm sm:max-w-[42rem]">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-xs font-medium text-slate-600 marker:hidden">
                <span className="inline-flex items-center gap-2">
                  <BookMarked className="h-3.5 w-3.5" strokeWidth={2} />
                  {memorySummaryLabel}
                </span>
                <span className="inline-flex items-center gap-1 text-[11px] text-slate-400">
                  {t('messageGroup.collapsedByDefault')}
                  <ChevronDown className="h-3.5 w-3.5" strokeWidth={2} />
                </span>
              </summary>
              <div className="mt-3 space-y-2">
                {memoryRecall && (
                  <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3">
                    <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                      <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 font-semibold text-emerald-700">
                        {t('messageGroup.memoryRecall.currentRound')}
                      </span>
                      {typeof memoryRecall.latency_ms === 'number' && (
                        <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-700">
                          {t('messageGroup.memoryRecall.latency', { value: memoryRecall.latency_ms.toFixed(1) })}
                        </span>
                      )}
                      {typeof memoryRecall.candidates_count === 'number' && (
                        <span className="inline-flex items-center rounded-full bg-sky-50 px-2 py-0.5 font-medium text-sky-700">
                          {t('messageGroup.memoryRecall.candidates', { count: memoryRecall.candidates_count })}
                        </span>
                      )}
                      {typeof memoryRecall.selected_count === 'number' && (
                        <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 font-medium text-amber-700">
                          {t('messageGroup.memoryRecall.hits', { count: memoryRecall.selected_count })}
                        </span>
                      )}
                    </div>
                    {memoryRecall.query && (
                      <p className="mt-2 text-xs text-slate-600">
                        {t('messageGroup.memoryRecall.query')}: {memoryRecall.query}
                      </p>
                    )}
                  </div>
                )}
                {memorySources.slice(0, 5).map((source, sourceIdx) => {
                  const categoryMeta = getMemoryCategoryMeta(source.category, t);
                  const originMeta = getOriginMeta(source, t);
                  const sortedReasons = sortReasons(source.reasons);
                  const snippetView = previewSnippet(source.snippet);
                  return (
                    <div
                      key={`${message.id}-memory-${source.path || source.file || sourceIdx}`}
                      className="rounded-2xl border border-slate-200 bg-white px-3 py-2"
                    >
                      <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                        <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 font-semibold text-slate-700">
                          {source.level}
                        </span>
                        {source.category && (
                          <span className={`inline-flex items-center rounded-full px-2 py-0.5 font-medium ${categoryMeta.tone}`}>
                            {categoryMeta.label}
                          </span>
                        )}
                        {originMeta && (
                          <span className={`inline-flex items-center rounded-full px-2 py-0.5 font-medium ${originMeta.tone}`}>
                            {originMeta.label}
                          </span>
                        )}
                        {source.scope_label && (
                          <span className="inline-flex items-center rounded-full bg-teal-50 px-2 py-0.5 font-medium text-teal-700">
                            {source.scope_label}
                          </span>
                        )}
                        {typeof source.relevance === 'number' && (
                          <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-700">
                            {t('messageGroup.matchPercent', { percent: (source.relevance * 100).toFixed(0) })}
                          </span>
                        )}
                        <span>{source.title || source.file || t('messageGroup.unnamedMemory')}</span>
                        <button
                          type="button"
                          onClick={() => handleOpenMemorySource(source)}
                          data-testid="memory-source-open-detail"
                          className="ml-auto inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 transition-colors hover:bg-slate-200 hover:text-slate-800"
                        >
                          {t('messageGroup.viewDetails')}
                          <ArrowUpRight className="h-3 w-3" strokeWidth={2} />
                        </button>
                      </div>
                      {source.snippet && (
                        <>
                          <p className="mt-2 whitespace-pre-wrap break-words text-xs text-slate-700">
                            {snippetView.preview}
                          </p>
                          {snippetView.expanded && (
                            <details className="mt-2 rounded-xl bg-slate-50 px-2 py-1">
                              <summary className="cursor-pointer list-none text-[11px] font-medium text-slate-500 marker:hidden">
                                {t('messageGroup.expandSnippet')}
                              </summary>
                              <p className="mt-2 whitespace-pre-wrap break-words text-xs text-slate-700">
                                {source.snippet}
                              </p>
                            </details>
                          )}
                        </>
                      )}
                      {(source.reasons?.length || source.matched_terms?.length) ? (
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                          {sortedReasons.slice(0, 4).map((reason) => (
                            <span
                              key={`${message.id}-memory-reason-${sourceIdx}-${reason}`}
                              className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 font-medium text-emerald-700"
                            >
                              {reason}
                            </span>
                          ))}
                          {source.matched_terms?.slice(0, 4).map((term) => (
                            <span
                              key={`${message.id}-memory-term-${sourceIdx}-${term}`}
                              className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 font-medium text-amber-700"
                            >
                              {term}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </details>
          )}

          {!message.isStreaming && (
            <div className={`mt-1.5 flex transition-all duration-150 ${isUser ? 'justify-end' : 'justify-start'} opacity-0 translate-y-1 pointer-events-none group-hover/message-row:opacity-100 group-hover/message-row:translate-y-0 group-hover/message-row:pointer-events-auto group-focus-within/message-row:opacity-100 group-focus-within/message-row:translate-y-0 group-focus-within/message-row:pointer-events-auto`}>
              <div className={`inline-flex items-center gap-2 rounded-full border px-2 py-1 shadow-sm ${
                isUser
                  ? 'border-blue-200 bg-blue-50/80 text-blue-700'
                  : isErrorMessage
                    ? 'border-red-200 bg-red-50/80 text-red-700'
                    : 'border-slate-200 bg-slate-50 text-slate-600'
              }`}>
                <button
                  type="button"
                  onClick={() => handleCopy(message)}
                  className={`inline-flex h-8 w-8 items-center justify-center rounded-full transition-colors ${
                    isUser
                      ? 'hover:bg-blue-100/80'
                      : 'hover:bg-white'
                  }`}
                  aria-label={t('messageGroup.copyContent')}
                  title={t('messageGroup.copyContent')}
                >
                  <Copy className="h-3.5 w-3.5" strokeWidth={2} />
                </button>
                {isErrorMessage && message.retryable && onRetryMessage && (
                  <button
                    type="button"
                    onClick={() => onRetryMessage(message)}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:bg-white"
                    aria-label={t('messageGroup.retryLastMessage')}
                    title={t('messageGroup.retryLastMessage')}
                  >
                    <RotateCcw className="h-3.5 w-3.5" strokeWidth={2} />
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div
      className="min-w-0 space-y-0"
      data-testid="chat-message-group"
      data-role={isUser ? 'user' : 'assistant'}
      data-agent-id={agentId || ''}
      data-agent-name={agentName || ''}
    >
      {messages.map((msg, idx) => renderMessage(msg, idx))}
      <Modal
        isOpen={!!inspectedSource}
        onClose={() => setInspectedSource(null)}
        title={inspectedSource?.title || inspectedSource?.file || t('messageGroup.memorySourceDetail')}
        size="lg"
      >
        {inspectedSource && (
          <div className="space-y-4" data-testid="memory-source-detail-modal">
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 font-semibold text-slate-700">
                {inspectedSource.level}
              </span>
              {inspectedSource.category && (
                <span className={`inline-flex items-center rounded-full px-2 py-0.5 font-medium ${getMemoryCategoryMeta(inspectedSource.category, t).tone}`}>
                  {getMemoryCategoryMeta(inspectedSource.category, t).label}
                </span>
              )}
              {inspectedSourceOrigin && (
                <span className={`inline-flex items-center rounded-full px-2 py-0.5 font-medium ${inspectedSourceOrigin.tone}`}>
                  {inspectedSourceOrigin.label}
                </span>
              )}
              {inspectedSource.scope_label && (
                <span className="inline-flex items-center rounded-full bg-teal-50 px-2 py-0.5 font-medium text-teal-700">
                  {inspectedSource.scope_label}
                </span>
              )}
              {typeof inspectedSource.relevance === 'number' && (
                <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 font-medium text-amber-700">
                  {t('messageGroup.matchPercent', { percent: (inspectedSource.relevance * 100).toFixed(0) })}
                </span>
              )}
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{t('messageGroup.sourceFile')}</div>
              <div className="mt-2 break-all text-sm text-slate-700">{inspectedSource.path || inspectedSource.file || t('messageGroup.pathNotRecorded')}</div>
            </div>

            <div className="rounded-2xl border border-sky-100 bg-sky-50 px-4 py-3">
              <div className="text-xs font-medium uppercase tracking-wide text-sky-700">{t('messageGroup.sourceTypeTitle')}</div>
              <p className="mt-2 text-sm text-sky-900" data-testid="memory-source-description">
                {getSourceTypeDescription(inspectedSource, t)}
              </p>
            </div>

            {inspectedSource.reasons?.length ? (
              <div>
                <div className="text-sm font-semibold text-slate-800">{t('messageGroup.hitReasons')}</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {sortReasons(inspectedSource.reasons).map((reason) => (
                    <span
                      key={`inspect-reason-${reason}`}
                      className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700"
                    >
                      {reason}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            {inspectedSource.matched_terms?.length ? (
              <div>
                <div className="text-sm font-semibold text-slate-800">{t('messageGroup.hitTerms')}</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {inspectedSource.matched_terms.map((term) => (
                    <span
                      key={`inspect-term-${term}`}
                      className="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700"
                    >
                      {term}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            <div>
              <div className="text-sm font-semibold text-slate-800">{t('messageGroup.originalSnippet')}</div>
              <pre className="mt-2 max-h-[45vh] overflow-auto rounded-2xl border border-slate-200 bg-white px-4 py-3 whitespace-pre-wrap break-words text-sm text-slate-700">
                {inspectedSource.snippet || t('messageGroup.noSnippet')}
              </pre>
            </div>

            <ModalFooter className="flex-col items-stretch gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div className="space-y-2">
                <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{t('messageGroup.copySection')}</div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={handleCopySourceHandoff}
                    data-testid="memory-source-copy-handoff"
                    className="inline-flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-700 transition-colors hover:bg-emerald-100"
                  >
                    {t('messageGroup.copyHandoffTemplate')}
                  </button>
                  <button
                    type="button"
                    onClick={handleCopySourceSummary}
                    data-testid="memory-source-copy-summary"
                    className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
                  >
                    {t('messageGroup.copySummary')}
                  </button>
                  <button
                    type="button"
                    onClick={handleCopySourceContext}
                    data-testid="memory-source-copy-context"
                    className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
                  >
                    {t('messageGroup.copyContext')}
                  </button>
                  <button
                    type="button"
                    onClick={handleCopySourcePath}
                    data-testid="memory-source-copy-path"
                    className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
                  >
                    {t('messageGroup.copyPath')}
                  </button>
                </div>
              </div>
              <div className="space-y-2 sm:text-right">
                <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{t('messageGroup.navigateSection')}</div>
                <div className="flex flex-wrap gap-2 sm:justify-end">
                  {inspectedSourceChatLabel && (
                    <button
                      type="button"
                      onClick={handleOpenSourceChat}
                      data-testid="memory-source-open-chat"
                      className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
                    >
                      {inspectedSourceChatLabel}
                    </button>
                  )}
                  {inspectedSourceTargetLabel && (
                    <button
                      type="button"
                      onClick={handleNavigateToSource}
                      data-testid="memory-source-navigate"
                      className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-800"
                    >
                      {inspectedSourceTargetLabel}
                      <ArrowUpRight className="h-4 w-4" strokeWidth={2} />
                    </button>
                  )}
                </div>
              </div>
            </ModalFooter>
          </div>
        )}
      </Modal>
      <Modal
        isOpen={!!previewedFile}
        onClose={() => setPreviewedFile(null)}
        title={previewedFile?.originalName || t('messageGroup.filePreviewTitle')}
        size={getFilePreviewModalSize(previewedFile)}
      >
        {previewedFile && (
          <div className="space-y-4" data-testid="message-file-preview-modal">
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 font-semibold text-slate-700">
                {getFileKindLabel(previewedFile, t)}
              </span>
              {formatFileSize(previewedFile.size) ? (
                <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-700">
                  {formatFileSize(previewedFile.size)}
                </span>
              ) : null}
              {previewedFile.mimeType && (
                <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-700">
                  {previewedFile.mimeType}
                </span>
              )}
              {previewedImageIndex >= 0 && previewableImageFiles.length > 1 && (
                <span className="inline-flex items-center rounded-full bg-sky-50 px-2 py-0.5 font-medium text-sky-700">
                  {t('messageGroup.previewCounter', { current: previewedImageIndex + 1, total: previewableImageFiles.length })}
                </span>
              )}
            </div>

            {renderFilePreviewContent(previewedFile, t)}

            {previewedImageIndex >= 0 && previewableImageFiles.length > 1 && (
              <div className="space-y-2" data-testid="message-file-preview-thumbnails">
                <div className="overflow-x-auto pb-1">
                  <div className="flex min-w-max gap-2">
                    {previewableImageFiles.map((file, index) => {
                      const previewUrl = getFilePreviewUrl(file);
                      const isActive = index === previewedImageIndex;
                      return (
                        <button
                          key={file.fileId}
                          type="button"
                          onClick={() => handleSelectPreviewImage(index)}
                          data-testid="message-file-preview-thumbnail"
                          aria-pressed={isActive}
                          className={`group relative h-16 w-16 shrink-0 overflow-hidden rounded-2xl border transition-all sm:h-20 sm:w-20 ${
                            isActive
                              ? 'border-sky-500 ring-2 ring-sky-200'
                              : 'border-slate-200 hover:border-slate-300'
                          }`}
                          title={file.originalName}
                        >
                          {previewUrl ? (
                            <img
                              src={previewUrl}
                              alt={file.originalName}
                              className="h-full w-full object-cover"
                            />
                          ) : (
                            <div className="flex h-full w-full items-center justify-center bg-slate-100 text-[11px] font-medium text-slate-500">
                              {index + 1}
                            </div>
                          )}
                          <div className={`absolute inset-0 transition-colors ${isActive ? 'bg-sky-950/0' : 'bg-slate-950/5 group-hover:bg-slate-950/0'}`} />
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            <ModalFooter className="flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-wrap items-center gap-2">
                {previewedImageIndex >= 0 && previewableImageFiles.length > 1 && (
                  <>
                    <button
                      type="button"
                      onClick={handlePreviewPreviousImage}
                      disabled={!canPreviewPreviousImage}
                      data-testid="message-file-preview-prev"
                      className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {t('messageGroup.previewPrevious')}
                    </button>
                    <button
                      type="button"
                      onClick={handlePreviewNextImage}
                      disabled={!canPreviewNextImage}
                      data-testid="message-file-preview-next"
                      className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {t('messageGroup.previewNext')}
                    </button>
                  </>
                )}
              </div>
              <button
                type="button"
                onClick={handleOpenOriginalFile}
                className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-800"
              >
                {t('messageGroup.openOriginalFile')}
                <ArrowUpRight className="h-4 w-4" strokeWidth={2} />
              </button>
            </ModalFooter>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default memo(MessageGroup);
