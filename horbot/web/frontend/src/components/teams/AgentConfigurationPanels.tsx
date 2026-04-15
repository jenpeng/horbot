import type { AgentInfo, AgentAssetBundle, SummarySectionKey } from '../../pages/teams/types';
import { useI18n } from '../../contexts/I18nContext';

interface SummarySectionDef {
  key: SummarySectionKey;
  label: string;
  placeholder: string;
}

interface AgentConfigurationPanelsProps {
  selectedAgent: AgentInfo;
  agentAssets: AgentAssetBundle | null;
  assetReady: boolean;
  assetLoading: boolean;
  assetError: string;
  assetSuccess: string;
  assetSaving: 'agents' | 'soul' | 'user' | null;
  assetDrafts: {
    agents: string;
    soul: string;
    user: string;
  };
  summaryDrafts: Record<SummarySectionKey, string>;
  summarySaving: boolean;
  summarySectionDefs: SummarySectionDef[];
  noticeToneClasses: {
    pending: string;
    success: string;
  };
  onSaveSummary: () => void;
  onSummaryDraftChange: (key: SummarySectionKey, value: string) => void;
  onSaveAssetFile: (fileKind: 'agents' | 'soul' | 'user') => void;
  onAssetDraftChange: (fileKind: 'agents' | 'soul' | 'user', value: string) => void;
}

