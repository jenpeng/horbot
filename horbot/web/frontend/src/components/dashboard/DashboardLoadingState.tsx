import Skeleton from '../ui/Skeleton';

const PulseBlock = ({
  className,
}: {
  className: string;
}) => <Skeleton variant="rect" className={`rounded-2xl bg-surface-200/80 ${className}`} />;

const DashboardLoadingState = () => (
  <div className="h-full overflow-y-auto bg-gradient-to-br from-surface-50 via-surface-100 to-surface-50">
    <div className="max-w-7xl mx-auto p-8 space-y-6">
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-primary-600/85 via-primary-500/80 to-accent-indigo/80 p-8 shadow-lg shadow-primary-500/10 -mx-8 px-8 mb-6">
        <div className="flex items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <PulseBlock className="h-16 w-16 rounded-2xl bg-white/25" />
            <div className="space-y-3">
              <PulseBlock className="h-8 w-40 bg-white/25" />
              <PulseBlock className="h-4 w-28 rounded-full bg-white/20" />
            </div>
          </div>
          <PulseBlock className="h-12 w-40 rounded-full bg-white/20" />
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <PulseBlock className="h-24" />
        <PulseBlock className="h-24" />
      </div>

      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <PulseBlock className="h-6 w-48" />
            <PulseBlock className="h-4 w-40 rounded-full" />
          </div>
          <PulseBlock className="h-8 w-24 rounded-full" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, index) => (
            <div key={index} className="rounded-2xl border border-surface-200/80 bg-white p-5 shadow-sm">
              <PulseBlock className="mb-4 h-12 w-12 rounded-xl" />
              <PulseBlock className="mb-2 h-5 w-32" />
              <PulseBlock className="h-4 w-full rounded-full" />
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 mt-2">
        <div className="rounded-2xl border border-surface-200/60 bg-white p-4 shadow-sm space-y-4">
          <div className="flex items-center gap-3">
            <PulseBlock className="h-10 w-10 rounded-xl" />
            <PulseBlock className="h-5 w-32" />
          </div>
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="space-y-2">
              <div className="flex items-center justify-between">
                <PulseBlock className="h-4 w-20 rounded-full" />
                <PulseBlock className="h-4 w-14 rounded-full" />
              </div>
              <PulseBlock className="h-2.5 w-full rounded-full" />
            </div>
          ))}
        </div>

        <div className="xl:col-span-2 rounded-2xl border border-surface-200/60 bg-white p-5 shadow-sm">
          <div className="mb-5 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <PulseBlock className="h-6 w-36" />
              <PulseBlock className="h-5 w-8 rounded-full" />
            </div>
            <PulseBlock className="h-5 w-20 rounded-full" />
          </div>
          <div className="space-y-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="flex items-start gap-4 border-t border-surface-100 pt-4 first:border-t-0 first:pt-0">
                <PulseBlock className="h-10 w-10 rounded-xl" />
                <div className="flex-1 space-y-2">
                  <PulseBlock className="h-4 w-3/4" />
                  <PulseBlock className="h-3 w-1/3 rounded-full" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        {Array.from({ length: 2 }).map((_, cardIndex) => (
          <div key={cardIndex} className="rounded-2xl border border-surface-200/60 bg-white p-5 shadow-sm">
            <div className="mb-5 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <PulseBlock className="h-6 w-36" />
                <PulseBlock className="h-5 w-16 rounded-full" />
              </div>
              <PulseBlock className="h-5 w-16 rounded-full" />
            </div>
            <div className="space-y-4">
              {Array.from({ length: 4 }).map((_, rowIndex) => (
                <div key={rowIndex} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <PulseBlock className="h-10 w-10 rounded-xl" />
                    <div className="space-y-2">
                      <PulseBlock className="h-4 w-28" />
                      <PulseBlock className="h-3 w-20 rounded-full" />
                    </div>
                  </div>
                  <PulseBlock className="h-7 w-12 rounded-full" />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  </div>
);

export default DashboardLoadingState;
