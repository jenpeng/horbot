import React, { useEffect, useState } from 'react';
import { channelsService } from '../services';
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

const statusLabel = (status: ChannelEndpoint['status']) => {
  if (status === 'ready') {
    return '可用';
  }
  if (status === 'incomplete') {
    return '待完善';
  }
  return '已停用';
};

const formatDateTime = (value?: string | null) => {
  if (!value) {
    return '暂无';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('zh-CN', { hour12: false });
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

const getChannelSpecificHints = (channelType: string, kind: ConnectionErrorKind): string[] => {
  switch (channelType) {
    case 'feishu':
      if (kind === 'missing') {
        return [
          '至少补齐 App ID 和 App Secret；如果启用了事件订阅，再检查 Encrypt Key 和 Verification Token 是否与飞书后台一致。',
          '如果这是企业内网环境，确认是否需要开启“跳过 SSL 校验”来绕过公司代理证书注入。',
        ];
      }
      if (kind === 'credential') {
        return [
          '去飞书开放平台的“凭证与基础信息”核对 App ID、App Secret 是否来自同一个应用，避免把测试应用和生产应用混用。',
          '如果最近在飞书后台重置过密钥，记得同步更新这里的配置后再测试。',
        ];
      }
      if (kind === 'permission') {
        return [
          '去飞书开放平台检查应用权限、机器人能力和事件订阅是否已开启，尤其是消息接收、通讯录或群聊相关权限。',
          '如果平台提示 scope 不足，先在飞书后台补齐权限并重新发布应用，再回来重试。',
        ];
      }
      if (kind === 'ssl') {
        return [
          '如果当前网络经过公司代理或 HTTPS 检查设备，先确认代理证书是否可信；必要时仅在受信任内网里临时启用“跳过 SSL 校验”。',
        ];
      }
      return [
        '如果账号本身没问题，再去飞书开放平台查看应用状态、可用性和最近调用日志。',
      ];

    case 'sharecrm':
      if (kind === 'missing') {
        return [
          '至少补齐 App ID 和 App Secret；如果你走的不是默认网关，还要确认 Gateway Base URL 已填写正确。',
          '建议直接对照纷享销客 IM Gateway 后台里的机器人配置逐项核对字段名。',
        ];
      }
      if (kind === 'credential' || kind === 'permission') {
        return [
          '去纷享销客 IM Gateway / 开放平台检查当前 bot 的 App ID、App Secret 是否已启用且未过期。',
          '确认该机器人账号具备获取 token、接收会话和发送消息所需权限。',
        ];
      }
      return [
        '如果报的是网关或 404/5xx 类错误，优先核对 Gateway Base URL 是否仍然指向正确环境，再检查平台侧服务状态。',
      ];

    case 'telegram':
      if (kind === 'credential' || kind === 'missing') {
        return [
          '直接在浏览器或命令行调用 `https://api.telegram.org/bot<TOKEN>/getMe`，先独立验证这枚 Bot Token 是否有效。',
          '如果 BotFather 刚重新生成过 token，需要把旧 token 全部替换掉。',
        ];
      }
      return [
        '如果网络在国内或受限环境，优先检查代理是否可用，以及 Telegram API 是否被当前网络出口拦截。',
      ];

    case 'slack':
      if (kind === 'credential' || kind === 'missing') {
        return [
          '去 Slack App 管理后台核对 Bot Token 和 App Token 是否来自同一个应用，避免把不同 workspace 的 token 混在一起。',
          '如果最近重新安装过应用，记得使用新的 OAuth Token。',
        ];
      }
      if (kind === 'permission') {
        return [
          '去 Slack App 后台检查 OAuth scopes、Event Subscriptions 和 Socket Mode 是否已开启，尤其是消息读取和回复相关 scope。',
          '如果 `auth.test` 能过但真实收发不通，通常是 scope 或事件订阅没有配齐。',
        ];
      }
      return [
        '保存前最好再确认一次目标 workspace 已正确安装该应用，而不是只在开发工作区里可用。',
      ];

    case 'discord':
      if (kind === 'credential' || kind === 'missing') {
        return [
          '去 Discord Developer Portal 检查 Bot Token 是否已被重置；如果重置过，这里的旧 token 会立刻失效。',
        ];
      }
      if (kind === 'permission') {
        return [
          '去 Discord Developer Portal 检查 Privileged Gateway Intents，尤其是 Message Content Intent 是否已开启。',
          '再确认目标服务器里机器人角色本身具备读取频道和发送消息权限。',
        ];
      }
      return [
        '如果只是连接通过但收不到消息，优先排查 intents 和服务器角色权限，而不是 token 本身。',
      ];

    case 'email':
      if (kind === 'missing') {
        return [
          'IMAP/SMTP 主机、账号、密码和发件地址都需要成套配置，缺一项都会导致测试失败。',
        ];
      }
      if (kind === 'credential') {
        return [
          '很多邮箱不能直接用登录密码，而必须使用 IMAP/SMTP 授权码；先去邮箱后台确认开启了 IMAP/SMTP 并生成授权码。',
          '如果只改了收件或发件一侧配置，也会导致一半可用一半失败，建议成对核对 IMAP 和 SMTP。 ',
        ];
      }
      if (kind === 'ssl') {
        return [
          '检查 IMAP/SMTP 的 SSL/TLS 组合和端口是否匹配，例如 IMAP 993 + SSL、SMTP 587 + STARTTLS。',
        ];
      }
      return [
        '如果是企业邮箱，再检查是否有 IP 白名单、异地登录限制或安全策略拦截。 ',
      ];

    case 'dingtalk':
      if (kind === 'credential' || kind === 'missing') {
        return [
          '去钉钉开放平台核对 Client ID / Client Secret，确认当前应用已开通 Stream 模式并处于可用状态。',
        ];
      }
      if (kind === 'permission') {
        return [
          '检查钉钉机器人消息接收、会话访问等权限是否已授权给当前应用。',
        ];
      }
      return [];

    case 'matrix':
      if (kind === 'credential' || kind === 'missing') {
        return [
          '先用当前 homeserver 调 `/_matrix/client/v3/account/whoami` 验证 access token 是否有效，并确认 user_id 属于同一实例。',
        ];
      }
      return [
        '如果 homeserver 走自建部署，优先检查地址路径、反向代理和证书配置是否正确。',
      ];

    case 'mochat':
      if (kind === 'credential' || kind === 'missing') {
        return [
          '核对 Mochat Base URL、Claw Token 和 Agent User ID 是否对应同一个环境实例。',
        ];
      }
      return [
        '如果 `/api/health` 都打不通，先看 Mochat 服务自身是否在线，再排查反向代理或访问控制。',
      ];

    case 'qq':
      if (kind === 'credential' || kind === 'missing') {
        return [
          '去 QQ 开放平台核对 App ID 和 Secret，确认机器人应用已启用并且密钥未失效。',
        ];
      }
      return [];

    case 'whatsapp':
      if (kind === 'credential' || kind === 'missing') {
        return [
          '如果 bridge 开启了鉴权，确认这里的 Bridge Token 与桥接服务配置一致。',
        ];
      }
      return [
        '先直接访问 bridge 的 `/health` 接口，确认桥接服务在线，再看账号侧是否已完成扫码或会话绑定。',
      ];

    default:
      return [];
  }
};

const getConnectionFeedback = (result?: ConnectionResultLike | null, channelType?: string | null) => {
  if (!result) {
    return null;
  }

  const resolvedChannelType = String(channelType || result.name || '').trim().toLowerCase();
  const backendKind = String(result.error_kind || '').trim().toLowerCase();
  const backendRemediation = Array.isArray(result.remediation) ? result.remediation.filter(Boolean) : [];

  if (result.status === 'ok') {
    return {
      tone: 'success' as const,
      title: '连接验证通过',
      summary: '当前账号配置可用，可以进入下一步保存或开始真实收发联调。',
      hints: [
        '保存后建议马上从目标通道发一条测试消息，确认真实路由与回复链路也正常。',
        '如果这是生产账号，建议再补充 allow_from 或群策略，避免刚接通就暴露给全部来源。',
      ],
    };
  }

  const rawError = normalizeConnectionError(result.error);
  const kind = (backendKind || detectConnectionErrorKind(rawError)) as ConnectionErrorKind;
  const channelHints = backendRemediation.length > 0
    ? backendRemediation
    : getChannelSpecificHints(resolvedChannelType, kind);

  if (kind === 'missing') {
    return {
      tone: 'warning' as const,
      title: '必填凭据还没有补齐',
      summary: '当前失败更像是配置项缺失，而不是账号真的失效。先补全关键字段，再做真实连接测试。',
      hints: [
        '优先把当前通道的必填字段补齐，再重新测试，避免被无效报错干扰判断。',
        ...channelHints,
      ],
    };
  }

  if (kind === 'credential') {
    return {
      tone: 'warning' as const,
      title: '凭据校验失败',
      summary: '更像是账号密钥、Token、App Secret 或权限范围不正确，而不是单纯的网络波动。',
      hints: [
        '确认 App ID、App Secret、Bot Token 等是否对应同一个应用实例。',
        '如果第三方平台支持权限范围配置，检查当前应用是否已开通所需接口权限。',
        ...channelHints,
      ],
    };
  }

  if (kind === 'permission') {
    return {
      tone: 'warning' as const,
      title: '平台权限不足',
      summary: '当前账号可能能连上平台，但缺少接口 scope、事件订阅或会话访问权限，所以校验没有通过。',
      hints: [
        '先检查第三方平台控制台里的权限范围、事件订阅、机器人能力或应用发布状态。',
        ...channelHints,
      ],
    };
  }

  if (kind === 'timeout') {
    return {
      tone: 'warning' as const,
      title: '连接超时',
      summary: '请求已经发出，但在预期时间内没有收到平台响应，通常是网络抖动或平台响应慢。',
      hints: [
        '先重新测试一次，确认不是瞬时网络问题。',
        '如果多次超时，检查本机网络、代理、VPN 或第三方平台当前可用性。',
        ...channelHints,
      ],
    };
  }

  if (kind === 'dns') {
    return {
      tone: 'warning' as const,
      title: '域名解析异常',
      summary: '系统在访问目标平台前就失败了，通常是 DNS、代理或网络出口问题。',
      hints: [
        '确认当前机器能访问对应平台域名，必要时检查 DNS、代理或公司网络策略。',
        '如果你在受限网络环境中运行，建议先验证浏览器里是否能打开对应平台。',
        ...channelHints,
      ],
    };
  }

  if (kind === 'ssl') {
    return {
      tone: 'warning' as const,
      title: '证书或 SSL 校验失败',
      summary: '连接已经到达目标服务，但在 HTTPS/证书校验阶段失败。',
      hints: [
        '检查当前网络是否有 HTTPS 劫持、企业代理或自签证书注入。',
        '如果当前通道支持跳过 SSL 校验，仅建议在受信任内网环境里临时使用。',
        ...channelHints,
      ],
    };
  }

  if (kind === 'rate_limit') {
    return {
      tone: 'warning' as const,
      title: '平台限流或频控',
      summary: '当前请求被平台的限流、频控或安全策略挡住了，不一定是凭据本身有问题。',
      hints: [
        '先间隔一段时间再重试，避免短时间连续测试触发更严格限制。',
        '如果这是正式环境账号，去对应平台后台查看调用频率限制或安全风控记录。',
        ...channelHints,
      ],
    };
  }

  return {
    tone: 'warning' as const,
    title: '连接测试未通过',
    summary: '账号或网络还有问题，暂时不建议直接保存为正式通道实例。',
    hints: [
      '先根据原始错误检查凭据、网络、平台状态，再重新测试。',
      '如果问题持续存在，建议先在平台控制台或官方测试工具中验证这组账号是否可用。',
      ...channelHints,
    ],
  };
};

const ChannelsPage: React.FC = () => {
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
      setError('通道配置加载失败');
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
  const draftStepOneReady = Boolean(form?.type && form?.agent_id);
  const draftStepTwoReady = requiredFieldKeys.every(fieldKey => hasConfiguredValue(form?.config?.[fieldKey]));
  const draftMissingFields = requiredFieldKeys.filter(fieldKey => !hasConfiguredValue(form?.config?.[fieldKey]));
  const draftTestPassed = draftTestResult?.result.status === 'ok';
  const canRunDraftTest = Boolean(isDraft && draftStepTwoReady && form?.type);
  const draftConnectionFeedback = getConnectionFeedback(draftTestResult?.result, form?.type);
  const savedConnectionFeedback = getConnectionFeedback(testResult?.result, form?.type);

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
      setError('请选择通道类型');
      return;
    }
    if (form?.source === 'draft' && !draftTestPassed) {
      setError('新建通道前请先完成连接测试并确保测试通过');
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
      setError('保存通道配置失败');
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
      setError('删除通道实例失败');
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
      }
    } catch (err) {
      console.error('Failed to test channel endpoint:', err);
      setError('测试连接失败');
    } finally {
      setIsTesting(false);
    }
  };

  const getAgentLabel = (agentId: string) => {
    const agent = data.agents.find(item => item.id === agentId);
    return agent ? `${agent.name} · ${agent.provider || '未设置 provider'}` : '未绑定 Agent';
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
              <h1 className="text-3xl font-semibold text-surface-900">按 Agent 管理外部通道</h1>
              <p className="mt-2 max-w-3xl text-sm text-surface-600">
                每个通道实例都可以独立绑定到一个 Agent。legacy 全局通道仍可继续使用，但建议逐步迁移到实例化配置。
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button variant="secondary" onClick={() => void loadEndpoints(true, selectedEndpointId)} isLoading={isRefreshing}>
              刷新
            </Button>
            <Button variant="primary" onClick={handleCreateEndpoint}>
              新建通道实例
            </Button>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="border-surface-200">
          <CardContent className="p-5">
            <p className="text-sm text-surface-500">实例总数</p>
            <p className="mt-2 text-3xl font-semibold text-surface-900">{data.counts.total}</p>
          </CardContent>
        </Card>
        <Card className="border-accent-emerald/20 bg-accent-emerald/5">
          <CardContent className="p-5">
            <p className="text-sm text-surface-500">启用中</p>
            <p className="mt-2 text-3xl font-semibold text-accent-emerald">{data.counts.enabled}</p>
          </CardContent>
        </Card>
        <Card className="border-primary-200 bg-primary-50/80">
          <CardContent className="p-5">
            <p className="text-sm text-surface-500">已就绪</p>
            <p className="mt-2 text-3xl font-semibold text-primary-700">{data.counts.ready}</p>
          </CardContent>
        </Card>
        <Card className="border-accent-orange/20 bg-accent-orange/5">
          <CardContent className="p-5">
            <p className="text-sm text-surface-500">待完善</p>
            <p className="mt-2 text-3xl font-semibold text-accent-orange">{data.counts.incomplete}</p>
          </CardContent>
        </Card>
      </div>

      <section className="space-y-4 rounded-[24px] border border-surface-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-1">
          <h2 className="text-lg font-semibold text-surface-900">Agent 通道路由概览</h2>
          <p className="text-sm text-surface-500">
            先看这里，就能快速判断每个 Agent 当前接了哪些外部入口，以及哪些实例还没有完成绑定。
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-4">
          {routeOverview.map(agent => (
            <div key={agent.id} className="rounded-2xl border border-surface-200 bg-surface-50/70 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-surface-900">{agent.name}</p>
                  <p className="mt-1 text-xs text-surface-500">
                    {agent.provider || '未设置 provider'} · {agent.model || '未设置模型'}
                  </p>
                </div>
                <Badge variant={agent.readyCount > 0 ? 'success' : 'default'} size="sm">
                  {agent.endpoints.length} 个实例
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
                        {statusLabel(endpoint.status)}
                      </Badge>
                    </div>
                  ))
                ) : (
                  <div className="rounded-xl border border-dashed border-surface-300 bg-white px-3 py-4 text-sm text-surface-500">
                    该 Agent 还没有绑定外部通道。
                  </div>
                )}
              </div>
            </div>
          ))}

          <div className="rounded-2xl border border-dashed border-surface-300 bg-surface-50/50 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-surface-900">未绑定实例</p>
                <p className="mt-1 text-xs text-surface-500">这些实例已创建，但还没有路由到具体 Agent。</p>
              </div>
              <Badge variant={unboundEndpoints.length > 0 ? 'warning' : 'default'} size="sm">
                {unboundEndpoints.length} 个
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
                  当前没有未绑定实例。
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
                <h2 className="text-lg font-semibold text-surface-900">通道实例列表</h2>
                <p className="text-sm text-surface-500">选择一个实例查看或编辑绑定关系与账号凭据。</p>
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
                            {endpoint.source === 'legacy' ? 'Legacy' : 'Custom'}
                          </Badge>
                        </div>
                        <p className="mt-1 text-xs text-surface-500">
                          {data.catalog.find(item => item.type === endpoint.type)?.label || endpoint.type}
                        </p>
                      </div>
                      <Badge variant={statusVariant(endpoint.status)} size="sm">
                        {statusLabel(endpoint.status)}
                      </Badge>
                    </div>
                    <div className="mt-3 space-y-1 text-xs text-surface-500">
                      <p>绑定 Agent：{getAgentLabel(endpoint.agent_id)}</p>
                      {endpoint.missing_fields.length > 0 && (
                        <p>缺失字段：{endpoint.missing_fields.join('、')}</p>
                      )}
                    </div>
                  </button>
                );
              })}

              {data.endpoints.length === 0 && (
                <Empty
                  title="还没有通道实例"
                  description="先创建一个通道实例，再将它绑定到具体 Agent。"
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
                        {form.source === 'draft' ? '新建通道实例' : form.name || form.type}
                      </h2>
                      <Badge variant={form.source === 'legacy' ? 'warning' : 'info'} size="sm">
                        {form.source === 'legacy' ? 'Legacy 全局配置' : form.source === 'draft' ? '新实例' : 'Custom 实例'}
                      </Badge>
                    </div>
                    <p className="mt-2 text-sm text-surface-500">
                      {selectedCatalog?.description || '为该 Agent 配置独立的外部通道账号。'}
                    </p>
                  </div>
                  <div className="flex gap-3">
                    {isDraft ? (
                      <>
                        {draftStep > 1 && (
                          <Button variant="secondary" onClick={() => setDraftStep(current => Math.max(1, current - 1))}>
                            上一步
                          </Button>
                        )}
                        {draftStep < 3 && (
                          <Button
                            variant="primary"
                            onClick={() => setDraftStep(current => Math.min(3, current + 1))}
                            disabled={(draftStep === 1 && !draftStepOneReady) || (draftStep === 2 && !draftStepTwoReady)}
                          >
                            下一步
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
                              {draftTestResult ? '重新测试' : '开始测试'}
                            </Button>
                            <Button variant="primary" onClick={handleSave} isLoading={isSaving} disabled={!draftTestPassed}>
                              保存
                            </Button>
                          </>
                        )}
                      </>
                    ) : (
                      <>
                        {form.id && (
                          <Button variant="secondary" onClick={handleTestConnection} isLoading={isTesting}>
                            {testResult ? '重新测试连接' : '测试连接'}
                          </Button>
                        )}
                        {form.source === 'custom' && form.id && (
                          <Button variant="danger" onClick={handleDelete} isLoading={isDeleting}>
                            删除
                          </Button>
                        )}
                        <Button variant="primary" onClick={handleSave} isLoading={isSaving}>
                          保存
                        </Button>
                      </>
                    )}
                  </div>
                </div>

                {isDraft ? (
                  <>
                    <section className="space-y-4 rounded-[24px] border border-surface-200 bg-surface-50/70 p-5">
                      <div className="flex flex-col gap-1">
                        <h3 className="text-base font-semibold text-surface-900">创建向导</h3>
                        <p className="text-sm text-surface-500">
                          先选类型和目标 Agent，再填写凭据，最后测试连接并保存，避免一上来就面对整张大表单。
                        </p>
                      </div>
                      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                        {[
                          { id: 1, title: '选择类型与 Agent', ready: draftStepOneReady },
                          { id: 2, title: '填写凭据', ready: draftStepTwoReady },
                          { id: 3, title: '测试并保存', ready: draftTestPassed },
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
                                    {step.id === 1 ? '确定入口和接手 Agent' : step.id === 2 ? '完成必填账号信息' : '先验证账号再入库'}
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
                          <h3 className="text-base font-semibold text-surface-900">第一步：选择通道类型和绑定 Agent</h3>
                          <p className="text-sm text-surface-500">
                            这里只做路由决策，不在这一步填写复杂凭据。
                          </p>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <Select
                            label="通道类型"
                            value={form.type}
                            onChange={(event) => handleTypeChange(event.target.value)}
                            options={data.catalog.map(item => ({ value: item.type, label: item.label }))}
                          />
                          <Select
                            label="绑定 Agent"
                            value={form.agent_id}
                            onChange={(event) => handleFieldChange('agent_id', event.target.value)}
                            options={[
                              { value: '', label: '请选择 Agent' },
                              ...data.agents.map(agent => ({
                                value: agent.id,
                                label: `${agent.name} · ${agent.provider || '未设置 provider'} · ${agent.model || '未设置模型'}`,
                              })),
                            ]}
                            hint="后续来自这个通道账号的外部消息会优先路由到这里选中的 Agent。"
                          />
                          <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-4 md:col-span-2">
                            <label className="flex items-center gap-3">
                              <input
                                type="checkbox"
                                className="h-4 w-4 rounded border-surface-300 text-primary-600 focus:ring-primary-500"
                                checked={form.enabled}
                                onChange={(event) => handleFieldChange('enabled', event.target.checked)}
                              />
                              <span className="text-sm font-medium text-surface-700">创建后立即启用该通道实例</span>
                            </label>
                            <p className="mt-2 text-sm text-surface-500">
                              如果只是先录入账号，暂时不想接流量，也可以先关掉。
                            </p>
                          </div>
                        </div>
                      </section>
                    )}

                    {draftStep === 2 && (
                      <>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <Input
                            label="实例名称"
                            value={form.name}
                            onChange={(event) => handleFieldChange('name', event.target.value)}
                            placeholder={`例如：${selectedCatalog?.label || '通道'}销售一号`}
                            hint="建议用业务角色或账号用途命名，后面排查路由时更直观。"
                          />
                          <Textarea
                            label="允许来源"
                            value={form.allow_from_text}
                            onChange={(event) => handleFieldChange('allow_from_text', event.target.value)}
                            rows={4}
                            placeholder="每行一个用户标识，留空表示不限制。"
                            hint="支持逐行填写，也支持用逗号分隔。"
                          />
                        </div>

                        <section className="space-y-4 rounded-[24px] border border-surface-200 bg-surface-50/70 p-5">
                          <div className="flex items-center justify-between">
                            <div>
                              <h3 className="text-base font-semibold text-surface-900">第二步：填写必填凭据</h3>
                              <p className="text-sm text-surface-500">
                                先把真正影响连通性的字段填完，再决定是否补充其它可选参数。
                              </p>
                            </div>
                            {selectedCatalog && (
                              <Badge variant={draftStepTwoReady ? 'success' : 'warning'} size="sm">
                                {requiredFieldKeys.length > 0 ? `必填：${requiredFieldKeys.join('、')}` : '无必填字段'}
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
                                    <h4 className="text-sm font-semibold text-surface-900">可选参数</h4>
                                    <p className="text-sm text-surface-500">
                                      这些字段通常用于高级策略、兼容性或体验微调，不是首次接通的必要前置条件。
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
                              title="当前通道类型没有可渲染的字段"
                              description="请先选择一个通道类型。"
                            />
                          )}
                        </section>
                      </>
                    )}

                    {draftStep === 3 && (
                      <section className="space-y-4 rounded-[24px] border border-surface-200 bg-white p-5">
                        <div>
                          <h3 className="text-base font-semibold text-surface-900">第三步：测试连接并保存</h3>
                          <p className="text-sm text-surface-500">
                            先用当前草稿做一次真实连接测试。通过后再保存，避免把无效账号直接写进配置。
                          </p>
                        </div>

                        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
                          <div className="space-y-4">
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                              <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-4">
                                <p className="text-xs text-surface-500">通道类型</p>
                                <p className="mt-1 text-sm font-semibold text-surface-900">{selectedCatalog?.label || form.type}</p>
                              </div>
                              <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-4">
                                <p className="text-xs text-surface-500">目标 Agent</p>
                                <p className="mt-1 text-sm font-semibold text-surface-900">{getAgentLabel(form.agent_id)}</p>
                              </div>
                              <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-4">
                                <p className="text-xs text-surface-500">必填字段状态</p>
                                <p className="mt-1 text-sm font-semibold text-surface-900">{draftStepTwoReady ? '已完整' : '仍有缺失'}</p>
                              </div>
                            </div>

                            <div className="rounded-2xl border border-surface-200 bg-surface-50/70 px-4 py-4">
                              <div className="flex items-center justify-between gap-3">
                                <div>
                                  <h4 className="text-sm font-semibold text-surface-900">测试前检查清单</h4>
                                  <p className="mt-1 text-sm text-surface-500">
                                    先确认前置条件是否满足，再开始真实连接测试。
                                  </p>
                                </div>
                                <Badge variant={draftStepTwoReady ? 'success' : 'warning'} size="sm">
                                  {draftStepTwoReady ? '可开始测试' : '需先补齐'}
                                </Badge>
                              </div>
                              <div className="mt-4 space-y-3">
                                <div className="flex items-start justify-between gap-3 rounded-xl border border-surface-200 bg-white px-3 py-3">
                                  <div>
                                    <p className="text-sm font-medium text-surface-900">目标 Agent 已确定</p>
                                    <p className="mt-1 text-xs text-surface-500">这个账号收到的消息会优先分发到当前选中的 Agent。</p>
                                  </div>
                                  <Badge variant={form.agent_id ? 'success' : 'warning'} size="sm">
                                    {form.agent_id ? '已完成' : '未完成'}
                                  </Badge>
                                </div>
                                <div className="flex items-start justify-between gap-3 rounded-xl border border-surface-200 bg-white px-3 py-3">
                                  <div>
                                    <p className="text-sm font-medium text-surface-900">必填凭据已填写</p>
                                    <p className="mt-1 text-xs text-surface-500">
                                      {draftMissingFields.length > 0
                                        ? `仍缺少：${draftMissingFields.join('、')}`
                                        : '当前所选通道的必填字段都已填写。'}
                                    </p>
                                  </div>
                                  <Badge variant={draftStepTwoReady ? 'success' : 'warning'} size="sm">
                                    {draftStepTwoReady ? '已完成' : `${draftMissingFields.length} 项缺失`}
                                  </Badge>
                                </div>
                                <div className="flex items-start justify-between gap-3 rounded-xl border border-surface-200 bg-white px-3 py-3">
                                  <div>
                                    <p className="text-sm font-medium text-surface-900">最近测试结果</p>
                                    <p className="mt-1 text-xs text-surface-500">
                                      {draftTestPassed
                                        ? '最近一次草稿测试已通过，可以直接保存。'
                                        : draftTestResult
                                          ? '最近一次草稿测试失败，建议修正凭据后重新测试。'
                                          : '还没有执行过草稿测试。'}
                                    </p>
                                  </div>
                                  <Badge variant={draftTestPassed ? 'success' : draftTestResult ? 'warning' : 'default'} size="sm">
                                    {draftTestPassed ? '已通过' : draftTestResult ? '未通过' : '未测试'}
                                  </Badge>
                                </div>
                              </div>
                            </div>

                            {isTesting && (
                              <div className="rounded-2xl border border-primary-200 bg-primary-50 px-4 py-4 text-sm text-primary-700">
                                正在测试连接。系统会使用当前草稿配置发起真实连通性检查，完成后会自动刷新结果。
                              </div>
                            )}

                            {draftTestResult && (
                              <div className={`rounded-2xl border px-4 py-4 text-sm ${
                                draftTestResult.result.status === 'ok'
                                  ? 'border-accent-emerald/30 bg-accent-emerald/5 text-accent-emerald'
                                  : 'border-accent-orange/30 bg-accent-orange/5 text-accent-orange'
                              }`}>
                                <div className="flex flex-wrap items-center gap-3">
                                  <span>测试时间：{formatDateTime(draftTestResult.tested_at)}</span>
                                  <span>延迟：{draftTestResult.result.latency_ms} ms</span>
                                  <span>结果：{draftTestResult.result.status === 'ok' ? '通过' : '失败'}</span>
                                </div>
                                {draftConnectionFeedback && (
                                  <>
                                    <p className="mt-3 text-base font-semibold">{draftConnectionFeedback.title}</p>
                                    <p className="mt-1">{draftConnectionFeedback.summary}</p>
                                    {draftTestResult.result.error && draftTestResult.result.status !== 'ok' && (
                                      <div className="mt-3 rounded-xl border border-current/15 bg-white/60 px-3 py-3 text-xs leading-6 text-surface-700">
                                        原始错误：{draftTestResult.result.error}
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
                          </div>

                          <div className="space-y-4 rounded-2xl border border-surface-200 bg-surface-50/70 px-4 py-4">
                            <div>
                              <h4 className="text-sm font-semibold text-surface-900">下一步建议</h4>
                              <p className="mt-1 text-sm text-surface-500">
                                系统会根据当前状态明确告诉你下一步应该做什么。
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
                                ? '还不能开始测试。请先回到上一步补齐必填凭据。'
                                : draftTestPassed
                                  ? '测试已经通过。现在可以直接保存这个通道实例。'
                                  : draftTestResult
                                    ? '最近一次测试失败了。建议修正凭据后点击“重新测试”。'
                                    : '所有前置条件都已满足，现在可以点击“开始测试”。'}
                            </div>
                            <div className="flex flex-col gap-3">
                              <Button
                                variant="secondary"
                                onClick={handleTestConnection}
                                isLoading={isTesting}
                                disabled={!canRunDraftTest}
                              >
                                {isTesting ? '正在测试连接...' : draftTestResult ? '重新测试连接' : '开始测试连接'}
                              </Button>
                              <Button
                                variant="primary"
                                onClick={handleSave}
                                isLoading={isSaving}
                                disabled={!draftTestPassed}
                              >
                                {draftTestPassed ? '保存这个通道实例' : '测试通过后才能保存'}
                              </Button>
                            </div>
                            <div className="rounded-xl border border-surface-200 bg-white px-3 py-3 text-sm text-surface-600">
                              保存策略：
                              当前向导要求先测试成功再保存。这样创建出来的实例默认就是“可连通”的，后面在路由排查时不会混入半成品配置。
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
                        label="实例名称"
                        value={form.name}
                        onChange={(event) => handleFieldChange('name', event.target.value)}
                        placeholder="例如：飞书销售一号"
                        hint="建议用业务视角命名，方便看出这个账号接到哪类外部消息。"
                      />
                      <Select
                        label="通道类型"
                        value={form.type}
                        onChange={(event) => handleTypeChange(event.target.value)}
                        disabled={form.source !== 'draft'}
                        options={data.catalog.map(item => ({ value: item.type, label: item.label }))}
                      />
                      <Select
                        label="绑定 Agent"
                        value={form.agent_id}
                        onChange={(event) => handleFieldChange('agent_id', event.target.value)}
                        options={[
                          { value: '', label: '暂不绑定' },
                          ...data.agents.map(agent => ({
                            value: agent.id,
                            label: `${agent.name} · ${agent.provider || '未设置 provider'} · ${agent.model || '未设置模型'}`,
                          })),
                        ]}
                        hint="外部消息会优先路由到这里选择的 Agent。"
                      />
                      <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-4">
                        <label className="flex items-center gap-3">
                          <input
                            type="checkbox"
                            className="h-4 w-4 rounded border-surface-300 text-primary-600 focus:ring-primary-500"
                            checked={form.enabled}
                            onChange={(event) => handleFieldChange('enabled', event.target.checked)}
                          />
                          <span className="text-sm font-medium text-surface-700">启用该通道实例</span>
                        </label>
                        <p className="mt-2 text-sm text-surface-500">
                          关闭后会保留配置，但不会实际接收和发送外部消息。
                        </p>
                      </div>
                    </div>

                    <Textarea
                      label="允许来源"
                      value={form.allow_from_text}
                      onChange={(event) => handleFieldChange('allow_from_text', event.target.value)}
                      rows={4}
                      placeholder="每行一个用户标识，留空表示不限制。"
                      hint="支持逐行填写，也支持用逗号分隔。"
                    />

                    <section className="space-y-4 rounded-[24px] border border-surface-200 bg-surface-50/70 p-5">
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="text-base font-semibold text-surface-900">账号凭据与通道参数</h3>
                          <p className="text-sm text-surface-500">
                            这里只配置这个通道实例自己的账号信息，不再走全局 configuration。
                          </p>
                        </div>
                        {selectedCatalog && (
                          <Badge variant={draftStepTwoReady ? 'success' : 'warning'} size="sm">
                            {selectedCatalog.required_fields.length > 0
                              ? `必填：${selectedCatalog.required_fields.join('、')}`
                              : '无必填字段'}
                          </Badge>
                        )}
                      </div>

                      {selectedCatalog ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {selectedCatalog.fields.map(renderChannelField)}
                        </div>
                      ) : (
                        <Empty
                          title="当前通道类型没有可渲染的字段"
                          description="请先选择一个通道类型。"
                        />
                      )}
                    </section>

                    {form.source === 'legacy' && (
                      <div className="rounded-2xl border border-accent-orange/30 bg-accent-orange/5 px-4 py-4 text-sm text-accent-orange">
                        这是从旧版全局 `channels.*` 自动投影出来的 legacy 配置。可以直接编辑继续使用，也可以新建 custom 实例后逐步迁移。
                      </div>
                    )}

                    <section className="space-y-4 rounded-[24px] border border-surface-200 bg-white p-5">
                      <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                        <div>
                          <h3 className="text-base font-semibold text-surface-900">运行状态与最近事件</h3>
                          <p className="text-sm text-surface-500">
                            这里会显示最近的收发、测试连接和错误事件，便于判断当前通道是否真正可用。
                          </p>
                        </div>
                        {testResult && (
                          <Badge variant={testResult.result.status === 'ok' ? 'success' : 'warning'} size="sm">
                            最近测试：{testResult.result.status === 'ok' ? '通过' : '失败'}
                          </Badge>
                        )}
                      </div>

                      {currentSummary && (
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                          <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-3">
                            <p className="text-xs text-surface-500">收到消息</p>
                            <p className="mt-1 text-xl font-semibold text-surface-900">{currentSummary.messages_received}</p>
                          </div>
                          <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-3">
                            <p className="text-xs text-surface-500">发送消息</p>
                            <p className="mt-1 text-xl font-semibold text-surface-900">{currentSummary.messages_sent}</p>
                          </div>
                          <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-3">
                            <p className="text-xs text-surface-500">错误次数</p>
                            <p className="mt-1 text-xl font-semibold text-accent-red">{currentSummary.errors}</p>
                          </div>
                          <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-3">
                            <p className="text-xs text-surface-500">最近事件</p>
                            <p className="mt-1 text-sm font-medium text-surface-900">{formatDateTime(currentSummary.last_event_at)}</p>
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
                            <span>测试时间：{formatDateTime(testResult.tested_at)}</span>
                            <span>延迟：{testResult.result.latency_ms} ms</span>
                          </div>
                          {savedConnectionFeedback && (
                            <>
                              <p className="mt-3 text-base font-semibold">{savedConnectionFeedback.title}</p>
                              <p className="mt-1">{savedConnectionFeedback.summary}</p>
                              {testResult.result.error && testResult.result.status !== 'ok' && (
                                <div className="mt-3 rounded-xl border border-current/15 bg-white/60 px-3 py-3 text-xs leading-6 text-surface-700">
                                  原始错误：{testResult.result.error}
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
                                <span className="text-xs text-surface-500">{formatDateTime(event.timestamp)}</span>
                              </div>
                              <p className="mt-2 text-sm text-surface-900">{event.message}</p>
                            </div>
                          ))
                        ) : (
                          <Empty
                            title="暂无运行事件"
                            description="保存配置、测试连接或实际收发消息后，这里会开始积累运行轨迹。"
                          />
                        )}
                      </div>
                    </section>
                  </>
                )}
              </div>
            ) : (
              <Empty
                title="没有可编辑的通道"
                description="请先创建一个通道实例。"
              />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default ChannelsPage;
