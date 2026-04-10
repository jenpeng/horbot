interface PageErrorStateProps {
  error: string;
  onRetry: () => void;
  title?: string;
}

const PageErrorState = ({
  error,
  onRetry,
  title = '加载失败',
}: PageErrorStateProps) => (
  <div className="h-full overflow-y-auto bg-surface-100">
    <div className="max-w-7xl mx-auto p-8">
      <div className="flex flex-col items-center justify-center min-h-[400px]">
        <div className="w-20 h-20 rounded-2xl bg-accent-red/10 flex items-center justify-center mb-6">
          <svg className="w-10 h-10 text-accent-red" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
        </div>
        <h2 className="text-2xl font-semibold text-surface-900 mb-3">{title}</h2>
        <p className="text-surface-600 mb-6">{error}</p>
        <button onClick={onRetry} className="btn btn-primary">
          重试
        </button>
      </div>
    </div>
  </div>
);

export default PageErrorState;
