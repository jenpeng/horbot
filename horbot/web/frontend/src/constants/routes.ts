export const ROUTES = {
  HOME: '/',
  DASHBOARD: '/',
  CHAT: '/chat',
  CONFIG: '/config',
  CHANNELS: '/channels',
  TASKS: '/tasks',
  STATUS: '/status',
  SKILLS: '/skills',
  TOKENS: '/tokens',
} as const;

export type RoutePath = (typeof ROUTES)[keyof typeof ROUTES];
