import React from 'react';
import { Link } from 'react-router-dom';
import { useI18n } from '../../contexts/I18nContext';
import { Card } from '../ui/Card';
import type {
  ConfigurationSectionKey,
  ConfigurationValidationSummary,
  MainAgentSummary,
} from '../../hooks/useConfigurationState';

interface ConfigurationOverviewProps {
  configuredProviders: number;
  totalProviders: number;
  missingProviderCount: number;
  mainModel: string;
  mainProvider: string;
  mainProviderConfigured: boolean;
  mainAgent: MainAgentSummary | null;
  workspacePath: string;
  validationSummary: ConfigurationValidationSummary | null;
  hasPendingChanges: boolean;
  dirtySections: ConfigurationSectionKey[];
  webSearchProvider: string;
  webSearchProviderName: string;
  webSearchTavilyEnabled: boolean;
  webSearchRequiresApiKey: boolean;
  webSearchHasApiKey: boolean;
  webSearchMaxResults: number;
}

const toneBadgeClass: Record<NonNullable<ConfigurationValidationSummary>['tone'], string> = {
  ok: 'bg-accent-emerald/15 text-accent-emerald',
  warning: 'bg-accent-orange/15 text-accent-orange',
  error: 'bg-accent-red/15 text-accent-red',
};

