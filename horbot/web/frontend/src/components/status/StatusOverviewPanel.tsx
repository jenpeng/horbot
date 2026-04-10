import { Card, CardContent, CardHeader } from '../ui';
import { SystemMetricsSummary } from '../system';
import type { SystemStatus } from '../../types';
import type { MemoryStatsResponse } from '../../services/status';
import StatusMetricCard from './StatusMetricCard';

interface StatusOverviewPanelProps {
  status: SystemStatus;
  memoryStats: MemoryStatsResponse | null;
  formatDurationMs: (value?: number) => string;
}

const StatusOverviewPanel = ({
  status,
  memoryStats,
  formatDurationMs,
}: StatusOverviewPanelProps) => (
  <div className="flex flex-col gap-10" role="tabpanel" id="overview-panel" aria-labelledby="overview-tab">
    <div className="rounded-xl border border-accent-orange/30 bg-accent-orange/10 px-4 py-3 text-sm text-surface-800">
      <p className="font-semibold text-surface-900">访问边界</p>
      <p className="mt-1">
        当前版本默认仅支持本机直连。若你通过局域网或公网访问页面，后端会要求管理员令牌；否则会看到 401 或 403。
      </p>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <StatusMetricCard
        label="Status"
        value={status.status}
        icon={(
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        )}
        status={status.status === 'running' ? 'success' : 'error'}
      />
      <StatusMetricCard
        label="Version"
        value={status.version || 'N/A'}
        icon={(
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
          </svg>
        )}
        status="info"
      />
      <StatusMetricCard
        label="Uptime"
        value={status.uptime || 'N/A'}
        icon={(
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        )}
        status="info"
      />
    </div>

    {memoryStats?.details?.metrics && (
      <Card padding="lg" className="group relative overflow-hidden transition-all duration-300 hover:shadow-lg hover:shadow-accent-emerald/10">
        <div className="absolute inset-0 bg-gradient-to-br from-accent-emerald/5 via-transparent to-primary-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        <CardHeader title="Memory Recall" className="relative z-10" />
        <CardContent className="relative z-10 space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatusMetricCard
              label="Recall Avg"
              value={formatDurationMs(memoryStats.details.metrics.recall.avg_latency_ms)}
              subtext={`累计 ${memoryStats.details.metrics.recall.count} 次`}
              status={memoryStats.details.metrics.recall.avg_latency_ms > 800 ? 'warning' : 'success'}
            />
            <StatusMetricCard
              label="Recall Candidates"
              value={memoryStats.details.metrics.recall.avg_candidates_count.toFixed(1)}
              subtext="平均候选数"
              status="info"
            />
            <StatusMetricCard
              label="Consolidation Avg"
              value={formatDurationMs(memoryStats.details.metrics.consolidation.avg_latency_ms)}
              subtext={`成功 ${memoryStats.details.metrics.consolidation.success_count} / 失败 ${memoryStats.details.metrics.consolidation.failure_count}`}
              status={memoryStats.details.metrics.consolidation.failure_count > 0 ? 'warning' : 'success'}
            />
            <StatusMetricCard
              label="Memory Size"
              value={`${memoryStats.total_size_kb.toFixed(1)} KB`}
              subtext={`当前 ${memoryStats.details.metrics.growth.current_entries} 个核心文件`}
              status={memoryStats.details.metrics.growth.last_delta_bytes > 0 ? 'info' : 'success'}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-surface-900">最近一次召回</p>
                <span className="text-xs text-surface-500">
                  {memoryStats.details.metrics.recall.last_samples.at(-1)?.timestamp
                    ? new Date(memoryStats.details.metrics.recall.last_samples.at(-1)!.timestamp).toLocaleString()
                    : '暂无'}
                </span>
              </div>
              <div className="mt-3 space-y-2 text-xs text-surface-600">
                <div>最近选中记忆: {memoryStats.details.metrics.recall.last_selected_memory_ids.length}</div>
                {memoryStats.details.metrics.recall.last_selected_memory_ids.slice(0, 3).map((item) => (
                  <div key={item} className="truncate rounded-full bg-white px-3 py-1 text-surface-700 ring-1 ring-slate-200">
                    {item}
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-surface-900">记忆增长</p>
                <span className="text-xs text-surface-500">最近变化</span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-2xl bg-white px-3 py-3 ring-1 ring-slate-200">
                  <div className="text-xs text-surface-500">文件增量</div>
                  <div className="mt-1 font-semibold text-surface-900">
                    {memoryStats.details.metrics.growth.last_delta_entries >= 0 ? '+' : ''}
                    {memoryStats.details.metrics.growth.last_delta_entries}
                  </div>
                </div>
                <div className="rounded-2xl bg-white px-3 py-3 ring-1 ring-slate-200">
                  <div className="text-xs text-surface-500">体积增量</div>
                  <div className="mt-1 font-semibold text-surface-900">
                    {memoryStats.details.metrics.growth.last_delta_bytes >= 0 ? '+' : ''}
                    {memoryStats.details.metrics.growth.last_delta_bytes} B
                  </div>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    )}

    <Card padding="lg" className="group relative overflow-hidden transition-all duration-300 hover:shadow-lg hover:shadow-primary-500/10">
      <div className="absolute inset-0 bg-gradient-to-br from-primary-500/5 via-transparent to-accent-purple/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
      <CardHeader title="Performance" className="relative z-10" />
      <CardContent className="relative z-10">
        <SystemMetricsSummary
          systemStatus={status}
          showDisk
          showMemoryFootnote
        />
      </CardContent>
    </Card>

    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <StatusMetricCard
        label="Cron Service"
        value={status.services.cron.enabled ? 'Running' : 'Stopped'}
        subtext={`${status.services.cron.jobs_count} jobs scheduled`}
        icon={(
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        )}
        status={status.services.cron.enabled ? 'success' : 'error'}
      />
      <StatusMetricCard
        label="AI Agent"
        value={status.services.agent.initialized ? 'Ready' : 'Not Ready'}
        subtext={`Model: ${status.config.model || 'N/A'}`}
        icon={(
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
        )}
        status={status.services.agent.initialized ? 'success' : 'error'}
      />
    </div>
  </div>
);

export default StatusOverviewPanel;
