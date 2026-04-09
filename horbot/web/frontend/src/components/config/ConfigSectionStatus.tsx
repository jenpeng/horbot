import React from 'react';

interface ConfigSectionStatusProps {
  status: 'synced' | 'dirty' | 'info';
  title: string;
  description: string;
  className?: string;
}

const toneClasses: Record<ConfigSectionStatusProps['status'], string> = {
  synced: 'border-surface-200 bg-surface-50 text-surface-600',
  dirty: 'border-accent-orange/30 bg-accent-orange/10 text-accent-orange',
  info: 'border-primary-200 bg-primary-50/70 text-primary-700',
};

const dotClasses: Record<ConfigSectionStatusProps['status'], string> = {
  synced: 'bg-surface-300',
  dirty: 'bg-accent-orange',
  info: 'bg-primary-500',
};

const ConfigSectionStatus: React.FC<ConfigSectionStatusProps> = ({
  status,
  title,
  description,
  className = '',
}) => {
  return (
    <div className={`rounded-xl border px-4 py-3 ${toneClasses[status]} ${className}`}>
      <div className="flex items-center gap-2 text-sm font-semibold">
        <span className={`h-2.5 w-2.5 rounded-full ${dotClasses[status]}`}></span>
        <span>{title}</span>
      </div>
      <p className="mt-1 text-sm leading-6">{description}</p>
    </div>
  );
};

export default ConfigSectionStatus;
