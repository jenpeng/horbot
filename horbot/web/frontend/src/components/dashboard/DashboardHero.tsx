import type { SystemStatus } from '../../types';
import { formatUptime } from './utils';

interface DashboardHeroProps {
  systemStatus: SystemStatus | null;
}

const DashboardHero = ({ systemStatus }: DashboardHeroProps) => (
  <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-primary-600 via-primary-500 to-accent-indigo p-8 shadow-lg shadow-primary-500/20 -mx-8 px-8 mb-6">
    <div className="absolute top-0 right-0 w-96 h-96 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2" />
    <div className="absolute bottom-0 left-0 w-64 h-64 bg-white/5 rounded-full translate-y-1/2 -translate-x-1/2" />
    <div className="absolute top-1/2 right-1/4 w-32 h-32 bg-white/5 rounded-full" />

    <div className="relative flex items-center justify-between">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center shadow-lg overflow-hidden">
            <img src="/logo.png" alt="Logo" className="w-14 h-14 object-contain" />
          </div>
          <div>
            <h1 className="text-[32px] font-bold text-white tracking-tight">Dashboard</h1>
            <p className="text-white/70 text-sm mt-1">horbot Dashboard</p>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3">
        {systemStatus?.status === 'running' ? (
          <div className="inline-flex items-center justify-center gap-2.5 px-6 py-3 bg-white/20 backdrop-blur-sm rounded-full text-white font-medium text-sm shadow-lg border border-white/20 transition-all duration-300 hover:bg-white/30 hover:shadow-xl">
            <div className="relative flex items-center justify-center">
              <div className="w-3 h-3 bg-white rounded-full animate-ping opacity-75" />
              <div className="absolute inset-0 w-3 h-3 bg-white rounded-full" />
            </div>
            <span className="tracking-wide">Running</span>
            <span className="text-xs text-white/70 ml-1">• {formatUptime(systemStatus.uptime_seconds)}</span>
          </div>
        ) : (
          <div className="inline-flex items-center justify-center gap-2.5 px-6 py-3 bg-gradient-to-r from-accent-red to-accent-orange rounded-full text-white font-medium text-sm shadow-lg shadow-accent-red/20 transition-all duration-300 hover:shadow-xl hover:shadow-accent-red/30 border border-white/20">
            <div className="flex items-center justify-center">
              <div className="w-3 h-3 bg-white rounded-full" />
            </div>
            <span className="tracking-wide">Stopped</span>
          </div>
        )}
      </div>
    </div>
  </div>
);

export default DashboardHero;
