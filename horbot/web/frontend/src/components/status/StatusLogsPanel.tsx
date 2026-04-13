import { Badge, Button, Card, CardContent, CardHeader } from '../ui';
import { PanelEmptyState } from '../state';
import { useI18n } from '../../contexts/I18nContext';
import type { LogEntry } from '../../services/status';

interface StatusLogsPanelProps {
  logs: LogEntry[];
  logLevel: string;
  logLines: number;
  setLogLevel: (value: string) => void;
  setLogLines: (value: number) => void;
  fetchLogs: () => void;
}

const StatusLogsPanel = ({
  logs,
  logLevel,
  logLines,
  setLogLevel,
  setLogLines,
  fetchLogs,
}: StatusLogsPanelProps) => {
  const { t } = useI18n();

  return (
  <div role="tabpanel" id="logs-panel" aria-labelledby="logs-tab">
    <Card padding="lg">
      <CardHeader title={t('status.logs.title')} />
      <CardContent>
        <div className="flex flex-wrap justify-between items-center mb-4 gap-3">
          <div className="flex flex-wrap gap-3">
            <div className="relative">
              <select
                value={logLevel}
                onChange={(e) => setLogLevel(e.target.value)}
                className="bg-white border border-surface-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 text-surface-900 appearance-none pr-8"
                aria-label={t('status.logs.filterByLevel')}
              >
                <option value="">{t('status.logs.allLevels')}</option>
                <option value="DEBUG">DEBUG</option>
                <option value="INFO">INFO</option>
                <option value="WARNING">WARNING</option>
                <option value="ERROR">ERROR</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>
              <div className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
                <svg className="w-4 h-4 text-surface-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </div>
            </div>
            <div className="relative">
              <select
                value={logLines}
                onChange={(e) => setLogLines(Number(e.target.value))}
                className="bg-white border border-surface-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 text-surface-900 appearance-none pr-8"
                aria-label={t('status.logs.numberOfLines')}
              >
                <option value={50}>{t('status.logs.linesOption', { count: 50 })}</option>
                <option value={100}>{t('status.logs.linesOption', { count: 100 })}</option>
                <option value={200}>{t('status.logs.linesOption', { count: 200 })}</option>
                <option value={500}>{t('status.logs.linesOption', { count: 500 })}</option>
              </select>
              <div className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
                <svg className="w-4 h-4 text-surface-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </div>
            </div>
            {logLevel && (
              <Badge variant="info" size="sm">
                {t('status.logs.filtered', { level: logLevel })}
              </Badge>
            )}
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchLogs}
            leftIcon={(
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            )}
          >
            {t('common.refresh')}
          </Button>
        </div>

        <div className="bg-surface-50 rounded-lg p-4 max-h-[600px] overflow-y-auto font-mono text-xs border border-surface-200">
          {logs.length === 0 ? (
            <PanelEmptyState
              title={t('status.logs.noLogs')}
              description={t('status.logs.noLogsBody')}
            />
          ) : (
            <div className="space-y-1">
              {logs.map((log, index) => (
                <div
                  key={index}
                  className={`py-1.5 px-2 rounded transition-colors hover:bg-surface-100 ${
                    log.level === 'ERROR' || log.level === 'CRITICAL' ? 'text-accent-red bg-accent-red/5' :
                    log.level === 'WARNING' ? 'text-accent-orange bg-accent-orange/5' :
                    log.level === 'DEBUG' ? 'text-surface-500' : 'text-surface-700'
                  }`}
                >
                  {log.raw}
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  </div>
  );
};

export default StatusLogsPanel;
