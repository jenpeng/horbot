export interface TaskSchedule {
  kind: 'every' | 'cron' | 'at';
  at_ms?: number;
  every_ms?: number;
  expr?: string;
  tz?: string;
}

export interface DeliveryTarget {
  channel: string;
  to: string;
}

export interface TaskPayload {
  kind: string;
  message: string;
  deliver: boolean;
  channel?: string;
  to?: string;
  channels?: DeliveryTarget[];
  notify?: boolean;
}

export interface TaskState {
  next_run_at_ms?: number;
  last_run_at_ms?: number;
  last_status?: string;
  last_error?: string;
}

export interface Task {
  id: string;
  name: string;
  enabled: boolean;
  schedule: TaskSchedule;
  payload: TaskPayload;
  state: TaskState;
  created_at_ms: number;
  updated_at_ms: number;
  delete_after_run: boolean;
}

export interface ChannelConfig {
  enabled: boolean;
  allow_from: string[];
}

export interface ChannelCatalogField {
  key: string;
  label: string;
  secret?: boolean;
  placeholder?: string;
  type?: 'text' | 'boolean' | 'number';
}

export interface ChannelCatalogEntry {
  type: string;
  label: string;
  description: string;
  required_fields: string[];
  fields: ChannelCatalogField[];
}

export interface ChannelEndpointAgent {
  id: string;
  name: string;
  model: string;
  provider: string;
}

export interface ChannelEndpoint {
  id: string;
  type: string;
  name: string;
  enabled: boolean;
  agent_id: string;
  allow_from: string[];
  config: Record<string, unknown>;
  source: 'legacy' | 'custom';
  missing_fields: string[];
  status: 'ready' | 'incomplete' | 'disabled';
  runtime?: ChannelEndpointRuntimeSummary;
}

export interface ChannelEndpointRuntimeSummary {
  endpoint_id: string;
  messages_sent: number;
  messages_received: number;
  errors: number;
  last_event_at: string | null;
  last_event_type: string | null;
  last_status: string | null;
  last_message: string | null;
  last_inbound_at: string | null;
  last_outbound_at: string | null;
  last_error_at: string | null;
  last_error_message: string | null;
}

export interface ChannelEndpointEvent {
  timestamp: string;
  endpoint_id: string;
  channel_type: string;
  event_type: string;
  status: string;
  message: string;
  details: Record<string, unknown>;
}

export interface ChannelEndpointEventsResponse {
  endpoint: ChannelEndpoint;
  summary: ChannelEndpointRuntimeSummary;
  events: ChannelEndpointEvent[];
}

export interface ChannelEndpointTestResponse {
  endpoint: ChannelEndpoint;
  tested_at: string;
  result: {
    name: string;
    enabled: boolean;
    status: 'ok' | 'error' | 'disabled';
    latency_ms: number;
    error: string | null;
    error_code?: string | null;
    error_kind?: string | null;
    remediation?: string[];
  };
  summary: ChannelEndpointRuntimeSummary;
  events: ChannelEndpointEvent[];
}

export interface ChannelEndpointDraftTestResponse {
  endpoint: ChannelEndpoint;
  tested_at: string;
  result: {
    name: string;
    enabled: boolean;
    status: 'ok' | 'error' | 'disabled';
    latency_ms: number;
    error: string | null;
    error_code?: string | null;
    error_kind?: string | null;
    remediation?: string[];
  };
}

export interface ChannelEndpointsResponse {
  endpoints: ChannelEndpoint[];
  catalog: ChannelCatalogEntry[];
  agents: ChannelEndpointAgent[];
  counts: {
    total: number;
    enabled: number;
    ready: number;
    incomplete: number;
  };
}

export interface ChannelEndpointPayload {
  id?: string;
  type: string;
  name: string;
  agent_id: string;
  enabled: boolean;
  allow_from: string[];
  config: Record<string, unknown>;
}

export interface WhatsAppConfig extends ChannelConfig {
  bridge_url: string;
  bridge_token: string;
}

export interface TelegramConfig extends ChannelConfig {
  token: string;
  proxy?: string;
  reply_to_message: boolean;
}

export interface DiscordConfig extends ChannelConfig {
  token: string;
  gateway_url: string;
  intents: number;
}

export interface FeishuConfig extends ChannelConfig {
  app_id: string;
  app_secret: string;
  encrypt_key: string;
  verification_token: string;
}

export interface DingTalkConfig extends ChannelConfig {
  client_id: string;
  client_secret: string;
}

