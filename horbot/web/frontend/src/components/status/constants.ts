export const STATUS_TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'resources', label: 'Resources' },
  { id: 'services', label: 'Services' },
  { id: 'api', label: 'Api' },
  { id: 'logs', label: 'Logs' },
] as const;

export type StatusTabId = typeof STATUS_TABS[number]['id'];
