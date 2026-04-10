import { Card, CardContent, CardHeader } from '../ui';
import type { SystemStatus } from '../../types';
import { formatBytes, getProgressColor } from './utils';

interface DashboardSystemInfoCardProps {
  copiedVersion: boolean;
  onCopyVersion: () => void;
  systemStatus: SystemStatus | null;
}

const formatWorkspaceLabel = (workspace?: string) => {
  if (!workspace) return 'N/A';
  const segments = workspace.split(/[\\/]/).filter(Boolean);
  return segments.at(-1) || workspace;
};

const DashboardSystemInfoCard = ({
  copiedVersion,
  onCopyVersion,
  systemStatus,
}: DashboardSystemInfoCardProps) => (
  <Card data-testid="dashboard-system-info-card" className="self-start overflow-hidden border border-surface-200/60 shadow-sm transition-all duration-500 ease-out hover:shadow-lg">
    <CardHeader
      className="px-5 pt-5 pb-0"
      title={(
        <div className="flex items-center gap-2">
          <span className="text-lg font-semibold text-surface-900 tracking-tight">System Information</span>
          <span className="rounded-full bg-primary-100 px-2.5 py-0.5 text-xs font-medium text-primary-700 shadow-sm">
            v{systemStatus?.version?.split('.')[0] || '0'}
          </span>
        </div>
      )}
    />
    <CardContent className="px-5 pb-5 pt-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <button
          type="button"
          onClick={onCopyVersion}
          className="group rounded-2xl border border-surface-200 bg-surface-50 px-4 py-4 text-left transition-all duration-300 hover:border-primary-200 hover:bg-white hover:shadow-sm"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-surface-400">Version</p>
              <p className="mt-2 font-mono text-sm font-semibold text-surface-900">{systemStatus?.version || 'N/A'}</p>
            </div>
            <div className={`flex h-8 w-8 items-center justify-center rounded-lg transition-all duration-300 ${
              copiedVersion ? 'bg-emerald-50 text-emerald-600' : 'bg-surface-100 text-surface-400 group-hover:bg-primary-50 group-hover:text-primary-600'
            }`}>
              {copiedVersion ? (
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              )}
            </div>
          </div>
          <p className="mt-3 text-xs text-surface-500">Click to copy the current runtime version.</p>
        </button>

        <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-4">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-surface-400">Provider</p>
          <p className="mt-2 text-sm font-semibold text-surface-900">{systemStatus?.config.provider || 'N/A'}</p>
          <p className="mt-3 text-xs text-surface-500">Current default provider used by the runtime.</p>
        </div>

        <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-4">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-surface-400">Workspace</p>
          <p className="mt-2 text-sm font-semibold text-surface-900">{formatWorkspaceLabel(systemStatus?.config.workspace)}</p>
          <p className="mt-1 truncate text-xs text-surface-500">{systemStatus?.config.workspace || 'N/A'}</p>
        </div>

        <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-surface-400">Memory</p>
              <p className="mt-2 text-sm font-semibold text-surface-900">
                {systemStatus ? formatBytes(systemStatus.system.memory.used) : 'N/A'}
              </p>
              <p className="mt-1 text-xs text-surface-500">
                / {systemStatus ? formatBytes(systemStatus.system.memory.total) : 'N/A'}
              </p>
            </div>
            <span className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-surface-700 shadow-sm">
              {Math.round(systemStatus?.system.memory.percent || 0)}%
            </span>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-100">
            <div
              className={`h-full rounded-full bg-gradient-to-r ${getProgressColor(systemStatus?.system.memory.percent || 0)} transition-all duration-700`}
              style={{ width: `${systemStatus?.system.memory.percent || 0}%` }}
            />
          </div>
        </div>

        <div className="rounded-2xl border border-surface-200 bg-surface-50 px-4 py-4 sm:col-span-2">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-surface-400">Disk</p>
              <p className="mt-2 text-sm font-semibold text-surface-900">
                {systemStatus?.system.disk ? `${Math.round(systemStatus.system.disk.percent)}% used` : 'N/A'}
              </p>
              <p className="mt-1 text-xs text-surface-500">
                {systemStatus?.system.disk
                  ? `${formatBytes(systemStatus.system.disk.used)} / ${formatBytes(systemStatus.system.disk.total)}`
                  : 'Disk metrics unavailable'}
              </p>
            </div>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-100">
            <div
              className={`h-full rounded-full bg-gradient-to-r ${
                systemStatus?.system.disk && systemStatus.system.disk.percent > 80
                  ? 'from-amber-500 to-red-500'
                  : 'from-amber-500 to-orange-500'
              } transition-all duration-700`}
              style={{ width: `${systemStatus?.system.disk?.percent || 0}%` }}
            />
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
);

export default DashboardSystemInfoCard;
