import { Badge, Card, CardContent, CardHeader } from '../ui';
import Skeleton from '../ui/Skeleton';
import { PanelEmptyState } from '../state';
import { useI18n } from '../../contexts/I18nContext';
import type { ApiMetricsResponse } from '../../services/status';
import StatusMetricCard from './StatusMetricCard';

interface StatusApiPanelProps {
  apiMetrics: ApiMetricsResponse | null;
}

const StatusApiPanel = ({ apiMetrics }: StatusApiPanelProps) => {
  const { intlLocale, t } = useI18n();

  return (
  <div role="tabpanel" id="api-panel" aria-labelledby="api-tab">
    <Card padding="lg">
      <CardHeader title={t('status.api.title')} />
      <CardContent>
        {apiMetrics ? (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <StatusMetricCard label={t('status.api.totalRequestsSample')} value={apiMetrics.total_count} status="info" />
              <StatusMetricCard
                label={t('status.api.avgResponseTime')}
                value={t('status.durationMs', { value: apiMetrics.avg_process_time_ms })}
                status={apiMetrics.avg_process_time_ms > 1000 ? 'warning' : 'success'}
              />
              <StatusMetricCard
                label={t('status.api.errorCount')}
                value={apiMetrics.error_count}
                status={apiMetrics.error_count > 0 ? 'error' : 'success'}
              />
            </div>

            <div className="mt-6">
              <h3 className="text-sm font-medium text-surface-900 mb-3">{t('status.api.recentRequests')}</h3>
              <div className="bg-surface-50 rounded-lg p-4 max-h-[400px] overflow-y-auto border border-surface-200">
                {apiMetrics.recent_requests.length === 0 ? (
                  <PanelEmptyState
                    title={t('status.api.noRecentRequests')}
                    description={t('status.api.noRecentRequestsBody')}
                  />
                ) : (
                  <div className="space-y-2">
                    {apiMetrics.recent_requests.map((req, idx) => (
                      <div key={idx} className="flex flex-wrap items-center justify-between py-2 px-3 bg-white rounded border border-surface-100 shadow-sm text-sm">
                        <div className="flex items-center gap-3">
                          <Badge variant={req.status_code >= 400 ? 'error' : req.status_code >= 300 ? 'warning' : 'success'}>
                            {req.status_code}
                          </Badge>
                          <span className="font-mono font-medium text-surface-700">{req.method}</span>
                          <span className="text-surface-600 truncate max-w-xs">{req.url}</span>
                        </div>
                        <div className="flex items-center gap-4 text-xs text-surface-500">
                          <span>{t('status.durationMs', { value: req.process_time_ms })}</span>
                          <span>{new Date(req.timestamp).toLocaleString(intlLocale)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex justify-center items-center h-32">
            <Skeleton className="w-full h-full" />
          </div>
        )}
      </CardContent>
    </Card>
  </div>
  );
};

export default StatusApiPanel;
