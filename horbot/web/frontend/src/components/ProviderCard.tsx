import React, { useState, useEffect, memo } from 'react';
import { configService } from '../services';
import { Badge, Button } from './ui';
import type { ProviderConfig } from '../types';

type ProviderApiKeyMode = 'keep' | 'replace' | 'clear';

interface ProviderCardProps {
  name: string;
  settings: ProviderConfig;
  isCustom?: boolean;
  onDelete?: () => void;
  onUpdate?: () => void;
}

const ProviderCard: React.FC<ProviderCardProps> = ({
  name,
  settings,
  isCustom = false,
  onDelete,
  onUpdate,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [localSettings, setLocalSettings] = useState({
    apiKey: '',
    apiKeyMode: (settings?.hasApiKey ? 'keep' : 'replace') as ProviderApiKeyMode,
    apiBase: settings?.apiBase || '',
  });

  const isConfigured = !!(settings?.hasApiKey || settings?.apiKey);

  useEffect(() => {
    setLocalSettings({
      apiKey: '',
      apiKeyMode: settings?.hasApiKey ? 'keep' : 'replace',
      apiBase: settings?.apiBase || '',
    });
  }, [settings]);

  useEffect(() => {
    const hasChanges = 
      localSettings.apiKeyMode === 'clear' ||
      (localSettings.apiKeyMode === 'replace' && localSettings.apiKey.trim() !== '') ||
      localSettings.apiBase !== (settings?.apiBase || '');
    setHasChanges(hasChanges);
  }, [localSettings, settings]);

  const canSave = !isSaving && hasChanges && (
    localSettings.apiKeyMode !== 'replace' || localSettings.apiKey.trim().length > 0
  );

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);
    setSuccess(false);

    try {
      await configService.updateProvider(name, {
        apiKey: localSettings.apiKeyMode === 'replace' ? localSettings.apiKey.trim() : undefined,
        clearApiKey: localSettings.apiKeyMode === 'clear',
        apiBase: localSettings.apiBase,
      });

      setSuccess(true);
      setHasChanges(false);
      onUpdate?.();
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail || 
                       (err as Error).message || 'Failed to save provider configuration';
      setError(errorMsg);
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    setLocalSettings({
      apiKey: '',
      apiKeyMode: settings?.hasApiKey ? 'keep' : 'replace',
      apiBase: settings?.apiBase || '',
    });
    setError(null);
  };

  const apiKeyModeLabel = localSettings.apiKeyMode === 'clear'
    ? '本次保存将清空已保存密钥'
    : localSettings.apiKeyMode === 'replace'
      ? '本次保存将用新密钥覆盖旧值'
      : isConfigured
        ? '当前将保留已保存密钥'
        : '当前尚未配置密钥';

  return (
    <div
      data-testid="provider-card"
      data-provider-name={name}
      className="bg-white rounded-lg border border-surface-200 overflow-hidden transition-all duration-200 hover:border-surface-300"
    >
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        data-testid="provider-card-toggle"
        className="w-full flex items-center justify-between p-4 text-left hover:bg-surface-50 transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-4">
          <div className={`w-2.5 h-2.5 rounded-full ${isConfigured ? 'bg-semantic-success' : 'bg-surface-400'}`} />
          <span className="font-medium text-surface-900 capitalize">{name}</span>
          {isConfigured && (
            <Badge variant="success" size="sm">已配置</Badge>
          )}
          {isCustom && (
            <Badge variant="info" size="sm">自定义</Badge>
          )}
          {hasChanges && (
            <Badge variant="warning" size="sm">未保存</Badge>
          )}
        </div>
        <div className="flex items-center space-x-2">
          <svg
            className={`w-5 h-5 text-surface-500 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      <div
        className={`overflow-hidden transition-all duration-300 ease-in-out ${
          isExpanded ? 'max-h-[600px] opacity-100' : 'max-h-0 opacity-0'
        }`}
      >
        <div className="px-4 pb-4 border-t border-surface-200 pt-4 space-y-4">
          {error && (
            <div className="bg-semantic-error/20 border border-semantic-error/50 text-semantic-error p-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          {success && (
            <div className="bg-semantic-success/20 border border-semantic-success/50 text-semantic-success p-3 rounded-lg text-sm">
              Provider 配置已保存。
            </div>
          )}

          <div>
            <label className="block text-sm font-medium mb-1.5 text-surface-700">API Key</label>
            <div className="flex flex-wrap gap-2">
              {settings?.hasApiKey && (
                <button
                  type="button"
                  data-testid="provider-api-key-mode-keep"
                  onClick={() => setLocalSettings((prev) => ({ ...prev, apiKeyMode: 'keep', apiKey: '' }))}
                  className={`rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                    localSettings.apiKeyMode === 'keep'
                      ? 'bg-slate-900 text-white'
                      : 'bg-surface-100 text-surface-700 hover:bg-surface-200'
                  }`}
                >
                  保留现有密钥
                </button>
              )}
              <button
                type="button"
                data-testid="provider-api-key-mode-replace"
                onClick={() => setLocalSettings((prev) => ({ ...prev, apiKeyMode: 'replace' }))}
                className={`rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                  localSettings.apiKeyMode === 'replace'
                    ? 'bg-primary-600 text-white'
                    : 'bg-surface-100 text-surface-700 hover:bg-surface-200'
                }`}
              >
                {settings?.hasApiKey ? '更新为新密钥' : '设置密钥'}
              </button>
              {settings?.hasApiKey && (
                <button
                  type="button"
                  data-testid="provider-api-key-mode-clear"
                  onClick={() => setLocalSettings((prev) => ({ ...prev, apiKeyMode: 'clear', apiKey: '' }))}
                  className={`rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                    localSettings.apiKeyMode === 'clear'
                      ? 'bg-semantic-error text-white'
                      : 'bg-red-50 text-red-700 hover:bg-red-100'
                  }`}
                >
                  清空已保存密钥
                </button>
              )}
            </div>

            {localSettings.apiKeyMode === 'replace' && (
              <input
                type="password"
                data-testid="provider-card-api-key-input"
                value={localSettings.apiKey}
                onChange={(e) => setLocalSettings({ ...localSettings, apiKey: e.target.value, apiKeyMode: 'replace' })}
                className="mt-3 w-full bg-surface-50 border border-surface-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all"
                placeholder={
                  settings?.hasApiKey
                    ? `当前已配置${settings.apiKeyMasked ? ` (${settings.apiKeyMasked})` : ''}，输入后将覆盖`
                    : `输入 ${name} 的 API Key`
                }
              />
            )}

            <div
              className={`mt-3 rounded-xl border px-3 py-2 text-sm ${
                localSettings.apiKeyMode === 'clear'
                  ? 'border-red-200 bg-red-50 text-red-700'
                  : localSettings.apiKeyMode === 'replace'
                    ? 'border-primary-200 bg-primary-50/70 text-primary-700'
                    : 'border-surface-200 bg-surface-50 text-surface-600'
              }`}
            >
              <p className="font-medium">{apiKeyModeLabel}</p>
              {settings?.apiKeyMasked && localSettings.apiKeyMode !== 'replace' && (
                <p className="mt-1 text-xs">已保存密钥掩码：{settings.apiKeyMasked}</p>
              )}
              {localSettings.apiKeyMode === 'replace' && localSettings.apiKey.trim().length === 0 && (
                <p className="mt-1 text-xs">请输入新的 API Key 后再保存。</p>
              )}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1.5 text-surface-700">API Base URL</label>
            <input
              type="text"
              data-testid="provider-card-api-base-input"
              value={localSettings.apiBase}
              onChange={(e) => setLocalSettings({ ...localSettings, apiBase: e.target.value })}
              className="w-full bg-surface-50 border border-surface-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all"
              placeholder="可选：自定义 API 网关地址"
            />
            <p className="mt-2 text-sm text-surface-500">当你使用代理网关、兼容层或私有部署时，可以在这里覆盖默认 API 地址。</p>
          </div>

          <div className="flex items-center justify-end space-x-2 pt-2">
            {isCustom && onDelete && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete();
                }}
                className="px-3 py-1.5 text-sm text-semantic-error hover:text-semantic-error/80 transition-colors flex items-center gap-1.5"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3m4 7h16" />
                </svg>
                删除
              </button>
            )}
            {hasChanges && (
              <button
                onClick={handleReset}
                className="px-3 py-1.5 text-sm text-surface-600 hover:text-surface-700 transition-colors"
              >
                重置
              </button>
            )}
            <Button
              onClick={handleSave}
              disabled={!canSave}
              size="sm"
              data-testid="provider-card-save"
            >
              {isSaving ? (
                <>
                  <svg className="animate-spin -ml-1 mr-1.5 h-3.5 w-3.5" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  保存中...
                </>
              ) : (
                <>
                  <svg className="w-3.5 h-3.5 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  保存
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default memo(ProviderCard);
