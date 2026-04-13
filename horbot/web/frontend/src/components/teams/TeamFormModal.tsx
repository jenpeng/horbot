import type { Dispatch, SetStateAction } from 'react';
import {
  getTeamPriorityOptions,
  getTeamRoleOptions,
  getTeamTemplateOptions,
} from '../../pages/teams/formOptions';
import { useI18n } from '../../contexts/I18nContext';
import type { TeamTemplateId, TeamTemplateOption } from '../../pages/teams/formOptions';
import type {
  AgentInfo,
  TeamFormState,
  TeamMemberProfile,
} from '../../pages/teams/types';

interface TeamFormModalProps {
  mode: 'create' | 'edit';
  form: TeamFormState;
  agents: AgentInfo[];
  createIdError?: string;
  createNameError?: string;
  submitDisabled?: boolean;
  advancedOpen: boolean;
  setAdvancedOpen: Dispatch<SetStateAction<boolean>>;
  advancedSummaryItems: string[];
  teamAssignmentGuide: string;
  selectedTeamTemplateId: TeamTemplateId;
  selectedTeamTemplate: TeamTemplateOption;
  recommendedTeamTemplate: TeamTemplateOption;
  recommendedTeamLead: AgentInfo | null;
  onChange: Dispatch<SetStateAction<TeamFormState>>;
  onSelectTemplate: (templateId: TeamTemplateId) => void;
  onApplyTeamTemplate: (templateId: TeamTemplateId) => void;
  onApplyRecommendedTeamSetup: () => void;
  onToggleMemberSelection: (agentId: string, checked: boolean) => void;
  onUpsertMemberProfile: (agentId: string, patch: Partial<TeamMemberProfile>) => void;
  onSelectLead: (agentId: string) => void;
  getAgentById: (agentId: string) => AgentInfo | undefined;
  getTeamRoleDescription: (role?: string) => string;
  getTeamPriorityDescription: (priority?: number) => string;
  onClose: () => void;
  onSubmit: () => void;
}

