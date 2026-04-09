import React from 'react';
import { Card, CardContent, Badge } from './ui';

export type GatewayStatus = 'ok' | 'error' | 'disabled';

export interface GatewayChannelResult {
  name: string;
  status: GatewayStatus;
  latency_ms?: number;
  error?: string;
  details?: Record<string, unknown>;
}

export interface GatewayDiagnosticsData {
  channels: GatewayChannelResult[];
  overall_status: 'healthy' | 'degraded' | 'unhealthy';
  checked_at?: string;
}

interface GatewayDiagnosticsResultProps {
  data: GatewayDiagnosticsData;
  title?: string;
  className?: string;
}

const StatusIcon: React.FC<{ status: GatewayStatus }> = ({ status }) => {
  if (status === 'ok') {
    return (
      <div className="w-8 h-8 rounded-lg bg-accent-emerald/10 flex items-center justify-center">
        <svg className="w-5 h-5 text-accent-emerald" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      </div>
    );
  }
  if (status === 'error') {
    return (
      <div className="w-8 h-8 rounded-lg bg-accent-red/10 flex items-center justify-center">
        <svg className="w-5 h-5 text-accent-red" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </div>
    );
  }
  return (
    <div className="w-8 h-8 rounded-lg bg-surface-100 flex items-center justify-center">
      <svg className="w-5 h-5 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
      </svg>
    </div>
  );
};

const LatencyIndicator: React.FC<{ latency?: number }> = ({ latency }) => {
  if (latency === undefined) return null;

  let colorClass = 'text-accent-emerald';
  let bgClass = 'bg-accent-emerald/10';
  if (latency > 500) {
    colorClass = 'text-accent-red';
    bgClass = 'bg-accent-red/10';
  } else if (latency > 200) {
    colorClass = 'text-accent-orange';
    bgClass = 'bg-accent-orange/10';
  }

  return (
    <span className={`px-2 py-1 text-xs font-mono font-semibold rounded ${colorClass} ${bgClass}`}>
      {latency}ms
    </span>
  );
};

const ChannelCard: React.FC<{ channel: GatewayChannelResult }> = ({ channel }) => {
  const statusVariant = channel.status === 'ok' ? 'success' : channel.status === 'error' ? 'error' : 'default';

  return (
    <div className="bg-surface-50 rounded-xl p-4 border border-surface-200 hover:border-surface-300 transition-all duration-200">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <StatusIcon status={channel.status} />
          <div>
            <h4 className="text-sm font-semibold text-surface-900">{channel.name}</h4>
            <Badge variant={statusVariant} size="sm" dot>
              {channel.status === 'ok' ? '正常' : channel.status === 'error' ? '错误' : '已禁用'}
            </Badge>
          </div>
        </div>
        <LatencyIndicator latency={channel.latency_ms} />
      </div>

      {channel.error && (
        <div className="mt-3 p-3 bg-accent-red/5 border border-accent-red/20 rounded-lg">
          <div className="flex items-start gap-2">
            <svg className="w-4 h-4 text-accent-red mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-xs text-accent-red font-medium">{channel.error}</p>
          </div>
        </div>
      )}

      {channel.details && Object.keys(channel.details).length > 0 && (
        <div className="mt-3 space-y-1">
          {Object.entries(channel.details).map(([key, value]) => (
            <div key={key} className="flex items-center justify-between text-xs">
              <span className="text-surface-500">{key}</span>
              <span className="text-surface-700 font-mono">{String(value)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const GatewayDiagnosticsResult: React.FC<GatewayDiagnosticsResultProps> = ({
  data,
  title = '网关诊断结果',
  className = '',
}) => {
  const overallVariant = data.overall_status === 'healthy' ? 'success' : data.overall_status === 'degraded' ? 'warning' : 'error';
  const overallText = data.overall_status === 'healthy' ? '健康' : data.overall_status === 'degraded' ? '降级' : '不健康';

  const okCount = data.channels.filter(c => c.status === 'ok').length;
  const errorCount = data.channels.filter(c => c.status === 'error').length;
  const disabledCount = data.channels.filter(c => c.status === 'disabled').length;

  return (
    <Card padding="none" variant="default" className={`shadow-sm hover:shadow-md transition-shadow duration-300 ${className}`}>
      <div className={`px-6 py-4 border-b border-surface-200 ${
        data.overall_status === 'healthy' 
          ? 'bg-gradient-to-r from-accent-emerald/10 to-transparent'
          : data.overall_status === 'degraded'
          ? 'bg-gradient-to-r from-accent-orange/10 to-transparent'
          : 'bg-gradient-to-r from-accent-red/5 to-transparent'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
              data.overall_status === 'healthy' 
                ? 'bg-accent-emerald/20'
                : data.overall_status === 'degraded'
                ? 'bg-accent-orange/20'
                : 'bg-accent-red/10'
            }`}>
              <svg className={`w-5 h-5 ${
                data.overall_status === 'healthy' 
                  ? 'text-accent-emerald'
                  : data.overall_status === 'degraded'
                  ? 'text-accent-orange'
                  : 'text-accent-red'
              }`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
              </svg>
            </div>
            <div>
              <h3 className="text-lg font-bold text-surface-900">{title}</h3>
              <p className="text-sm text-surface-600">
                {data.channels.length} 个渠道 · {okCount} 正常 · {errorCount} 错误 · {disabledCount} 禁用
              </p>
            </div>
          </div>
          <Badge variant={overallVariant} dot pulse={data.overall_status !== 'healthy'}>
            {overallText}
          </Badge>
        </div>
      </div>

      <CardContent className="p-6">
        {data.channels.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8">
            <div className="w-16 h-16 rounded-2xl bg-surface-100 flex items-center justify-center mb-4">
              <svg className="w-8 h-8 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
              </svg>
            </div>
            <p className="text-surface-600 font-medium">暂无渠道配置</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data.channels.map((channel, index) => (
              <ChannelCard key={`channel-${index}`} channel={channel} />
            ))}
          </div>
        )}

        {data.checked_at && (
          <div className="mt-4 pt-4 border-t border-surface-200 flex items-center justify-end text-xs text-surface-500">
            <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            检查时间: {new Date(data.checked_at).toLocaleString()}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default GatewayDiagnosticsResult;
