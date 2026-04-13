import type { I18nContextValue } from '../../contexts/I18nContext';

type Translator = I18nContextValue['t'];

export const getStatusTabs = (t: Translator) => [
  { id: 'overview', label: t('status.tab.overview') },
  { id: 'resources', label: t('status.tab.resources') },
  { id: 'services', label: t('status.tab.services') },
  { id: 'api', label: t('status.tab.api') },
  { id: 'logs', label: t('status.tab.logs') },
] as const;

export type StatusTabId = ReturnType<typeof getStatusTabs>[number]['id'];
