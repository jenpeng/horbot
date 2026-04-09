import api from './api';
import type { Config, ProviderConfig, ModelConfig, ModelsConfig, WebSearchProvider } from '../types';

export interface AddProviderData {
  apiKey?: string;
  apiBase?: string;
  extraHeaders?: Record<string, string>;
}

export interface UpdateProviderData {
  apiKey?: string;
  clearApiKey?: boolean;
  apiBase?: string;
  extraHeaders?: Record<string, string>;
}

export interface UpdateConfigResponse {
  status: string;
  message: string;
  path: string;
}

export interface AgentDefaultsUpdateData {
  workspace?: string;
  maxTokens?: number;
  temperature?: number;
  models?: ModelsConfig;
}

export interface AgentRecord {
  id: string;
  name: string;
  description: string;
  model: string;
  provider: string;
  model_override?: string;
  provider_override?: string;
  is_main: boolean;
  workspace?: string;
  effective_workspace?: string;
}

export interface WebSearchUpdateData {
  provider?: string;
  apiKey?: string;
  maxResults?: number;
}
export type ModelScenario = 'main' | 'planning' | 'file' | 'image' | 'audio' | 'video';

const configService = {
  getConfig: async (): Promise<Config> => {
    const response = await api.get<Config>('/api/config');
    return response.data;
  },

  getAgents: async (): Promise<AgentRecord[]> => {
    const response = await api.get<{ agents: AgentRecord[] }>('/api/agents');
    return response.data?.agents || [];
  },

  updateConfig: async (data: Partial<Config>): Promise<UpdateConfigResponse> => {
    const response = await api.put<UpdateConfigResponse>('/api/config', data);
    return response.data;
  },

  updateAgentDefaults: async (data: AgentDefaultsUpdateData): Promise<UpdateConfigResponse> => {
    const response = await api.patch<UpdateConfigResponse>('/api/config/agent-defaults', data);
    return response.data;
  },

  updateWebSearchConfig: async (data: WebSearchUpdateData): Promise<UpdateConfigResponse> => {
    const response = await api.patch<UpdateConfigResponse>('/api/config/web-search', data);
    return response.data;
  },

  getProviders: async (): Promise<Record<string, ProviderConfig>> => {
    const config = await configService.getConfig();
    return config.providers || {};
  },

  addProvider: async (name: string, data: AddProviderData): Promise<void> => {
    await api.post('/api/config/providers', {
      name,
      apiKey: data.apiKey,
      apiBase: data.apiBase,
      extraHeaders: data.extraHeaders,
    });
  },

  updateProvider: async (name: string, data: UpdateProviderData): Promise<void> => {
    await api.put(`/api/config/providers/${name}`, {
      apiKey: data.apiKey,
      clearApiKey: data.clearApiKey,
      apiBase: data.apiBase,
      extraHeaders: data.extraHeaders,
    });
  },

  deleteProvider: async (name: string): Promise<void> => {
    await api.delete(`/api/config/providers/${name}`);
  },

  updateModelConfig: async (scenario: ModelScenario, modelConfig: ModelConfig): Promise<UpdateConfigResponse> => {
    const response = await api.put<UpdateConfigResponse>(`/api/config/models/${scenario}`, modelConfig);
    return response.data;
  },

  getWebSearchProviders: async (): Promise<WebSearchProvider[]> => {
    try {
      const response = await api.get<{ providers: WebSearchProvider[] }>('/api/web-search-providers');
      return response.data?.providers || [];
    } catch (error) {
      console.error('Failed to fetch web search providers:', error);
      return [];
    }
  },
};

export default configService;
