import api, { resolveApiBase } from './api';
import type { RenderableArtifactSpec } from '../types/conversation';

export interface LiveArtifactRenderResponse {
  artifact_id: string;
  title: string;
  template: string;
  render_url: string;
  expires_at: string;
  ttl_seconds: number;
}

const resolveRenderUrl = (value: string): string => {
  if (/^https?:\/\//i.test(value)) {
    return value;
  }
  const apiBase = resolveApiBase();
  if (!apiBase) {
    return value;
  }
  return `${apiBase}${value.startsWith('/') ? value : `/${value}`}`;
};

export const liveArtifactService = {
  render: async (
    spec: RenderableArtifactSpec,
    ttlSeconds: number = 1800,
  ): Promise<LiveArtifactRenderResponse> => {
    const response = await api.post<LiveArtifactRenderResponse>('/api/artifacts/render', {
      spec,
      ttl_seconds: ttlSeconds,
    });
    return {
      ...response.data,
      render_url: resolveRenderUrl(response.data.render_url),
    };
  },
};
