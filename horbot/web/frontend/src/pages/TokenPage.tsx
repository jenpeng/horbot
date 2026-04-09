import React, { useState, useEffect, useCallback } from 'react';
import { tokensService } from '../services';
import { Card, CardHeader, CardContent } from '../components/ui';
import { Button, IconButton } from '../components/ui/Button';
import { formatNumber, formatCost } from '../utils/format';
import type { TokenUsageStats } from '../types';

type TimeRange = '7d' | '30d' | 'all';

const TokenPage: React.FC = () => {
  const [stats, setStats] = useState<TokenUsageStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dateRange, setDateRange] = useState<TimeRange>('30d');
  const [activeTab, setActiveTab] = useState<'overview' | 'details'>('overview');

  const fetchStats = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const params: Record<string, string> = {};
      const now = new Date();
      
      if (dateRange === '7d') {
        params.start_date = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString();
      } else if (dateRange === '30d') {
        params.start_date = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString();
      }
      
      const response = await tokensService.getStats(params);
      setStats(response);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : '获取 Token 统计失败';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [dateRange]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  const formatChartDate = (dateStr: string): string => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
  };

  const timeRangeOptions: { value: TimeRange; label: string }[] = [
    { value: '7d', label: '近 7 天' },
    { value: '30d', label: '近 30 天' },
    { value: 'all', label: '全部' },
  ];

  if (isLoading && !stats) {
    return (
      <div className="flex items-center justify-center h-full bg-surface-50">
        <div className="flex flex-col items-center gap-3">
          <div className="flex space-x-2">
            <div className="w-3 h-3 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
            <div className="w-3 h-3 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
            <div className="w-3 h-3 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
          </div>
          <span className="text-surface-600 text-sm">加载数据中...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-surface-50">
      <div className="flex-shrink-0 p-6 border-b border-surface-200 bg-white">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-surface-900">Token 使用统计</h2>
            <p className="text-sm text-surface-600 mt-1">监控 API Token 消耗和成本</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex bg-surface-100 border border-surface-200 rounded-lg p-1">
              {timeRangeOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => setDateRange(option.value)}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
                    dateRange === option.value
                      ? 'bg-primary-500 text-white shadow-md'
                      : 'text-surface-600 hover:text-surface-900 hover:bg-surface-200'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <IconButton
              onClick={fetchStats}
              disabled={isLoading}
              variant="default"
              size="md"
              title="刷新数据"
              aria-label="刷新数据"
            >
              <svg className={`w-5 h-5 ${isLoading ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </IconButton>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {error && (
          <div className="mb-6 bg-accent-red/10 border border-accent-red/30 text-accent-red p-4 rounded-lg flex items-center gap-3">
            <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{error}</span>
          </div>
        )}

        {stats && (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <Card hover className="group">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm text-primary-600 font-medium">总 Token</span>
                  <div className="p-2 bg-primary-100 rounded-lg group-hover:bg-primary-200 transition-colors">
                    <svg className="w-5 h-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                    </svg>
                  </div>
                </div>
                <p className="text-3xl font-bold text-surface-900 mb-1">{formatNumber(stats.total_tokens)}</p>
                <p className="text-xs text-surface-600">
                  {formatNumber(stats.total_input_tokens)} 输入 + {formatNumber(stats.total_output_tokens)} 输出
                </p>
              </Card>

              <Card hover className="group">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm text-primary-600 font-medium">API 请求</span>
                  <div className="p-2 bg-primary-100 rounded-lg group-hover:bg-primary-200 transition-colors">
                    <svg className="w-5 h-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </div>
                </div>
                <p className="text-3xl font-bold text-surface-900 mb-1">{stats.total_requests.toLocaleString()}</p>
                <p className="text-xs text-surface-600">总调用次数</p>
              </Card>

              <Card hover className="group">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm text-primary-600 font-medium">预估成本</span>
                  <div className="p-2 bg-primary-100 rounded-lg group-hover:bg-primary-200 transition-colors">
                    <svg className="w-5 h-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                </div>
                <p className="text-3xl font-bold text-surface-900 mb-1">{formatCost(stats.total_cost)}</p>
                <p className="text-xs text-surface-600">基于标准定价</p>
              </Card>

              <Card hover className="group">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm text-primary-600 font-medium">平均 Token</span>
                  <div className="p-2 bg-primary-100 rounded-lg group-hover:bg-primary-200 transition-colors">
                    <svg className="w-5 h-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                  </div>
                </div>
                <p className="text-3xl font-bold text-surface-900 mb-1">
                  {stats.total_requests > 0 ? Math.round(stats.total_tokens / stats.total_requests).toLocaleString() : 0}
                </p>
                <p className="text-xs text-surface-600">每次请求平均</p>
              </Card>
            </div>

            <div className="flex gap-2 mb-6">
              <Button
                onClick={() => setActiveTab('overview')}
                variant={activeTab === 'overview' ? 'primary' : 'secondary'}
                size="md"
              >
                概览
              </Button>
              <Button
                onClick={() => setActiveTab('details')}
                variant={activeTab === 'details' ? 'primary' : 'secondary'}
                size="md"
              >
                详细数据
              </Button>
            </div>

            {activeTab === 'overview' ? (
              <>
                {stats.by_day.length > 0 && (
                  <Card className="mb-6">
                    <CardHeader 
                      title="每日使用趋势"
                      action={
                        <svg className="w-5 h-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                        </svg>
                      }
                    />
                    <CardContent>
                      <div className="h-48 flex items-end gap-2">
                        {stats.by_day.slice(-14).map((dayData) => {
                          const maxTokens = Math.max(...stats.by_day.map(d => d.total), 1);
                          const height = (dayData.total / maxTokens) * 100;
                          return (
                            <div key={dayData.date} className="flex-1 flex flex-col items-center group min-w-[30px]">
                              <div className="w-full relative h-40 flex items-end">
                                <div
                                  className="w-full bg-gradient-to-t from-primary-500 to-primary-400 rounded-t-lg transition-all cursor-pointer hover:from-primary-400 hover:to-primary-300"
                                  style={{ height: `${Math.max(height, 4)}%` }}
                                >
                                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block bg-white border border-surface-200 rounded-lg px-3 py-2 text-xs whitespace-nowrap z-10 shadow-lg">
                                    <div className="font-semibold text-surface-900">{formatChartDate(dayData.date)}</div>
                                    <div className="text-primary-600 font-medium">{formatNumber(dayData.total)} tokens</div>
                                    <div className="text-surface-600">{formatNumber(dayData.input)} 输入</div>
                                    <div className="text-surface-600">{formatNumber(dayData.output)} 输出</div>
                                  </div>
                                </div>
                              </div>
                              <span className="text-xs text-surface-500 mt-2 truncate w-full text-center">{formatChartDate(dayData.date)}</span>
                            </div>
                          );
                        })}
                      </div>
                    </CardContent>
                  </Card>
                )}

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <Card>
                    <CardHeader title="按提供商" />
                    <CardContent>
                      {Object.keys(stats.by_provider).length === 0 ? (
                        <div className="text-center py-8 text-surface-500">
                          <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                          </svg>
                          暂无数据
                        </div>
                      ) : (
                        <div className="space-y-4">
                          {Object.entries(stats.by_provider)
                            .sort((a, b) => b[1].total - a[1].total)
                            .map(([provider, data]) => {
                              const maxTokens = Math.max(...Object.values(stats.by_provider).map(d => d.total), 1);
                              const width = (data.total / maxTokens) * 100;
                              return (
                                <div key={provider} className="group">
                                  <div className="flex justify-between text-sm mb-2">
                                    <span className="text-surface-700 font-medium capitalize">{provider}</span>
                                    <span className="text-surface-900 font-semibold">{formatNumber(data.total)}</span>
                                  </div>
                                  <div className="h-3 bg-surface-100 rounded-full overflow-hidden">
                                    <div
                                      className="h-full bg-gradient-to-r from-primary-600 to-primary-500 rounded-full transition-all group-hover:from-primary-500 group-hover:to-primary-400"
                                      style={{ width: `${width}%` }}
                                    />
                                  </div>
                                  <div className="flex justify-between text-xs text-surface-500 mt-1.5">
                                    <span>{formatNumber(data.input)} 输入</span>
                                    <span>{formatNumber(data.output)} 输出</span>
                                  </div>
                                </div>
                              );
                            })}
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader title="按模型" />
                    <CardContent>
                      {Object.keys(stats.by_model).length === 0 ? (
                        <div className="text-center py-8 text-surface-500">
                          <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                          </svg>
                          暂无数据
                        </div>
                      ) : (
                        <div className="space-y-4">
                          {Object.entries(stats.by_model)
                            .sort((a, b) => b[1].total - a[1].total)
                            .slice(0, 8)
                            .map(([model, data]) => {
                              const maxTokens = Math.max(...Object.values(stats.by_model).map(d => d.total), 1);
                              const width = (data.total / maxTokens) * 100;
                              return (
                                <div key={model} className="group">
                                  <div className="flex justify-between text-sm mb-2">
                                    <span className="text-surface-700 truncate mr-2 font-medium" title={model}>{model}</span>
                                    <span className="text-surface-900 font-semibold whitespace-nowrap">{formatNumber(data.total)}</span>
                                  </div>
                                  <div className="h-3 bg-surface-100 rounded-full overflow-hidden">
                                    <div
                                      className="h-full bg-gradient-to-r from-primary-600 to-primary-500 rounded-full transition-all group-hover:from-primary-500 group-hover:to-primary-400"
                                      style={{ width: `${width}%` }}
                                    />
                                  </div>
                                  <div className="flex justify-between text-xs text-surface-500 mt-1.5">
                                    <span>{formatNumber(data.input)} 输入</span>
                                    <span>{formatNumber(data.output)} 输出</span>
                                  </div>
                                </div>
                              );
                            })}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>
              </>
            ) : (
              <Card>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-surface-100">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-primary-600 uppercase tracking-wider">日期</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-primary-600 uppercase tracking-wider">提供商</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-primary-600 uppercase tracking-wider">模型</th>
                        <th className="px-4 py-3 text-right text-xs font-semibold text-primary-600 uppercase tracking-wider">输入 Token</th>
                        <th className="px-4 py-3 text-right text-xs font-semibold text-primary-600 uppercase tracking-wider">输出 Token</th>
                        <th className="px-4 py-3 text-right text-xs font-semibold text-primary-600 uppercase tracking-wider">总 Token</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-200">
                      {stats.by_day.slice(0, 20).map((dayData) => (
                        Object.entries(stats.by_model).map(([model, modelData]) => (
                          <tr key={`${dayData.date}-${model}`} className="hover:bg-surface-50 transition-colors cursor-pointer">
                            <td className="px-4 py-3 text-sm text-surface-600">{formatChartDate(dayData.date)}</td>
                            <td className="px-4 py-3 text-sm text-surface-600 capitalize">{Object.keys(stats.by_provider)[0] || '-'}</td>
                            <td className="px-4 py-3 text-sm text-surface-700 font-medium">{model}</td>
                            <td className="px-4 py-3 text-sm text-surface-600 text-right">{formatNumber(modelData.input)}</td>
                            <td className="px-4 py-3 text-sm text-surface-600 text-right">{formatNumber(modelData.output)}</td>
                            <td className="px-4 py-3 text-sm text-surface-900 text-right font-semibold">{formatNumber(modelData.total)}</td>
                          </tr>
                        ))
                      )).flat().slice(0, 20)}
                    </tbody>
                  </table>
                </div>
                {stats.by_day.length * Object.keys(stats.by_model).length > 20 && (
                  <div className="px-4 py-3 bg-surface-50 text-center text-sm text-surface-500 border-t border-surface-200">
                    显示前 20 条记录
                  </div>
                )}
              </Card>
            )}
          </>
        )}

        {stats && Object.keys(stats.by_provider).length === 0 && !isLoading && (
          <div className="text-center py-16">
            <svg className="w-16 h-16 mx-auto mb-4 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <h3 className="text-lg font-medium text-surface-700 mb-2">暂无使用数据</h3>
            <p className="text-surface-500">开始使用 AI 对话后，统计数据将显示在这里</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default TokenPage;
