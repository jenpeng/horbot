import axios from 'axios';

const ADMIN_TOKEN_STORAGE_KEY = 'horbotAdminToken';

export const resolveApiBase = (): string => {
  const envBase = import.meta.env.VITE_API_BASE_URL?.trim();
  if (envBase) {
    return envBase.replace(/\/$/, '');
  }

  if (typeof window === 'undefined') {
    return '';
  }

  const { protocol, hostname, port } = window.location;

  // In Vite dev, proxying SSE through port 3000 can buffer stream events.
  // Talk to the backend directly so chat streaming stays incremental.
  if (port === '3000') {
    return `${protocol}//${hostname}:8000`;
  }

  return '';
};

export const getAdminToken = (): string => {
  const envToken =
    import.meta.env.VITE_HORBOT_ADMIN_TOKEN?.trim();
  if (envToken) {
    return envToken;
  }

  if (typeof window === 'undefined') {
    return '';
  }

  return (
    window.localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY)?.trim()
    || ''
  );
};

export const getAdminAuthHeaders = (): Record<string, string> => {
  const token = getAdminToken();
  return token ? { 'X-Horbot-Admin-Token': token } : {};
};

const api = axios.create({
  baseURL: resolveApiBase(),
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    const token = getAdminToken();
    if (token) {
      if (typeof config.headers?.set === 'function') {
        config.headers.set('X-Horbot-Admin-Token', token);
      } else {
        const headers = (config.headers ?? {}) as Record<string, string>;
        headers['X-Horbot-Admin-Token'] = token;
        config.headers = headers as typeof config.headers;
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    if (status === 401) {
      return Promise.reject(new Error('远程访问需要管理员令牌。请设置 Authorization 或 X-Horbot-Admin-Token。'));
    }
    if (status === 403) {
      return Promise.reject(new Error('当前安全策略仅允许本机访问；如需远程访问，请先配置 gateway.adminToken。'));
    }
    const message =
      error.response?.data?.message ||
      error.response?.data?.detail ||
      error.message ||
      '请求失败';
    return Promise.reject(new Error(message));
  }
);

export default api;
