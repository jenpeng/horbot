import { Globe } from 'lucide-react';
import { LANGUAGE_OPTIONS, useI18n } from '../../contexts/I18nContext';
import { LANGUAGE_SHORT_LABELS } from '../../i18n/messages';

interface LanguageSwitcherProps {
  compact?: boolean;
  className?: string;
}

const baseSelectClassName = 'rounded-lg border border-surface-200 bg-white px-3 py-2 text-sm text-surface-700 shadow-sm outline-none transition-colors hover:border-surface-300 focus:border-primary-500';

const LanguageSwitcher = ({
  compact = false,
  className = '',
}: LanguageSwitcherProps) => {
  const { locale, setLocale, t } = useI18n();
  const currentLabel = t(LANGUAGE_OPTIONS.find((option) => option.value === locale)?.labelKey || 'locale.zhCN');

  if (compact) {
    const currentIndex = LANGUAGE_OPTIONS.findIndex((option) => option.value === locale);
    const nextLocale = LANGUAGE_OPTIONS[(currentIndex + 1) % LANGUAGE_OPTIONS.length].value;

    return (
      <button
        type="button"
        onClick={() => setLocale(nextLocale)}
        className={`inline-flex h-10 items-center justify-center gap-1.5 rounded-xl border border-surface-200 bg-white px-2.5 text-surface-700 shadow-sm transition-colors hover:border-surface-300 hover:bg-surface-50 hover:text-surface-900 ${className}`}
        aria-label={`${t('locale.label')}: ${currentLabel}`}
        title={`${t('locale.label')}: ${currentLabel}`}
      >
        <Globe className="h-4 w-4" />
        <span className="text-xs font-semibold leading-none">{LANGUAGE_SHORT_LABELS[locale]}</span>
      </button>
    );
  }

  return (
    <label className={`flex items-center gap-2 text-sm text-surface-600 ${className}`}>
      <Globe className="h-4 w-4 text-surface-500" />
      <span className="whitespace-nowrap">{t('locale.label')}</span>
      <select
        value={locale}
        onChange={(event) => setLocale(event.target.value as typeof locale)}
        className={baseSelectClassName}
        aria-label={t('locale.label')}
      >
        {LANGUAGE_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {t(option.labelKey)}
          </option>
        ))}
      </select>
    </label>
  );
};

export default LanguageSwitcher;
