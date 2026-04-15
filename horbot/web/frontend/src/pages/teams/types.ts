export interface AgentInfo {
  id: string;
  name: string;
  description: string;
  external?: boolean;
  transport?: 'http' | 'http_sse' | 'websocket';
  endpoint?: string;
  dm_enabled?: boolean;
  team_enabled?: boolean;
  profile?: string;
  permission_profile?: string;
  tool_permission_profile?: string;
  model: string;
  provider: string;
  capabilities: string[];
  tools: string[];
  skills: string[];
  teams: string[];
  setup_required?: boolean;
  bootstrap_setup_pending?: boolean;
  workspace?: string;
  effective_workspace?: string;
  system_prompt?: string;
  personality?: string;
  avatar?: string;
  evolution_enabled?: boolean;
  learning_enabled?: boolean;
  memory_bank_profile?: {
    mission?: string;
    directives?: string[];
    reasoning_style?: string;
  };
}

export interface MemoryBankProfileDraft {
  mission: string;
  directives: string[];
  reasoning_style: string;
}

export interface AgentFormState {
  id: string;
  name: string;
  description: string;
  profile: string;
  permission_profile: string;
  model: string;
  provider: string;
  system_prompt: string;
  capabilities: string[];
  tools: string[];
  skills: string[];
  workspace: string;
  teams: string[];
  personality: string;
  avatar: string;
  evolution_enabled: boolean;
  learning_enabled: boolean;
  memory_bank_profile: MemoryBankProfileDraft;
}

export interface TeamMemberProfile {
  role?: string;
  responsibility?: string;
  priority?: number;
  isLead?: boolean;
}

export interface TeamFormState {
  id: string;
  name: string;
  description: string;
  members: string[];
  member_profiles: Record<string, TeamMemberProfile>;
  workspace: string;
}

export interface TeamInfo {
  id: string;
  name: string;
  description: string;
  members: string[];
  member_profiles?: Record<string, TeamMemberProfile>;
  workspace?: string;
  effective_workspace?: string;
}

export interface ExternalAgentInfo {
  id: string;
  name: string;
  description: string;
  avatar?: string;
  transport: 'http' | 'http_sse' | 'websocket';
  endpoint: string;
  auth_type: 'none' | 'bearer' | 'header';
  auth_header: string;
  auth_secret_configured?: boolean;
  capabilities: string[];
  dm_enabled: boolean;
  team_enabled: boolean;
  mention_required: boolean;
  timeout_s: number;
  max_turn_chars: number;
  context_scope: 'message_only' | 'recent_turns' | 'dm_summary';
  memory_access: 'none' | 'summary_only';
  file_access: 'none' | 'referenced_only';
  metadata?: Record<string, unknown>;
}

export interface ProviderInfo {
  id: string;
  name: string;
  configured: boolean;
  models: { id: string; name: string; description: string }[];
}

export interface TeamsPageSelection {
  kind: 'agent' | 'team' | 'external-agent';
  id: string | null;
}

export type TeamsPageFocusTarget =
  | 'agent-overview'
  | 'agent-runtime'
  | 'agent-tool-audits'
  | 'agent-summary'
  | 'agent-files'
  | 'agent-file-agents'
  | 'agent-file-soul'
  | 'agent-file-user'
  | 'team-overview'
  | 'team-members'
  | 'team-workspace'
  | 'team-collaboration';

export interface ExternalAgentFormState {
  id: string;
  name: string;
  description: string;
  avatar: string;
  transport: 'http' | 'http_sse' | 'websocket';
  endpoint: string;
  auth_type: 'none' | 'bearer' | 'header';
  auth_header: string;
  auth_secret: string;
  auth_secret_configured?: boolean;
  capabilities: string[];
  dm_enabled: boolean;
  team_enabled: boolean;
  mention_required: boolean;
  timeout_s: number;
  max_turn_chars: number;
  context_scope: 'message_only' | 'recent_turns' | 'dm_summary';
  memory_access: 'none' | 'summary_only';
  file_access: 'none' | 'referenced_only';
  metadata: Record<string, unknown>;
}

export interface AgentBootstrapFile {
  path: string;
  exists: boolean;
  content: string;
}

export interface AgentAssetBundle {
  workspace_path: string;
  summary?: {
    identity?: string[];
    role_focus?: string[];
    communication_style?: string[];
    boundaries?: string[];
    user_preferences?: string[];
    is_structured?: boolean;
    source_titles?: {
      soul?: string;
      user?: string;
    };
  };
  files: {
    agents: AgentBootstrapFile;
    soul: AgentBootstrapFile;
    user: AgentBootstrapFile;
  };
}

export type SummarySectionKey =
  | 'identity'
  | 'role_focus'
  | 'communication_style'
  | 'boundaries'
  | 'user_preferences';

export type SummaryDrafts = Record<SummarySectionKey, string>;

export interface AgentMemoryStats {
  total_entries: number;
  total_size_kb: number;
}

export interface AgentSkillInfo {
  name: string;
  source: string;
  enabled: boolean;
  always?: boolean;
}

export interface AgentToolAuditItem {
  type: string;
  task: string;
  result?: string | null;
  tool_name: string;
  tools_used?: string[];
  timestamp: string;
  message_count?: number;
  guard_blocked?: boolean;
  guard_reasons?: string[];
  permission_level?: string | null;
  duration_ms?: number | null;
  error?: string | null;
  audit_event?: {
    event_type?: string;
    session_key?: string;
    origin?: string;
    source_channel?: string;
    source_chat_id?: string;
    guard_blocked?: boolean;
    guard_reasons?: string[];
    result_redacted?: boolean;
    permission_level?: string;
    duration_ms?: number;
  };
}

export interface AgentToolAuditSummary {
  window_hours: number;
  total_count: number;
  blocked_count: number;
  error_count: number;
  exec_count: number;
  outbound_count: number;
}

export type ToolAuditRiskFilter = 'all' | 'blocked' | 'exec' | 'outbound' | 'error';

export interface AgentToolAuditBundle {
  agent_id?: string | null;
  session_key?: string | null;
  risk_kind?: ToolAuditRiskFilter;
  window_hours?: number;
  limit: number;
  total_returned: number;
  total_matches: number;
  blocked_count: number;
  error_count: number;
  summary: AgentToolAuditSummary;
  items: AgentToolAuditItem[];
}
