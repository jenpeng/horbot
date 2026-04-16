import type { ModelsConfig, WebSearchProvider } from '../../types';

export type ModelScenarioKey = keyof ModelsConfig;

export const DEFAULT_MODELS_CONFIG: ModelsConfig = {
  main: { provider: 'openrouter', model: 'anthropic/claude-sonnet-4-20250514', description: '主模型 - 通用对话', capabilities: [] },
  planning: { provider: 'openrouter', model: 'anthropic/claude-sonnet-4-20250514', description: '计划模型 - 复杂任务规划', capabilities: [] },
  file: { provider: 'openrouter', model: 'anthropic/claude-sonnet-4-20250514', description: '文件处理模型', capabilities: [] },
  image: { provider: 'openrouter', model: 'anthropic/claude-sonnet-4-20250514', description: '图片处理模型', capabilities: ['vision'] },
  audio: { provider: 'openrouter', model: 'anthropic/claude-sonnet-4-20250514', description: '音频处理模型', capabilities: ['audio'] },
  video: { provider: 'openrouter', model: 'anthropic/claude-sonnet-4-20250514', description: '视频处理模型', capabilities: ['vision'] },
};

export const MODEL_SCENARIOS: { key: ModelScenarioKey; label: string; icon: string; description: string }[] = [
  { key: 'main', label: '主模型', icon: '⚡', description: '通用 AI 对话和简单任务处理' },
  { key: 'planning', label: '规划模型', icon: '📋', description: '复杂任务规划和任务拆解' },
  { key: 'file', label: '文件处理模型', icon: '📄', description: '上传文件后的解析与总结' },
  { key: 'image', label: '图片处理模型', icon: '🖼️', description: '图片理解、多模态识别与分析' },
  { key: 'audio', label: '音频处理模型', icon: '🎵', description: '音频理解、转写和分析' },
  { key: 'video', label: '视频处理模型', icon: '🎬', description: '视频帧理解和多模态分析' },
];

export const BUILTIN_PROVIDER_NAMES = [
  'minimax',
  'openai',
  'anthropic',
  'deepseek',
  'openrouter',
  'groq',
  'zhipu',
  'dashscope',
  'vllm',
  'gemini',
  'moonshot',
  'aihubmix',
  'siliconflow',
  'volcengine',
  'custom',
  'openaiCodex',
  'githubCopilot',
];

export const DEFAULT_WEB_SEARCH = {
  enabled: true,
  provider: 'duckduckgo',
  tavilyEnabled: true,
  langsearchEnabled: true,
  apiKey: '',
  maxResults: 5,
};

export const BUILTIN_WEB_SEARCH_PROVIDERS: WebSearchProvider[] = [
  {
    id: 'duckduckgo',
    name: 'DuckDuckGo',
    description: '免费搜索，无需 API key',
    requires_api_key: false,
  },
  {
    id: 'brave',
    name: 'Brave Search',
    description: 'Brave 搜索 API，需要 API key',
    requires_api_key: true,
    api_key_url: 'https://brave.com/search/api/',
  },
  {
    id: 'tavily',
    name: 'Tavily',
    description: 'AI 优化的搜索 API，可通过 Tavily 开关显式启用或关闭',
    requires_api_key: true,
    api_key_url: 'https://tavily.com/',
    enabled_config_key: 'tavilyEnabled' as const,
  },
  {
    id: 'langsearch',
    name: 'LangSearch',
    description: '免费 Web Search API，可通过 LangSearch 开关显式启用或关闭',
    requires_api_key: true,
    api_key_url: 'https://langsearch.com/',
    enabled_config_key: 'langsearchEnabled' as const,
  },
];

export const normalizeModelsConfig = (models?: Partial<ModelsConfig> | null): ModelsConfig => ({
  main: { ...DEFAULT_MODELS_CONFIG.main, ...(models?.main || {}) },
  planning: { ...DEFAULT_MODELS_CONFIG.planning, ...(models?.planning || {}) },
  file: { ...DEFAULT_MODELS_CONFIG.file, ...(models?.file || {}) },
  image: { ...DEFAULT_MODELS_CONFIG.image, ...(models?.image || {}) },
  audio: { ...DEFAULT_MODELS_CONFIG.audio, ...(models?.audio || {}) },
  video: { ...DEFAULT_MODELS_CONFIG.video, ...(models?.video || {}) },
});
