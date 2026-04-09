import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardContent, Badge, Button } from '../components/ui';
import Skeleton from '../components/ui/Skeleton';
import statusService from '../services/status';
import type { SystemStatus } from '../types';
import type { LogEntry, ApiMetricsResponse, MemoryStatsResponse } from '../services/status';

const MetricCard: React.FC<{
  label: string;
  value: string | number;
  subtext?: string;
  status?: 'success' | 'warning' | 'error' | 'info';
  icon?: React.ReactNode;
}> = ({ label, value, subtext, status = 'info', icon }) => {
  const statusColors = {
    success: 'border-accent-emerald/30 bg-accent-emerald/5 hover:shadow-accent-emerald/20',
    warning: 'border-accent-orange/30 bg-accent-orange/5 hover:shadow-accent-orange/20',
    error: 'border-accent-red/30 bg-accent-red/5 hover:shadow-accent-red/20',
    info: 'border-primary-500/30 bg-primary-500/5 hover:shadow-primary-500/20'
  };

  const textColor = {
    success: 'text-accent-emerald',
    warning: 'text-accent-orange',
    error: 'text-accent-red',
    info: 'text-primary-600'
  };

  const gradientColors = {
    success: 'from-accent-emerald/5 via-transparent to-transparent',
    warning: 'from-accent-orange/5 via-transparent to-transparent',
    error: 'from-accent-red/5 via-transparent to-transparent',
    info: 'from-primary-500/5 via-transparent to-transparent'
  };

  return (
    <div className={`group rounded-xl p-5 border bg-white ${statusColors[status]} transition-all duration-300 hover:scale-[1.02] hover:shadow-lg relative overflow-hidden`}>
      <div className={`absolute inset-0 bg-gradient-to-br ${gradientColors[status]} opacity-0 group-hover:opacity-100 transition-opacity duration-300`} />
      <div className="flex items-start justify-between mb-2 relative z-10">
        <span className="text-sm font-medium text-surface-600">{label}</span>
        {icon && <span className={textColor[status]}>{icon}</span>}
      </div>
      <p className={`text-2xl font-bold ${textColor[status]} mb-1 relative z-10`}>{value}</p>
      {subtext && <p className="text-xs text-surface-500 relative z-10">{subtext}</p>}
    </div>
  );
};

