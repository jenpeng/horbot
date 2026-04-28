import React, { useCallback, useEffect, useState } from 'react';
import AgentActivityPanels from '../components/teams/AgentActivityPanels';
import AgentFormModal from '../components/teams/AgentFormModal';
import AgentConfigurationPanels from '../components/teams/AgentConfigurationPanels';
import AgentOverviewCard from '../components/teams/AgentOverviewCard';
import TeamDetailView from '../components/teams/TeamDetailView';
import TeamFormModal from '../components/teams/TeamFormModal';
import TeamsSidebar from '../components/teams/TeamsSidebar';
import ExternalAgentDetailView from '../components/teams/external/ExternalAgentDetailView';
import ExternalAgentFormModal from '../components/teams/external/ExternalAgentFormModal';
import { useI18n } from '../contexts/I18nContext';
import { PageLoadingState } from '../components/state';
import {
  getAgentPermissionPreset,
  getAgentProfilePreset,
} from '../constants';
import { useTeamAgentAssets, useTeamsDirectoryData, useTeamsMutations } from '../hooks';
import { getStorageItem, removeStorageItem, setStorageItem } from '../utils/storage';
import {
  getAgentCapabilityOptions,
  getMemoryReasoningStyleOptions,
  getTeamPriorityMeta,
  getTeamRoleMeta,
  getTeamTemplateOptions,
} from './teams/formOptions';
import type { TeamTemplateId } from './teams/formOptions';
import {
  createDefaultToolAuditState,
  readFocusFromUrl,
  readSelectionFromUrl,
  readToolAuditStateFromUrl,
  writeSelectionToUrl,
} from './teams/selection';
import type {
  AgentFormState,
  AgentInfo,
  ExternalAgentFormState,
  ExternalAgentInfo,
  MemoryBankProfileDraft,
  TeamInfo,
  TeamFormState,
  TeamMemberProfile,
  SummarySectionKey,
  TeamsPageFocusTarget,
  TeamsPageSelection,
} from './teams/types';

type ModalType =
  | 'create-agent'
  | 'create-team'
  | 'edit-agent'
  | 'edit-team'
  | 'create-external-agent'
  | 'edit-external-agent'
  | 'group-chat'
  | null;

type BadgeTone = 'neutral' | 'warning' | 'pending' | 'success' | 'primary' | 'slate';
type BadgeSize = 'sm' | 'md';
type NoticeTone = 'warning' | 'pending' | 'success';
type TranslateFn = (key: string, values?: Record<string, number | string>) => string;
type DirectorySelection = {
  selectedAgentId: string | null;
  selectedTeam: TeamInfo | null;
  selectedExternalAgentId: string | null;
};

const TEAMS_PAGE_SELECTION_STORAGE_KEY = 'horbot.teams.selection';
const getErrorMessage = (error: unknown, fallback: string): string => (
  error instanceof Error ? error.message : fallback
);

const getSummarySectionDefs = (t: (key: string, values?: Record<string, number | string>) => string): Array<{ key: SummarySectionKey; label: string; placeholder: string }> => [
  { key: 'identity', label: t('teams.summarySection.identityLabel'), placeholder: t('teams.summarySection.identityPlaceholder') },
  { key: 'role_focus', label: t('teams.summarySection.roleFocusLabel'), placeholder: t('teams.summarySection.roleFocusPlaceholder') },
  { key: 'communication_style', label: t('teams.summarySection.communicationStyleLabel'), placeholder: t('teams.summarySection.communicationStylePlaceholder') },
  { key: 'boundaries', label: t('teams.summarySection.boundariesLabel'), placeholder: t('teams.summarySection.boundariesPlaceholder') },
  { key: 'user_preferences', label: t('teams.summarySection.userPreferencesLabel'), placeholder: t('teams.summarySection.userPreferencesPlaceholder') },
];

const MEMORY_PROFILE_RECOMMENDATIONS: Record<string, {
  keyPrefix: string;
  reasoningStyle: string;
}> = {
  generalist: {
    keyPrefix: 'teams.memoryProfile.generalist',
    reasoningStyle: 'balanced',
  },
  builder: {
    keyPrefix: 'teams.memoryProfile.builder',
    reasoningStyle: 'structured',
  },
  researcher: {
    keyPrefix: 'teams.memoryProfile.researcher',
    reasoningStyle: 'exploratory',
  },
  coordinator: {
    keyPrefix: 'teams.memoryProfile.coordinator',
    reasoningStyle: 'strict',
  },
  companion: {
    keyPrefix: 'teams.memoryProfile.companion',
    reasoningStyle: 'strict',
  },
};

const BADGE_TONE_CLASSES: Record<BadgeTone, string> = {
  neutral: 'bg-surface-100 text-surface-700 ring-1 ring-surface-200',
  warning: 'bg-accent-orange/10 text-accent-orange ring-1 ring-accent-orange/20',
  pending: 'bg-amber-100 text-amber-800 ring-1 ring-amber-200',
  success: 'bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200',
  primary: 'bg-primary-100 text-primary-700 ring-1 ring-primary-200',
  slate: 'bg-slate-100 text-slate-700 ring-1 ring-slate-200',
};

const BADGE_SIZE_CLASSES: Record<BadgeSize, string> = {
  sm: 'px-1.5 py-0.5 text-[10px]',
  md: 'px-2 py-1 text-xs',
};

const NOTICE_TONE_CLASSES: Record<NoticeTone, string> = {
  warning: 'border-accent-orange/30 bg-accent-orange/5 text-surface-700',
  pending: 'border-amber-200 bg-amber-50 text-amber-900',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-900',
};

const getBadgeClassName = (tone: BadgeTone, size: BadgeSize = 'md'): string => (
  `inline-flex items-center rounded-full font-medium ${BADGE_TONE_CLASSES[tone]} ${BADGE_SIZE_CLASSES[size]}`
);

const getNoticeClassName = (tone: NoticeTone): string => (
  `rounded-2xl border px-4 py-4 text-sm ${NOTICE_TONE_CLASSES[tone]}`
);

const getAgentStatusMeta = (
  agent: Pick<AgentInfo, 'setup_required' | 'bootstrap_setup_pending'> | null | undefined,
  t: (key: string, values?: Record<string, number | string>) => string,
) => {
  if (agent?.setup_required) {
    return {
      shortLabel: t('teams.agentStatus.setupShort'),
      detailLabel: t('teams.agentStatus.setupDetail'),
      tone: 'warning' as const,
    };
  }

  if (agent?.bootstrap_setup_pending) {
    return {
      shortLabel: t('teams.agentStatus.onboardingShort'),
      detailLabel: t('teams.agentStatus.onboardingDetail'),
      tone: 'pending' as const,
    };
  }

  return {
    shortLabel: t('teams.agentStatus.readyShort'),
    detailLabel: t('teams.agentStatus.readyDetail'),
    tone: 'success' as const,
  };
};

const normalizeMemoryProfileDraft = (profile?: Partial<MemoryBankProfileDraft> | null): MemoryBankProfileDraft => ({
  mission: String(profile?.mission || '').trim(),
  directives: (profile?.directives || []).map((item) => item.trim()).filter(Boolean),
  reasoning_style: String(profile?.reasoning_style || '').trim(),
});

const inferMemoryProfilePresetId = (profileId?: string, capabilities: string[] = []): keyof typeof MEMORY_PROFILE_RECOMMENDATIONS => {
  if (profileId && profileId in MEMORY_PROFILE_RECOMMENDATIONS) {
    return profileId as keyof typeof MEMORY_PROFILE_RECOMMENDATIONS;
  }
  if (capabilities.includes('code') || capabilities.includes('testing')) {
    return 'builder';
  }
  if (capabilities.includes('research') || capabilities.includes('data')) {
    return 'researcher';
  }
  if (capabilities.includes('planning') && capabilities.includes('review')) {
    return 'coordinator';
  }
  return 'generalist';
};

