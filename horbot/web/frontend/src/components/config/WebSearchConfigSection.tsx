import type { WebSearchApiKeyMode } from '../../hooks/useConfigurationState';
import React from 'react';
import { useI18n } from '../../contexts/I18nContext';
import type { WebSearchProvider } from '../../types';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';

type WebSearchToggleKey = 'tavilyEnabled' | 'langsearchEnabled';

interface WebSearchConfigSectionProps {
  currentWebSearchConfig: {
    enabled: boolean;
    provider: string;
    tavilyEnabled: boolean;
    langsearchEnabled: boolean;
    apiKey: string;
    apiKeyMode: WebSearchApiKeyMode;
    hasApiKey: boolean;
    apiKeyMasked: string;
    maxResults: number;
  };
  selectedWebSearchProvider?: WebSearchProvider;
  webSearchProviders: WebSearchProvider[];
  isLoadingProviders: boolean;
  hasWebSearchChanges: boolean;
  canSaveWebSearch: boolean;
  isSavingWebSearch: boolean;
  remoteImageCacheStatus: {
    count: number;
    total_size_bytes: number;
    newest_updated_at?: string | null;
  };
  isClearingRemoteImageCache: boolean;
  onWebSearchChange: (patch: Partial<{ enabled: boolean; provider: string; tavilyEnabled: boolean; langsearchEnabled: boolean; apiKey: string; apiKeyMode: WebSearchApiKeyMode; maxResults: number }>) => void;
  onSaveWebSearch: () => void | Promise<void>;
  onClearRemoteImageCache: () => void | Promise<void>;
}

