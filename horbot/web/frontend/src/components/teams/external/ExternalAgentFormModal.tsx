import { useEffect, useMemo, useState, type Dispatch, type KeyboardEvent, type SetStateAction } from 'react';
import { useI18n } from '../../../contexts/I18nContext';
import type { AgentCapabilityOption } from '../../../pages/teams/formOptions';
import type { ExternalAgentFormState } from '../../../pages/teams/types';

interface ExternalAgentFormModalProps {
  mode: 'create' | 'edit';
  form: ExternalAgentFormState;
  setForm: Dispatch<SetStateAction<ExternalAgentFormState>>;
  capabilityOptions: AgentCapabilityOption[];
  createIdError?: string;
  createNameError?: string;
  createEndpointError?: string;
  submitDisabled?: boolean;
  onClose: () => void;
  onSubmit: () => void;
}

const parseCapabilities = (value: string): string[] => (
  value
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean)
);

const normalizeCapabilities = (values: string[]): string[] => {
  const deduped = new Map<string, string>();
  values
    .map((value) => value.trim())
    .filter(Boolean)
    .forEach((value) => {
      const normalized = value.toLowerCase();
      if (!deduped.has(normalized)) {
        deduped.set(normalized, value);
      }
    });
  return Array.from(deduped.values());
};

const formatAdapterConfig = (value: ExternalAgentFormState['adapter_config']): string => {
  const config = value || {};
  return Object.keys(config).length > 0 ? JSON.stringify(config, null, 2) : '';
};

const normalizeAdapterId = (value?: string): string => value || 'inbound-bot';

const adapterRequiresEndpoint = (adapterId: string): boolean => (
  adapterId === 'generic-agent-api' || adapterId === 'openai-compatible'
);

const adapterUsesTransport = (adapterId: string): boolean => adapterId === 'generic-agent-api';

const adapterIsInboundBot = (adapterId: string): boolean => (
  adapterId === 'inbound-bot' || adapterId === 'channel-backed-agent' || adapterId === 'web-ui-bridge'
);

const randomHex = (bytes: number): string => {
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    const buffer = new Uint8Array(bytes);
    crypto.getRandomValues(buffer);
    return Array.from(buffer, (item) => item.toString(16).padStart(2, '0')).join('');
  }
  return Array.from({ length: bytes }, () => Math.floor(Math.random() * 256).toString(16).padStart(2, '0')).join('');
};

const buildInboundBotConfig = (
  currentConfig: ExternalAgentFormState['adapter_config'],
  externalAgentId: string,
): Record<string, unknown> => {
  const nextConfig = { ...(currentConfig || {}) };
  const safeId = externalAgentId.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '') || 'external';
  if (!nextConfig.bot_app_id) {
    nextConfig.bot_app_id = `hbot_${safeId}_${randomHex(4)}`;
  }
  if (!nextConfig.bot_token) {
    nextConfig.bot_token = randomHex(24);
  }
  return nextConfig;
};

const getExternalCapabilityPresets = (t: (key: string) => string) => ([
  {
    id: 'research',
    label: t('teams.external.form.capabilityPreset.research.label'),
    summary: t('teams.external.form.capabilityPreset.research.summary'),
    capabilities: ['research', 'planning', 'writing'],
  },
  {
    id: 'engineering',
    label: t('teams.external.form.capabilityPreset.engineering.label'),
    summary: t('teams.external.form.capabilityPreset.engineering.summary'),
    capabilities: ['code', 'testing', 'review'],
  },
  {
    id: 'data',
    label: t('teams.external.form.capabilityPreset.data.label'),
    summary: t('teams.external.form.capabilityPreset.data.summary'),
    capabilities: ['data', 'research', 'planning'],
  },
  {
    id: 'vision',
    label: t('teams.external.form.capabilityPreset.vision.label'),
    summary: t('teams.external.form.capabilityPreset.vision.summary'),
    capabilities: ['vision', 'research', 'writing'],
  },
]);

const RECOMMENDATION_KEYWORDS: Record<string, string[]> = {
  research: ['research', 'search', 'retrieve', 'retrieval', 'rag', 'docs', 'document', 'knowledge', 'report', 'analysis', 'analyst', '调研', '研究', '检索', '资料', '报告'],
  engineering: ['code', 'coding', 'developer', 'dev', 'engineering', 'test', 'testing', 'qa', 'review', 'repo', 'github', 'gitlab', 'ci', '编程', '代码', '测试', '审查', '工程'],
  data: ['data', 'sql', 'database', 'db', 'tableau', 'bi', 'metric', 'warehouse', 'analytics', 'dataset', 'csv', 'excel', '数据', '报表', '指标', '分析'],
  vision: ['vision', 'image', 'ocr', 'screenshot', 'diagram', 'figure', 'photo', 'scan', 'visual', '图片', '图像', '识图', '截图', '视觉'],
};

const recommendCapabilityPresetId = (
  content: string,
  presetIds: string[],
): string | null => {
  const normalized = content.trim().toLowerCase();
  if (!normalized) {
    return null;
  }

  const scores = new Map<string, number>();
  presetIds.forEach((id) => scores.set(id, 0));

  for (const presetId of presetIds) {
    const keywords = RECOMMENDATION_KEYWORDS[presetId] || [];
    for (const keyword of keywords) {
      if (normalized.includes(keyword)) {
        scores.set(presetId, (scores.get(presetId) || 0) + 1);
      }
    }
  }

  const ranked = Array.from(scores.entries()).sort((left, right) => right[1] - left[1]);
  return ranked[0] && ranked[0][1] > 0 ? ranked[0][0] : null;
};

interface ConnectionRecommendation {
  updates: Partial<Pick<ExternalAgentFormState, 'transport' | 'auth_type' | 'dm_enabled' | 'team_enabled' | 'mention_required'>>;
  reasons: string[];
}

