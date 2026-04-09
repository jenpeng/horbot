import api from './api';
import type { TokenUsageStats, TokenUsageRecord } from '../types';

export interface TokenStatsParams {
  start_date?: string;
  end_date?: string;
  provider?: string;
  model?: string;
}

export interface TokenUsageParams {
  start_date?: string;
  end_date?: string;
  provider?: string;
  model?: string;
  session_id?: string;
  page?: number;
  page_size?: number;
}

const tokensService = {
  getStats: async (params?: TokenStatsParams): Promise<TokenUsageStats> => {
    const response = await api.get<TokenUsageStats>('/api/token-usage/stats', { params });
    return response.data;
  },

  getUsage: async (params?: TokenUsageParams): Promise<TokenUsageRecord[]> => {
    const response = await api.get<TokenUsageRecord[]>('/api/token-usage', { params });
    return response.data;
  },
};

export default tokensService;
