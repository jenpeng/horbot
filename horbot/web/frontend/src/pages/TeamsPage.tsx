import React, { useEffect, useRef, useState } from 'react';
import CollaborationFlow from '../components/CollaborationFlow';
import {
  AGENT_PERMISSION_PRESETS,
  AGENT_PROFILE_PRESETS,
  getAgentPermissionPreset,
  getAgentProfilePreset,
} from '../constants';
import { getStorageItem, removeStorageItem, setStorageItem } from '../utils/storage';

interface AgentInfo {
  id: string;
  name: string;
  description: string;
  profile?: string;
  permission_profile?: string;
  tool_permission_profile?: string;
  model: string;
  provider: string;
  capabilities: string[];
  tools: string[];
  skills: string[];
  teams: string[];
  setup_required?: boolean;
  bootstrap_setup_pending?: boolean;
  workspace?: string;
  effective_workspace?: string;
  system_prompt?: string;
  personality?: string;
  avatar?: string;
  evolution_enabled?: boolean;
  learning_enabled?: boolean;
  memory_bank_profile?: {
    mission?: string;
    directives?: string[];
    reasoning_style?: string;
  };
}

interface TeamMemberProfile {
  role?: string;
  responsibility?: string;
  priority?: number;
  isLead?: boolean;
}

type TeamTemplateId = 'delivery' | 'research' | 'support' | 'custom';
type MemoryBankProfileDraft = {
  mission: string;
  directives: string[];
  reasoning_style: string;
};

interface TeamInfo {
  id: string;
  name: string;
  description: string;
  members: string[];
  member_profiles?: Record<string, TeamMemberProfile>;
  workspace?: string;
  effective_workspace?: string;
}

interface AgentBootstrapFile {
  path: string;
  exists: boolean;
  content: string;
}

interface AgentAssetBundle {
  workspace_path: string;
  summary?: {
    identity?: string[];
    role_focus?: string[];
    communication_style?: string[];
    boundaries?: string[];
    user_preferences?: string[];
    is_structured?: boolean;
    source_titles?: {
      soul?: string;
      user?: string;
    };
  };
  files: {
    soul: AgentBootstrapFile;
    user: AgentBootstrapFile;
  };
}

type SummarySectionKey =
  | 'identity'
  | 'role_focus'
  | 'communication_style'
  | 'boundaries'
  | 'user_preferences';

type SummaryDrafts = Record<SummarySectionKey, string>;

interface AgentMemoryStats {
  total_entries: number;
  total_size_kb: number;
}

interface AgentSkillInfo {
  name: string;
  source: string;
  enabled: boolean;
  always?: boolean;
}

interface AgentFormState {
  id: string;
  name: string;
  description: string;
  profile: string;
  permission_profile: string;
  model: string;
  provider: string;
  system_prompt: string;
  capabilities: string[];
  tools: string[];
  skills: string[];
  workspace: string;
  teams: string[];
  personality: string;
  avatar: string;
  evolution_enabled: boolean;
  learning_enabled: boolean;
  memory_bank_profile: {
    mission: string;
    directives: string[];
    reasoning_style: string;
  };
}

type ModalType = 'create-agent' | 'create-team' | 'edit-agent' | 'edit-team' | 'group-chat' | null;

interface ProviderInfo {
  id: string;
  name: string;
  configured: boolean;
  models: { id: string; name: string; description: string }[];
}

interface TeamsPageSelection {
  kind: 'agent' | 'team';
  id: string | null;
}

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

const AGENT_CAPABILITY_OPTIONS = [
  { id: 'planning', label: '规划', description: '复杂任务拆解与流程设计' },
  { id: 'research', label: '研究', description: '信息检索、资料梳理与分析' },
  { id: 'code', label: '编码', description: '实现功能、改代码与修复问题' },
  { id: 'testing', label: '测试', description: '回归验证、端到端与质量检查' },
  { id: 'writing', label: '写作', description: '文档、方案与内容产出' },
  { id: 'review', label: '评审', description: '代码审查与风险识别' },
  { id: 'data', label: '数据', description: '数据整理、统计与结构化处理' },
  { id: 'vision', label: '视觉', description: '图像理解、界面分析与视觉任务' },
] as const;

const MEMORY_REASONING_STYLE_OPTIONS = [
  {
    id: 'balanced',
    label: '平衡',
    description: '默认优先相关性与可执行性，避免记忆过载。',
  },
  {
    id: 'structured',
    label: '结构化',
    description: '优先按事实、决策、约束和待确认项组织记忆。',
  },
  {
    id: 'exploratory',
    label: '探索式',
    description: '更积极联想历史线索，但保留事实与推断边界。',
  },
  {
    id: 'strict',
    label: '严格约束',
    description: '优先尊重边界、偏好和显式规则，减少推断。',
  },
] as const;

const TEAM_ROLE_OPTIONS = [
  {
    id: 'member',
    label: '普通成员',
    description: '按分配任务执行，适合默认协作角色。',
  },
  {
    id: 'coordinator',
    label: '协调者',
    description: '负责拆解任务、安排接力与同步进度。',
  },
  {
    id: 'builder',
    label: '执行者',
    description: '偏实现、修复、交付和直接产出结果。',
  },
  {
    id: 'reviewer',
    label: '评审者',
    description: '偏检查质量、识别风险与验收结果。',
  },
  {
    id: 'researcher',
    label: '分析者',
    description: '偏调研、检索、对比与信息梳理。',
  },
  {
    id: 'support',
    label: '支援者',
    description: '负责补位、协助处理杂项和临时请求。',
  },
] as const;

const TEAM_PRIORITY_OPTIONS = [
  {
    value: 10,
    label: '第一棒',
    description: '通常最先接手，负责开局或澄清问题。',
  },
  {
    value: 50,
    label: '前段参与',
    description: '较早介入，适合在主流程前半段提供支持。',
  },
  {
    value: 100,
    label: '常规顺序',
    description: '默认接力位置，不主动前置也不后置。',
  },
  {
    value: 200,
    label: '后段收尾',
    description: '更适合在最后验证、收敛或补充。',
  },
] as const;

