import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { I18nProvider } from '../contexts/I18nContext';
import { useConfigurationState } from './useConfigurationState';
import configService from '../services/config';
import diagnosticsService from '../services/diagnostics';

vi.mock('../services/config', () => ({
  default: {
    getConfig: vi.fn(),
    getAgents: vi.fn(),
    getWebSearchProviders: vi.fn(),
    getRemoteImageCacheStatus: vi.fn(),
    updateAgentDefaults: vi.fn(),
    updateWebSearchConfig: vi.fn(),
    clearRemoteImageCache: vi.fn(),
    updateModelConfig: vi.fn(),
  },
}));

vi.mock('../services/diagnostics', () => ({
  default: {
    validateConfig: vi.fn(),
  },
}));

const wrapper = ({ children }: { children: ReactNode }) => (
  <I18nProvider>{children}</I18nProvider>
);

describe('useConfigurationState', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(configService.getConfig).mockResolvedValue({
      agents: {
        defaults: {
          workspace: '.horbot/agents/main/workspace',
          maxTokens: 8192,
          temperature: 0.7,
          models: {
            main: { provider: 'openai', model: 'gpt-5.4', description: '', capabilities: [] },
            planning: { provider: 'openai', model: 'gpt-5.4', description: '', capabilities: [] },
            file: { provider: 'openai', model: 'gpt-5.4', description: '', capabilities: [] },
            image: { provider: 'openai', model: 'gpt-5.4', description: '', capabilities: ['vision'] },
            audio: { provider: 'openai', model: 'gpt-5.4', description: '', capabilities: ['audio'] },
            video: { provider: 'openai', model: 'gpt-5.4', description: '', capabilities: ['vision'] },
          },
        },
      },
      teams: { instances: {} },
      channels: {},
      providers: {},
      gateway: {
        host: '127.0.0.1',
        port: 18790,
        heartbeat: { enabled: true, intervalS: 1800 },
      },
      tools: {
        web: {
          search: {
            enabled: false,
            provider: 'langsearch',
            tavilyEnabled: true,
            langsearchEnabled: true,
            hasApiKey: true,
            apiKeyMasked: 'ls-s...cret',
            providerApiKeyStatus: {
              langsearch: {
                hasApiKey: true,
                apiKeyMasked: 'ls-s...cret',
              },
            },
            maxResults: 7,
          },
        },
      },
      autonomous: {
        enabled: false,
        maxPlanSteps: 10,
        stepTimeout: 300,
        totalTimeout: 3600,
        retryCount: 3,
        retryDelay: 5,
        confirmSensitive: true,
        sensitiveOperations: [],
        protectedPaths: [],
      },
    } as any);
    vi.mocked(configService.getAgents).mockResolvedValue([]);
    vi.mocked(configService.getWebSearchProviders).mockResolvedValue([
      {
        id: 'duckduckgo',
        name: 'DuckDuckGo',
        description: 'free',
        requires_api_key: false,
      },
      {
        id: 'tavily',
        name: 'Tavily',
        description: 'tavily',
        requires_api_key: true,
        enabled_config_key: 'tavilyEnabled',
      },
    ]);
    vi.mocked(configService.getRemoteImageCacheStatus).mockResolvedValue({
      count: 0,
      total_size_bytes: 0,
      newest_updated_at: null,
    });
    vi.mocked(diagnosticsService.validateConfig).mockResolvedValue({
      status: 'passed',
      errors: [],
      warnings: [],
      info: [],
    });
  });

  it('merges built-in web-search providers and preserves the configured langsearch selection', async () => {
    const { result } = renderHook(() => useConfigurationState(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.currentWebSearchConfig.enabled).toBe(false);
    expect(result.current.currentWebSearchConfig.provider).toBe('langsearch');
    expect(result.current.selectedWebSearchProvider?.id).toBe('langsearch');
    expect(result.current.webSearchProviders.some((provider) => provider.id === 'langsearch')).toBe(true);
  });
});
