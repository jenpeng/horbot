import React, { useCallback, useEffect, useState } from 'react';
import AgentActivityPanels from '../components/teams/AgentActivityPanels';
import AgentFormModal from '../components/teams/AgentFormModal';
import AgentConfigurationPanels from '../components/teams/AgentConfigurationPanels';
import AgentOverviewCard from '../components/teams/AgentOverviewCard';
import TeamDetailView from '../components/teams/TeamDetailView';
import TeamFormModal from '../components/teams/TeamFormModal';
import TeamsSidebar from '../components/teams/TeamsSidebar';
import { PageLoadingState } from '../components/state';
import {
  getAgentPermissionPreset,
  getAgentProfilePreset,
} from '../constants';
import { useTeamAgentAssets, useTeamsDirectoryData, useTeamsMutations } from '../hooks';
import { getStorageItem, removeStorageItem, setStorageItem } from '../utils/storage';
import {
  AGENT_CAPABILITY_OPTIONS,
  getTeamPriorityMeta,
  getTeamRoleMeta,
  MEMORY_REASONING_STYLE_OPTIONS,
  TEAM_TEMPLATE_OPTIONS,
} from './teams/formOptions';
import type { TeamTemplateId } from './teams/formOptions';
import { readSelectionFromUrl, writeSelectionToUrl } from './teams/selection';
import type {
  AgentFormState,
  AgentInfo,
  MemoryBankProfileDraft,
  TeamInfo,
  TeamFormState,
  TeamMemberProfile,
  TeamsPageSelection,
  SummarySectionKey,
} from './teams/types';

type ModalType = 'create-agent' | 'create-team' | 'edit-agent' | 'edit-team' | 'group-chat' | null;

type TeamsPageFocusTarget =
  | 'agent-overview'
  | 'agent-runtime'
  | 'agent-summary'
  | 'agent-files'
  | 'agent-file-soul'
  | 'agent-file-user'
  | 'team-overview'
  | 'team-members'
  | 'team-workspace'
  | 'team-collaboration';

type BadgeTone = 'neutral' | 'warning' | 'pending' | 'success' | 'primary' | 'slate';
type BadgeSize = 'sm' | 'md';
type NoticeTone = 'warning' | 'pending' | 'success';

const TEAMS_PAGE_SELECTION_STORAGE_KEY = 'horbot.teams.selection';
const SUMMARY_SECTION_DEFS: Array<{ key: SummarySectionKey; label: string; placeholder: string }> = [
  { key: 'identity', label: '身份定位', placeholder: '每行一条，例如：定位：负责复杂任务拆解' },
  { key: 'role_focus', label: '职责重点', placeholder: '每行一条，例如：负责需求梳理' },
  { key: 'communication_style', label: '沟通风格', placeholder: '每行一条，例如：先结论后细节' },
  { key: 'boundaries', label: '边界约束', placeholder: '每行一条，例如：未经确认不修改生产配置' },
  { key: 'user_preferences', label: '用户偏好', placeholder: '每行一条，例如：默认使用中文' },
];

