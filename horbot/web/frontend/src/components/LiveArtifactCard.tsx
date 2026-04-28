import React, { useCallback, useMemo, useState } from 'react';
import { BarChart3, Maximize2, RefreshCcw, X } from 'lucide-react';
import { liveArtifactService, type LiveArtifactRenderResponse } from '../services/liveArtifacts';
import type { RenderableArtifactSpec } from '../types/conversation';
import { useI18n } from '../contexts/I18nContext';

interface LiveArtifactCardProps {
  spec: RenderableArtifactSpec;
}

const getSpecText = (spec: RenderableArtifactSpec, key: string): string => {
  const value = spec[key];
  return typeof value === 'string' ? value : '';
};

const getTemplateLabel = (template?: string): string => {
  switch ((template || '').toLowerCase()) {
    case 'chart-story':
      return 'Chart Story';
    case 'data-workbench':
      return 'Data Workbench';
    case 'map-story':
      return 'Map Story';
    case 'process-map':
      return 'Process Map';
    case 'interactive-report':
      return 'Interactive Report';
    default:
      return 'Dashboard';
  }
};

const countDataHints = (spec: RenderableArtifactSpec): number => {
  const keys = ['items', 'cards', 'metrics', 'rows', 'points', 'sections'];
  return keys.reduce((count, key) => count + (Array.isArray(spec[key]) ? (spec[key] as unknown[]).length : 0), 0);
};

const LiveArtifactCard: React.FC<LiveArtifactCardProps> = ({ spec }) => {
  const { t } = useI18n();
  const [renderResult, setRenderResult] = useState<LiveArtifactRenderResponse | null>(null);
  const [isRendering, setIsRendering] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState('');

  const title = getSpecText(spec, 'title') || getSpecText(spec, 'name') || t('liveArtifact.untitled');
  const summary = getSpecText(spec, 'summary') || getSpecText(spec, 'description') || t('liveArtifact.summaryFallback');
  const template = typeof spec.template === 'string' ? spec.template : 'dashboard';
  const dataHints = useMemo(() => countDataHints(spec), [spec]);

  const handleRender = useCallback(async () => {
    setIsRendering(true);
    setError('');
    try {
      const result = await liveArtifactService.render(spec);
      setRenderResult(result);
      setIsOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('liveArtifact.renderFailed'));
    } finally {
      setIsRendering(false);
    }
  }, [spec, t]);

  const handleCloseRuntime = useCallback(() => {
    setIsOpen(false);
  }, []);

  return (
    <div
      className="mt-2 overflow-hidden rounded-3xl border border-cyan-200/80 bg-gradient-to-br from-cyan-50 via-white to-slate-50 text-slate-800 shadow-sm"
      data-testid="live-artifact-card"
    >
      <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-cyan-100 px-2.5 py-1 text-[11px] font-semibold text-cyan-900">
              <BarChart3 className="h-3.5 w-3.5" strokeWidth={2} />
              {t('liveArtifact.badge')}
            </span>
            <span className="rounded-full bg-white/80 px-2.5 py-1 text-[11px] font-medium text-slate-600 shadow-sm">
              {getTemplateLabel(template)}
            </span>
            {dataHints > 0 ? (
              <span className="rounded-full bg-white/80 px-2.5 py-1 text-[11px] font-medium text-slate-500 shadow-sm">
                {t('liveArtifact.dataHints', { count: dataHints })}
              </span>
            ) : null}
          </div>
          <h3 className="truncate text-[15px] font-semibold tracking-tight text-slate-950">{title}</h3>
          <p className="mt-1 line-clamp-2 text-[12px] leading-5 text-slate-600">{summary}</p>
          {error ? (
            <p className="mt-2 rounded-2xl border border-red-100 bg-red-50 px-3 py-2 text-[12px] text-red-700">
              {error}
            </p>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {renderResult ? (
            <button
              type="button"
              onClick={() => setIsOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[12px] font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
            >
              <Maximize2 className="h-3.5 w-3.5" strokeWidth={2} />
              {t('liveArtifact.open')}
            </button>
          ) : null}
          <button
            type="button"
            onClick={handleRender}
            disabled={isRendering}
            className="inline-flex items-center gap-1.5 rounded-full bg-slate-950 px-3.5 py-1.5 text-[12px] font-semibold text-white shadow-sm transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RefreshCcw className={`h-3.5 w-3.5 ${isRendering ? 'animate-spin' : ''}`} strokeWidth={2} />
            {isRendering ? t('liveArtifact.rendering') : renderResult ? t('liveArtifact.rerender') : t('liveArtifact.render')}
          </button>
        </div>
      </div>

      {isOpen && renderResult ? (
        <div className="border-t border-cyan-100 bg-white">
          <div className="flex items-center justify-between gap-3 px-4 py-2">
            <div className="min-w-0">
              <div className="truncate text-[12px] font-semibold text-slate-700">{renderResult.title}</div>
              <div className="text-[11px] text-slate-400">{t('liveArtifact.ephemeral')}</div>
            </div>
            <button
              type="button"
              onClick={handleCloseRuntime}
              className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-800"
              aria-label={t('common.close')}
              title={t('common.close')}
            >
              <X className="h-4 w-4" strokeWidth={2} />
            </button>
          </div>
          <iframe
            key={renderResult.artifact_id}
            src={renderResult.render_url}
            title={renderResult.title}
            sandbox="allow-scripts"
            className="h-[520px] w-full border-0 bg-white"
            data-testid="live-artifact-frame"
          />
        </div>
      ) : null}
    </div>
  );
};

export default LiveArtifactCard;
