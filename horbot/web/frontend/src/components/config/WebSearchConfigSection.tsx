import type { WebSearchApiKeyMode } from '../../hooks/useConfigurationState';
import React from 'react';
import type { WebSearchProvider } from '../../types';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';

interface WebSearchConfigSectionProps {
  currentWebSearchConfig: {
    provider: string;
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
  onWebSearchChange: (patch: Partial<{ provider: string; apiKey: string; apiKeyMode: WebSearchApiKeyMode; maxResults: number }>) => void;
  onSaveWebSearch: () => void | Promise<void>;
}

const WebSearchConfigSection: React.FC<WebSearchConfigSectionProps> = ({
  currentWebSearchConfig,
  selectedWebSearchProvider,
  webSearchProviders,
  isLoadingProviders,
  hasWebSearchChanges,
  canSaveWebSearch,
  isSavingWebSearch,
  onWebSearchChange,
  onSaveWebSearch,
}) => {
  const providerRequiresApiKey = Boolean(selectedWebSearchProvider?.requires_api_key);
  const hasMaskedKey = currentWebSearchConfig.hasApiKey && currentWebSearchConfig.apiKeyMasked;
  const apiKeyActionLabel = currentWebSearchConfig.apiKeyMode === 'clear'
    ? '本次保存将清空已保存密钥'
    : currentWebSearchConfig.apiKeyMode === 'replace'
      ? '本次保存将使用新密钥覆盖旧值'
      : currentWebSearchConfig.hasApiKey
        ? '当前将保留已保存密钥'
        : '当前尚未配置密钥';

  return (
    <Card padding="none" variant="default" className="shadow-sm hover:shadow-md transition-shadow duration-300">
      <div className="px-6 py-4 border-b border-surface-200 bg-gradient-to-r from-accent-blue/10 to-transparent">
        <h2 className="text-xl font-bold text-surface-900 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-accent-blue/20 flex items-center justify-center">
            <svg className="w-5 h-5 text-accent-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          Web Search
        </h2>
        <p className="text-base text-surface-600 mt-2 ml-12">配置联网搜索提供商、API Key 和结果条数</p>
      </div>
      <div className="p-6 space-y-4">
        <div>
          <label className="block text-sm font-semibold text-surface-700 mb-2">Search Provider</label>
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
                {provider.name} {provider.requires_api_key ? '' : '(免费)'}
              </option>
            ))}
          </select>
          {selectedWebSearchProvider?.description && (
            <p className="text-sm text-surface-500 mt-2">{selectedWebSearchProvider.description}</p>
          )}
        </div>

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
                保留现有密钥
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
                更新为新密钥
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
                  清空已保存密钥
                </button>
              )}
            </div>

            {currentWebSearchConfig.apiKeyMode === 'replace' && (
              <input
                type="password"
                value={currentWebSearchConfig.apiKey}
                onChange={(e) => onWebSearchChange({ apiKey: e.target.value })}
                placeholder={hasMaskedKey ? `当前已配置 ${currentWebSearchConfig.apiKeyMasked}，输入后将覆盖` : 'Enter your API key'}
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
                <p className="mt-1 text-xs">已保存密钥掩码：{currentWebSearchConfig.apiKeyMasked}</p>
              )}
              {currentWebSearchConfig.apiKeyMode === 'replace' && !currentWebSearchConfig.apiKey.trim() && (
                <p className="mt-1 text-xs">请输入新的 API Key 后再保存。</p>
              )}
            </div>
          </div>
        )}

        <div>
          <label className="block text-sm font-semibold text-surface-700 mb-2">Max Results</label>
          <input
            type="number"
            value={currentWebSearchConfig.maxResults}
            onChange={(e) => onWebSearchChange({ maxResults: parseInt(e.target.value, 10) || 5 })}
            min={1}
            max={10}
            className="w-full bg-white border-2 border-surface-200 rounded-xl px-4 py-3 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all duration-200"
          />
          <p className="text-sm text-surface-500 mt-2">Number of search results to return (1-10)</p>
        </div>
      </div>

      <div className="flex items-center justify-between gap-3 pt-5 border-t border-surface-200 px-6 pb-6 flex-wrap">
        <div className="text-sm">
          {hasWebSearchChanges ? (
            <span className="inline-flex items-center gap-2 text-accent-orange font-medium">
              <span className="h-2.5 w-2.5 rounded-full bg-accent-orange"></span>
              Web Search 有未保存修改
            </span>
          ) : (
            <span className="inline-flex items-center gap-2 text-surface-500">
              <span className="h-2.5 w-2.5 rounded-full bg-surface-300"></span>
              当前配置已与磁盘同步
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
          保存 Web Search 配置
        </Button>
      </div>
    </Card>
  );
};

export default WebSearchConfigSection;
