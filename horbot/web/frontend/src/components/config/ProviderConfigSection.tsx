import React, { useState } from 'react';
import { useI18n } from '../../contexts/I18nContext';
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
  const { t } = useI18n();
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
            {t('config.section.providers')}
          </h2>
          <p className="text-base text-surface-600 mt-2 ml-12">{t('config.providers.subtitle')}</p>
        </div>
        <div className="p-6 space-y-4">
          <ConfigSectionStatus
            status={totalProviders > 0 ? 'info' : 'dirty'}
            title={totalProviders > 0 ? t('config.providers.loadedTitle', { count: totalProviders }) : t('config.providers.emptyTitle')}
            description={
              totalProviders > 0
                ? t('config.providers.loadedDescription', { count: configuredProviders })
                : t('config.providers.emptyDescription')
            }
          />
          <div className="rounded-xl border border-primary-200 bg-primary-50 px-4 py-3 text-sm text-primary-800">
            <p className="font-semibold">{t('config.providers.securityTitle')}</p>
            <p className="mt-1">
              {t('config.providers.securityBodyPrefix')}
              <code className="mx-1 rounded bg-white/70 px-1.5 py-0.5 text-xs">gateway.adminToken</code>
              {t('config.providers.securityBodyMiddle')}
              <code className="mx-1 rounded bg-white/70 px-1.5 py-0.5 text-xs">localStorage.horbotAdminToken</code>
              .
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
              <h3 className="text-lg font-semibold text-surface-700 mb-2">{t('config.providers.emptyCardTitle')}</h3>
              <p className="text-sm text-surface-500 text-center max-w-sm mb-6">
                {t('config.providers.emptyCardBody')}
              </p>
              <div className="flex items-center gap-2 text-xs text-surface-400">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>{t('config.providers.emptyCardHint')}</span>
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
                    title: t('config.providers.deleteTitle'),
                    message: t('config.providers.deleteMessage', { name }),
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
        confirmText={t('common.delete')}
        cancelText={t('common.cancel')}
        onConfirm={confirmDialog.onConfirm}
        onCancel={() => setConfirmDialog((prev) => ({ ...prev, isOpen: false }))}
        variant="danger"
      />
    </>
  );
};

export default ProviderConfigSection;
