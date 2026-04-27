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
  getCachedLocaleMessages,
  getLocaleMessages,
  normalizeLocale,
  type AppLocale,
  type LocaleMessages,
} from '../i18n/messages';

type TranslationValues = Record<string, number | string>;

interface I18nContextValue {
  intlLocale: string;
  locale: AppLocale;
  setLocale: (locale: AppLocale) => void;
  t: (key: string, values?: TranslationValues) => string;
}

const I18nContext = createContext<I18nContextValue | undefined>(undefined);
const LOCALE_CATALOG_CACHE_VERSION = '2026-04-26';

interface CachedLocaleCatalog {
  version: string;
  messages: LocaleMessages;
}

const localeCatalogStorageKey = (locale: AppLocale): string => `horbot-ui-locale-catalog:${locale}`;

const readCachedLocaleCatalog = (locale: AppLocale): LocaleMessages | null => {
  if (typeof window === 'undefined') {
    return null;
  }

  const cached = getStorageItem<CachedLocaleCatalog | null>(localeCatalogStorageKey(locale), null);
  if (!cached || cached.version !== LOCALE_CATALOG_CACHE_VERSION || !cached.messages) {
    return null;
  }
  return cached.messages;
};

const writeCachedLocaleCatalog = (locale: AppLocale, messages: LocaleMessages): void => {
  if (typeof window === 'undefined') {
    return;
  }

  setStorageItem<CachedLocaleCatalog>(localeCatalogStorageKey(locale), {
    version: LOCALE_CATALOG_CACHE_VERSION,
    messages,
  });
};

const resolveInitialLocale = (): AppLocale => {
  if (typeof window === 'undefined') {
    return DEFAULT_LOCALE;
  }

  const storedLocale = getStorageItem<string | null>(LOCALE_STORAGE_KEY, null);
  if (storedLocale) {
    return normalizeLocale(storedLocale);
  }
  return normalizeLocale(window.navigator.language || DEFAULT_LOCALE);
};

const interpolate = (template: string, values?: TranslationValues): string => {
  if (!values) {
    return template;
  }

  return template.replace(/\{(\w+)\}/g, (_, key: string) => String(values[key] ?? `{${key}}`));
};

export const I18nProvider = ({ children }: { children: ReactNode }) => {
  const [locale, setLocaleState] = useState<AppLocale>(resolveInitialLocale);
  const [localeMessages, setLocaleMessages] = useState<LocaleMessages | null>(() => (
    getCachedLocaleMessages(resolveInitialLocale()) || readCachedLocaleCatalog(resolveInitialLocale())
  ));
  const [fallbackMessages, setFallbackMessages] = useState<LocaleMessages | null>(() => (
    getCachedLocaleMessages(FALLBACK_LOCALE) || readCachedLocaleCatalog(FALLBACK_LOCALE)
  ));
  const [resolvedLocale, setResolvedLocale] = useState<AppLocale | null>(() => (
    (getCachedLocaleMessages(resolveInitialLocale()) || readCachedLocaleCatalog(resolveInitialLocale()))
      ? resolveInitialLocale()
      : null
  ));

  useEffect(() => {
    setStorageItem(LOCALE_STORAGE_KEY, locale);
  }, [locale]);

  const setLocale = useCallback((nextLocale: AppLocale) => {
    setLocaleState(nextLocale);
  }, []);

  useEffect(() => {
    if (locale === FALLBACK_LOCALE && localeMessages) {
      setFallbackMessages(localeMessages);
      return undefined;
    }

    let cancelled = false;
    void getLocaleMessages(FALLBACK_LOCALE).then((catalog) => {
      if (!cancelled) {
        setFallbackMessages(catalog);
        writeCachedLocaleCatalog(FALLBACK_LOCALE, catalog);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [locale, localeMessages]);

  useEffect(() => {
    let cancelled = false;
    void getLocaleMessages(locale).then((catalog) => {
      if (!cancelled) {
        setLocaleMessages(catalog);
        setResolvedLocale(locale);
        writeCachedLocaleCatalog(locale, catalog);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [locale]);

  const t = useCallback((key: string, values?: TranslationValues) => {
    const localized = localeMessages?.[key]
      ?? fallbackMessages?.[key]
      ?? key;
    return interpolate(localized, values);
  }, [fallbackMessages, localeMessages]);

  const value = useMemo<I18nContextValue>(() => ({
    intlLocale: INTL_LOCALE_MAP[locale],
    locale,
    setLocale,
    t,
  }), [locale, setLocale, t]);

  if (resolvedLocale !== locale || !localeMessages) {
    return (
      <div className="flex h-full min-h-screen items-center justify-center bg-white text-sm text-slate-500">
        {fallbackMessages?.['app.loading'] || 'Loading...'}
      </div>
    );
  }

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
