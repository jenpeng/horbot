import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent, Dispatch, RefObject, SetStateAction } from 'react';
import type { Config, ModelConfig, ModelsConfig, WebSearchProvider } from '../types';
import configService from '../services/config';
import type { AgentRecord, RemoteImageCacheStatus } from '../services/config';
import diagnosticsService from '../services/diagnostics';
import type { ConfigCheckResultData } from '../components/ConfigCheckResult';
import { useI18n } from '../contexts/I18nContext';
import { createAsyncResourceCache } from '../utils/asyncResourceCache';
import {
  BUILTIN_PROVIDER_NAMES,
  DEFAULT_MODELS_CONFIG,
  DEFAULT_WEB_SEARCH,
  normalizeModelsConfig,
  type ModelScenarioKey,
} from '../components/config/constants';

const createEmptyModelChangeState = (): Record<ModelScenarioKey, boolean> => ({
  main: false,
  planning: false,
  file: false,
  image: false,
  audio: false,
  video: false,
});

const configSnapshotCache = createAsyncResourceCache(
  async () => {
    const [config, agents] = await Promise.all([
      configService.getConfig(),
      configService.getAgents(),
    ]);
    return { config, agents };
  },
  {
    ttlMs: 20_000,
    keyFn: () => 'config-snapshot',
  },
);

const webSearchProvidersCache = createAsyncResourceCache(
  () => configService.getWebSearchProviders(),
  {
    ttlMs: 5 * 60_000,
    keyFn: () => 'web-search-providers',
  },
);

const remoteImageCacheStatusCache = createAsyncResourceCache(
  () => configService.getRemoteImageCacheStatus(),
  {
    ttlMs: 20_000,
    keyFn: () => 'remote-image-cache-status',
  },
);

const configValidationCache = createAsyncResourceCache(
  () => diagnosticsService.validateConfig(),
  {
    ttlMs: 20_000,
    keyFn: () => 'config-validation',
  },
);

export interface ConfigurationValidationSummary {
  label: string;
  tone: 'ok' | 'warning' | 'error';
}

export type WebSearchApiKeyMode = 'keep' | 'replace' | 'clear';
export type ConfigurationSectionKey = 'agent' | 'workspace' | 'web-search';

export interface MainAgentSummary {
  id: string;
  name: string;
  model: string;
  provider: string;
  effectiveWorkspace: string;
  usesModelOverride: boolean;
  usesWorkspaceOverride: boolean;
}

export interface UseConfigurationStateResult {
  config: Config | null;
  isLoading: boolean;
  error: string | null;
  success: string | null;
  fileInputRef: RefObject<HTMLInputElement | null>;
  agentSettings: {
    max_tokens: number;
    temperature: number;
  };
  modelsConfig: ModelsConfig;
  modelChanges: Record<ModelScenarioKey, boolean>;
  modelSaving: Record<ModelScenarioKey, boolean>;
  workspacePath: string;
  agentErrors: Record<string, string>;
  hasAgentChanges: boolean;
  hasWorkspaceChanges: boolean;
  hasModelsChanges: boolean;
  hasWebSearchChanges: boolean;
  isSavingAgent: boolean;
  isSavingWorkspace: boolean;
  isSavingModels: boolean;
  isSavingWebSearch: boolean;
  isClearingRemoteImageCache: boolean;
  isRefreshing: boolean;
  isValidating: boolean;
  validationData: ConfigCheckResultData | null;
  validationSummary: ConfigurationValidationSummary | null;
  webSearchProviders: WebSearchProvider[];
  isLoadingProviders: boolean;
  currentWebSearchConfig: {
    provider: string;
    tavilyEnabled: boolean;
    apiKey: string;
    apiKeyMode: WebSearchApiKeyMode;
    hasApiKey: boolean;
    apiKeyMasked: string;
    maxResults: number;
  };
  selectedWebSearchProvider?: WebSearchProvider;
  configuredProviders: number;
  totalProviders: number;
  missingProviderCount: number;
  mainProviderConfigured: boolean;
  mainAgent: MainAgentSummary | null;
  dirtySections: ConfigurationSectionKey[];
  providerOptions: string[];
  hasPendingChanges: boolean;
  canSaveWebSearch: boolean;
  remoteImageCacheStatus: RemoteImageCacheStatus;
  setError: Dispatch<SetStateAction<string | null>>;
  setSuccess: Dispatch<SetStateAction<string | null>>;
  clearFieldError: (fieldName: string) => void;
  setAgentSettings: Dispatch<
    SetStateAction<{
      max_tokens: number;
      temperature: number;
    }>
  >;
  setWorkspacePath: Dispatch<SetStateAction<string>>;
  updateModelConfig: (scenario: ModelScenarioKey, field: keyof ModelConfig, value: string) => void;
  updateWebSearchConfig: (
    patch: Partial<{ provider: string; tavilyEnabled: boolean; apiKey: string; apiKeyMode: WebSearchApiKeyMode; maxResults: number }>
  ) => void;
  handleSaveAgentSettings: () => Promise<void>;
  handleSaveWorkspace: () => Promise<void>;
  handleSaveModelsConfig: () => Promise<void>;
  handleSaveModel: (scenario: ModelScenarioKey) => Promise<void>;
  handleSaveWebSearch: () => Promise<void>;
  handleClearRemoteImageCache: () => Promise<void>;
  handleExport: () => void;
  handleImport: (event: ChangeEvent<HTMLInputElement>) => void;
  handleProviderAdded: () => Promise<void>;
  handleProviderDeleted: (name: string) => Promise<void>;
  handleValidateClick: () => Promise<void>;
  refreshConfigFromServer: (successMessage?: string) => Promise<void>;
}