const AgentConfigurationPanels = ({
  selectedAgent,
  agentAssets,
  assetReady,
  assetLoading,
  assetError,
  assetSuccess,
  assetSaving,
  assetDrafts,
  summaryDrafts,
  summarySaving,
  summarySectionDefs,
  noticeToneClasses,
  onSaveSummary,
  onSummaryDraftChange,
  onSaveAssetFile,
  onAssetDraftChange,
}: AgentConfigurationPanelsProps) => {
  const { t } = useI18n();
  return (
  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
    <div className="lg:col-span-3 pt-2">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-surface-900">{t('teams.agentConfig.title')}</h3>
          <p className="mt-1 text-sm text-surface-500">{t('teams.agentConfig.subtitle')}</p>
        </div>
      </div>
    </div>

    <div className="bg-white rounded-2xl border border-surface-200 p-6 lg:col-span-2 transition-shadow" data-focus-anchor="agent-summary">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-surface-900">{t('teams.agentConfig.summaryTitle')}</h3>
          <p className="mt-1 text-sm text-surface-500">{t('teams.agentConfig.summarySubtitle')}</p>
        </div>
        {assetReady && (
          <button
            onClick={onSaveSummary}
            disabled={summarySaving}
            data-testid="agent-save-summary"
            className="px-3 py-2 rounded-xl bg-primary-500 text-white hover:bg-primary-600 disabled:opacity-60 transition-colors"
          >
            {summarySaving ? t('teams.agentConfig.saving') : t('teams.agentConfig.saveSummary')}
          </button>
        )}
      </div>
      {assetReady ? (
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          {summarySectionDefs.map((section) => (
            <div key={section.key} className="rounded-2xl border border-surface-200 bg-surface-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-semibold text-surface-900">{section.label}</div>
                <span className="text-xs text-surface-500">
                  {(summaryDrafts[section.key] || '')
                    .split('\n')
                    .map((item) => item.trim())
                    .filter(Boolean).length} {t('teams.agentConfig.itemsSuffix')}
                </span>
              </div>
              <textarea
                value={summaryDrafts[section.key]}
                onChange={(e) => onSummaryDraftChange(section.key, e.target.value)}
                data-testid={`agent-summary-${section.key}`}
                className="mt-3 h-32 w-full rounded-xl border border-surface-300 bg-white px-3 py-3 text-sm text-surface-800 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                placeholder={section.placeholder}
              />
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="rounded-2xl border border-surface-200 bg-surface-50 p-4">
              <div className="animate-pulse">
                <div className="h-4 w-24 rounded bg-surface-200" />
                <div className="mt-3 flex flex-wrap gap-2">
                  <div className="h-6 w-20 rounded-full bg-surface-200" />
                  <div className="h-6 w-28 rounded-full bg-surface-200" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>

    <div className="bg-white rounded-2xl border border-surface-200 p-6 lg:col-span-2 transition-shadow" data-focus-anchor="agent-files">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-surface-900">{t('teams.agentConfig.bootstrapTitle')}</h3>
          <p className="text-sm text-surface-500 mt-1">{t('teams.agentConfig.bootstrapSubtitle')}</p>
        </div>
        {assetLoading && <span className="text-sm text-surface-500">{t('teams.agentConfig.loading')}</span>}
      </div>
      {assetError && (
        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
          {assetError}
        </div>
      )}
      {assetSuccess && (
        <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {assetSuccess}
        </div>
      )}
      {assetReady ? (
        <div className="mt-4">
          <div className={`rounded-2xl border px-4 py-3 text-sm ${
            selectedAgent.bootstrap_setup_pending
              ? noticeToneClasses.pending
              : noticeToneClasses.success
          }`}>
            {selectedAgent.bootstrap_setup_pending
              ? t('teams.agentConfig.pendingNotice')
              : t('teams.agentConfig.readyNotice')}
          </div>
          <div className="mt-4 grid grid-cols-1 xl:grid-cols-3 gap-4">
            <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4 transition-shadow" data-focus-anchor="agent-file-agents">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h4 className="font-semibold text-surface-900">AGENTS.md</h4>
                  <p className="text-xs text-surface-500 break-all">{agentAssets?.files?.agents?.path || t('teams.agentConfig.notLoaded')}</p>
                </div>
                <button
                  onClick={() => onSaveAssetFile('agents')}
                  data-testid="agent-save-agents"
                  disabled={assetSaving === 'agents'}
                  className="px-3 py-2 bg-amber-600 text-white rounded-xl hover:bg-amber-700 disabled:opacity-60 transition-colors"
                >
                  {assetSaving === 'agents' ? t('teams.agentConfig.saving') : t('teams.agentConfig.saveAgents')}
                </button>
              </div>
              <textarea
                data-testid="agent-agents-editor"
                value={assetDrafts.agents}
                onChange={(e) => onAssetDraftChange('agents', e.target.value)}
                className="mt-4 h-72 w-full rounded-xl border border-surface-300 bg-white px-3 py-3 text-sm text-surface-800 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                placeholder={t('teams.agentConfig.agentsPlaceholder')}
              />
            </div>

            <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4 transition-shadow" data-focus-anchor="agent-file-soul">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h4 className="font-semibold text-surface-900">SOUL.md</h4>
                  <p className="text-xs text-surface-500 break-all">{agentAssets?.files?.soul?.path || t('teams.agentConfig.notLoaded')}</p>
                </div>
                <button
                  onClick={() => onSaveAssetFile('soul')}
                  data-testid="agent-save-soul"
                  disabled={assetSaving === 'soul'}
                  className="px-3 py-2 bg-primary-500 text-white rounded-xl hover:bg-primary-600 disabled:opacity-60 transition-colors"
                >
                  {assetSaving === 'soul' ? t('teams.agentConfig.saving') : t('teams.agentConfig.saveSoul')}
                </button>
              </div>
              <textarea
                data-testid="agent-soul-editor"
                value={assetDrafts.soul}
                onChange={(e) => onAssetDraftChange('soul', e.target.value)}
                className="mt-4 h-72 w-full rounded-xl border border-surface-300 bg-white px-3 py-3 text-sm text-surface-800 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                placeholder={t('teams.agentConfig.soulPlaceholder')}
              />
            </div>

            <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4 transition-shadow" data-focus-anchor="agent-file-user">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h4 className="font-semibold text-surface-900">USER.md</h4>
                  <p className="text-xs text-surface-500 break-all">{agentAssets?.files?.user?.path || t('teams.agentConfig.notLoaded')}</p>
                </div>
                <button
                  onClick={() => onSaveAssetFile('user')}
                  data-testid="agent-save-user"
                  disabled={assetSaving === 'user'}
                  className="px-3 py-2 bg-surface-900 text-white rounded-xl hover:bg-surface-800 disabled:opacity-60 transition-colors"
                >
                  {assetSaving === 'user' ? t('teams.agentConfig.saving') : t('teams.agentConfig.saveUser')}
                </button>
              </div>
              <textarea
                data-testid="agent-user-editor"
                value={assetDrafts.user}
                onChange={(e) => onAssetDraftChange('user', e.target.value)}
                className="mt-4 h-72 w-full rounded-xl border border-surface-300 bg-white px-3 py-3 text-sm text-surface-800 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                placeholder={t('teams.agentConfig.userPlaceholder')}
              />
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-4 grid grid-cols-1 xl:grid-cols-3 gap-4">
          {['AGENTS.md', 'SOUL.md', 'USER.md'].map((label) => (
            <div key={label} className="rounded-2xl border border-surface-200 bg-surface-50 p-4">
              <div className="animate-pulse">
                <div className="flex items-center justify-between gap-3">
                  <div className="space-y-2">
                    <div className="h-4 w-24 rounded bg-surface-200" />
                    <div className="h-3 w-48 rounded bg-surface-200" />
                  </div>
                  <div className="h-9 w-24 rounded-xl bg-surface-200" />
                </div>
                <div className="mt-4 h-72 rounded-xl bg-white/80 border border-surface-200" />
              </div>
              <p className="mt-3 text-xs text-surface-500">
                {assetLoading ? t('teams.agentConfig.loadingFile', { label }) : t('teams.agentConfig.waitingAssets')}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  </div>
  );
};

export default AgentConfigurationPanels;
