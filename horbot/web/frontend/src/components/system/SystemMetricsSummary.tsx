import { Badge } from '../ui';
import type { SystemStatus } from '../../types';
import { formatSystemBytes, formatUptime, getProgressColor } from '../../utils/systemStatus';

interface SystemMetricsSummaryProps {
  systemStatus: SystemStatus | null;
  compact?: boolean;
  showDisk?: boolean;
  showStatus?: boolean;
  showUptime?: boolean;
  showMemoryFootnote?: boolean;
}

const rowSpacing = (compact: boolean) => (compact ? 'space-y-3' : 'space-y-5');
const labelClass = (compact: boolean) => (compact ? 'text-sm text-surface-600' : 'text-sm font-medium text-surface-700');
const valueClass = (compact: boolean) => (compact ? 'text-sm font-medium text-surface-900' : 'text-sm font-semibold text-surface-900');
const progressClass = (compact: boolean) => (compact ? 'h-1.5' : 'h-2.5');

const MetricRow = ({
  compact = false,
  label,
  percent,
  value,
  detail,
}: {
  compact?: boolean;
  label: string;
  percent: number;
  value: string;
  detail?: string;
}) => (
  <div>
    <div className="flex items-center justify-between mb-1.5">
      <span className={labelClass(compact)}>{label}</span>
      <div className="flex items-center gap-2">
        <span className={valueClass(compact)}>{value}</span>
        {detail && !compact && (
          <span className="text-xs text-surface-500">{detail}</span>
        )}
      </div>
    </div>
    <div className={`${progressClass(compact)} bg-surface-100 rounded-full overflow-hidden`}>
      <div
        className={`h-full bg-gradient-to-r ${getProgressColor(percent)} rounded-full transition-all duration-700 ease-out`}
        style={{ width: `${Math.min(percent, 100)}%` }}
      />
    </div>
    {detail && compact && (
      <p className="mt-1 text-xs text-surface-500">{detail}</p>
    )}
  </div>
);

const SystemMetricsSummary = ({
  systemStatus,
  compact = false,
  showDisk = true,
  showStatus = false,
  showUptime = false,
  showMemoryFootnote = false,
}: SystemMetricsSummaryProps) => {
  if (!systemStatus) {
    return (
      <div className={rowSpacing(compact)}>
        {showStatus && (
          <div className="flex items-center justify-between">
            <span className={labelClass(compact)}>Status</span>
            <span className={valueClass(compact)}>N/A</span>
          </div>
        )}
        <MetricRow compact={compact} label="CPU Usage" percent={0} value="N/A" />
        <MetricRow compact={compact} label="Memory Usage" percent={0} value="N/A" />
        {showDisk && <MetricRow compact={compact} label="Disk Usage" percent={0} value="N/A" />}
        {showUptime && (
          <div className="flex items-center justify-between pt-2 border-t border-surface-100">
            <span className={labelClass(compact)}>Uptime</span>
            <span className={valueClass(compact)}>N/A</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={rowSpacing(compact)}>
      {showStatus && (
        <div className="flex items-center justify-between">
          <span className={labelClass(compact)}>Status</span>
          <Badge variant={systemStatus.status === 'running' ? 'success' : 'error'} size="sm" dot>
            {systemStatus.status === 'running' ? 'Running' : 'Stopped'}
          </Badge>
        </div>
      )}

      <MetricRow
        compact={compact}
        label="CPU Usage"
        percent={systemStatus.system.cpu_percent}
        value={`${systemStatus.system.cpu_percent.toFixed(1)}%`}
      />

      <MetricRow
        compact={compact}
        label="Memory Usage"
        percent={systemStatus.system.memory.percent}
        value={`${Math.round(systemStatus.system.memory.percent)}%`}
        detail={showMemoryFootnote ? `${formatSystemBytes(systemStatus.system.memory.used)} / ${formatSystemBytes(systemStatus.system.memory.total)}` : undefined}
      />

      {showDisk && (
        <MetricRow
          compact={compact}
          label="Disk Usage"
          percent={systemStatus.system.disk.percent}
          value={`${Math.round(systemStatus.system.disk.percent)}%`}
          detail={`${formatSystemBytes(systemStatus.system.disk.used)} / ${formatSystemBytes(systemStatus.system.disk.total)}`}
        />
      )}

      {showUptime && (
        <div className="flex items-center justify-between pt-2 border-t border-surface-100">
          <span className={labelClass(compact)}>Uptime</span>
          <span className={valueClass(compact)}>{formatUptime(systemStatus.uptime_seconds)}</span>
        </div>
      )}
    </div>
  );
};

export default SystemMetricsSummary;
