import api from './api';

export interface SubTask {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  tools: string[];
  result: string;
  required_skills?: string[];
  required_mcp_tools?: string[];
}

export interface PlanSpec {
  why: string;
  what_changes: string[];
  impact: {
    affected_specs?: string[];
    affected_code?: string[];
  };
}

export interface PlanChecklistItem {
  id: string;
  description: string;
  category: string;
  checked: boolean;
}

export interface PlanChecklist {
  items: PlanChecklistItem[];
}

export interface Plan {
  id: string;
  title: string;
  description: string;
  subtasks: SubTask[];
  status: 'pending' | 'confirmed' | 'cancelled' | 'running' | 'completed' | 'stopped';
  created_at: string;
  updated_at: string;
  session_key: string;
  message_id: string;
  spec?: PlanSpec;
  checklist?: PlanChecklist;
  spec_content?: string;
  tasks_content?: string;
  checklist_content?: string;
  folder?: string;
  plan_type?: 'informational' | 'actionable';
  content?: string;
  report_content?: string;
}

export interface PlanStep {
  id: string;
  description: string;
  tool_name: string | null;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  result?: string;
  error?: string;
}

export interface SimplePlan {
  id: string;
  title: string;
  steps: PlanStep[];
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  progress: number;
}

interface PlanLogsResponse {
  logs: Record<string, { logs: Array<{ type: string; message?: string; content?: string; timestamp?: number | string; data?: unknown }> }>;
}

interface CancelResponse {
  status: string;
}

interface StopResponse {
  status: string;
}

export const planService = {
  getPlan: async (id: string): Promise<SimplePlan> => {
    const response = await api.get<SimplePlan>(`/api/plans/${id}`);
    return response.data;
  },

  getPlanLogs: async (planId: string): Promise<PlanLogsResponse> => {
    const response = await api.get<PlanLogsResponse>(`/api/plan/${planId}/logs`);
    return response.data;
  },

  cancelPlan: async (planId: string, sessionKey: string): Promise<CancelResponse> => {
    const response = await api.post<CancelResponse>(`/api/plan/${planId}/cancel`, {
      plan_id: planId,
      session_key: sessionKey,
    });
    return response.data;
  },

  stopPlan: async (planId: string, sessionKey: string): Promise<StopResponse> => {
    const response = await api.post<StopResponse>(`/api/plan/${planId}/stop`, {
      plan_id: planId,
      session_key: sessionKey,
    });
    return response.data;
  },

  pausePlan: async (planId: string): Promise<void> => {
    await api.post(`/api/plans/${planId}/pause`);
  },

  resumePlan: async (planId: string): Promise<void> => {
    await api.post(`/api/plans/${planId}/resume`);
  },

  confirmPlanStream: (planId: string, sessionKey: string): { url: string; body: string } => {
    return {
      url: `/api/plan/${planId}/confirm`,
      body: JSON.stringify({
        plan_id: planId,
        session_key: sessionKey,
      }),
    };
  },
};

export default planService;
