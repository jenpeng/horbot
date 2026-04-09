import React, { useState } from 'react';
import { configService } from '../../services';
import type { ProvidersConfig } from '../../types';
import { Card } from '../ui/Card';
import ConfirmDialog from '../ui/ConfirmDialog';
import ProviderCard from '../ProviderCard';
import ProviderManager from '../ProviderManager';
import ConfigSectionStatus from './ConfigSectionStatus';

interface ProviderConfigSectionProps {
  providers?: ProvidersConfig;
  onProviderAdded: () => void | Promise<void>;
  onProviderUpdated: () => void | Promise<void>;
  onProviderDeleted: (name: string) => void | Promise<void>;
  onError: (message: string) => void;
}

const NON_CUSTOM_PROVIDER_NAMES = [
  'custom',
  'anthropic',
  'openai',
  'openrouter',
  'deepseek',
  'groq',
  'zhipu',
  'dashscope',
  'vllm',
  'gemini',
  'moonshot',
  'minimax',
  'aihubmix',
  'siliconflow',
  'volcengine',
  'openaiCodex',
  'githubCopilot',
];

const ProviderConfigSection: React.FC<ProviderConfigSectionProps> = ({
  providers,
  onProviderAdded,
  onProviderUpdated,
  onProviderDeleted,
  onError,
}) => {
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: () => {},
  });

  const totalProviders = providers ? Object.keys(providers).length : 0;
  const configuredProviders = providers
    ? Object.values(providers).filter((provider) => provider?.hasApiKey || provider?.apiKey).length
    : 0;

  return (
    <>
      <Card padding="none" variant="default" className="shadow-sm hover:shadow-md transition-shadow duration-300">
        <div className="px-6 py-4 border-b border-surface-200 bg-gradient-to-r from-accent-purple/10 to-transparent">
          <h2 className="text-xl font-bold text-surface-900 flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-accent-purple/20 flex items-center justify-center">
              <svg className="w-5 h-5 text-accent-purple" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14v6m-3-3h6M6 10h2a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v2a2 2 0 002 2zm10 0h2a2 2 0 002-2V6a2 2 0 00-2-2h-2a2 2 0 00-2 2v2a2 2 0 002 2zM6 20h2a2 2 0 002-2v-2a2 2 0 00-2-2H6a2 2 0 00-2 2v2a2 2 0 002 2z" />
              </svg>
            </div>
            Providers
          </h2>
          <p className="text-base text-surface-600 mt-2 ml-12">集中维护各类模型供应商的 API Key、网关地址和自定义接入</p>
        </div>
        <div className="p-6 space-y-4">
          <ConfigSectionStatus
            status={totalProviders > 0 ? 'info' : 'dirty'}
            title={totalProviders > 0 ? `已载入 ${totalProviders} 个 Provider` : '尚未添加任何 Provider'}
            description={
              totalProviders > 0
                ? `其中 ${configuredProviders} 个已配置密钥。Provider 采用卡片内单独保存模式，修改某个 Provider 后需要在该卡片中单独点击保存。`
                : '至少需要配置一个可用 Provider，聊天与模型调用才能正常工作。你可以先添加一个自定义 Provider，或直接完善内置 Provider 的 API Key。'
            }
          />
          <div className="rounded-xl border border-primary-200 bg-primary-50 px-4 py-3 text-sm text-primary-800">
            <p className="font-semibold">安全提示</p>
            <p className="mt-1">
              已保存的 API Key 不会回显到页面。输入新值表示覆盖，留空表示保持不变。若需远程访问 Web UI，请先配置
              <code className="mx-1 rounded bg-white/70 px-1.5 py-0.5 text-xs">gateway.adminToken</code>
              ，并在浏览器中设置
              <code className="mx-1 rounded bg-white/70 px-1.5 py-0.5 text-xs">localStorage.horbotAdminToken</code>。
            </p>
          </div>
          <ProviderManager providers={providers} onProviderAdded={() => void onProviderAdded()} />
          {totalProviders === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 px-4">
              <div className="w-16 h-16 rounded-2xl bg-surface-100 flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 14v6m-3-3h6M6 10h2a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v2a2 2 0 002 2zm10 0h2a2 2 0 002-2V6a2 2 0 00-2-2h-2a2 2 0 00-2 2v2a2 2 0 002 2zM6 20h2a2 2 0 002-2v-2a2 2 0 00-2-2H6a2 2 0 00-2 2v2a2 2 0 002 2z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-surface-700 mb-2">还没有可用的 Provider 配置</h3>
              <p className="text-sm text-surface-500 text-center max-w-sm mb-6">
                可以先点击上方“添加自定义 Provider”，或直接展开内置 Provider 卡片补全 API Key。
              </p>
              <div className="flex items-center gap-2 text-xs text-surface-400">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>通常至少需要准备一个上游模型服务的 API Key</span>
              </div>
            </div>
          ) : (
            providers &&
            Object.entries(providers).map(([name, settings]) => (
              <ProviderCard
                key={name}
                name={name}
                settings={{
                  apiKey: settings?.apiKey,
                  hasApiKey: settings?.hasApiKey,
                  apiKeyMasked: settings?.apiKeyMasked,
                  apiBase: settings?.apiBase,
                  extraHeaders: settings?.extraHeaders,
                }}
                isCustom={!NON_CUSTOM_PROVIDER_NAMES.includes(name)}
                onUpdate={() => void onProviderUpdated()}
                onDelete={() => {
                  setConfirmDialog({
                    isOpen: true,
                    title: 'Delete Provider',
                    message: `确定要删除 Provider "${name}" 吗？此操作不可撤销。`,
                    onConfirm: async () => {
                      try {
                        await configService.deleteProvider(name);
                        await onProviderDeleted(name);
                      } catch (err: any) {
                        const errorMsg = err.response?.data?.detail || err.message || 'Failed to delete provider';
                        onError(errorMsg);
                      } finally {
                        setConfirmDialog((prev) => ({ ...prev, isOpen: false }));
                      }
                    },
                  });
                }}
              />
            ))
          )}
        </div>
      </Card>

      <ConfirmDialog
        isOpen={confirmDialog.isOpen}
        title={confirmDialog.title}
        message={confirmDialog.message}
        confirmText="删除"
        cancelText="取消"
        onConfirm={confirmDialog.onConfirm}
        onCancel={() => setConfirmDialog((prev) => ({ ...prev, isOpen: false }))}
        variant="danger"
      />
    </>
  );
};

export default ProviderConfigSection;
