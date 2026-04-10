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
