import api from './api';

export type TaskWorkspaceStatus = 'ready' | 'running' | 'blocked' | 'done' | 'failed';
export type TaskWorkspaceMode = 'conversation' | 'current' | 'scratch' | 'worktree';

export interface TaskWorkspace {
  id: string;
  title: string;
  agent_id?: string | null;
  conversation_id?: string | null;
  session_key?: string | null;
  status: TaskWorkspaceStatus;
  cwd: string;
  workspace_mode: TaskWorkspaceMode;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface TaskWorkspaceFile {
  path: string;
  name: string;
  kind: 'file' | 'directory';
  size?: number | null;
  modified_at?: string;
}

export interface TaskWorkspaceFilesPayload {
  task_id: string;
  cwd: string;
  exists: boolean;
  files: TaskWorkspaceFile[];
  truncated: boolean;
}

export interface CreateTaskWorkspacePayload {
  title: string;
  agent_id?: string | null;
  conversation_id?: string | null;
  session_key?: string | null;
  cwd?: string | null;
  workspace_mode?: TaskWorkspaceMode;
  metadata?: Record<string, unknown>;
}

export interface UpdateTaskWorkspacePayload {
  title?: string;
  status?: TaskWorkspaceStatus;
  cwd?: string;
  workspace_mode?: TaskWorkspaceMode;
  metadata?: Record<string, unknown>;
}

interface TaskWorkspaceListResponse {
  task_workspaces: TaskWorkspace[];
}

export const taskWorkspacesService = {
  list: async (params: {
    conversation_id?: string | null;
    agent_id?: string | null;
    session_key?: string | null;
  } = {}): Promise<TaskWorkspace[]> => {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value) {
        searchParams.set(key, value);
      }
    });
    const suffix = searchParams.toString() ? `?${searchParams.toString()}` : '';
    const response = await api.get<TaskWorkspaceListResponse>(`/api/task-workspaces${suffix}`);
    return response.data.task_workspaces || [];
  },

  create: async (payload: CreateTaskWorkspacePayload): Promise<TaskWorkspace> => {
    const response = await api.post<TaskWorkspace>('/api/task-workspaces', payload);
    return response.data;
  },

  update: async (taskId: string, payload: UpdateTaskWorkspacePayload): Promise<TaskWorkspace> => {
    const response = await api.patch<TaskWorkspace>(`/api/task-workspaces/${taskId}`, payload);
    return response.data;
  },

  listFiles: async (taskId: string, limit = 80): Promise<TaskWorkspaceFilesPayload> => {
    const response = await api.get<TaskWorkspaceFilesPayload>(`/api/task-workspaces/${taskId}/files?limit=${limit}`);
    return response.data;
  },
};

export default taskWorkspacesService;
