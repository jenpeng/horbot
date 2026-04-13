import type { AgentInfo, AgentMemoryStats, AgentSkillInfo } from '../../pages/teams/types';
import { useI18n } from '../../contexts/I18nContext';

interface AgentActivityPanelsProps {
  selectedAgent: AgentInfo;
  agentMemoryStats: AgentMemoryStats | null;
  agentSkills: AgentSkillInfo[];
  assetReady: boolean;
  assetLoading: boolean;
  reasoningStyleLabel: string | null;
}

const AgentActivityPanels = ({
  selectedAgent,
  agentMemoryStats,
  agentSkills,
  assetReady,
  assetLoading,
  reasoningStyleLabel,
}: AgentActivityPanelsProps) => {
  const { t } = useI18n();
  const loadingLabels = [
    t('teams.agentActivity.memoryEntries'),
    t('teams.agentActivity.memorySize'),
    t('teams.agentActivity.skillCount'),
  ];
  return (
  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
    <div className="lg:col-span-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-surface-900">{t('teams.agentActivity.title')}</h3>
          <p className="mt-1 text-sm text-surface-500">{t('teams.agentActivity.subtitle')}</p>
        </div>
      </div>
    </div>
    <div className="bg-white rounded-2xl border border-surface-200 p-6 transition-shadow" data-focus-anchor="agent-runtime">
      <h3 className="text-lg font-semibold text-surface-900">{t('teams.agentActivity.runtimeTitle')}</h3>
      {assetReady ? (
        <div className="mt-4 space-y-3">
          <div className="rounded-xl bg-surface-50 p-4">
            <p className="text-xs uppercase tracking-wide text-surface-500">{t('teams.agentActivity.memoryEntries')}</p>
            <p className="mt-1 text-2xl font-bold text-surface-900">{agentMemoryStats?.total_entries ?? t('teams.agentActivity.notLoaded')}</p>
          </div>
          <div className="rounded-xl bg-surface-50 p-4">
            <p className="text-xs uppercase tracking-wide text-surface-500">{t('teams.agentActivity.memorySize')}</p>
            <p className="mt-1 text-2xl font-bold text-surface-900">
              {agentMemoryStats ? `${agentMemoryStats.total_size_kb} KB` : t('teams.agentActivity.notLoaded')}
            </p>
          </div>
          <div className="rounded-xl bg-surface-50 p-4">
            <p className="text-xs uppercase tracking-wide text-surface-500">{t('teams.agentActivity.skillCount')}</p>
            <p className="mt-1 text-2xl font-bold text-surface-900">{agentSkills.length}</p>
          </div>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          {loadingLabels.map((label) => (
            <div key={label} className="rounded-xl bg-surface-50 p-4">
              <div className="animate-pulse">
                <div className="h-3 w-20 rounded bg-surface-200" />
                <div className="mt-3 h-8 w-24 rounded bg-surface-200" />
              </div>
              <p className="mt-2 text-xs text-surface-500">
                {assetLoading ? t('teams.agentActivity.loadingMetric', { label }) : t('teams.agentActivity.waitingRuntime')}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>

    <div className="bg-white rounded-2xl border border-surface-200 p-6">
      <h3 className="text-lg font-semibold text-surface-900">{t('teams.agentActivity.skillsTitle')}</h3>
      {assetReady ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {agentSkills.length > 0 ? agentSkills.map((skill) => (
            <span
              key={`${skill.source}-${skill.name}`}
              className={`px-3 py-1.5 rounded-full text-xs font-medium ${
                skill.enabled ? 'bg-primary-100 text-primary-700' : 'bg-surface-100 text-surface-500'
              }`}
            >
              {skill.name}
              {skill.always ? ` · ${t('teams.agentActivity.always')}` : ''}
            </span>
          )) : (
            <p className="text-sm text-surface-500">{t('teams.agentActivity.noSkills')}</p>
          )}
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          <div className="flex flex-wrap gap-2 animate-pulse">
            {Array.from({ length: 4 }).map((_, index) => (
              <span key={index} className="h-8 w-24 rounded-full bg-surface-200" />
            ))}
          </div>
          <p className="text-xs text-surface-500">
            {assetLoading ? t('teams.agentActivity.loadingSkills') : t('teams.agentActivity.waitingSkills')}
          </p>
        </div>
      )}
    </div>

    <div className="bg-white rounded-2xl border border-surface-200 p-6 lg:col-span-2 transition-shadow">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-surface-900">{t('teams.agentActivity.memoryProfileTitle')}</h3>
          <p className="mt-1 text-sm text-surface-500">{t('teams.agentActivity.memoryProfileSubtitle')}</p>
        </div>
        {reasoningStyleLabel && (
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
            {reasoningStyleLabel}
          </span>
        )}
      </div>
      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4">
          <div className="text-xs font-medium uppercase tracking-wide text-surface-500">Mission</div>
          <div className="mt-2 text-sm text-surface-800">
            {selectedAgent.memory_bank_profile?.mission || t('teams.agentActivity.memoryMissionFallback')}
          </div>
        </div>
        <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4 md:col-span-2">
          <div className="flex items-center justify-between gap-3">
            <div className="text-xs font-medium uppercase tracking-wide text-surface-500">Directives</div>
            <span className="text-xs text-surface-500">{t('teams.agentActivity.directiveCount', { count: selectedAgent.memory_bank_profile?.directives?.length || 0 })}</span>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {(selectedAgent.memory_bank_profile?.directives || []).length > 0 ? (
              (selectedAgent.memory_bank_profile?.directives || []).map((directive) => (
                <span key={directive} className="rounded-full bg-white px-3 py-1.5 text-xs text-surface-700 ring-1 ring-surface-200">
                  {directive}
                </span>
              ))
            ) : (
              <p className="text-sm text-surface-500">{t('teams.agentActivity.directivesFallback')}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  </div>
  );
};

export default AgentActivityPanels;