export interface MatrixConfig extends ChannelConfig {
  homeserver: string;
  access_token: string;
  user_id: string;
  device_id: string;
  e2ee_enabled: boolean;
  sync_stop_grace_seconds: number;
  max_media_bytes: number;
  group_policy: 'open' | 'mention' | 'allowlist';
  group_allow_from: string[];
  allow_room_mentions: boolean;
}

export interface EmailConfig extends ChannelConfig {
  consent_granted: boolean;
  imap_host: string;
  imap_port: number;
  imap_username: string;
  imap_password: string;
  imap_mailbox: string;
  imap_use_ssl: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_password: string;
  smtp_use_tls: boolean;
  smtp_use_ssl: boolean;
  from_address: string;
  auto_reply_enabled: boolean;
  poll_interval_seconds: number;
  mark_seen: boolean;
  max_body_chars: number;
  subject_prefix: string;
}

export interface SlackDMConfig {
  enabled: boolean;
  policy: 'open' | 'allowlist';
  allow_from: string[];
}

export interface SlackConfig extends ChannelConfig {
  mode: string;
  webhook_path: string;
  bot_token: string;
  app_token: string;
  user_token_read_only: boolean;
  reply_in_thread: boolean;
  react_emoji: string;
  group_policy: 'mention' | 'open' | 'allowlist';
  group_allow_from: string[];
  dm: SlackDMConfig;
}

export interface QQConfig extends ChannelConfig {
  app_id: string;
  secret: string;
}

export interface ChannelsConfig {
  send_progress: boolean;
  send_tool_hints: boolean;
  endpoints?: ChannelEndpoint[];
  whatsapp: WhatsAppConfig;
  telegram: TelegramConfig;
  discord: DiscordConfig;
  feishu: FeishuConfig;
  dingtalk: DingTalkConfig;
  email: EmailConfig;
  slack: SlackConfig;
  qq: QQConfig;
  matrix: MatrixConfig;
}

export interface Session {
  key: string;
  title: string;
  created_at: string;
  message_count: number;
}

export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
  execution_steps?: ExecutionStep[];
  metadata?: Record<string, unknown>;
}

export interface ExecutionStep {
  id: string;
  type: string;
  title: string;
  status: 'running' | 'completed' | 'failed' | 'pending' | 'stopped' | 'skipped' | 'error' | 'success';
  timestamp: string;
  details?: Record<string, unknown>;
}

export interface Skill {
  name: string;
  source: 'builtin' | 'user';
  path: string;
  description: string;
  available: boolean;
  enabled: boolean;
  always: boolean;
  requires: Record<string, unknown>;
  schema: string;
  schema_version: number | null;
  source_schema: string;
  source_schema_version: number | null;
  normalized_from_legacy: boolean;
  install?: SkillInstallOption[];
  missing_requirements?: string[];
}

export interface SkillDetail extends Skill {
  content: string;
  metadata: Record<string, unknown>;
}

export interface SkillInstallOption {
  id?: string;
  kind?: string;
  formula?: string;
  package?: string;
  bins?: string[];
  label?: string;
  command?: string;
}

export interface ProviderConfig {
  apiKey: string;
  hasApiKey?: boolean;
  apiKeyMasked?: string;
  apiBase?: string;
  extraHeaders?: Record<string, string>;
}

export interface ProvidersConfig {
  custom: ProviderConfig;
  anthropic: ProviderConfig;
  openai: ProviderConfig;
  openrouter: ProviderConfig;
  deepseek: ProviderConfig;
  groq: ProviderConfig;
  zhipu: ProviderConfig;
  dashscope: ProviderConfig;
  vllm: ProviderConfig;
  gemini: ProviderConfig;
  moonshot: ProviderConfig;
  minimax: ProviderConfig;
  aihubmix: ProviderConfig;
  siliconflow: ProviderConfig;
  volcengine: ProviderConfig;
  openai_codex: ProviderConfig;
  github_copilot: ProviderConfig;
  [key: string]: ProviderConfig;
}

export interface AgentDefaults {
  workspace: string;
  maxTokens: number;
  temperature: number;
  maxToolIterations: number;
  memoryWindow: number;
  models: ModelsConfig;
}

export interface ModelConfig {
  provider: string;
  model: string;
  description: string;
  capabilities: string[];
}

export interface ModelsConfig {
  main: ModelConfig;
  planning: ModelConfig;
  file: ModelConfig;
  image: ModelConfig;
  audio: ModelConfig;
  video: ModelConfig;
}

export interface AgentsConfig {
  defaults: AgentDefaults;
}

export interface TeamConfig {
  id: string;
  name: string;
  description?: string;
  members: string[];
  workspace?: string;
}

