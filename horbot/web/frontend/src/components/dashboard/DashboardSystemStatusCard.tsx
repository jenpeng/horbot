import type { SystemStatus } from '../../types';
import { SystemMetricsSummary } from '../system';

interface DashboardSystemStatusCardProps {
  systemStatus: SystemStatus | null;
}

const DashboardSystemStatusCard = ({ systemStatus }: DashboardSystemStatusCardProps) => (
  <div data-testid="dashboard-system-status-card" className="xl:col-span-1 bg-white rounded-2xl shadow-sm border border-surface-200/60 overflow-hidden">
    <div className="p-3">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary-500 to-accent-indigo flex items-center justify-center shadow-sm">
          <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
          </svg>
        </div>
        <div>
          <h3 className="text-base font-semibold text-surface-900 tracking-tight">System Status</h3>
        </div>
      </div>
      <SystemMetricsSummary
        systemStatus={systemStatus}
        compact
        showDisk={false}
        showStatus
        showUptime
      />
    </div>
  </div>
);

export default DashboardSystemStatusCard;