const ProgressBar: React.FC<{
  value: number;
  max?: number;
  label?: string;
  showPercentage?: boolean;
  icon?: React.ReactNode;
}> = ({ value, max = 100, label, showPercentage = true, icon }) => {
  const percentage = Math.min((value / max) * 100, 100);
  const getColorClass = () => {
    if (percentage > 80) return 'from-accent-red to-accent-orange';
    if (percentage > 60) return 'from-accent-orange to-accent-yellow';
    return 'from-accent-emerald to-accent-teal';
  };

  return (
    <div className="space-y-2">
      {label && (
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            {icon}
            <span className="text-sm font-medium text-surface-700">{label}</span>
          </div>
          {showPercentage && (
            <span className="text-sm font-bold text-surface-900">{percentage.toFixed(1)}%</span>
          )}
        </div>
      )}
      <div className="w-full bg-surface-200 rounded-full h-2.5 overflow-hidden">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${getColorClass()} transition-all duration-500 relative`}
          style={{ width: `${percentage}%` }}
        >
          <div className="absolute inset-0 bg-white/20 animate-pulse"></div>
        </div>
      </div>
    </div>
  );
};

const StatusPageV2: React.FC = () => {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [apiMetrics, setApiMetrics] = useState<ApiMetricsResponse | null>(null);
  const [memoryStats, setMemoryStats] = useState<MemoryStatsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'resources' | 'services' | 'api' | 'logs'>('overview');
  const [logLevel, setLogLevel] = useState<string>('');
  const [logLines, setLogLines] = useState<number>(100);

  const fetchStatus = async () => {
    try {
      const response = await statusService.getStatus();
      setStatus(response);
      setError(null);
    } catch (err) {
      setError('Failed to fetch system status');
      console.error('Error fetching status:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchLogs = async () => {
    try {
      const params: any = { lines: logLines };
      if (logLevel) params.level = logLevel;
      const response = await statusService.getLogs(params);
      setLogs(response.logs || []);
    } catch (err) {
      console.error('Error fetching logs:', err);
    }
  };

  const fetchApiMetrics = async () => {
    try {
      const response = await statusService.getApiMetrics(100);
      setApiMetrics(response);
    } catch (err) {
      console.error('Error fetching API metrics:', err);
    }
  };

  const fetchMemoryStats = async () => {
    try {
      const response = await statusService.getMemoryStats();
      setMemoryStats(response);
    } catch (err) {
      console.error('Error fetching memory stats:', err);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchLogs();
    fetchApiMetrics();
    fetchMemoryStats();
    const interval = setInterval(() => {
      fetchStatus();
      if (activeTab === 'api') fetchApiMetrics();
      if (activeTab === 'overview' || activeTab === 'resources') fetchMemoryStats();
    }, 10000);
    return () => clearInterval(interval);
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === 'logs') {
      fetchLogs();
    } else if (activeTab === 'api') {
      fetchApiMetrics();
    }
  }, [logLevel, logLines, activeTab]);

  const formatBytes = (bytes: number) => {
    const gb = bytes / (1024 * 1024 * 1024);
    return `${gb.toFixed(2)} GB`;
  };

  const formatTime = (ms?: number) => {
    if (!ms) return 'N/A';
    return new Date(ms).toLocaleString();
  };

  const formatDurationMs = (value?: number) => {
    if (!value || Number.isNaN(value)) return '0 ms';
    if (value >= 1000) return `${(value / 1000).toFixed(2)} s`;
    return `${value.toFixed(1)} ms`;
  };

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6 bg-surface-50 min-h-full">
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

        <div className="border-b border-surface-200">
          <div className="flex gap-8">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-10 w-24" />
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-32 rounded-xl" />
          ))}
        </div>

        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6 bg-surface-50 min-h-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900">System Status</h1>
          <p className="text-sm text-surface-600 mt-1">Monitor your AI assistant</p>
        </div>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${status?.status === 'running' ? 'bg-accent-emerald animate-pulse' : 'bg-accent-red'}`}></div>
          <span className="text-sm text-surface-700">{status?.status || 'Unknown'}</span>
        </div>
      </div>

      <div className="border-b border-surface-200" role="tablist" aria-label="Status tabs">
        <nav className="flex gap-8">
          {(['overview', 'resources', 'services', 'api', 'logs'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              role="tab"
              aria-selected={activeTab === tab}
              aria-controls={`${tab}-panel`}
              id={`${tab}-tab`}
              tabIndex={activeTab === tab ? 0 : -1}
              className={`pb-3 px-1 text-sm font-medium transition-all duration-200 border-b-2 relative group ${
                activeTab === tab
                  ? 'text-primary-600 border-primary-600'
                  : 'text-surface-600 border-transparent hover:text-surface-900 hover:border-surface-400'
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
              {activeTab === tab && (
                <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-8 h-0.5 bg-primary-600 blur-sm" />
              )}
            </button>
          ))}
        </nav>
      </div>

      {error && (
        <div className="bg-accent-red/10 border border-accent-red/30 text-accent-red p-4 rounded-lg" role="alert">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {error}
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={fetchStatus}
              leftIcon={
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              }
            >
              重试
            </Button>
          </div>
        </div>
      )}

      {activeTab === 'overview' && status && (
        <div className="flex flex-col gap-10" role="tabpanel" id="overview-panel" aria-labelledby="overview-tab">
          <div className="rounded-xl border border-accent-orange/30 bg-accent-orange/10 px-4 py-3 text-sm text-surface-800">
            <p className="font-semibold text-surface-900">访问边界</p>
            <p className="mt-1">
              当前版本默认仅支持本机直连。若你通过局域网或公网访问页面，后端会要求管理员令牌；否则会看到 401 或 403。
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <MetricCard
              label="Status"
              value={status.status}
              icon={
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              }
              status={status.status === 'running' ? 'success' : 'error'}
            />
            <MetricCard
              label="Version"
              value={status.version || 'N/A'}
              icon={
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                </svg>
              }
              status="info"
            />
            <MetricCard
              label="Uptime"
              value={status.uptime || 'N/A'}
              icon={
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              }
              status="info"
            />
          </div>

          {memoryStats?.details?.metrics && (
            <Card padding="lg" className="group relative overflow-hidden transition-all duration-300 hover:shadow-lg hover:shadow-accent-emerald/10">
              <div className="absolute inset-0 bg-gradient-to-br from-accent-emerald/5 via-transparent to-primary-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              <CardHeader title="Memory Recall" className="relative z-10" />
              <CardContent className="relative z-10 space-y-5">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <MetricCard
                    label="Recall Avg"
                    value={formatDurationMs(memoryStats.details.metrics.recall.avg_latency_ms)}
                    subtext={`累计 ${memoryStats.details.metrics.recall.count} 次`}
                    status={memoryStats.details.metrics.recall.avg_latency_ms > 800 ? 'warning' : 'success'}
                  />
                  <MetricCard
                    label="Recall Candidates"
                    value={memoryStats.details.metrics.recall.avg_candidates_count.toFixed(1)}
                    subtext="平均候选数"
                    status="info"
                  />
                  <MetricCard
                    label="Consolidation Avg"
                    value={formatDurationMs(memoryStats.details.metrics.consolidation.avg_latency_ms)}
                    subtext={`成功 ${memoryStats.details.metrics.consolidation.success_count} / 失败 ${memoryStats.details.metrics.consolidation.failure_count}`}
                    status={memoryStats.details.metrics.consolidation.failure_count > 0 ? 'warning' : 'success'}
                  />
                  <MetricCard
                    label="Memory Size"
                    value={`${memoryStats.total_size_kb.toFixed(1)} KB`}
                    subtext={`当前 ${memoryStats.details.metrics.growth.current_entries} 个核心文件`}
                    status={memoryStats.details.metrics.growth.last_delta_bytes > 0 ? 'info' : 'success'}
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-surface-900">最近一次召回</p>
                      <span className="text-xs text-surface-500">{memoryStats.details.metrics.recall.last_samples.at(-1)?.timestamp ? new Date(memoryStats.details.metrics.recall.last_samples.at(-1)!.timestamp).toLocaleString() : '暂无'}</span>
                    </div>
                    <div className="mt-3 space-y-2 text-xs text-surface-600">
                      <div>最近选中记忆: {memoryStats.details.metrics.recall.last_selected_memory_ids.length}</div>
                      {memoryStats.details.metrics.recall.last_selected_memory_ids.slice(0, 3).map((item) => (
                        <div key={item} className="truncate rounded-full bg-white px-3 py-1 text-surface-700 ring-1 ring-slate-200">
                          {item}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-surface-900">记忆增长</p>
                      <span className="text-xs text-surface-500">最近变化</span>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                      <div className="rounded-2xl bg-white px-3 py-3 ring-1 ring-slate-200">
                        <div className="text-xs text-surface-500">文件增量</div>
                        <div className="mt-1 font-semibold text-surface-900">{memoryStats.details.metrics.growth.last_delta_entries >= 0 ? '+' : ''}{memoryStats.details.metrics.growth.last_delta_entries}</div>
                      </div>
                      <div className="rounded-2xl bg-white px-3 py-3 ring-1 ring-slate-200">
                        <div className="text-xs text-surface-500">体积增量</div>
                        <div className="mt-1 font-semibold text-surface-900">{memoryStats.details.metrics.growth.last_delta_bytes >= 0 ? '+' : ''}{memoryStats.details.metrics.growth.last_delta_bytes} B</div>
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          <Card padding="lg" className="group relative overflow-hidden transition-all duration-300 hover:shadow-lg hover:shadow-primary-500/10">
            <div className="absolute inset-0 bg-gradient-to-br from-primary-500/5 via-transparent to-accent-purple/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            <CardHeader title="Performance" className="relative z-10" />
            <CardContent className="relative z-10">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <ProgressBar
                  value={status.system.cpu_percent}
                  label="CPU Usage"
                  icon={
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-surface-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                    </svg>
                  }
                />
                <div>
                  <ProgressBar
                    value={status.system.memory.percent}
                    label="Memory Usage"
                    icon={
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-surface-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                      </svg>
                    }
                  />
                  <p className="text-xs text-surface-600 mt-1">
                    {formatBytes(status.system.memory.used)} / {formatBytes(status.system.memory.total)}
                  </p>
                </div>
                <div>
                  <ProgressBar
                    value={status.system.disk.percent}
                    label="Disk Usage"
                    icon={
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-surface-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                      </svg>
                    }
                  />
                  <p className="text-xs text-surface-600 mt-1">
                    {formatBytes(status.system.disk.used)} / {formatBytes(status.system.disk.total)}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <MetricCard
              label="Cron Service"
              value={status.services.cron.enabled ? 'Running' : 'Stopped'}
              subtext={`${status.services.cron.jobs_count} jobs scheduled`}
              icon={
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              }
              status={status.services.cron.enabled ? 'success' : 'error'}
            />
            <MetricCard
              label="AI Agent"
              value={status.services.agent.initialized ? 'Ready' : 'Not Ready'}
              subtext={`Model: ${status.config.model || 'N/A'}`}
              icon={
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              }
              status={status.services.agent.initialized ? 'success' : 'error'}
            />
          </div>
        </div>
      )}

      {activeTab === 'resources' && status && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6" role="tabpanel" id="resources-panel" aria-labelledby="resources-tab">
          <Card padding="lg" className="group relative overflow-hidden transition-all duration-300 hover:shadow-lg hover:shadow-primary-500/10">
            <div className="absolute inset-0 bg-gradient-to-br from-primary-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            <CardHeader title="CPU Usage" className="relative z-10" />
            <CardContent className="relative z-10">
              <div className="text-center py-4">
                <div className="relative w-32 h-32 mx-auto mb-4">
                  <svg className="w-32 h-32 transform -rotate-90" aria-hidden="true">
                    <circle cx="64" cy="64" r="56" stroke="currentColor" strokeWidth="8" fill="none" className="text-surface-200"/>
                    <circle cx="64" cy="64" r="56" stroke="currentColor" strokeWidth="8" fill="none"
                      className={status.system.cpu_percent > 80 ? 'text-accent-red' : status.system.cpu_percent > 60 ? 'text-accent-orange' : 'text-accent-emerald'}
                      strokeDasharray={`${status.system.cpu_percent * 3.52} 352`}
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-3xl font-bold text-surface-900">{status.system.cpu_percent.toFixed(0)}%</span>
                  </div>
                </div>
                <p className="text-sm text-surface-600">Current CPU utilization</p>
              </div>
            </CardContent>
          </Card>

          <Card padding="lg" className="group relative overflow-hidden transition-all duration-300 hover:shadow-lg hover:shadow-accent-purple/10">
            <div className="absolute inset-0 bg-gradient-to-br from-accent-purple/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            <CardHeader title="Memory Usage" className="relative z-10" />
            <CardContent className="relative z-10">
              <div className="text-center py-4">
                <div className="relative w-32 h-32 mx-auto mb-4">
                  <svg className="w-32 h-32 transform -rotate-90" aria-hidden="true">
                    <circle cx="64" cy="64" r="56" stroke="currentColor" strokeWidth="8" fill="none" className="text-surface-200"/>
                    <circle cx="64" cy="64" r="56" stroke="currentColor" strokeWidth="8" fill="none"
                      className={status.system.memory.percent > 80 ? 'text-accent-red' : status.system.memory.percent > 60 ? 'text-accent-orange' : 'text-accent-emerald'}
                      strokeDasharray={`${status.system.memory.percent * 3.52} 352`}
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-3xl font-bold text-surface-900">{status.system.memory.percent.toFixed(0)}%</span>
                  </div>
                </div>
                <p className="text-sm text-surface-600">{formatBytes(status.system.memory.used)} / {formatBytes(status.system.memory.total)}</p>
              </div>
            </CardContent>
          </Card>

          <Card padding="lg" className="group relative overflow-hidden transition-all duration-300 hover:shadow-lg hover:shadow-accent-emerald/10">
            <div className="absolute inset-0 bg-gradient-to-br from-accent-emerald/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            <CardHeader title="Disk Usage" className="relative z-10" />
            <CardContent className="relative z-10">
              <div className="text-center py-4">
                <div className="relative w-32 h-32 mx-auto mb-4">
                  <svg className="w-32 h-32 transform -rotate-90" aria-hidden="true">
                    <circle cx="64" cy="64" r="56" stroke="currentColor" strokeWidth="8" fill="none" className="text-surface-200"/>
                    <circle cx="64" cy="64" r="56" stroke="currentColor" strokeWidth="8" fill="none"
                      className={status.system.disk.percent > 80 ? 'text-accent-red' : status.system.disk.percent > 60 ? 'text-accent-orange' : 'text-accent-emerald'}
                      strokeDasharray={`${status.system.disk.percent * 3.52} 352`}
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-3xl font-bold text-surface-900">{status.system.disk.percent.toFixed(0)}%</span>
                  </div>
                </div>
                <p className="text-sm text-surface-600">{formatBytes(status.system.disk.used)} / {formatBytes(status.system.disk.total)}</p>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'services' && status && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6" role="tabpanel" id="services-panel" aria-labelledby="services-tab">
          <Card padding="lg" className="group relative overflow-hidden transition-all duration-300 hover:shadow-lg hover:shadow-primary-500/10">
            <div className="absolute inset-0 bg-gradient-to-br from-primary-500/5 via-transparent to-accent-orange/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            <CardHeader title="Cron Service" className="relative z-10" />
            <CardContent className="relative z-10">
              <div className="space-y-4">
                <div className="flex items-center justify-between p-3 bg-surface-50 rounded-lg border border-surface-200">
                  <span className="text-sm text-surface-700">Status</span>
                  <Badge variant={status.services.cron.enabled ? 'success' : 'error'} dot>
                    {status.services.cron.enabled ? 'Running' : 'Stopped'}
                  </Badge>
                </div>
                <div className="flex items-center justify-between p-3 bg-surface-50 rounded-lg border border-surface-200">
                  <span className="text-sm text-surface-700">Jobs Count</span>
                  <span className="text-sm font-medium text-surface-900">{status.services.cron.jobs_count}</span>
                </div>
                {status.services.cron.next_wake_at_ms && (
                  <div className="flex items-center justify-between p-3 bg-surface-50 rounded-lg border border-surface-200">
                    <span className="text-sm text-surface-700">Next Wake</span>
                    <span className="text-sm font-medium text-surface-900">{formatTime(status.services.cron.next_wake_at_ms)}</span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          <Card padding="lg" className="group relative overflow-hidden transition-all duration-300 hover:shadow-lg hover:shadow-accent-purple/10">
            <div className="absolute inset-0 bg-gradient-to-br from-accent-purple/5 via-transparent to-accent-emerald/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            <CardHeader title="AI Agent" className="relative z-10" />
            <CardContent className="relative z-10">
              <div className="space-y-4">
                <div className="flex items-center justify-between p-3 bg-surface-50 rounded-lg border border-surface-200">
                  <span className="text-sm text-surface-700">Status</span>
                  <Badge variant={status.services.agent.initialized ? 'success' : 'error'} dot>
                    {status.services.agent.initialized ? 'Initialized' : 'Not Ready'}
                  </Badge>
                </div>
                <div className="flex items-center justify-between p-3 bg-surface-50 rounded-lg border border-surface-200">
                  <span className="text-sm text-surface-700">Model</span>
                  <span className="text-sm font-medium text-surface-900">{status.config.model || 'N/A'}</span>
                </div>
                <div className="flex items-center justify-between p-3 bg-surface-50 rounded-lg border border-surface-200">
                  <span className="text-sm text-surface-700">Provider</span>
                  <span className="text-sm font-medium text-surface-900">{status.config.provider || 'N/A'}</span>
                </div>
                <div className="flex items-center justify-between p-3 bg-surface-50 rounded-lg border border-surface-200">
                  <span className="text-sm text-surface-700">Workspace</span>
                  <span className="text-sm font-medium text-surface-900 truncate ml-4">{status.config.workspace}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'api' && (
        <div role="tabpanel" id="api-panel" aria-labelledby="api-tab">
          <Card padding="lg">
            <CardHeader title="API Request Metrics" />
            <CardContent>
              {apiMetrics ? (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <MetricCard
                      label="Total Requests (Sample)"
                      value={apiMetrics.total_count}
                      status="info"
                    />
                    <MetricCard
                      label="Avg Response Time"
                      value={`${apiMetrics.avg_process_time_ms} ms`}
                      status={apiMetrics.avg_process_time_ms > 1000 ? 'warning' : 'success'}
                    />
                    <MetricCard
                      label="Error Count"
                      value={apiMetrics.error_count}
                      status={apiMetrics.error_count > 0 ? 'error' : 'success'}
                    />
                  </div>

                  <div className="mt-6">
                    <h3 className="text-sm font-medium text-surface-900 mb-3">Recent Requests</h3>
                    <div className="bg-surface-50 rounded-lg p-4 max-h-[400px] overflow-y-auto border border-surface-200">
                      {apiMetrics.recent_requests.length === 0 ? (
                        <div className="text-center py-8 text-surface-500 text-sm">No recent requests</div>
                      ) : (
                        <div className="space-y-2">
                          {apiMetrics.recent_requests.map((req, idx) => (
                            <div key={idx} className="flex flex-wrap items-center justify-between py-2 px-3 bg-white rounded border border-surface-100 shadow-sm text-sm">
                              <div className="flex items-center gap-3">
                                <Badge variant={req.status_code >= 400 ? 'error' : req.status_code >= 300 ? 'warning' : 'success'}>
                                  {req.status_code}
                                </Badge>
                                <span className="font-mono font-medium text-surface-700">{req.method}</span>
                                <span className="text-surface-600 truncate max-w-xs">{req.url}</span>
                              </div>
                              <div className="flex items-center gap-4 text-xs text-surface-500">
                                <span>{req.process_time_ms} ms</span>
                                <span>{req.timestamp}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex justify-center items-center h-32">
                  <Skeleton className="w-full h-full" />
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'logs' && (
        <div role="tabpanel" id="logs-panel" aria-labelledby="logs-tab">
          <Card padding="lg">
          <CardHeader title="System Logs" />
          <CardContent>
            <div className="flex flex-wrap justify-between items-center mb-4 gap-3">
              <div className="flex flex-wrap gap-3">
                <div className="relative">
                  <select
                    value={logLevel}
                    onChange={(e) => setLogLevel(e.target.value)}
                    className="bg-white border border-surface-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 text-surface-900 appearance-none pr-8"
                    aria-label="Filter by log level"
                  >
                    <option value="">All Levels</option>
                    <option value="DEBUG">DEBUG</option>
                    <option value="INFO">INFO</option>
                    <option value="WARNING">WARNING</option>
                    <option value="ERROR">ERROR</option>
                    <option value="CRITICAL">CRITICAL</option>
                  </select>
                  <div className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
                    <svg className="w-4 h-4 text-surface-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </div>
                <div className="relative">
                  <select
                    value={logLines}
                    onChange={(e) => setLogLines(Number(e.target.value))}
                    className="bg-white border border-surface-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 text-surface-900 appearance-none pr-8"
                    aria-label="Number of log lines"
                  >
                    <option value={50}>50 lines</option>
                    <option value={100}>100 lines</option>
                    <option value={200}>200 lines</option>
                    <option value={500}>500 lines</option>
                  </select>
                  <div className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
                    <svg className="w-4 h-4 text-surface-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </div>
                {logLevel && (
                  <Badge variant="info" size="sm">
                    Filtered: {logLevel}
                  </Badge>
                )}
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={fetchLogs}
                leftIcon={
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                }
              >
                Refresh
              </Button>
            </div>

            <div className="bg-surface-50 rounded-lg p-4 max-h-[600px] overflow-y-auto font-mono text-xs border border-surface-200">
              {logs.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-40 text-surface-500">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 mb-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                  <p>No logs available</p>
                </div>
              ) : (
                <div className="space-y-1">
                  {logs.map((log, index) => (
                    <div
                      key={index}
                      className={`py-1.5 px-2 rounded transition-colors hover:bg-surface-100 ${
                        log.level === 'ERROR' || log.level === 'CRITICAL' ? 'text-accent-red bg-accent-red/5' :
                        log.level === 'WARNING' ? 'text-accent-orange bg-accent-orange/5' :
                        log.level === 'DEBUG' ? 'text-surface-500' : 'text-surface-700'
                      }`}
                    >
                      {log.raw}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default StatusPageV2;
