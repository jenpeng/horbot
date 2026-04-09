import React from 'react';

export interface PageContainerProps {
  children: React.ReactNode;
  title?: string;
  description?: string;
  loading?: boolean;
  error?: string | Error | null;
  onRetry?: () => void;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  className?: string;
}

const LoadingSpinner: React.FC = () => (
  <div className="flex flex-col items-center justify-center h-full min-h-[200px]">
    <div className="relative">
      <div className="w-12 h-12 rounded-full border-2 border-surface-700" />
      <div className="absolute inset-0 w-12 h-12 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
    </div>
    <p className="mt-4 text-sm text-surface-400">Loading...</p>
  </div>
);

interface ErrorDisplayProps {
  error: string | Error;
  onRetry?: () => void;
}

const ErrorDisplay: React.FC<ErrorDisplayProps> = ({ error, onRetry }) => {
  const message = typeof error === 'string' ? error : error.message;

  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[200px] p-6">
      <div className="w-16 h-16 rounded-full bg-semantic-error/10 flex items-center justify-center mb-4">
        <svg
          className="w-8 h-8 text-semantic-error"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
          />
        </svg>
      </div>
      <h3 className="text-lg font-semibold text-surface-100 mb-2">Something went wrong</h3>
      <p className="text-sm text-surface-400 text-center max-w-md mb-4">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 text-sm font-medium text-white bg-brand-500 hover:bg-brand-600 rounded-lg transition-colors"
        >
          Try Again
        </button>
      )}
    </div>
  );
};

interface PageHeaderProps {
  title?: string;
  description?: string;
}

const PageHeader: React.FC<PageHeaderProps> = ({ title, description }) => {
  if (!title && !description) return null;

  return (
    <div className="mb-6">
      {title && (
        <h1 className="text-2xl font-semibold text-surface-100">{title}</h1>
      )}
      {description && (
        <p className="mt-1 text-sm text-surface-400">{description}</p>
      )}
    </div>
  );
};

const paddingClasses: Record<string, string> = {
  none: '',
  sm: 'p-3',
  md: 'p-4 sm:p-6',
  lg: 'p-6 sm:p-8',
};

export const PageContainer: React.FC<PageContainerProps> = ({
  children,
  title,
  description,
  loading = false,
  error = null,
  onRetry,
  padding = 'md',
  className = '',
}) => {
  const renderContent = () => {
    if (loading) {
      return <LoadingSpinner />;
    }

    if (error) {
      return <ErrorDisplay error={error} onRetry={onRetry} />;
    }

    return children;
  };

  return (
    <div
      className={`
        h-full overflow-auto
        ${paddingClasses[padding]}
        ${className}
      `}
    >
      <PageHeader title={title} description={description} />
      {renderContent()}
    </div>
  );
};

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  action,
}) => (
  <div className="flex flex-col items-center justify-center h-full min-h-[300px] p-6">
    {icon && (
      <div className="w-16 h-16 rounded-full bg-surface-800 flex items-center justify-center mb-4">
        {icon}
      </div>
    )}
    <h3 className="text-lg font-semibold text-surface-100 mb-2">{title}</h3>
    {description && (
      <p className="text-sm text-surface-400 text-center max-w-md mb-4">{description}</p>
    )}
    {action}
  </div>
);

export default PageContainer;
