type TranslateFn = (key: string, values?: Record<string, number | string>) => string;

export interface AgentProfilePreset {
  id: string;
  label: string;
  summary: string;
  detail: string;
  suggestedCapabilities: string[];
  accent: string;
  placeholderHint: string;
  onboardingChecklist: string[];
  starterPrompts: string[];
}

interface AgentProfilePresetBase {
  id: string;
  suggestedCapabilities: string[];
  accent: string;
}

const AGENT_PROFILE_PRESET_BASES: AgentProfilePresetBase[] = [
  {
    id: 'generalist',
    suggestedCapabilities: ['planning', 'research', 'writing'],
    accent: 'border-sky-200 bg-sky-50 text-sky-700',
  },
  {
    id: 'builder',
    suggestedCapabilities: ['code', 'testing', 'review'],
    accent: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  },
  {
    id: 'researcher',
    suggestedCapabilities: ['research', 'writing', 'data'],
    accent: 'border-amber-200 bg-amber-50 text-amber-700',
  },
  {
    id: 'coordinator',
    suggestedCapabilities: ['planning', 'review', 'writing'],
    accent: 'border-violet-200 bg-violet-50 text-violet-700',
  },
  {
    id: 'companion',
    suggestedCapabilities: ['writing', 'research'],
    accent: 'border-rose-200 bg-rose-50 text-rose-700',
  },
];

const buildAgentProfilePreset = (
  t: TranslateFn,
  preset: AgentProfilePresetBase,
): AgentProfilePreset => {
  const keyPrefix = `teams.agentProfile.${preset.id}`;
  return {
    ...preset,
    label: t(`${keyPrefix}.label`),
    summary: t(`${keyPrefix}.summary`),
    detail: t(`${keyPrefix}.detail`),
    placeholderHint: t(`${keyPrefix}.placeholderHint`),
    onboardingChecklist: [1, 2, 3, 4].map((index) => t(`${keyPrefix}.checklist${index}`)),
    starterPrompts: [1, 2, 3].map((index) => t(`${keyPrefix}.starter${index}`)),
  };
};

export const getAgentProfilePresets = (t: TranslateFn): AgentProfilePreset[] => (
  AGENT_PROFILE_PRESET_BASES.map((preset) => buildAgentProfilePreset(t, preset))
);

export const getAgentProfilePreset = (
  t: TranslateFn,
  profileId?: string,
): AgentProfilePreset | undefined => {
  const preset = AGENT_PROFILE_PRESET_BASES.find((item) => item.id === profileId);
  return preset ? buildAgentProfilePreset(t, preset) : undefined;
};
