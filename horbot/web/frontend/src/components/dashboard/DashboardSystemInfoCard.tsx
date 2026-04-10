import { Card, CardContent, CardHeader } from '../ui';
import type { SystemStatus } from '../../types';
import { formatBytes, getProgressColor } from './utils';

interface DashboardSystemInfoCardProps {
  copiedVersion: boolean;
  onCopyVersion: () => void;
  systemStatus: SystemStatus | null;
}

const DashboardSystemInfoCard = ({
  copiedVersion,
  onCopyVersion,
  systemStatus,
}: DashboardSystemInfoCardProps) => (
  <Card data-testid="dashboard-system-info-card" className="border border-surface-200/60 shadow-sm hover:shadow-lg transition-all duration-500 ease-out overflow-hidden">
    <CardHeader
      title={(
        <div className="flex items-center gap-2">
          <span className="text-lg font-semibold text-surface-900 tracking-tight">System Information</span>
          <span className="px-2.5 py-0.5 text-xs font-medium bg-primary-100 text-primary-700 rounded-full shadow-sm">
            v{systemStatus?.version?.split('.')[0] || '0'}
          </span>
        </div>
      )}
    />
    <CardContent>
      <div className="space-y-1 p-2">
        <div className="flex items-center justify-between py-3 px-3 rounded-xl hover:bg-surface-50 transition-all duration-300 group cursor-pointer" onClick={onCopyVersion}>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-primary-100 to-primary-50 text-primary-600 flex items-center justify-center shadow-sm group-hover:shadow-md transition-shadow duration-300">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
            </div>
            <div>
              <span className="text-sm text-surface-600 block">Version</span>
              <span className="text-xs text-surface-400">Version</span>
            </div>
          </div>
          <div className="flex items-center gap-2 group-hover:gap-3 transition-all duration-300">
            <span className="text-sm font-mono font-medium text-surface-900 bg-surface-100 px-3 py-1.5 rounded-lg">{systemStatus?.version || 'N/A'}</span>
            {copiedVersion ? (
              <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 animate-bounce">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
            ) : (
              <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-surface-100 text-surface-400 hover:bg-primary-50 hover:text-primary-600 opacity-0 group-hover:opacity-100 transition-all duration-300">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center justify-between py-3 px-3 rounded-xl hover:bg-surface-50 transition-all duration-300 group">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-purple-100 to-purple-50 text-purple-600 flex items-center justify-center shadow-sm group-hover:shadow-md transition-shadow duration-300">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605" />
              </svg>
            </div>
            <div>
              <span className="text-sm text-surface-600 block">Memory Usage</span>
              <span className="text-xs text-surface-400">Memory Usage</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="text-right">
              <span className="text-sm font-mono font-medium text-surface-900 block">{systemStatus ? formatBytes(systemStatus.system.memory.used) : 'N/A'}</span>
              <span className="text-xs text-surface-400">/ {systemStatus ? formatBytes(systemStatus.system.memory.total) : 'N/A'}</span>
            </div>
            <div className="w-16 h-2 bg-surface-100 rounded-full overflow-hidden">
              <div
                className={`h-full bg-gradient-to-r ${getProgressColor(systemStatus?.system.memory.percent || 0)} rounded-full transition-all duration-700`}
                style={{ width: `${systemStatus?.system.memory.percent || 0}%` }}
              />
            </div>
          </div>
        </div>
        <div className="flex items-center justify-between py-3 px-3 rounded-xl hover:bg-surface-50 transition-all duration-300 group">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-amber-100 to-amber-50 text-amber-600 flex items-center justify-center shadow-sm group-hover:shadow-md transition-shadow duration-300">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
              </svg>
            </div>
            <div>
              <span className="text-sm text-surface-600 block">Disk Usage</span>
              <span className="text-xs text-surface-400">Disk Usage</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-mono font-medium text-surface-900">{systemStatus?.system.disk ? `${Math.round(systemStatus.system.disk.percent)}%` : 'N/A'}</span>
            <div className="w-16 h-2 bg-surface-100 rounded-full overflow-hidden">
              <div
                className={`h-full bg-gradient-to-r ${systemStatus?.system.disk && systemStatus.system.disk.percent > 80 ? 'from-amber-500 to-red-500' : 'from-amber-500 to-orange-500'} rounded-full transition-all duration-700`}
                style={{ width: `${systemStatus?.system.disk?.percent || 0}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
);

export default DashboardSystemInfoCard;
