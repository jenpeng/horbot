import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { getStorageItem, setStorageItem } from '../utils/storage';
import {
  DEFAULT_LOCALE,
  FALLBACK_LOCALE,
  INTL_LOCALE_MAP,
  LANGUAGE_OPTIONS,
  LOCALE_STORAGE_KEY,
  messages,
  normalizeLocale,
  type AppLocale,
} from '../i18n/messages';

type TranslationValues = Record<string, number | string>;

interface I18nContextValue {
  intlLocale: string;
  locale: AppLocale;
  setLocale: (locale: AppLocale) => void;
  t: (key: string, values?: TranslationValues) => string;
}

const I18nContext = createContext<I18nContextValue | undefined>(undefined);

const resolveInitialLocale = (): AppLocale => {
  if (typeof window === 'undefined') {
    return DEFAULT_LOCALE;
  }

  const storedLocale = getStorageItem<string | null>(LOCALE_STORAGE_KEY, null);
  if (storedLocale) {
    return normalizeLocale(storedLocale);
  }
  return DEFAULT_LOCALE;
};

const interpolate = (template: string, values?: TranslationValues): string => {
  if (!values) {
    return template;
  }

  return template.replace(/\{(\w+)\}/g, (_, key: string) => String(values[key] ?? `{${key}}`));
};

export const I18nProvider = ({ children }: { children: ReactNode }) => {
  const [locale, setLocaleState] = useState<AppLocale>(resolveInitialLocale);

  useEffect(() => {
    setStorageItem(LOCALE_STORAGE_KEY, locale);
  }, [locale]);

  const setLocale = useCallback((nextLocale: AppLocale) => {
    setLocaleState(nextLocale);
  }, []);

  const t = useCallback((key: string, values?: TranslationValues) => {
    const activeMessages = messages[locale] as Record<string, string>;
    const fallbackMessages = messages[FALLBACK_LOCALE] as Record<string, string>;
    const localized = activeMessages[key]
      ?? fallbackMessages[key]
      ?? key;
    return interpolate(localized, values);
  }, [locale]);

  const value = useMemo<I18nContextValue>(() => ({
    intlLocale: INTL_LOCALE_MAP[locale],
    locale,
    setLocale,
    t,
  }), [locale, setLocale, t]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
};

export const useI18n = () => {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useI18n must be used within an I18nProvider');
  }
  return context;
};

export { LANGUAGE_OPTIONS, type AppLocale, type I18nContextValue };
