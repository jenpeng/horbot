import type { Dispatch, SetStateAction } from 'react';
import {
  AGENT_PERMISSION_PRESETS,
  AGENT_PROFILE_PRESETS,
} from '../../constants';
import {
  MEMORY_REASONING_STYLE_OPTIONS,
} from '../../pages/teams/formOptions';
import type {
  AgentFormState,
  ProviderInfo,
  TeamInfo,
} from '../../pages/teams/types';

interface AgentFormModalProps {
  mode: 'create' | 'edit';
  form: AgentFormState;
  setForm: Dispatch<SetStateAction<AgentFormState>>;
  providers: ProviderInfo[];
  teams: TeamInfo[];
  capabilityOptions: Array<{ id: string; label: string; description: string }>;
  createIdError?: string;
  createNameError?: string;
  createProviderError?: string;
  createModelError?: string;
  submitDisabled?: boolean;
  recommendedMemoryProfile: AgentFormState['memory_bank_profile'];
  recommendedMemoryProfileMeta: {
    label: string;
    summary: string;
  };
  isUsingRecommendedMemoryProfile: boolean;
  advancedOpen: boolean;
  setAdvancedOpen: Dispatch<SetStateAction<boolean>>;
  advancedSummaryItems: string[];
  onApplyAgentProfilePreset: (profileId: string) => void;
  onApplyAgentPermissionPreset: (permissionProfileId: string) => void;
  onRestoreRecommendedMemoryProfile: () => void;
  onClose: () => void;
  onSubmit: () => void;
}