const ConfigurationOverview: React.FC<ConfigurationOverviewProps> = ({
  configuredProviders,
  totalProviders,
  missingProviderCount,
  mainProviderConfigured,
  mainAgent,
  workspacePath,
  validationSummary,
  hasPendingChanges,
  dirtySections,
  webSearchProvider,
  webSearchProviderName,
  webSearchTavilyEnabled,
  webSearchRequiresApiKey,
  webSearchHasApiKey,
  webSearchMaxResults,
}) => {
  const { t } = useI18n();
  const sectionMeta: Record<ConfigurationSectionKey, { label: string; href: string }> = {
    agent: { label: t('config.section.agent'), href: '#config-agent' },
    workspace: { label: t('config.section.workspace'), href: '#config-workspace' },
    'web-search': { label: t('config.section.webSearch'), href: '#config-web-search' },
  };
  const tavilyDisabled = webSearchProvider === 'tavily' && !webSearchTavilyEnabled;
  const webSearchStatus = tavilyDisabled
    ? t('config.overview.webSearchTavilyDisabled')
    : webSearchRequiresApiKey
      ? webSearchHasApiKey
        ? t('config.overview.webSearchKeyConfigured')
        : t('config.overview.webSearchKeyMissing')
      : t('config.overview.webSearchKeyNotRequired');

  return (
    <Card padding="md" variant="gradient" gradient="primary" className="shadow-md">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="text-xl font-bold text-surface-900">{t('config.overview.title')}</h2>
            {validationSummary && (
              <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${toneBadgeClass[validationSummary.tone]}`}>
                {validationSummary.label}
              </span>
            )}
            <span
              className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${
                hasPendingChanges
                  ? 'bg-accent-orange/15 text-accent-orange'
                  : 'bg-accent-emerald/15 text-accent-emerald'
              }`}
            >
              {hasPendingChanges ? t('config.overview.unsavedChanges') : t('config.overview.syncedAll')}
            </span>
          </div>
          <p className="mt-2 text-sm text-surface-600">
            {t('config.overview.subtitle')}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap justify-end">
          <a href="#config-agent" className="rounded-full bg-white/80 px-3 py-1.5 text-xs font-semibold text-surface-700 shadow-sm transition hover:bg-white">
            {t('config.overview.jumpAgent')}
          </a>
          <a href="#config-workspace" className="rounded-full bg-white/80 px-3 py-1.5 text-xs font-semibold text-surface-700 shadow-sm transition hover:bg-white">
            {t('config.overview.jumpWorkspace')}
          </a>
          <a href="#config-web-search" className="rounded-full bg-white/80 px-3 py-1.5 text-xs font-semibold text-surface-700 shadow-sm transition hover:bg-white">
            {t('config.overview.jumpWebSearch')}
          </a>
          <a href="#config-providers" className="rounded-full bg-white/80 px-3 py-1.5 text-xs font-semibold text-surface-700 shadow-sm transition hover:bg-white">
            {t('config.overview.jumpProviders')}
          </a>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-white/70 bg-white/80 p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-surface-500">{t('config.overview.unsavedSections')}</p>
          <p className="mt-2 text-2xl font-bold text-surface-900">{dirtySections.length}</p>
          <p className="mt-1 text-sm text-surface-600">
            {dirtySections.length > 0 ? t('config.overview.unsavedSectionsHint') : t('config.overview.noUnsavedSections')}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {dirtySections.length > 0 ? (
              dirtySections.map((section) => (
                <a
                  key={section}
                  href={sectionMeta[section].href}
                  className="rounded-full bg-accent-orange/12 px-2.5 py-1 text-xs font-semibold text-accent-orange transition hover:bg-accent-orange/20"
                >
                  {sectionMeta[section].label}
                </a>
              ))
            ) : (
              <span className="rounded-full bg-accent-emerald/12 px-2.5 py-1 text-xs font-semibold text-accent-emerald">
                {t('config.overview.syncedShort')}
              </span>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-white/70 bg-white/80 p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-surface-500">{t('config.overview.agentEntry')}</p>
          <p className="mt-2 text-sm font-semibold text-surface-900 break-words">{t('config.overview.agentEntryBody')}</p>
          <p className="mt-2 text-sm text-surface-600">
            {t('config.overview.currentMainAgent')}
            <span className="font-semibold text-surface-900"> {mainAgent ? `${mainAgent.name} (${mainAgent.id})` : t('config.overview.notSelected')}</span>
          </p>
          <span
            className={`mt-3 inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${
              mainProviderConfigured
                ? 'bg-accent-emerald/12 text-accent-emerald'
                : 'bg-accent-orange/12 text-accent-orange'
            }`}
          >
            {mainProviderConfigured ? t('config.overview.providerAssetsReady') : t('config.overview.providerAssetsCheck')}
          </span>
        </div>

        <div className="rounded-2xl border border-white/70 bg-white/80 p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-surface-500">{t('config.section.webSearch')}</p>
          <p className="mt-2 text-sm font-semibold text-surface-900">{webSearchProviderName || webSearchProvider || t('config.overview.webSearchProviderUnset')}</p>
          <p className="mt-2 text-sm text-surface-600">
            {t('config.overview.maxResults')} <span className="font-semibold text-surface-900">{webSearchMaxResults}</span>
          </p>
          <span
            className={`mt-3 inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${
              tavilyDisabled
                ? 'bg-accent-orange/12 text-accent-orange'
                : webSearchRequiresApiKey && !webSearchHasApiKey
                ? 'bg-accent-red/12 text-accent-red'
                : 'bg-accent-emerald/12 text-accent-emerald'
            }`}
          >
            {webSearchStatus}
          </span>
        </div>

        <div className="rounded-2xl border border-white/70 bg-white/80 p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-surface-500">{t('config.overview.providerCoverage')}</p>
          <p className="mt-2 text-2xl font-bold text-surface-900">
            {configuredProviders} <span className="text-base font-semibold text-surface-500">/ {totalProviders}</span>
          </p>
          <p className="mt-1 text-sm text-surface-600">
            {missingProviderCount > 0
              ? t('config.overview.providerMissingCount', { count: missingProviderCount })
              : t('config.overview.providerCoverageReady')}
          </p>
          <a
            href="#config-providers"
            className="mt-3 inline-flex rounded-full bg-primary-50 px-2.5 py-1 text-xs font-semibold text-primary-700 transition hover:bg-primary-100"
          >
            {t('config.overview.checkProviders')}
          </a>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_auto]">
        <div className="rounded-2xl border border-white/60 bg-white/70 px-4 py-3 text-sm text-surface-600">
          <div>
            <span className="font-semibold text-surface-900">{t('config.overview.globalWorkspace')}</span>
            <span className="break-all"> {workspacePath || '.horbot/agents/default/workspace'}</span>
          </div>
          {mainAgent && (
            <div className="mt-2">
              <span className="font-semibold text-surface-900">{t('config.overview.effectiveWorkspace')}</span>
              <span className="break-all"> {mainAgent.effectiveWorkspace || workspacePath || '.horbot/agents/default/workspace'}</span>
            </div>
          )}
        </div>
        <div className="flex items-stretch">
          <Link
            to="/teams"
            className="inline-flex items-center justify-center rounded-2xl bg-surface-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-surface-800"
          >
            {t('config.openTeams')}
          </Link>
        </div>
      </div>
    </Card>
  );
};

export default ConfigurationOverview;
