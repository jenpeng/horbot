import React, { useState } from 'react';
import { Button } from '../components/ui';
import { PageLoadingState } from '../components/state';
import { useI18n } from '../contexts/I18nContext';
import {
  getStatusTabs,
  StatusApiPanel,
  StatusLogsPanel,
  StatusOverviewPanel,
  StatusResourcesPanel,
  StatusServicesPanel,
  type StatusTabId,
} from '../components/status';
import { useStatusPageData } from '../hooks';

const StatusPageV2: React.FC = () => {
  const { intlLocale, t } = useI18n();
  const [activeTab, setActiveTab] = useState<StatusTabId>('overview');
  const statusTabs = getStatusTabs(t);
  const {
    status,
    logs,
    apiMetrics,
    memoryStats,
    isLoading,
    error,
    logLevel,
    logLines,
    setLogLevel,
    setLogLines,
    refreshPage,
    fetchLogs,
  } = useStatusPageData(activeTab);

  const formatTime = (ms?: number) => {
    if (!ms) return t('common.notAvailable');
    return new Date(ms).toLocaleString(intlLocale);
  };

  const formatDurationMs = (value?: number) => {
    if (!value || Number.isNaN(value)) return t('status.durationMs', { value: 0 });
    if (value >= 1000) return t('status.durationSeconds', { value: (value / 1000).toFixed(2) });
    return t('status.durationMs', { value: value.toFixed(1) });
  };

  const statusLabel = status?.status === 'running'
    ? t('system.running')
    : status?.status === 'stopped'
      ? t('system.stopped')
      : (status?.status || t('common.unknown'));

  if (isLoading) {
    return <PageLoadingState metricCount={3} showTabs />;
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6 bg-surface-50 min-h-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900">{t('status.title')}</h1>
          <p className="text-sm text-surface-600 mt-1">{t('status.subtitle')}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${status?.status === 'running' ? 'bg-accent-emerald animate-pulse' : 'bg-accent-red'}`} />
          <span className="text-sm text-surface-700">{statusLabel}</span>
        </div>
      </div>

      <div className="border-b border-surface-200" role="tablist" aria-label={t('status.tabs')}>
        <nav className="flex gap-8">
          {statusTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls={`${tab.id}-panel`}
              id={`${tab.id}-tab`}
              tabIndex={activeTab === tab.id ? 0 : -1}
              className={`pb-3 px-1 text-sm font-medium transition-all duration-200 border-b-2 relative group ${
                activeTab === tab.id
                  ? 'text-primary-600 border-primary-600'
                  : 'text-surface-600 border-transparent hover:text-surface-900 hover:border-surface-400'
              }`}
            >
              {tab.label}
              {activeTab === tab.id && (
                <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-8 h-0.5 bg-primary-600 blur-sm" />
              )}
            </button>
          ))}
        </nav>
      </div>

      {error && (
        <div className="bg-accent-red/10 border border-accent-red/30 text-accent-red p-4 rounded-lg" role="alert">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {error}
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => { void refreshPage(); }}
              leftIcon={(
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              )}
            >
              {t('status.retry')}
            </Button>
          </div>
        </div>
      )}

      {activeTab === 'overview' && status && (
        <StatusOverviewPanel
          status={status}
          memoryStats={memoryStats}
          formatDurationMs={formatDurationMs}
        />
      )}

      {activeTab === 'resources' && status && (
        <StatusResourcesPanel status={status} />
      )}

      {activeTab === 'services' && status && (
        <StatusServicesPanel
          status={status}
          formatTime={formatTime}
        />
      )}

      {activeTab === 'api' && (
        <StatusApiPanel apiMetrics={apiMetrics} />
      )}

      {activeTab === 'logs' && (
        <StatusLogsPanel
          logs={logs}
          logLevel={logLevel}
          logLines={logLines}
          setLogLevel={setLogLevel}
          setLogLines={setLogLines}
          fetchLogs={fetchLogs}
        />
      )}
    </div>
  );
};

export default StatusPageV2;
