import Skeleton from '../ui/Skeleton';

interface PageLoadingStateProps {
  metricCount?: number;
  showTabs?: boolean;
}

const PageLoadingState = ({
  metricCount = 3,
  showTabs = true,
}: PageLoadingStateProps) => (
  <div
    className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6 bg-surface-50 min-h-full"
    role="status"
    aria-live="polite"
    aria-label="页面加载中"
  >
    <div className="flex items-center justify-between">
      <div>
        <Skeleton className="h-8 w-48 mb-2" />
        <Skeleton className="h-4 w-32" />
      </div>
      <div className="flex items-center gap-2">
        <Skeleton className="w-2 h-2 rounded-full" />
        <Skeleton className="h-4 w-20" />
      </div>
    </div>

    {showTabs && (
      <div className="border-b border-surface-200">
        <div className="flex gap-8">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-10 w-24" />
          ))}
        </div>
      </div>
    )}

    <div className={`grid grid-cols-1 ${metricCount >= 3 ? 'md:grid-cols-3' : 'md:grid-cols-2'} gap-6`}>
      {Array.from({ length: metricCount }).map((_, i) => (
        <Skeleton key={i} className="h-32 rounded-xl" />
      ))}
    </div>

    <Skeleton className="h-64 rounded-xl" />
  </div>
);

export default PageLoadingState;
