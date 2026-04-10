export type TeamTemplateId = 'delivery' | 'research' | 'support' | 'custom';

export const AGENT_CAPABILITY_OPTIONS = [
  { id: 'planning', label: '规划', description: '复杂任务拆解与流程设计' },
  { id: 'research', label: '研究', description: '信息检索、资料梳理与分析' },
  { id: 'code', label: '编码', description: '实现功能、改代码与修复问题' },
  { id: 'testing', label: '测试', description: '回归验证、端到端与质量检查' },
  { id: 'writing', label: '写作', description: '文档、方案与内容产出' },
  { id: 'review', label: '评审', description: '代码审查与风险识别' },
  { id: 'data', label: '数据', description: '数据整理、统计与结构化处理' },
  { id: 'vision', label: '视觉', description: '图像理解、界面分析与视觉任务' },
] as const;

export const MEMORY_REASONING_STYLE_OPTIONS = [
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

export const TEAM_ROLE_OPTIONS = [
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

export const TEAM_PRIORITY_OPTIONS = [
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

export const TEAM_TEMPLATE_OPTIONS: Array<{
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

export const getTeamRoleMeta = (role?: string) => (
  TEAM_ROLE_OPTIONS.find((item) => item.id === (role || 'member'))
  || { id: role || 'member', label: role || '普通成员', description: '自定义角色' }
);

export const getTeamPriorityMeta = (priority?: number) => (
  TEAM_PRIORITY_OPTIONS.find((item) => item.value === (priority ?? 100))
  || { value: priority ?? 100, label: `顺序 ${priority ?? 100}`, description: '自定义接力顺序' }
);
