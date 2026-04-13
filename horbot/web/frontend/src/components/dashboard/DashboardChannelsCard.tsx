import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader } from '../ui';
import { useI18n } from '../../contexts/I18nContext';

interface DashboardChannelsCardProps {
  counts: {
    total: number;
    enabled: number;
    online: number;
    disabled: number;
    misconfigured: number;
  };
}

const DashboardChannelsCard = ({
  counts,
}: DashboardChannelsCardProps) => {
  const { t } = useI18n();

  return (
    <Card data-testid="dashboard-channel-card" className="self-start overflow-hidden border border-surface-200/60 shadow-sm transition-all duration-500 ease-out hover:shadow-lg">
    <CardHeader
      className="px-5 pt-5 pb-0"
      title={(
        <div>
          <div className="flex items-center gap-2">
            <span className="text-lg font-semibold text-surface-900 tracking-tight">{t('dashboard.channels.title')}</span>
            <span className="flex items-center gap-1.5 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-700 shadow-sm">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
              {counts.online} {t('dashboard.channels.online')}
            </span>
          </div>
        </div>
      )}
      action={(
        <Link to="/channels" className="text-sm font-medium text-primary-600 hover:text-primary-700 transition-colors flex items-center gap-1.5 group">
          {t('common.manage')}
          <svg className="w-4 h-4 transform group-hover:translate-x-1 transition-transform duration-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
          </svg>
        </Link>
      )}
    />
    <CardContent className="space-y-4 px-5 pb-5 pt-4">
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <div className="rounded-2xl border border-surface-200 bg-surface-50 px-3 py-3">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-surface-400">{t('dashboard.channels.total')}</p>
          <p className="mt-2 text-base font-semibold text-surface-900">{counts.total}</p>
        </div>
        <div className="rounded-2xl border border-primary-100 bg-primary-50 px-3 py-3">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-primary-500">{t('dashboard.channels.enabled')}</p>
          <p className="mt-2 text-base font-semibold text-primary-700">{counts.enabled}</p>
        </div>
        <div className="rounded-2xl border border-emerald-100 bg-emerald-50 px-3 py-3">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-emerald-500">{t('dashboard.channels.online')}</p>
          <p className="mt-2 text-base font-semibold text-emerald-700">{counts.online}</p>
        </div>
        <div className="rounded-2xl border border-amber-100 bg-amber-50 px-3 py-3">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-amber-500">{t('dashboard.channels.missingConfig')}</p>
          <p className="mt-2 text-base font-semibold text-amber-700">{counts.misconfigured}</p>
        </div>
      </div>
      <div className="rounded-2xl border border-dashed border-surface-200 bg-surface-50/80 px-4 py-4 text-sm text-surface-600">
        {t('dashboard.channels.note')}
      </div>
    </CardContent>
  </Card>
  );
};

export default DashboardChannelsCard;
