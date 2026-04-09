import api from './api';
import type { DashboardSummary, SystemStatus } from '../types';

export interface LogEntry {
  raw: string;
  timestamp?: string;
  level: string;
}

export interface LogsParams {
  lines?: number;
  level?: string;
}

export interface LogsResponse {
  logs: LogEntry[];
}

export interface HealthResponse {
  status: string;
  timestamp?: string;
}

export interface ApiRequestEntry {
  timestamp: string;
  method: string;
  url: string;
  status_code: number;
  process_time_ms: number;
  client_ip: string;
}

export interface ApiMetricsResponse {
  recent_requests: ApiRequestEntry[];
  total_count: number;
  avg_process_time_ms: number;
  error_count: number;
}

export interface MemoryMetricsSummary {
  recall: {
    count: number;
    avg_latency_ms: number;
    max_latency_ms: number;
    avg_candidates_count: number;
    last_selected_memory_ids: string[];
    last_samples: Array<{
      timestamp: string;
      latency_ms: number;
      candidates_count: number;
      selected_count: number;
      query: string;
      selected_memory_ids: string[];
    }>;
  };
  consolidation: {
    count: number;
    success_count: number;
    failure_count: number;
    avg_latency_ms: number;
    max_latency_ms: number;
    last_latency_ms: number;
    last_status?: string | null;
    last_samples: Array<{
      timestamp: string;
      latency_ms: number;
      success: boolean;
      session_key: string;
      messages_processed: number;
    }>;
  };
  growth: {
    current_entries: number;
    current_size_bytes: number;
    history: Array<{
      timestamp: string;
      entries: number;
      size_bytes: number;
    }>;
    last_delta_entries: number;
    last_delta_bytes: number;
  };
}

export interface MemoryStatsResponse {
  agent_id?: string | null;
  total_entries: number;
  total_size_kb: number;
  oldest_entry?: string | null;
  newest_entry?: string | null;
  details: {
    metrics?: MemoryMetricsSummary;
    [key: string]: unknown;
  };
}

const statusService = {
  getStatus: async (): Promise<SystemStatus> => {
    const response = await api.get<SystemStatus>('/api/status');
    return response.data;
  },

  getDashboardSummary: async (): Promise<DashboardSummary> => {
    const response = await api.get<DashboardSummary>('/api/dashboard/summary');
    return response.data;
  },

  getLogs: async (params?: LogsParams): Promise<LogsResponse> => {
    const response = await api.get<LogsResponse>('/api/logs', { params });
    return response.data;
  },

  getApiMetrics: async (lines: number = 100): Promise<ApiMetricsResponse> => {
    const response = await api.get<ApiMetricsResponse>('/api/api-metrics', { params: { lines } });
    return response.data;
  },

  getMemoryStats: async (agentId?: string): Promise<MemoryStatsResponse> => {
    const response = await api.get<MemoryStatsResponse>('/api/memory', {
      params: agentId ? { agent_id: agentId } : undefined,
    });
    return response.data;
  },

  getHealth: async (): Promise<HealthResponse> => {
    const response = await api.get<HealthResponse>('/api/health');
    return response.data;
  },
};

export default statusService;
