import React from 'react';
import { Card, CardContent, Badge } from './ui';

export interface ConfigCheckItem {
  code: string;
  message: string;
  field_path?: string;
  suggestion?: string;
}

export interface ConfigCheckResultData {
  status: 'passed' | 'failed';
  errors: ConfigCheckItem[];
  warnings: ConfigCheckItem[];
  info: ConfigCheckItem[];
}

interface ConfigCheckResultProps {
  data: ConfigCheckResultData;
  title?: string;
  className?: string;
}

const ResultItem: React.FC<{
  item: ConfigCheckItem;
  variant: 'error' | 'warning' | 'info';
}> = ({ item, variant }) => {
  const variantStyles = {
    error: {
      bg: 'bg-accent-red/5',
      border: 'border-accent-red/20',
      icon: 'text-accent-red',
      codeBg: 'bg-accent-red/10 text-accent-red',
    },
    warning: {
      bg: 'bg-accent-orange/5',
      border: 'border-accent-orange/20',
      icon: 'text-accent-orange',
      codeBg: 'bg-accent-orange/10 text-accent-orange',
    },
    info: {
      bg: 'bg-primary-50',
      border: 'border-primary-200',
      icon: 'text-primary-600',
      codeBg: 'bg-primary-100 text-primary-700',
    },
  };

  const styles = variantStyles[variant];

  return (
    <div className={`${styles.bg} border ${styles.border} rounded-xl p-4 transition-all duration-200 hover:shadow-sm`}>
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-0.5">
          {variant === 'error' && (
            <svg className={`w-5 h-5 ${styles.icon}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          )}
          {variant === 'warning' && (
            <svg className={`w-5 h-5 ${styles.icon}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.732 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          )}
          {variant === 'info' && (
            <svg className={`w-5 h-5 ${styles.icon}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className={`px-2 py-0.5 text-xs font-mono font-semibold rounded ${styles.codeBg}`}>
              {item.code}
            </span>
            {item.field_path && (
              <span className="text-xs text-surface-500 font-mono truncate">
                {item.field_path}
              </span>
            )}
          </div>
          <p className="text-sm text-surface-800 font-medium">{item.message}</p>
          {item.suggestion && (
            <p className="text-xs text-surface-600 mt-2 pl-3 border-l-2 border-surface-300">
              {item.suggestion}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

const ConfigCheckResult: React.FC<ConfigCheckResultProps> = ({
  data,
  title = '配置检查结果',
  className = '',
}) => {
  const totalIssues = data.errors.length + data.warnings.length + data.info.length;
  const isPassed = data.status === 'passed' && data.errors.length === 0;

  return (
    <Card padding="none" variant="default" className={`shadow-sm hover:shadow-md transition-shadow duration-300 ${className}`}>
      <div className={`px-6 py-4 border-b border-surface-200 ${isPassed ? 'bg-gradient-to-r from-accent-emerald/10 to-transparent' : 'bg-gradient-to-r from-accent-red/5 to-transparent'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${isPassed ? 'bg-accent-emerald/20' : 'bg-accent-red/10'}`}>
              {isPassed ? (
                <svg className="w-5 h-5 text-accent-emerald" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              ) : (
                <svg className="w-5 h-5 text-accent-red" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              )}
            </div>
            <div>
              <h3 className="text-lg font-bold text-surface-900">{title}</h3>
              <p className="text-sm text-surface-600">
                {isPassed ? '所有检查通过' : `发现 ${totalIssues} 个问题`}
              </p>
            </div>
          </div>
          <Badge variant={isPassed ? 'success' : 'error'} dot pulse={!isPassed}>
            {isPassed ? '通过' : '失败'}
          </Badge>
        </div>
      </div>

      <CardContent className="p-6">
        {totalIssues === 0 ? (
          <div className="flex flex-col items-center justify-center py-8">
            <div className="w-16 h-16 rounded-2xl bg-accent-emerald/10 flex items-center justify-center mb-4">
              <svg className="w-8 h-8 text-accent-emerald" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <p className="text-surface-600 font-medium">配置验证通过，无问题发现</p>
          </div>
        ) : (
          <div className="space-y-6">
            {data.errors.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Badge variant="error" size="sm">
                    {data.errors.length} 个错误
                  </Badge>
                  <span className="text-sm text-surface-500">需要立即修复</span>
                </div>
                <div className="space-y-2">
                  {data.errors.map((item, index) => (
                    <ResultItem key={`error-${index}`} item={item} variant="error" />
                  ))}
                </div>
              </div>
            )}

            {data.warnings.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Badge variant="warning" size="sm">
                    {data.warnings.length} 个警告
                  </Badge>
                  <span className="text-sm text-surface-500">建议修复</span>
                </div>
                <div className="space-y-2">
                  {data.warnings.map((item, index) => (
                    <ResultItem key={`warning-${index}`} item={item} variant="warning" />
                  ))}
                </div>
              </div>
            )}

            {data.info.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Badge variant="info" size="sm">
                    {data.info.length} 条信息
                  </Badge>
                  <span className="text-sm text-surface-500">供参考</span>
                </div>
                <div className="space-y-2">
                  {data.info.map((item, index) => (
                    <ResultItem key={`info-${index}`} item={item} variant="info" />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default ConfigCheckResult;
