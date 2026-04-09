import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo });
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    this.props.onReset?.();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex flex-col items-center justify-center min-h-[200px] p-8 text-center">
          <div className="w-16 h-16 mb-4 rounded-full bg-semantic-error/10 flex items-center justify-center">
            <svg
              className="w-8 h-8 text-semantic-error"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-surface-200 mb-2">
            出错了
          </h3>
          <p className="text-sm text-surface-400 mb-4 max-w-md">
            {this.state.error?.message || '发生了未知错误，请刷新页面重试'}
          </p>

          {(this.state.error?.stack || this.state.errorInfo?.componentStack) && (
            <details className="w-full max-w-2xl mb-6 text-left bg-surface-800 rounded-lg border border-surface-700 overflow-hidden">
              <summary className="px-4 py-2 bg-surface-700/50 text-sm font-medium text-surface-200 cursor-pointer hover:bg-surface-700 transition-colors">
                查看错误详情
              </summary>
              <div className="p-4 overflow-auto max-h-[300px] text-xs font-mono text-surface-300 whitespace-pre-wrap">
                {this.state.error?.stack && (
                  <div className="mb-4">
                    <div className="font-bold text-semantic-error mb-1">Error Stack:</div>
                    {this.state.error.stack}
                  </div>
                )}
                {this.state.errorInfo?.componentStack && (
                  <div>
                    <div className="font-bold text-semantic-warning mb-1">Component Stack:</div>
                    {this.state.errorInfo.componentStack}
                  </div>
                )}
              </div>
            </details>
          )}

          <button
            onClick={this.handleReset}
            className="
              px-4 py-2 rounded-lg
              bg-brand-500 text-white
              hover:bg-brand-600
              transition-colors duration-200
              text-sm font-medium
            "
          >
            重试
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
