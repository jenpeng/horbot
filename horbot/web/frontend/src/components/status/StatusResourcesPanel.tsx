import { Card, CardContent, CardHeader } from '../ui';
import { formatSystemBytes } from '../../utils/systemStatus';
import type { SystemStatus } from '../../types';

interface StatusResourcesPanelProps {
  status: SystemStatus;
}

const ringColor = (percent: number): string => (
  percent > 80 ? 'text-accent-red' : percent > 60 ? 'text-accent-orange' : 'text-accent-emerald'
);

const ResourceGauge = ({
  title,
  percent,
  subtitle,
  glowClass,
}: {
  title: string;
  percent: number;
  subtitle: string;
  glowClass: string;
}) => (
  <Card padding="lg" className={`group relative overflow-hidden transition-all duration-300 hover:shadow-lg ${glowClass}`}>
    <div className="absolute inset-0 bg-gradient-to-br from-primary-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
    <CardHeader title={title} className="relative z-10" />
    <CardContent className="relative z-10">
      <div className="text-center py-4">
        <div className="relative w-32 h-32 mx-auto mb-4">
          <svg className="w-32 h-32 transform -rotate-90" aria-hidden="true">
            <circle cx="64" cy="64" r="56" stroke="currentColor" strokeWidth="8" fill="none" className="text-surface-200" />
            <circle
              cx="64"
              cy="64"
              r="56"
              stroke="currentColor"
              strokeWidth="8"
              fill="none"
              className={ringColor(percent)}
              strokeDasharray={`${percent * 3.52} 352`}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-3xl font-bold text-surface-900">{percent.toFixed(0)}%</span>
          </div>
        </div>
        <p className="text-sm text-surface-600">{subtitle}</p>
      </div>
    </CardContent>
  </Card>
);

const StatusResourcesPanel = ({ status }: StatusResourcesPanelProps) => (
  <div className="grid grid-cols-1 md:grid-cols-3 gap-6" role="tabpanel" id="resources-panel" aria-labelledby="resources-tab">
    <ResourceGauge
      title="CPU Usage"
      percent={status.system.cpu_percent}
      subtitle="Current CPU utilization"
      glowClass="hover:shadow-primary-500/10"
    />
    <ResourceGauge
      title="Memory Usage"
      percent={status.system.memory.percent}
      subtitle={`${formatSystemBytes(status.system.memory.used)} / ${formatSystemBytes(status.system.memory.total)}`}
      glowClass="hover:shadow-accent-purple/10"
    />
    <ResourceGauge
      title="Disk Usage"
      percent={status.system.disk.percent}
      subtitle={`${formatSystemBytes(status.system.disk.used)} / ${formatSystemBytes(status.system.disk.total)}`}
      glowClass="hover:shadow-accent-emerald/10"
    />
  </div>
);

export default StatusResourcesPanel;
