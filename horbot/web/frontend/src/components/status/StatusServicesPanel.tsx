import { Badge, Card, CardContent, CardHeader } from '../ui';
import { useI18n } from '../../contexts/I18nContext';
import type { SystemStatus } from '../../types';

interface StatusServicesPanelProps {
  status: SystemStatus;
  formatTime: (ms?: number) => string;
}

const StatusServicesPanel = ({
  status,
  formatTime,
}: StatusServicesPanelProps) => {
  const { t } = useI18n();
  const notAvailable = t('common.notAvailable');

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6" role="tabpanel" id="services-panel" aria-labelledby="services-tab">
      <Card padding="lg" className="group relative overflow-hidden transition-all duration-300 hover:shadow-lg hover:shadow-primary-500/10">
        <div className="absolute inset-0 bg-gradient-to-br from-primary-500/5 via-transparent to-accent-orange/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        <CardHeader title={t('status.services.cronTitle')} className="relative z-10" />
        <CardContent className="relative z-10">
          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-surface-50 rounded-lg border border-surface-200">
              <span className="text-sm text-surface-700">{t('system.status')}</span>
              <Badge variant={status.services.cron.enabled ? 'success' : 'error'} dot>
                {status.services.cron.enabled ? t('system.running') : t('system.stopped')}
              </Badge>
            </div>
            <div className="flex items-center justify-between p-3 bg-surface-50 rounded-lg border border-surface-200">
              <span className="text-sm text-surface-700">{t('status.services.jobsCount')}</span>
              <span className="text-sm font-medium text-surface-900">{status.services.cron.jobs_count}</span>
            </div>
            {status.services.cron.next_wake_at_ms && (
              <div className="flex items-center justify-between p-3 bg-surface-50 rounded-lg border border-surface-200">
                <span className="text-sm text-surface-700">{t('status.services.nextWake')}</span>
                <span className="text-sm font-medium text-surface-900">{formatTime(status.services.cron.next_wake_at_ms)}</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card padding="lg" className="group relative overflow-hidden transition-all duration-300 hover:shadow-lg hover:shadow-accent-purple/10">
        <div className="absolute inset-0 bg-gradient-to-br from-accent-purple/5 via-transparent to-accent-emerald/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        <CardHeader title={t('status.services.agentTitle')} className="relative z-10" />
        <CardContent className="relative z-10">
          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-surface-50 rounded-lg border border-surface-200">
              <span className="text-sm text-surface-700">{t('system.status')}</span>
              <Badge variant={status.services.agent.initialized ? 'success' : 'error'} dot>
                {status.services.agent.initialized ? t('status.services.initialized') : t('status.services.notReady')}
              </Badge>
            </div>
            <div className="flex items-center justify-between p-3 bg-surface-50 rounded-lg border border-surface-200">
              <span className="text-sm text-surface-700">{t('common.model')}</span>
              <span className="text-sm font-medium text-surface-900">{status.config.model || notAvailable}</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-surface-50 rounded-lg border border-surface-200">
              <span className="text-sm text-surface-700">{t('common.provider')}</span>
              <span className="text-sm font-medium text-surface-900">{status.config.provider || notAvailable}</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-surface-50 rounded-lg border border-surface-200">
              <span className="text-sm text-surface-700">{t('dashboard.systemInfo.workspace')}</span>
              <span className="text-sm font-medium text-surface-900 truncate ml-4">{status.config.workspace || notAvailable}</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default StatusServicesPanel;