const WebSearchConfigSection: React.FC<WebSearchConfigSectionProps> = ({
  currentWebSearchConfig,
  selectedWebSearchProvider,
  webSearchProviders,
  isLoadingProviders,
  hasWebSearchChanges,
  canSaveWebSearch,
  isSavingWebSearch,
  remoteImageCacheStatus,
  isClearingRemoteImageCache,
  onWebSearchChange,
  onSaveWebSearch,
  onClearRemoteImageCache,
}) => {
  const { t } = useI18n();
  const providerRequiresApiKey = Boolean(selectedWebSearchProvider?.requires_api_key);
  const providerToggleKey = selectedWebSearchProvider?.enabled_config_key as WebSearchToggleKey | undefined;
  const providerToggleEnabled = providerToggleKey ? currentWebSearchConfig[providerToggleKey] : true;
  const hasMaskedKey = currentWebSearchConfig.hasApiKey && currentWebSearchConfig.apiKeyMasked;
  const apiKeyActionLabel = currentWebSearchConfig.apiKeyMode === 'clear'
    ? t('config.webSearch.keyClear')
    : currentWebSearchConfig.apiKeyMode === 'replace'
      ? t('config.webSearch.keyReplace')
      : currentWebSearchConfig.hasApiKey
        ? t('config.webSearch.keyKeep')
        : t('config.webSearch.keyMissing');

  return (
    <Card padding="none" variant="default" className="shadow-sm hover:shadow-md transition-shadow duration-300">
      <div className="px-6 py-4 border-b border-surface-200 bg-gradient-to-r from-accent-blue/10 to-transparent">
        <h2 className="text-xl font-bold text-surface-900 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-accent-blue/20 flex items-center justify-center">
            <svg className="w-5 h-5 text-accent-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          {t('config.section.webSearch')}
        </h2>
        <p className="text-base text-surface-600 mt-2 ml-12">{t('config.webSearch.subtitle')}</p>
      </div>
      <div className="p-6 space-y-4">
        <div className="rounded-2xl border border-surface-200 bg-surface-50/80 p-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-surface-900">{t('config.webSearch.globalToggleLabel')}</p>
              <p className="mt-1 text-sm text-surface-600">
                {currentWebSearchConfig.enabled
                  ? t('config.webSearch.globalEnabledHint')
                  : t('config.webSearch.globalDisabledHint')}
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={currentWebSearchConfig.enabled}
              onClick={() => onWebSearchChange({ enabled: !currentWebSearchConfig.enabled })}
              className={`relative inline-flex h-7 w-12 flex-shrink-0 items-center rounded-full transition-colors ${
                currentWebSearchConfig.enabled ? 'bg-primary-600' : 'bg-surface-300'
              }`}
            >
              <span
                className={`inline-block h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${
                  currentWebSearchConfig.enabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
          <div className="mt-3 rounded-xl border border-dashed border-surface-200 bg-white/70 px-3 py-2 text-xs text-surface-600">
            {currentWebSearchConfig.enabled
              ? t('config.webSearch.globalEnabledMode')
              : t('config.webSearch.globalDisabledMode')}
          </div>
        </div>

        <div>
          <label className="block text-sm font-semibold text-surface-700 mb-2">{t('config.webSearch.providerLabel')}</label>
          <select
            value={currentWebSearchConfig.provider}
            onChange={(e) => {
              onWebSearchChange({ provider: e.target.value });
            }}
            className="w-full bg-white border-2 border-surface-200 rounded-xl px-4 py-3 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all duration-200"
            disabled={isLoadingProviders}
          >
            {webSearchProviders.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.name} {provider.requires_api_key ? '' : `(${t('common.freeTier')})`}
              </option>
            ))}
          </select>
          {selectedWebSearchProvider?.description && (
            <p className="text-sm text-surface-500 mt-2">{selectedWebSearchProvider.description}</p>
          )}
        </div>

        {providerToggleKey && (
          <div className="rounded-2xl border border-surface-200 bg-surface-50/80 p-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-surface-900">
                  {t('config.webSearch.providerToggleLabel', { provider: selectedWebSearchProvider?.name || currentWebSearchConfig.provider })}
                </p>
                <p className="mt-1 text-sm text-surface-600">
                  {providerToggleEnabled
                    ? t('config.webSearch.providerEnabledHint', { provider: selectedWebSearchProvider?.name || currentWebSearchConfig.provider })
                    : t('config.webSearch.providerDisabledHint', { provider: selectedWebSearchProvider?.name || currentWebSearchConfig.provider })}
                </p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={providerToggleEnabled}
                onClick={() => onWebSearchChange({ [providerToggleKey]: !providerToggleEnabled } as Partial<{ enabled: boolean; provider: string; tavilyEnabled: boolean; langsearchEnabled: boolean; apiKey: string; apiKeyMode: WebSearchApiKeyMode; maxResults: number }>)}
                className={`relative inline-flex h-7 w-12 flex-shrink-0 items-center rounded-full transition-colors ${
                  providerToggleEnabled ? 'bg-primary-600' : 'bg-surface-300'
                }`}
              >
                <span
                  className={`inline-block h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${
                    providerToggleEnabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
            <div className="mt-3 rounded-xl border border-dashed border-surface-200 bg-white/70 px-3 py-2 text-xs text-surface-600">
              {providerToggleEnabled
                ? t('config.webSearch.providerEnabledMode', { provider: selectedWebSearchProvider?.name || currentWebSearchConfig.provider })
                : t('config.webSearch.providerDisabledMode', { provider: selectedWebSearchProvider?.name || currentWebSearchConfig.provider })}
            </div>
          </div>
        )}

        {providerRequiresApiKey && (
          <div className="space-y-4">
            <label className="block text-sm font-semibold text-surface-700 mb-2">API Key</label>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => onWebSearchChange({ apiKeyMode: 'keep' })}
                className={`rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                  currentWebSearchConfig.apiKeyMode === 'keep'
                    ? 'bg-slate-900 text-white'
                    : 'bg-surface-100 text-surface-700 hover:bg-surface-200'
                }`}
              >
                {t('config.webSearch.keepKey')}
              </button>
              <button
                type="button"
                onClick={() => onWebSearchChange({ apiKeyMode: 'replace' })}
                className={`rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                  currentWebSearchConfig.apiKeyMode === 'replace'
                    ? 'bg-primary-600 text-white'
                    : 'bg-surface-100 text-surface-700 hover:bg-surface-200'
                }`}
              >
                {t('config.webSearch.replaceKey')}
              </button>
              {currentWebSearchConfig.hasApiKey && (
                <button
                  type="button"
                  onClick={() => onWebSearchChange({ apiKeyMode: 'clear' })}
                  className={`rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                    currentWebSearchConfig.apiKeyMode === 'clear'
                      ? 'bg-accent-red text-white'
                      : 'bg-red-50 text-red-700 hover:bg-red-100'
                  }`}
                >
                  {t('config.webSearch.clearKey')}
                </button>
              )}
            </div>

            {currentWebSearchConfig.apiKeyMode === 'replace' && (
              <input
                type="password"
                value={currentWebSearchConfig.apiKey}
                onChange={(e) => onWebSearchChange({ apiKey: e.target.value })}
                placeholder={hasMaskedKey ? t('config.webSearch.replacePlaceholderMasked', { mask: currentWebSearchConfig.apiKeyMasked }) : t('config.webSearch.replacePlaceholder')}
                className="w-full bg-white border-2 border-surface-200 rounded-xl px-4 py-3 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all duration-200"
              />
            )}

            <div className={`rounded-xl border px-4 py-3 text-sm ${
              currentWebSearchConfig.apiKeyMode === 'clear'
                ? 'border-red-200 bg-red-50 text-red-700'
                : currentWebSearchConfig.apiKeyMode === 'replace'
                  ? 'border-primary-200 bg-primary-50/60 text-primary-700'
                  : 'border-surface-200 bg-surface-50 text-surface-600'
            }`}>
              <p className="font-medium">{apiKeyActionLabel}</p>
              {hasMaskedKey && currentWebSearchConfig.apiKeyMode !== 'replace' && (
                <p className="mt-1 text-xs">{t('config.webSearch.savedMask', { mask: currentWebSearchConfig.apiKeyMasked })}</p>
              )}
              {currentWebSearchConfig.apiKeyMode === 'replace' && !currentWebSearchConfig.apiKey.trim() && (
                <p className="mt-1 text-xs">{t('config.webSearch.enterKeyBeforeSave')}</p>
              )}
            </div>
          </div>
        )}

        <div>
          <label className="block text-sm font-semibold text-surface-700 mb-2">{t('config.webSearch.maxResultsLabel')}</label>
          <input
            type="number"
            value={currentWebSearchConfig.maxResults}
            onChange={(e) => onWebSearchChange({ maxResults: parseInt(e.target.value, 10) || 5 })}
            min={1}
            max={10}
            className="w-full bg-white border-2 border-surface-200 rounded-xl px-4 py-3 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all duration-200"
          />
          <p className="text-sm text-surface-500 mt-2">{t('config.webSearch.maxResultsHint')}</p>
        </div>

        <div className="rounded-2xl border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm text-amber-900">
          <p className="font-medium">{t('config.webSearch.fallbackTitle')}</p>
          <p className="mt-1 text-amber-800">
            {currentWebSearchConfig.enabled
              ? t('config.webSearch.fallbackHint')
              : t('config.webSearch.disabledFallbackHint')}
          </p>
        </div>

        <div className="rounded-2xl border border-surface-200 bg-surface-50/80 px-4 py-4">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="text-sm font-semibold text-surface-900">{t('config.remoteImageCache.title')}</p>
              <p className="mt-1 text-sm text-surface-600">{t('config.remoteImageCache.subtitle')}</p>
            </div>
            <Button
              variant="secondary"
              onClick={() => void onClearRemoteImageCache()}
              disabled={remoteImageCacheStatus.count === 0 || isClearingRemoteImageCache}
              isLoading={isClearingRemoteImageCache}
            >
              {t('config.remoteImageCache.clear')}
            </Button>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-sm">
            <span className="inline-flex rounded-full bg-white px-3 py-1 font-medium text-surface-700">
              {t('config.remoteImageCache.count', { count: remoteImageCacheStatus.count })}
            </span>
            <span className="inline-flex rounded-full bg-white px-3 py-1 font-medium text-surface-700">
              {t('config.remoteImageCache.size', { size: formatBytes(remoteImageCacheStatus.total_size_bytes) })}
            </span>
            {remoteImageCacheStatus.newest_updated_at ? (
              <span className="inline-flex rounded-full bg-white px-3 py-1 font-medium text-surface-700">
                {t('config.remoteImageCache.updatedAt', { value: formatDateTime(remoteImageCacheStatus.newest_updated_at) })}
              </span>
            ) : (
              <span className="inline-flex rounded-full bg-white px-3 py-1 font-medium text-surface-500">
                {t('config.remoteImageCache.empty')}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between gap-3 pt-5 border-t border-surface-200 px-6 pb-6 flex-wrap">
        <div className="text-sm">
          {hasWebSearchChanges ? (
            <div className="space-y-1">
              <span className="inline-flex items-center gap-2 text-accent-orange font-medium">
                <span className="h-2.5 w-2.5 rounded-full bg-accent-orange"></span>
                {t('config.webSearch.unsaved')}
              </span>
              {providerRequiresApiKey && !canSaveWebSearch && (
                <p className="text-xs text-accent-red">
                  {t('config.webSearch.keyRequiredBeforeSave', { provider: selectedWebSearchProvider?.name || currentWebSearchConfig.provider })}
                </p>
              )}
            </div>
          ) : (
            <span className="inline-flex items-center gap-2 text-surface-500">
              <span className="h-2.5 w-2.5 rounded-full bg-surface-300"></span>
              {t('config.webSearch.synced')}
            </span>
          )}
        </div>
        <Button
          variant="primary"
          onClick={() => void onSaveWebSearch()}
          disabled={!canSaveWebSearch || isSavingWebSearch}
          isLoading={isSavingWebSearch}
          leftIcon={
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          }
        >
          {t('config.webSearch.save')}
        </Button>
      </div>
    </Card>
  );
};

const formatBytes = (value: number): string => {
  if (!Number.isFinite(value) || value <= 0) {
    return '0 B';
  }
  if (value >= 1024 * 1024) {
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  }
  if (value >= 1024) {
    return `${Math.round(value / 1024)} KB`;
  }
  return `${value} B`;
};

const formatDateTime = (value: string): string => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
};

export default WebSearchConfigSection;