export const useConfigurationState = (): UseConfigurationStateResult => {
  const { t } = useI18n();
  const cachedConfigSnapshot = configSnapshotCache.peek();
  const cachedProviders = webSearchProvidersCache.peek();
  const cachedValidation = configValidationCache.peek();
  const cachedRemoteImageCacheStatus = remoteImageCacheStatusCache.peek();
  const [config, setConfig] = useState<Config | null>(null);
  const [isLoading, setIsLoading] = useState(!cachedConfigSnapshot);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const successTimerRef = useRef<number | null>(null);

  const [agentSettings, setAgentSettings] = useState({
    max_tokens: 8192,
    temperature: 0.7,
  });
  const [modelsConfig, setModelsConfig] = useState<ModelsConfig>(DEFAULT_MODELS_CONFIG);
  const [isSavingModels, setIsSavingModels] = useState(false);
  const [hasModelsChanges, setHasModelsChanges] = useState(false);
  const [modelChanges, setModelChanges] = useState<Record<ModelScenarioKey, boolean>>(createEmptyModelChangeState());
  const [modelSaving, setModelSaving] = useState<Record<ModelScenarioKey, boolean>>(createEmptyModelChangeState());
  const [workspacePath, setWorkspacePath] = useState('');
  const [isSavingAgent, setIsSavingAgent] = useState(false);
  const [isSavingWorkspace, setIsSavingWorkspace] = useState(false);
  const [agentErrors, setAgentErrors] = useState<Record<string, string>>({});
  const [hasAgentChanges, setHasAgentChanges] = useState(false);
  const [hasWorkspaceChanges, setHasWorkspaceChanges] = useState(false);
  const [hasWebSearchChanges, setHasWebSearchChanges] = useState(false);
  const [isSavingWebSearch, setIsSavingWebSearch] = useState(false);
  const [webSearchSettings, setWebSearchSettings] = useState({
    provider: DEFAULT_WEB_SEARCH.provider,
    tavilyEnabled: DEFAULT_WEB_SEARCH.tavilyEnabled,
    maxResults: DEFAULT_WEB_SEARCH.maxResults,
  });
  const [webSearchApiKeyInput, setWebSearchApiKeyInput] = useState('');
  const [webSearchApiKeyMode, setWebSearchApiKeyMode] = useState<WebSearchApiKeyMode>('keep');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [validationData, setValidationData] = useState<ConfigCheckResultData | null>(cachedValidation ?? null);
  const [webSearchProviders, setWebSearchProviders] = useState<WebSearchProvider[]>(cachedProviders ?? []);
  const [isLoadingProviders, setIsLoadingProviders] = useState(false);
  const [mainAgent, setMainAgent] = useState<MainAgentSummary | null>(null);
  const [remoteImageCacheStatus, setRemoteImageCacheStatus] = useState<RemoteImageCacheStatus>({
    count: cachedRemoteImageCacheStatus?.count ?? 0,
    total_size_bytes: cachedRemoteImageCacheStatus?.total_size_bytes ?? 0,
    newest_updated_at: cachedRemoteImageCacheStatus?.newest_updated_at ?? null,
  });
  const [isClearingRemoteImageCache, setIsClearingRemoteImageCache] = useState(false);

  const showSuccessMessage = useCallback((message: string) => {
    if (successTimerRef.current !== null) {
      window.clearTimeout(successTimerRef.current);
    }
    setSuccess(message);
    successTimerRef.current = window.setTimeout(() => {
      setSuccess(null);
      successTimerRef.current = null;
    }, 3000);
  }, []);

  useEffect(() => {
    return () => {
      if (successTimerRef.current !== null) {
        window.clearTimeout(successTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (error) {
      const timer = window.setTimeout(() => {
        setError(null);
      }, 5000);
      return () => window.clearTimeout(timer);
    }
  }, [error]);

  useEffect(() => {
    if (Object.keys(agentErrors).length > 0) {
      const timer = window.setTimeout(() => {
        setAgentErrors({});
      }, 5000);
      return () => window.clearTimeout(timer);
    }
  }, [agentErrors]);

  const applyConfigToForm = useCallback((data: Config) => {
    setConfig(data);
    const defaults = data.agents?.defaults;
    setAgentSettings({
      max_tokens: defaults?.maxTokens || 8192,
      temperature: defaults?.temperature ?? 0.7,
    });
    setWorkspacePath(defaults?.workspace || '');
    setModelsConfig(normalizeModelsConfig(defaults?.models));
    const search = data.tools?.web?.search;
    const resolvedTavilyEnabled = typeof search?.tavilyEnabled === 'boolean'
      ? search.tavilyEnabled
      : typeof (search as { tavily_enabled?: boolean } | undefined)?.tavily_enabled === 'boolean'
        ? Boolean((search as { tavily_enabled?: boolean }).tavily_enabled)
        : DEFAULT_WEB_SEARCH.tavilyEnabled;
    setWebSearchSettings({
      provider: search?.provider || DEFAULT_WEB_SEARCH.provider,
      tavilyEnabled: resolvedTavilyEnabled,
      maxResults: search?.maxResults || DEFAULT_WEB_SEARCH.maxResults,
    });
    setHasAgentChanges(false);
    setHasWorkspaceChanges(false);
    setHasModelsChanges(false);
    setHasWebSearchChanges(false);
    setModelChanges(createEmptyModelChangeState());
    setAgentErrors({});
    setWebSearchApiKeyInput('');
    setWebSearchApiKeyMode('keep');
  }, []);

  const applyMainAgentToState = useCallback((agents: AgentRecord[]) => {
    const currentMainAgent = agents[0] || null;
    if (!currentMainAgent) {
      setMainAgent(null);
      return;
    }

    setMainAgent({
      id: currentMainAgent.id,
      name: currentMainAgent.name,
      model: currentMainAgent.model,
      provider: currentMainAgent.provider,
      effectiveWorkspace: currentMainAgent.effective_workspace || currentMainAgent.workspace || '',
      usesModelOverride: Boolean(currentMainAgent.model_override?.trim()),
      usesWorkspaceOverride: Boolean(currentMainAgent.workspace?.trim()),
    });
  }, []);

  const loadConfigState = useCallback(
    async (options: { showLoading?: boolean; successMessage?: string; force?: boolean } = {}) => {
      if (options.showLoading) {
        setIsLoading(true);
      }

      try {
        const snapshot = options.force
          ? await configSnapshotCache.refresh()
          : await configSnapshotCache.get();
        applyConfigToForm(snapshot.config);
        applyMainAgentToState(snapshot.agents);
        if (options.successMessage) {
          showSuccessMessage(options.successMessage);
        }
        return snapshot.config;
      } catch (err) {
        setError(t('config.fetchFailed'));
        console.error('Error fetching config:', err);
        return null;
      } finally {
        if (options.showLoading) {
          setIsLoading(false);
        }
      }
    },
    [applyConfigToForm, applyMainAgentToState, showSuccessMessage]
  );

  const runValidation = useCallback(async (options: { silent?: boolean; force?: boolean } = {}) => {
    setIsValidating(true);
    try {
      const data = options.force
        ? await configValidationCache.refresh()
        : await configValidationCache.get();
      setValidationData(data);
      return data;
    } catch (err) {
      console.error('Failed to validate config:', err);
      if (!options.silent) {
        setError(t('config.validateFailed'));
      }
      return null;
    } finally {
      setIsValidating(false);
    }
  }, []);

  const refreshConfigFromServer = useCallback(
    async (successMessage?: string) => {
      setIsRefreshing(true);
      try {
        await loadConfigState({ successMessage, force: true });
        await runValidation({ silent: true, force: true });
      } finally {
        setIsRefreshing(false);
      }
    },
    [loadConfigState, runValidation]
  );

  const fetchProviders = useCallback(async (options: { force?: boolean } = {}) => {
    setIsLoadingProviders(true);
    try {
      const providers = options.force
        ? await webSearchProvidersCache.refresh()
        : await webSearchProvidersCache.get();
      setWebSearchProviders(providers);
    } catch (err) {
      console.error('Failed to fetch web search providers:', err);
    } finally {
      setIsLoadingProviders(false);
    }
  }, []);

  const refreshRemoteImageCacheStatus = useCallback(async (options: { force?: boolean } = {}) => {
    try {
      const status = options.force
        ? await remoteImageCacheStatusCache.refresh()
        : await remoteImageCacheStatusCache.get();
      setRemoteImageCacheStatus(status);
    } catch (err) {
      console.error('Failed to fetch remote image cache status:', err);
    }
  }, []);

  useEffect(() => {
    if (cachedConfigSnapshot) {
      applyConfigToForm(cachedConfigSnapshot.config);
      applyMainAgentToState(cachedConfigSnapshot.agents);
    }

    void Promise.all([
      loadConfigState({ showLoading: !cachedConfigSnapshot }),
      fetchProviders({ force: false }),
      refreshRemoteImageCacheStatus({ force: false }),
      runValidation({ silent: true, force: false }),
    ]);
  }, [applyConfigToForm, applyMainAgentToState, cachedConfigSnapshot, fetchProviders, loadConfigState, refreshRemoteImageCacheStatus, runValidation]);

  const validateAgentSettings = useCallback(() => {
    const errors: Record<string, string> = {};
    if (agentSettings.max_tokens < 1 || agentSettings.max_tokens > 1000000) {
      errors.max_tokens = t('config.validation.maxTokens');
    }
    if (agentSettings.temperature < 0 || agentSettings.temperature > 2) {
      errors.temperature = t('config.validation.temperature');
    }
    setAgentErrors(errors);
    return Object.keys(errors).length === 0;
  }, [agentSettings]);

  const clearFieldError = useCallback((fieldName: string) => {
    setAgentErrors((prev) => {
      const next = { ...prev };
      delete next[fieldName];
      return next;
    });
  }, []);

  useEffect(() => {
    if (!config) {
      return;
    }
    const defaults = config.agents?.defaults || {};
    const hasChanges =
      agentSettings.max_tokens !== (defaults.maxTokens || 8192) ||
      agentSettings.temperature !== (defaults.temperature ?? 0.7);
    setHasAgentChanges(hasChanges);
  }, [agentSettings, config]);

  useEffect(() => {
    if (!config) {
      return;
    }
    const defaults = config.agents?.defaults || {};
    setHasWorkspaceChanges(workspacePath !== (defaults.workspace || ''));
  }, [workspacePath, config]);

  const currentWebSearchConfig = useMemo(() => {
    const search = config?.tools?.web?.search;
    return {
      provider: webSearchSettings.provider,
      tavilyEnabled: webSearchSettings.tavilyEnabled,
      apiKey: webSearchApiKeyInput,
      apiKeyMode: webSearchApiKeyMode,
      hasApiKey: Boolean(search?.hasApiKey),
      apiKeyMasked: search?.apiKeyMasked || '',
      maxResults: webSearchSettings.maxResults,
    };
  }, [config, webSearchApiKeyInput, webSearchApiKeyMode, webSearchSettings]);

  const selectedWebSearchProvider = useMemo(
    () => webSearchProviders.find((provider) => provider.id === currentWebSearchConfig.provider),
    [currentWebSearchConfig.provider, webSearchProviders]
  );

  const updateWebSearchConfig = useCallback(
    (patch: Partial<{ provider: string; tavilyEnabled: boolean; apiKey: string; apiKeyMode: WebSearchApiKeyMode; maxResults: number }>) => {
      setWebSearchSettings((prev) => ({
        provider: patch.provider ?? prev.provider,
        tavilyEnabled: patch.tavilyEnabled ?? prev.tavilyEnabled,
        maxResults: patch.maxResults ?? prev.maxResults,
      }));
      if (patch.apiKeyMode !== undefined) {
        setWebSearchApiKeyMode(patch.apiKeyMode);
        if (patch.apiKeyMode === 'keep' || patch.apiKeyMode === 'clear') {
          setWebSearchApiKeyInput('');
        }
      }
      if (patch.apiKey !== undefined) {
        setWebSearchApiKeyInput(patch.apiKey);
        if (patch.apiKey.trim().length > 0) {
          setWebSearchApiKeyMode('replace');
        }
      }
    },
    []
  );

  useEffect(() => {
    if (!config) {
      return;
    }
    const search = config.tools?.web?.search;
    const persistedTavilyEnabled = typeof search?.tavilyEnabled === 'boolean'
      ? search.tavilyEnabled
      : typeof (search as { tavily_enabled?: boolean } | undefined)?.tavily_enabled === 'boolean'
        ? Boolean((search as { tavily_enabled?: boolean }).tavily_enabled)
        : DEFAULT_WEB_SEARCH.tavilyEnabled;
    const hasChanges =
      webSearchSettings.provider !== (search?.provider || DEFAULT_WEB_SEARCH.provider) ||
      webSearchSettings.tavilyEnabled !== persistedTavilyEnabled ||
      webSearchSettings.maxResults !== (search?.maxResults || DEFAULT_WEB_SEARCH.maxResults) ||
      webSearchApiKeyMode === 'clear' ||
      (webSearchApiKeyMode === 'replace' && webSearchApiKeyInput.trim().length > 0);
    setHasWebSearchChanges(hasChanges);
  }, [config, webSearchApiKeyInput, webSearchApiKeyMode, webSearchSettings]);

  const canSaveWebSearch = useMemo(() => {
    if (!hasWebSearchChanges) {
      return false;
    }
    if (!selectedWebSearchProvider?.requires_api_key) {
      return true;
    }
    if (webSearchApiKeyMode === 'replace') {
      return webSearchApiKeyInput.trim().length > 0;
    }
    return true;
  }, [hasWebSearchChanges, selectedWebSearchProvider?.requires_api_key, webSearchApiKeyInput, webSearchApiKeyMode]);

  const handleSaveAgentSettings = useCallback(async () => {
    if (!validateAgentSettings()) {
      return;
    }

    setIsSavingAgent(true);
    setError(null);
    setSuccess(null);

    try {
      await configService.updateAgentDefaults({
        maxTokens: agentSettings.max_tokens,
        temperature: agentSettings.temperature,
      });
      await refreshConfigFromServer(t('config.success.agentSettingsSaved'));
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || t('config.error.saveAgentSettings');
      setError(errorMsg);
    } finally {
      setIsSavingAgent(false);
    }
  }, [agentSettings.max_tokens, agentSettings.temperature, refreshConfigFromServer, validateAgentSettings]);

  const handleSaveWorkspace = useCallback(async () => {
    setIsSavingWorkspace(true);
    setError(null);
    setSuccess(null);

    try {
      await configService.updateAgentDefaults({
        workspace: workspacePath,
      });
      await refreshConfigFromServer(t('config.success.workspaceSaved'));
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || t('config.error.saveWorkspace');
      setError(errorMsg);
    } finally {
      setIsSavingWorkspace(false);
    }
  }, [refreshConfigFromServer, workspacePath]);

  const handleSaveWebSearch = useCallback(async () => {
    setIsSavingWebSearch(true);
    setError(null);
    setSuccess(null);

    try {
      await configService.updateWebSearchConfig({
        provider: currentWebSearchConfig.provider,
        tavilyEnabled: currentWebSearchConfig.tavilyEnabled,
        ...(webSearchApiKeyMode === 'replace' ? { apiKey: webSearchApiKeyInput.trim() } : {}),
        ...(webSearchApiKeyMode === 'clear' ? { apiKey: '' } : {}),
        maxResults: currentWebSearchConfig.maxResults,
      });
      await refreshConfigFromServer(t('config.success.webSearchSaved'));
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || t('config.error.saveWebSearch');
      setError(errorMsg);
    } finally {
      setIsSavingWebSearch(false);
    }
  }, [currentWebSearchConfig, refreshConfigFromServer, webSearchApiKeyInput, webSearchApiKeyMode]);

  const handleClearRemoteImageCache = useCallback(async () => {
    setIsClearingRemoteImageCache(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await configService.clearRemoteImageCache();
      remoteImageCacheStatusCache.clear();
      await refreshRemoteImageCacheStatus({ force: true });
      showSuccessMessage(
        t('config.remoteImageCache.clearSuccess', { count: result.deleted_count }),
      );
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || t('config.remoteImageCache.clearFailed');
      setError(errorMsg);
    } finally {
      setIsClearingRemoteImageCache(false);
    }
  }, [refreshRemoteImageCacheStatus, setError, showSuccessMessage, t]);

  const handleSaveModelsConfig = useCallback(async () => {
    setIsSavingModels(true);
    setError(null);
    setSuccess(null);

    try {
      await configService.updateAgentDefaults({
        models: modelsConfig,
      });
      await refreshConfigFromServer(t('config.success.modelsSaved'));
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || t('config.error.saveModels');
      setError(errorMsg);
    } finally {
      setIsSavingModels(false);
    }
  }, [modelsConfig, refreshConfigFromServer]);

  const handleSaveModel = useCallback(
    async (scenario: ModelScenarioKey) => {
      setModelSaving((prev) => ({ ...prev, [scenario]: true }));
      setError(null);
      setSuccess(null);

      try {
        await configService.updateModelConfig(scenario, modelsConfig[scenario]);
        const scenarioLabelKeyMap: Record<ModelScenarioKey, string> = {
          main: 'config.modelScenario.main',
          planning: 'config.modelScenario.planning',
          file: 'config.modelScenario.file',
          image: 'config.modelScenario.image',
          audio: 'config.modelScenario.audio',
          video: 'config.modelScenario.video',
        };
        const label = t(scenarioLabelKeyMap[scenario]);
        await refreshConfigFromServer(t('config.success.modelSaved', { label }));
      } catch (err: any) {
        const errorMsg = err.response?.data?.detail || err.message || t('config.error.saveGeneric');
        setError(errorMsg);
      } finally {
        setModelSaving((prev) => ({ ...prev, [scenario]: false }));
      }
    },
    [modelsConfig, refreshConfigFromServer]
  );

  const updateModelConfig = useCallback((scenario: ModelScenarioKey, field: keyof ModelConfig, value: string) => {
    setModelsConfig((prev) => ({
      ...prev,
      [scenario]: {
        ...prev[scenario],
        [field]: value,
      },
    }));
    setModelChanges((prev) => ({ ...prev, [scenario]: true }));
    setHasModelsChanges(true);
  }, []);

  const handleExport = useCallback(() => {
    if (!config) {
      return;
    }
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const dataStr = JSON.stringify(config, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `horbot-config-${timestamp}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [config]);

  const handleImport = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }

      const reader = new FileReader();
      reader.onload = async (e) => {
        setError(null);
        setSuccess(null);
        try {
          const importedConfig = JSON.parse(e.target?.result as string);
          await configService.updateConfig(importedConfig);
          await refreshConfigFromServer(t('config.success.imported'));
        } catch (err: any) {
          const errorMsg = err.response?.data?.detail || t('config.invalidImportFormat');
          setError(errorMsg);
        }
      };
      reader.readAsText(file);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    },
    [refreshConfigFromServer]
  );

  const handleProviderAdded = useCallback(async () => {
    await refreshConfigFromServer(t('config.success.providerAdded'));
  }, [refreshConfigFromServer, t]);

  const handleProviderDeleted = useCallback(
    async (name: string) => {
      await refreshConfigFromServer(t('config.success.providerDeleted', { name }));
    },
    [refreshConfigFromServer, t]
  );

  const handleValidateClick = useCallback(async () => {
    setError(null);
    await runValidation();
  }, [runValidation]);

  const configuredProviders = config?.providers
    ? Object.values(config.providers).filter((provider) => provider?.hasApiKey || provider?.apiKey).length
    : 0;
  const totalProviders = config?.providers ? Object.keys(config.providers).length : 0;
  const missingProviderCount = Math.max(0, totalProviders - configuredProviders);
  const mainProviderConfigured = Boolean(
    config?.providers?.[modelsConfig.main.provider]?.hasApiKey || config?.providers?.[modelsConfig.main.provider]?.apiKey
  );

  const providerOptions = useMemo(
    () => Array.from(new Set([...(config?.providers ? Object.keys(config.providers) : []), ...BUILTIN_PROVIDER_NAMES])),
    [config?.providers]
  );

  const validationSummary = useMemo(() => {
    if (!validationData) {
      return null;
    }
    if (validationData.errors.length === 0 && validationData.warnings.length === 0) {
      return { label: t('config.validationSummary.passed'), tone: 'ok' as const };
    }
    if (validationData.errors.length > 0) {
      return { label: t('config.validationSummary.errorsWarnings', { errors: validationData.errors.length, warnings: validationData.warnings.length }), tone: 'error' as const };
    }
    return { label: t('config.validationSummary.warnings', { warnings: validationData.warnings.length }), tone: 'warning' as const };
  }, [t, validationData]);

  const hasPendingChanges = hasAgentChanges || hasWorkspaceChanges || hasModelsChanges || hasWebSearchChanges;
  const dirtySections = useMemo(() => {
    const sections: ConfigurationSectionKey[] = [];
    if (hasAgentChanges || hasModelsChanges) {
      sections.push('agent');
    }
    if (hasWorkspaceChanges) {
      sections.push('workspace');
    }
    if (hasWebSearchChanges) {
      sections.push('web-search');
    }
    return sections;
  }, [hasAgentChanges, hasModelsChanges, hasWebSearchChanges, hasWorkspaceChanges]);

  return {
    config,
    isLoading,
    error,
    success,
    fileInputRef,
    agentSettings,
    modelsConfig,
    modelChanges,
    modelSaving,
    workspacePath,
    agentErrors,
    hasAgentChanges,
    hasWorkspaceChanges,
    hasModelsChanges,
    hasWebSearchChanges,
    isSavingAgent,
    isSavingWorkspace,
    isSavingModels,
    isSavingWebSearch,
    isClearingRemoteImageCache,
    isRefreshing,
    isValidating,
    validationData,
    validationSummary,
    webSearchProviders,
    isLoadingProviders,
    currentWebSearchConfig,
    selectedWebSearchProvider,
    configuredProviders,
    totalProviders,
    missingProviderCount,
    mainProviderConfigured,
    mainAgent,
    dirtySections,
    providerOptions,
    hasPendingChanges,
    canSaveWebSearch,
    remoteImageCacheStatus,
    setError,
    setSuccess,
    clearFieldError,
    setAgentSettings,
    setWorkspacePath,
    updateModelConfig,
    updateWebSearchConfig,
    handleSaveAgentSettings,
    handleSaveWorkspace,
    handleSaveModelsConfig,
    handleSaveModel,
    handleSaveWebSearch,
    handleClearRemoteImageCache,
    handleExport,
    handleImport,
    handleProviderAdded,
    handleProviderDeleted,
    handleValidateClick,
    refreshConfigFromServer,
  };
};

export default useConfigurationState;
