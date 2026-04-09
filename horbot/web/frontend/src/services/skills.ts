import api from './api';
import type { Skill, SkillDetail, MCPServerConfig, SkillImportResult } from '../types';

interface SkillsListResponse {
  skills: Skill[];
}

interface MCPServerResponse {
  name: string;
  command?: string;
  args?: string[];
  url?: string;
  env?: Record<string, string>;
  tool_timeout?: number;
  headers?: Record<string, string>;
  has_secret_values?: boolean;
}

interface MCPServersListResponse {
  servers: MCPServerResponse[];
}

interface CreateSkillRequest {
  name: string;
  content: string;
}

interface UpdateSkillRequest {
  content: string;
}

interface ToggleSkillResponse {
  enabled: boolean;
}


export const skillsService = {
  getSkills: async (): Promise<Skill[]> => {
    const response = await api.get<SkillsListResponse>('/api/skills');
    return response.data.skills || [];
  },

  getSkill: async (name: string): Promise<SkillDetail> => {
    const response = await api.get<SkillDetail>(`/api/skills/${name}`);
    return response.data;
  },

  createSkill: async (data: CreateSkillRequest): Promise<void> => {
    await api.post('/api/skills', data);
  },

  updateSkill: async (name: string, data: UpdateSkillRequest): Promise<void> => {
    await api.put(`/api/skills/${name}`, data);
  },

  deleteSkill: async (name: string): Promise<void> => {
    await api.delete(`/api/skills/${name}`);
  },

  toggleSkill: async (name: string): Promise<boolean> => {
    const response = await api.patch<ToggleSkillResponse>(`/api/skills/${name}/toggle`);
    return response.data.enabled;
  },

  importSkill: async (file: File, replaceExisting = false): Promise<SkillImportResult> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('replace_existing', String(replaceExisting));
    const response = await api.post<SkillImportResult>('/api/skills/import', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  getMcpServers: async (): Promise<Record<string, MCPServerConfig>> => {
    const response = await api.get<MCPServersListResponse>('/api/mcp-servers');
    const servers = response.data.servers || [];
    const result: Record<string, MCPServerConfig> = {};
    for (const server of servers) {
      result[server.name] = {
        command: server.command,
        args: server.args,
        url: server.url,
        env: server.env,
        tool_timeout: server.tool_timeout,
        headers: server.headers,
        has_secret_values: server.has_secret_values,
      };
    }
    return result;
  },

  addMcpServer: async (name: string, config: MCPServerConfig): Promise<void> => {
    await api.post('/api/mcp-servers', { name, ...config });
  },

  updateMcpServer: async (name: string, config: MCPServerConfig): Promise<void> => {
    await api.put(`/api/mcp-servers/${name}`, config);
  },

  deleteMcpServer: async (name: string): Promise<void> => {
    await api.delete(`/api/mcp-servers/${name}`);
  },
};

export default skillsService;
