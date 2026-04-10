import type { Dispatch, SetStateAction } from 'react';
import {
  TEAM_TEMPLATE_OPTIONS,
  TEAM_PRIORITY_OPTIONS,
  TEAM_ROLE_OPTIONS,
} from '../../pages/teams/formOptions';
import type { TeamTemplateId } from '../../pages/teams/formOptions';
import type {
  AgentInfo,
  TeamFormState,
  TeamMemberProfile,
} from '../../pages/teams/types';

type TeamTemplateOption = (typeof TEAM_TEMPLATE_OPTIONS)[number];

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

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl p-6 w-full max-w-3xl mx-4">
        <h3 className="text-lg font-semibold text-surface-900 mb-4">
          {isCreateMode ? '创建新团队' : '编辑团队'}
        </h3>
        <div className="space-y-4 max-h-[70vh] overflow-y-auto">
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1">ID</label>
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
              placeholder="team-id"
              aria-invalid={Boolean(createIdError)}
            />
            {createIdError && (
              <p className="mt-1 text-xs text-red-600">{createIdError}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1">名称</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => onChange({ ...form, name: e.target.value })}
              className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 ${
                isCreateMode && createNameError ? 'border-red-300 bg-red-50/40' : 'border-surface-300'
              }`}
              placeholder="团队名称"
              aria-invalid={Boolean(createNameError)}
            />
            {createNameError && (
              <p className="mt-1 text-xs text-red-600">{createNameError}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1">描述</label>
            <input
              type="text"
              value={form.description}
              onChange={(e) => onChange({ ...form, description: e.target.value })}
              className="w-full px-3 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="团队描述"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1">成员 (选择 Agent)</label>
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
                <h4 className="text-sm font-medium text-surface-800">高级设置</h4>
                <p className="mt-1 text-xs text-surface-500">团队分工和共享工作区属于低频配置，默认收起。</p>
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
                {advancedOpen ? '收起高级设置' : '展开高级设置'}
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
                <label className="block text-sm font-medium text-surface-700 mb-1">自定义工作空间</label>
                <input
                  type="text"
                  value={form.workspace}
                  onChange={(e) => onChange({ ...form, workspace: e.target.value })}
                  className="w-full px-3 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="留空使用默认团队目录"
                />
                {isCreateMode && (
                  <p className="mt-1 text-xs text-surface-500">填写后该目录会成为团队共享工作区，协作元数据写入其中隐藏目录。</p>
                )}
              </div>
              {form.members.length > 0 && (
                <div className="border-t border-surface-200 pt-4">
                  <label className="block text-sm font-medium text-surface-700 mb-2">协作模板</label>
                  <div className="rounded-2xl border border-surface-200 bg-white px-4 py-4">
                    <div className="mb-3 rounded-xl bg-surface-50 px-4 py-3">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-medium text-surface-800">系统推荐</p>
                          <p className="mt-1 text-xs text-surface-500">
                            推荐模板：{recommendedTeamTemplate.label}{recommendedTeamLead ? ` · 推荐负责人：${recommendedTeamLead.name}` : ''}
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={onApplyRecommendedTeamSetup}
                          className="inline-flex items-center justify-center rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-700 transition-colors hover:bg-emerald-100"
                        >
                          采用系统推荐
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
                          {TEAM_TEMPLATE_OPTIONS.map((option) => (
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
                          套用到当前成员
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
                  <label className="block text-sm font-medium text-surface-700 mb-2">团队分工</label>
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
                              负责人
                            </label>
                          </div>
                          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
                            <label className="block">
                              <span className="mb-1 block text-xs font-medium text-surface-600">角色</span>
                              <select
                                value={profile.role || 'member'}
                                onChange={(e) => onUpsertMemberProfile(agentId, { role: e.target.value })}
                                className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm"
                              >
                                {TEAM_ROLE_OPTIONS.map((option) => (
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
                              <span className="mb-1 block text-xs font-medium text-surface-600">接力顺序</span>
                              <select
                                value={profile.priority ?? 100}
                                onChange={(e) => onUpsertMemberProfile(agentId, { priority: Number(e.target.value) || 100 })}
                                className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm"
                              >
                                {TEAM_PRIORITY_OPTIONS.map((option) => (
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
                              <span className="mb-1 block text-xs font-medium text-surface-600">负责内容</span>
                              <input
                                type="text"
                                value={profile.responsibility || ''}
                                onChange={(e) => onUpsertMemberProfile(agentId, { responsibility: e.target.value })}
                                className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm"
                                placeholder={isCreateMode ? '例如：负责需求拆解和接力安排' : '例如：负责结果验收和风险把关'}
                              />
                              <p className="mt-1 text-[11px] text-surface-400">一句话写清楚这个 Agent 的具体职责。</p>
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
            取消
          </button>
          <button
            onClick={onSubmit}
            disabled={submitDisabled}
            className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors disabled:cursor-not-allowed disabled:bg-surface-300"
          >
            {isCreateMode ? '创建' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default TeamFormModal;
