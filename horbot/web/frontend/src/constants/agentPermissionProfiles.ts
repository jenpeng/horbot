type TranslateFn = (key: string, values?: Record<string, number | string>) => string;

export interface AgentPermissionPreset {
  id: string;
  label: string;
  summary: string;
  detail: string;
  accent: string;
}

interface AgentPermissionPresetBase {
  id: string;
  accent: string;
}

const AGENT_PERMISSION_PRESET_BASES: AgentPermissionPresetBase[] = [
  {
    id: 'inherit',
    accent: 'border-slate-200 bg-slate-50 text-slate-700',
  },
  {
    id: 'minimal',
    accent: 'border-amber-200 bg-amber-50 text-amber-700',
  },
  {
    id: 'balanced',
    accent: 'border-sky-200 bg-sky-50 text-sky-700',
  },
  {
    id: 'coding',
    accent: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  },
  {
    id: 'readonly',
    accent: 'border-violet-200 bg-violet-50 text-violet-700',
  },
  {
    id: 'full',
    accent: 'border-rose-200 bg-rose-50 text-rose-700',
  },
];

const buildAgentPermissionPreset = (
  t: TranslateFn,
  preset: AgentPermissionPresetBase,
): AgentPermissionPreset => {
  const keyPrefix = `teams.permissionProfile.${preset.id}`;
  return {
    ...preset,
    label: t(`${keyPrefix}.label`),
    summary: t(`${keyPrefix}.summary`),
    detail: t(`${keyPrefix}.detail`),
  };
};

export const getAgentPermissionPresets = (t: TranslateFn): AgentPermissionPreset[] => (
  AGENT_PERMISSION_PRESET_BASES.map((preset) => buildAgentPermissionPreset(t, preset))
);

export const getAgentPermissionPreset = (
  t: TranslateFn,
  permissionProfile?: string,
): AgentPermissionPreset | undefined => {
  const preset = AGENT_PERMISSION_PRESET_BASES.find((item) => item.id === permissionProfile);
  return preset ? buildAgentPermissionPreset(t, preset) : undefined;
};
