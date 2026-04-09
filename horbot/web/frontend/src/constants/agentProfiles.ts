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

export const AGENT_PROFILE_PRESETS: AgentProfilePreset[] = [
  {
    id: 'generalist',
    label: '通用执行者',
    summary: '适合日常问答、配置确认与稳定执行',
    detail: '偏稳健，适合作为默认单聊 Agent，强调响应速度和交付确定性。',
    suggestedCapabilities: ['planning', 'research', 'writing'],
    accent: 'border-sky-200 bg-sky-50 text-sky-700',
    placeholderHint: '先和它约定职责、风格，或直接交代一个明确任务',
    onboardingChecklist: [
      '你主要负责什么类型的任务',
      '默认输出结构和结论风格是什么',
      '遇到不确定信息时，先澄清还是先给方案',
      '哪些边界内不要擅自决策',
    ],
    starterPrompts: [
      '先介绍一下你之后会负责的核心任务、默认输出风格，以及你最适合处理的问题类型。',
      '请先和我约定：你收到任务后默认怎么确认目标、怎么组织答案、怎么暴露不确定性。',
      '请整理你的协作边界：你会主动做什么、不会擅自做什么、需要我额外确认什么。',
    ],
  },
  {
    id: 'builder',
    label: '工程实现者',
    summary: '偏开发与落地，适合改代码、修问题、跑验证',
    detail: '强调实现、调试、测试闭环，适合代码与工程自动化场景。',
    suggestedCapabilities: ['code', 'testing', 'review'],
    accent: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    placeholderHint: '描述一个代码问题、缺陷或待实现功能',
    onboardingChecklist: [
      '默认如何理解需求并拆解实现步骤',
      '改代码前会先确认哪些信息',
      '默认要不要附带验证与回归结果',
      '哪些高风险改动必须先和你确认',
    ],
    starterPrompts: [
      '请先把你的工程协作方式说清楚：接到任务后你会如何拆解、实现、验证，并在什么情况下主动停下来确认。',
      '以后我让你改代码时，请默认给出变更思路、风险点和验证结果；先把这套协作约定整理出来。',
      '请明确你在工程场景里的边界：哪些改动你会直接执行，哪些涉及风险时你必须先征求确认。',
    ],
  },
  {
    id: 'researcher',
    label: '研究分析者',
    summary: '偏检索、分析、梳理与总结',
    detail: '适合做资料搜集、对比分析、方案研究和结构化输出。',
    suggestedCapabilities: ['research', 'writing', 'data'],
    accent: 'border-amber-200 bg-amber-50 text-amber-700',
    placeholderHint: '抛一个研究主题、对比问题或方案评估任务',
    onboardingChecklist: [
      '默认研究输出采用什么结构',
      '结论、证据和假设如何区分',
      '做对比分析时重点关注什么维度',
      '什么时候需要先补充背景或范围',
    ],
    starterPrompts: [
      '请先说明你做研究分析时的默认输出结构，尤其是结论、证据、假设和待验证项怎么区分。',
      '以后我让你做方案对比时，请默认按维度对比、列证据和不确定性；先把这套规范说清楚。',
      '请总结你的研究协作边界：什么任务你适合直接分析，什么任务需要我先补上下文或判定标准。',
    ],
  },
  {
    id: 'coordinator',
    label: '协作协调者',
    summary: '偏任务拆解、团队协同与多 Agent 接力',
    detail: '适合负责分工、调度、推进状态和多 Agent 协作边界。',
    suggestedCapabilities: ['planning', 'review', 'writing'],
    accent: 'border-violet-200 bg-violet-50 text-violet-700',
    placeholderHint: '给它一个复杂目标，让它负责拆解分工与推进',
    onboardingChecklist: [
      '如何拆解任务并选择合适的下一棒',
      '接力时默认输出哪些状态信息',
      '何时需要停止接力并回到用户确认',
      '如何处理冲突意见与优先级变化',
    ],
    starterPrompts: [
      '请先定义你的协调规则：你会如何拆解任务、分配下一棒、同步状态，并在什么时候停止接力回到我这里确认。',
      '以后你作为协调型 Agent 时，请默认告诉我当前阶段、下一棒和剩余风险；先把这套工作方式说清楚。',
      '请整理你的团队协作边界：什么情况下你自己回答，什么情况下你应该拉起其他 Agent 接力。',
    ],
  },
  {
    id: 'companion',
    label: '陪伴助理',
    summary: '偏温和沟通、细致引导与长期陪伴',
    detail: '适合需要更柔和语气、更多引导感与解释感的使用场景。',
    suggestedCapabilities: ['writing', 'research'],
    accent: 'border-rose-200 bg-rose-50 text-rose-700',
    placeholderHint: '先约定沟通方式、解释深度和长期陪伴风格',
    onboardingChecklist: [
      '默认语气与解释深度是什么',
      '如何在不打断的前提下做温和引导',
      '遇到模糊需求时先问什么',
      '什么内容要尽量解释得更耐心、更具体',
    ],
    starterPrompts: [
      '请先和我约定你的沟通风格：语气、解释深度、引导方式，以及什么时候该更主动地追问我。',
      '以后你作为陪伴型 Agent 时，请默认更耐心地解释关键判断，同时避免过度打扰；先把这套原则整理出来。',
      '请明确你在长期陪伴场景里的边界：你会怎样帮助我整理目标、推进任务和维持上下文连续性。',
    ],
  },
];

export const getAgentProfilePreset = (profileId?: string): AgentProfilePreset | undefined => (
  AGENT_PROFILE_PRESETS.find((preset) => preset.id === profileId)
);
