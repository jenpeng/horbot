import React from 'react';
import { Card, CardContent, Badge } from './ui';

export interface DependencyVersion {
  name: string;
  version: string;
  required?: string;
  status?: 'ok' | 'warning' | 'error';
}

export interface ResourceUsage {
  used: number;
  total: number;
  percent: number;
}

export interface EnvironmentDetectionData {
  python_version: string;
  os_info: {
    system: string;
    release: string;
    version: string;
    machine: string;
  };
  dependencies: DependencyVersion[];
  resources: {
    disk: ResourceUsage;
    memory: ResourceUsage;
    cpu: number;
  };
  workspace: {
    path: string;
    exists: boolean;
    writable: boolean;
  };
}

interface EnvironmentDetectionResultProps {
  data: EnvironmentDetectionData;
  title?: string;
  className?: string;
}

const ProgressBar: React.FC<{
  value: number;
  label: string;
  showDetails?: boolean;
  used?: string;
  total?: string;
}> = ({ value, label, showDetails = false, used, total }) => {
  const getColorClass = () => {
    if (value > 80) return 'from-accent-red to-accent-orange';
    if (value > 60) return 'from-accent-orange to-accent-yellow';
    return 'from-accent-emerald to-accent-teal';
  };

  const getTextColorClass = () => {
    if (value > 80) return 'text-accent-red';
    if (value > 60) return 'text-accent-orange';
    return 'text-accent-emerald';
  };

  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <span className="text-sm font-medium text-surface-700">{label}</span>
        <span className={`text-sm font-bold ${getTextColorClass()}`}>{value.toFixed(1)}%</span>
      </div>
      <div className="w-full bg-surface-200 rounded-full h-2.5 overflow-hidden">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${getColorClass()} transition-all duration-500 relative`}
          style={{ width: `${Math.min(value, 100)}%` }}
        >
          <div className="absolute inset-0 bg-white/20 animate-pulse"></div>
        </div>
      </div>
      {showDetails && used && total && (
        <p className="text-xs text-surface-500">{used} / {total}</p>
      )}
    </div>
  );
};

const DependencyItem: React.FC<{ dep: DependencyVersion }> = ({ dep }) => {
  const statusVariant = dep.status === 'ok' ? 'success' : dep.status === 'warning' ? 'warning' : dep.status === 'error' ? 'error' : 'default';

  return (
    <div className="flex items-center justify-between p-3 bg-surface-50 rounded-lg border border-surface-200">
      <div className="flex items-center gap-3">
        {dep.status && (
          <div className={`w-2 h-2 rounded-full ${
            dep.status === 'ok' ? 'bg-accent-emerald' :
            dep.status === 'warning' ? 'bg-accent-orange' : 'bg-accent-red'
          }`} />
        )}
        <span className="text-sm font-medium text-surface-800">{dep.name}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-sm font-mono text-surface-600">{dep.version}</span>
        {dep.required && (
          <Badge variant={statusVariant} size="sm">
            需要 {dep.required}
          </Badge>
        )}
      </div>
    </div>
  );
};

const formatBytes = (bytes: number): string => {
  const gb = bytes / (1024 * 1024 * 1024);
  return `${gb.toFixed(2)} GB`;
};

const EnvironmentDetectionResult: React.FC<EnvironmentDetectionResultProps> = ({
  data,
  title = '环境检测结果',
  className = '',
}) => {
  const formatBytesSafe = (bytes: number | undefined): string => {
    if (bytes === undefined) return 'N/A';
    return formatBytes(bytes);
  };

  return (
    <Card padding="none" variant="default" className={`shadow-sm hover:shadow-md transition-shadow duration-300 ${className}`}>
      <div className="px-6 py-4 border-b border-surface-200 bg-gradient-to-r from-primary-50/50 to-transparent">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center">
            <svg className="w-5 h-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <div>
            <h3 className="text-lg font-bold text-surface-900">{title}</h3>
            <p className="text-sm text-surface-600">系统环境与依赖信息</p>
          </div>
        </div>
      </div>

      <CardContent className="p-6">
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-surface-50 rounded-xl p-5 border border-surface-200">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-accent-yellow/10 flex items-center justify-center">
                  <svg className="w-5 h-5 text-accent-yellow" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                  </svg>
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-surface-700">Python 版本</h4>
                  <p className="text-lg font-bold text-surface-900 font-mono">{data.python_version}</p>
                </div>
              </div>
            </div>

            <div className="bg-surface-50 rounded-xl p-5 border border-surface-200">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-accent-purple/10 flex items-center justify-center">
                  <svg className="w-5 h-5 text-accent-purple" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-surface-700">操作系统</h4>
                  <p className="text-lg font-bold text-surface-900">{data.os_info.system}</p>
                </div>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-surface-500">版本</span>
                  <span className="text-surface-700 font-mono">{data.os_info.release}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-surface-500">架构</span>
                  <span className="text-surface-700 font-mono">{data.os_info.machine}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-surface-50 rounded-xl p-5 border border-surface-200">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-lg bg-accent-cyan/10 flex items-center justify-center">
                <svg className="w-5 h-5 text-accent-cyan" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                </svg>
              </div>
              <h4 className="text-sm font-semibold text-surface-700">依赖版本</h4>
            </div>
            <div className="space-y-2">
              {data.dependencies.map((dep, index) => (
                <DependencyItem key={`dep-${index}`} dep={dep} />
              ))}
            </div>
          </div>

          <div className="bg-surface-50 rounded-xl p-5 border border-surface-200">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-lg bg-accent-emerald/10 flex items-center justify-center">
                <svg className="w-5 h-5 text-accent-emerald" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <h4 className="text-sm font-semibold text-surface-700">资源使用情况</h4>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <ProgressBar
                label="CPU 使用率"
                value={data.resources.cpu}
              />
              <ProgressBar
                label="内存使用"
                value={data.resources.memory.percent}
                showDetails
                used={formatBytesSafe(data.resources.memory.used)}
                total={formatBytesSafe(data.resources.memory.total)}
              />
              <ProgressBar
                label="磁盘使用"
                value={data.resources.disk.percent}
                showDetails
                used={formatBytesSafe(data.resources.disk.used)}
                total={formatBytesSafe(data.resources.disk.total)}
              />
            </div>
          </div>

          <div className="bg-surface-50 rounded-xl p-5 border border-surface-200">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-lg bg-accent-orange/10 flex items-center justify-center">
                <svg className="w-5 h-5 text-accent-orange" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
              </div>
              <h4 className="text-sm font-semibold text-surface-700">工作区信息</h4>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 bg-white rounded-lg border border-surface-200">
                <span className="text-sm text-surface-600">路径</span>
                <span className="text-sm font-mono text-surface-900 truncate max-w-xs" title={data.workspace.path}>
                  {data.workspace.path}
                </span>
              </div>
              <div className="flex gap-3">
                <div className="flex-1 flex items-center justify-between p-3 bg-white rounded-lg border border-surface-200">
                  <span className="text-sm text-surface-600">存在</span>
                  <Badge variant={data.workspace.exists ? 'success' : 'error'} dot size="sm">
                    {data.workspace.exists ? '是' : '否'}
                  </Badge>
                </div>
                <div className="flex-1 flex items-center justify-between p-3 bg-white rounded-lg border border-surface-200">
                  <span className="text-sm text-surface-600">可写</span>
                  <Badge variant={data.workspace.writable ? 'success' : 'error'} dot size="sm">
                    {data.workspace.writable ? '是' : '否'}
                  </Badge>
                </div>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default EnvironmentDetectionResult;
