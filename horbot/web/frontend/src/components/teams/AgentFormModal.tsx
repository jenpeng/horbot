import type { Dispatch, SetStateAction } from 'react';
import {
  getAgentPermissionPresets,
  getAgentProfilePresets,
} from '../../constants';
import { useI18n } from '../../contexts/I18nContext';
import {
  getMemoryReasoningStyleOptions,
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
  const { t } = useI18n();
  const agentProfilePresets = getAgentProfilePresets(t);
  const agentPermissionPresets = getAgentPermissionPresets(t);
  const memoryReasoningStyleOptions = getMemoryReasoningStyleOptions(t);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl p-6 w-full max-w-4xl mx-4">
        <h3 className="text-lg font-semibold text-surface-900 mb-4">
          {isCreateMode ? t('teams.agentForm.createTitle') : t('teams.agentForm.editTitle')}
        </h3>
        <div className="space-y-4 max-h-[70vh] overflow-y-auto">
          <div>
            <label htmlFor="agent-form-id" className="block text-sm font-medium text-surface-700 mb-1">{t('common.id')}</label>
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
              placeholder={t('teams.teamForm.agentIdPlaceholder')}
              aria-invalid={Boolean(createIdError)}
            />
            {createIdError && (
              <p className="mt-1 text-xs text-red-600">{createIdError}</p>
            )}
          </div>
          <div>
            <label htmlFor="agent-form-name" className="block text-sm font-medium text-surface-700 mb-1">{t('common.name')}</label>
            <input
              id="agent-form-name"
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 ${
                isCreateMode && createNameError ? 'border-red-300 bg-red-50/40' : 'border-surface-300'
              }`}
              placeholder={t('teams.agentForm.namePlaceholder')}
              aria-invalid={Boolean(createNameError)}
            />
            {createNameError && (
              <p className="mt-1 text-xs text-red-600">{createNameError}</p>
            )}
          </div>
          <div className="border-t border-surface-200 pt-4">
            <h4 className="text-sm font-medium text-surface-700 mb-3">{t('teams.agentForm.modelConfig')}</h4>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="agent-form-provider" className="block text-xs font-medium text-surface-600 mb-1">{t('common.provider')}</label>
                <select
                  id="agent-form-provider"
                  value={form.provider}
                  onChange={(e) => setForm({ ...form, provider: e.target.value })}
                  className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm ${
                    isCreateMode && createProviderError ? 'border-red-300 bg-red-50/40' : 'border-surface-300'
                  }`}
                  aria-invalid={Boolean(createProviderError)}
                >
                  {isCreateMode && <option value="">{t('teams.agentForm.providerPlaceholder')}</option>}
                  <option value="auto" disabled={isCreateMode}>{t('teams.agentForm.autoSelect')}</option>
                  {providers.map((provider) => (
                    <option key={provider.id} value={provider.id} disabled={!provider.configured}>
                      {provider.name} {!provider.configured && `(${t('teams.agentForm.notConfigured')})`}
                    </option>
                  ))}
                </select>
                {createProviderError && (
                  <p className="mt-1 text-xs text-red-600">{createProviderError}</p>
                )}
              </div>
              <div>
                <label htmlFor="agent-form-model" className="block text-xs font-medium text-surface-600 mb-1">{t('common.model')}</label>
                <input
                  id="agent-form-model"
                  type="text"
                  value={form.model}
                  onChange={(e) => setForm({ ...form, model: e.target.value })}
                  className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm ${
                    isCreateMode && createModelError ? 'border-red-300 bg-red-50/40' : 'border-surface-300'
                  }`}
                  placeholder={t('teams.agentForm.modelPlaceholder')}
                  aria-invalid={Boolean(createModelError)}
                />
                {createModelError ? (
                  <p className="mt-1 text-xs text-red-600">{createModelError}</p>
                ) : (
                  <p className="mt-1 text-xs text-surface-500">
                    {t('teams.agentForm.modelHint')}
                  </p>
                )}
              </div>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1">{t('common.description')}</label>
            <input
              type="text"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="w-full px-3 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder={t('teams.agentForm.descriptionPlaceholder')}
            />
          </div>
          <div className="border-t border-surface-200 pt-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h4 className="text-sm font-medium text-surface-700">{t('teams.agentForm.profileSectionTitle')}</h4>
                <p className="mt-1 text-xs text-surface-500">
                  {isCreateMode
                    ? t('teams.agentForm.profileCreateHint')
                    : t('teams.agentForm.profileEditHint')}
                </p>
              </div>
              {form.profile && (
                <button
                  type="button"
                  onClick={() => setForm({ ...form, profile: '', memory_bank_profile: recommendedMemoryProfile })}
                  className="text-xs text-surface-500 hover:text-surface-700"
                >
                  {t('teams.agentForm.clearProfile')}
                </button>
              )}
            </div>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
              {agentProfilePresets.map((preset) => {
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
                        {t('teams.agentForm.presetBadge')}
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
                <h4 className="text-sm font-medium text-surface-700">{t('teams.agentForm.permissionSectionTitle')}</h4>
                <p className="mt-1 text-xs text-surface-500">
                  {isCreateMode
                    ? t('teams.agentForm.permissionCreateHint')
                    : t('teams.agentForm.permissionEditHint')}
                </p>
              </div>
              {!isCreateMode && form.permission_profile && (
                        <button
                          type="button"
                          onClick={() => setForm({ ...form, permission_profile: '' })}
                          className="text-xs text-surface-500 hover:text-surface-700"
                        >
                          {t('teams.agentForm.cancelGlobalInherit')}
                        </button>
              )}
            </div>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
              {agentPermissionPresets.map((preset) => {
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
                        {t('teams.agentForm.permissionBadge')}
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
                <div className="font-semibold text-surface-900">{t('teams.agentForm.memoryDefaultNoticeTitle')}</div>
                <div className="mt-1">
                  {t('teams.agentForm.memoryDefaultNoticeBody', { label: recommendedMemoryProfileMeta.label })}
                </div>
              </div>
              <div className="rounded-2xl border border-primary-200 bg-primary-50/70 px-4 py-4 text-sm text-surface-700">
                <div className="font-semibold text-surface-900">{t('teams.agentForm.modelRequiredNoticeTitle')}</div>
                <div className="mt-1">
                  {t('teams.agentForm.modelRequiredNoticeBody')}
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="rounded-2xl border border-surface-200 bg-surface-50/80 px-4 py-4">
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                  <div>
                    <h4 className="text-sm font-medium text-surface-800">{t('teams.agentForm.advancedSettings')}</h4>
                    <p className="mt-1 text-xs text-surface-500">{t('teams.agentForm.advancedHint')}</p>
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
                    {advancedOpen ? t('teams.agentForm.advancedCollapse') : t('teams.agentForm.advancedExpand')}
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
                        <h4 className="text-sm font-medium text-surface-700">{t('teams.agentForm.memoryProfileTitle')}</h4>
                        <p className="mt-1 text-xs text-surface-500">{t('teams.agentForm.memoryProfileHint')}</p>
                      </div>
                      {!isUsingRecommendedMemoryProfile && (
                        <button
                          type="button"
                          onClick={onRestoreRecommendedMemoryProfile}
                          className="text-xs text-surface-500 hover:text-surface-700"
                        >
                          {t('teams.agentForm.restoreRecommended')}
                        </button>
                      )}
                    </div>
                    <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50/70 px-4 py-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-surface-900">{recommendedMemoryProfileMeta.label}</span>
                        <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-surface-700 ring-1 ring-surface-200">
                          {memoryReasoningStyleOptions.find((item) => item.id === recommendedMemoryProfile.reasoning_style)?.label || recommendedMemoryProfile.reasoning_style}
                        </span>
                        <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${isUsingRecommendedMemoryProfile ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                          {isUsingRecommendedMemoryProfile ? t('teams.agentForm.usingRecommended') : t('teams.agentForm.deviatedRecommended')}
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-surface-600">{recommendedMemoryProfileMeta.summary}</p>
                    </div>
                    <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
                      <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4">
                        <label className="block text-sm font-medium text-surface-800">{t('teams.agentForm.missionLabel')}</label>
                        <p className="mt-1 text-xs text-surface-500">{t('teams.agentForm.missionHint')}</p>
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
                          placeholder={t('teams.agentForm.missionPlaceholder')}
                        />
                      </div>
                      <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4 xl:col-span-2">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <label className="block text-sm font-medium text-surface-800">{t('teams.agentForm.reasoningLabel')}</label>
                            <p className="mt-1 text-xs text-surface-500">{t('teams.agentForm.reasoningHint')}</p>
                          </div>
                          {form.memory_bank_profile.reasoning_style && (
                            <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-surface-700 ring-1 ring-surface-200">
                              {memoryReasoningStyleOptions.find((item) => item.id === form.memory_bank_profile.reasoning_style)?.label || form.memory_bank_profile.reasoning_style}
                            </span>
                          )}
                        </div>
                        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                          {memoryReasoningStyleOptions.map((option) => {
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
                          <label className="block text-sm font-medium text-surface-800">{t('teams.agentForm.directivesLabel')}</label>
                          <p className="mt-1 text-xs text-surface-500">{t('teams.agentForm.directivesHint')}</p>
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
                            placeholder={t('teams.agentForm.directivesPlaceholder')}
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="border-t border-surface-200 pt-4">
                    <h4 className="text-sm font-medium text-surface-700 mb-3">{t('teams.agentForm.workspaceTeamsTitle')}</h4>
                    <div>
                      <label className="block text-xs font-medium text-surface-600 mb-1">{t('teams.agentForm.customWorkspace')}</label>
                      <input
                        type="text"
                        value={form.workspace}
                        onChange={(e) => setForm({ ...form, workspace: e.target.value })}
                        className="w-full px-3 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
                        placeholder={t('teams.agentForm.customWorkspacePlaceholder')}
                      />
                      <p className="mt-1 text-xs text-surface-500">
                        {t('teams.agentForm.customWorkspaceHint')}
                      </p>
                    </div>
                    <div className="mt-3">
                      <label className="block text-xs font-medium text-surface-600 mb-2">{t('teams.agentForm.teamsLabel')}</label>
                      <div className="max-h-32 overflow-y-auto space-y-2 border border-surface-200 rounded-lg p-3">
                        {teams.length === 0 ? (
                          <p className="text-xs text-surface-500">{t('teams.agentForm.noTeams')}</p>
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
                    <h4 className="text-sm font-medium text-surface-700 mb-3">{t('teams.agentForm.onboardingSectionTitle')}</h4>
                    <div className="rounded-2xl border border-primary-200 bg-primary-50/70 px-4 py-4 text-sm text-surface-700">
                      <div className="font-semibold text-surface-900">{t('teams.agentForm.onboardingTitle')}</div>
                      <div className="mt-1">
                        {t('teams.agentForm.onboardingBody')}
                      </div>
                    </div>
                  </div>

                  <div className="border-t border-surface-200 pt-4">
                    <h4 className="text-sm font-medium text-surface-700 mb-3">{t('teams.agentForm.capabilities')}</h4>
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
                      {t('teams.agentForm.capabilitiesHint')}
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

export default AgentFormModal;
