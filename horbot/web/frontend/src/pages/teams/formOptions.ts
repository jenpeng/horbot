type TranslateFn = (key: string, values?: Record<string, number | string>) => string;

export type TeamTemplateId = 'delivery' | 'research' | 'support' | 'custom';

export interface AgentCapabilityOption {
  id: string;
  label: string;
  description: string;
}

export interface MemoryReasoningStyleOption {
  id: string;
  label: string;
  description: string;
}

export interface TeamRoleOption {
  id: string;
  label: string;
  description: string;
}

export interface TeamPriorityOption {
  value: number;
  label: string;
  description: string;
}

export interface TeamTemplateOption {
  id: TeamTemplateId;
  label: string;
  description: string;
  assignments: string[];
}

const AGENT_CAPABILITY_IDS = [
  'planning',
  'research',
  'code',
  'testing',
  'writing',
  'review',
  'data',
  'vision',
] as const;

const MEMORY_REASONING_STYLE_IDS = [
  'balanced',
  'structured',
  'exploratory',
  'strict',
] as const;

const TEAM_ROLE_IDS = [
  'member',
  'coordinator',
  'builder',
  'reviewer',
  'researcher',
  'support',
] as const;

const TEAM_PRIORITY_ENTRIES = [
  { value: 10, key: 'first' },
  { value: 50, key: 'early' },
  { value: 100, key: 'default' },
  { value: 200, key: 'late' },
] as const;

const TEAM_TEMPLATE_IDS = [
  'delivery',
  'research',
  'support',
  'custom',
] as const satisfies readonly TeamTemplateId[];

export const getAgentCapabilityOptions = (t: TranslateFn): AgentCapabilityOption[] => (
  AGENT_CAPABILITY_IDS.map((id) => ({
    id,
    label: t(`teams.capability.${id}.label`),
    description: t(`teams.capability.${id}.description`),
  }))
);

export const getMemoryReasoningStyleOptions = (t: TranslateFn): MemoryReasoningStyleOption[] => (
  MEMORY_REASONING_STYLE_IDS.map((id) => ({
    id,
    label: t(`teams.memoryReasoning.${id}.label`),
    description: t(`teams.memoryReasoning.${id}.description`),
  }))
);

export const getTeamRoleOptions = (t: TranslateFn): TeamRoleOption[] => (
  TEAM_ROLE_IDS.map((id) => ({
    id,
    label: t(`teams.teamRole.${id}.label`),
    description: t(`teams.teamRole.${id}.description`),
  }))
);

export const getTeamPriorityOptions = (t: TranslateFn): TeamPriorityOption[] => (
  TEAM_PRIORITY_ENTRIES.map((entry) => ({
    value: entry.value,
    label: t(`teams.teamPriority.${entry.key}.label`),
    description: t(`teams.teamPriority.${entry.key}.description`),
  }))
);

export const getTeamTemplateOptions = (t: TranslateFn): TeamTemplateOption[] => (
  TEAM_TEMPLATE_IDS.map((id) => {
    const assignments = id === 'custom'
      ? [t('teams.teamTemplate.custom.assignment1')]
      : [1, 2, 3].map((index) => t(`teams.teamTemplate.${id}.assignment${index}`));
    return {
      id,
      label: t(`teams.teamTemplate.${id}.label`),
      description: t(`teams.teamTemplate.${id}.description`),
      assignments,
    };
  })
);

export const getTeamRoleMeta = (t: TranslateFn, role?: string): TeamRoleOption => (
  getTeamRoleOptions(t).find((item) => item.id === (role || 'member'))
  || {
    id: role || 'member',
    label: role || 'member',
    description: t('teams.teamRole.customDescription'),
  }
);

export const getTeamPriorityMeta = (t: TranslateFn, priority?: number): TeamPriorityOption => (
  getTeamPriorityOptions(t).find((item) => item.value === (priority ?? 100))
  || {
    value: priority ?? 100,
    label: t('teams.teamPriority.customLabel', { value: priority ?? 100 }),
    description: t('teams.teamPriority.customDescription'),
  }
);
