export interface AgentInfo {
  id: string;
  name: string;
  description: string;
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

export interface ProviderInfo {
  id: string;
  name: string;
  configured: boolean;
  models: { id: string; name: string; description: string }[];
}

export interface TeamsPageSelection {
  kind: 'agent' | 'team';
  id: string | null;
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
