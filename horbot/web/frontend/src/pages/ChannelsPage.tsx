import React, { useEffect, useState } from 'react';
import { channelsService } from '../services';
import { useI18n } from '../contexts/I18nContext';
import type {
  ChannelCatalogEntry,
  ChannelEndpoint,
  ChannelEndpointDraftTestResponse,
  ChannelEndpointEvent,
  ChannelEndpointEventsResponse,
  ChannelEndpointTestResponse,
  ChannelEndpointPayload,
  ChannelEndpointsResponse,
} from '../types';
import { Badge, Button, Card, CardContent, Empty, Input, Select, Skeleton, Textarea } from '../components/ui';

type EndpointFormSource = 'custom' | 'legacy' | 'draft';

interface EndpointFormState {
  id?: string;
  type: string;
  name: string;
  agent_id: string;
  enabled: boolean;
  allow_from_text: string;
  config: Record<string, unknown>;
  source: EndpointFormSource;
}

type TranslateFn = (key: string, values?: Record<string, number | string>) => string;

const defaultResponse: ChannelEndpointsResponse = {
  endpoints: [],
  catalog: [],
  agents: [],
  counts: {
    total: 0,
    enabled: 0,
    ready: 0,
    incomplete: 0,
  },
};

const parseAllowFrom = (value: string): string[] =>
  value
    .split(/[\n,]/)
    .map(item => item.trim())
    .filter(Boolean);

const buildFormFromEndpoint = (endpoint: ChannelEndpoint): EndpointFormState => ({
  id: endpoint.id,
  type: endpoint.type,
  name: endpoint.name,
  agent_id: endpoint.agent_id,
  enabled: endpoint.enabled,
  allow_from_text: (endpoint.allow_from || []).join('\n'),
  config: { ...(endpoint.config || {}) },
  source: endpoint.source,
});

const buildDraftForm = (catalog: ChannelCatalogEntry[], agentId: string): EndpointFormState => ({
  type: catalog[0]?.type || 'telegram',
  name: '',
  agent_id: agentId,
  enabled: true,
  allow_from_text: '',
  config: {},
  source: 'draft',
});

const statusVariant = (status: ChannelEndpoint['status']) => {
  if (status === 'ready') {
    return 'success';
  }
  if (status === 'incomplete') {
    return 'warning';
  }
  return 'default';
};

const hasConfiguredValue = (value: unknown) => {
  if (typeof value === 'boolean') {
    return true;
  }
  if (typeof value === 'number') {
    return Number.isFinite(value);
  }
  if (Array.isArray(value)) {
    return value.length > 0;
  }
  return value !== undefined && value !== null && String(value).trim() !== '';
};

type ConnectionResultLike =
  ChannelEndpointTestResponse['result']
  | ChannelEndpointDraftTestResponse['result'];

type ConnectionErrorKind =
  | 'missing'
  | 'credential'
  | 'permission'
  | 'timeout'
  | 'dns'
  | 'ssl'
  | 'rate_limit'
  | 'generic';

const normalizeConnectionError = (value?: string | null) => String(value || '').trim().toLowerCase();

const detectConnectionErrorKind = (rawError: string): ConnectionErrorKind => {
  if (!rawError) {
    return 'generic';
  }

  if (
    rawError.includes('not configured')
    || rawError.includes('missing')
    || rawError.includes('required')
    || rawError.includes('empty')
  ) {
    return 'missing';
  }

  if (
    rawError.includes('401')
    || rawError.includes('invalid token')
    || rawError.includes('invalid access token')
    || rawError.includes('invalid_auth')
    || rawError.includes('authentication failed')
    || rawError.includes('login failed')
    || rawError.includes('app id or secret')
    || rawError.includes('client id or secret')
    || rawError.includes('bot token')
    || rawError.includes('app token')
    || rawError.includes('secret')
  ) {
    return 'credential';
  }

  if (
    rawError.includes('403')
    || rawError.includes('forbidden')
    || rawError.includes('permission')
    || rawError.includes('scope')
    || rawError.includes('not allowed')
    || rawError.includes('insufficient')
    || rawError.includes('no authority')
  ) {
    return 'permission';
  }

  if (rawError.includes('timeout') || rawError.includes('timed out')) {
    return 'timeout';
  }

  if (
    rawError.includes('resolve')
    || rawError.includes('name or service not known')
    || rawError.includes('nodename nor servname')
    || rawError.includes('dns')
    || rawError.includes('getaddrinfo')
  ) {
    return 'dns';
  }

  if (rawError.includes('ssl') || rawError.includes('certificate') || rawError.includes('tls')) {
    return 'ssl';
  }

  if (rawError.includes('429') || rawError.includes('rate limit') || rawError.includes('too many requests')) {
    return 'rate_limit';
  }

  return 'generic';
};

const getChannelSpecificHints = (t: TranslateFn, channelType: string, kind: ConnectionErrorKind): string[] => {
  switch (channelType) {
    case 'feishu':
      if (kind === 'missing') {
        return [
          t('channels.hint.feishu.missing1'),
          t('channels.hint.feishu.missing2'),
        ];
      }
      if (kind === 'credential') {
        return [
          t('channels.hint.feishu.credential1'),
          t('channels.hint.feishu.credential2'),
        ];
      }
      if (kind === 'permission') {
        return [
          t('channels.hint.feishu.permission1'),
          t('channels.hint.feishu.permission2'),
        ];
      }
      if (kind === 'ssl') {
        return [
          t('channels.hint.feishu.ssl1'),
        ];
      }
      return [
        t('channels.hint.feishu.generic1'),
      ];

    case 'sharecrm':
      if (kind === 'missing') {
        return [
          t('channels.hint.sharecrm.missing1'),
          t('channels.hint.sharecrm.missing2'),
        ];
      }
      if (kind === 'credential' || kind === 'permission') {
        return [
          t('channels.hint.sharecrm.credential1'),
          t('channels.hint.sharecrm.credential2'),
        ];
      }
      return [
        t('channels.hint.sharecrm.generic1'),
      ];

    case 'wecom':
      if (kind === 'missing') {
        return [
          t('channels.hint.wecom.missing1'),
          t('channels.hint.wecom.missing2'),
        ];
      }
      if (kind === 'credential' || kind === 'permission') {
        return [
          t('channels.hint.wecom.credential1'),
          t('channels.hint.wecom.credential2'),
        ];
      }
      return [
        t('channels.hint.wecom.generic1'),
      ];

    case 'telegram':
      if (kind === 'credential' || kind === 'missing') {
        return [
          t('channels.hint.telegram.credential1'),
          t('channels.hint.telegram.credential2'),
        ];
      }
      return [
        t('channels.hint.telegram.generic1'),
      ];

    case 'slack':
      if (kind === 'credential' || kind === 'missing') {
        return [
          t('channels.hint.slack.credential1'),
          t('channels.hint.slack.credential2'),
        ];
      }
      if (kind === 'permission') {
        return [
          t('channels.hint.slack.permission1'),
          t('channels.hint.slack.permission2'),
        ];
      }
      return [
        t('channels.hint.slack.generic1'),
      ];

    case 'discord':
      if (kind === 'credential' || kind === 'missing') {
        return [
          t('channels.hint.discord.credential1'),
        ];
      }
      if (kind === 'permission') {
        return [
          t('channels.hint.discord.permission1'),
          t('channels.hint.discord.permission2'),
        ];
      }
      return [
        t('channels.hint.discord.generic1'),
      ];

    case 'email':
      if (kind === 'missing') {
        return [
          t('channels.hint.email.missing1'),
        ];
      }
      if (kind === 'credential') {
        return [
          t('channels.hint.email.credential1'),
          t('channels.hint.email.credential2'),
        ];
      }
      if (kind === 'ssl') {
        return [
          t('channels.hint.email.ssl1'),
        ];
      }
      return [
        t('channels.hint.email.generic1'),
      ];

    case 'dingtalk':
      if (kind === 'credential' || kind === 'missing') {
        return [
          t('channels.hint.dingtalk.credential1'),
        ];
      }
      if (kind === 'permission') {
        return [
          t('channels.hint.dingtalk.permission1'),
        ];
      }
      return [];

    case 'matrix':
      if (kind === 'credential' || kind === 'missing') {
        return [
          t('channels.hint.matrix.credential1'),
        ];
      }
      return [
        t('channels.hint.matrix.generic1'),
      ];

    case 'mochat':
      if (kind === 'credential' || kind === 'missing') {
        return [
          t('channels.hint.mochat.credential1'),
        ];
      }
      return [
        t('channels.hint.mochat.generic1'),
      ];

    case 'qq':
      if (kind === 'credential' || kind === 'missing') {
        return [
          t('channels.hint.qq.credential1'),
        ];
      }
      return [];

    case 'whatsapp':
      if (kind === 'credential' || kind === 'missing') {
        return [
          t('channels.hint.whatsapp.credential1'),
        ];
      }
      return [
        t('channels.hint.whatsapp.generic1'),
      ];

    default:
      return [];
  }
};