const TeamFormModal = ({
  mode,
  form,
  agents,
  createIdError = '',
  createNameError = '',
  submitDisabled = false,
  advancedOpen,
  setAdvancedOpen,
  advancedSummaryItems,
  teamAssignmentGuide,
  selectedTeamTemplateId,
  selectedTeamTemplate,
  recommendedTeamTemplate,
  recommendedTeamLead,
  onChange,
  onSelectTemplate,
  onApplyTeamTemplate,
  onApplyRecommendedTeamSetup,
  onToggleMemberSelection,
  onUpsertMemberProfile,
  onSelectLead,
  getAgentById,
  getTeamRoleDescription,
  getTeamPriorityDescription,
  onClose,
  onSubmit,
}: TeamFormModalProps) => {
  const isCreateMode = mode === 'create';
  const leadInputName = isCreateMode ? 'team-create-lead' : 'team-edit-lead';
  const { t } = useI18n();
  const teamTemplateOptions = getTeamTemplateOptions(t);
  const teamPriorityOptions = getTeamPriorityOptions(t);
  const teamRoleOptions = getTeamRoleOptions(t);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl p-6 w-full max-w-3xl mx-4">
        <h3 className="text-lg font-semibold text-surface-900 mb-4">
          {isCreateMode ? t('teams.teamForm.createTitle') : t('teams.teamForm.editTitle')}
        </h3>
        <div className="space-y-4 max-h-[70vh] overflow-y-auto">
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1">{t('common.id')}</label>
            <input
              type="text"
              value={form.id}
              disabled={!isCreateMode}
              onChange={(e) => onChange({ ...form, id: e.target.value })}
              className={
                isCreateMode
                  ? `w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 ${
                      createIdError ? 'border-red-300 bg-red-50/40' : 'border-surface-300'
                    }`
                  : 'w-full px-3 py-2 border border-surface-300 rounded-lg bg-surface-50 text-surface-500 cursor-not-allowed'
              }
              placeholder={t('teams.teamForm.teamIdPlaceholder')}
              aria-invalid={Boolean(createIdError)}
            />
            {createIdError && (
              <p className="mt-1 text-xs text-red-600">{createIdError}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1">{t('common.name')}</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => onChange({ ...form, name: e.target.value })}
              className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 ${
                isCreateMode && createNameError ? 'border-red-300 bg-red-50/40' : 'border-surface-300'
              }`}
              placeholder={t('teams.teamForm.namePlaceholder')}
              aria-invalid={Boolean(createNameError)}
            />
            {createNameError && (
              <p className="mt-1 text-xs text-red-600">{createNameError}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1">{t('common.description')}</label>
            <input
              type="text"
              value={form.description}
              onChange={(e) => onChange({ ...form, description: e.target.value })}
              className="w-full px-3 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder={t('teams.teamForm.descriptionPlaceholder')}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1">{t('teams.teamForm.members')}</label>
            <div className="max-h-40 overflow-y-auto border border-surface-300 rounded-lg p-2">
              {agents.map((agent) => (
                <label key={agent.id} className="flex items-center gap-2 p-1 hover:bg-surface-50 rounded cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.members.includes(agent.id)}
                    onChange={(e) => onToggleMemberSelection(agent.id, e.target.checked)}
                    className="rounded border-surface-300 text-primary-500 focus:ring-primary-500"
                  />
                  <span className="text-sm text-surface-700">{agent.name}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="rounded-2xl border border-surface-200 bg-surface-50/80 px-4 py-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <h4 className="text-sm font-medium text-surface-800">{t('teams.teamForm.advancedSettings')}</h4>
                <p className="mt-1 text-xs text-surface-500">{t('teams.teamForm.advancedHint')}</p>
              </div>
              <button
                type="button"
                onClick={() => setAdvancedOpen((current) => !current)}
                data-testid="team-advanced-toggle"
                className="inline-flex items-center justify-center gap-2 rounded-xl border border-surface-300 bg-white px-3 py-2 text-sm font-medium text-surface-700 transition-colors hover:border-primary-300 hover:text-primary-700"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className={`h-4 w-4 transition-transform ${advancedOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
                {advancedOpen ? t('teams.teamForm.advancedCollapse') : t('teams.teamForm.advancedExpand')}
              </button>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {advancedSummaryItems.map((item) => (
                <span key={item} className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-surface-600 ring-1 ring-surface-200">
                  {item}
                </span>
              ))}
            </div>
          </div>
          {advancedOpen && (
            <div className="space-y-4" data-testid="team-advanced-panel">
              <div className="border-t border-surface-200 pt-4">
                <label className="block text-sm font-medium text-surface-700 mb-1">{t('teams.teamForm.customWorkspace')}</label>
                <input
                  type="text"
                  value={form.workspace}
                  onChange={(e) => onChange({ ...form, workspace: e.target.value })}
                  className="w-full px-3 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder={t('teams.teamForm.customWorkspacePlaceholder')}
                />
                {isCreateMode && (
                  <p className="mt-1 text-xs text-surface-500">{t('teams.teamForm.customWorkspaceHint')}</p>
                )}
              </div>
              {form.members.length > 0 && (
                <div className="border-t border-surface-200 pt-4">
                  <label className="block text-sm font-medium text-surface-700 mb-2">{t('teams.teamForm.templateLabel')}</label>
                  <div className="rounded-2xl border border-surface-200 bg-white px-4 py-4">
                    <div className="mb-3 rounded-xl bg-surface-50 px-4 py-3">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-medium text-surface-800">{t('teams.teamForm.systemRecommended')}</p>
                          <p className="mt-1 text-xs text-surface-500">
                            {t('teams.teamForm.recommendedTemplate', {
                              template: recommendedTeamTemplate.label,
                              lead: recommendedTeamLead ? ` · ${t('teams.teamForm.recommendedLead', { name: recommendedTeamLead.name })}` : '',
                            })}
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={onApplyRecommendedTeamSetup}
                          className="inline-flex items-center justify-center rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-700 transition-colors hover:bg-emerald-100"
                        >
                          {t('teams.teamForm.applyRecommended')}
                        </button>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,220px),1fr]">
                      <div>
                        <select
                          value={selectedTeamTemplateId}
                          onChange={(e) => onSelectTemplate(e.target.value as TeamTemplateId)}
                          className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm"
                        >
                          {teamTemplateOptions.map((option) => (
                            <option key={option.id} value={option.id}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          onClick={() => onApplyTeamTemplate(selectedTeamTemplateId)}
                          className="mt-3 inline-flex w-full items-center justify-center rounded-lg border border-primary-200 bg-primary-50 px-3 py-2 text-sm font-medium text-primary-700 transition-colors hover:bg-primary-100"
                        >
                          {t('teams.teamForm.applyTemplate')}
                        </button>
                      </div>
                      <div className="rounded-xl bg-surface-50 px-4 py-3">
                        <p className="text-sm font-medium text-surface-800">{selectedTeamTemplate.label}</p>
                        <p className="mt-1 text-xs text-surface-500">{selectedTeamTemplate.description}</p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {selectedTeamTemplate.assignments.map((item) => (
                            <span key={item} className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-surface-600 ring-1 ring-surface-200">
                              {item}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              {form.members.length > 0 && (
                <div className="border-t border-surface-200 pt-4">
                  <label className="block text-sm font-medium text-surface-700 mb-2">{t('teams.teamForm.teamAssignments')}</label>
                  <div className="mb-3 rounded-2xl border border-surface-200 bg-white px-4 py-3 text-xs text-surface-600">
                    {teamAssignmentGuide}
                  </div>
                  <div className="space-y-3">
                    {form.members.map((agentId) => {
                      const agent = getAgentById(agentId);
                      const profile = form.member_profiles[agentId] || { role: 'member', responsibility: '', priority: 100, isLead: false };
                      return (
                        <div key={agentId} className="rounded-xl border border-surface-200 p-3">
                          <div className="flex items-center justify-between gap-3">
                            <div className="font-medium text-surface-900">{agent?.name || agentId}</div>
                            <label className="flex items-center gap-2 text-xs text-surface-600">
                              <input
                                type="radio"
                                name={leadInputName}
                                checked={Boolean(profile.isLead)}
                                onChange={() => onSelectLead(agentId)}
                              />
                              {t('teams.teamForm.lead')}
                            </label>
                          </div>
                          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
                            <label className="block">
                              <span className="mb-1 block text-xs font-medium text-surface-600">{t('teams.teamForm.role')}</span>
                              <select
                                value={profile.role || 'member'}
                                onChange={(e) => onUpsertMemberProfile(agentId, { role: e.target.value })}
                                className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm"
                              >
                                {teamRoleOptions.map((option) => (
                                  <option key={option.id} value={option.id}>
                                    {option.label}
                                  </option>
                                ))}
                              </select>
                              <p className="mt-1 text-[11px] text-surface-400">
                                {getTeamRoleDescription(profile.role)}
                              </p>
                            </label>
                            <label className="block">
                              <span className="mb-1 block text-xs font-medium text-surface-600">{t('teams.teamForm.order')}</span>
                              <select
                                value={profile.priority ?? 100}
                                onChange={(e) => onUpsertMemberProfile(agentId, { priority: Number(e.target.value) || 100 })}
                                className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm"
                              >
                                {teamPriorityOptions.map((option) => (
                                  <option key={option.value} value={option.value}>
                                    {option.label}
                                  </option>
                                ))}
                              </select>
                              <p className="mt-1 text-[11px] text-surface-400">
                                {getTeamPriorityDescription(profile.priority)}
                              </p>
                            </label>
                            <label className="block">
                              <span className="mb-1 block text-xs font-medium text-surface-600">{t('teams.teamForm.responsibility')}</span>
                              <input
                                type="text"
                                value={profile.responsibility || ''}
                                onChange={(e) => onUpsertMemberProfile(agentId, { responsibility: e.target.value })}
                                className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm"
                                placeholder={isCreateMode ? t('teams.teamForm.responsibilityPlaceholderCreate') : t('teams.teamForm.responsibilityPlaceholderEdit')}
                              />
                              <p className="mt-1 text-[11px] text-surface-400">{t('teams.teamForm.responsibilityHint')}</p>
                            </label>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-surface-700 hover:bg-surface-100 rounded-lg transition-colors"
          >
            {t('common.cancel')}
          </button>
          <button
            onClick={onSubmit}
            disabled={submitDisabled}
            className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors disabled:cursor-not-allowed disabled:bg-surface-300"
          >
            {isCreateMode ? t('common.create') : t('common.save')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default TeamFormModal;
