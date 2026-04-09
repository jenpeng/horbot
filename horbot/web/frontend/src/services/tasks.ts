import api from './api';
import type { Task, TaskSchedule, TaskPayload, DeliveryTarget } from '../types/models';

interface ApiListResponse<T> {
  [key: string]: T[];
}

export interface CreateTaskData {
  name: string;
  schedule: TaskSchedule;
  message: string;
  deliver?: boolean;
  channel?: string;
  to?: string;
  channels?: DeliveryTarget[];
  delete_after_run?: boolean;
}

export interface UpdateTaskData {
  name?: string;
  schedule?: TaskSchedule;
  payload?: TaskPayload;
  enabled?: boolean;
  delete_after_run?: boolean;
}

export interface ToggleTaskData {
  enabled: boolean;
}

const tasksService = {
  getTasks: async (): Promise<Task[]> => {
    const response = await api.get<ApiListResponse<Task>>('/api/tasks');
    return response.data.tasks || [];
  },

  getTask: async (id: string): Promise<Task> => {
    const response = await api.get<Task>(`/api/tasks/${id}`);
    return response.data;
  },

  createTask: async (data: CreateTaskData): Promise<Task> => {
    const response = await api.post<Task>('/api/tasks', data);
    return response.data;
  },

  updateTask: async (id: string, data: UpdateTaskData): Promise<Task> => {
    const response = await api.put<Task>(`/api/tasks/${id}`, data);
    return response.data;
  },

  deleteTask: async (id: string): Promise<void> => {
    await api.delete(`/api/tasks/${id}`);
  },

  toggleTask: async (id: string, enabled: boolean): Promise<Task> => {
    const response = await api.put<Task>(`/api/tasks/${id}/enable`, { enabled });
    return response.data;
  },

  runTask: async (id: string): Promise<void> => {
    await api.post(`/api/tasks/${id}/run`);
  },
};

export default tasksService;
