import type { MCPInputSchema, MCPOutputSchema } from '../../types/webmcp';

export interface WebMCPToolDefinition {
  name: string;
  description: string;
  inputSchema: MCPInputSchema;
  outputSchema?: MCPOutputSchema;
  execute: (params: Record<string, unknown>) => Promise<WebMCPToolResult>;
}

export interface WebMCPToolResult {
  success: boolean;
  data?: unknown;
  error?: string;
  message?: string;
}

export interface ChatSendParams {
  message: string;
  session_key?: string;
}

export interface ChatHistoryParams {
  session_key: string;
  limit?: number;
}

export interface TaskCreateParams {
  name: string;
  cron_expr: string;
  prompt: string;
  channels?: Array<{
    channel: string;
    to: string;
  }>;
}

export interface TaskDeleteParams {
  task_id: string;
}

export interface TaskRunParams {
  task_id: string;
}

export interface ConfigSetProviderParams {
  provider: string;
  api_key: string;
  model?: string;
}
