import type { RenderableArtifactSpec } from '../types/conversation';

export interface ParsedRenderableArtifacts {
  content: string;
  artifacts: RenderableArtifactSpec[];
}

const RENDERABLE_BLOCK_RE = /```(?:json\s+)?horbot-renderable\s*\n([\s\S]*?)```|```horbot-renderable\s*\n([\s\S]*?)```/gi;
const JSON_RENDERABLE_BLOCK_RE = /```json\s*\n([\s\S]*?)```/gi;
const SUPPORTED_RENDERABLE_TEMPLATES = new Set([
  'dashboard',
  'chart-story',
  'data-workbench',
  'map-story',
  'process-map',
  'interactive-report',
]);

const isSupportedTemplate = (value: unknown): value is string => (
  typeof value === 'string' && SUPPORTED_RENDERABLE_TEMPLATES.has(value.trim().toLowerCase())
);

const isRenderableSpec = (value: unknown): value is RenderableArtifactSpec => {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const item = value as Record<string, unknown>;
  if (item.response_mode === 'renderable_spec' && typeof item.artifact === 'object') {
    return isRenderableSpec(item.artifact);
  }
  return (
    isSupportedTemplate(item.template)
    && (
      Array.isArray(item.items)
      || Array.isArray(item.cards)
      || Array.isArray(item.metrics)
      || Array.isArray(item.rows)
      || Array.isArray(item.points)
      || Array.isArray(item.sections)
      || typeof item.data === 'object'
    )
  );
};

const normalizeSpec = (value: unknown): RenderableArtifactSpec | null => {
  if (!isRenderableSpec(value)) {
    return null;
  }
  const item = value as Record<string, unknown>;
  if (item.response_mode === 'renderable_spec' && item.artifact && typeof item.artifact === 'object') {
    return item.artifact as RenderableArtifactSpec;
  }
  return item as RenderableArtifactSpec;
};

const parseJson = (raw: string): RenderableArtifactSpec | null => {
  try {
    return normalizeSpec(JSON.parse(raw.trim()));
  } catch {
    return null;
  }
};

export const parseRenderableArtifacts = (
  content: string,
  metadata?: Record<string, unknown>,
): ParsedRenderableArtifacts => {
  const artifacts: RenderableArtifactSpec[] = [];
  let displayContent = content || '';

  const metadataSpec = normalizeSpec(metadata?.renderable);
  if (metadataSpec) {
    artifacts.push(metadataSpec);
  }

  displayContent = displayContent.replace(RENDERABLE_BLOCK_RE, (_match, first, second) => {
    const spec = parseJson(first || second || '');
    if (spec) {
      artifacts.push(spec);
      return '';
    }
    return _match;
  });

  displayContent = displayContent.replace(JSON_RENDERABLE_BLOCK_RE, (match, raw) => {
    const spec = parseJson(raw || '');
    if (spec) {
      artifacts.push(spec);
      return '';
    }
    return match;
  });

  return {
    content: displayContent.trim(),
    artifacts,
  };
};