const getRecommendedMemoryProfileMeta = (
  t: TranslateFn,
  profileId?: string,
  capabilities: string[] = [],
) => {
  const recommendation = MEMORY_PROFILE_RECOMMENDATIONS[inferMemoryProfilePresetId(profileId, capabilities)];
  return {
    label: t(`${recommendation.keyPrefix}.label`),
    summary: t(`${recommendation.keyPrefix}.summary`),
    reasoningStyle: recommendation.reasoningStyle,
    mission: t(`${recommendation.keyPrefix}.mission`),
    directives: [
      t(`${recommendation.keyPrefix}.directive1`),
      t(`${recommendation.keyPrefix}.directive2`),
      t(`${recommendation.keyPrefix}.directive3`),
    ],
  };
};

const buildRecommendedMemoryBankProfile = (
  t: TranslateFn,
  profileId?: string,
  capabilities: string[] = [],
): MemoryBankProfileDraft => {
  const recommendation = getRecommendedMemoryProfileMeta(t, profileId, capabilities);
  return {
    mission: recommendation.mission,
    directives: recommendation.directives,
    reasoning_style: recommendation.reasoningStyle,
  };
};

const memoryProfilesEqual = (left?: Partial<MemoryBankProfileDraft> | null, right?: Partial<MemoryBankProfileDraft> | null): boolean => {
  const normalizedLeft = normalizeMemoryProfileDraft(left);
  const normalizedRight = normalizeMemoryProfileDraft(right);
  return normalizedLeft.mission === normalizedRight.mission
    && normalizedLeft.reasoning_style === normalizedRight.reasoning_style
    && normalizedLeft.directives.join('\n') === normalizedRight.directives.join('\n');
};

const recommendTeamTemplateId = (memberAgents: AgentInfo[]): TeamTemplateId => {
  if (memberAgents.length === 0) {
    return 'delivery';
  }

  const deliveryScore = memberAgents.reduce((total, agent) => (
    total
    + (agent.capabilities.includes('code') ? 3 : 0)
    + (agent.capabilities.includes('testing') ? 2 : 0)
    + (agent.capabilities.includes('review') ? 2 : 0)
  ), 0);
  const researchScore = memberAgents.reduce((total, agent) => (
    total
    + (agent.capabilities.includes('research') ? 3 : 0)
    + (agent.capabilities.includes('data') ? 2 : 0)
    + (agent.capabilities.includes('writing') ? 1 : 0)
  ), 0);
  const supportScore = memberAgents.reduce((total, agent) => (
    total
    + (agent.profile === 'companion' ? 3 : 0)
    + (agent.capabilities.includes('writing') ? 1 : 0)
    + (agent.capabilities.includes('planning') ? 1 : 0)
  ), 0);

  if (deliveryScore >= researchScore && deliveryScore >= supportScore) {
    return 'delivery';
  }
  if (researchScore >= supportScore) {
    return 'research';
  }
  return 'support';
};

const recommendTeamLeadId = (memberAgents: AgentInfo[], templateId: TeamTemplateId): string | null => {
  if (memberAgents.length === 0) {
    return null;
  }

  const scored = memberAgents.map((agent, index) => {
    let score = 0;
    if (agent.profile === 'coordinator') {
      score += 4;
    }
    if (agent.capabilities.includes('planning')) {
      score += 3;
    }
    if (agent.capabilities.includes('review')) {
      score += 2;
    }
    if (templateId === 'delivery' && agent.capabilities.includes('code')) {
      score += 2;
    }
    if (templateId === 'research' && agent.capabilities.includes('research')) {
      score += 2;
    }
    if (templateId === 'support' && agent.profile === 'companion') {
      score += 2;
    }
    return { agentId: agent.id, score, index };
  });

  scored.sort((a, b) => (b.score - a.score) || (a.index - b.index));
  return scored[0]?.agentId || null;
};

const applyLeadToProfiles = (profiles: Record<string, TeamMemberProfile>, leadAgentId: string | null): Record<string, TeamMemberProfile> => (
  Object.fromEntries(
    Object.entries(profiles).map(([agentId, profile]) => [
      agentId,
      {
        ...profile,
        isLead: leadAgentId ? agentId === leadAgentId : Boolean(profile.isLead),
      },
    ]),
  )
);

const buildTeamProfilesFromTemplate = (
  t: TranslateFn,
  memberIds: string[],
  currentProfiles: Record<string, TeamMemberProfile>,
  templateId: TeamTemplateId,
): Record<string, TeamMemberProfile> => {
  if (templateId === 'custom') {
    return Object.fromEntries(
      memberIds.map((agentId) => [
        agentId,
        {
          role: currentProfiles[agentId]?.role || 'member',
          responsibility: currentProfiles[agentId]?.responsibility || '',
          priority: currentProfiles[agentId]?.priority ?? 100,
          isLead: Boolean(currentProfiles[agentId]?.isLead),
        },
      ]),
    );
  }

  const rolePlanByTemplate: Record<Exclude<TeamTemplateId, 'custom'>, Array<Pick<TeamMemberProfile, 'role' | 'priority' | 'responsibility' | 'isLead'>>> = {
    delivery: [
      { role: 'coordinator', priority: 10, responsibility: t('teams.template.delivery.coordinator'), isLead: true },
      { role: 'builder', priority: 50, responsibility: t('teams.template.delivery.builder'), isLead: false },
      { role: 'reviewer', priority: 200, responsibility: t('teams.template.delivery.reviewer'), isLead: false },
    ],
    research: [
      { role: 'coordinator', priority: 10, responsibility: t('teams.template.research.coordinator'), isLead: true },
      { role: 'researcher', priority: 50, responsibility: t('teams.template.research.researcher'), isLead: false },
      { role: 'reviewer', priority: 200, responsibility: t('teams.template.research.reviewer'), isLead: false },
    ],
    support: [
      { role: 'coordinator', priority: 10, responsibility: t('teams.template.support.coordinator'), isLead: true },
      { role: 'support', priority: 50, responsibility: t('teams.template.support.support'), isLead: false },
      { role: 'builder', priority: 100, responsibility: t('teams.template.support.builder'), isLead: false },
    ],
  };

  const fallbackByTemplate: Record<Exclude<TeamTemplateId, 'custom'>, Pick<TeamMemberProfile, 'role' | 'priority' | 'responsibility' | 'isLead'>> = {
    delivery: { role: 'support', priority: 100, responsibility: t('teams.template.delivery.fallback'), isLead: false },
    research: { role: 'support', priority: 100, responsibility: t('teams.template.research.fallback'), isLead: false },
    support: { role: 'support', priority: 100, responsibility: t('teams.template.support.fallback'), isLead: false },
  };

  const plan = rolePlanByTemplate[templateId];
  const fallback = fallbackByTemplate[templateId];
  return Object.fromEntries(
    memberIds.map((agentId, index) => {
      const preset = plan[index] || fallback;
      const current = currentProfiles[agentId] || {};
      return [
        agentId,
        {
          role: preset.role,
          responsibility: current.responsibility?.trim() || preset.responsibility,
          priority: preset.priority,
          isLead: Boolean(preset.isLead),
        },
      ];
    }),
  );
};

const createEmptyAgentForm = (t: TranslateFn): AgentFormState => ({
  id: '',
  name: '',
  description: '',
  profile: '',
  permission_profile: '',
  model: '',
  provider: '',
  system_prompt: '',
  capabilities: [],
  tools: [],
  skills: [],
  workspace: '',
  teams: [],
  personality: '',
  avatar: '',
  evolution_enabled: true,
  learning_enabled: true,
  memory_bank_profile: buildRecommendedMemoryBankProfile(t),
});

const normalizeAgentId = (value: string): string => value.trim().toLowerCase();

const createEmptyTeamForm = (): TeamFormState => ({
  id: '',
  name: '',
  description: '',
  members: [] as string[],
  member_profiles: {} as Record<string, TeamMemberProfile>,
  workspace: '',
});

const normalizeTeamId = (value: string): string => value.trim().toLowerCase();

const externalAgentAdapterRequiresEndpoint = (adapter?: string): boolean => (
  (adapter || 'inbound-bot') === 'generic-agent-api' || adapter === 'openai-compatible'
);

