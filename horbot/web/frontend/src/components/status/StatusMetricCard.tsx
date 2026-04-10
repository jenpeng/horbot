import type React from 'react';

interface StatusMetricCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  status?: 'success' | 'warning' | 'error' | 'info';
  icon?: React.ReactNode;
}

const StatusMetricCard = ({
  label,
  value,
  subtext,
  status = 'info',
  icon,
}: StatusMetricCardProps) => {
  const statusColors = {
    success: 'border-accent-emerald/30 bg-accent-emerald/5 hover:shadow-accent-emerald/20',
    warning: 'border-accent-orange/30 bg-accent-orange/5 hover:shadow-accent-orange/20',
    error: 'border-accent-red/30 bg-accent-red/5 hover:shadow-accent-red/20',
    info: 'border-primary-500/30 bg-primary-500/5 hover:shadow-primary-500/20',
  };

  const textColor = {
    success: 'text-accent-emerald',
    warning: 'text-accent-orange',
    error: 'text-accent-red',
    info: 'text-primary-600',
  };

  const gradientColors = {
    success: 'from-accent-emerald/5 via-transparent to-transparent',
    warning: 'from-accent-orange/5 via-transparent to-transparent',
    error: 'from-accent-red/5 via-transparent to-transparent',
    info: 'from-primary-500/5 via-transparent to-transparent',
  };

  return (
    <div className={`group rounded-xl p-5 border bg-white ${statusColors[status]} transition-all duration-300 hover:scale-[1.02] hover:shadow-lg relative overflow-hidden`}>
      <div className={`absolute inset-0 bg-gradient-to-br ${gradientColors[status]} opacity-0 group-hover:opacity-100 transition-opacity duration-300`} />
      <div className="flex items-start justify-between mb-2 relative z-10">
        <span className="text-sm font-medium text-surface-600">{label}</span>
        {icon && <span className={textColor[status]}>{icon}</span>}
      </div>
      <p className={`text-2xl font-bold ${textColor[status]} mb-1 relative z-10`}>{value}</p>
      {subtext && <p className="text-xs text-surface-500 relative z-10">{subtext}</p>}
    </div>
  );
};

export default StatusMetricCard;
