import React from 'react';

export interface StatusIndicator {
  label: string;
  status: 'online' | 'offline' | 'active' | 'warning' | 'error';
  pulse?: boolean;
}

interface FooterProps {
  version?: string;
  copyright?: string;
  statusIndicators?: StatusIndicator[];
  showStatus?: boolean;
  className?: string;
}

const DEFAULT_STATUS_INDICATORS: StatusIndicator[] = [
  { label: 'Services Online', status: 'online', pulse: true },
  { label: 'AI Active', status: 'active' },
];

const statusColors: Record<string, string> = {
  online: 'bg-semantic-success',
  offline: 'bg-semantic-error',
  active: 'bg-brand-500',
  warning: 'bg-semantic-warning',
  error: 'bg-semantic-error',
};

export const Footer: React.FC<FooterProps> = ({
  version = 'horbot v0.1.4.post2',
  copyright = '© 2026 HKUDS',
  statusIndicators = DEFAULT_STATUS_INDICATORS,
  showStatus = true,
  className = '',
}) => {
  return (
    <footer
      className={`
        bg-surface-900/50 border-t border-surface-800/50 px-4 py-2.5
        ${className}
      `}
    >
      <div className="flex flex-col sm:flex-row justify-between items-center gap-2 text-xs">
        <div className="flex items-center gap-4 text-surface-500">
          <span className="font-mono">{version}</span>
          {showStatus && (
            <div className="hidden sm:flex items-center gap-3">
              {statusIndicators.map((indicator) => (
                <span key={indicator.label} className="flex items-center gap-1.5">
                  <span
                    className={`
                      w-1.5 h-1.5 rounded-full
                      ${statusColors[indicator.status]}
                      ${indicator.pulse ? 'animate-pulse' : ''}
                    `}
                  />
                  <span>{indicator.label}</span>
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-4 text-surface-600">
          <span>{copyright}</span>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
