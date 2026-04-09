import React from 'react';

interface StatusIndicatorProps {
  message: string;
  isLoading?: boolean;
}

const StatusIndicator: React.FC<StatusIndicatorProps> = ({ message, isLoading = true }) => {
  if (!message) return null;

  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-secondary-700/50 border border-secondary-600 mb-3">
      {isLoading && (
        <svg className="animate-spin h-4 w-4 text-primary-400" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
      )}
      <span className="text-sm text-gray-300">{message}</span>
    </div>
  );
};

export default StatusIndicator;