const MEMORY_PROFILE_RECOMMENDATIONS: Record<string, {
  label: string;
  summary: string;
  reasoningStyle: string;
  mission: string;
  directives: string[];
}> = {
  generalist: {
    label: '默认平衡',
    summary: '优先保留长期协作背景、用户偏好和可复用工作习惯，适合作为通用默认策略。',
    reasoningStyle: 'balanced',
    mission: '优先沉淀与用户长期协作相关的背景、偏好、稳定约束和可复用策略。',
    directives: [
      '优先召回当前任务直接相关的事实、偏好和约束',
      '当记忆很多时优先保留最近仍然有效的稳定信息',
      '反思时记录可复用的处理方法，而不是重复保存短期细节',
    ],
  },
  builder: {
    label: '工程沉淀',
    summary: '更强调工程上下文、排障经验、回归风险和实现约束。',
    reasoningStyle: 'structured',
    mission: '优先沉淀工程实现上下文、回归风险、排障经验和关键技术约束。',
    directives: [
      '优先召回与当前代码、缺陷、验证结论相关的事实和决策',
      '遇到冲突记忆时优先相信较新的实现约束和回归结果',
      '反思时记录可复用的排障路径、验证方式和风险清单',
    ],
  },
  researcher: {
    label: '研究归纳',
    summary: '更适合资料梳理、证据链沉淀和结论演化。',
    reasoningStyle: 'exploratory',
    mission: '优先沉淀研究主题、证据线索、对比维度和阶段性结论。',
    directives: [
      '优先召回和当前议题相关的证据、对比维度和开放问题',
      '保留事实与推断边界，避免把未验证结论当成长期记忆',
      '反思时记录哪些分析框架和检索路径值得下次复用',
    ],
  },
  coordinator: {
    label: '协作调度',
    summary: '更适合多 Agent 协作中的角色分工、接力约束和未完成事项。',
    reasoningStyle: 'strict',
    mission: '优先沉淀协作分工、接力状态、关键约束和待确认事项。',
    directives: [
      '优先召回团队决策、共享约束、未完成接力和阻塞项',
      '冲突信息出现时先保留最新的团队分工和显式边界',
      '反思时记录哪些接力路径和分工方式最稳定有效',
    ],
  },
  companion: {
    label: '陪伴偏好',
    summary: '更强调用户长期偏好、沟通习惯和陪伴式协作连续性。',
    reasoningStyle: 'strict',
    mission: '优先沉淀用户长期偏好、沟通习惯、边界和连续性需求。',
    directives: [
      '优先召回用户偏好、禁忌和长期目标，不要被短期噪声覆盖',
      '遇到冲突记忆时优先保留用户最近明确表达的边界和偏好',
      '反思时记录更适合这个用户的沟通方式和引导节奏',
    ],
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

const getAgentStatusMeta = (agent?: Pick<AgentInfo, 'setup_required' | 'bootstrap_setup_pending'> | null) => {
  if (agent?.setup_required) {
    return {
      shortLabel: '待配置',
      detailLabel: '等待首次配置',
      tone: 'warning' as const,
    };
  }

  if (agent?.bootstrap_setup_pending) {
    return {
      shortLabel: '待引导',
      detailLabel: '待完成首次引导',
      tone: 'pending' as const,
    };
  }

  return {
    shortLabel: '已完成',
    detailLabel: '已完成个性化配置',
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

const buildRecommendedMemoryBankProfile = (profileId?: string, capabilities: string[] = []): MemoryBankProfileDraft => {
  const recommendation = MEMORY_PROFILE_RECOMMENDATIONS[inferMemoryProfilePresetId(profileId, capabilities)];
  return {
    mission: recommendation.mission,
    directives: recommendation.directives,
    reasoning_style: recommendation.reasoningStyle,
  };
};

const getRecommendedMemoryProfileMeta = (profileId?: string, capabilities: string[] = []) => (
  MEMORY_PROFILE_RECOMMENDATIONS[inferMemoryProfilePresetId(profileId, capabilities)]
);

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
      { role: 'coordinator', priority: 10, responsibility: '负责需求拆解、分派下一棒并同步进度', isLead: true },
      { role: 'builder', priority: 50, responsibility: '负责主要实现、修复和结果产出', isLead: false },
      { role: 'reviewer', priority: 200, responsibility: '负责验收结果、补充风险和最终收尾', isLead: false },
    ],
    research: [
      { role: 'coordinator', priority: 10, responsibility: '负责明确研究问题、范围和输出结构', isLead: true },
      { role: 'researcher', priority: 50, responsibility: '负责检索资料、梳理信息并形成结论草案', isLead: false },
      { role: 'reviewer', priority: 200, responsibility: '负责校验证据链、对比维度与结论严谨性', isLead: false },
    ],
    support: [
      { role: 'coordinator', priority: 10, responsibility: '负责先接单、澄清问题并判断处理路径', isLead: true },
      { role: 'support', priority: 50, responsibility: '负责补位响应、收集上下文并辅助推进', isLead: false },
      { role: 'builder', priority: 100, responsibility: '负责实际处理问题并给出可执行结果', isLead: false },
    ],
  };

  const fallbackByTemplate: Record<Exclude<TeamTemplateId, 'custom'>, Pick<TeamMemberProfile, 'role' | 'priority' | 'responsibility' | 'isLead'>> = {
    delivery: { role: 'support', priority: 100, responsibility: '负责补位处理临时任务与辅助协作', isLead: false },
    research: { role: 'support', priority: 100, responsibility: '负责补充检索、整理材料与辅助总结', isLead: false },
    support: { role: 'support', priority: 100, responsibility: '负责承接补位任务并保持响应连续性', isLead: false },
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

const createEmptyAgentForm = (): AgentFormState => ({
  id: '',
  name: '',
  description: '',
  profile: '',
  permission_profile: '',
  model: '',
  provider: 'auto',
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
  memory_bank_profile: buildRecommendedMemoryBankProfile(),
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

const readFocusFromUrl = (): TeamsPageFocusTarget | null => {
  if (typeof window === 'undefined') {
    return null;
  }

  const focus = new URLSearchParams(window.location.search).get('focus')?.trim();
  if (!focus) {
    return null;
  }

  const allowed: TeamsPageFocusTarget[] = [
    'agent-overview',
    'agent-runtime',
    'agent-summary',
    'agent-files',
    'agent-file-soul',
    'agent-file-user',
    'team-overview',
    'team-members',
    'team-workspace',
    'team-collaboration',
  ];

  return allowed.includes(focus as TeamsPageFocusTarget) ? (focus as TeamsPageFocusTarget) : null;
};


const TeamsPage: React.FC = () => {
  const [selectedTeam, setSelectedTeam] = useState<TeamInfo | null>(null);
  const [focusTarget] = useState<TeamsPageFocusTarget | null>(() => readFocusFromUrl());
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
  
  const [agentForm, setAgentForm] = useState<AgentFormState>(createEmptyAgentForm);
  
  const [teamForm, setTeamForm] = useState<TeamFormState>(createEmptyTeamForm);

  const handleDirectorySelectionResolved = useCallback((selection: {
    selectedAgentId: string | null;
    selectedTeam: TeamInfo | null;
  }) => {
    setSelectedAgentId(selection.selectedAgentId);
    setSelectedTeam(selection.selectedTeam);
  }, []);

  const {
    agents,
    teams,
    providers,
    loading,
    refreshDirectory: fetchData,
  } = useTeamsDirectoryData({
    currentSelectedAgentId: selectedAgentId,
    currentSelectedTeamId: selectedTeam?.id || null,
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
  } = useTeamsMutations({
    onRefresh: fetchData,
  });

  const resetAgentForm = () => {
    setAgentForm(createEmptyAgentForm());
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

  const normalizedCreateAgentId = normalizeAgentId(agentForm.id);
  const createAgentIdRequired = modalType === 'create-agent' && !agentForm.id.trim();
  const createAgentNameRequired = modalType === 'create-agent' && !agentForm.name.trim();
  const createAgentIdExists = modalType === 'create-agent'
    && normalizedCreateAgentId.length > 0
    && agents.some((agent) => normalizeAgentId(agent.id) === normalizedCreateAgentId);
  const createAgentIdError = createAgentIdRequired
    ? '请输入 Agent ID。'
    : createAgentIdExists
      ? `Agent ID "${agentForm.id.trim()}" 已存在，请使用新的唯一 ID。`
      : '';
  const createAgentNameError = createAgentNameRequired ? '请输入 Agent 名称。' : '';
  const createAgentSubmitDisabled = modalType === 'create-agent'
    && (!agentForm.id.trim() || !agentForm.name.trim() || createAgentIdExists);
  const normalizedCreateTeamId = normalizeTeamId(teamForm.id);
  const createTeamIdRequired = modalType === 'create-team' && !teamForm.id.trim();
  const createTeamNameRequired = modalType === 'create-team' && !teamForm.name.trim();
  const createTeamIdExists = modalType === 'create-team'
    && normalizedCreateTeamId.length > 0
    && teams.some((team) => normalizeTeamId(team.id) === normalizedCreateTeamId);
  const createTeamIdError = createTeamIdRequired
    ? '请输入 Team ID。'
    : createTeamIdExists
      ? `Team ID "${teamForm.id.trim()}" 已存在，请使用新的唯一 ID。`
      : '';
  const createTeamNameError = createTeamNameRequired ? '请输入团队名称。' : '';
  const createTeamSubmitDisabled = modalType === 'create-team'
    && (!teamForm.id.trim() || !teamForm.name.trim() || createTeamIdExists);
  const recommendedMemoryProfile = buildRecommendedMemoryBankProfile(agentForm.profile, agentForm.capabilities);
  const recommendedMemoryProfileMeta = getRecommendedMemoryProfileMeta(agentForm.profile, agentForm.capabilities);
  const isUsingRecommendedMemoryProfile = memoryProfilesEqual(agentForm.memory_bank_profile, recommendedMemoryProfile);
  const agentAdvancedSummaryItems = [
    agentForm.capabilities.length ? `${agentForm.capabilities.length} 个能力标签` : '未选能力标签',
    agentForm.teams.length ? `${agentForm.teams.length} 个团队` : '未绑定团队',
    agentForm.workspace.trim() ? '自定义工作区' : '默认工作区',
    isUsingRecommendedMemoryProfile ? '系统默认记忆画像' : '已手动调整记忆画像',
  ];
  const teamLeadAssigned = teamForm.members.some((agentId) => Boolean(teamForm.member_profiles[agentId]?.isLead));
  const teamConfiguredResponsibilitiesCount = teamForm.members.filter((agentId) => {
    const profile = teamForm.member_profiles[agentId];
    return Boolean(profile?.role || profile?.responsibility || (profile?.priority ?? 100) !== 100);
  }).length;
  const teamAdvancedSummaryItems = [
    teamForm.members.length ? `${teamForm.members.length} 个成员` : '未选择成员',
    teamLeadAssigned ? '已指定负责人' : '未指定负责人',
    teamConfiguredResponsibilitiesCount ? `${teamConfiguredResponsibilitiesCount} 个成员已设分工` : '未设团队分工',
    teamForm.workspace.trim() ? '自定义工作区' : '默认工作区',
  ];
  const teamAssignmentGuide = '角色表示它在团队里扮演什么类型；接力顺序表示多 Agent 协作时谁更早参与；负责内容用一句话写清楚它具体负责什么。';
  const selectedTeamTemplate = TEAM_TEMPLATE_OPTIONS.find((item) => item.id === selectedTeamTemplateId) || TEAM_TEMPLATE_OPTIONS[0];
  const recommendedTeamTemplateId = recommendTeamTemplateId(
    teamForm.members
      .map((agentId) => agents.find((agent) => agent.id === agentId))
      .filter(Boolean) as AgentInfo[],
  );
  const recommendedTeamTemplate = TEAM_TEMPLATE_OPTIONS.find((item) => item.id === recommendedTeamTemplateId) || TEAM_TEMPLATE_OPTIONS[0];
  const recommendedTeamLeadId = recommendTeamLeadId(
    teamForm.members
      .map((agentId) => agents.find((agent) => agent.id === agentId))
      .filter(Boolean) as AgentInfo[],
    recommendedTeamTemplateId,
  );
  const recommendedTeamLead = recommendedTeamLeadId
    ? agents.find((agent) => agent.id === recommendedTeamLeadId) || null
    : null;

  const capabilityOptions = Array.from(new Set([
    ...AGENT_CAPABILITY_OPTIONS.map((item) => item.id),
    ...agentForm.capabilities,
  ])).map((id) => AGENT_CAPABILITY_OPTIONS.find((item) => item.id === id) || {
    id,
    label: id,
    description: '历史标签',
  });

  const getAgentById = (agentId: string): AgentInfo | undefined => {
    return agents.find(a => a.id === agentId);
  };

  useEffect(() => {
    if (!focusTarget) {
      return;
    }

    const target = document.querySelector<HTMLElement>(`[data-focus-anchor="${focusTarget}"]`);
    if (!target) {
      return;
    }

    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    target.classList.add('ring-2', 'ring-primary-300', 'ring-offset-2');
    const timer = window.setTimeout(() => {
      target.classList.remove('ring-2', 'ring-primary-300', 'ring-offset-2');
    }, 2400);

    return () => window.clearTimeout(timer);
  }, [focusTarget, selectedAgentId, selectedTeam?.id]);

  const getAgentsByTeam = (teamId: string): AgentInfo[] => {
    const team = teams.find(t => t.id === teamId);
    if (!team) return [];
    return team.members.map(id => getAgentById(id)).filter(Boolean) as AgentInfo[];
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
  const selectedAgentProfilePreset = getAgentProfilePreset(selectedAgent?.profile);
  const selectedAgentPermissionPreset = getAgentPermissionPreset(selectedAgent?.permission_profile || selectedAgent?.tool_permission_profile || 'inherit');
  const selectedAgentReasoningStyleLabel = selectedAgent?.memory_bank_profile?.reasoning_style
    ? MEMORY_REASONING_STYLE_OPTIONS.find((item) => item.id === selectedAgent.memory_bank_profile?.reasoning_style)?.label
      || selectedAgent.memory_bank_profile.reasoning_style
    : null;
  const selectedTeamLead = selectedTeam
    ? selectedTeamAgents.find((agent) => getTeamMemberProfile(selectedTeam, agent.id).isLead)
    : undefined;
  const selectedTeamCapabilitiesCount = Array.from(new Set(selectedTeamAgents.flatMap((agent) => agent.capabilities))).length;
  const selectedAgentStatusMeta = getAgentStatusMeta(selectedAgent);

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
      member_profiles: buildTeamProfilesFromTemplate(prev.members, prev.member_profiles, templateId),
    }));
  };

  const applyRecommendedTeamSetup = () => {
    setSelectedTeamTemplateId(recommendedTeamTemplateId);
    setTeamRecommendationAutoApply(true);
    setTeamForm((prev) => {
      const profiles = buildTeamProfilesFromTemplate(prev.members, prev.member_profiles, recommendedTeamTemplateId);
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
        .map((memberId) => agents.find((agent) => agent.id === memberId))
        .filter(Boolean) as AgentInfo[];
      const nextTemplateId = teamRecommendationAutoApply ? recommendTeamTemplateId(nextAgents) : selectedTeamTemplateId;
      const nextLeadId = teamRecommendationAutoApply ? recommendTeamLeadId(nextAgents, nextTemplateId) : null;
      const resolvedProfiles = nextTemplateId === 'custom'
        ? nextProfiles
        : buildTeamProfilesFromTemplate(nextMembers, nextProfiles, nextTemplateId);

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
    setSelectedTeam(team);
  };

  const handleSelectAgent = (agentId: string) => {
    setSelectedTeam(null);
    setSelectedAgentId(agentId);
  };

  useEffect(() => {
    if (selectedAgentId) {
      const selection = {
        kind: 'agent',
        id: selectedAgentId,
      } satisfies TeamsPageSelection;
      setStorageItem<TeamsPageSelection>(TEAMS_PAGE_SELECTION_STORAGE_KEY, selection);
      writeSelectionToUrl(selection);
      return;
    }

    if (selectedTeam?.id) {
      const selection = {
        kind: 'team',
        id: selectedTeam.id,
      } satisfies TeamsPageSelection;
      setStorageItem<TeamsPageSelection>(TEAMS_PAGE_SELECTION_STORAGE_KEY, selection);
      writeSelectionToUrl(selection);
      return;
    }

    removeStorageItem(TEAMS_PAGE_SELECTION_STORAGE_KEY);
    writeSelectionToUrl(null);
  }, [selectedAgentId, selectedTeam]);
  const {
    agentAssets,
    agentMemoryStats,
    agentSkills,
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
  } = useTeamAgentAssets({
    selectedAgentId,
    onSaved: fetchData,
  });
  const assetReady = Boolean(selectedAgentId) && assetLoadedAgentId === selectedAgentId && !assetLoading;

  const handleCreateAgent = async () => {
    if (!agentForm.id.trim()) {
      alert('Agent ID is required');
      return;
    }

    if (!agentForm.name.trim()) {
      alert('Agent name is required');
      return;
    }

    if (createAgentIdExists) {
      alert(createAgentIdError);
      return;
    }

    try {
      await createAgent(agentForm);
      closeAgentModal();
    } catch (error: any) {
      alert(error.message);
    }
  };

  const applyAgentProfilePreset = (profileId: string) => {
    const preset = getAgentProfilePreset(profileId);
    setAgentForm((prev) => {
      const previousRecommendation = buildRecommendedMemoryBankProfile(prev.profile, prev.capabilities);
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
          ? buildRecommendedMemoryBankProfile(nextProfileId, resolvedCapabilities)
          : prev.memory_bank_profile,
      };
    });
  };

  const restoreRecommendedMemoryProfile = () => {
    setAgentForm((prev) => ({
      ...prev,
      memory_bank_profile: buildRecommendedMemoryBankProfile(prev.profile, prev.capabilities),
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
    } catch (error: any) {
      alert(error.message);
    }
  };

  const handleEditAgent = (agent: AgentInfo) => {
    setEditAgentAdvancedOpen(false);
    const normalizedMemoryProfile = normalizeMemoryProfileDraft(agent.memory_bank_profile);
    const fallbackMemoryProfile = buildRecommendedMemoryBankProfile(agent.profile, agent.capabilities || []);
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

  const handleUpdateAgent = async () => {
    try {
      await updateAgent(agentForm);
      closeAgentModal();
    } catch (error: any) {
      alert(error.message);
    }
  };

  const handleUpdateTeam = async () => {
    try {
      await updateTeam(teamForm);
      closeTeamModal();
    } catch (error: any) {
      alert(error.message);
    }
  };

  const handleDeleteAgent = async (agentId: string) => {
    if (!confirm(`确定要删除 Agent "${agentId}" 吗？`)) return;
    
    try {
      await deleteAgent(agentId);
      if (selectedAgentId === agentId) {
        setSelectedAgentId(null);
      }
    } catch (error: any) {
      alert(error.message);
    }
  };

  const handleDeleteTeam = async (teamId: string) => {
    if (!confirm(`确定要删除团队 "${teamId}" 吗？`)) return;
    
    try {
      await deleteTeam(teamId);
      setSelectedTeam(null);
    } catch (error: any) {
      alert(error.message);
    }
  };

  const startGroupChat = () => {
    window.location.href = '/chat?mode=group';
  };

  if (loading) {
    return <PageLoadingState metricCount={3} showTabs={false} />;
  }

  return (
    <div className="h-full flex flex-col bg-surface-100">
      <div className="px-6 py-4 border-b border-surface-200 bg-white flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-surface-900">团队管理</h1>
          <p className="text-sm text-surface-500 mt-1">管理多 Agent 团队和协作</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={openCreateAgentModal}
            className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors flex items-center gap-2"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            创建 Agent
          </button>
              <button
                onClick={openCreateTeamModal}
                className="px-4 py-2 bg-surface-100 text-surface-700 rounded-lg hover:bg-surface-200 transition-colors flex items-center gap-2"
              >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            创建团队
          </button>
          <button
            onClick={startGroupChat}
            className="px-4 py-2 bg-accent-purple text-white rounded-lg hover:bg-accent-purple/90 transition-colors flex items-center gap-2"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" />
            </svg>
            群聊
          </button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        <TeamsSidebar
          teams={teams}
          agents={agents}
          selectedTeamId={selectedTeam?.id || null}
          selectedAgentId={selectedAgentId}
          onCreateTeam={openCreateTeamModal}
          onCreateAgent={openCreateAgentModal}
          onSelectTeam={handleSelectTeam}
          onEditTeam={handleEditTeam}
          onDeleteTeam={handleDeleteTeam}
          onSelectAgent={handleSelectAgent}
          onEditAgent={handleEditAgent}
          onDeleteAgent={handleDeleteAgent}
          getBadgeClassName={(tone, size = 'md') => getBadgeClassName(tone as BadgeTone, size)}
          getAgentProfileLabel={(profileId) => {
            if (!profileId) {
              return null;
            }
            return getAgentProfilePreset(profileId)?.label || profileId;
          }}
          getAgentPermissionLabel={(permissionId) => {
            if (!permissionId) {
              return null;
            }
            return getAgentPermissionPreset(permissionId)?.label || permissionId;
          }}
          getAgentStatusMeta={getAgentStatusMeta}
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
                workspacePath={agentAssets?.workspace_path || selectedAgent.effective_workspace || selectedAgent.workspace || '默认工作区'}
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
                assetReady={assetReady}
                assetLoading={assetLoading}
                reasoningStyleLabel={selectedAgentReasoningStyleLabel}
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
                summarySectionDefs={SUMMARY_SECTION_DEFS}
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
          ) : selectedTeam ? (
            <TeamDetailView
              selectedTeam={selectedTeam}
              selectedTeamAgents={selectedTeamAgents}
              selectedTeamLead={selectedTeamLead}
              selectedTeamCapabilitiesCount={selectedTeamCapabilitiesCount}
              getBadgeClassName={(tone, size = 'md') => getBadgeClassName(tone as BadgeTone, size)}
              getTeamMemberProfile={getTeamMemberProfile}
              getTeamRoleLabel={(role) => getTeamRoleMeta(role).label}
              getTeamPriorityLabel={(priority) => getTeamPriorityMeta(priority).label}
              onEditTeam={() => handleEditTeam(selectedTeam)}
              onSelectAgent={handleSelectAgent}
              onEditAgent={handleEditAgent}
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-2xl bg-surface-100 flex items-center justify-center mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-surface-900 mb-2">选择一个团队</h3>
              <p className="text-surface-500">从左侧列表中选择团队查看详情</p>
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
          agents={agents}
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
          getAgentById={getAgentById}
          getTeamRoleDescription={(role) => getTeamRoleMeta(role).description}
          getTeamPriorityDescription={(priority) => getTeamPriorityMeta(priority).description}
          onClose={closeTeamModal}
          onSubmit={handleCreateTeam}
        />
      )}

      {modalType === 'edit-team' && (
        <TeamFormModal
          mode="edit"
          form={teamForm}
          agents={agents}
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
          getAgentById={getAgentById}
          getTeamRoleDescription={(role) => getTeamRoleMeta(role).description}
          getTeamPriorityDescription={(priority) => getTeamPriorityMeta(priority).description}
          onClose={closeTeamModal}
          onSubmit={handleUpdateTeam}
        />
      )}
    </div>
  );
};

export default TeamsPage;