const buildConnectionRecommendation = ({
  endpoint,
  name,
  description,
}: Pick<ExternalAgentFormState, 'endpoint' | 'name' | 'description'>): ConnectionRecommendation | null => {
  const updates: ConnectionRecommendation['updates'] = {};
  const reasons: string[] = [];
  const normalizedEndpoint = endpoint.trim().toLowerCase();
  const normalizedContext = `${name} ${description} ${endpoint}`.trim().toLowerCase();

  if (!normalizedEndpoint && !normalizedContext) {
    return null;
  }

  if (normalizedEndpoint.startsWith('ws://') || normalizedEndpoint.startsWith('wss://')) {
    updates.transport = 'websocket';
    reasons.push('transport_websocket');
  } else if (/(^https?:\/\/.*(sse|stream))|([/?=&_-](sse|stream)([/?=&_-]|$))/.test(normalizedEndpoint)) {
    updates.transport = 'http_sse';
    reasons.push('transport_sse');
  } else if (normalizedEndpoint.startsWith('http://') || normalizedEndpoint.startsWith('https://')) {
    updates.transport = 'http';
    reasons.push('transport_http');
  }

  if (/\b(x-api-key|header auth|custom header|signature)\b/.test(normalizedContext)) {
    updates.auth_type = 'header';
    reasons.push('auth_header');
  } else if (/\b(bearer|token|api key|apikey)\b/.test(normalizedContext) || /bearer/i.test(description)) {
    updates.auth_type = 'bearer';
    reasons.push('auth_bearer');
  }

  const teamLike = /\b(team|group|relay|mention|@mention|workspace)\b/.test(normalizedContext)
    || /(团队|群聊|协作|接力|提及|mention)/.test(`${name} ${description}`);
  if (teamLike) {
    updates.team_enabled = true;
    updates.mention_required = true;
    reasons.push('access_team');
  }

  const dmLike = /\b(dm|direct chat|direct message|private chat|one[- ]on[- ]one)\b/.test(normalizedContext)
    || /(单聊|私聊|直接对话)/.test(`${name} ${description}`);
  if (dmLike) {
    updates.dm_enabled = true;
    reasons.push('access_dm');
  }

  return Object.keys(updates).length > 0 ? { updates, reasons } : null;
};

