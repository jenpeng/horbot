import type { AgentInfo } from '../../pages/teams/types';
import { useI18n } from '../../contexts/I18nContext';

interface AgentOverviewCardProps {
  selectedAgent: AgentInfo;
  selectedAgentStatusMeta: {
    tone: string;
    detailLabel: string;
  };
  selectedAgentProfileLabel: string | null;
  selectedAgentProfileSummary: string | null;
  selectedAgentPermissionLabel: string | null;
  selectedAgentPermissionSummary: string | null;
  memoryReasoningStyleLabel: string | null;
  workspacePath: string;
  getBadgeClassName: (tone: string, size?: 'sm' | 'md') => string;
  getNoticeClassName: (tone: 'warning' | 'pending' | 'success') => string;
  onEditAgent: () => void;
  onOpenChat: () => void;
}

const AgentOverviewCard = ({
  selectedAgent,
  selectedAgentStatusMeta,
  selectedAgentProfileLabel,
  selectedAgentProfileSummary,
  selectedAgentPermissionLabel,
  selectedAgentPermissionSummary,
  memoryReasoningStyleLabel,
  workspacePath,
  getBadgeClassName,
  getNoticeClassName,
  onEditAgent,
  onOpenChat,
}: AgentOverviewCardProps) => {
  const { t } = useI18n();
  return (
  <div className="bg-white rounded-2xl border border-surface-200 p-6 transition-shadow" data-focus-anchor="agent-overview">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <div className="flex items-center gap-2">
          <h2 className="text-2xl font-bold text-surface-900">{selectedAgent.name}</h2>
          <span className={getBadgeClassName(selectedAgentStatusMeta.tone)}>
            {selectedAgentStatusMeta.detailLabel}
          </span>
        </div>
        <p className="text-surface-600 mt-1">{selectedAgent.description || t('teams.agentOverview.noDescription')}</p>
        <div className="mt-3 flex flex-wrap gap-2 text-xs text-surface-500">
          {selectedAgent.profile && (
            <span className={getBadgeClassName('neutral')}>
              {selectedAgentProfileLabel || selectedAgent.profile}
            </span>
          )}
          {(selectedAgent.permission_profile || selectedAgent.tool_permission_profile) && (
            <span className={getBadgeClassName('slate')}>
              {selectedAgentPermissionLabel || selectedAgent.permission_profile || selectedAgent.tool_permission_profile}
            </span>
          )}
          <span className={getBadgeClassName('neutral')}>{selectedAgent.provider || t('teams.agentOverview.providerUnset')}</span>
          <span className={getBadgeClassName('neutral')}>{selectedAgent.model || t('teams.agentOverview.modelUnset')}</span>
          <span className={getBadgeClassName('neutral')}>{t('teams.agentOverview.teamCount', { count: selectedAgent.teams.length })}</span>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onEditAgent}
          className="px-3 py-2 bg-white border border-surface-200 text-surface-700 rounded-xl hover:bg-surface-50 transition-colors"
        >
          {t('teams.agentOverview.editAgent')}
        </button>
        <button
          onClick={onOpenChat}
          className="px-3 py-2 bg-primary-500 text-white rounded-xl hover:bg-primary-600 transition-colors"
        >
          {t('teams.agentOverview.openDirectChat')}
        </button>
      </div>
    </div>

    {selectedAgent.setup_required && (
      <div className={`mt-4 ${getNoticeClassName('warning')}`}>
        <div className="font-semibold text-surface-900">{t('teams.agentOverview.setupNoticeTitle')}</div>
        <div className="mt-1">
          {t('teams.agentOverview.setupNoticeBody')}
        </div>
      </div>
    )}
    {!selectedAgent.setup_required && selectedAgent.bootstrap_setup_pending && (
      <div className={`mt-4 ${getNoticeClassName('pending')}`}>
        <div className="font-semibold">{t('teams.agentOverview.onboardingNoticeTitle')}</div>
        <div className="mt-1">
          {t('teams.agentOverview.onboardingNoticeBody')}
        </div>
      </div>
    )}
    {!selectedAgent.setup_required && !selectedAgent.bootstrap_setup_pending && (
      <div className={`mt-4 ${getNoticeClassName('success')}`}>
        <div className="font-semibold">{t('teams.agentOverview.readyNoticeTitle')}</div>
        <div className="mt-1">
          {t('teams.agentOverview.readyNoticeBody')}
        </div>
      </div>
    )}

    <div className="mt-4 rounded-2xl bg-surface-50 px-4 py-3 text-sm text-surface-600">
      {selectedAgent.profile && (
        <div className="mb-2">
          <span className="font-semibold text-surface-900">{t('teams.agentOverview.profileLabel')}</span>
          <span>{selectedAgentProfileSummary || selectedAgent.profile}</span>
        </div>
      )}
      {(selectedAgent.permission_profile || selectedAgent.tool_permission_profile) && (
        <div className="mb-2">
          <span className="font-semibold text-surface-900">{t('teams.agentOverview.permissionLabel')}</span>
          <span>
            {selectedAgentPermissionSummary || selectedAgent.permission_profile || selectedAgent.tool_permission_profile}
            {selectedAgent.permission_profile ? '' : t('teams.agentOverview.permissionInherited')}
          </span>
        </div>
      )}
      <div className="mb-2">
        <span className="font-semibold text-surface-900">{t('teams.agentOverview.statusLabel')}</span>
        <span>
          {selectedAgent.setup_required
            ? t('teams.agentOverview.statusMissingModel')
            : selectedAgent.bootstrap_setup_pending
              ? t('teams.agentOverview.statusWaitingOnboarding')
              : t('teams.agentOverview.statusReady')}
        </span>
      </div>
      {(selectedAgent.memory_bank_profile?.mission
        || selectedAgent.memory_bank_profile?.directives?.length
        || selectedAgent.memory_bank_profile?.reasoning_style) && (
        <div className="mb-2">
          <span className="font-semibold text-surface-900">{t('teams.agentOverview.memoryProfileLabel')}</span>
          <span>
            {selectedAgent.memory_bank_profile?.mission || t('teams.agentOverview.memoryMissionUnset')}
            {memoryReasoningStyleLabel ? ` · ${memoryReasoningStyleLabel}` : ''}
          </span>
        </div>
      )}
      <div>
        <span className="font-semibold text-surface-900">{t('teams.agentOverview.workspaceLabel')}</span>
        <span className="break-all">{workspacePath}</span>
      </div>
      <div className="mt-2">
        <span className="font-semibold text-surface-900">{t('teams.agentOverview.systemPromptLabel')}</span>
        <span>{selectedAgent.system_prompt ? t('teams.agentOverview.systemPromptConfigured') : t('teams.agentOverview.systemPromptUnset')}</span>
      </div>
    </div>
  </div>
  );
};

export default AgentOverviewCard;
