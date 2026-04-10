import { Card, CardContent, CardHeader } from '../ui';
import type { SystemStatus } from '../../types';
import { SystemMetricsSummary } from '../system';

interface DashboardSystemStatusCardProps {
  systemStatus: SystemStatus | null;
}

const DashboardSystemStatusCard = ({ systemStatus }: DashboardSystemStatusCardProps) => {
  const cronJobsCount = systemStatus?.services.cron.jobs_count ?? 0;
  const agentStatusLabel = systemStatus?.services.agent.initialized ? 'Initialized' : 'Pending';

  return (
    <Card
      data-testid="dashboard-system-status-card"
      className="xl:col-span-1 self-start overflow-hidden border border-surface-200/60 shadow-sm"
    >
      <CardHeader
        className="px-5 pt-5 pb-0"
        title={(
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary-500 to-accent-indigo shadow-sm">
              <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
              </svg>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-surface-900 tracking-tight">System Status</h3>
              <p className="text-sm text-surface-500">Core runtime and resource health</p>
            </div>
          </div>
        )}
      />
      <CardContent className="space-y-4 px-5 pb-5 pt-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-2xl border border-surface-200 bg-surface-50 px-3 py-3">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-surface-400">Agent</p>
            <p className="mt-2 text-sm font-semibold text-surface-900">{agentStatusLabel}</p>
          </div>
          <div className="rounded-2xl border border-surface-200 bg-surface-50 px-3 py-3">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-surface-400">Cron Jobs</p>
            <p className="mt-2 text-sm font-semibold text-surface-900">{cronJobsCount}</p>
          </div>
        </div>
        <SystemMetricsSummary
          systemStatus={systemStatus}
          compact
          showDisk
          showStatus
          showUptime
          showMemoryFootnote
        />
      </CardContent>
    </Card>
  );
};

export default DashboardSystemStatusCard;