const getConnectionFeedback = (t: TranslateFn, result?: ConnectionResultLike | null, channelType?: string | null) => {
  if (!result) {
    return null;
  }

  const resolvedChannelType = String(channelType || result.name || '').trim().toLowerCase();
  const backendKind = String(result.error_kind || '').trim().toLowerCase();
  const backendRemediation = Array.isArray(result.remediation) ? result.remediation.filter(Boolean) : [];

  if (result.status === 'ok') {
    return {
      tone: 'success' as const,
      title: t('channels.feedback.ok.title'),
      summary: t('channels.feedback.ok.summary'),
      hints: [
        t('channels.feedback.ok.hint1'),
        t('channels.feedback.ok.hint2'),
      ],
    };
  }

  const rawError = normalizeConnectionError(result.error);
  const kind = (backendKind || detectConnectionErrorKind(rawError)) as ConnectionErrorKind;
  const channelHints = backendRemediation.length > 0
    ? backendRemediation
    : getChannelSpecificHints(t, resolvedChannelType, kind);

  if (kind === 'missing') {
    return {
      tone: 'warning' as const,
      title: t('channels.feedback.missing.title'),
      summary: t('channels.feedback.missing.summary'),
      hints: [
        t('channels.feedback.missing.hint1'),
        ...channelHints,
      ],
    };
  }

  if (kind === 'credential') {
    return {
      tone: 'warning' as const,
      title: t('channels.feedback.credential.title'),
      summary: t('channels.feedback.credential.summary'),
      hints: [
        t('channels.feedback.credential.hint1'),
        t('channels.feedback.credential.hint2'),
        ...channelHints,
      ],
    };
  }

  if (kind === 'permission') {
    return {
      tone: 'warning' as const,
      title: t('channels.feedback.permission.title'),
      summary: t('channels.feedback.permission.summary'),
      hints: [
        t('channels.feedback.permission.hint1'),
        ...channelHints,
      ],
    };
  }

  if (kind === 'timeout') {
    return {
      tone: 'warning' as const,
      title: t('channels.feedback.timeout.title'),
      summary: t('channels.feedback.timeout.summary'),
      hints: [
        t('channels.feedback.timeout.hint1'),
        t('channels.feedback.timeout.hint2'),
        ...channelHints,
      ],
    };
  }

  if (kind === 'dns') {
    return {
      tone: 'warning' as const,
      title: t('channels.feedback.dns.title'),
      summary: t('channels.feedback.dns.summary'),
      hints: [
        t('channels.feedback.dns.hint1'),
        t('channels.feedback.dns.hint2'),
        ...channelHints,
      ],
    };
  }

  if (kind === 'ssl') {
    return {
      tone: 'warning' as const,
      title: t('channels.feedback.ssl.title'),
      summary: t('channels.feedback.ssl.summary'),
      hints: [
        t('channels.feedback.ssl.hint1'),
        t('channels.feedback.ssl.hint2'),
        ...channelHints,
      ],
    };
  }

  if (kind === 'rate_limit') {
    return {
      tone: 'warning' as const,
      title: t('channels.feedback.rateLimit.title'),
      summary: t('channels.feedback.rateLimit.summary'),
      hints: [
        t('channels.feedback.rateLimit.hint1'),
        t('channels.feedback.rateLimit.hint2'),
        ...channelHints,
      ],
    };
  }

  return {
    tone: 'warning' as const,
    title: t('channels.feedback.generic.title'),
    summary: t('channels.feedback.generic.summary'),
    hints: [
      t('channels.feedback.generic.hint1'),
      t('channels.feedback.generic.hint2'),
      ...channelHints,
    ],
  };
};