const createEmptyExternalAgentForm = (): ExternalAgentFormState => ({
  id: '',
  name: '',
  description: '',
  avatar: '',
  adapter: 'inbound-bot',
  transport: 'http_sse',
  endpoint: '',
  auth_type: 'none',
  auth_header: 'Authorization',
  auth_secret: '',
  auth_secret_configured: false,
  capabilities: [],
  dm_enabled: true,
  team_enabled: false,
  mention_required: true,
  timeout_s: 90,
  max_turn_chars: 12000,
  context_scope: 'recent_turns',
  memory_access: 'none',
  file_access: 'none',
  adapter_config: {},
  metadata: {},
});

const normalizeExternalAgentId = (value: string): string => value.trim().toLowerCase();

const TeamsPage: React.FC = () => {
  const { t } = useI18n();
  const baseCapabilityOptions = getAgentCapabilityOptions(t);
  const memoryReasoningStyleOptions = getMemoryReasoningStyleOptions(t);
  const teamTemplateOptions = getTeamTemplateOptions(t);
  const [selectedTeam, setSelectedTeam] = useState<TeamInfo | null>(null);
  const [selectedExternalAgentId, setSelectedExternalAgentId] = useState<string | null>(() => {
    const urlSelection = readSelectionFromUrl();
    if (urlSelection?.kind === 'external-agent') {
      return urlSelection.id;
    }
    const persistedSelection = getStorageItem<TeamsPageSelection | null>(TEAMS_PAGE_SELECTION_STORAGE_KEY, null);
    return persistedSelection?.kind === 'external-agent' ? persistedSelection.id : null;
  });
  const [focusTarget, setFocusTarget] = useState<TeamsPageFocusTarget | null>(() => readFocusFromUrl());
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(() => {
    const urlSelection = readSelectionFromUrl();
    if (urlSelection?.kind === 'agent') {
      return urlSelection.id;
    }
    const persistedSelection = getStorageItem<TeamsPageSelection | null>(TEAMS_PAGE_SELECTION_STORAGE_KEY, null);
    return persistedSelection?.kind === 'agent' ? persistedSelection.id : null;
  });
  const [modalType, setModalType] = useState<ModalType>(null);
  const [editAgentAdvancedOpen, setEditAgentAdvancedOpen] = useState(false);
  const [teamAdvancedOpen, setTeamAdvancedOpen] = useState(false);
  const [selectedTeamTemplateId, setSelectedTeamTemplateId] = useState<TeamTemplateId>('delivery');
  const [teamRecommendationAutoApply, setTeamRecommendationAutoApply] = useState(true);
  
  const [agentForm, setAgentForm] = useState<AgentFormState>(() => createEmptyAgentForm(t));
  
  const [teamForm, setTeamForm] = useState<TeamFormState>(createEmptyTeamForm);
  const [externalAgentForm, setExternalAgentForm] = useState<ExternalAgentFormState>(createEmptyExternalAgentForm);
  const [externalAgentTestFeedback, setExternalAgentTestFeedback] = useState<{
    agentId: string;
    tone: 'success' | 'warning';
    summary: string;
    detail: string;
  } | null>(null);

  const handleDirectorySelectionResolved = useCallback((selection: DirectorySelection) => {
    setSelectedAgentId(selection.selectedAgentId);
    setSelectedTeam(selection.selectedTeam);
    setSelectedExternalAgentId(selection.selectedExternalAgentId);
  }, [setSelectedAgentId, setSelectedTeam, setSelectedExternalAgentId]);

  const {
    agents,
    teams,
    externalAgents,
    providers,
    loading,
    refreshDirectory: fetchData,
  } = useTeamsDirectoryData({
    currentSelectedAgentId: selectedAgentId,
    currentSelectedTeamId: selectedTeam?.id || null,
    currentSelectedExternalAgentId: selectedExternalAgentId,
    selectionStorageKey: TEAMS_PAGE_SELECTION_STORAGE_KEY,
    onSelectionResolved: handleDirectorySelectionResolved,
  });
  const {
    createAgent,
    updateAgent,
    deleteAgent,
    createTeam,
    updateTeam,
    deleteTeam,
    createExternalAgent,
    updateExternalAgent,
    deleteExternalAgent,
    testExternalAgent,
  } = useTeamsMutations({
    onRefresh: () => fetchData({ force: true }),
  });

  const resetAgentForm = () => {
    setAgentForm(createEmptyAgentForm(t));
  };

  const openCreateAgentModal = () => {
    resetAgentForm();
    setModalType('create-agent');
  };

  const closeAgentModal = () => {
    setEditAgentAdvancedOpen(false);
    resetAgentForm();
    setModalType(null);
  };

  const resetTeamForm = () => {
    setSelectedTeamTemplateId('delivery');
    setTeamRecommendationAutoApply(true);
    setTeamForm(createEmptyTeamForm());
  };

  const openCreateTeamModal = () => {
    setTeamAdvancedOpen(false);
    resetTeamForm();
    setModalType('create-team');
  };

  const closeTeamModal = () => {
    setTeamAdvancedOpen(false);
    resetTeamForm();
    setModalType(null);
  };

  const resetExternalAgentForm = () => {
    setExternalAgentForm(createEmptyExternalAgentForm());
  };

  const openCreateExternalAgentModal = () => {
    resetExternalAgentForm();
    setModalType('create-external-agent');
  };

  const closeExternalAgentModal = () => {
    resetExternalAgentForm();
    setModalType(null);
  };

  const normalizedCreateAgentId = normalizeAgentId(agentForm.id);
  const createAgentIdRequired = modalType === 'create-agent' && !agentForm.id.trim();
  const createAgentNameRequired = modalType === 'create-agent' && !agentForm.name.trim();
  const createAgentProviderRequired = modalType === 'create-agent' && !agentForm.provider.trim();
  const createAgentModelRequired = modalType === 'create-agent' && !agentForm.model.trim();
  const createAgentIdExists = modalType === 'create-agent'
    && normalizedCreateAgentId.length > 0
    && agents.some((agent) => normalizeAgentId(agent.id) === normalizedCreateAgentId);
  const createAgentIdError = createAgentIdRequired
    ? t('teams.validation.agentIdRequired')
    : createAgentIdExists
      ? t('teams.validation.agentIdExists', { id: agentForm.id.trim() })
      : '';
  const createAgentNameError = createAgentNameRequired ? t('teams.validation.agentNameRequired') : '';
  const createAgentProviderError = createAgentProviderRequired ? t('teams.validation.agentProviderRequired') : '';
  const createAgentModelError = createAgentModelRequired ? t('teams.validation.agentModelRequired') : '';
  const createAgentSubmitDisabled = modalType === 'create-agent'
    && (
      !agentForm.id.trim()
      || !agentForm.name.trim()
      || !agentForm.provider.trim()
      || !agentForm.model.trim()
      || createAgentIdExists
    );
  const normalizedCreateTeamId = normalizeTeamId(teamForm.id);
  const createTeamIdRequired = modalType === 'create-team' && !teamForm.id.trim();
  const createTeamNameRequired = modalType === 'create-team' && !teamForm.name.trim();
  const createTeamIdExists = modalType === 'create-team'
    && normalizedCreateTeamId.length > 0
    && teams.some((team) => normalizeTeamId(team.id) === normalizedCreateTeamId);
  const createTeamIdError = createTeamIdRequired
    ? t('teams.validation.teamIdRequired')
    : createTeamIdExists
      ? t('teams.validation.teamIdExists', { id: teamForm.id.trim() })
      : '';
  const createTeamNameError = createTeamNameRequired ? t('teams.validation.teamNameRequired') : '';
  const createTeamSubmitDisabled = modalType === 'create-team'
    && (!teamForm.id.trim() || !teamForm.name.trim() || createTeamIdExists);
  const normalizedCreateExternalAgentId = normalizeExternalAgentId(externalAgentForm.id);
  const createExternalAgentIdRequired = modalType === 'create-external-agent' && !externalAgentForm.id.trim();
  const createExternalAgentNameRequired = modalType === 'create-external-agent' && !externalAgentForm.name.trim();
  const createExternalAgentEndpointRequired = modalType === 'create-external-agent'
    && externalAgentAdapterRequiresEndpoint(externalAgentForm.adapter)
    && !externalAgentForm.endpoint.trim();
  const createExternalAgentIdExists = modalType === 'create-external-agent'
    && normalizedCreateExternalAgentId.length > 0
    && externalAgents.some((agent) => normalizeExternalAgentId(agent.id) === normalizedCreateExternalAgentId);
  const createExternalAgentIdError = createExternalAgentIdRequired
    ? t('teams.validation.externalAgentIdRequired')
    : createExternalAgentIdExists
      ? t('teams.validation.externalAgentIdExists', { id: externalAgentForm.id.trim() })
      : '';
  const createExternalAgentNameError = createExternalAgentNameRequired ? t('teams.validation.externalAgentNameRequired') : '';
  const createExternalAgentEndpointError = createExternalAgentEndpointRequired ? t('teams.validation.externalAgentEndpointRequired') : '';
  const createExternalAgentSubmitDisabled = modalType === 'create-external-agent'
    && (
      !externalAgentForm.id.trim()
      || !externalAgentForm.name.trim()
      || (externalAgentAdapterRequiresEndpoint(externalAgentForm.adapter) && !externalAgentForm.endpoint.trim())
      || createExternalAgentIdExists
    );
  const recommendedMemoryProfile = buildRecommendedMemoryBankProfile(t, agentForm.profile, agentForm.capabilities);
  const recommendedMemoryProfileMeta = getRecommendedMemoryProfileMeta(t, agentForm.profile, agentForm.capabilities);
  const isUsingRecommendedMemoryProfile = memoryProfilesEqual(agentForm.memory_bank_profile, recommendedMemoryProfile);
  const agentAdvancedSummaryItems = [
    agentForm.capabilities.length ? t('teams.summary.capabilities', { count: agentForm.capabilities.length }) : t('teams.summary.noCapabilities'),
    agentForm.teams.length ? t('teams.summary.teams', { count: agentForm.teams.length }) : t('teams.summary.noTeams'),
    agentForm.workspace.trim() ? t('teams.summary.customWorkspace') : t('teams.summary.defaultWorkspace'),
    isUsingRecommendedMemoryProfile ? t('teams.summary.defaultMemoryProfile') : t('teams.summary.customizedMemoryProfile'),
  ];
  const getAgentById = (agentId: string): AgentInfo | undefined => {
    return agents.find(a => a.id === agentId);
  };

  const toExternalTeamMemberAgent = (agent: ExternalAgentInfo): AgentInfo => ({
    id: agent.id,
    name: agent.name,
    description: agent.description,
    external: true,
    transport: agent.transport,
    endpoint: agent.endpoint,
    dm_enabled: agent.dm_enabled,
    team_enabled: agent.team_enabled,
    profile: '',
    permission_profile: '',
    model: agent.transport,
    provider: 'external',
    capabilities: agent.capabilities || [],
    tools: [],
    skills: [],
    teams: [],
    workspace: '',
    effective_workspace: '',
    avatar: agent.avatar || '',
  });

  const teamMemberOptions = [
    ...agents,
    ...externalAgents
      .filter((agent) => agent.team_enabled)
      .map((agent) => toExternalTeamMemberAgent(agent)),
  ];

  const getTeamMemberById = (agentId: string): AgentInfo | undefined => {
    return teamMemberOptions.find((agent) => agent.id === agentId);
  };
  const teamLeadAssigned = teamForm.members.some((agentId) => Boolean(teamForm.member_profiles[agentId]?.isLead));
  const teamConfiguredResponsibilitiesCount = teamForm.members.filter((agentId) => {
    const profile = teamForm.member_profiles[agentId];
    return Boolean(profile?.role || profile?.responsibility || (profile?.priority ?? 100) !== 100);
  }).length;
  const teamAdvancedSummaryItems = [
    teamForm.members.length ? t('teams.summary.members', { count: teamForm.members.length }) : t('teams.summary.noMembers'),
    teamLeadAssigned ? t('teams.summary.leadAssigned') : t('teams.summary.noLeadAssigned'),
    teamConfiguredResponsibilitiesCount ? t('teams.summary.configuredResponsibilities', { count: teamConfiguredResponsibilitiesCount }) : t('teams.summary.noResponsibilities'),
    teamForm.workspace.trim() ? t('teams.summary.customWorkspace') : t('teams.summary.defaultWorkspace'),
  ];
  const teamAssignmentGuide = t('teams.summary.assignmentGuide');
  const selectedTeamTemplate = teamTemplateOptions.find((item) => item.id === selectedTeamTemplateId) || teamTemplateOptions[0];
  const recommendedTeamTemplateId = recommendTeamTemplateId(
    teamForm.members
      .map((agentId) => getTeamMemberById(agentId))
      .filter(Boolean) as AgentInfo[],
  );
  const recommendedTeamTemplate = teamTemplateOptions.find((item) => item.id === recommendedTeamTemplateId) || teamTemplateOptions[0];
  const recommendedTeamLeadId = recommendTeamLeadId(
    teamForm.members
      .map((agentId) => getTeamMemberById(agentId))
      .filter(Boolean) as AgentInfo[],
    recommendedTeamTemplateId,
  );
  const recommendedTeamLead = recommendedTeamLeadId
    ? getTeamMemberById(recommendedTeamLeadId) || null
    : null;
  const summarySectionDefs = getSummarySectionDefs(t);

  const capabilityOptions = Array.from(new Set([
    ...baseCapabilityOptions.map((item) => item.id),
    ...agentForm.capabilities,
    ...externalAgentForm.capabilities,
  ])).map((id) => baseCapabilityOptions.find((item) => item.id === id) || {
    id,
    label: id,
    description: t('teams.capabilityHistoryLabel'),
  });

  useEffect(() => {
    if (!focusTarget) {
      return;
    }

    const target = document.querySelector<HTMLElement>(`[data-focus-anchor="${focusTarget}"]`);
    if (!target) {
      return;
    }

    if (typeof target.scrollIntoView === 'function') {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    target.classList.add('ring-2', 'ring-primary-300', 'ring-offset-2');
    const timer = window.setTimeout(() => {
      target.classList.remove('ring-2', 'ring-primary-300', 'ring-offset-2');
    }, 2400);

    return () => window.clearTimeout(timer);
  }, [focusTarget, selectedAgentId, selectedTeam?.id]);

  const getAgentsByTeam = (teamId: string): AgentInfo[] => {
    const team = teams.find(t => t.id === teamId);
    if (!team) return [];
    return team.members.map(id => getTeamMemberById(id)).filter(Boolean) as AgentInfo[];
  };

  const getTeamMemberProfile = (team: TeamInfo | null, agentId: string): TeamMemberProfile => {
    if (!team) {
      return { role: 'member', responsibility: '', priority: 100, isLead: false };
    }
    const profile = team.member_profiles?.[agentId];
    return {
      role: profile?.role || 'member',
      responsibility: profile?.responsibility || '',
      priority: profile?.priority ?? 100,
      isLead: Boolean(profile?.isLead),
    };
  };

  const selectedAgent = selectedAgentId ? getAgentById(selectedAgentId) : undefined;
  const selectedTeamAgents = selectedTeam ? getAgentsByTeam(selectedTeam.id) : [];
  const selectedAgentProfilePreset = getAgentProfilePreset(t, selectedAgent?.profile);
  const selectedAgentPermissionPreset = getAgentPermissionPreset(t, selectedAgent?.permission_profile || selectedAgent?.tool_permission_profile || 'inherit');
  const selectedAgentReasoningStyleLabel = selectedAgent?.memory_bank_profile?.reasoning_style
    ? memoryReasoningStyleOptions.find((item) => item.id === selectedAgent.memory_bank_profile?.reasoning_style)?.label
      || selectedAgent.memory_bank_profile.reasoning_style
    : null;
  const selectedTeamLead = selectedTeam
    ? selectedTeamAgents.find((agent) => getTeamMemberProfile(selectedTeam, agent.id).isLead)
    : undefined;
  const selectedTeamCapabilitiesCount = Array.from(new Set(selectedTeamAgents.flatMap((agent) => agent.capabilities))).length;
  const selectedAgentStatusMeta = getAgentStatusMeta(selectedAgent, t);

  const upsertTeamMemberProfile = (agentId: string, patch: Partial<TeamMemberProfile>) => {
    setTeamRecommendationAutoApply(false);
    setTeamForm((prev) => ({
      ...prev,
      member_profiles: {
        ...prev.member_profiles,
        [agentId]: {
          role: prev.member_profiles[agentId]?.role || 'member',
          responsibility: prev.member_profiles[agentId]?.responsibility || '',
          priority: prev.member_profiles[agentId]?.priority ?? 100,
          isLead: Boolean(prev.member_profiles[agentId]?.isLead),
          ...patch,
        },
      },
    }));
  };

  const applyTeamTemplate = (templateId: TeamTemplateId) => {
    setSelectedTeamTemplateId(templateId);
    setTeamRecommendationAutoApply(false);
    setTeamForm((prev) => ({
      ...prev,
      member_profiles: buildTeamProfilesFromTemplate(t, prev.members, prev.member_profiles, templateId),
    }));
  };

  const applyRecommendedTeamSetup = () => {
    setSelectedTeamTemplateId(recommendedTeamTemplateId);
    setTeamRecommendationAutoApply(true);
    setTeamForm((prev) => {
      const profiles = buildTeamProfilesFromTemplate(t, prev.members, prev.member_profiles, recommendedTeamTemplateId);
      return {
        ...prev,
        member_profiles: applyLeadToProfiles(profiles, recommendedTeamLeadId),
      };
    });
  };

  const toggleTeamMemberSelection = (agentId: string, checked: boolean) => {
    setTeamForm((prev) => {
      const nextMembers = checked
        ? (prev.members.includes(agentId) ? prev.members : [...prev.members, agentId])
        : prev.members.filter((id) => id !== agentId);

      const nextProfiles = checked
        ? {
            ...prev.member_profiles,
            [agentId]: prev.member_profiles[agentId] || { role: 'member', responsibility: '', priority: 100, isLead: false },
          }
        : Object.fromEntries(
            Object.entries(prev.member_profiles).filter(([id]) => id !== agentId),
          );

      const nextAgents = nextMembers
        .map((memberId) => getTeamMemberById(memberId))
        .filter(Boolean) as AgentInfo[];
      const nextTemplateId = teamRecommendationAutoApply ? recommendTeamTemplateId(nextAgents) : selectedTeamTemplateId;
      const nextLeadId = teamRecommendationAutoApply ? recommendTeamLeadId(nextAgents, nextTemplateId) : null;
      const resolvedProfiles = nextTemplateId === 'custom'
        ? nextProfiles
        : buildTeamProfilesFromTemplate(t, nextMembers, nextProfiles, nextTemplateId);

      if (teamRecommendationAutoApply) {
        setSelectedTeamTemplateId(nextTemplateId);
      }

      return {
        ...prev,
        members: nextMembers,
        member_profiles: teamRecommendationAutoApply
          ? applyLeadToProfiles(resolvedProfiles, nextLeadId)
          : resolvedProfiles,
      };
    });
  };

  const handleSelectTeam = (team: TeamInfo) => {
    setSelectedAgentId(null);
    setSelectedExternalAgentId(null);
    setSelectedTeam(team);
  };

  const handleSelectAgent = (agentId: string) => {
    setSelectedTeam(null);
    setSelectedExternalAgentId(null);
    setSelectedAgentId(agentId);
  };

  const handleSelectExternalAgent = (agentId: string) => {
    setSelectedAgentId(null);
    setSelectedTeam(null);
    setSelectedExternalAgentId(agentId);
    setExternalAgentTestFeedback(null);
  };

  const handleSelectTeamMember = (agent: AgentInfo) => {
    if (agent.external) {
      handleSelectExternalAgent(agent.id);
      return;
    }
    handleSelectAgent(agent.id);
  };

  const handleEditTeamMember = (agent: AgentInfo) => {
    if (agent.external) {
      const externalAgent = externalAgents.find((item) => item.id === agent.id);
      if (externalAgent) {
        handleEditExternalAgent(externalAgent);
      }
      return;
    }
    handleEditAgent(agent);
  };

  const {
    agentAssets,
    agentMemoryStats,
    agentSkills,
    agentToolAudits,
    toolAuditState,
    toolAuditLoading,
    assetDrafts,
    assetLoading,
    assetLoadedAgentId,
    assetSaving,
    assetError,
    assetSuccess,
    summaryDrafts,
    summarySaving,
    handleAssetDraftChange,
    handleSummaryDraftChange,
    handleSaveAssetFile,
    handleSaveSummary,
    setToolAuditState,
    setToolAuditSessionKey,
    setToolAuditRiskFilter,
    setToolAuditWindowHours,
    loadMoreToolAudits,
  } = useTeamAgentAssets({
    selectedAgentId,
    onSaved: fetchData,
  });
  const assetReady = Boolean(selectedAgentId) && assetLoadedAgentId === selectedAgentId && !assetLoading;
  const applyToolAuditState = useCallback((auditState = createDefaultToolAuditState()) => {
    setToolAuditState(auditState);
  }, [setToolAuditState]);

  useEffect(() => {
    const handlePopState = () => {
      const urlSelection = readSelectionFromUrl();
      if (urlSelection?.kind === 'agent') {
        const matchedAgent = agents.find((agent) => agent.id === urlSelection.id) || null;
        setSelectedAgentId(matchedAgent?.id || null);
        setSelectedTeam(null);
        setSelectedExternalAgentId(null);
        applyToolAuditState(readToolAuditStateFromUrl());
        setFocusTarget(readFocusFromUrl());
        return;
      }

      if (urlSelection?.kind === 'external-agent') {
        const matchedExternalAgent = externalAgents.find((agent) => agent.id === urlSelection.id) || null;
        setSelectedAgentId(null);
        setSelectedTeam(null);
        setSelectedExternalAgentId(matchedExternalAgent?.id || null);
        applyToolAuditState();
        setFocusTarget(readFocusFromUrl());
        return;
      }

      if (urlSelection?.kind === 'team') {
        const matchedTeam = teams.find((team) => team.id === urlSelection.id) || null;
        setSelectedAgentId(null);
        setSelectedTeam(matchedTeam || teams[0] || null);
        setSelectedExternalAgentId(null);
        applyToolAuditState();
        setFocusTarget(readFocusFromUrl());
        return;
      }

      setSelectedAgentId(null);
      setSelectedTeam(teams[0] || null);
      setSelectedExternalAgentId(null);
      applyToolAuditState();
      setFocusTarget(readFocusFromUrl());
    };

    window.addEventListener('popstate', handlePopState);
    return () => {
      window.removeEventListener('popstate', handlePopState);
    };
  }, [
    agents,
    teams,
    externalAgents,
    applyToolAuditState,
  ]);

  useEffect(() => {
    if (selectedAgentId) {
      const selection = {
        kind: 'agent',
        id: selectedAgentId,
      } satisfies TeamsPageSelection;
      setStorageItem<TeamsPageSelection>(TEAMS_PAGE_SELECTION_STORAGE_KEY, selection);
      writeSelectionToUrl(selection, toolAuditState, focusTarget);
      return;
    }

    if (selectedExternalAgentId) {
      const selection = {
        kind: 'external-agent',
        id: selectedExternalAgentId,
      } satisfies TeamsPageSelection;
      setStorageItem<TeamsPageSelection>(TEAMS_PAGE_SELECTION_STORAGE_KEY, selection);
      writeSelectionToUrl(selection, null, focusTarget);
      return;
    }

    if (selectedTeam?.id) {
      const selection = {
        kind: 'team',
        id: selectedTeam.id,
      } satisfies TeamsPageSelection;
      setStorageItem<TeamsPageSelection>(TEAMS_PAGE_SELECTION_STORAGE_KEY, selection);
      writeSelectionToUrl(selection, null, focusTarget);
      return;
    }

    removeStorageItem(TEAMS_PAGE_SELECTION_STORAGE_KEY);
    writeSelectionToUrl(null, null, focusTarget);
  }, [selectedAgentId, selectedExternalAgentId, selectedTeam, toolAuditState, focusTarget]);

  const handleCreateAgent = async () => {
    if (!agentForm.id.trim()) {
      alert('Agent ID is required');
      return;
    }

    if (!agentForm.name.trim()) {
      alert('Agent name is required');
      return;
    }

    if (!agentForm.provider.trim()) {
      alert('Agent provider is required');
      return;
    }

    if (!agentForm.model.trim()) {
      alert('Agent model is required');
      return;
    }

    if (createAgentIdExists) {
      alert(createAgentIdError);
      return;
    }

    try {
      await createAgent(agentForm);
      closeAgentModal();
    } catch (error: unknown) {
      alert(getErrorMessage(error, 'Failed to create agent'));
    }
  };

  const applyAgentProfilePreset = (profileId: string) => {
    const preset = getAgentProfilePreset(t, profileId);
    setAgentForm((prev) => {
      const previousRecommendation = buildRecommendedMemoryBankProfile(t, prev.profile, prev.capabilities);
      const nextCapabilities = Array.from(new Set([
        ...prev.capabilities,
        ...(preset?.suggestedCapabilities || []),
      ]));
      const nextProfileId = prev.profile === profileId ? '' : profileId;
      const resolvedCapabilities = prev.profile === profileId ? prev.capabilities : nextCapabilities;
      return {
        ...prev,
        profile: nextProfileId,
        capabilities: resolvedCapabilities,
        memory_bank_profile: memoryProfilesEqual(prev.memory_bank_profile, previousRecommendation)
          ? buildRecommendedMemoryBankProfile(t, nextProfileId, resolvedCapabilities)
          : prev.memory_bank_profile,
      };
    });
  };

  const restoreRecommendedMemoryProfile = () => {
    setAgentForm((prev) => ({
      ...prev,
      memory_bank_profile: buildRecommendedMemoryBankProfile(t, prev.profile, prev.capabilities),
    }));
  };

  const applyAgentPermissionPreset = (permissionProfileId: string) => {
    setAgentForm((prev) => ({
      ...prev,
      permission_profile: permissionProfileId === 'inherit' ? '' : permissionProfileId,
    }));
  };

  const handleCreateTeam = async () => {
    if (!teamForm.id.trim()) {
      alert('Team ID is required');
      return;
    }

    if (!teamForm.name.trim()) {
      alert('Team name is required');
      return;
    }

    if (createTeamIdExists) {
      alert(createTeamIdError);
      return;
    }

    try {
      await createTeam(teamForm);
      closeTeamModal();
    } catch (error: unknown) {
      alert(getErrorMessage(error, 'Failed to create team'));
    }
  };

  const handleCreateExternalAgent = async () => {
    if (!externalAgentForm.id.trim()) {
      alert(t('teams.validation.externalAgentIdRequired'));
      return;
    }

    if (!externalAgentForm.name.trim()) {
      alert(t('teams.validation.externalAgentNameRequired'));
      return;
    }

    if (externalAgentAdapterRequiresEndpoint(externalAgentForm.adapter) && !externalAgentForm.endpoint.trim()) {
      alert(t('teams.validation.externalAgentEndpointRequired'));
      return;
    }

    if (createExternalAgentIdExists) {
      alert(createExternalAgentIdError);
      return;
    }

    try {
      await createExternalAgent(externalAgentForm);
      closeExternalAgentModal();
    } catch (error: unknown) {
      alert(getErrorMessage(error, t('teams.external.test.failedTitle')));
    }
  };

  const handleEditAgent = (agent: AgentInfo) => {
    setEditAgentAdvancedOpen(false);
    const normalizedMemoryProfile = normalizeMemoryProfileDraft(agent.memory_bank_profile);
    const fallbackMemoryProfile = buildRecommendedMemoryBankProfile(t, agent.profile, agent.capabilities || []);
    setAgentForm({
      id: agent.id,
      name: agent.name,
      description: agent.description,
      profile: agent.profile || '',
      permission_profile: agent.permission_profile || '',
      model: agent.model,
      provider: agent.provider,
      system_prompt: agent.system_prompt || '',
      capabilities: agent.capabilities,
      tools: agent.tools || [],
      skills: agent.skills || [],
      workspace: agent.workspace || agent.effective_workspace || '',
      teams: agent.teams,
      personality: agent.personality || '',
      avatar: agent.avatar || '',
      evolution_enabled: agent.evolution_enabled ?? true,
      learning_enabled: agent.learning_enabled ?? true,
      memory_bank_profile: normalizedMemoryProfile.mission || normalizedMemoryProfile.directives.length || normalizedMemoryProfile.reasoning_style
        ? normalizedMemoryProfile
        : fallbackMemoryProfile,
    });
    setModalType('edit-agent');
  };

  const handleEditTeam = (team: TeamInfo) => {
    setTeamAdvancedOpen(false);
    setSelectedTeamTemplateId('custom');
    setTeamRecommendationAutoApply(false);
    setTeamForm({
      id: team.id,
      name: team.name,
      description: team.description || '',
      members: team.members || [],
      member_profiles: team.member_profiles || {},
      workspace: team.workspace || '',
    });
    setModalType('edit-team');
  };

  const handleEditExternalAgent = (agent: ExternalAgentInfo) => {
    setExternalAgentForm({
      id: agent.id,
      name: agent.name,
      description: agent.description || '',
      avatar: agent.avatar || '',
      adapter: agent.adapter || 'generic-agent-api',
      transport: agent.transport,
      endpoint: agent.endpoint,
      auth_type: agent.auth_type,
      auth_header: agent.auth_header || 'Authorization',
      auth_secret: '',
      auth_secret_configured: Boolean(agent.auth_secret_configured),
      capabilities: agent.capabilities || [],
      dm_enabled: agent.dm_enabled,
      team_enabled: agent.team_enabled,
      mention_required: agent.mention_required,
      timeout_s: agent.timeout_s,
      max_turn_chars: agent.max_turn_chars,
      context_scope: agent.context_scope,
      memory_access: agent.memory_access,
      file_access: agent.file_access,
      adapter_config: agent.adapter_config || {},
      metadata: agent.metadata || {},
    });
    setModalType('edit-external-agent');
  };

  const handleUpdateAgent = async () => {
    try {
      await updateAgent(agentForm);
      closeAgentModal();
    } catch (error: unknown) {
      alert(getErrorMessage(error, 'Failed to update agent'));
    }
  };

  const handleUpdateTeam = async () => {
    try {
      await updateTeam(teamForm);
      closeTeamModal();
    } catch (error: unknown) {
      alert(getErrorMessage(error, 'Failed to update team'));
    }
  };

  const handleUpdateExternalAgent = async () => {
    try {
      await updateExternalAgent(externalAgentForm);
      closeExternalAgentModal();
    } catch (error: unknown) {
      alert(getErrorMessage(error, 'Failed to update external agent'));
    }
  };

  const handleDeleteAgent = async (agentId: string) => {
    if (!confirm(t('teams.confirmDeleteAgent', { id: agentId }))) return;
    
    try {
      await deleteAgent(agentId);
      if (selectedAgentId === agentId) {
        setSelectedAgentId(null);
      }
    } catch (error: unknown) {
      alert(getErrorMessage(error, 'Failed to delete agent'));
    }
  };

  const handleDeleteTeam = async (teamId: string) => {
    if (!confirm(t('teams.confirmDeleteTeam', { id: teamId }))) return;
    
    try {
      await deleteTeam(teamId);
      setSelectedTeam(null);
    } catch (error: unknown) {
      alert(getErrorMessage(error, 'Failed to delete team'));
    }
  };

  const handleDeleteExternalAgent = async (externalAgentId: string) => {
    if (!confirm(t('teams.confirmDeleteExternalAgent', { id: externalAgentId }))) return;

    try {
      await deleteExternalAgent(externalAgentId);
      if (selectedExternalAgentId === externalAgentId) {
        setSelectedExternalAgentId(null);
        setExternalAgentTestFeedback(null);
      }
    } catch (error: unknown) {
      alert(getErrorMessage(error, 'Failed to delete external agent'));
    }
  };

  const handleTestExternalAgent = async (externalAgentId: string) => {
    try {
      const result = await testExternalAgent(externalAgentId);
      setExternalAgentTestFeedback({
        agentId: externalAgentId,
        tone: result.ok ? 'success' : 'warning',
        summary: result.ok ? t('teams.external.test.successTitle') : t('teams.external.test.failedTitle'),
        detail: result.detail || t('teams.external.test.noDetail'),
      });
    } catch (error: unknown) {
      setExternalAgentTestFeedback({
        agentId: externalAgentId,
        tone: 'warning',
        summary: t('teams.external.test.failedTitle'),
        detail: getErrorMessage(error, t('teams.external.test.noDetail')),
      });
    }
  };

  const startGroupChat = () => {
    window.location.href = '/chat?mode=group';
  };

  const selectedExternalAgent = selectedExternalAgentId
    ? externalAgents.find((agent) => agent.id === selectedExternalAgentId)
    : undefined;

  if (loading) {
    return <PageLoadingState metricCount={3} showTabs={false} />;
  }

  return (
    <div className="h-full flex flex-col bg-surface-100">
      <div className="px-6 py-4 border-b border-surface-200 bg-white flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-surface-900">{t('teams.pageTitle')}</h1>
          <p className="text-sm text-surface-500 mt-1">{t('teams.pageSubtitle')}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={openCreateAgentModal}
            className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors flex items-center gap-2"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            {t('teams.createAgent')}
          </button>
          <button
            onClick={openCreateExternalAgentModal}
            className="px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 transition-colors flex items-center gap-2"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4h10l6 6v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6a2 2 0 012-2zm4 5h8m-8 4h8m-8 4h5" />
            </svg>
            {t('teams.external.createAction')}
          </button>
              <button
                onClick={openCreateTeamModal}
                className="px-4 py-2 bg-surface-100 text-surface-700 rounded-lg hover:bg-surface-200 transition-colors flex items-center gap-2"
              >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            {t('teams.createTeam')}
          </button>
          <button
            onClick={startGroupChat}
            className="px-4 py-2 bg-accent-purple text-white rounded-lg hover:bg-accent-purple/90 transition-colors flex items-center gap-2"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" />
            </svg>
            {t('teams.groupChat')}
          </button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        <TeamsSidebar
          teams={teams}
          agents={agents}
          externalAgents={externalAgents}
          selectedTeamId={selectedTeam?.id || null}
          selectedAgentId={selectedAgentId}
          selectedExternalAgentId={selectedExternalAgentId}
          onCreateTeam={openCreateTeamModal}
          onCreateAgent={openCreateAgentModal}
          onCreateExternalAgent={openCreateExternalAgentModal}
          onSelectTeam={handleSelectTeam}
          onEditTeam={handleEditTeam}
          onDeleteTeam={handleDeleteTeam}
          onSelectAgent={handleSelectAgent}
          onEditAgent={handleEditAgent}
          onDeleteAgent={handleDeleteAgent}
          onSelectExternalAgent={handleSelectExternalAgent}
          onEditExternalAgent={handleEditExternalAgent}
          onDeleteExternalAgent={handleDeleteExternalAgent}
          getBadgeClassName={(tone, size = 'md') => getBadgeClassName(tone as BadgeTone, size)}
          getAgentProfileLabel={(profileId) => {
            if (!profileId) {
              return null;
            }
            return getAgentProfilePreset(t, profileId)?.label || profileId;
          }}
          getAgentPermissionLabel={(permissionId) => {
            if (!permissionId) {
              return null;
            }
            return getAgentPermissionPreset(t, permissionId)?.label || permissionId;
          }}
          getAgentStatusMeta={(agent) => getAgentStatusMeta(agent, t)}
        />

        <div className="flex-1 overflow-y-auto p-6">
          {selectedAgent ? (
            <div className="space-y-6" data-testid="agent-detail-view" data-agent-id={selectedAgent.id}>
              <AgentOverviewCard
                selectedAgent={selectedAgent}
                selectedAgentStatusMeta={selectedAgentStatusMeta}
                selectedAgentProfileLabel={selectedAgentProfilePreset?.label || null}
                selectedAgentProfileSummary={selectedAgentProfilePreset?.summary || null}
                selectedAgentPermissionLabel={selectedAgentPermissionPreset?.label || null}
                selectedAgentPermissionSummary={selectedAgentPermissionPreset?.summary || null}
                memoryReasoningStyleLabel={selectedAgentReasoningStyleLabel}
                workspacePath={agentAssets?.workspace_path || selectedAgent.effective_workspace || selectedAgent.workspace || t('teams.summary.defaultWorkspace')}
                getBadgeClassName={(tone, size = 'md') => getBadgeClassName(tone as BadgeTone, size)}
                getNoticeClassName={getNoticeClassName}
                onEditAgent={() => handleEditAgent(selectedAgent)}
                onOpenChat={() => {
                  const setupQuery = (selectedAgent.setup_required || selectedAgent.bootstrap_setup_pending) ? '&setup=1' : '';
                  window.location.href = `/chat?agent=${encodeURIComponent(selectedAgent.id)}${setupQuery}`;
                }}
              />

              <AgentActivityPanels
                selectedAgent={selectedAgent}
                agentMemoryStats={agentMemoryStats}
                agentSkills={agentSkills}
                agentToolAudits={agentToolAudits}
                toolAuditState={toolAuditState}
                toolAuditLoading={toolAuditLoading}
                assetReady={assetReady}
                assetLoading={assetLoading}
                reasoningStyleLabel={selectedAgentReasoningStyleLabel}
                onToolAuditSessionKeyChange={setToolAuditSessionKey}
                onToolAuditRiskFilterChange={setToolAuditRiskFilter}
                onToolAuditWindowHoursChange={setToolAuditWindowHours}
                onLoadMoreToolAudits={loadMoreToolAudits}
                onToolAuditFocus={() => setFocusTarget('agent-tool-audits')}
              />

              <AgentConfigurationPanels
                selectedAgent={selectedAgent}
                agentAssets={agentAssets}
                assetReady={assetReady}
                assetLoading={assetLoading}
                assetError={assetError}
                assetSuccess={assetSuccess}
                assetSaving={assetSaving}
                assetDrafts={assetDrafts}
                summaryDrafts={summaryDrafts}
                summarySaving={summarySaving}
                summarySectionDefs={summarySectionDefs}
                noticeToneClasses={{
                  pending: NOTICE_TONE_CLASSES.pending,
                  success: NOTICE_TONE_CLASSES.success,
                }}
                onSaveSummary={handleSaveSummary}
                onSummaryDraftChange={handleSummaryDraftChange}
                onSaveAssetFile={handleSaveAssetFile}
                onAssetDraftChange={handleAssetDraftChange}
              />
            </div>
          ) : selectedExternalAgent ? (
            <ExternalAgentDetailView
              externalAgent={selectedExternalAgent}
              getBadgeClassName={(tone, size = 'md') => getBadgeClassName(tone as BadgeTone, size)}
              onEdit={() => handleEditExternalAgent(selectedExternalAgent)}
              onDelete={() => handleDeleteExternalAgent(selectedExternalAgent.id)}
              onTest={() => handleTestExternalAgent(selectedExternalAgent.id)}
              testFeedback={
                externalAgentTestFeedback?.agentId === selectedExternalAgent.id
                  ? {
                      tone: externalAgentTestFeedback.tone,
                      summary: externalAgentTestFeedback.summary,
                      detail: externalAgentTestFeedback.detail,
                    }
                  : null
              }
            />
          ) : selectedTeam ? (
            <TeamDetailView
              selectedTeam={selectedTeam}
              selectedTeamAgents={selectedTeamAgents}
              selectedTeamLead={selectedTeamLead}
              selectedTeamCapabilitiesCount={selectedTeamCapabilitiesCount}
              getBadgeClassName={(tone, size = 'md') => getBadgeClassName(tone as BadgeTone, size)}
              getTeamMemberProfile={getTeamMemberProfile}
              getTeamRoleLabel={(role) => getTeamRoleMeta(t, role).label}
              getTeamPriorityLabel={(priority) => getTeamPriorityMeta(t, priority).label}
              onEditTeam={() => handleEditTeam(selectedTeam)}
              onSelectMember={handleSelectTeamMember}
              onEditMember={handleEditTeamMember}
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-2xl bg-surface-100 flex items-center justify-center mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-surface-900 mb-2">{t('teams.selectTeamTitle')}</h3>
              <p className="text-surface-500">{t('teams.selectTeamDescription')}</p>
            </div>
          )}
        </div>
      </div>

      {modalType === 'create-agent' && (
        <AgentFormModal
          mode="create"
          form={agentForm}
          setForm={setAgentForm}
          providers={providers}
          teams={teams}
          capabilityOptions={capabilityOptions}
          createIdError={createAgentIdError}
          createNameError={createAgentNameError}
          createProviderError={createAgentProviderError}
          createModelError={createAgentModelError}
          submitDisabled={createAgentSubmitDisabled}
          recommendedMemoryProfile={recommendedMemoryProfile}
          recommendedMemoryProfileMeta={recommendedMemoryProfileMeta}
          isUsingRecommendedMemoryProfile={isUsingRecommendedMemoryProfile}
          advancedOpen={editAgentAdvancedOpen}
          setAdvancedOpen={setEditAgentAdvancedOpen}
          advancedSummaryItems={agentAdvancedSummaryItems}
          onApplyAgentProfilePreset={applyAgentProfilePreset}
          onApplyAgentPermissionPreset={applyAgentPermissionPreset}
          onRestoreRecommendedMemoryProfile={restoreRecommendedMemoryProfile}
          onClose={closeAgentModal}
          onSubmit={handleCreateAgent}
        />
      )}

      {modalType === 'edit-agent' && (
        <AgentFormModal
          mode="edit"
          form={agentForm}
          setForm={setAgentForm}
          providers={providers}
          teams={teams}
          capabilityOptions={capabilityOptions}
          recommendedMemoryProfile={recommendedMemoryProfile}
          recommendedMemoryProfileMeta={recommendedMemoryProfileMeta}
          isUsingRecommendedMemoryProfile={isUsingRecommendedMemoryProfile}
          advancedOpen={editAgentAdvancedOpen}
          setAdvancedOpen={setEditAgentAdvancedOpen}
          advancedSummaryItems={agentAdvancedSummaryItems}
          onApplyAgentProfilePreset={applyAgentProfilePreset}
          onApplyAgentPermissionPreset={applyAgentPermissionPreset}
          onRestoreRecommendedMemoryProfile={restoreRecommendedMemoryProfile}
          onClose={closeAgentModal}
          onSubmit={handleUpdateAgent}
        />
      )}

      {modalType === 'create-team' && (
        <TeamFormModal
          mode="create"
          form={teamForm}
          agents={teamMemberOptions}
          createIdError={createTeamIdError}
          createNameError={createTeamNameError}
          submitDisabled={createTeamSubmitDisabled}
          advancedOpen={teamAdvancedOpen}
          setAdvancedOpen={setTeamAdvancedOpen}
          advancedSummaryItems={teamAdvancedSummaryItems}
          teamAssignmentGuide={teamAssignmentGuide}
          selectedTeamTemplateId={selectedTeamTemplateId}
          selectedTeamTemplate={selectedTeamTemplate}
          recommendedTeamTemplate={recommendedTeamTemplate}
          recommendedTeamLead={recommendedTeamLead}
          onChange={setTeamForm}
          onSelectTemplate={(templateId) => {
            setTeamRecommendationAutoApply(false);
            setSelectedTeamTemplateId(templateId);
          }}
          onApplyTeamTemplate={applyTeamTemplate}
          onApplyRecommendedTeamSetup={applyRecommendedTeamSetup}
          onToggleMemberSelection={toggleTeamMemberSelection}
          onUpsertMemberProfile={upsertTeamMemberProfile}
          onSelectLead={(agentId) => {
            setTeamRecommendationAutoApply(false);
            const nextProfiles = Object.fromEntries(
              teamForm.members.map((id) => [
                id,
                {
                  role: teamForm.member_profiles[id]?.role || 'member',
                  responsibility: teamForm.member_profiles[id]?.responsibility || '',
                  priority: teamForm.member_profiles[id]?.priority ?? 100,
                  isLead: id === agentId,
                },
              ]),
            );
            setTeamForm((prev) => ({ ...prev, member_profiles: nextProfiles }));
          }}
          getAgentById={getTeamMemberById}
          getTeamRoleDescription={(role) => getTeamRoleMeta(t, role).description}
          getTeamPriorityDescription={(priority) => getTeamPriorityMeta(t, priority).description}
          onClose={closeTeamModal}
          onSubmit={handleCreateTeam}
        />
      )}

      {modalType === 'edit-team' && (
        <TeamFormModal
          mode="edit"
          form={teamForm}
          agents={teamMemberOptions}
          advancedOpen={teamAdvancedOpen}
          setAdvancedOpen={setTeamAdvancedOpen}
          advancedSummaryItems={teamAdvancedSummaryItems}
          teamAssignmentGuide={teamAssignmentGuide}
          selectedTeamTemplateId={selectedTeamTemplateId}
          selectedTeamTemplate={selectedTeamTemplate}
          recommendedTeamTemplate={recommendedTeamTemplate}
          recommendedTeamLead={recommendedTeamLead}
          onChange={setTeamForm}
          onSelectTemplate={(templateId) => {
            setTeamRecommendationAutoApply(false);
            setSelectedTeamTemplateId(templateId);
          }}
          onApplyTeamTemplate={applyTeamTemplate}
          onApplyRecommendedTeamSetup={applyRecommendedTeamSetup}
          onToggleMemberSelection={toggleTeamMemberSelection}
          onUpsertMemberProfile={upsertTeamMemberProfile}
          onSelectLead={(agentId) => {
            setTeamRecommendationAutoApply(false);
            const nextProfiles = Object.fromEntries(
              teamForm.members.map((id) => [
                id,
                {
                  role: teamForm.member_profiles[id]?.role || 'member',
                  responsibility: teamForm.member_profiles[id]?.responsibility || '',
                  priority: teamForm.member_profiles[id]?.priority ?? 100,
                  isLead: id === agentId,
                },
              ]),
            );
            setTeamForm((prev) => ({ ...prev, member_profiles: nextProfiles }));
          }}
          getAgentById={getTeamMemberById}
          getTeamRoleDescription={(role) => getTeamRoleMeta(t, role).description}
          getTeamPriorityDescription={(priority) => getTeamPriorityMeta(t, priority).description}
          onClose={closeTeamModal}
          onSubmit={handleUpdateTeam}
        />
      )}

      {modalType === 'create-external-agent' && (
        <ExternalAgentFormModal
          mode="create"
          form={externalAgentForm}
          setForm={setExternalAgentForm}
          capabilityOptions={capabilityOptions}
          createIdError={createExternalAgentIdError}
          createNameError={createExternalAgentNameError}
          createEndpointError={createExternalAgentEndpointError}
          submitDisabled={createExternalAgentSubmitDisabled}
          onClose={closeExternalAgentModal}
          onSubmit={handleCreateExternalAgent}
        />
      )}

      {modalType === 'edit-external-agent' && (
        <ExternalAgentFormModal
          mode="edit"
          form={externalAgentForm}
          setForm={setExternalAgentForm}
          capabilityOptions={capabilityOptions}
          onClose={closeExternalAgentModal}
          onSubmit={handleUpdateExternalAgent}
        />
      )}
    </div>
  );
};

export default TeamsPage;
