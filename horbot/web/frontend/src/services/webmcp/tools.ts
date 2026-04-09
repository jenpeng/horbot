import type { WebMCPToolDefinition, WebMCPToolResult } from './types';
import chatService from '../chat';
import tasksService from '../tasks';
import statusService from '../status';
import configService from '../config';
import channelsService from '../channels';

const createChatTools = (): WebMCPToolDefinition[] => [
  {
    name: 'horbot_chat_send',
    description: '发送消息给 Horbot AI 助手并获取响应。用于与 AI 进行对话交互。',
    inputSchema: {
      type: 'object',
      properties: {
        message: {
          type: 'string',
          description: '要发送给 AI 的消息内容',
        },
        session_key: {
          type: 'string',
          description: '会话标识符，可选。不提供则使用默认会话。',
        },
      },
      required: ['message'],
    },
    execute: async (params): Promise<WebMCPToolResult> => {
      try {
        const { message, session_key } = params as { message: string; session_key?: string };
        const result = await chatService.sendMessage({
          content: message,
          session_key: session_key || 'default',
        });
        return {
          success: true,
          data: result,
          message: '消息发送成功',
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : '发送消息失败',
        };
      }
    },
  },
  {
    name: 'horbot_chat_history',
    description: '获取指定会话的聊天历史记录。',
    inputSchema: {
      type: 'object',
      properties: {
        session_key: {
          type: 'string',
          description: '会话标识符',
        },
        limit: {
          type: 'number',
          description: '返回的消息数量限制，可选',
        },
      },
      required: ['session_key'],
    },
    execute: async (params): Promise<WebMCPToolResult> => {
      try {
        const { session_key } = params as { session_key: string };
        const result = await chatService.getMessages(session_key);
        return {
          success: true,
          data: result.messages,
          message: `获取到 ${result.messages.length} 条消息`,
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : '获取历史记录失败',
        };
      }
    },
  },
  {
    name: 'horbot_chat_new_session',
    description: '创建一个新的聊天会话。',
    inputSchema: {
      type: 'object',
      properties: {
        title: {
          type: 'string',
          description: '会话标题，可选',
        },
      },
      required: [],
    },
    execute: async (params): Promise<WebMCPToolResult> => {
      try {
        const { title } = params as { title?: string };
        const result = await chatService.createSession(title ? { title } : undefined);
        return {
          success: true,
          data: { session_key: result.session_key },
          message: '会话创建成功',
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : '创建会话失败',
        };
      }
    },
  },
  {
    name: 'horbot_chat_sessions',
    description: '获取所有聊天会话列表。',
    inputSchema: {
      type: 'object',
      properties: {},
      required: [],
    },
    execute: async (): Promise<WebMCPToolResult> => {
      try {
        const result = await chatService.getSessions();
        return {
          success: true,
          data: result.sessions,
          message: `获取到 ${result.sessions.length} 个会话`,
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : '获取会话列表失败',
        };
      }
    },
  },
];

const createTaskTools = (): WebMCPToolDefinition[] => [
  {
    name: 'horbot_task_list',
    description: '获取所有定时任务列表。',
    inputSchema: {
      type: 'object',
      properties: {},
      required: [],
    },
    execute: async (): Promise<WebMCPToolResult> => {
      try {
        const tasks = await tasksService.getTasks();
        return {
          success: true,
          data: tasks,
          message: `获取到 ${tasks.length} 个任务`,
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : '获取任务列表失败',
        };
      }
    },
  },
  {
    name: 'horbot_task_create',
    description: '创建一个新的定时任务。任务将按照指定的 cron 表达式定期执行。',
    inputSchema: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          description: '任务名称',
        },
        cron_expr: {
          type: 'string',
          description: 'Cron 表达式，如 "0 9 * * *" 表示每天早上9点执行',
        },
        prompt: {
          type: 'string',
          description: '任务执行时要发送给 AI 的提示内容',
        },
        channels: {
          type: 'array',
          description: '推送目标渠道列表，可选',
        },
      },
      required: ['name', 'cron_expr', 'prompt'],
    },
    execute: async (params): Promise<WebMCPToolResult> => {
      try {
        const { name, cron_expr, prompt, channels } = params as {
          name: string;
          cron_expr: string;
          prompt: string;
          channels?: Array<{ channel: string; to: string }>;
        };
        const task = await tasksService.createTask({
          name,
          schedule: { kind: 'cron', expr: cron_expr },
          message: prompt,
          channels: channels,
        });
        return {
          success: true,
          data: { id: task.id, name: task.name },
          message: `任务 "${name}" 创建成功`,
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : '创建任务失败',
        };
      }
    },
  },
  {
    name: 'horbot_task_delete',
    description: '删除指定的定时任务。',
    inputSchema: {
      type: 'object',
      properties: {
        task_id: {
          type: 'string',
          description: '要删除的任务 ID',
        },
      },
      required: ['task_id'],
    },
    execute: async (params): Promise<WebMCPToolResult> => {
      try {
        const { task_id } = params as { task_id: string };
        await tasksService.deleteTask(task_id);
        return {
          success: true,
          message: `任务 ${task_id} 已删除`,
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : '删除任务失败',
        };
      }
    },
  },
  {
    name: 'horbot_task_run',
    description: '立即执行指定的定时任务，无需等待定时触发。',
    inputSchema: {
      type: 'object',
      properties: {
        task_id: {
          type: 'string',
          description: '要执行的任务 ID',
        },
      },
      required: ['task_id'],
    },
    execute: async (params): Promise<WebMCPToolResult> => {
      try {
        const { task_id } = params as { task_id: string };
        await tasksService.runTask(task_id);
        return {
          success: true,
          message: `任务 ${task_id} 已开始执行`,
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : '执行任务失败',
        };
      }
    },
  },
  {
    name: 'horbot_task_toggle',
    description: '启用或禁用指定的定时任务。',
    inputSchema: {
      type: 'object',
      properties: {
        task_id: {
          type: 'string',
          description: '任务 ID',
        },
        enabled: {
          type: 'boolean',
          description: 'true 启用任务，false 禁用任务',
        },
      },
      required: ['task_id', 'enabled'],
    },
    execute: async (params): Promise<WebMCPToolResult> => {
      try {
        const { task_id, enabled } = params as { task_id: string; enabled: boolean };
        await tasksService.toggleTask(task_id, enabled);
        return {
          success: true,
          message: `任务 ${task_id} 已${enabled ? '启用' : '禁用'}`,
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : '切换任务状态失败',
        };
      }
    },
  },
];