const AgentFormModal = ({
  mode,
  form,
  setForm,
  providers,
  teams,
  capabilityOptions,
  createIdError = '',
  createNameError = '',
  createProviderError = '',
  createModelError = '',
  submitDisabled = false,
  recommendedMemoryProfile,
  recommendedMemoryProfileMeta,
  isUsingRecommendedMemoryProfile,
  advancedOpen,
  setAdvancedOpen,
  advancedSummaryItems,
  onApplyAgentProfilePreset,
  onApplyAgentPermissionPreset,
  onRestoreRecommendedMemoryProfile,
  onClose,
  onSubmit,
}: AgentFormModalProps) => {
  const isCreateMode = mode === 'create';

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl p-6 w-full max-w-4xl mx-4">
        <h3 className="text-lg font-semibold text-surface-900 mb-4">
          {isCreateMode ? '创建新 Agent' : '编辑 Agent'}
        </h3>
        <div className="space-y-4 max-h-[70vh] overflow-y-auto">
          <div>
            <label htmlFor="agent-form-id" className="block text-sm font-medium text-surface-700 mb-1">ID</label>
            <input
              id="agent-form-id"
              type="text"
              value={form.id}
              disabled={!isCreateMode}
              onChange={(e) => setForm({ ...form, id: e.target.value })}
              className={
                isCreateMode
                  ? `w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 ${
                      createIdError ? 'border-red-300 bg-red-50/40' : 'border-surface-300'
                    }`
                  : 'w-full px-3 py-2 border border-surface-300 rounded-lg bg-surface-50 text-surface-500 cursor-not-allowed'
              }
              placeholder="agent-id"
              aria-invalid={Boolean(createIdError)}
            />
            {createIdError && (
              <p className="mt-1 text-xs text-red-600">{createIdError}</p>
            )}
          </div>
          <div>
            <label htmlFor="agent-form-name" className="block text-sm font-medium text-surface-700 mb-1">名称</label>
            <input
              id="agent-form-name"
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 ${
                isCreateMode && createNameError ? 'border-red-300 bg-red-50/40' : 'border-surface-300'
              }`}
              placeholder="Agent 名称"
              aria-invalid={Boolean(createNameError)}
            />
            {createNameError && (
              <p className="mt-1 text-xs text-red-600">{createNameError}</p>
            )}
          </div>
          <div className="border-t border-surface-200 pt-4">
            <h4 className="text-sm font-medium text-surface-700 mb-3">模型配置</h4>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="agent-form-provider" className="block text-xs font-medium text-surface-600 mb-1">供应商</label>
                <select
                  id="agent-form-provider"
                  value={form.provider}
                  onChange={(e) => setForm({ ...form, provider: e.target.value })}
                  className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm ${
                    isCreateMode && createProviderError ? 'border-red-300 bg-red-50/40' : 'border-surface-300'
                  }`}
                  aria-invalid={Boolean(createProviderError)}
                >
                  {isCreateMode && <option value="">请选择供应商</option>}
                  <option value="auto" disabled={isCreateMode}>自动选择</option>
                  {providers.map((provider) => (
                    <option key={provider.id} value={provider.id} disabled={!provider.configured}>
                      {provider.name} {!provider.configured && '(未配置)'}
                    </option>
                  ))}
                </select>
                {createProviderError && (
                  <p className="mt-1 text-xs text-red-600">{createProviderError}</p>
                )}
              </div>
              <div>
                <label htmlFor="agent-form-model" className="block text-xs font-medium text-surface-600 mb-1">模型名称</label>
                <input
                  id="agent-form-model"
                  type="text"
                  value={form.model}
                  onChange={(e) => setForm({ ...form, model: e.target.value })}
                  className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm ${
                    isCreateMode && createModelError ? 'border-red-300 bg-red-50/40' : 'border-surface-300'
                  }`}
                  placeholder="如: gpt-4o, claude-sonnet-4-5"
                  aria-invalid={Boolean(createModelError)}
                />
                {createModelError ? (
                  <p className="mt-1 text-xs text-red-600">{createModelError}</p>
                ) : (
                  <p className="mt-1 text-xs text-surface-500">
                    创建阶段需要明确 provider 和 model，创建完成后即可直接开始首次私聊。
                  </p>
                )}
              </div>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1">描述</label>
            <input
              type="text"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="w-full px-3 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="Agent 描述"
            />
          </div>
          <div className="border-t border-surface-200 pt-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h4 className="text-sm font-medium text-surface-700">协作画像</h4>
                <p className="mt-1 text-xs text-surface-500">
                  {isCreateMode
                    ? '用可视化方式给 Agent 一个默认工作风格，首次私聊时再继续细化。'
                    : '这里保存 Agent 的可视化 profile，不直接替代首次私聊里的细节设定。'}
                </p>
              </div>
              {form.profile && (
                <button
                  type="button"
                  onClick={() => setForm({ ...form, profile: '', memory_bank_profile: recommendedMemoryProfile })}
                  className="text-xs text-surface-500 hover:text-surface-700"
                >
                  清除画像
                </button>
              )}
            </div>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
              {AGENT_PROFILE_PRESETS.map((preset) => {
                const selected = form.profile === preset.id;
                return (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => onApplyAgentProfilePreset(preset.id)}
                    className={`rounded-2xl border p-4 text-left transition-colors ${
                      selected
                        ? 'border-primary-500 bg-primary-50 shadow-sm'
                        : 'border-surface-200 bg-white hover:border-primary-200 hover:bg-primary-50/40'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-sm font-semibold text-surface-900">{preset.label}</div>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${preset.accent}`}>
                        预设
                      </span>
                    </div>
                    <p className="mt-2 text-xs text-surface-700">{preset.summary}</p>
                    <p className="mt-2 text-[11px] text-surface-500">{preset.detail}</p>
                    <div className="mt-3 flex flex-wrap gap-1">
                      {preset.suggestedCapabilities.map((capabilityId) => {
                        const capability = capabilityOptions.find((item) => item.id === capabilityId);
                        return (
                          <span key={capabilityId} className="rounded-full bg-surface-100 px-2 py-0.5 text-[10px] text-surface-600">
                            {capability?.label || capabilityId}
                          </span>
                        );
                      })}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
          <div className="border-t border-surface-200 pt-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h4 className="text-sm font-medium text-surface-700">工具权限</h4>
                <p className="mt-1 text-xs text-surface-500">
                  {isCreateMode
                    ? '创建时可先给一个默认权限档位；不选则继承系统全局配置。'
                    : '为当前 Agent 选择默认权限档位；未单独设置时将继承系统全局权限。'}
                </p>
              </div>
              {!isCreateMode && form.permission_profile && (
                <button
                  type="button"
                  onClick={() => setForm({ ...form, permission_profile: '' })}
                  className="text-xs text-surface-500 hover:text-surface-700"
                >
                  继承全局
                </button>
              )}
            </div>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
              {AGENT_PERMISSION_PRESETS.map((preset) => {
                const selected = (form.permission_profile || 'inherit') === preset.id;
                return (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => onApplyAgentPermissionPreset(preset.id)}
                    className={`rounded-2xl border p-4 text-left transition-colors ${
                      selected
                        ? 'border-primary-500 bg-primary-50 shadow-sm'
                        : 'border-surface-200 bg-white hover:border-primary-200 hover:bg-primary-50/40'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-sm font-semibold text-surface-900">{preset.label}</div>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${preset.accent}`}>
                        权限
                      </span>
                    </div>
                    <p className="mt-2 text-xs text-surface-700">{preset.summary}</p>
                    <p className="mt-2 text-[11px] text-surface-500">{preset.detail}</p>
                  </button>
                );
              })}
            </div>
          </div>
          {isCreateMode ? (
            <>
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 px-4 py-4 text-sm text-surface-700">
                <div className="font-semibold text-surface-900">记忆银行画像已自动设置为默认策略。</div>
                <div className="mt-1">
                  当前会按“{recommendedMemoryProfileMeta.label}”创建记忆偏好，系统会自动决定长期目标、召回倾向和反思重点。通常不需要在创建阶段手动配置，后续如果觉得不合适，再到编辑页微调即可。
                </div>
              </div>
              <div className="rounded-2xl border border-primary-200 bg-primary-50/70 px-4 py-4 text-sm text-surface-700">
                <div className="font-semibold text-surface-900">创建前需要先把模型配置补齐。</div>
                <div className="mt-1">
                  这样创建完成后就可以直接进入首次私聊，引导它完善职责、风格与协作边界，不再出现“先创建、再补模型”的往返操作。
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="rounded-2xl border border-surface-200 bg-surface-50/80 px-4 py-4">
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                  <div>
                    <h4 className="text-sm font-medium text-surface-800">高级设置</h4>
                    <p className="mt-1 text-xs text-surface-500">低频配置默认收起，避免编辑 Agent 时一次看到过多信息。</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setAdvancedOpen((current) => !current)}
                    data-testid="agent-edit-advanced-toggle"
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
                <>
                  <div className="border-t border-surface-200 pt-4" data-testid="agent-edit-advanced-panel">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <h4 className="text-sm font-medium text-surface-700">记忆银行画像</h4>
                        <p className="mt-1 text-xs text-surface-500">默认已按协作画像自动设置。只有当你明确想改变记忆召回倾向时，再手动微调。</p>
                      </div>
                      {!isUsingRecommendedMemoryProfile && (
                        <button
                          type="button"
                          onClick={onRestoreRecommendedMemoryProfile}
                          className="text-xs text-surface-500 hover:text-surface-700"
                        >
                          恢复系统推荐
                        </button>
                      )}
                    </div>
                    <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50/70 px-4 py-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-surface-900">{recommendedMemoryProfileMeta.label}</span>
                        <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-surface-700 ring-1 ring-surface-200">
                          {MEMORY_REASONING_STYLE_OPTIONS.find((item) => item.id === recommendedMemoryProfile.reasoning_style)?.label || recommendedMemoryProfile.reasoning_style}
                        </span>
                        <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${isUsingRecommendedMemoryProfile ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                          {isUsingRecommendedMemoryProfile ? '正在使用推荐策略' : '已偏离推荐策略'}
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-surface-600">{recommendedMemoryProfileMeta.summary}</p>
                    </div>
                    <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
                      <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4">
                        <label className="block text-sm font-medium text-surface-800">长期目标</label>
                        <p className="mt-1 text-xs text-surface-500">一句话说明这个 Agent 的长期记忆应该优先服务什么。</p>
                        <textarea
                          value={form.memory_bank_profile.mission}
                          onChange={(e) => setForm((current) => ({
                            ...current,
                            memory_bank_profile: {
                              ...current.memory_bank_profile,
                              mission: e.target.value,
                            },
                          }))}
                          className="mt-3 h-28 w-full rounded-xl border border-surface-300 bg-white px-3 py-3 text-sm text-surface-800 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                          placeholder="例如：优先保留与前端交互优化、用户习惯和回归风险相关的长期记忆。"
                        />
                      </div>
                      <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4 xl:col-span-2">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <label className="block text-sm font-medium text-surface-800">记忆策略</label>
                            <p className="mt-1 text-xs text-surface-500">决定它在解释记忆和做轻量反思时更偏向哪种方式。</p>
                          </div>
                          {form.memory_bank_profile.reasoning_style && (
                            <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-surface-700 ring-1 ring-surface-200">
                              {MEMORY_REASONING_STYLE_OPTIONS.find((item) => item.id === form.memory_bank_profile.reasoning_style)?.label || form.memory_bank_profile.reasoning_style}
                            </span>
                          )}
                        </div>
                        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                          {MEMORY_REASONING_STYLE_OPTIONS.map((option) => {
                            const selected = form.memory_bank_profile.reasoning_style === option.id;
                            return (
                              <button
                                key={option.id}
                                type="button"
                                onClick={() => setForm((current) => ({
                                  ...current,
                                  memory_bank_profile: {
                                    ...current.memory_bank_profile,
                                    reasoning_style: current.memory_bank_profile.reasoning_style === option.id ? '' : option.id,
                                  },
                                }))}
                                className={`rounded-2xl border p-4 text-left transition-colors ${
                                  selected
                                    ? 'border-primary-500 bg-primary-50 shadow-sm'
                                    : 'border-surface-200 bg-white hover:border-primary-200 hover:bg-primary-50/40'
                                }`}
                              >
                                <div className="text-sm font-semibold text-surface-900">{option.label}</div>
                                <p className="mt-2 text-xs text-surface-600">{option.description}</p>
                              </button>
                            );
                          })}
                        </div>
                        <div className="mt-4">
                          <label className="block text-sm font-medium text-surface-800">优先注意事项</label>
                          <p className="mt-1 text-xs text-surface-500">每行一条，告诉系统在召回和反思时应该优先关注什么。</p>
                          <textarea
                            value={form.memory_bank_profile.directives.join('\n')}
                            onChange={(e) => setForm((current) => ({
                              ...current,
                              memory_bank_profile: {
                                ...current.memory_bank_profile,
                                directives: e.target.value
                                  .split('\n')
                                  .map((item) => item.trim())
                                  .filter(Boolean),
                              },
                            }))}
                            className="mt-3 h-28 w-full rounded-xl border border-surface-300 bg-white px-3 py-3 text-sm text-surface-800 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                            placeholder={'例如：\n优先召回与当前团队协作有关的决策\n遇到冲突记忆时优先相信较新的约束\n反思时记录可复用的排障策略'}
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="border-t border-surface-200 pt-4">
                    <h4 className="text-sm font-medium text-surface-700 mb-3">工作空间与团队</h4>
                    <div>
                      <label className="block text-xs font-medium text-surface-600 mb-1">自定义工作空间</label>
                      <input
                        type="text"
                        value={form.workspace}
                        onChange={(e) => setForm({ ...form, workspace: e.target.value })}
                        className="w-full px-3 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
                        placeholder="留空使用默认 Agent 目录"
                      />
                      <p className="mt-1 text-xs text-surface-500">
                        填写后该目录会成为 Agent 实际工作区，记忆与会话数据写入其中隐藏目录。
                      </p>
                    </div>
                    <div className="mt-3">
                      <label className="block text-xs font-medium text-surface-600 mb-2">所属团队</label>
                      <div className="max-h-32 overflow-y-auto space-y-2 border border-surface-200 rounded-lg p-3">
                        {teams.length === 0 ? (
                          <p className="text-xs text-surface-500">暂无团队，可稍后再绑定。</p>
                        ) : (
                          teams.map((team) => (
                            <label key={team.id} className="flex items-center gap-2 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={form.teams.includes(team.id)}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setForm({ ...form, teams: [...form.teams, team.id] });
                                  } else {
                                    setForm({ ...form, teams: form.teams.filter((id) => id !== team.id) });
                                  }
                                }}
                                className="rounded border-surface-300 text-primary-500 focus:ring-primary-500"
                              />
                              <span className="text-sm text-surface-700">{team.name}</span>
                            </label>
                          ))
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="border-t border-surface-200 pt-4">
                    <h4 className="text-sm font-medium text-surface-700 mb-3">引导式配置</h4>
                    <div className="rounded-2xl border border-primary-200 bg-primary-50/70 px-4 py-4 text-sm text-surface-700">
                      <div className="font-semibold text-surface-900">人格、系统提示词和用户偏好不再在这里直接编辑。</div>
                      <div className="mt-1">
                        请在首次私聊时由 AI 引导完成，并将结果沉淀到该 Agent 的 `SOUL.md`、`USER.md` 等工作区文件中。
                      </div>
                    </div>
                  </div>

                  <div className="border-t border-surface-200 pt-4">
                    <h4 className="text-sm font-medium text-surface-700 mb-3">协作能力标签</h4>
                    <div className="flex flex-wrap gap-2">
                      {capabilityOptions.map((capability) => {
                        const selected = form.capabilities.includes(capability.id);
                        return (
                          <button
                            key={capability.id}
                            type="button"
                            onClick={() => setForm({
                              ...form,
                              capabilities: selected
                                ? form.capabilities.filter((item) => item !== capability.id)
                                : [...form.capabilities, capability.id],
                            })}
                            className={`rounded-2xl border px-3 py-2 text-left transition-colors ${
                              selected
                                ? 'border-primary-500 bg-primary-50 text-primary-700'
                                : 'border-surface-200 bg-white text-surface-700 hover:border-primary-200 hover:bg-primary-50/40'
                            }`}
                          >
                            <div className="text-sm font-medium">{capability.label}</div>
                            <div className="mt-0.5 text-[11px] text-surface-500">{capability.description}</div>
                          </button>
                        );
                      })}
                    </div>
                    <p className="mt-3 text-xs text-surface-500">
                      这些标签用于团队协作展示与后续能力匹配；优先选择稳定、可复用的职责标签。
                    </p>
                  </div>
                </>
              )}
            </>
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

export default AgentFormModal;