const TEAM_TEMPLATE_OPTIONS: Array<{
  id: TeamTemplateId;
  label: string;
  description: string;
  assignments: string[];
}> = [
  {
    id: 'delivery',
    label: '交付协作',
    description: '适合需求拆解、实现、验收这一类标准交付流程。',
    assignments: ['负责人负责拆解与调度', '执行者负责主要产出', '评审者负责收尾和验收'],
  },
  {
    id: 'research',
    label: '研究分析',
    description: '适合调研、方案对比、信息梳理与结论沉淀。',
    assignments: ['负责人先明确问题和维度', '分析者负责检索和整理', '评审者负责校验结论质量'],
  },
  {
    id: 'support',
    label: '响应支援',
    description: '适合客服、运维、陪跑或临时支持类团队。',
    assignments: ['负责人先接单和澄清', '支援者负责快速补位', '执行者负责落地处理'],
  },
  {
    id: 'custom',
    label: '自定义',
    description: '保留当前分工，不主动覆盖已有角色和顺序。',
    assignments: ['适合已经手动调好的团队分工'],
  },
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

const getTeamRoleMeta = (role?: string) => (
  TEAM_ROLE_OPTIONS.find((item) => item.id === (role || 'member'))
  || { id: role || 'member', label: role || '普通成员', description: '自定义角色' }
);

const getTeamPriorityMeta = (priority?: number) => (
  TEAM_PRIORITY_OPTIONS.find((item) => item.value === (priority ?? 100))
  || { value: priority ?? 100, label: `顺序 ${priority ?? 100}`, description: '自定义接力顺序' }
);

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

const createEmptyTeamForm = () => ({
  id: '',
  name: '',
  description: '',
  members: [] as string[],
  member_profiles: {} as Record<string, TeamMemberProfile>,
  workspace: '',
});

const normalizeTeamId = (value: string): string => value.trim().toLowerCase();

const readSelectionFromUrl = (): TeamsPageSelection | null => {
  if (typeof window === 'undefined') {
    return null;
  }

  const params = new URLSearchParams(window.location.search);
  const agentId = params.get('agent')?.trim();
  if (agentId) {
    return { kind: 'agent', id: agentId };
  }

  const teamId = params.get('team')?.trim();
  if (teamId) {
    return { kind: 'team', id: teamId };
  }

  return null;
};

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

const writeSelectionToUrl = (selection: TeamsPageSelection | null): void => {
  if (typeof window === 'undefined') {
    return;
  }

  const url = new URL(window.location.href);
  url.searchParams.delete('agent');
  url.searchParams.delete('team');
  url.searchParams.delete('focus');

  if (selection?.kind === 'agent' && selection.id) {
    url.searchParams.set('agent', selection.id);
  } else if (selection?.kind === 'team' && selection.id) {
    url.searchParams.set('team', selection.id);
  }

  const nextUrl = `${url.pathname}${url.search}${url.hash}`;
  window.history.replaceState(null, '', nextUrl);
};

const TeamsPage: React.FC = () => {
  const emptySummaryDrafts = (): SummaryDrafts => ({
    identity: '',
    role_focus: '',
    communication_style: '',
    boundaries: '',
    user_preferences: '',
  });

  const summaryToDrafts = (summary?: AgentAssetBundle['summary']): SummaryDrafts => ({
    identity: (summary?.identity || []).join('\n'),
    role_focus: (summary?.role_focus || []).join('\n'),
    communication_style: (summary?.communication_style || []).join('\n'),
    boundaries: (summary?.boundaries || []).join('\n'),
    user_preferences: (summary?.user_preferences || []).join('\n'),
  });

  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [teams, setTeams] = useState<TeamInfo[]>([]);
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
  const [loading, setLoading] = useState(true);
  const [modalType, setModalType] = useState<ModalType>(null);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [agentAssets, setAgentAssets] = useState<AgentAssetBundle | null>(null);
  const [agentMemoryStats, setAgentMemoryStats] = useState<AgentMemoryStats | null>(null);
  const [agentSkills, setAgentSkills] = useState<AgentSkillInfo[]>([]);
  const [editAgentAdvancedOpen, setEditAgentAdvancedOpen] = useState(false);
  const [teamAdvancedOpen, setTeamAdvancedOpen] = useState(false);
  const [selectedTeamTemplateId, setSelectedTeamTemplateId] = useState<TeamTemplateId>('delivery');
  const [teamRecommendationAutoApply, setTeamRecommendationAutoApply] = useState(true);
  const [assetDrafts, setAssetDrafts] = useState({ soul: '', user: '' });
  const [assetLoading, setAssetLoading] = useState(false);
  const [assetLoadedAgentId, setAssetLoadedAgentId] = useState<string | null>(null);
  const [assetSaving, setAssetSaving] = useState<'soul' | 'user' | null>(null);
  const [assetError, setAssetError] = useState('');
  const [assetSuccess, setAssetSuccess] = useState('');
  const [summaryDrafts, setSummaryDrafts] = useState<SummaryDrafts>(emptySummaryDrafts);
  const [summarySaving, setSummarySaving] = useState(false);
  const assetDraftsRef = useRef({ soul: '', user: '' });
  const summaryDraftsRef = useRef<SummaryDrafts>(emptySummaryDrafts());
  
  const [agentForm, setAgentForm] = useState<AgentFormState>(createEmptyAgentForm);
  
  const [teamForm, setTeamForm] = useState(createEmptyTeamForm);

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
  const recommendedTeamLead = recommendedTeamLeadId ? agents.find((agent) => agent.id === recommendedTeamLeadId) : null;

  const capabilityOptions = Array.from(new Set([
    ...AGENT_CAPABILITY_OPTIONS.map((item) => item.id),
    ...agentForm.capabilities,
  ])).map((id) => AGENT_CAPABILITY_OPTIONS.find((item) => item.id === id) || {
    id,
    label: id,
    description: '历史标签',
  });

  const fetchData = async () => {
    try {
      const [agentsRes, teamsRes, providersRes] = await Promise.all([
        fetch('/api/agents'),
        fetch('/api/teams'),
        fetch('/api/providers')
      ]);
      
      const agentsData = await agentsRes.json();
      const teamsData = await teamsRes.json();
      const providersData = await providersRes.json();
      
      const nextAgents = agentsData.agents || [];
      const nextTeams = teamsData.teams || [];
      const urlSelection = readSelectionFromUrl();
      const persistedSelection = getStorageItem<TeamsPageSelection | null>(TEAMS_PAGE_SELECTION_STORAGE_KEY, null);
      const preferredAgentId =
        (urlSelection?.kind === 'agent' ? urlSelection.id : null)
        || selectedAgentId
        || (persistedSelection?.kind === 'agent' ? persistedSelection.id : null);
      const resolvedAgentId = preferredAgentId && nextAgents.some((agent: AgentInfo) => agent.id === preferredAgentId)
        ? preferredAgentId
        : null;
      const preferredTeamId =
        (urlSelection?.kind === 'team' ? urlSelection.id : null)
        || selectedTeam?.id
        || (persistedSelection?.kind === 'team' ? persistedSelection.id : null);
      const resolvedTeam = !resolvedAgentId
        ? (
            (preferredTeamId
              ? nextTeams.find((team: TeamInfo) => team.id === preferredTeamId)
              : undefined)
            || nextTeams[0]
            || null
          )
        : null;

      setAgents(nextAgents);
      setTeams(nextTeams);
      setProviders(providersData.providers || []);
      setSelectedAgentId(resolvedAgentId);
      setSelectedTeam(resolvedTeam);
    } catch (error) {
      console.error('Failed to fetch data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

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

  const replaceAssetDrafts = (nextDrafts: { soul: string; user: string }) => {
    assetDraftsRef.current = nextDrafts;
    setAssetDrafts(nextDrafts);
  };

  const replaceSummaryDrafts = (nextDrafts: SummaryDrafts) => {
    summaryDraftsRef.current = nextDrafts;
    setSummaryDrafts(nextDrafts);
  };

  const handleAssetDraftChange = (fileKind: 'soul' | 'user', value: string) => {
    replaceAssetDrafts({
      ...assetDraftsRef.current,
      [fileKind]: value,
    });
  };

  const handleSummaryDraftChange = (key: SummarySectionKey, value: string) => {
    replaceSummaryDrafts({
      ...summaryDraftsRef.current,
      [key]: value,
    });
  };

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
  const assetReady = Boolean(selectedAgentId) && assetLoadedAgentId === selectedAgentId && !assetLoading;
  const selectedAgentProfilePreset = getAgentProfilePreset(selectedAgent?.profile);
  const selectedAgentPermissionPreset = getAgentPermissionPreset(selectedAgent?.permission_profile || selectedAgent?.tool_permission_profile || 'inherit');
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
    setAssetError('');
    setAssetSuccess('');
  };

  const handleSelectAgent = (agentId: string) => {
    setSelectedTeam(null);
    setSelectedAgentId(agentId);
    setAssetError('');
    setAssetSuccess('');
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

  useEffect(() => {
    let disposed = false;

    const loadAgentAssets = async () => {
      if (!selectedAgentId) {
        setAgentAssets(null);
        setAgentMemoryStats(null);
        setAgentSkills([]);
        replaceAssetDrafts({ soul: '', user: '' });
        replaceSummaryDrafts(emptySummaryDrafts());
        setAssetLoadedAgentId(null);
        setAssetLoading(false);
        return;
      }

      const currentAgentId = selectedAgentId;
      setAssetLoading(true);
      setAssetError('');
      setAssetLoadedAgentId(null);
      setAgentAssets(null);
      setAgentMemoryStats(null);
      setAgentSkills([]);
      replaceAssetDrafts({ soul: '', user: '' });
      replaceSummaryDrafts(emptySummaryDrafts());
      try {
        const [bootstrapRes, memoryRes, skillsRes] = await Promise.all([
          fetch(`/api/agents/${currentAgentId}/bootstrap-files`),
          fetch(`/api/memory?agent_id=${encodeURIComponent(currentAgentId)}`),
          fetch(`/api/skills?agent_id=${encodeURIComponent(currentAgentId)}`),
        ]);

        if (!bootstrapRes.ok) {
          const error = await bootstrapRes.json();
          throw new Error(error.detail || 'Failed to load agent bootstrap files');
        }

        const bootstrapData = await bootstrapRes.json();
        const memoryData = memoryRes.ok ? await memoryRes.json() : null;
        const skillsData = skillsRes.ok ? await skillsRes.json() : { skills: [] };

        if (disposed) {
          return;
        }

        setAgentAssets(bootstrapData);
        replaceAssetDrafts({
          soul: bootstrapData.files?.soul?.content || '',
          user: bootstrapData.files?.user?.content || '',
        });
        replaceSummaryDrafts(summaryToDrafts(bootstrapData.summary));
        setAgentMemoryStats(memoryData ? {
          total_entries: memoryData.total_entries || 0,
          total_size_kb: memoryData.total_size_kb || 0,
        } : null);
        setAgentSkills(skillsData.skills || []);
        setAssetLoadedAgentId(currentAgentId);
      } catch (error: any) {
        if (disposed) {
          return;
        }
        setAssetError(error.message || '加载 Agent 资产失败');
      } finally {
        if (!disposed) {
          setAssetLoading(false);
        }
      }
    };

    loadAgentAssets();

    return () => {
      disposed = true;
    };
  }, [selectedAgentId, agents]);

  const handleSaveAssetFile = async (fileKind: 'soul' | 'user') => {
    if (!selectedAgentId) return;

    try {
      setAssetSaving(fileKind);
      setAssetError('');
      setAssetSuccess('');

      const response = await fetch(`/api/agents/${selectedAgentId}/bootstrap-files/${fileKind}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: assetDraftsRef.current[fileKind] }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to save bootstrap file');
      }

      const updated = await fetch(`/api/agents/${selectedAgentId}/bootstrap-files`);
      if (updated.ok) {
        const updatedData = await updated.json();
        setAgentAssets(updatedData);
        replaceAssetDrafts({
          soul: updatedData.files?.soul?.content || '',
          user: updatedData.files?.user?.content || '',
        });
        replaceSummaryDrafts(summaryToDrafts(updatedData.summary));
      }

      fetchData();

      setAssetSuccess(fileKind === 'soul' ? 'SOUL.md 已保存' : 'USER.md 已保存');
    } catch (error: any) {
      setAssetError(error.message || '保存失败');
    } finally {
      setAssetSaving(null);
    }
  };

  const handleSaveSummary = async () => {
    if (!selectedAgentId) return;

    const toItems = (value: string) =>
      value
        .split('\n')
        .map((item) => item.trim())
        .filter(Boolean);

    try {
      setSummarySaving(true);
      setAssetError('');
      setAssetSuccess('');

      const response = await fetch(`/api/agents/${selectedAgentId}/bootstrap-summary`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          identity: toItems(summaryDraftsRef.current.identity),
          role_focus: toItems(summaryDraftsRef.current.role_focus),
          communication_style: toItems(summaryDraftsRef.current.communication_style),
          boundaries: toItems(summaryDraftsRef.current.boundaries),
          user_preferences: toItems(summaryDraftsRef.current.user_preferences),
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to save summary');
      }

      const updatedData = await response.json();
      setAgentAssets(updatedData);
      replaceAssetDrafts({
        soul: updatedData.files?.soul?.content || '',
        user: updatedData.files?.user?.content || '',
      });
      replaceSummaryDrafts(summaryToDrafts(updatedData.summary));

      fetchData();
      setAssetSuccess('配置摘要已保存，并已同步写回 SOUL.md / USER.md');
    } catch (error: any) {
      setAssetError(error.message || '保存配置摘要失败');
    } finally {
      setSummarySaving(false);
    }
  };

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
      const response = await fetch('/api/agents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(agentForm),
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create agent');
      }

      closeAgentModal();
      fetchData();
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

  const handleMemoryProfileMissionChange = (value: string) => {
    setAgentForm((prev) => ({
      ...prev,
      memory_bank_profile: {
        ...prev.memory_bank_profile,
        mission: value,
      },
    }));
  };

  const handleMemoryProfileDirectivesChange = (value: string) => {
    setAgentForm((prev) => ({
      ...prev,
      memory_bank_profile: {
        ...prev.memory_bank_profile,
        directives: value
          .split('\n')
          .map((item) => item.trim())
          .filter(Boolean),
      },
    }));
  };

  const handleMemoryProfileReasoningStyleChange = (reasoningStyle: string) => {
    setAgentForm((prev) => ({
      ...prev,
      memory_bank_profile: {
        ...prev.memory_bank_profile,
        reasoning_style: prev.memory_bank_profile.reasoning_style === reasoningStyle ? '' : reasoningStyle,
      },
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
      const response = await fetch('/api/teams', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(teamForm),
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create team');
      }

      closeTeamModal();
      fetchData();
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
      const response = await fetch(`/api/agents/${agentForm.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(agentForm),
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to update agent');
      }

      closeAgentModal();
      fetchData();
    } catch (error: any) {
      alert(error.message);
    }
  };

  const handleUpdateTeam = async () => {
    try {
      const response = await fetch(`/api/teams/${teamForm.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(teamForm),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to update team');
      }

      closeTeamModal();
      fetchData();
    } catch (error: any) {
      alert(error.message);
    }
  };

  const handleDeleteAgent = async (agentId: string) => {
    if (!confirm(`确定要删除 Agent "${agentId}" 吗？`)) return;
    
    try {
      const response = await fetch(`/api/agents/${agentId}`, { method: 'DELETE' });
      if (!response.ok) throw new Error('Failed to delete agent');
      if (selectedAgentId === agentId) {
        setSelectedAgentId(null);
      }
      fetchData();
    } catch (error: any) {
      alert(error.message);
    }
  };

  const handleDeleteTeam = async (teamId: string) => {
    if (!confirm(`确定要删除团队 "${teamId}" 吗？`)) return;
    
    try {
      const response = await fetch(`/api/teams/${teamId}`, { method: 'DELETE' });
      if (!response.ok) throw new Error('Failed to delete team');
      setSelectedTeam(null);
      fetchData();
    } catch (error: any) {
      alert(error.message);
    }
  };

  const startGroupChat = () => {
    window.location.href = '/chat?mode=group';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex gap-2">
          {[0, 1, 2].map((i) => (
            <div 
              key={i} 
              className="w-2.5 h-2.5 bg-primary-500 rounded-full animate-bounce" 
              style={{ animationDelay: `${i * 150}ms` }}
            />
          ))}
        </div>
      </div>
    );
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
        <div className="w-64 border-r border-surface-200 bg-white overflow-y-auto">
          <div className="p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-medium text-surface-500 uppercase tracking-wider">
                团队列表
              </h2>
              <button
                onClick={openCreateTeamModal}
                className="p-1 hover:bg-surface-100 rounded"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
              </button>
            </div>
            {teams.length === 0 ? (
              <div className="text-sm text-surface-500 text-center py-8">
                暂无团队配置
              </div>
            ) : (
              <div className="space-y-2">
                {teams.map((team) => (
                  <div
                    key={team.id}
                    className={`group relative p-3 rounded-xl transition-all ${
                      selectedTeam?.id === team.id
                        ? 'bg-primary-50 border border-primary-200'
                        : 'hover:bg-surface-50 border border-transparent'
                    }`}
                  >
                    <button
                      onClick={() => handleSelectTeam(team)}
                      data-testid="team-list-select"
                      data-team-id={team.id}
                      className="w-full text-left flex items-center gap-3"
                    >
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                        selectedTeam?.id === team.id
                          ? 'bg-primary-500 text-white'
                          : 'bg-surface-100 text-surface-600'
                      }`}>
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                        </svg>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-surface-900 truncate">{team.name}</p>
                        <p className="text-xs text-surface-500">{team.members.length} 成员</p>
                      </div>
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleEditTeam(team); }}
                      className="absolute right-8 top-1/2 -translate-y-1/2 p-1 opacity-0 group-hover:opacity-100 hover:bg-surface-100 rounded transition-all"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-surface-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                      </svg>
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDeleteTeam(team.id); }}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-1 opacity-0 group-hover:opacity-100 hover:bg-red-100 rounded transition-all"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="p-4 border-t border-surface-100">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-medium text-surface-500 uppercase tracking-wider">
                所有 Agent
              </h2>
              <button
                onClick={openCreateAgentModal}
                className="p-1 hover:bg-surface-100 rounded"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
              </button>
            </div>
            <div className="space-y-2">
              {agents.map((agent) => {
                const statusMeta = getAgentStatusMeta(agent);
                return (
                  <div
                    key={agent.id}
                    data-testid="agent-list-item"
                    data-agent-id={agent.id}
                    className={`group relative flex items-center gap-3 p-2 rounded-lg transition-colors ${
                      selectedAgentId === agent.id ? 'bg-primary-50 ring-1 ring-primary-200' : 'hover:bg-surface-50'
                    }`}
                  >
                    <button
                      onClick={() => handleSelectAgent(agent.id)}
                      data-testid="agent-list-select"
                      data-agent-id={agent.id}
                      className="min-w-0 flex flex-1 items-center gap-3 text-left"
                    >
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                        agent.setup_required ? 'bg-accent-orange/15 text-accent-orange' : 'bg-surface-100 text-surface-600'
                      }`}>
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-surface-900 truncate">{agent.name}</p>
                        <div className="flex items-center gap-2">
                          <p className="text-xs text-surface-500 truncate">{agent.description || agent.model || '等待首次配置'}</p>
                          {agent.profile && (
                            <span className={`shrink-0 ${getBadgeClassName('neutral', 'sm')}`}>
                              {getAgentProfilePreset(agent.profile)?.label || agent.profile}
                            </span>
                          )}
                          {(agent.permission_profile || agent.tool_permission_profile) && (
                            <span className={`shrink-0 ${getBadgeClassName('slate', 'sm')}`}>
                              {getAgentPermissionPreset(agent.permission_profile || agent.tool_permission_profile)?.label || agent.permission_profile || agent.tool_permission_profile}
                            </span>
                          )}
                        </div>
                      </div>
                      <span className={getBadgeClassName(statusMeta.tone, 'sm')}>{statusMeta.shortLabel}</span>
                    </button>
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-all">
                      <button
                        onClick={() => handleEditAgent(agent)}
                        className="p-1 hover:bg-surface-200 rounded transition-all"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 text-surface-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                        </svg>
                      </button>
                      <button
                        onClick={() => handleDeleteAgent(agent.id)}
                        className="p-1 hover:bg-red-100 rounded transition-all"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {selectedAgent ? (
            <div className="space-y-6" data-testid="agent-detail-view" data-agent-id={selectedAgent.id}>
              <div className="bg-white rounded-2xl border border-surface-200 p-6 transition-shadow" data-focus-anchor="agent-overview">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-2xl font-bold text-surface-900">{selectedAgent.name}</h2>
                      <span className={getBadgeClassName(selectedAgentStatusMeta.tone)}>
                        {selectedAgentStatusMeta.detailLabel}
                      </span>
                    </div>
                    <p className="text-surface-600 mt-1">{selectedAgent.description || '暂无描述'}</p>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs text-surface-500">
                      {selectedAgent.profile && (
                        <span className={getBadgeClassName('neutral')}>
                          {selectedAgentProfilePreset?.label || selectedAgent.profile}
                        </span>
                      )}
                      {(selectedAgent.permission_profile || selectedAgent.tool_permission_profile) && (
                        <span className={getBadgeClassName('slate')}>
                          {getAgentPermissionPreset(selectedAgent.permission_profile || selectedAgent.tool_permission_profile)?.label || selectedAgent.permission_profile || selectedAgent.tool_permission_profile}
                        </span>
                      )}
                      <span className={getBadgeClassName('neutral')}>{selectedAgent.provider || '未选择 provider'}</span>
                      <span className={getBadgeClassName('neutral')}>{selectedAgent.model || '未选择模型'}</span>
                      <span className={getBadgeClassName('neutral')}>{selectedAgent.teams.length} 个团队</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleEditAgent(selectedAgent)}
                      className="px-3 py-2 bg-white border border-surface-200 text-surface-700 rounded-xl hover:bg-surface-50 transition-colors"
                    >
                      编辑 Agent
                    </button>
                    <button
                      onClick={() => {
                        const setupQuery = (selectedAgent.setup_required || selectedAgent.bootstrap_setup_pending) ? '&setup=1' : '';
                        window.location.href = `/chat?agent=${encodeURIComponent(selectedAgent.id)}${setupQuery}`;
                      }}
                      className="px-3 py-2 bg-primary-500 text-white rounded-xl hover:bg-primary-600 transition-colors"
                    >
                      打开单聊
                    </button>
                  </div>
                </div>
                {selectedAgent.setup_required && (
                  <div className={`mt-4 ${getNoticeClassName('warning')}`}>
                    <div className="font-semibold text-surface-900">这个 Agent 还没有完成首次配置。</div>
                    <div className="mt-1">
                      先在这里为它选择 provider 和 model，然后进入私聊，用第一轮对话引导它完善职责、风格和协作边界。
                    </div>
                  </div>
                )}
                {!selectedAgent.setup_required && selectedAgent.bootstrap_setup_pending && (
                  <div className={`mt-4 ${getNoticeClassName('pending')}`}>
                    <div className="font-semibold">这个 Agent 已具备模型能力，但首次私聊引导还没完全落盘。</div>
                    <div className="mt-1">
                      建议继续单聊，直到它把 `SOUL.md` 与 `USER.md` 写成正式版本并移除待配置标记。
                    </div>
                  </div>
                )}
                {!selectedAgent.setup_required && !selectedAgent.bootstrap_setup_pending && (
                  <div className={`mt-4 ${getNoticeClassName('success')}`}>
                    <div className="font-semibold">这个 Agent 已完成个性化配置。</div>
                    <div className="mt-1">
                      后续可以继续通过私聊或直接编辑 `SOUL.md` / `USER.md` 逐步微调，不再强制进入首次引导流程。
                    </div>
                  </div>
                )}
                <div className="mt-4 rounded-2xl bg-surface-50 px-4 py-3 text-sm text-surface-600">
                  {selectedAgent.profile && (
                    <div className="mb-2">
                      <span className="font-semibold text-surface-900">协作画像：</span>
                      <span>{selectedAgentProfilePreset?.summary || selectedAgent.profile}</span>
                    </div>
                  )}
                  {(selectedAgent.permission_profile || selectedAgent.tool_permission_profile) && (
                    <div className="mb-2">
                      <span className="font-semibold text-surface-900">权限档位：</span>
                      <span>
                        {selectedAgentPermissionPreset?.summary || selectedAgent.permission_profile || selectedAgent.tool_permission_profile}
                        {selectedAgent.permission_profile ? '' : '（继承全局）'}
                      </span>
                    </div>
                  )}
                  <div className="mb-2">
                    <span className="font-semibold text-surface-900">配置状态：</span>
                    <span>
                      {selectedAgent.setup_required
                        ? '缺少 provider / model'
                        : selectedAgent.bootstrap_setup_pending
                          ? '模型已就绪，等待首次私聊引导落盘'
                          : '已完成个性化配置'}
                    </span>
                  </div>
                  {(selectedAgent.memory_bank_profile?.mission
                    || selectedAgent.memory_bank_profile?.directives?.length
                    || selectedAgent.memory_bank_profile?.reasoning_style) && (
                    <div className="mb-2">
                      <span className="font-semibold text-surface-900">记忆银行画像：</span>
                      <span>
                        {selectedAgent.memory_bank_profile?.mission || '未设置使命'}
                        {selectedAgent.memory_bank_profile?.reasoning_style
                          ? ` · ${MEMORY_REASONING_STYLE_OPTIONS.find((item) => item.id === selectedAgent.memory_bank_profile?.reasoning_style)?.label || selectedAgent.memory_bank_profile?.reasoning_style}`
                          : ''}
                      </span>
                    </div>
                  )}
                  <div>
                    <span className="font-semibold text-surface-900">实际工作区：</span>
                    <span className="break-all">{agentAssets?.workspace_path || selectedAgent.effective_workspace || selectedAgent.workspace || '默认工作区'}</span>
                  </div>
                  <div className="mt-2">
                    <span className="font-semibold text-surface-900">系统提示：</span>
                    <span>{selectedAgent.system_prompt ? '已配置实例级系统提示词' : '未配置实例级系统提示词'}</span>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h3 className="text-lg font-semibold text-surface-900">日常协作</h3>
                      <p className="mt-1 text-sm text-surface-500">先看当前可直接影响聊天与协作表现的运行、技能和记忆状态。</p>
                    </div>
                  </div>
                </div>
                <div className="bg-white rounded-2xl border border-surface-200 p-6 transition-shadow" data-focus-anchor="agent-runtime">
                  <h3 className="text-lg font-semibold text-surface-900">运行摘要</h3>
                  {assetReady ? (
                    <div className="mt-4 space-y-3">
                      <div className="rounded-xl bg-surface-50 p-4">
                        <p className="text-xs uppercase tracking-wide text-surface-500">记忆条目</p>
                        <p className="mt-1 text-2xl font-bold text-surface-900">{agentMemoryStats?.total_entries ?? '未加载'}</p>
                      </div>
                      <div className="rounded-xl bg-surface-50 p-4">
                        <p className="text-xs uppercase tracking-wide text-surface-500">记忆体积</p>
                        <p className="mt-1 text-2xl font-bold text-surface-900">
                          {agentMemoryStats ? `${agentMemoryStats.total_size_kb} KB` : '未加载'}
                        </p>
                      </div>
                      <div className="rounded-xl bg-surface-50 p-4">
                        <p className="text-xs uppercase tracking-wide text-surface-500">技能数量</p>
                        <p className="mt-1 text-2xl font-bold text-surface-900">{agentSkills.length}</p>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-4 space-y-3">
                      {['记忆条目', '记忆体积', '技能数量'].map((label) => (
                        <div key={label} className="rounded-xl bg-surface-50 p-4">
                          <div className="animate-pulse">
                            <div className="h-3 w-20 rounded bg-surface-200" />
                            <div className="mt-3 h-8 w-24 rounded bg-surface-200" />
                          </div>
                          <p className="mt-2 text-xs text-surface-500">
                            {assetLoading ? `正在加载 ${label}...` : '等待当前 Agent 运行摘要就绪...'}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="bg-white rounded-2xl border border-surface-200 p-6">
                  <h3 className="text-lg font-semibold text-surface-900">技能概览</h3>
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
                          {skill.always ? ' · always' : ''}
                        </span>
                      )) : (
                        <p className="text-sm text-surface-500">当前 Agent 没有加载到独立技能。</p>
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
                        {assetLoading ? '正在加载当前 Agent 技能...' : '等待当前 Agent 技能概览就绪...'}
                      </p>
                    </div>
                  )}
                </div>

                <div className="bg-white rounded-2xl border border-surface-200 p-6 lg:col-span-2 transition-shadow">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h3 className="text-lg font-semibold text-surface-900">记忆银行画像</h3>
                      <p className="mt-1 text-sm text-surface-500">这组设置只影响记忆召回、解释与反思，不直接替代人格文件。</p>
                    </div>
                    {selectedAgent.memory_bank_profile?.reasoning_style && (
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                        {MEMORY_REASONING_STYLE_OPTIONS.find((item) => item.id === selectedAgent.memory_bank_profile?.reasoning_style)?.label || selectedAgent.memory_bank_profile?.reasoning_style}
                      </span>
                    )}
                  </div>
                  <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
                    <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-surface-500">Mission</div>
                      <div className="mt-2 text-sm text-surface-800">
                        {selectedAgent.memory_bank_profile?.mission || '未设置。建议说明这个 Agent 在长期记忆里应优先服务什么目标。'}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4 md:col-span-2">
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-xs font-medium uppercase tracking-wide text-surface-500">Directives</div>
                        <span className="text-xs text-surface-500">{selectedAgent.memory_bank_profile?.directives?.length || 0} 条</span>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {(selectedAgent.memory_bank_profile?.directives || []).length > 0 ? (
                          (selectedAgent.memory_bank_profile?.directives || []).map((directive) => (
                            <span key={directive} className="rounded-full bg-white px-3 py-1.5 text-xs text-surface-700 ring-1 ring-surface-200">
                              {directive}
                            </span>
                          ))
                        ) : (
                          <p className="text-sm text-surface-500">未设置。可补充“优先记住什么”“如何解释历史约束”“何时保守处理”等规则。</p>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="lg:col-span-3 pt-2">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h3 className="text-lg font-semibold text-surface-900">档案与配置</h3>
                      <p className="mt-1 text-sm text-surface-500">结构化摘要和人格档案属于低频配置，集中放在后面统一管理。</p>
                    </div>
                  </div>
                </div>

                <div className="bg-white rounded-2xl border border-surface-200 p-6 lg:col-span-2 transition-shadow" data-focus-anchor="agent-summary">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h3 className="text-lg font-semibold text-surface-900">配置摘要</h3>
                      <p className="mt-1 text-sm text-surface-500">这里按分类直接编辑结构化要点。每行一条，保存后会自动写回 `SOUL.md` 和 `USER.md` 对应章节。</p>
                    </div>
                    {assetReady && (
                      <button
                        onClick={handleSaveSummary}
                        disabled={summarySaving}
                        data-testid="agent-save-summary"
                        className="px-3 py-2 rounded-xl bg-primary-500 text-white hover:bg-primary-600 disabled:opacity-60 transition-colors"
                      >
                        {summarySaving ? '保存中...' : '保存摘要'}
                      </button>
                    )}
                  </div>
                  {assetReady ? (
                    <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                      {SUMMARY_SECTION_DEFS.map((section) => (
                        <div key={section.key} className="rounded-2xl border border-surface-200 bg-surface-50 p-4">
                          <div className="flex items-center justify-between gap-3">
                            <div className="text-sm font-semibold text-surface-900">{section.label}</div>
                            <span className="text-xs text-surface-500">
                              {(summaryDrafts[section.key] || '')
                                .split('\n')
                                .map((item) => item.trim())
                                .filter(Boolean).length} 条
                            </span>
                          </div>
                          <textarea
                            value={summaryDrafts[section.key]}
                            onChange={(e) => handleSummaryDraftChange(section.key, e.target.value)}
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
                      <h3 className="text-lg font-semibold text-surface-900">Bootstrap 文件</h3>
                      <p className="text-sm text-surface-500 mt-1">这里直接管理当前 Agent 的独立人格与用户档案文件。若文件仍处于初始状态，系统会按画像和权限档位自动生成待确认模板。</p>
                    </div>
                    {assetLoading && <span className="text-sm text-surface-500">加载中...</span>}
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
                        selectedAgent?.bootstrap_setup_pending
                          ? NOTICE_TONE_CLASSES.pending
                          : NOTICE_TONE_CLASSES.success
                      }`}>
                        {selectedAgent?.bootstrap_setup_pending
                          ? '当前仍处于首次引导阶段：建议继续通过私聊完善信息，或在这里手动补全并移除待配置标记。'
                          : '当前档案已完成初始化，不会再自动进入首次引导。'}
                      </div>
                      <div className="mt-4 grid grid-cols-1 xl:grid-cols-2 gap-4">
                      <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4 transition-shadow" data-focus-anchor="agent-file-soul">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <h4 className="font-semibold text-surface-900">SOUL.md</h4>
                            <p className="text-xs text-surface-500 break-all">{agentAssets?.files?.soul?.path || '未加载'}</p>
                          </div>
                          <button
                            onClick={() => handleSaveAssetFile('soul')}
                            data-testid="agent-save-soul"
                            disabled={assetSaving === 'soul'}
                            className="px-3 py-2 bg-primary-500 text-white rounded-xl hover:bg-primary-600 disabled:opacity-60 transition-colors"
                          >
                            {assetSaving === 'soul' ? '保存中...' : '保存 SOUL'}
                          </button>
                        </div>
                        <textarea
                          data-testid="agent-soul-editor"
                          value={assetDrafts.soul}
                          onChange={(e) => handleAssetDraftChange('soul', e.target.value)}
                          className="mt-4 h-72 w-full rounded-xl border border-surface-300 bg-white px-3 py-3 text-sm text-surface-800 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                          placeholder="为这个 Agent 编写独立的 SOUL.md..."
                        />
                      </div>

                      <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4 transition-shadow" data-focus-anchor="agent-file-user">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <h4 className="font-semibold text-surface-900">USER.md</h4>
                            <p className="text-xs text-surface-500 break-all">{agentAssets?.files?.user?.path || '未加载'}</p>
                          </div>
                          <button
                            onClick={() => handleSaveAssetFile('user')}
                            data-testid="agent-save-user"
                            disabled={assetSaving === 'user'}
                            className="px-3 py-2 bg-surface-900 text-white rounded-xl hover:bg-surface-800 disabled:opacity-60 transition-colors"
                          >
                            {assetSaving === 'user' ? '保存中...' : '保存 USER'}
                          </button>
                        </div>
                        <textarea
                          data-testid="agent-user-editor"
                          value={assetDrafts.user}
                          onChange={(e) => handleAssetDraftChange('user', e.target.value)}
                          className="mt-4 h-72 w-full rounded-xl border border-surface-300 bg-white px-3 py-3 text-sm text-surface-800 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                          placeholder="为这个 Agent 编写独立的 USER.md..."
                        />
                      </div>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-4 grid grid-cols-1 xl:grid-cols-2 gap-4">
                      {['SOUL.md', 'USER.md'].map((label) => (
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
                            {assetLoading ? `正在加载 ${label}...` : '等待当前 Agent 资产就绪...'}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : selectedTeam ? (
            <div data-testid="team-detail-view" data-team-id={selectedTeam.id}>
              <div className="mb-6 transition-shadow" data-focus-anchor="team-overview">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-2xl font-bold text-surface-900">{selectedTeam.name}</h2>
                    {selectedTeam.description && (
                      <p className="text-surface-600 mt-1">{selectedTeam.description}</p>
                    )}
                    <p className="mt-2 text-xs text-surface-500">
                      工作空间：{selectedTeam.effective_workspace || selectedTeam.workspace || '默认团队目录'}
                    </p>
                  </div>
                  <button
                    onClick={() => handleEditTeam(selectedTeam)}
                    className="px-3 py-2 bg-white border border-surface-200 text-surface-700 rounded-xl hover:bg-surface-50 transition-colors flex items-center gap-2"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                    </svg>
                    编辑团队
                  </button>
                </div>
                <div className="mt-4 flex flex-wrap gap-2 text-xs text-surface-500">
                  <span className={getBadgeClassName('neutral')}>{selectedTeamAgents.length} 个成员</span>
                  <span className={getBadgeClassName(selectedTeamLead ? 'primary' : 'neutral')}>{selectedTeamLead ? `负责人 ${selectedTeamLead.name}` : '未指定负责人'}</span>
                  <span className={getBadgeClassName('neutral')}>{selectedTeamCapabilitiesCount} 类能力</span>
                  <span className={getBadgeClassName('neutral')}>{selectedTeam.workspace || selectedTeam.effective_workspace ? '自定义工作区' : '默认工作区'}</span>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="lg:col-span-2">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h3 className="text-lg font-semibold text-surface-900">日常协作</h3>
                      <p className="mt-1 text-sm text-surface-500">优先查看成员组成和当前团队接力流程。</p>
                    </div>
                  </div>
                </div>
                <div className="bg-white rounded-2xl border border-surface-200 p-6 transition-shadow" data-focus-anchor="team-members">
                  <h3 className="text-lg font-semibold text-surface-900 mb-4">团队成员</h3>
                  <div className="space-y-3">
                    {selectedTeamAgents.map((agent) => (
                      <div
                        key={agent.id}
                        className="group flex items-center gap-3 p-3 rounded-xl bg-surface-50 hover:bg-surface-100 transition-colors"
                      >
                        <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-surface-200 text-surface-600">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                          </svg>
                        </div>
                        <div className="flex-1 min-w-0">
                          {(() => {
                            const profile = getTeamMemberProfile(selectedTeam, agent.id);
                            const roleMeta = getTeamRoleMeta(profile.role);
                            const priorityMeta = getTeamPriorityMeta(profile.priority);
                            return (
                              <>
                          <div className="flex items-center gap-2">
                            <p className="font-medium text-surface-900">{agent.name}</p>
                            {profile.isLead && (
                              <span className={getBadgeClassName('primary', 'sm')}>负责人</span>
                            )}
                            {profile.role && profile.role !== 'member' && (
                              <span className={getBadgeClassName('neutral', 'sm')}>{roleMeta.label}</span>
                            )}
                          </div>
                          <p className="text-sm text-surface-500">{agent.description || '暂无描述'}</p>
                          {profile.responsibility && (
                            <p className="mt-1 text-xs text-surface-500">负责内容：{profile.responsibility}</p>
                          )}
                          <p className="mt-1 text-[11px] text-surface-400">接力顺序：{priorityMeta.label}</p>
                              </>
                            );
                          })()}
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="text-right">
                            <p className="text-xs text-surface-400">{agent.provider}</p>
                            <p className="text-xs text-surface-500">{agent.model}</p>
                            <p className="text-[11px] text-surface-400 truncate max-w-[180px]" title={agent.effective_workspace}>
                              {agent.effective_workspace || agent.workspace || '默认工作区'}
                            </p>
                          </div>
                          <button
                            onClick={() => handleSelectAgent(agent.id)}
                            data-testid="team-member-open-agent"
                            data-agent-id={agent.id}
                            className="p-1.5 opacity-0 group-hover:opacity-100 hover:bg-white rounded transition-all"
                            title="查看 Agent 资产"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12H9m12 0c0 1.657-4.03 6-9 6s-9-4.343-9-6 4.03-6 9-6 9 4.343 9 6z" />
                            </svg>
                          </button>
                          <button
                            onClick={() => handleEditAgent(agent)}
                            className="p-1.5 opacity-0 group-hover:opacity-100 hover:bg-white rounded transition-all"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-surface-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    ))}
                    {selectedTeamAgents.length === 0 && (
                      <div className="text-center py-8 text-surface-500">
                        该团队暂无成员
                      </div>
                    )}
                  </div>
                </div>

                <div className="lg:col-span-2 bg-white rounded-2xl border border-surface-200 p-6 transition-shadow" data-focus-anchor="team-collaboration">
                  <div className="mb-4">
                    <h3 className="text-lg font-semibold text-surface-900">团队协作流</h3>
                    <p className="mt-1 text-sm text-surface-500">这里查看群聊接力、分工协作和当前执行流。</p>
                  </div>
                  <CollaborationFlow teamId={selectedTeam.id} />
                </div>

                <div className="lg:col-span-2 pt-2">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h3 className="text-lg font-semibold text-surface-900">资产与拓扑</h3>
                      <p className="mt-1 text-sm text-surface-500">能力分布和团队工作区属于次级信息，放在协作视图之后。</p>
                    </div>
                  </div>
                </div>

                <div className="bg-white rounded-2xl border border-surface-200 p-6">
                  <h3 className="text-lg font-semibold text-surface-900 mb-4">能力分布</h3>
                  <div className="space-y-3">
                    {Array.from(new Set(selectedTeamAgents.flatMap(a => a.capabilities))).map((capability) => {
                      const agentsWithCapability = selectedTeamAgents.filter(a => a.capabilities.includes(capability));
                      return (
                        <div key={capability} className="p-3 rounded-xl bg-surface-50">
                          <div className="flex items-center justify-between mb-2">
                            <span className="font-medium text-surface-900">{capability}</span>
                            <span className="text-xs text-surface-500">{agentsWithCapability.length} 个 Agent</span>
                          </div>
                          <div className="flex flex-wrap gap-1">
                            {agentsWithCapability.map((agent) => (
                              <span
                                key={agent.id}
                                className="text-xs bg-white px-2 py-1 rounded-lg border border-surface-200 text-surface-600"
                              >
                                {agent.name}
                              </span>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                    {selectedTeamAgents.flatMap(a => a.capabilities).length === 0 && (
                      <div className="text-center py-8 text-surface-500">
                        暂无能力信息
                      </div>
                    )}
                  </div>
                </div>

                <div className="bg-white rounded-2xl border border-surface-200 p-6 lg:col-span-2 transition-shadow" data-focus-anchor="team-workspace">
                  <h3 className="text-lg font-semibold text-surface-900 mb-4">团队工作空间</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="p-4 rounded-xl bg-surface-50 text-center">
                      <div className="w-10 h-10 mx-auto mb-2 rounded-xl bg-primary-100 flex items-center justify-center">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                        </svg>
                      </div>
                      <p className="text-sm font-medium text-surface-900">共享工作空间</p>
                      <p className="text-xs text-surface-500 mt-1">团队共享文件</p>
                    </div>
                    <div className="p-4 rounded-xl bg-surface-50 text-center">
                      <div className="w-10 h-10 mx-auto mb-2 rounded-xl bg-accent-purple/10 flex items-center justify-center">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-accent-purple" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                      </div>
                      <p className="text-sm font-medium text-surface-900">共享记忆</p>
                      <p className="text-xs text-surface-500 mt-1">团队上下文</p>
                    </div>
                    <div className="p-4 rounded-xl bg-surface-50 text-center">
                      <div className="w-10 h-10 mx-auto mb-2 rounded-xl bg-accent-emerald/10 flex items-center justify-center">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-accent-emerald" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                        </svg>
                      </div>
                      <p className="text-sm font-medium text-surface-900">消息总线</p>
                      <p className="text-xs text-surface-500 mt-1">Agent 通信</p>
                    </div>
                    <div className="p-4 rounded-xl bg-surface-50 text-center">
                      <div className="w-10 h-10 mx-auto mb-2 rounded-xl bg-accent-orange/10 flex items-center justify-center">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-accent-orange" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                        </svg>
                      </div>
                      <p className="text-sm font-medium text-surface-900">任务委派</p>
                      <p className="text-xs text-surface-500 mt-1">工作分配</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
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

      {/* Create Agent Modal */}
      {modalType === 'create-agent' && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-4xl mx-4">
            <h3 className="text-lg font-semibold text-surface-900 mb-4">创建新 Agent</h3>
            <div className="space-y-4 max-h-[70vh] overflow-y-auto">
              <div>
                <label className="block text-sm font-medium text-surface-700 mb-1">ID</label>
                <input
                  type="text"
                  value={agentForm.id}
                  onChange={(e) => setAgentForm({ ...agentForm, id: e.target.value })}
                  className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 ${
                    createAgentIdError ? 'border-red-300 bg-red-50/40' : 'border-surface-300'
                  }`}
                  placeholder="agent-id"
                  aria-invalid={Boolean(createAgentIdError)}
                />
                {createAgentIdError && (
                  <p className="mt-1 text-xs text-red-600">{createAgentIdError}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-700 mb-1">名称</label>
                <input
                  type="text"
                  value={agentForm.name}
                  onChange={(e) => setAgentForm({ ...agentForm, name: e.target.value })}
                  className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 ${
                    createAgentNameError ? 'border-red-300 bg-red-50/40' : 'border-surface-300'
                  }`}
                  placeholder="Agent 名称"
                  aria-invalid={Boolean(createAgentNameError)}
                />
                {createAgentNameError && (
                  <p className="mt-1 text-xs text-red-600">{createAgentNameError}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-700 mb-1">描述</label>
                <input
                  type="text"
                  value={agentForm.description}
                  onChange={(e) => setAgentForm({ ...agentForm, description: e.target.value })}
                  className="w-full px-3 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="Agent 描述"
                />
              </div>
              <div className="border-t border-surface-200 pt-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h4 className="text-sm font-medium text-surface-700">协作画像</h4>
                    <p className="mt-1 text-xs text-surface-500">用可视化方式给 Agent 一个默认工作风格，首次私聊时再继续细化。</p>
                  </div>
                  {agentForm.profile && (
                    <button
                      type="button"
                      onClick={() => setAgentForm({ ...agentForm, profile: '', memory_bank_profile: buildRecommendedMemoryBankProfile('', agentForm.capabilities) })}
                      className="text-xs text-surface-500 hover:text-surface-700"
                    >
                      清除画像
                    </button>
                  )}
                </div>
                <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {AGENT_PROFILE_PRESETS.map((preset) => {
                    const selected = agentForm.profile === preset.id;
                    return (
                      <button
                        key={preset.id}
                        type="button"
                        onClick={() => applyAgentProfilePreset(preset.id)}
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
                            const capability = AGENT_CAPABILITY_OPTIONS.find((item) => item.id === capabilityId);
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
                    <p className="mt-1 text-xs text-surface-500">创建时可先给一个默认权限档位；不选则继承系统全局配置。</p>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {AGENT_PERMISSION_PRESETS.map((preset) => {
                    const selected = (agentForm.permission_profile || 'inherit') === preset.id;
                    return (
                      <button
                        key={preset.id}
                        type="button"
                        onClick={() => applyAgentPermissionPreset(preset.id)}
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
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 px-4 py-4 text-sm text-surface-700">
                <div className="font-semibold text-surface-900">记忆银行画像已自动设置为默认策略。</div>
                <div className="mt-1">
                  当前会按“{recommendedMemoryProfileMeta.label}”创建记忆偏好，系统会自动决定长期目标、召回倾向和反思重点。通常不需要在创建阶段手动配置，后续如果觉得不合适，再到编辑页微调即可。
                </div>
              </div>
              <div className="rounded-2xl border border-primary-200 bg-primary-50/70 px-4 py-4 text-sm text-surface-700">
                <div className="font-semibold text-surface-900">创建阶段只保留最小信息。</div>
                <div className="mt-1">
                  创建完成后，请在 Agent 详情里选择 provider 和 model；随后进入该 Agent 的第一次私聊，继续引导它完善职责、风格与协作边界。
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={closeAgentModal}
                className="px-4 py-2 text-surface-700 hover:bg-surface-100 rounded-lg transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleCreateAgent}
                disabled={createAgentSubmitDisabled}
                className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors disabled:cursor-not-allowed disabled:bg-surface-300"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Agent Modal */}
      {modalType === 'edit-agent' && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-4xl mx-4">
            <h3 className="text-lg font-semibold text-surface-900 mb-4">编辑 Agent</h3>
            <div className="space-y-4 max-h-[70vh] overflow-y-auto">
              <div>
                <label className="block text-sm font-medium text-surface-700 mb-1">ID</label>
                <input
                  type="text"
                  value={agentForm.id}
                  disabled
                  className="w-full px-3 py-2 border border-surface-300 rounded-lg bg-surface-50 text-surface-500 cursor-not-allowed"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-700 mb-1">名称</label>
                <input
                  type="text"
                  value={agentForm.name}
                  onChange={(e) => setAgentForm({ ...agentForm, name: e.target.value })}
                  className="w-full px-3 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="Agent 名称"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-700 mb-1">描述</label>
                <input
                  type="text"
                  value={agentForm.description}
                  onChange={(e) => setAgentForm({ ...agentForm, description: e.target.value })}
                  className="w-full px-3 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="Agent 描述"
                />
              </div>
              <div className="border-t border-surface-200 pt-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h4 className="text-sm font-medium text-surface-700">协作画像</h4>
                    <p className="mt-1 text-xs text-surface-500">这里保存 Agent 的可视化 profile，不直接替代首次私聊里的细节设定。</p>
                  </div>
                  {agentForm.profile && (
                    <button
                      type="button"
                      onClick={() => setAgentForm({ ...agentForm, profile: '', memory_bank_profile: buildRecommendedMemoryBankProfile('', agentForm.capabilities) })}
                      className="text-xs text-surface-500 hover:text-surface-700"
                    >
                      清除画像
                    </button>
                  )}
                </div>
                <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {AGENT_PROFILE_PRESETS.map((preset) => {
                    const selected = agentForm.profile === preset.id;
                    return (
                      <button
                        key={preset.id}
                        type="button"
                        onClick={() => applyAgentProfilePreset(preset.id)}
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
                            const capability = AGENT_CAPABILITY_OPTIONS.find((item) => item.id === capabilityId);
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
                    <p className="mt-1 text-xs text-surface-500">为当前 Agent 选择默认权限档位；未单独设置时将继承系统全局权限。</p>
                  </div>
                  {agentForm.permission_profile && (
                    <button
                      type="button"
                      onClick={() => setAgentForm({ ...agentForm, permission_profile: '' })}
                      className="text-xs text-surface-500 hover:text-surface-700"
                    >
                      继承全局
                    </button>
                  )}
                </div>
                <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {AGENT_PERMISSION_PRESETS.map((preset) => {
                    const selected = (agentForm.permission_profile || 'inherit') === preset.id;
                    return (
                      <button
                        key={preset.id}
                        type="button"
                        onClick={() => applyAgentPermissionPreset(preset.id)}
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
              
              <div className="border-t border-surface-200 pt-4">
                <h4 className="text-sm font-medium text-surface-700 mb-3">模型配置</h4>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-surface-600 mb-1">供应商</label>
                    <select
                      value={agentForm.provider}
                      onChange={(e) => setAgentForm({ ...agentForm, provider: e.target.value })}
                      className="w-full px-3 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
                    >
                      <option value="auto">自动选择</option>
                      {providers.map((p) => (
                        <option key={p.id} value={p.id} disabled={!p.configured}>
                          {p.name} {!p.configured && '(未配置)'}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-surface-600 mb-1">模型名称</label>
                    <input
                      type="text"
                      value={agentForm.model}
                      onChange={(e) => setAgentForm({ ...agentForm, model: e.target.value })}
                      className="w-full px-3 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
                      placeholder="如: gpt-4o, claude-3-5-sonnet"
                    />
                    <p className="mt-1 text-xs text-surface-500">
                      provider 和 model 只在这里配置；未设置时该 Agent 会被视为待完成首次配置。
                    </p>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-surface-200 bg-surface-50/80 px-4 py-4">
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                  <div>
                    <h4 className="text-sm font-medium text-surface-800">高级设置</h4>
                    <p className="mt-1 text-xs text-surface-500">低频配置默认收起，避免编辑 Agent 时一次看到过多信息。</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setEditAgentAdvancedOpen((current) => !current)}
                    data-testid="agent-edit-advanced-toggle"
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-surface-300 bg-white px-3 py-2 text-sm font-medium text-surface-700 transition-colors hover:border-primary-300 hover:text-primary-700"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className={`h-4 w-4 transition-transform ${editAgentAdvancedOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                    {editAgentAdvancedOpen ? '收起高级设置' : '展开高级设置'}
                  </button>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {agentAdvancedSummaryItems.map((item) => (
                    <span key={item} className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-surface-600 ring-1 ring-surface-200">
                      {item}
                    </span>
                  ))}
                </div>
              </div>

              {editAgentAdvancedOpen && (
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
                          onClick={restoreRecommendedMemoryProfile}
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
                          value={agentForm.memory_bank_profile.mission}
                          onChange={(e) => handleMemoryProfileMissionChange(e.target.value)}
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
                          {agentForm.memory_bank_profile.reasoning_style && (
                            <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-surface-700 ring-1 ring-surface-200">
                              {MEMORY_REASONING_STYLE_OPTIONS.find((item) => item.id === agentForm.memory_bank_profile.reasoning_style)?.label || agentForm.memory_bank_profile.reasoning_style}
                            </span>
                          )}
                        </div>
                        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                          {MEMORY_REASONING_STYLE_OPTIONS.map((option) => {
                            const selected = agentForm.memory_bank_profile.reasoning_style === option.id;
                            return (
                              <button
                                key={option.id}
                                type="button"
                                onClick={() => handleMemoryProfileReasoningStyleChange(option.id)}
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
                            value={agentForm.memory_bank_profile.directives.join('\n')}
                            onChange={(e) => handleMemoryProfileDirectivesChange(e.target.value)}
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
                        value={agentForm.workspace}
                        onChange={(e) => setAgentForm({ ...agentForm, workspace: e.target.value })}
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
                                checked={agentForm.teams.includes(team.id)}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setAgentForm({ ...agentForm, teams: [...agentForm.teams, team.id] });
                                  } else {
                                    setAgentForm({ ...agentForm, teams: agentForm.teams.filter((id) => id !== team.id) });
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
                        const selected = agentForm.capabilities.includes(capability.id);
                        return (
                          <button
                            key={capability.id}
                            type="button"
                            onClick={() => setAgentForm({
                              ...agentForm,
                              capabilities: selected
                                ? agentForm.capabilities.filter((item) => item !== capability.id)
                                : [...agentForm.capabilities, capability.id],
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
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={closeAgentModal}
                className="px-4 py-2 text-surface-700 hover:bg-surface-100 rounded-lg transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleUpdateAgent}
                className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Team Modal */}
      {modalType === 'create-team' && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-3xl mx-4">
            <h3 className="text-lg font-semibold text-surface-900 mb-4">创建新团队</h3>
            <div className="space-y-4 max-h-[70vh] overflow-y-auto">
              <div>
                <label className="block text-sm font-medium text-surface-700 mb-1">ID</label>
                <input
                  type="text"
                  value={teamForm.id}
                  onChange={(e) => setTeamForm({ ...teamForm, id: e.target.value })}
                  className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 ${
                    createTeamIdError ? 'border-red-300 bg-red-50/40' : 'border-surface-300'
                  }`}
                  placeholder="team-id"
                  aria-invalid={Boolean(createTeamIdError)}
                />
                {createTeamIdError && (
                  <p className="mt-1 text-xs text-red-600">{createTeamIdError}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-700 mb-1">名称</label>
                <input
                  type="text"
                  value={teamForm.name}
                  onChange={(e) => setTeamForm({ ...teamForm, name: e.target.value })}
                  className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 ${
                    createTeamNameError ? 'border-red-300 bg-red-50/40' : 'border-surface-300'
                  }`}
                  placeholder="团队名称"
                  aria-invalid={Boolean(createTeamNameError)}
                />
                {createTeamNameError && (
                  <p className="mt-1 text-xs text-red-600">{createTeamNameError}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-700 mb-1">描述</label>
                <input
                  type="text"
                  value={teamForm.description}
                  onChange={(e) => setTeamForm({ ...teamForm, description: e.target.value })}
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
                        checked={teamForm.members.includes(agent.id)}
                        onChange={(e) => toggleTeamMemberSelection(agent.id, e.target.checked)}
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
                    onClick={() => setTeamAdvancedOpen((current) => !current)}
                    data-testid="team-advanced-toggle"
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-surface-300 bg-white px-3 py-2 text-sm font-medium text-surface-700 transition-colors hover:border-primary-300 hover:text-primary-700"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className={`h-4 w-4 transition-transform ${teamAdvancedOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                    {teamAdvancedOpen ? '收起高级设置' : '展开高级设置'}
                  </button>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {teamAdvancedSummaryItems.map((item) => (
                    <span key={item} className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-surface-600 ring-1 ring-surface-200">
                      {item}
                    </span>
                  ))}
                </div>
              </div>
              {teamAdvancedOpen && (
                <div className="space-y-4" data-testid="team-advanced-panel">
                  <div className="border-t border-surface-200 pt-4">
                    <label className="block text-sm font-medium text-surface-700 mb-1">自定义工作空间</label>
                    <input
                      type="text"
                      value={teamForm.workspace}
                      onChange={(e) => setTeamForm({ ...teamForm, workspace: e.target.value })}
                      className="w-full px-3 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      placeholder="留空使用默认团队目录"
                    />
                    <p className="mt-1 text-xs text-surface-500">填写后该目录会成为团队共享工作区，协作元数据写入其中隐藏目录。</p>
                  </div>
                  {teamForm.members.length > 0 && (
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
                              onClick={applyRecommendedTeamSetup}
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
                              onChange={(e) => {
                                setTeamRecommendationAutoApply(false);
                                setSelectedTeamTemplateId(e.target.value as TeamTemplateId);
                              }}
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
                              onClick={() => applyTeamTemplate(selectedTeamTemplateId)}
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
                  {teamForm.members.length > 0 && (
                    <div className="border-t border-surface-200 pt-4">
                      <label className="block text-sm font-medium text-surface-700 mb-2">团队分工</label>
                      <div className="mb-3 rounded-2xl border border-surface-200 bg-white px-4 py-3 text-xs text-surface-600">
                        {teamAssignmentGuide}
                      </div>
                      <div className="space-y-3">
                        {teamForm.members.map((agentId) => {
                          const agent = getAgentById(agentId);
                          const profile = teamForm.member_profiles[agentId] || { role: 'member', responsibility: '', priority: 100, isLead: false };
                          return (
                            <div key={agentId} className="rounded-xl border border-surface-200 p-3">
                              <div className="flex items-center justify-between gap-3">
                                <div className="font-medium text-surface-900">{agent?.name || agentId}</div>
                                <label className="flex items-center gap-2 text-xs text-surface-600">
                                  <input
                                    type="radio"
                                    name="team-create-lead"
                                    checked={Boolean(profile.isLead)}
                                    onChange={() => {
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
                                  />
                                  负责人
                                </label>
                              </div>
                              <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
                                <label className="block">
                                  <span className="mb-1 block text-xs font-medium text-surface-600">角色</span>
                                  <select
                                    value={profile.role || 'member'}
                                    onChange={(e) => upsertTeamMemberProfile(agentId, { role: e.target.value })}
                                    className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm"
                                  >
                                    {TEAM_ROLE_OPTIONS.map((option) => (
                                      <option key={option.id} value={option.id}>
                                        {option.label}
                                      </option>
                                    ))}
                                  </select>
                                  <p className="mt-1 text-[11px] text-surface-400">
                                    {getTeamRoleMeta(profile.role).description}
                                  </p>
                                </label>
                                <label className="block">
                                  <span className="mb-1 block text-xs font-medium text-surface-600">接力顺序</span>
                                  <select
                                    value={profile.priority ?? 100}
                                    onChange={(e) => upsertTeamMemberProfile(agentId, { priority: Number(e.target.value) || 100 })}
                                    className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm"
                                  >
                                    {TEAM_PRIORITY_OPTIONS.map((option) => (
                                      <option key={option.value} value={option.value}>
                                        {option.label}
                                      </option>
                                    ))}
                                  </select>
                                  <p className="mt-1 text-[11px] text-surface-400">
                                    {getTeamPriorityMeta(profile.priority).description}
                                  </p>
                                </label>
                                <label className="block">
                                  <span className="mb-1 block text-xs font-medium text-surface-600">负责内容</span>
                                  <input
                                    type="text"
                                    value={profile.responsibility || ''}
                                    onChange={(e) => upsertTeamMemberProfile(agentId, { responsibility: e.target.value })}
                                    className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm"
                                    placeholder="例如：负责需求拆解和接力安排"
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
                onClick={closeTeamModal}
                className="px-4 py-2 text-surface-700 hover:bg-surface-100 rounded-lg transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleCreateTeam}
                disabled={createTeamSubmitDisabled}
                className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors disabled:cursor-not-allowed disabled:bg-surface-300"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}

      {modalType === 'edit-team' && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-3xl mx-4">
            <h3 className="text-lg font-semibold text-surface-900 mb-4">编辑团队</h3>
            <div className="space-y-4 max-h-[70vh] overflow-y-auto">
              <div>
                <label className="block text-sm font-medium text-surface-700 mb-1">ID</label>
                <input
                  type="text"
                  value={teamForm.id}
                  disabled
                  className="w-full px-3 py-2 border border-surface-300 rounded-lg bg-surface-50 text-surface-500 cursor-not-allowed"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-700 mb-1">名称</label>
                <input
                  type="text"
                  value={teamForm.name}
                  onChange={(e) => setTeamForm({ ...teamForm, name: e.target.value })}
                  className="w-full px-3 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-700 mb-1">描述</label>
                <input
                  type="text"
                  value={teamForm.description}
                  onChange={(e) => setTeamForm({ ...teamForm, description: e.target.value })}
                  className="w-full px-3 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-700 mb-1">成员 (选择 Agent)</label>
                <div className="max-h-40 overflow-y-auto border border-surface-300 rounded-lg p-2">
                  {agents.map((agent) => (
                    <label key={agent.id} className="flex items-center gap-2 p-1 hover:bg-surface-50 rounded cursor-pointer">
                      <input
                        type="checkbox"
                        checked={teamForm.members.includes(agent.id)}
                        onChange={(e) => toggleTeamMemberSelection(agent.id, e.target.checked)}
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
                    onClick={() => setTeamAdvancedOpen((current) => !current)}
                    data-testid="team-advanced-toggle"
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-surface-300 bg-white px-3 py-2 text-sm font-medium text-surface-700 transition-colors hover:border-primary-300 hover:text-primary-700"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className={`h-4 w-4 transition-transform ${teamAdvancedOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                    {teamAdvancedOpen ? '收起高级设置' : '展开高级设置'}
                  </button>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {teamAdvancedSummaryItems.map((item) => (
                    <span key={item} className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-surface-600 ring-1 ring-surface-200">
                      {item}
                    </span>
                  ))}
                </div>
              </div>
              {teamAdvancedOpen && (
                <div className="space-y-4" data-testid="team-advanced-panel">
                  <div className="border-t border-surface-200 pt-4">
                    <label className="block text-sm font-medium text-surface-700 mb-1">自定义工作空间</label>
                    <input
                      type="text"
                      value={teamForm.workspace}
                      onChange={(e) => setTeamForm({ ...teamForm, workspace: e.target.value })}
                      className="w-full px-3 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      placeholder="留空使用默认团队目录"
                    />
                  </div>
                  {teamForm.members.length > 0 && (
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
                              onClick={applyRecommendedTeamSetup}
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
                              onChange={(e) => {
                                setTeamRecommendationAutoApply(false);
                                setSelectedTeamTemplateId(e.target.value as TeamTemplateId);
                              }}
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
                              onClick={() => applyTeamTemplate(selectedTeamTemplateId)}
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
                  {teamForm.members.length > 0 && (
                    <div className="border-t border-surface-200 pt-4">
                      <label className="block text-sm font-medium text-surface-700 mb-2">团队分工</label>
                      <div className="mb-3 rounded-2xl border border-surface-200 bg-white px-4 py-3 text-xs text-surface-600">
                        {teamAssignmentGuide}
                      </div>
                      <div className="space-y-3">
                        {teamForm.members.map((agentId) => {
                          const agent = getAgentById(agentId);
                          const profile = teamForm.member_profiles[agentId] || { role: 'member', responsibility: '', priority: 100, isLead: false };
                          return (
                            <div key={agentId} className="rounded-xl border border-surface-200 p-3">
                              <div className="flex items-center justify-between gap-3">
                                <div className="font-medium text-surface-900">{agent?.name || agentId}</div>
                                <label className="flex items-center gap-2 text-xs text-surface-600">
                                  <input
                                    type="radio"
                                    name="team-edit-lead"
                                    checked={Boolean(profile.isLead)}
                                    onChange={() => {
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
                                  />
                                  负责人
                                </label>
                              </div>
                              <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
                                <label className="block">
                                  <span className="mb-1 block text-xs font-medium text-surface-600">角色</span>
                                  <select
                                    value={profile.role || 'member'}
                                    onChange={(e) => upsertTeamMemberProfile(agentId, { role: e.target.value })}
                                    className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm"
                                  >
                                    {TEAM_ROLE_OPTIONS.map((option) => (
                                      <option key={option.id} value={option.id}>
                                        {option.label}
                                      </option>
                                    ))}
                                  </select>
                                  <p className="mt-1 text-[11px] text-surface-400">
                                    {getTeamRoleMeta(profile.role).description}
                                  </p>
                                </label>
                                <label className="block">
                                  <span className="mb-1 block text-xs font-medium text-surface-600">接力顺序</span>
                                  <select
                                    value={profile.priority ?? 100}
                                    onChange={(e) => upsertTeamMemberProfile(agentId, { priority: Number(e.target.value) || 100 })}
                                    className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm"
                                  >
                                    {TEAM_PRIORITY_OPTIONS.map((option) => (
                                      <option key={option.value} value={option.value}>
                                        {option.label}
                                      </option>
                                    ))}
                                  </select>
                                  <p className="mt-1 text-[11px] text-surface-400">
                                    {getTeamPriorityMeta(profile.priority).description}
                                  </p>
                                </label>
                                <label className="block">
                                  <span className="mb-1 block text-xs font-medium text-surface-600">负责内容</span>
                                  <input
                                    type="text"
                                    value={profile.responsibility || ''}
                                    onChange={(e) => upsertTeamMemberProfile(agentId, { responsibility: e.target.value })}
                                    className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm"
                                    placeholder="例如：负责结果验收和风险把关"
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
                onClick={closeTeamModal}
                className="px-4 py-2 text-surface-700 hover:bg-surface-100 rounded-lg transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleUpdateTeam}
                className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TeamsPage;
