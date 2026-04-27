export const APP_LOCALES = ['zh-CN', 'en', 'th'] as const;
export type AppLocale = (typeof APP_LOCALES)[number];
export type LocaleMessages = Record<string, string>;

export const DEFAULT_LOCALE: AppLocale = 'en';
export const FALLBACK_LOCALE: AppLocale = 'en';
export const LOCALE_STORAGE_KEY = 'horbot-ui-locale';

export const LANGUAGE_OPTIONS: Array<{ value: AppLocale; labelKey: string }> = [
  { value: 'zh-CN', labelKey: 'locale.zhCN' },
  { value: 'en', labelKey: 'locale.english' },
  { value: 'th', labelKey: 'locale.thai' },
];

export const LANGUAGE_SHORT_LABELS: Record<AppLocale, string> = {
  'zh-CN': '中文',
  en: 'EN',
  th: 'ไทย',
};

export const INTL_LOCALE_MAP: Record<AppLocale, string> = {
  'zh-CN': 'zh-CN',
  en: 'en-US',
  th: 'th-TH',
};

export const normalizeLocale = (value?: string | null): AppLocale => {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized.startsWith('zh')) {
    return 'zh-CN';
  }
  if (normalized.startsWith('th')) {
    return 'th';
  }
  if (normalized.startsWith('en')) {
    return 'en';
  }
  return DEFAULT_LOCALE;
};

const localeLoaders: Record<AppLocale, () => Promise<{ default: LocaleMessages }>> = {
  'zh-CN': () => import('./locales/zh-CN'),
  en: () => import('./locales/en'),
  th: () => import('./locales/th'),
};

const localeMessageCache = new Map<AppLocale, LocaleMessages>();
const localeMessageInflight = new Map<AppLocale, Promise<LocaleMessages>>();

export const getCachedLocaleMessages = (locale: AppLocale): LocaleMessages | null => (
  localeMessageCache.get(locale) || null
);

export const getLocaleMessages = async (locale: AppLocale): Promise<LocaleMessages> => {
  const cached = localeMessageCache.get(locale);
  if (cached) {
    return cached;
  }

  const inflight = localeMessageInflight.get(locale);
  if (inflight) {
    return inflight;
  }

  const promise = localeLoaders[locale]()
    .then((module) => {
      localeMessageCache.set(locale, module.default);
      return module.default;
    })
    .finally(() => {
      localeMessageInflight.delete(locale);
    });

  localeMessageInflight.set(locale, promise);
  return promise;
};

export const preloadLocaleMessages = async (locale: AppLocale): Promise<void> => {
  await getLocaleMessages(locale);
};