const ExternalAgentFormModal = ({
  mode,
  form,
  setForm,
  capabilityOptions,
  createIdError = '',
  createNameError = '',
  createEndpointError = '',
  submitDisabled = false,
  onClose,
  onSubmit,
}: ExternalAgentFormModalProps) => {
  const isCreateMode = mode === 'create';
  const { t } = useI18n();
  const [currentStep, setCurrentStep] = useState<0 | 1>(0);
  const [customCapabilityInput, setCustomCapabilityInput] = useState('');
  const [manualCapabilityOpen, setManualCapabilityOpen] = useState(false);
  const [runtimeOpen, setRuntimeOpen] = useState(false);
  const [advancedAdapterOpen, setAdvancedAdapterOpen] = useState(() => !adapterIsInboundBot(normalizeAdapterId(form.adapter)));
  const [adapterConfigDraft, setAdapterConfigDraft] = useState(() => formatAdapterConfig(form.adapter_config));
  const [adapterConfigError, setAdapterConfigError] = useState('');
  const adapterId = normalizeAdapterId(form.adapter);
  const endpointRequired = adapterRequiresEndpoint(adapterId);
  const transportVisible = adapterUsesTransport(adapterId);
  const inboundBotAdapter = adapterIsInboundBot(adapterId);
  const botAppId = typeof form.adapter_config?.bot_app_id === 'string' ? form.adapter_config.bot_app_id : '';
  const botToken = typeof form.adapter_config?.bot_token === 'string' ? form.adapter_config.bot_token : '';
  const inboundUrlPath = botAppId ? `/api/external-agents/inbound/${botAppId}/messages` : '';
  const inboundUrl = inboundUrlPath && typeof window !== 'undefined'
    ? `${window.location.origin.replace(/:3000$/, ':8000')}${inboundUrlPath}`
    : inboundUrlPath;
  const capabilityPresets = useMemo(() => getExternalCapabilityPresets(t), [t]);
  const adapterOptions = useMemo(() => ([
    { id: 'inbound-bot', label: t('teams.external.adapter.inboundBot'), description: t('teams.external.adapterDescription.inboundBot') },
    { id: 'generic-agent-api', label: t('teams.external.adapter.genericAgentApi'), description: t('teams.external.adapterDescription.genericAgentApi') },
    { id: 'openai-compatible', label: t('teams.external.adapter.openaiCompatible'), description: t('teams.external.adapterDescription.openaiCompatible') },
    { id: 'dify', label: 'Dify', description: t('teams.external.adapterDescription.futureVendor') },
    { id: 'coze', label: 'Coze', description: t('teams.external.adapterDescription.futureVendor') },
    { id: 'langgraph', label: 'LangGraph', description: t('teams.external.adapterDescription.futureLocal') },
    { id: 'mcp-agent', label: 'MCP Agent', description: t('teams.external.adapterDescription.futureLocal') },
  ]), [t]);
  const selectedAdapter = adapterOptions.find((option) => option.id === adapterId) || adapterOptions[0];
  const visibleAdapterOptions = advancedAdapterOpen
    ? adapterOptions
    : [selectedAdapter.id === 'inbound-bot' ? selectedAdapter : adapterOptions[0], ...(selectedAdapter.id === 'inbound-bot' ? [] : [selectedAdapter])];
  const stepItems = useMemo(() => ([
    {
      id: 0 as const,
      title: t('teams.external.form.step.connection.title'),
      description: t('teams.external.form.step.connection.description'),
    },
    {
      id: 1 as const,
      title: t('teams.external.form.step.behavior.title'),
      description: t('teams.external.form.step.behavior.description'),
    },
  ]), [t]);

  const selectedCapabilities = useMemo(
    () => normalizeCapabilities(form.capabilities),
    [form.capabilities],
  );
  const capabilityMetaById = useMemo(
    () => new Map(capabilityOptions.map((option) => [option.id.toLowerCase(), option])),
    [capabilityOptions],
  );
  const connectionRecommendation = useMemo(
    () => (adapterId === 'generic-agent-api' ? buildConnectionRecommendation({
      endpoint: form.endpoint,
      name: form.name,
      description: form.description,
    }) : null),
    [adapterId, form.description, form.endpoint, form.name],
  );
  const recommendedPresetId = useMemo(
    () => recommendCapabilityPresetId(
      [form.name, form.description, form.endpoint].filter(Boolean).join(' '),
      capabilityPresets.map((preset) => preset.id),
    ),
    [capabilityPresets, form.description, form.endpoint, form.name],
  );
  const recommendedPreset = capabilityPresets.find((preset) => preset.id === recommendedPresetId) || null;
  const canProceedToBehaviorStep = Boolean(
    form.name.trim()
    && (!endpointRequired || form.endpoint.trim())
    && (!isCreateMode || form.id.trim()),
  );

  useEffect(() => {
    setCustomCapabilityInput('');
    setCurrentStep(0);
    setManualCapabilityOpen(false);
    setRuntimeOpen(false);
    setAdvancedAdapterOpen(!adapterIsInboundBot(normalizeAdapterId(form.adapter)));
    setAdapterConfigDraft(formatAdapterConfig(form.adapter_config));
    setAdapterConfigError('');
  }, [mode, form.id]);

  useEffect(() => {
    if (!inboundBotAdapter || (botAppId && botToken)) {
      return;
    }
    if (!form.id.trim()) {
      return;
    }
    const nextAdapterConfig = buildInboundBotConfig(form.adapter_config, form.id);
    setAdapterConfigDraft(formatAdapterConfig(nextAdapterConfig));
    setForm({ ...form, adapter_config: nextAdapterConfig });
  }, [botAppId, botToken, form, inboundBotAdapter, setForm]);

  const updateCapabilities = (nextCapabilities: string[]) => {
    setForm({ ...form, capabilities: normalizeCapabilities(nextCapabilities) });
  };

  const toggleCapability = (capabilityId: string) => {
    const normalizedId = capabilityId.toLowerCase();
    const exists = selectedCapabilities.some((item) => item.toLowerCase() === normalizedId);
    updateCapabilities(
      exists
        ? selectedCapabilities.filter((item) => item.toLowerCase() !== normalizedId)
        : [...selectedCapabilities, capabilityId],
    );
  };

  const handleAddCustomCapabilities = () => {
    const parsed = parseCapabilities(customCapabilityInput);
    if (parsed.length === 0) {
      return;
    }
    updateCapabilities([...selectedCapabilities, ...parsed]);
    setCustomCapabilityInput('');
  };

  const handleCustomCapabilityKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'Enter') {
      return;
    }
    event.preventDefault();
    handleAddCustomCapabilities();
  };

  const applyCapabilityPreset = (presetCapabilities: string[]) => {
    updateCapabilities([...selectedCapabilities, ...presetCapabilities]);
  };

  const applyConnectionRecommendation = () => {
    if (!connectionRecommendation) {
      return;
    }
    setForm({ ...form, ...connectionRecommendation.updates });
  };

  const handleAdapterChange = (nextAdapter: string) => {
    const nextAdapterConfig = adapterIsInboundBot(nextAdapter)
      ? buildInboundBotConfig(form.adapter_config, form.id)
      : { ...(form.adapter_config || {}) };
    setAdapterConfigDraft(formatAdapterConfig(nextAdapterConfig));
    setAdapterConfigError('');
    setForm({
      ...form,
      adapter: nextAdapter,
      transport: adapterUsesTransport(nextAdapter) ? form.transport : 'http',
      adapter_config: nextAdapterConfig,
    });
  };

  const handleAdapterConfigChange = (value: string) => {
    setAdapterConfigDraft(value);
    const trimmed = value.trim();
    if (!trimmed) {
      setAdapterConfigError('');
      setForm({ ...form, adapter_config: {} });
      return;
    }
    try {
      const parsed = JSON.parse(trimmed);
      if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
        setAdapterConfigError(t('teams.external.form.adapterConfigInvalid'));
        return;
      }
      setAdapterConfigError('');
      setForm({ ...form, adapter_config: parsed as Record<string, unknown> });
    } catch {
      setAdapterConfigError(t('teams.external.form.adapterConfigInvalid'));
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 w-full max-w-4xl rounded-2xl bg-white p-6">
        <h3 className="mb-4 text-lg font-semibold text-surface-900">
          {isCreateMode ? t('teams.external.form.createTitle') : t('teams.external.form.editTitle')}
        </h3>

        <div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-2">
          {stepItems.map((step, index) => {
            const active = currentStep === step.id;
            const completed = currentStep > step.id;
            return (
              <button
                key={step.id}
                type="button"
                onClick={() => {
                  if (step.id === 0 || canProceedToBehaviorStep) {
                    setCurrentStep(step.id);
                  }
                }}
                className={`rounded-2xl border p-4 text-left transition-colors ${
                  active
                    ? 'border-primary-500 bg-primary-50'
                    : completed
                      ? 'border-emerald-200 bg-emerald-50/70'
                      : 'border-surface-200 bg-surface-50/70'
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className={`flex h-7 w-7 items-center justify-center rounded-full text-sm font-semibold ${
                    active
                      ? 'bg-primary-500 text-white'
                      : completed
                        ? 'bg-emerald-500 text-white'
                        : 'bg-surface-200 text-surface-600'
                  }`}>
                    {index + 1}
                  </span>
                  <div>
                    <div className="text-sm font-semibold text-surface-900">{step.title}</div>
                    <div className="mt-0.5 text-xs text-surface-500">{step.description}</div>
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        <div className="max-h-[72vh] space-y-5 overflow-y-auto">
          {currentStep === 0 && (
            <div className="space-y-5" data-testid="external-form-step-connection">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <label htmlFor="external-agent-id" className="mb-1 block text-sm font-medium text-surface-700">
                    {t('common.id')}
                  </label>
                  <input
                    id="external-agent-id"
                    type="text"
                    value={form.id}
                    disabled={!isCreateMode}
                    onChange={(event) => setForm({ ...form, id: event.target.value })}
                    className={
                      isCreateMode
                        ? `w-full rounded-lg border px-3 py-2 focus:border-primary-500 focus:ring-2 focus:ring-primary-500 ${
                            createIdError ? 'border-red-300 bg-red-50/40' : 'border-surface-300'
                          }`
                        : 'w-full cursor-not-allowed rounded-lg border border-surface-300 bg-surface-50 px-3 py-2 text-surface-500'
                    }
                    placeholder={t('teams.external.form.idPlaceholder')}
                    aria-invalid={Boolean(createIdError)}
                  />
                  {createIdError && <p className="mt-1 text-xs text-red-600">{createIdError}</p>}
                </div>
                <div>
                  <label htmlFor="external-agent-name" className="mb-1 block text-sm font-medium text-surface-700">
                    {t('common.name')}
                  </label>
                  <input
                    id="external-agent-name"
                    type="text"
                    value={form.name}
                    onChange={(event) => setForm({ ...form, name: event.target.value })}
                    className={`w-full rounded-lg border px-3 py-2 focus:border-primary-500 focus:ring-2 focus:ring-primary-500 ${
                      createNameError ? 'border-red-300 bg-red-50/40' : 'border-surface-300'
                    }`}
                    placeholder={t('teams.external.form.namePlaceholder')}
                    aria-invalid={Boolean(createNameError)}
                  />
                  {createNameError && <p className="mt-1 text-xs text-red-600">{createNameError}</p>}
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="md:col-span-2 rounded-2xl border border-primary-200 bg-primary-50/70 p-4">
                  <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <label htmlFor="external-agent-adapter" className="block text-sm font-semibold text-surface-800">
                      {t('teams.external.form.integrationMode')}
                    </label>
                    <button
                      type="button"
                      data-testid="toggle-external-advanced-adapters"
                      onClick={() => setAdvancedAdapterOpen((value) => !value)}
                      className="self-start rounded-lg border border-primary-200 bg-white px-3 py-1.5 text-xs font-medium text-primary-700 transition-colors hover:bg-primary-100 sm:self-auto"
                    >
                      {advancedAdapterOpen ? t('teams.external.form.hideCompatibilityAdapters') : t('teams.external.form.showCompatibilityAdapters')}
                    </button>
                  </div>
                  {advancedAdapterOpen ? (
                    <select
                      id="external-agent-adapter"
                      value={adapterId}
                      onChange={(event) => handleAdapterChange(event.target.value)}
                      className="w-full rounded-lg border border-primary-200 bg-white px-3 py-2 focus:border-primary-500 focus:ring-2 focus:ring-primary-500"
                    >
                      {visibleAdapterOptions.map((option) => (
                        <option key={option.id} value={option.id}>{option.label}</option>
                      ))}
                    </select>
                  ) : (
                    <div
                      id="external-agent-adapter"
                      className="rounded-xl border border-emerald-200 bg-white px-3 py-2 text-sm font-semibold text-emerald-800"
                    >
                      {selectedAdapter.label}
                    </div>
                  )}
                  <div className="mt-3 rounded-xl border border-white/80 bg-white/70 p-3">
                    <div className="text-sm font-medium text-surface-900">{selectedAdapter.label}</div>
                    <p className="mt-1 text-xs leading-5 text-surface-600">{selectedAdapter.description}</p>
                    <p className="mt-2 text-xs text-primary-700">{t('teams.external.form.adapterHint')}</p>
                    {!advancedAdapterOpen && (
                      <p className="mt-2 text-xs text-emerald-700">{t('teams.external.form.compatibilityAdaptersHint')}</p>
                    )}
                  </div>
                </div>

                {!inboundBotAdapter && (
                <div className="md:col-span-2">
                  <label htmlFor="external-agent-endpoint" className="mb-1 flex items-center gap-2 text-sm font-medium text-surface-700">
                    <span>
                      {adapterId === 'openai-compatible'
                        ? t('teams.external.form.chatCompletionsEndpoint')
                        : t('teams.external.form.endpoint')}
                    </span>
                    {!endpointRequired && (
                      <span className="rounded-full bg-surface-100 px-2 py-0.5 text-[11px] font-medium text-surface-500">
                        {t('common.optional')}
                      </span>
                    )}
                  </label>
                  <input
                    id="external-agent-endpoint"
                    type="text"
                    value={form.endpoint}
                    onChange={(event) => setForm({ ...form, endpoint: event.target.value })}
                    className={`w-full rounded-lg border px-3 py-2 focus:border-primary-500 focus:ring-2 focus:ring-primary-500 ${
                      createEndpointError ? 'border-red-300 bg-red-50/40' : 'border-surface-300'
                    }`}
                    placeholder={
                      adapterId === 'openai-compatible'
                        ? 'https://example.com/v1/chat/completions'
                        : endpointRequired
                          ? t('teams.external.form.endpointPlaceholder')
                          : t('teams.external.form.endpointOptionalPlaceholder')
                    }
                    aria-invalid={Boolean(createEndpointError)}
                  />
                  {createEndpointError
                    ? <p className="mt-1 text-xs text-red-600">{createEndpointError}</p>
                    : (
                      <p className="mt-1 text-xs text-surface-500">
                        {endpointRequired ? t('teams.external.form.endpointHint') : t('teams.external.form.endpointOptionalHint')}
                      </p>
                  )}
                </div>
                )}

                {connectionRecommendation && (
                  <div className="md:col-span-2 rounded-2xl border border-sky-200 bg-sky-50/80 p-4" data-testid="external-connection-recommendation">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="space-y-2">
                        <div className="text-xs font-semibold uppercase tracking-wide text-sky-700">
                          {t('teams.external.form.connectionRecommendedTitle')}
                        </div>
                        <div className="text-sm text-surface-700">{t('teams.external.form.connectionRecommendedBody')}</div>
                        <div className="flex flex-wrap gap-2 text-xs">
                          {connectionRecommendation.updates.transport && (
                            <span className="rounded-full bg-white px-2.5 py-1 text-surface-700 ring-1 ring-sky-200">
                              {t('teams.external.form.connectionRecommendedTransport', {
                                value: t(
                                  connectionRecommendation.updates.transport === 'http_sse'
                                    ? 'teams.external.transport.httpSse'
                                    : connectionRecommendation.updates.transport === 'websocket'
                                      ? 'teams.external.transport.websocket'
                                      : 'teams.external.transport.http',
                                ),
                              })}
                            </span>
                          )}
                          {connectionRecommendation.updates.auth_type && (
                            <span className="rounded-full bg-white px-2.5 py-1 text-surface-700 ring-1 ring-sky-200">
                              {t('teams.external.form.connectionRecommendedAuth', {
                                value: t(
                                  connectionRecommendation.updates.auth_type === 'bearer'
                                    ? 'teams.external.auth.bearer'
                                    : connectionRecommendation.updates.auth_type === 'header'
                                      ? 'teams.external.auth.header'
                                      : 'teams.external.auth.none',
                                ),
                              })}
                            </span>
                          )}
                          {connectionRecommendation.updates.dm_enabled && (
                            <span className="rounded-full bg-white px-2.5 py-1 text-surface-700 ring-1 ring-sky-200">
                              {t('teams.external.form.dmEnabled')}
                            </span>
                          )}
                          {connectionRecommendation.updates.team_enabled && (
                            <span className="rounded-full bg-white px-2.5 py-1 text-surface-700 ring-1 ring-sky-200">
                              {t('teams.external.form.teamEnabled')}
                            </span>
                          )}
                          {connectionRecommendation.updates.mention_required && (
                            <span className="rounded-full bg-white px-2.5 py-1 text-surface-700 ring-1 ring-sky-200">
                              {t('teams.external.form.mentionRequired')}
                            </span>
                          )}
                        </div>
                        <div className="flex flex-wrap gap-2 text-[11px] text-surface-500">
                          {connectionRecommendation.reasons.map((reason) => (
                            <span key={reason} className="rounded-full bg-sky-100 px-2 py-0.5 text-sky-700">
                              {t(`teams.external.form.connectionRecommendedReason.${reason}`)}
                            </span>
                          ))}
                        </div>
                      </div>
                      <button
                        type="button"
                        data-testid="apply-connection-recommendation"
                        onClick={applyConnectionRecommendation}
                        className="shrink-0 rounded-lg border border-sky-300 bg-white px-3 py-2 text-sm font-medium text-sky-700 transition-colors hover:border-sky-400 hover:bg-sky-100"
                      >
                        {t('teams.external.form.connectionRecommendedAction')}
                      </button>
                    </div>
                  </div>
                )}

                {inboundBotAdapter && botAppId && (
                  <div className="md:col-span-2 rounded-2xl border border-emerald-200 bg-emerald-50/80 p-4">
                    <div className="text-sm font-semibold text-emerald-900">{t('teams.external.form.inboundBotTitle')}</div>
                    <p className="mt-1 text-xs leading-5 text-emerald-800">{t('teams.external.form.inboundBotHint')}</p>
                    <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-3">
                      <div>
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700">App ID</div>
                        <div className="mt-1 break-all rounded-lg bg-white px-3 py-2 font-mono text-xs text-surface-800 ring-1 ring-emerald-100">{botAppId}</div>
                      </div>
                      <div>
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700">Token</div>
                        <div className="mt-1 break-all rounded-lg bg-white px-3 py-2 font-mono text-xs text-surface-800 ring-1 ring-emerald-100">{botToken}</div>
                      </div>
                      <div>
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700">Inbound URL</div>
                        <div className="mt-1 break-all rounded-lg bg-white px-3 py-2 font-mono text-xs text-surface-800 ring-1 ring-emerald-100">{inboundUrl}</div>
                      </div>
                    </div>
                  </div>
                )}

                {transportVisible && (
                  <div>
                    <label htmlFor="external-agent-transport" className="mb-1 block text-sm font-medium text-surface-700">
                      {t('teams.external.form.transport')}
                    </label>
                    <select
                      id="external-agent-transport"
                      value={form.transport}
                      onChange={(event) => setForm({ ...form, transport: event.target.value as ExternalAgentFormState['transport'] })}
                      className="w-full rounded-lg border border-surface-300 px-3 py-2 focus:border-primary-500 focus:ring-2 focus:ring-primary-500"
                    >
                      <option value="http_sse">{t('teams.external.transport.httpSse')}</option>
                      <option value="http">{t('teams.external.transport.http')}</option>
                      <option value="websocket">{t('teams.external.transport.websocket')}</option>
                    </select>
                    <p className="mt-1 text-xs text-surface-500">{t('teams.external.form.transportHint')}</p>
                  </div>
                )}
                <div>
                  <label htmlFor="external-agent-avatar" className="mb-1 block text-sm font-medium text-surface-700">
                    {t('teams.external.form.avatar')}
                  </label>
                  <input
                    id="external-agent-avatar"
                    type="text"
                    value={form.avatar}
                    onChange={(event) => setForm({ ...form, avatar: event.target.value })}
                    className="w-full rounded-lg border border-surface-300 px-3 py-2 focus:border-primary-500 focus:ring-2 focus:ring-primary-500"
                    placeholder={t('teams.external.form.avatarPlaceholder')}
                  />
                </div>
              </div>

              <div>
                <label htmlFor="external-agent-description" className="mb-1 block text-sm font-medium text-surface-700">
                  {t('common.description')}
                </label>
                <textarea
                  id="external-agent-description"
                  rows={3}
                  value={form.description}
                  onChange={(event) => setForm({ ...form, description: event.target.value })}
                  className="w-full rounded-lg border border-surface-300 px-3 py-2 focus:border-primary-500 focus:ring-2 focus:ring-primary-500"
                  placeholder={t('teams.external.form.descriptionPlaceholder')}
                />
              </div>

              {!inboundBotAdapter && (
              <div className="rounded-2xl border border-surface-200 bg-surface-50/80 p-4">
                <h4 className="text-sm font-medium text-surface-800">{t('teams.external.form.authSection')}</h4>
                <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-3">
                  <div>
                    <label htmlFor="external-agent-auth-type" className="mb-1 block text-xs font-medium text-surface-600">
                      {t('teams.external.form.authType')}
                    </label>
                    <select
                      id="external-agent-auth-type"
                      value={form.auth_type}
                      onChange={(event) => setForm({ ...form, auth_type: event.target.value as ExternalAgentFormState['auth_type'] })}
                      className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-500"
                    >
                      <option value="none">{t('teams.external.auth.none')}</option>
                      <option value="bearer">{t('teams.external.auth.bearer')}</option>
                      <option value="header">{t('teams.external.auth.header')}</option>
                    </select>
                  </div>
                  <div>
                    <label htmlFor="external-agent-auth-header" className="mb-1 block text-xs font-medium text-surface-600">
                      {t('teams.external.form.authHeader')}
                    </label>
                    <input
                      id="external-agent-auth-header"
                      type="text"
                      value={form.auth_header}
                      onChange={(event) => setForm({ ...form, auth_header: event.target.value })}
                      className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-500"
                      placeholder="Authorization"
                    />
                  </div>
                  <div>
                    <label htmlFor="external-agent-auth-secret" className="mb-1 block text-xs font-medium text-surface-600">
                      {t('teams.external.form.authSecret')}
                    </label>
                    <input
                      id="external-agent-auth-secret"
                      type="password"
                      value={form.auth_secret}
                      onChange={(event) => setForm({ ...form, auth_secret: event.target.value })}
                      className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-500"
                      placeholder={t('teams.external.form.authSecretPlaceholder')}
                    />
                    {!isCreateMode && form.auth_secret_configured && (
                      <p className="mt-1 text-xs text-surface-500">{t('teams.external.form.authSecretKeepHint')}</p>
                    )}
                  </div>
                </div>
              </div>
              )}
            </div>
          )}

          {currentStep === 1 && (
            <div className="space-y-5" data-testid="external-form-step-behavior">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="space-y-3">
                  <div>
                    <label className="mb-1 block text-sm font-medium text-surface-700">
                      {t('teams.external.form.capabilities')}
                    </label>
                    <p className="text-xs text-surface-500">{t('teams.external.form.capabilitiesHint')}</p>
                  </div>

                  {recommendedPreset && (
                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50/80 p-4" data-testid="external-capability-recommendation">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <div className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
                            {t('teams.external.form.capabilitiesRecommendedTitle')}
                          </div>
                          <div className="mt-1 text-sm font-semibold text-surface-900">
                            {t('teams.external.form.capabilitiesRecommendedBody', { label: recommendedPreset.label })}
                          </div>
                          <div className="mt-1 text-xs text-surface-600">{recommendedPreset.summary}</div>
                        </div>
                        <button
                          type="button"
                          onClick={() => applyCapabilityPreset(recommendedPreset.capabilities)}
                          className="shrink-0 rounded-lg border border-emerald-300 bg-white px-3 py-2 text-sm font-medium text-emerald-700 transition-colors hover:border-emerald-400 hover:bg-emerald-100"
                        >
                          {t('teams.external.form.capabilitiesRecommendedAction')}
                        </button>
                      </div>
                    </div>
                  )}

                  <div className="rounded-2xl border border-primary-200 bg-primary-50/70 p-4">
                    <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-primary-700">
                      {t('teams.external.form.capabilitiesPresetTitle')}
                    </div>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {capabilityPresets.map((preset) => {
                        const active = preset.capabilities.every((item) => selectedCapabilities.some((selected) => selected.toLowerCase() === item.toLowerCase()));
                        const recommended = preset.id === recommendedPresetId;
                        return (
                          <button
                            key={preset.id}
                            type="button"
                            onClick={() => applyCapabilityPreset(preset.capabilities)}
                            data-testid={`external-capability-preset-${preset.id}`}
                            className={`rounded-xl border px-3 py-3 text-left transition-colors ${
                              active
                                ? 'border-primary-500 bg-white shadow-sm'
                                : recommended
                                  ? 'border-emerald-300 bg-white shadow-sm'
                                  : 'border-primary-100 bg-white/80 hover:border-primary-300 hover:bg-white'
                            }`}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div className="text-sm font-semibold text-surface-900">{preset.label}</div>
                              <div className="flex items-center gap-1">
                                {recommended && (
                                  <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-700">
                                    {t('teams.external.form.capabilitiesRecommendedBadge')}
                                  </span>
                                )}
                                <span className="rounded-full bg-primary-100 px-2 py-0.5 text-[10px] font-medium text-primary-700">
                                  {t('teams.external.form.capabilitiesPresetApply')}
                                </span>
                              </div>
                            </div>
                            <div className="mt-1 text-xs text-surface-600">{preset.summary}</div>
                            <div className="mt-2 flex flex-wrap gap-1">
                              {preset.capabilities.map((capabilityId) => {
                                const capability = capabilityMetaById.get(capabilityId.toLowerCase());
                                return (
                                  <span key={capabilityId} className="rounded-full bg-surface-100 px-2 py-0.5 text-[10px] text-surface-600">
                                    {capability?.label || capabilityId}
                                  </span>
                                );
                              })}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div className="rounded-2xl border border-surface-200 bg-white p-4">
                    <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-surface-500">
                      {t('teams.external.form.capabilitiesSelected')}
                    </div>
                    {selectedCapabilities.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {selectedCapabilities.map((capability) => {
                          const capabilityMeta = capabilityMetaById.get(capability.toLowerCase());
                          return (
                            <button
                              key={capability}
                              type="button"
                              onClick={() => toggleCapability(capability)}
                              data-testid={`selected-capability-${capability.toLowerCase()}`}
                              className="inline-flex items-center gap-2 rounded-full border border-primary-200 bg-primary-50 px-3 py-1.5 text-sm text-primary-700 transition-colors hover:border-primary-300 hover:bg-primary-100"
                            >
                              <span>{capabilityMeta?.label || capability}</span>
                              <span className="text-xs text-primary-500">×</span>
                            </button>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="text-sm text-surface-500">{t('teams.external.form.capabilitiesEmpty')}</p>
                    )}
                  </div>

                  <div className="rounded-2xl border border-surface-200 bg-surface-50/80 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <h4 className="text-sm font-medium text-surface-800">{t('teams.external.form.manualCapabilitySection')}</h4>
                        <p className="mt-1 text-xs text-surface-500">{t('teams.external.form.manualCapabilityHint')}</p>
                      </div>
                      <button
                        type="button"
                        data-testid="toggle-manual-capabilities"
                        onClick={() => setManualCapabilityOpen((current) => !current)}
                        className="inline-flex items-center justify-center gap-2 rounded-xl border border-surface-300 bg-white px-3 py-2 text-sm font-medium text-surface-700 transition-colors hover:border-primary-300 hover:text-primary-700"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className={`h-4 w-4 transition-transform ${manualCapabilityOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                        {manualCapabilityOpen ? t('teams.external.form.manualCapabilityCollapse') : t('teams.external.form.manualCapabilityExpand')}
                      </button>
                    </div>
                    {manualCapabilityOpen && (
                      <div className="mt-4 space-y-4">
                        <div>
                          <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-surface-500">
                            {t('teams.external.form.capabilitiesQuickPick')}
                          </div>
                          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                            {capabilityOptions.map((option) => {
                              const selected = selectedCapabilities.some((item) => item.toLowerCase() === option.id.toLowerCase());
                              return (
                                <button
                                  key={option.id}
                                  type="button"
                                  onClick={() => toggleCapability(option.id)}
                                  aria-pressed={selected}
                                  className={`rounded-xl border px-3 py-3 text-left transition-colors ${
                                    selected
                                      ? 'border-primary-500 bg-primary-50 shadow-sm'
                                      : 'border-surface-200 bg-white hover:border-primary-200 hover:bg-primary-50/40'
                                  }`}
                                >
                                  <div className="text-sm font-medium text-surface-900">{option.label}</div>
                                  <div className="mt-1 text-xs text-surface-500">{option.description}</div>
                                </button>
                              );
                            })}
                          </div>
                        </div>

                        <div>
                          <label htmlFor="external-agent-capabilities-custom" className="mb-1 block text-sm font-medium text-surface-700">
                            {t('teams.external.form.capabilitiesCustomLabel')}
                          </label>
                          <div className="flex gap-2">
                            <input
                              id="external-agent-capabilities-custom"
                              type="text"
                              value={customCapabilityInput}
                              onChange={(event) => setCustomCapabilityInput(event.target.value)}
                              onKeyDown={handleCustomCapabilityKeyDown}
                              className="w-full rounded-lg border border-surface-300 px-3 py-2 focus:border-primary-500 focus:ring-2 focus:ring-primary-500"
                              placeholder={t('teams.external.form.capabilitiesCustomPlaceholder')}
                            />
                            <button
                              type="button"
                              onClick={handleAddCustomCapabilities}
                              className="rounded-lg border border-surface-300 px-3 py-2 text-sm font-medium text-surface-700 transition-colors hover:border-primary-300 hover:text-primary-700"
                            >
                              {t('teams.external.form.capabilitiesAdd')}
                            </button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                <div className="space-y-3 rounded-2xl border border-surface-200 bg-surface-50/80 p-4">
                  <h4 className="text-sm font-medium text-surface-800">{t('teams.external.form.accessSection')}</h4>
                  <label className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={form.dm_enabled}
                      onChange={(event) => setForm({ ...form, dm_enabled: event.target.checked })}
                      className="mt-1 rounded border-surface-300 text-primary-500 focus:ring-primary-500"
                    />
                    <span>
                      <span className="block text-sm font-medium text-surface-800">{t('teams.external.form.dmEnabled')}</span>
                      <span className="block text-xs text-surface-500">{t('teams.external.form.dmEnabledHint')}</span>
                    </span>
                  </label>
                  <label className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={form.team_enabled}
                      onChange={(event) => setForm({ ...form, team_enabled: event.target.checked })}
                      className="mt-1 rounded border-surface-300 text-primary-500 focus:ring-primary-500"
                    />
                    <span>
                      <span className="block text-sm font-medium text-surface-800">{t('teams.external.form.teamEnabled')}</span>
                      <span className="block text-xs text-surface-500">{t('teams.external.form.teamEnabledHint')}</span>
                    </span>
                  </label>
                  <label className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={form.mention_required}
                      onChange={(event) => setForm({ ...form, mention_required: event.target.checked })}
                      className="mt-1 rounded border-surface-300 text-primary-500 focus:ring-primary-500"
                    />
                    <span>
                      <span className="block text-sm font-medium text-surface-800">{t('teams.external.form.mentionRequired')}</span>
                      <span className="block text-xs text-surface-500">{t('teams.external.form.mentionRequiredHint')}</span>
                    </span>
                  </label>
                </div>
              </div>

              <div className="rounded-2xl border border-surface-200 bg-white p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h4 className="text-sm font-medium text-surface-800">{t('teams.external.form.runtimeSection')}</h4>
                    <p className="mt-1 text-xs text-surface-500">{t('teams.external.form.runtimeHint')}</p>
                  </div>
                  <button
                    type="button"
                    data-testid="toggle-runtime-settings"
                    onClick={() => setRuntimeOpen((current) => !current)}
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-surface-300 bg-white px-3 py-2 text-sm font-medium text-surface-700 transition-colors hover:border-primary-300 hover:text-primary-700"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className={`h-4 w-4 transition-transform ${runtimeOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                    {runtimeOpen ? t('teams.external.form.runtimeCollapse') : t('teams.external.form.runtimeExpand')}
                  </button>
                </div>
                {runtimeOpen && (
                  <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <div>
                      <label htmlFor="external-agent-timeout" className="mb-1 block text-xs font-medium text-surface-600">
                        {t('teams.external.form.timeout')}
                      </label>
                      <input
                        id="external-agent-timeout"
                        type="number"
                        min={5}
                        value={form.timeout_s}
                        onChange={(event) => setForm({ ...form, timeout_s: Number(event.target.value) || 90 })}
                        className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-500"
                      />
                    </div>
                    <div>
                      <label htmlFor="external-agent-max-turn" className="mb-1 block text-xs font-medium text-surface-600">
                        {t('teams.external.form.maxTurnChars')}
                      </label>
                      <input
                        id="external-agent-max-turn"
                        type="number"
                        min={1000}
                        step={500}
                        value={form.max_turn_chars}
                        onChange={(event) => setForm({ ...form, max_turn_chars: Number(event.target.value) || 12000 })}
                        className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-500"
                      />
                    </div>
                    <div>
                      <label htmlFor="external-agent-context-scope" className="mb-1 block text-xs font-medium text-surface-600">
                        {t('teams.external.form.contextScope')}
                      </label>
                      <select
                        id="external-agent-context-scope"
                        value={form.context_scope}
                        onChange={(event) => setForm({ ...form, context_scope: event.target.value as ExternalAgentFormState['context_scope'] })}
                        className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-500"
                      >
                        <option value="message_only">{t('teams.external.contextScope.messageOnly')}</option>
                        <option value="recent_turns">{t('teams.external.contextScope.recentTurns')}</option>
                        <option value="dm_summary">{t('teams.external.contextScope.dmSummary')}</option>
                      </select>
                    </div>
                    <div>
                      <label htmlFor="external-agent-memory-access" className="mb-1 block text-xs font-medium text-surface-600">
                        {t('teams.external.form.memoryAccess')}
                      </label>
                      <select
                        id="external-agent-memory-access"
                        value={form.memory_access}
                        onChange={(event) => setForm({ ...form, memory_access: event.target.value as ExternalAgentFormState['memory_access'] })}
                        className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-500"
                      >
                        <option value="none">{t('teams.external.memoryAccess.none')}</option>
                        <option value="summary_only">{t('teams.external.memoryAccess.summaryOnly')}</option>
                      </select>
                    </div>
                    <div>
                      <label htmlFor="external-agent-file-access" className="mb-1 block text-xs font-medium text-surface-600">
                        {t('teams.external.form.fileAccess')}
                      </label>
                      <select
                        id="external-agent-file-access"
                        value={form.file_access}
                        onChange={(event) => setForm({ ...form, file_access: event.target.value as ExternalAgentFormState['file_access'] })}
                        className="w-full rounded-lg border border-surface-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-500"
                      >
                        <option value="none">{t('teams.external.fileAccess.none')}</option>
                        <option value="referenced_only">{t('teams.external.fileAccess.referencedOnly')}</option>
                      </select>
                    </div>
                    <div className="md:col-span-2 xl:col-span-4">
                      <label htmlFor="external-agent-adapter-config" className="mb-1 block text-xs font-medium text-surface-600">
                        {t('teams.external.form.adapterConfig')}
                      </label>
                      <textarea
                        id="external-agent-adapter-config"
                        rows={5}
                        value={adapterConfigDraft}
                        onChange={(event) => handleAdapterConfigChange(event.target.value)}
                        className={`w-full rounded-lg border px-3 py-2 font-mono text-xs focus:border-primary-500 focus:ring-2 focus:ring-primary-500 ${
                          adapterConfigError ? 'border-red-300 bg-red-50/40' : 'border-surface-300'
                        }`}
                        placeholder='{"model":"gpt-4o-mini"}'
                        aria-invalid={Boolean(adapterConfigError)}
                      />
                      {adapterConfigError
                        ? <p className="mt-1 text-xs text-red-600">{adapterConfigError}</p>
                        : <p className="mt-1 text-xs text-surface-500">{t('teams.external.form.adapterConfigHint')}</p>}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="rounded-lg border border-surface-300 px-4 py-2 text-surface-700 hover:bg-surface-50"
          >
            {t('common.cancel')}
          </button>
          {currentStep === 1 && (
            <button
              type="button"
              onClick={() => setCurrentStep(0)}
              className="rounded-lg border border-surface-300 px-4 py-2 text-surface-700 hover:bg-surface-50"
            >
              {t('common.previous')}
            </button>
          )}
          {currentStep === 0 ? (
            <button
              type="button"
              data-testid="external-form-next"
              onClick={() => setCurrentStep(1)}
              disabled={!canProceedToBehaviorStep}
              className="rounded-lg bg-primary-500 px-4 py-2 text-white transition-colors hover:bg-primary-600 disabled:cursor-not-allowed disabled:bg-surface-300"
            >
              {t('common.next')}
            </button>
          ) : (
            <button
              onClick={onSubmit}
              disabled={submitDisabled || Boolean(adapterConfigError)}
              className="rounded-lg bg-primary-500 px-4 py-2 text-white transition-colors hover:bg-primary-600 disabled:cursor-not-allowed disabled:bg-surface-300"
            >
              {isCreateMode ? t('common.create') : t('common.save')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default ExternalAgentFormModal;