export interface TeamsConfig {
  instances: Record<string, TeamConfig>;
}

export interface MCPServerConfig {
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  url?: string;
  tool_timeout?: number;
  headers?: Record<string, string>;
  has_secret_values?: boolean;
}

export interface PermissionConfig {
  profile: string;
  allow: string[];
  deny: string[];
  confirm: string[];
}

export interface ToolsConfig {
  web?: {
    search?: {
      provider?: string;
      apiKey?: string;
      hasApiKey?: boolean;
      apiKeyMasked?: string;
      maxResults?: number;
    };
  };
  exec?: {
    timeout?: number;
    pathAppend?: string;
  };
  restrictToWorkspace?: boolean;
  mcpServers?: Record<string, MCPServerConfig>;
  permission?: PermissionConfig;
}

export interface WebSearchProvider {
  id: string;
  name: string;
  description: string;
  requires_api_key: boolean;
  api_key_url?: string;
}

export interface Config {
  agents: AgentsConfig;
  teams: TeamsConfig;
  channels: ChannelsConfig;
  providers: ProvidersConfig;
  gateway: {
    host: string;
    port: number;
    adminToken?: string;
    allowRemoteWithoutToken?: boolean;
    heartbeat: {
      enabled: boolean;
      interval_s: number;
    };
  };
  tools: ToolsConfig;
  autonomous: {
    enabled: boolean;
    maxPlanSteps: number;
    stepTimeout: number;
    totalTimeout: number;
    retryCount: number;
    retryDelay: number;
    confirmSensitive: boolean;
    sensitiveOperations: string[];
    protectedPaths: string[];
  };
}

export interface TokenUsageRecord {
  id: string;
  timestamp: string;
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  session_id?: string;
  request_type?: string;
}

export interface TokenUsageStats {
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_requests: number;
  total_cost: number;
  by_provider: Record<string, { input: number; output: number; total: number; cost: number }>;
  by_model: Record<string, { input: number; output: number; total: number; cost: number }>;
  by_day: Array<{
    date: string;
    input: number;
    output: number;
    total: number;
    cost: number;
  }>;
}

export interface SystemStatus {
  status: 'running' | 'stopped' | 'error';
  version: string;
  uptime: string;
  uptime_seconds: number;
  system: {
    cpu_percent: number;
    memory: {
      total: number;
      available: number;
      used: number;
      percent: number;
    };
    disk: {
      total: number;
      used: number;
      free: number;
      percent: number;
    };
  };
  services: {
    cron: {
      enabled: boolean;
      jobs_count: number;
      next_wake_at_ms?: number;
    };
    agent: {
      initialized: boolean;
    };
  };
  config: {
    workspace: string;
    model?: string;
    provider?: string;
  };
}

export interface DashboardChannelSummary {
  name: string;
  display_name: string;
  enabled: boolean;
  configured: boolean;
  status: 'online' | 'disabled' | 'error';
  status_label: string;
  reason?: string | null;
  missing_fields: string[];
}

export interface DashboardActivitySummary {
  id: string;
  type: 'system' | 'channel' | 'task' | 'agent';
  message: string;
  time: string;
  status: 'success' | 'warning' | 'info' | 'error';
}

export interface DashboardAlertSummary {
  id: string;
  level: 'warning' | 'error' | 'info';
  title: string;
  message: string;
}

export interface DashboardSummary {
  generated_at: string;
  system_status: SystemStatus;
  provider: {
    name?: string | null;
    configured: boolean;
  };
  channels: {
    items: DashboardChannelSummary[];
    counts: {
      total: number;
      enabled: number;
      online: number;
      disabled: number;
      misconfigured: number;
    };
  };
  recent_activities: DashboardActivitySummary[];
  alerts: DashboardAlertSummary[];
}

export interface Plan {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'confirmed' | 'running' | 'completed' | 'cancelled' | 'stopped';
  created_at: string;
  updated_at: string;
  session_key: string;
  subtasks: Subtask[];
  spec?: {
    why: string;
    what_changes: string[];
    impact: Record<string, unknown>;
  };
  checklist?: {
    items: string[];
  };
}

export interface Subtask {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  tools: string[];
}

export interface SubagentInfo {
  task_id: string;
  label: string;
  status: 'running' | 'completed' | 'failed' | 'cancelled';
  session_key: string;
  plan_id?: string;
  subtask_id?: string;
  started_at: string;
  completed_at?: string;
  input_tokens: number;
  output_tokens: number;
  result?: string;
  error?: string;
}