const ChannelsPage: React.FC = () => {
  const { intlLocale, t } = useI18n();
  const [data, setData] = useState<ChannelEndpointsResponse>(defaultResponse);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedEndpointId, setSelectedEndpointId] = useState<string | null>(null);
  const [form, setForm] = useState<EndpointFormState | null>(null);
  const [eventsData, setEventsData] = useState<ChannelEndpointEventsResponse | null>(null);
  const [testResult, setTestResult] = useState<ChannelEndpointTestResponse | null>(null);
  const [draftTestResult, setDraftTestResult] = useState<ChannelEndpointDraftTestResponse | null>(null);
  const [draftStep, setDraftStep] = useState(1);
  const getStatusLabel = (status: ChannelEndpoint['status']) => {
    if (status === 'ready') return t('common.online');
    if (status === 'incomplete') return t('dashboard.channels.missingConfig');
    return t('common.notAvailable');
  };
  const formatDateTimeLocal = (value?: string | null) => {
    if (!value) {
      return t('common.notAvailable');
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return date.toLocaleString(intlLocale, { hour12: false });
  };

  const loadEndpoints = async (showRefreshLoader = false, preferredEndpointId?: string | null) => {
    if (showRefreshLoader) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    setError(null);

    try {
      const response = await channelsService.getEndpoints();
      setData(response);

      const nextSelectedId = preferredEndpointId !== undefined
        ? preferredEndpointId
        : (selectedEndpointId ?? response.endpoints[0]?.id ?? null);

      const selectedEndpoint = response.endpoints.find(item => item.id === nextSelectedId);

      if (selectedEndpoint) {
        setSelectedEndpointId(selectedEndpoint.id);
        setForm(buildFormFromEndpoint(selectedEndpoint));
        setDraftStep(1);
        setDraftTestResult(null);
        if (selectedEndpoint.id) {
          try {
            const events = await channelsService.getEndpointEvents(selectedEndpoint.id, 12);
            setEventsData(events);
          } catch (eventsError) {
            console.error('Failed to fetch endpoint events:', eventsError);
            setEventsData(null);
          }
        }
      } else if (response.catalog.length > 0) {
        const defaultAgentId = response.agents[0]?.id || '';
        setSelectedEndpointId(null);
        setForm(buildDraftForm(response.catalog, defaultAgentId));
        setEventsData(null);
        setDraftStep(1);
        setDraftTestResult(null);
      } else {
        setSelectedEndpointId(null);
        setForm(null);
        setEventsData(null);
        setDraftStep(1);
        setDraftTestResult(null);
      }
      setTestResult(null);
    } catch (err) {
      console.error('Failed to fetch channel endpoints:', err);
      setError(t('channels.loadFailed'));
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    void loadEndpoints();
  }, []);

  const isDraft = form?.source === 'draft';
  const selectedCatalog = data.catalog.find(item => item.type === form?.type) || null;
  const requiredFieldKeys = selectedCatalog?.required_fields || [];
  const requiredCatalogFields = selectedCatalog?.fields.filter(field => requiredFieldKeys.includes(field.key)) || [];
  const optionalCatalogFields = selectedCatalog?.fields.filter(field => !requiredFieldKeys.includes(field.key)) || [];
  const routeOverview = data.agents.map(agent => {
    const endpoints = data.endpoints.filter(endpoint => endpoint.agent_id === agent.id);
    return {
      ...agent,
      endpoints,
      readyCount: endpoints.filter(endpoint => endpoint.status === 'ready').length,
    };
  });
  const unboundEndpoints = data.endpoints.filter(endpoint => !endpoint.agent_id);
  const isHorbotInboundBotSelected = form?.type === 'horbot-inbound-bot';
  const agentBindingOptional = isHorbotInboundBotSelected;
  const draftStepOneReady = Boolean(form?.type && (form?.agent_id || agentBindingOptional));
  const draftStepTwoReady = requiredFieldKeys.every(fieldKey => hasConfiguredValue(form?.config?.[fieldKey]));
  const draftMissingFields = requiredFieldKeys.filter(fieldKey => !hasConfiguredValue(form?.config?.[fieldKey]));
  const draftTestPassed = draftTestResult?.result.status === 'ok';
  const canRunDraftTest = Boolean(isDraft && draftStepTwoReady && form?.type);
  const draftConnectionFeedback = getConnectionFeedback(t, draftTestResult?.result, form?.type);
  const savedConnectionFeedback = getConnectionFeedback(t, testResult?.result, form?.type);
  const inboundBotAppId = typeof form?.config?.bot_app_id === 'string' ? form.config.bot_app_id : '';
  const inboundBotToken = typeof form?.config?.bot_token === 'string' ? form.config.bot_token : '';
  const inboundBotPath = typeof form?.config?.inbound_url_path === 'string' ? form.config.inbound_url_path : '';
  const inboundBotUrl = inboundBotPath
    ? (inboundBotPath.startsWith('http') ? inboundBotPath : `${window.location.origin}${inboundBotPath}`)
    : '';
  const hasInboundBotCredentials = Boolean(inboundBotAppId || inboundBotToken || inboundBotUrl);

  const renderInboundBotCredentials = () => {
    if (!isHorbotInboundBotSelected || !hasInboundBotCredentials) {
      return null;
    }

    const values = [
      { label: t('channels.inboundBotAppId'), value: inboundBotAppId },
      { label: t('channels.inboundBotToken'), value: inboundBotToken },
      { label: t('channels.inboundBotInboundUrl'), value: inboundBotUrl || inboundBotPath },
    ].filter(item => item.value);

    return (
      <div className="rounded-2xl border border-emerald-200 bg-emerald-50/80 p-4">
        <div className="text-sm font-semibold text-emerald-900">{t('channels.inboundBotCredentialsTitle')}</div>
        <p className="mt-1 text-xs leading-5 text-emerald-800">{t('channels.inboundBotCredentialsHint')}</p>
        <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-3">
          {values.map(item => (
            <div key={item.label}>
              <div className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700">{item.label}</div>
              <div className="mt-1 break-all rounded-lg bg-white px-3 py-2 font-mono text-xs text-surface-800 ring-1 ring-emerald-100">
                {item.value}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderChannelField = (field: ChannelCatalogEntry['fields'][number]) => {
    const rawValue = form?.config?.[field.key];
    if (field.type === 'boolean') {
      return (
        <div key={field.key} className="rounded-2xl border border-surface-200 bg-white px-4 py-4">
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-surface-300 text-primary-600 focus:ring-primary-500"
              checked={Boolean(rawValue)}
              onChange={(event) => handleConfigChange(field.key, event.target.checked)}
            />
            <span className="text-sm font-medium text-surface-700">{field.label}</span>
          </label>
        </div>
      );
    }

    return (
      <Input
        key={field.key}
        label={field.label}
        type={field.secret ? 'password' : field.type === 'number' ? 'number' : 'text'}
        disabled={Boolean(field.readonly)}
        value={rawValue === undefined || rawValue === null ? '' : String(rawValue)}
        onChange={(event) => {
          const nextValue = field.type === 'number'
            ? (event.target.value === '' ? '' : Number(event.target.value))
            : event.target.value;
          handleConfigChange(field.key, nextValue);
        }}
        placeholder={field.placeholder}
      />
    );
  };

  const handleSelectEndpoint = (endpoint: ChannelEndpoint) => {
    setSelectedEndpointId(endpoint.id);
    setForm(buildFormFromEndpoint(endpoint));
    setDraftStep(1);
    setDraftTestResult(null);
    setTestResult(null);
    void channelsService.getEndpointEvents(endpoint.id, 12)
      .then(setEventsData)
      .catch(eventsError => {
        console.error('Failed to fetch endpoint events:', eventsError);
        setEventsData(null);
      });
  };

  const handleCreateEndpoint = () => {
    const defaultAgentId = data.agents[0]?.id || '';
    setSelectedEndpointId(null);
    setForm(buildDraftForm(data.catalog, defaultAgentId));
    setEventsData(null);
    setTestResult(null);
    setDraftTestResult(null);
    setDraftStep(1);
  };

  const handleFieldChange = (key: keyof EndpointFormState, value: string | boolean) => {
    if (isDraft) {
      setDraftTestResult(null);
    }
    setForm(current => (current ? { ...current, [key]: value } : current));
  };

  const handleConfigChange = (key: string, value: unknown) => {
    if (isDraft) {
      setDraftTestResult(null);
    }
    setForm(current => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        config: {
          ...current.config,
          [key]: value,
        },
      };
    });
  };

  const handleTypeChange = (channelType: string) => {
    const catalogEntry = data.catalog.find(item => item.type === channelType);
    setDraftTestResult(null);
    setForm(current => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        type: channelType,
        name: current.source === 'draft' ? '' : current.name,
        config: catalogEntry
          ? catalogEntry.fields.reduce<Record<string, unknown>>((acc, field) => {
              acc[field.key] = current.config[field.key] ?? (field.type === 'boolean' ? false : '');
              return acc;
            }, {})
          : current.config,
      };
    });
  };

  const buildPayload = (): ChannelEndpointPayload | null => {
    if (!form) {
      return null;
    }
    return {
      id: form.id,
      type: form.type,
      name: form.name.trim(),
      agent_id: form.agent_id,
      enabled: form.enabled,
      allow_from: parseAllowFrom(form.allow_from_text),
      config: form.config,
    };
  };

  const handleSave = async () => {
    const payload = buildPayload();
    if (!payload) {
      return;
    }

    if (!payload.type) {
      setError(t('channels.errorSelectType'));
      return;
    }
    if (form?.source === 'draft' && !draftTestPassed) {
      setError(t('channels.errorDraftTestRequired'));
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      let savedEndpoint: ChannelEndpoint | null = null;
      if (form?.source === 'draft') {
        savedEndpoint = await channelsService.createEndpoint(payload);
      } else if (form?.id) {
        savedEndpoint = await channelsService.updateEndpoint(form.id, payload);
      }
      await loadEndpoints(false, savedEndpoint?.id || form?.id || null);
    } catch (err) {
      console.error('Failed to save channel endpoint:', err);
      setError(t('channels.errorSaveFailed'));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!form?.id || form.source !== 'custom') {
      return;
    }

    setIsDeleting(true);
    setError(null);
    try {
      await channelsService.deleteEndpoint(form.id);
      await loadEndpoints(false, null);
    } catch (err) {
      console.error('Failed to delete channel endpoint:', err);
      setError(t('channels.errorDeleteFailed'));
    } finally {
      setIsDeleting(false);
    }
  };

  const handleTestConnection = async () => {
    const payload = buildPayload();
    if (!form || !payload) {
      return;
    }
    setIsTesting(true);
    setError(null);
    try {
      if (form.id) {
        const result = await channelsService.testEndpoint(form.id);
        setTestResult(result);
        setDraftTestResult(null);
        setEventsData({
          endpoint: result.endpoint,
          summary: result.summary,
          events: result.events,
        });
        await loadEndpoints(false, form.id);
      } else {
        const result = await channelsService.testDraftEndpoint(payload);
        setDraftTestResult(result);
        setTestResult(null);
        setForm(current => current
          ? { ...current, config: { ...current.config, ...(result.endpoint.config || {}) } }
          : current);
      }
    } catch (err) {
      console.error('Failed to test channel endpoint:', err);
      setError(t('channels.errorTestFailed'));
    } finally {
      setIsTesting(false);
    }
  };

  const getAgentLabel = (agentId: string) => {
    if (!agentId && isHorbotInboundBotSelected) {
      return t('channels.inboundBotDynamicAgentLabel');
    }
    const agent = data.agents.find(item => item.id === agentId);
    return agent ? `${agent.name} · ${agent.provider || t('channels.providerNotSet')}` : t('channels.noBoundAgentLabel');
  };

  const currentSummary = eventsData?.summary || data.endpoints.find(item => item.id === selectedEndpointId)?.runtime || null;
  const currentEvents: ChannelEndpointEvent[] = eventsData?.events || [];

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(index => (
            <Skeleton key={index} className="h-28" />
          ))}
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-[360px_minmax(0,1fr)] gap-6">
          <Skeleton className="h-[680px]" />
          <Skeleton className="h-[680px]" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
      <section className="rounded-[28px] border border-surface-200 bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.12),_transparent_35%),linear-gradient(135deg,_#ffffff_0%,_#f8fafc_100%)] px-6 py-6 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <Badge variant="primary" size="sm">Channels</Badge>
            <div>
              <h1 className="text-3xl font-semibold text-surface-900">{t('channels.pageTitle')}</h1>
              <p className="mt-2 max-w-3xl text-sm text-surface-600">
                {t('channels.pageSubtitle')}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button variant="secondary" onClick={() => void loadEndpoints(true, selectedEndpointId)} isLoading={isRefreshing}>
              {t('common.refresh')}
            </Button>
            <Button variant="primary" onClick={handleCreateEndpoint}>
              {t('channels.newInstanceTitle')}
            </Button>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="border-surface-200">
          <CardContent className="p-5">
            <p className="text-sm text-surface-500">{t('channels.metricTotal')}</p>
            <p className="mt-2 text-3xl font-semibold text-surface-900">{data.counts.total}</p>
          </CardContent>
        </Card>
        <Card className="border-accent-emerald/20 bg-accent-emerald/5">
          <CardContent className="p-5">
            <p className="text-sm text-surface-500">{t('channels.metricEnabled')}</p>
            <p className="mt-2 text-3xl font-semibold text-accent-emerald">{data.counts.enabled}</p>
          </CardContent>
        </Card>
        <Card className="border-primary-200 bg-primary-50/80">
          <CardContent className="p-5">
            <p className="text-sm text-surface-500">{t('channels.metricReady')}</p>
            <p className="mt-2 text-3xl font-semibold text-primary-700">{data.counts.ready}</p>
          </CardContent>
        </Card>
        <Card className="border-accent-orange/20 bg-accent-orange/5">
          <CardContent className="p-5">
            <p className="text-sm text-surface-500">{t('channels.metricIncomplete')}</p>
            <p className="mt-2 text-3xl font-semibold text-accent-orange">{data.counts.incomplete}</p>
          </CardContent>
        </Card>
      </div>

      <section className="space-y-4 rounded-[24px] border border-surface-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-1">
          <h2 className="text-lg font-semibold text-surface-900">{t('channels.routeOverviewTitle')}</h2>
          <p className="text-sm text-surface-500">
            {t('channels.routeOverviewDescription')}
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-4">
          {routeOverview.map(agent => (
            <div key={agent.id} className="rounded-2xl border border-surface-200 bg-surface-50/70 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-surface-900">{agent.name}</p>
                  <p className="mt-1 text-xs text-surface-500">
                    {agent.provider || t('channels.providerNotSet')} · {agent.model || t('channels.modelNotSet')}
                  </p>
                </div>
                <Badge variant={agent.readyCount > 0 ? 'success' : 'default'} size="sm">
                  {t('channels.instanceCount', { count: agent.endpoints.length })}
                </Badge>
              </div>

              <div className="mt-4 space-y-2">
                {agent.endpoints.length > 0 ? (
                  agent.endpoints.map(endpoint => (
                    <div key={endpoint.id} className="flex items-center justify-between gap-3 rounded-xl border border-surface-200 bg-white px-3 py-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-surface-900">
                          {endpoint.name || endpoint.type}
                        </p>
                        <p className="mt-1 text-xs text-surface-500">
                          {data.catalog.find(item => item.type === endpoint.type)?.label || endpoint.type}
                        </p>
                      </div>
                      <Badge variant={statusVariant(endpoint.status)} size="sm">
                        {getStatusLabel(endpoint.status)}
                      </Badge>
                    </div>
                  ))
                ) : (
                  <div className="rounded-xl border border-dashed border-surface-300 bg-white px-3 py-4 text-sm text-surface-500">
                    {t('channels.agentNoEndpoints')}
                  </div>
                )}
              </div>
            </div>
          ))}

          <div className="rounded-2xl border border-dashed border-surface-300 bg-surface-50/50 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-surface-900">{t('channels.unboundTitle')}</p>
                <p className="mt-1 text-xs text-surface-500">{t('channels.unboundDescription')}</p>
              </div>
              <Badge variant={unboundEndpoints.length > 0 ? 'warning' : 'default'} size="sm">
                {t('channels.instanceCount', { count: unboundEndpoints.length })}
              </Badge>
            </div>
            <div className="mt-4 space-y-2">
              {unboundEndpoints.length > 0 ? (
                unboundEndpoints.map(endpoint => (
                  <div key={endpoint.id} className="rounded-xl border border-surface-200 bg-white px-3 py-2">
                    <p className="text-sm font-medium text-surface-900">{endpoint.name || endpoint.type}</p>
                    <p className="mt-1 text-xs text-surface-500">
                      {data.catalog.find(item => item.type === endpoint.type)?.label || endpoint.type}
                    </p>
                  </div>
                ))
              ) : (
                <div className="rounded-xl border border-surface-200 bg-white px-3 py-4 text-sm text-surface-500">
                  {t('channels.unboundEmpty')}
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {error && (
        <div className="rounded-2xl border border-accent-red/30 bg-accent-red/5 px-4 py-3 text-sm text-accent-red">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[360px_minmax(0,1fr)] gap-6">
        <Card className="border-surface-200">
          <CardContent className="p-4">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-surface-900">{t('channels.instanceListTitle')}</h2>
                <p className="text-sm text-surface-500">{t('channels.instanceListDescription')}</p>
              </div>
            </div>

            <div className="space-y-3">
              {data.endpoints.map(endpoint => {
                const isSelected = selectedEndpointId === endpoint.id;
                return (
                  <button
                    key={endpoint.id}
                    type="button"
                    onClick={() => handleSelectEndpoint(endpoint)}
                    className={`w-full rounded-2xl border px-4 py-4 text-left transition-all ${
                      isSelected
                        ? 'border-primary-500 bg-primary-50 shadow-md shadow-primary-500/10'
                        : 'border-surface-200 bg-white hover:border-surface-300 hover:bg-surface-50'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="truncate text-sm font-semibold text-surface-900">
                            {endpoint.name || endpoint.type}
                          </p>
                          <Badge variant={endpoint.source === 'legacy' ? 'warning' : 'info'} size="sm">
                            {endpoint.source === 'legacy' ? t('channels.legacyBadge') : t('channels.customBadge')}
                          </Badge>
                        </div>
                        <p className="mt-1 text-xs text-surface-500">
                          {data.catalog.find(item => item.type === endpoint.type)?.label || endpoint.type}
                        </p>
                      </div>
                      <Badge variant={statusVariant(endpoint.status)} size="sm">
                        {getStatusLabel(endpoint.status)}
                      </Badge>
                    </div>
                    <div className="mt-3 space-y-1 text-xs text-surface-500">
                      <p>{t('channels.bindAgent')}: {getAgentLabel(endpoint.agent_id)}</p>
                      {endpoint.missing_fields.length > 0 && (
                        <p>{t('channels.missingFields')}: {endpoint.missing_fields.join(', ')}</p>
                      )}
                    </div>
                  </button>
                );
              })}

              {data.endpoints.length === 0 && (
                <Empty
                  title={t('channels.emptyNoInstancesTitle')}
                  description={t('channels.emptyNoInstancesDescription')}
                />
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border-surface-200">
          <CardContent className="p-6">
            {form ? (
              <div className="space-y-6">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-xl font-semibold text-surface-900">
                        {form.source === 'draft' ? t('channels.newInstanceTitle') : form.name || form.type}
                      </h2>
                      <Badge variant={form.source === 'legacy' ? 'warning' : 'info'} size="sm">
                        {form.source === 'legacy'
                          ? t('channels.legacyGlobalBadge')
                          : form.source === 'draft'
                            ? t('channels.newInstanceBadge')
                            : t('channels.customInstanceBadge')}
                      </Badge>
                    </div>
                    <p className="mt-2 text-sm text-surface-500">
                      {selectedCatalog?.description || t('channels.detailDescriptionDefault')}
                    </p>
                  </div>
                  <div className="flex gap-3">
                    {isDraft ? (
                      <>
                        {draftStep > 1 && (
                          <Button variant="secondary" onClick={() => setDraftStep(current => Math.max(1, current - 1))}>
                            {t('common.previous')}
                          </Button>
                        )}
                        {draftStep < 3 && (
                          <Button
                            variant="primary"
                            onClick={() => setDraftStep(current => Math.min(3, current + 1))}
                            disabled={(draftStep === 1 && !draftStepOneReady) || (draftStep === 2 && !draftStepTwoReady)}
                          >
                            {t('common.next')}
                          </Button>
                        )}
                        {draftStep === 3 && (
                          <>
                            <Button
                              variant="secondary"
                              onClick={handleTestConnection}
                              isLoading={isTesting}
                              disabled={!canRunDraftTest}
                            >
                              {draftTestResult ? t('channels.retest') : t('channels.startTest')}
                            </Button>
                            <Button variant="primary" onClick={handleSave} isLoading={isSaving} disabled={!draftTestPassed}>
                              {t('common.save')}
                            </Button>
                          </>
                        )}
                      </>
                    ) : (
                      <>
                        {form.id && (
                          <Button variant="secondary" onClick={handleTestConnection} isLoading={isTesting}>
                            {testResult ? t('channels.retestConnection') : t('channels.testConnection')}
                          </Button>
                        )}
                        {form.source === 'custom' && form.id && (
                          <Button variant="danger" onClick={handleDelete} isLoading={isDeleting}>
                            {t('common.delete')}
                          </Button>
                        )}
                        <Button variant="primary" onClick={handleSave} isLoading={isSaving}>
                          {t('common.save')}
                        </Button>
                      </>
                    )}
                  </div>
                </div>

                {isDraft ? (
                  <>
                    <section className="space-y-4 rounded-[24px] border border-surface-200 bg-surface-50/70 p-5">
                      <div className="flex flex-col gap-1">
                        <h3 className="text-base font-semibold text-surface-900">{t('channels.wizardTitle')}</h3>
                        <p className="text-sm text-surface-500">
                          {t('channels.wizardDescription')}
                        </p>
                      </div>
                      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                        {[
                          { id: 1, title: t('channels.wizardStepChoose'), ready: draftStepOneReady },
                          { id: 2, title: t('channels.wizardStepCredentials'), ready: draftStepTwoReady },
                          { id: 3, title: t('channels.wizardStepTest'), ready: draftTestPassed },
                        ].map(step => {
                          const isCurrent = draftStep === step.id;
                          const isDone = draftStep > step.id || (step.id === 3 && draftTestPassed);
                          return (
                            <div
                              key={step.id}
                              className={`rounded-2xl border px-4 py-4 ${
                                isCurrent
                                  ? 'border-primary-500 bg-primary-50'
                                  : isDone
                                    ? 'border-accent-emerald/30 bg-accent-emerald/5'
                                    : 'border-surface-200 bg-white'
                              }`}
                            >
                              <div className="flex items-center gap-3">
                                <div className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold ${
                                  isCurrent ? 'bg-primary-600 text-white' : isDone ? 'bg-accent-emerald text-white' : 'bg-surface-100 text-surface-500'
                                }`}>
                                  {step.id}
                                </div>
                                <div>
                                  <p className="text-sm font-semibold text-surface-900">{step.title}</p>
                                  <p className="mt-1 text-xs text-surface-500">
                                    {step.id === 1 ? t('channels.wizardStepChooseHint') : step.id === 2 ? t('channels.wizardStepCredentialsHint') : t('channels.wizardStepTestHint')}
                                  </p>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </section>

                    {draftStep === 1 && (
                      <section className="space-y-4 rounded-[24px] border border-surface-200 bg-white p-5">
                        <div>
                          <h3 className="text-base font-semibold text-surface-900">{t('channels.stepOneTitle')}</h3>
                          <p className="text-sm text-surface-500">
                            {t('channels.stepOneDescription')}
                          </p>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <Select
                            label={t('channels.channelType')}
                            
                            value={form.type}
                            onChange={(event) => handleTypeChange(event.target.value)}
                            options={data.catalog.map(item => ({ value: item.type, label: item.label }))}
                          />
                          <Select
                            label={t('channels.bindAgent')}
                            value={form.agent_id}
                            onChange={(event) => handleFieldChange('agent_id', event.target.value)}
                            options={[
                              { value: '', label: isHorbotInboundBotSelected ? t('channels.inboundBotDynamicAgentOption') : t('channels.placeholderAgent') },
                              ...data.agents.map(agent => ({
                                value: agent.id,
                                label: `${agent.name} · ${agent.provider || t('channels.providerNotSet')} · ${agent.model || t('channels.modelNotSet')}`,
                              })),
                            ]}
                            hint={isHorbotInboundBotSelected ? t('channels.inboundBotBindAgentHint') : t('channels.bindAgentHint')}
                          />
                          <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-4 md:col-span-2">
                            <label className="flex items-center gap-3">
                              <input
                                type="checkbox"
                                className="h-4 w-4 rounded border-surface-300 text-primary-600 focus:ring-primary-500"
                                checked={form.enabled}
                                onChange={(event) => handleFieldChange('enabled', event.target.checked)}
                              />
                              <span className="text-sm font-medium text-surface-700">{t('channels.createEnabled')}</span>
                            </label>
                            <p className="mt-2 text-sm text-surface-500">
                              {t('channels.createEnabledHint')}
                            </p>
                          </div>
                        </div>
                      </section>
                    )}

                    {draftStep === 2 && (
                      <>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <Input
                            label={t('channels.instanceName')}
                            value={form.name}
                            onChange={(event) => handleFieldChange('name', event.target.value)}
                            placeholder={t('channels.placeholderInstanceName')}
                            hint={t('channels.instanceNameHint')}
                          />
                          <Textarea
                            label={t('channels.allowFromLabel')}
                            value={form.allow_from_text}
                            onChange={(event) => handleFieldChange('allow_from_text', event.target.value)}
                            rows={4}
                            placeholder={t('channels.placeholderAllowFrom')}
                            hint={t('channels.allowFromHint')}
                          />
                        </div>

                        <section className="space-y-4 rounded-[24px] border border-surface-200 bg-surface-50/70 p-5">
                          <div className="flex items-center justify-between">
                            <div>
                              <h3 className="text-base font-semibold text-surface-900">{t('channels.stepTwoTitle')}</h3>
                              <p className="text-sm text-surface-500">
                                {t('channels.stepTwoDescription')}
                              </p>
                            </div>
                            {selectedCatalog && (
                              <Badge variant={draftStepTwoReady ? 'success' : 'warning'} size="sm">
                                {requiredFieldKeys.length > 0
                                  ? t('channels.requiredFields', { fields: requiredFieldKeys.join(', ') })
                                  : t('channels.noRequiredFields')}
                              </Badge>
                            )}
                          </div>

                          {selectedCatalog ? (
                            <>
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {requiredCatalogFields.map(renderChannelField)}
                              </div>

                              {optionalCatalogFields.length > 0 && (
                                <div className="space-y-3 rounded-2xl border border-dashed border-surface-300 bg-white px-4 py-4">
                                  <div>
                                    <h4 className="text-sm font-semibold text-surface-900">{t('channels.optionalTitle')}</h4>
                                    <p className="text-sm text-surface-500">
                                      {t('channels.optionalDescription')}
                                    </p>
                                  </div>
                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {optionalCatalogFields.map(renderChannelField)}
                                  </div>
                                </div>
                              )}
                            </>
                          ) : (
                            <Empty
                              title={t('channels.emptyNoFieldsTitle')}
                              description={t('channels.emptyNoFieldsDescription')}
                            />
                          )}
                        </section>
                      </>
                    )}

                    {draftStep === 3 && (
                      <section className="space-y-4 rounded-[24px] border border-surface-200 bg-white p-5">
                        <div>
                          <h3 className="text-base font-semibold text-surface-900">{t('channels.stepThreeTitle')}</h3>
                          <p className="text-sm text-surface-500">
                            {t('channels.stepThreeDescription')}
                          </p>
                        </div>

                        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
                          <div className="space-y-4">
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                              <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-4">
                                <p className="text-xs text-surface-500">{t('channels.channelType')}</p>
                                <p className="mt-1 text-sm font-semibold text-surface-900">{selectedCatalog?.label || form.type}</p>
                              </div>
                              <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-4">
                                <p className="text-xs text-surface-500">{t('channels.targetAgent')}</p>
                                <p className="mt-1 text-sm font-semibold text-surface-900">{getAgentLabel(form.agent_id)}</p>
                              </div>
                              <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-4">
                                <p className="text-xs text-surface-500">{t('channels.requiredFieldsStatus')}</p>
                                <p className="mt-1 text-sm font-semibold text-surface-900">{draftStepTwoReady ? t('channels.requiredFieldsComplete') : t('channels.requiredFieldsMissing')}</p>
                              </div>
                            </div>

                            <div className="rounded-2xl border border-surface-200 bg-surface-50/70 px-4 py-4">
                              <div className="flex items-center justify-between gap-3">
                                <div>
                                  <h4 className="text-sm font-semibold text-surface-900">{t('channels.preflightTitle')}</h4>
                                  <p className="mt-1 text-sm text-surface-500">
                                    {t('channels.preflightDescription')}
                                  </p>
                                </div>
                                <Badge variant={draftStepTwoReady ? 'success' : 'warning'} size="sm">
                                  {draftStepTwoReady ? t('channels.preflightReady') : t('channels.preflightIncomplete')}
                                </Badge>
                              </div>
                              <div className="mt-4 space-y-3">
                                <div className="flex items-start justify-between gap-3 rounded-xl border border-surface-200 bg-white px-3 py-3">
                                  <div>
                                    <p className="text-sm font-medium text-surface-900">{t('channels.checkAgentReadyTitle')}</p>
                                    <p className="mt-1 text-xs text-surface-500">{t('channels.checkAgentReadyDescription')}</p>
                                  </div>
                                  <Badge variant={form.agent_id || agentBindingOptional ? 'success' : 'warning'} size="sm">
                                    {form.agent_id || agentBindingOptional ? t('channels.completed') : t('channels.incomplete')}
                                  </Badge>
                                </div>
                                <div className="flex items-start justify-between gap-3 rounded-xl border border-surface-200 bg-white px-3 py-3">
                                  <div>
                                    <p className="text-sm font-medium text-surface-900">{t('channels.checkRequiredReadyTitle')}</p>
                                    <p className="mt-1 text-xs text-surface-500">
                                      {draftMissingFields.length > 0
                                        ? t('channels.checkRequiredReadyMissing', { fields: draftMissingFields.join(', ') })
                                        : t('channels.checkRequiredReadyDone')}
                                    </p>
                                  </div>
                                  <Badge variant={draftStepTwoReady ? 'success' : 'warning'} size="sm">
                                    {draftStepTwoReady ? t('channels.completed') : t('channels.missingCount', { count: draftMissingFields.length })}
                                  </Badge>
                                </div>
                                <div className="flex items-start justify-between gap-3 rounded-xl border border-surface-200 bg-white px-3 py-3">
                                  <div>
                                    <p className="text-sm font-medium text-surface-900">{t('channels.checkRecentTestTitle')}</p>
                                    <p className="mt-1 text-xs text-surface-500">
                                      {draftTestPassed
                                        ? t('channels.checkRecentTestPassed')
                                        : draftTestResult
                                          ? t('channels.checkRecentTestFailed')
                                          : t('channels.checkRecentTestNever')}
                                    </p>
                                  </div>
                                  <Badge variant={draftTestPassed ? 'success' : draftTestResult ? 'warning' : 'default'} size="sm">
                                    {draftTestPassed ? t('channels.passed') : draftTestResult ? t('channels.failed') : t('channels.notTested')}
                                  </Badge>
                                </div>
                              </div>
                            </div>

                            {isTesting && (
                              <div className="rounded-2xl border border-primary-200 bg-primary-50 px-4 py-4 text-sm text-primary-700">
                                {t('channels.testingConnectionBanner')}
                              </div>
                            )}

                            {draftTestResult && (
                              <div className={`rounded-2xl border px-4 py-4 text-sm ${
                                draftTestResult.result.status === 'ok'
                                  ? 'border-accent-emerald/30 bg-accent-emerald/5 text-accent-emerald'
                                  : 'border-accent-orange/30 bg-accent-orange/5 text-accent-orange'
                              }`}>
                                <div className="flex flex-wrap items-center gap-3">
                                  <span>{t('channels.testedAt', { value: formatDateTimeLocal(draftTestResult.tested_at) })}</span>
                                  <span>{t('channels.latency', { value: draftTestResult.result.latency_ms })}</span>
                                  <span>{t('channels.testResultLabel', { value: draftTestResult.result.status === 'ok' ? t('channels.passed') : t('channels.failed') })}</span>
                                </div>
                                {draftConnectionFeedback && (
                                  <>
                                    <p className="mt-3 text-base font-semibold">{draftConnectionFeedback.title}</p>
                                    <p className="mt-1">{draftConnectionFeedback.summary}</p>
                                    {draftTestResult.result.error && draftTestResult.result.status !== 'ok' && (
                                      <div className="mt-3 rounded-xl border border-current/15 bg-white/60 px-3 py-3 text-xs leading-6 text-surface-700">
                                        {t('channels.rawError', { error: draftTestResult.result.error })}
                                      </div>
                                    )}
                                    <div className="mt-3 space-y-2">
                                      {draftConnectionFeedback.hints.map((hint, index) => (
                                        <div key={`${hint}-${index}`} className="rounded-xl border border-current/15 bg-white/60 px-3 py-2 text-xs leading-6 text-surface-700">
                                          {hint}
                                        </div>
                                      ))}
                                    </div>
                                  </>
                                )}
                              </div>
                            )}

                            {renderInboundBotCredentials()}
                          </div>

                          <div className="space-y-4 rounded-2xl border border-surface-200 bg-surface-50/70 px-4 py-4">
                            <div>
                              <h4 className="text-sm font-semibold text-surface-900">{t('channels.nextSuggestion')}</h4>
                              <p className="mt-1 text-sm text-surface-500">
                                {t('channels.nextSuggestionDescription')}
                              </p>
                            </div>
                            <div className={`rounded-xl border px-3 py-3 text-sm ${
                              !draftStepTwoReady
                                ? 'border-accent-orange/30 bg-accent-orange/5 text-accent-orange'
                                : draftTestPassed
                                  ? 'border-accent-emerald/30 bg-accent-emerald/5 text-accent-emerald'
                                  : draftTestResult
                                    ? 'border-accent-orange/30 bg-accent-orange/5 text-accent-orange'
                                    : 'border-primary-200 bg-primary-50 text-primary-700'
                            }`}>
                              {!draftStepTwoReady
                                ? t('channels.nextActionNeedCredentials')
                                : draftTestPassed
                                  ? t('channels.nextActionSaveReady')
                                  : draftTestResult
                                    ? t('channels.nextActionRetryAfterFailure')
                                    : t('channels.nextActionCanTest')}
                            </div>
                            <div className="flex flex-col gap-3">
                              <Button
                                variant="secondary"
                                onClick={handleTestConnection}
                                isLoading={isTesting}
                                disabled={!canRunDraftTest}
                              >
                                {isTesting ? t('channels.testing') : draftTestResult ? t('channels.retestConnection') : t('channels.startTestConnection')}
                              </Button>
                              <Button
                                variant="primary"
                                onClick={handleSave}
                                isLoading={isSaving}
                                disabled={!draftTestPassed}
                              >
                                {draftTestPassed ? t('channels.saveInstance') : t('channels.saveAfterPass')}
                              </Button>
                            </div>
                            <div className="rounded-xl border border-surface-200 bg-white px-3 py-3 text-sm text-surface-600">
                              <span className="font-medium text-surface-800">{t('channels.savePolicyTitle')}</span>
                              {' '}
                              {t('channels.savePolicyDescription')}
                            </div>
                          </div>
                        </div>
                      </section>
                    )}
                  </>
                ) : (
                  <>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <Input
                        label={t('channels.instanceName')}
                        value={form.name}
                        onChange={(event) => handleFieldChange('name', event.target.value)}
                        placeholder={t('channels.placeholderInstanceName')}
                        hint={t('channels.instanceNameBusinessHint')}
                      />
                      <Select
                        label={t('channels.channelType')}
                        value={form.type}
                        onChange={(event) => handleTypeChange(event.target.value)}
                        disabled={form.source !== 'draft'}
                        options={data.catalog.map(item => ({ value: item.type, label: item.label }))}
                      />
                      <Select
                        label={t('channels.bindAgent')}
                        value={form.agent_id}
                        onChange={(event) => handleFieldChange('agent_id', event.target.value)}
                        options={[
                          { value: '', label: isHorbotInboundBotSelected ? t('channels.inboundBotDynamicAgentOption') : t('channels.noBoundAgent') },
                          ...data.agents.map(agent => ({
                            value: agent.id,
                            label: `${agent.name} · ${agent.provider || t('channels.providerNotSet')} · ${agent.model || t('channels.modelNotSet')}`,
                          })),
                        ]}
                        hint={isHorbotInboundBotSelected ? t('channels.inboundBotBindAgentHint') : t('channels.bindAgentRouteHint')}
                      />
                      <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-4">
                        <label className="flex items-center gap-3">
                          <input
                            type="checkbox"
                            className="h-4 w-4 rounded border-surface-300 text-primary-600 focus:ring-primary-500"
                            checked={form.enabled}
                            onChange={(event) => handleFieldChange('enabled', event.target.checked)}
                          />
                          <span className="text-sm font-medium text-surface-700">{t('channels.createEnabled')}</span>
                        </label>
                        <p className="mt-2 text-sm text-surface-500">
                          {t('channels.disableHint')}
                        </p>
                      </div>
                    </div>

                    <Textarea
                      label={t('channels.allowFromLabel')}
                      value={form.allow_from_text}
                      onChange={(event) => handleFieldChange('allow_from_text', event.target.value)}
                      rows={4}
                      placeholder={t('channels.placeholderAllowFrom')}
                      hint={t('channels.allowFromHint')}
                    />

                    <section className="space-y-4 rounded-[24px] border border-surface-200 bg-surface-50/70 p-5">
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="text-base font-semibold text-surface-900">{t('channels.credentialsTitle')}</h3>
                          <p className="text-sm text-surface-500">
                            {t('channels.credentialsDescription')}
                          </p>
                        </div>
                        {selectedCatalog && (
                          <Badge variant={draftStepTwoReady ? 'success' : 'warning'} size="sm">
                            {selectedCatalog.required_fields.length > 0
                              ? t('channels.requiredFields', { fields: selectedCatalog.required_fields.join(', ') })
                              : t('channels.noRequiredFields')}
                          </Badge>
                        )}
                      </div>

                      {selectedCatalog ? (
                        <>
                          {renderInboundBotCredentials()}
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {selectedCatalog.fields.map(renderChannelField)}
                          </div>
                        </>
                      ) : (
                        <Empty
                          title={t('channels.emptyNoFieldsTitle')}
                          description={t('channels.emptyNoFieldsDescription')}
                        />
                      )}
                    </section>

                    {form.source === 'legacy' && (
                      <div className="rounded-2xl border border-accent-orange/30 bg-accent-orange/5 px-4 py-4 text-sm text-accent-orange">
                        {t('channels.legacyNotice')}
                      </div>
                    )}

                    <section className="space-y-4 rounded-[24px] border border-surface-200 bg-white p-5">
                      <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                        <div>
                          <h3 className="text-base font-semibold text-surface-900">{t('channels.runtimeTitle')}</h3>
                          <p className="text-sm text-surface-500">
                            {t('channels.runtimeDescription')}
                          </p>
                        </div>
                        {testResult && (
                          <Badge variant={testResult.result.status === 'ok' ? 'success' : 'warning'} size="sm">
                            {t('channels.recentTestLabel', { value: testResult.result.status === 'ok' ? t('channels.passed') : t('channels.failed') })}
                          </Badge>
                        )}
                      </div>

                      {currentSummary && (
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                          <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-3">
                            <p className="text-xs text-surface-500">{t('channels.metricReceived')}</p>
                            <p className="mt-1 text-xl font-semibold text-surface-900">{currentSummary.messages_received}</p>
                          </div>
                          <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-3">
                            <p className="text-xs text-surface-500">{t('channels.metricSent')}</p>
                            <p className="mt-1 text-xl font-semibold text-surface-900">{currentSummary.messages_sent}</p>
                          </div>
                          <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-3">
                            <p className="text-xs text-surface-500">{t('channels.metricErrors')}</p>
                            <p className="mt-1 text-xl font-semibold text-accent-red">{currentSummary.errors}</p>
                          </div>
                          <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-3">
                            <p className="text-xs text-surface-500">{t('channels.metricLastEvent')}</p>
                            <p className="mt-1 text-sm font-medium text-surface-900">{formatDateTimeLocal(currentSummary.last_event_at)}</p>
                          </div>
                        </div>
                      )}

                      {testResult && (
                        <div className={`rounded-2xl border px-4 py-4 text-sm ${
                          testResult.result.status === 'ok'
                            ? 'border-accent-emerald/30 bg-accent-emerald/5 text-accent-emerald'
                            : 'border-accent-orange/30 bg-accent-orange/5 text-accent-orange'
                        }`}>
                          <div className="flex flex-wrap items-center gap-3">
                            <span>{t('channels.testedAt', { value: formatDateTimeLocal(testResult.tested_at) })}</span>
                            <span>{t('channels.latency', { value: testResult.result.latency_ms })}</span>
                          </div>
                          {savedConnectionFeedback && (
                            <>
                              <p className="mt-3 text-base font-semibold">{savedConnectionFeedback.title}</p>
                              <p className="mt-1">{savedConnectionFeedback.summary}</p>
                              {testResult.result.error && testResult.result.status !== 'ok' && (
                                <div className="mt-3 rounded-xl border border-current/15 bg-white/60 px-3 py-3 text-xs leading-6 text-surface-700">
                                  {t('channels.rawError', { error: testResult.result.error })}
                                </div>
                              )}
                              <div className="mt-3 space-y-2">
                                {savedConnectionFeedback.hints.map((hint, index) => (
                                  <div key={`${hint}-${index}`} className="rounded-xl border border-current/15 bg-white/60 px-3 py-2 text-xs leading-6 text-surface-700">
                                    {hint}
                                  </div>
                                ))}
                              </div>
                            </>
                          )}
                        </div>
                      )}

                      <div className="space-y-3">
                        {currentEvents.length > 0 ? (
                          currentEvents.map(event => (
                            <div key={`${event.timestamp}-${event.event_type}-${event.message}`} className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-3">
                              <div className="flex flex-wrap items-center gap-2">
                                <Badge variant={event.status === 'ok' ? 'success' : event.status === 'error' ? 'error' : 'default'} size="sm">
                                  {event.event_type}
                                </Badge>
                                <span className="text-xs text-surface-500">{formatDateTimeLocal(event.timestamp)}</span>
                              </div>
                              <p className="mt-2 text-sm text-surface-900">{event.message}</p>
                            </div>
                          ))
                        ) : (
                          <Empty
                          title={t('channels.emptyNoEventsTitle')}
                          description={t('channels.emptyNoEventsDescription')}
                        />
                        )}
                      </div>
                    </section>
                  </>
                )}
              </div>
            ) : (
              <Empty
                title={t('channels.emptyNoEditableTitle')}
                description={t('channels.emptyNoEditableDescription')}
              />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default ChannelsPage;
