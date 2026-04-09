import React, { useEffect, useCallback } from 'react';
import { IconButton } from './ui/Button';

interface DiagnosticModalProps {
  title: string;
  children: React.ReactNode;
  isOpen: boolean;
  onClose: () => void;
  isLoading?: boolean;
  error?: string | null;
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
}

const sizeClasses = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl',
  full: 'max-w-4xl',
};

export const DiagnosticModal: React.FC<DiagnosticModalProps> = ({
  title,
  children,
  isOpen,
  onClose,
  isLoading = false,
  error = null,
  size = 'lg',
}) => {
  const handleEscape = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isLoading) {
        onClose();
      }
    },
    [onClose, isLoading]
  );

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, handleEscape]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-surface-900/60 backdrop-blur-sm animate-fade-in"
        onClick={isLoading ? undefined : onClose}
      />
      <div
        className={`
          relative 
          bg-white
          border border-surface-200 
          rounded-2xl 
          w-full ${sizeClasses[size]} max-h-[90vh] overflow-hidden
          shadow-2xl
          animate-scale-in
        `}
      >
        <div className="relative flex items-center justify-between px-6 py-4 border-b border-surface-200">
          <h2 className="text-lg font-semibold text-surface-900">{title}</h2>
          <IconButton
            onClick={onClose}
            variant="ghost"
            size="sm"
            className="ml-auto -mr-2 text-surface-500 hover:text-surface-700"
            disabled={isLoading}
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </IconButton>
        </div>

        <div className="relative px-6 py-5 overflow-y-auto max-h-[calc(90vh-80px)]">
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="relative">
                <div className="w-12 h-12 border-4 border-primary-200 rounded-full animate-spin border-t-primary-500" />
              </div>
              <p className="mt-4 text-sm text-surface-500">正在诊断中...</p>
            </div>
          )}

          {error && (
            <div className="mb-4 p-4 bg-accent-red/10 border border-accent-red/20 rounded-xl">
              <div className="flex items-start gap-3">
                <svg className="w-5 h-5 text-accent-red flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div>
                  <h4 className="text-sm font-medium text-accent-red">诊断错误</h4>
                  <p className="mt-1 text-sm text-accent-red/80">{error}</p>
                </div>
              </div>
            </div>
          )}

          {!isLoading && !error && children}
        </div>
      </div>
    </div>
  );
};

export default DiagnosticModal;
