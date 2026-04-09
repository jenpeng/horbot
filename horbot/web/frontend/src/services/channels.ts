import api from './api';
import type {
  ChannelConfig,
  ChannelEndpointPayload,
  ChannelEndpointEventsResponse,
  ChannelEndpointTestResponse,
  ChannelEndpointDraftTestResponse,
  ChannelEndpointsResponse,
  ChannelCatalogEntry,
  ChannelEndpointAgent,
} from '../types';

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const ensureArray = <T>(value: unknown): T[] => (Array.isArray(value) ? value as T[] : []);

const ensureNumber = (value: unknown): number => (typeof value === 'number' && Number.isFinite(value) ? value : 0);

const normalizeChannelEndpointsResponse = (value: unknown): ChannelEndpointsResponse => {
  if (!isRecord(value)) {
    throw new Error('通道接口返回格式异常');
  }

  const counts = isRecord(value.counts) ? value.counts : {};
  return {
    endpoints: ensureArray<ChannelEndpointsResponse['endpoints'][number]>(value.endpoints),
    catalog: ensureArray<ChannelCatalogEntry>(value.catalog),
    agents: ensureArray<ChannelEndpointAgent>(value.agents),
    counts: {
      total: ensureNumber(counts.total),
      enabled: ensureNumber(counts.enabled),
      ready: ensureNumber(counts.ready),
      incomplete: ensureNumber(counts.incomplete),
    },
  };
};

const channelsService = {
  getChannels: async (): Promise<Record<string, ChannelConfig>> => {
    const response = await api.get<Record<string, ChannelConfig>>('/api/channels');
    return response.data;
  },

  getChannel: async (name: string): Promise<ChannelConfig> => {
    const response = await api.get<ChannelConfig>(`/api/channels/${name}`);
    return response.data;
  },

  updateChannel: async (name: string, data: Partial<ChannelConfig>): Promise<ChannelConfig> => {
    const response = await api.patch<ChannelConfig>(`/api/channels/${name}`, data);
    return response.data;
  },

  getCatalog: async (): Promise<{ catalog: ChannelCatalogEntry[]; agents: ChannelEndpointAgent[] }> => {
    const response = await api.get<{ catalog: ChannelCatalogEntry[]; agents: ChannelEndpointAgent[] }>('/api/channels/catalog');
    return response.data;
  },

  getEndpoints: async (): Promise<ChannelEndpointsResponse> => {
    const response = await api.get<ChannelEndpointsResponse>('/api/channels/endpoints');
    return normalizeChannelEndpointsResponse(response.data);
  },

  createEndpoint: async (data: ChannelEndpointPayload): Promise<ChannelEndpointsResponse['endpoints'][number]> => {
    const response = await api.post<{ endpoint: ChannelEndpointsResponse['endpoints'][number] }>('/api/channels/endpoints', data);
    return response.data.endpoint;
  },

  updateEndpoint: async (endpointId: string, data: ChannelEndpointPayload): Promise<ChannelEndpointsResponse['endpoints'][number] | null> => {
    const response = await api.put<{ endpoint: ChannelEndpointsResponse['endpoints'][number] | null }>(`/api/channels/endpoints/${endpointId}`, data);
    return response.data.endpoint;
  },

  deleteEndpoint: async (endpointId: string): Promise<void> => {
    await api.delete(`/api/channels/endpoints/${endpointId}`);
  },

  getEndpointEvents: async (endpointId: string, limit = 20): Promise<ChannelEndpointEventsResponse> => {
    const response = await api.get<ChannelEndpointEventsResponse>(`/api/channels/endpoints/${endpointId}/events`, {
      params: { limit },
    });
    return response.data;
  },

  testEndpoint: async (endpointId: string): Promise<ChannelEndpointTestResponse> => {
    const response = await api.post<ChannelEndpointTestResponse>(`/api/channels/endpoints/${endpointId}/test`);
    return response.data;
  },

  testDraftEndpoint: async (data: ChannelEndpointPayload): Promise<ChannelEndpointDraftTestResponse> => {
    const response = await api.post<ChannelEndpointDraftTestResponse>('/api/channels/draft-test', data);
    return response.data;
  },
};

export default channelsService;