const createStatusTools = (): WebMCPToolDefinition[] => [
  {
    name: 'horbot_status',
    description: '获取 Horbot 系统状态，包括 CPU、内存、服务状态等信息。',
    inputSchema: {
      type: 'object',
      properties: {},
      required: [],
    },
    execute: async (): Promise<WebMCPToolResult> => {
      try {
        const status = await statusService.getStatus();
        return {
          success: true,
          data: status,
          message: '系统状态获取成功',
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : '获取系统状态失败',
        };
      }
    },
  },
  {
    name: 'horbot_channels',
    description: '获取所有消息渠道的配置和状态。',
    inputSchema: {
      type: 'object',
      properties: {},
      required: [],
    },
    execute: async (): Promise<WebMCPToolResult> => {
      try {
        const channels = await channelsService.getChannels();
        return {
          success: true,
          data: channels,
          message: '渠道状态获取成功',
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : '获取渠道状态失败',
        };
      }
    },
  },
  {
    name: 'horbot_health',
    description: '检查系统健康状态。',
    inputSchema: {
      type: 'object',
      properties: {},
      required: [],
    },
    execute: async (): Promise<WebMCPToolResult> => {
      try {
        const health = await statusService.getHealth();
        return {
          success: true,
          data: health,
          message: `系统状态: ${health.status}`,
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : '健康检查失败',
        };
      }
    },
  },
];

const createConfigTools = (): WebMCPToolDefinition[] => [
  {
    name: 'horbot_config_get',
    description: '获取 Horbot 当前配置信息。',
    inputSchema: {
      type: 'object',
      properties: {},
      required: [],
    },
    execute: async (): Promise<WebMCPToolResult> => {
      try {
        const config = await configService.getConfig();
        const safeConfig = {
          workspace: config.agents?.defaults?.workspace,
          providers: Object.keys(config.providers || {}),
          gateway: config.gateway,
        };
        return {
          success: true,
          data: safeConfig,
          message: '配置获取成功',
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : '获取配置失败',
        };
      }
    },
  },
  {
    name: 'horbot_config_set_provider',
    description: '设置 AI 提供商配置。',
    inputSchema: {
      type: 'object',
      properties: {
        provider: {
          type: 'string',
          description: '提供商名称，如 openai、anthropic、deepseek 等',
        },
        api_key: {
          type: 'string',
          description: 'API 密钥',
        },
        api_base: {
          type: 'string',
          description: 'API 基础 URL，可选',
        },
      },
      required: ['provider', 'api_key'],
    },
    execute: async (params): Promise<WebMCPToolResult> => {
      try {
        const { provider, api_key, api_base } = params as {
          provider: string;
          api_key: string;
          api_base?: string;
        };
        await configService.addProvider(provider, { 
          apiKey: api_key,
          apiBase: api_base,
        });
        return {
          success: true,
          message: `提供商 ${provider} 配置成功`,
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : '设置提供商失败',
        };
      }
    },
  },
  {
    name: 'horbot_config_providers',
    description: '获取所有已配置的 AI 提供商列表。',
    inputSchema: {
      type: 'object',
      properties: {},
      required: [],
    },
    execute: async (): Promise<WebMCPToolResult> => {
      try {
        const providers = await configService.getProviders();
        const providerList = Object.entries(providers).map(([name, config]) => ({
          name,
          hasApiKey: !!(config as { apiKey?: string }).apiKey,
          apiBase: (config as { apiBase?: string }).apiBase,
        }));
        return {
          success: true,
          data: providerList,
          message: `获取到 ${providerList.length} 个提供商`,
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : '获取提供商列表失败',
        };
      }
    },
  },
];

export const getAllTools = (): WebMCPToolDefinition[] => [
  ...createChatTools(),
  ...createTaskTools(),
  ...createStatusTools(),
  ...createConfigTools(),
];

export {
  createChatTools,
  createTaskTools,
  createStatusTools,
  createConfigTools,
};
