import React from 'react';

interface EmptyProps {
  icon?: React.ReactNode;
  title?: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
}

const Empty: React.FC<EmptyProps> = ({
  icon,
  title = 'No Data',
  description,
  action,
  className = '',
}) => {
  const defaultIcon = (
    <svg
      className="w-16 h-16 text-surface-600"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
      />
    </svg>
  );

  return (
    <div
      className={`
        flex flex-col items-center justify-center py-12 px-4
        text-center ${className}
      `}
    >
      <div className="mb-4 opacity-50">
        {icon || defaultIcon}
      </div>
      <h3 className="text-lg font-medium text-surface-700 mb-2">{title}</h3>
      {description && (
        <p className="text-sm text-surface-600 mb-4 max-w-sm">{description}</p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          className="
            px-4 py-2 rounded-lg
            bg-primary-500/10 text-primary-600
            hover:bg-primary-500/20
            transition-colors duration-200
            text-sm font-medium
          "
        >
          {action.label}
        </button>
      )}
    </div>
  );
};

export default Empty;
