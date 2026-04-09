import React from 'react';

interface SkeletonProps {
  variant?: 'text' | 'circle' | 'rect';
  width?: string | number;
  height?: string | number;
  className?: string;
  count?: number;
}

const Skeleton: React.FC<SkeletonProps> = ({
  variant = 'text',
  width,
  height,
  className = '',
  count = 1,
}) => {
  const getVariantStyles = () => {
    switch (variant) {
      case 'circle':
        return 'rounded-full';
      case 'rect':
        return 'rounded-lg';
      default:
        return 'rounded';
    }
  };

  const getDefaultDimensions = () => {
    switch (variant) {
      case 'circle':
        return { width: '40px', height: '40px' };
      case 'rect':
        return { width: '100%', height: '100px' };
      default:
        return { width: '100%', height: '14px' };
    }
  };

  const defaults = getDefaultDimensions();
  const style: React.CSSProperties = {
    width: width || defaults.width,
    height: height || defaults.height,
  };

  const skeletonClass = `
    bg-surface-700/50
    animate-pulse
    ${getVariantStyles()}
    ${className}
  `;

  if (count > 1) {
    return (
      <div className="space-y-2">
        {Array.from({ length: count }).map((_, index) => (
          <div
            key={index}
            className={skeletonClass}
            style={style}
          />
        ))}
      </div>
    );
  }

  return <div className={skeletonClass} style={style} />;
};

export const SkeletonText: React.FC<{ lines?: number; className?: string }> = ({
  lines = 3,
  className = '',
}) => (
  <div className={`space-y-2 ${className}`}>
    {Array.from({ length: lines }).map((_, index) => (
      <Skeleton
        key={index}
        variant="text"
        height="14px"
        width={index === lines - 1 ? '70%' : '100%'}
      />
    ))}
  </div>
);

export const SkeletonCard: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div className={`bg-surface-800/50 rounded-xl p-4 border border-surface-700/50 ${className}`}>
    <div className="flex items-center gap-3 mb-4">
      <Skeleton variant="circle" width={40} height={40} />
      <div className="flex-1">
        <Skeleton variant="text" height="14px" width="60%" className="mb-2" />
        <Skeleton variant="text" height="12px" width="40%" />
      </div>
    </div>
    <SkeletonText lines={2} />
  </div>
);

export const SkeletonDashboard: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div className={`space-y-6 ${className}`}>
    <div className="bg-surface-800/50 rounded-xl p-6 border border-surface-700/50">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Skeleton variant="circle" width={48} height={48} />
          <div>
            <Skeleton variant="text" height="20px" width="200px" className="mb-2" />
            <Skeleton variant="text" height="14px" width="150px" />
          </div>
        </div>
        <div className="flex gap-2">
          <Skeleton variant="rect" width={80} height={32} className="rounded-lg" />
          <Skeleton variant="rect" width={80} height={32} className="rounded-lg" />
        </div>
      </div>
      <div className="grid grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-surface-700/30 rounded-lg p-4">
            <Skeleton variant="text" height="12px" width="60%" className="mb-2" />
            <Skeleton variant="text" height="24px" width="80%" />
          </div>
        ))}
      </div>
    </div>

    <div>
      <div className="flex items-center justify-between mb-4">
        <Skeleton variant="text" height="24px" width="150px" />
        <Skeleton variant="rect" width={100} height={32} className="rounded-lg" />
      </div>
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    </div>

    <div className="grid grid-cols-2 gap-6">
      <div className="bg-surface-800/50 rounded-xl p-6 border border-surface-700/50">
        <Skeleton variant="text" height="20px" width="120px" className="mb-4" />
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex items-center gap-3">
              <Skeleton variant="circle" width={32} height={32} />
              <div className="flex-1">
                <Skeleton variant="text" height="14px" width="70%" className="mb-1" />
                <Skeleton variant="text" height="12px" width="50%" />
              </div>
              <Skeleton variant="rect" width={60} height={24} className="rounded-md" />
            </div>
          ))}
        </div>
      </div>

      <div className="bg-surface-800/50 rounded-xl p-6 border border-surface-700/50">
        <Skeleton variant="text" height="20px" width="100px" className="mb-4" />
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-surface-700/30 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <Skeleton variant="text" height="14px" width="60%" />
                <Skeleton variant="rect" width={40} height={20} className="rounded" />
              </div>
              <Skeleton variant="rect" height="8px" width="100%" className="rounded-full" />
            </div>
          ))}
        </div>
      </div>
    </div>
  </div>
);

export default Skeleton;
