import api from './api';
import type { ConfigCheckResultData } from '../components/ConfigCheckResult';
import type { GatewayDiagnosticsData } from '../components/GatewayDiagnosticsResult';
import type { EnvironmentDetectionData } from '../components/EnvironmentDetectionResult';

export interface MemoryData {
  total_entries: number;
  total_size_kb: number;
  oldest_entry: string | null;
  newest_entry: string | null;
  details: Record<string, unknown>;
}

export interface FixResult {
  fixed: Array<{ issue: string; message: string }>;
  failed: Array<{ issue: string; error: string }>;
  suggestions: Array<{ issue: string; message: string; action: string }>;
}

const diagnosticsService = {
  validateConfig: async (): Promise<ConfigCheckResultData> => {
    const response = await api.get<{
      valid: boolean;
      errors: Array<{ code: string; message: string; field_path?: string; suggestion?: string }>;
      warnings: Array<{ code: string; message: string; field_path?: string; suggestion?: string }>;
      infos: Array<{ code: string; message: string; field_path?: string; suggestion?: string }>;
    }>('/api/config/validate');
    const data = response.data;
    return {
      status: data.valid ? 'passed' : 'failed',
      errors: data.errors || [],
      warnings: data.warnings || [],
      info: data.infos || [],
    };
  },

  getGatewayDiagnostics: async (): Promise<GatewayDiagnosticsData> => {
    const response = await api.get<GatewayDiagnosticsData>('/api/gateway/diagnostics');
    return response.data;
  },

  getEnvironment: async (): Promise<EnvironmentDetectionData> => {
    const response = await api.get<{
      python_version: string;
      os_info: { name: string; version: string; platform: string };
      dependencies: Array<{ name: string; version: string }>;
      disk: { total_gb: number; used_gb: number; free_gb: number; usage_percent: number };
      memory: { total_gb: number; used_gb: number; available_gb: number; usage_percent: number };
      cpu: { count: number; percent: number };
      workspace: { path: string; exists: boolean; files_count: number };
    }>('/api/environment');
    const data = response.data;
    return {
      python_version: data.python_version,
      os_info: {
        system: data.os_info.name || 'Unknown',
        release: '',
        version: data.os_info.version || '',
        machine: data.os_info.platform || '',
      },
      dependencies: data.dependencies || [],
      resources: {
        disk: {
          used: data.disk?.used_gb || 0,
          total: data.disk?.total_gb || 0,
          percent: data.disk?.usage_percent || 0,
        },
        memory: {
          used: data.memory?.used_gb || 0,
          total: data.memory?.total_gb || 0,
          percent: data.memory?.usage_percent || 0,
        },
        cpu: data.cpu?.percent || 0,
      },
      workspace: {
        path: data.workspace?.path || '',
        exists: data.workspace?.exists || false,
        writable: true,
      },
    };
  },

  getMemory: async (): Promise<MemoryData> => {
    const response = await api.get<MemoryData>('/api/memory');
    return response.data;
  },

  runFix: async (): Promise<FixResult> => {
    const response = await api.post<FixResult>('/api/system/fix');
    return response.data;
  },
};

export default diagnosticsService;
