export interface AgentPermissionPreset {
  id: string;
  label: string;
  summary: string;
  detail: string;
  accent: string;
}

export const AGENT_PERMISSION_PRESETS: AgentPermissionPreset[] = [
  {
    id: 'inherit',
    label: '继承全局',
    summary: '沿用系统默认权限档位',
    detail: '适合大多数 Agent。若没有特殊安全边界要求，建议保持继承。',
    accent: 'border-slate-200 bg-slate-50 text-slate-700',
  },
  {
    id: 'minimal',
    label: '最小权限',
    summary: '尽量少开权限，适合保守问答',
    detail: '默认不开放终端与自动化操作，适合信息整理或陪伴型场景。',
    accent: 'border-amber-200 bg-amber-50 text-amber-700',
  },
  {
    id: 'balanced',
    label: '平衡模式',
    summary: '文件和网页可用，终端更谨慎',
    detail: '适合大多数日常 Agent，在安全性和可执行性之间保持平衡。',
    accent: 'border-sky-200 bg-sky-50 text-sky-700',
  },
  {
    id: 'coding',
    label: '工程模式',
    summary: '适合编码、调试与本地验证',
    detail: '开放文件、网页和终端能力，适合工程实现型 Agent。',
    accent: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  },
  {
    id: 'readonly',
    label: '只读模式',
    summary: '允许读取和检索，不允许写入和执行',
    detail: '适合只做审阅、研究、问答，不直接修改环境的 Agent。',
    accent: 'border-violet-200 bg-violet-50 text-violet-700',
  },
  {
    id: 'full',
    label: '完全模式',
    summary: '全部工具默认可用',
    detail: '适合高自治 Agent，但要确保职责和风险边界已经明确。',
    accent: 'border-rose-200 bg-rose-50 text-rose-700',
  },
];

export const getAgentPermissionPreset = (permissionProfile?: string): AgentPermissionPreset | undefined => (
  AGENT_PERMISSION_PRESETS.find((preset) => preset.id === permissionProfile)
);
