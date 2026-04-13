import React, { useState, useEffect, useCallback } from 'react';
import { tokensService } from '../services';
import { Card, CardHeader, CardContent } from '../components/ui';
import { Button, IconButton } from '../components/ui/Button';
import { useI18n } from '../contexts/I18nContext';
import { formatNumber } from '../utils/format';
import type { TokenUsageStats } from '../types';

type TimeRange = '7d' | '30d' | 'all';

const TokenPage: React.FC = () => {
  const { intlLocale, t } = useI18n();
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
      const errorMessage = err instanceof Error ? err.message : t('tokens.errorLoadFailed');
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [dateRange, t]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  const formatChartDate = (dateStr: string): string => {
    const date = new Date(dateStr);
    return date.toLocaleDateString(intlLocale, { month: 'short', day: 'numeric' });
  };

  const timeRangeOptions: { value: TimeRange; label: string }[] = [
    { value: '7d', label: t('tokens.range7d') },
    { value: '30d', label: t('tokens.range30d') },
    { value: 'all', label: t('tokens.rangeAll') },
  ];
  const averageTokensPerRequest = stats && stats.total_requests > 0
    ? Math.round(stats.total_tokens / stats.total_requests)
    : 0;
  const activeDays = stats?.by_day.filter((day) => day.total > 0).length ?? 0;
  const outputShare = stats && stats.total_tokens > 0
    ? Math.round((stats.total_output_tokens / stats.total_tokens) * 100)
    : 0;

  if (isLoading && !stats) {
    return (
      <div className="flex items-center justify-center h-full bg-surface-50">
        <div className="flex flex-col items-center gap-3">
          <div className="flex space-x-2">
            <div className="w-3 h-3 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
            <div className="w-3 h-3 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
            <div className="w-3 h-3 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
          </div>
          <span className="text-surface-600 text-sm">{t('tokens.loading')}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-surface-50">
      <div className="flex-shrink-0 p-6 border-b border-surface-200 bg-white">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-surface-900">{t('tokens.title')}</h2>
            <p className="text-sm text-surface-600 mt-1">{t('tokens.subtitle')}</p>
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
              title={t('tokens.refresh')}
              aria-label={t('tokens.refresh')}
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
            <div className="grid grid-cols-1 xl:grid-cols-4 gap-4 mb-6">
              <Card hover className="group xl:col-span-2">
                <div className="flex items-start justify-between gap-4 mb-5">
                  <div>
                    <span className="text-sm text-primary-600 font-medium">{t('tokens.totalTokens')}</span>
                    <p className="text-4xl font-bold text-surface-900 mt-2">{formatNumber(stats.total_tokens)}</p>
                    <p className="text-sm text-surface-600 mt-2">{t('tokens.totalTokensHint')}</p>
                  </div>
                  <div className="p-3 bg-primary-100 rounded-2xl group-hover:bg-primary-200 transition-colors">
                    <svg className="w-6 h-6 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                    </svg>
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="rounded-2xl bg-surface-50 border border-surface-200 px-4 py-3">
                    <div className="text-xs font-medium text-surface-500">{t('tokens.inputTokens')}</div>
                    <div className="mt-1 text-2xl font-semibold text-surface-900">{formatNumber(stats.total_input_tokens)}</div>
                  </div>
                  <div className="rounded-2xl bg-surface-50 border border-surface-200 px-4 py-3">
                    <div className="text-xs font-medium text-surface-500">{t('tokens.outputTokens')}</div>
                    <div className="mt-1 text-2xl font-semibold text-surface-900">{formatNumber(stats.total_output_tokens)}</div>
                  </div>
                </div>
              </Card>

              <Card hover className="group">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm text-primary-600 font-medium">{t('tokens.apiRequests')}</span>
                  <div className="p-2 bg-primary-100 rounded-lg group-hover:bg-primary-200 transition-colors">
                    <svg className="w-5 h-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </div>
                </div>
                <p className="text-3xl font-bold text-surface-900 mb-1">{stats.total_requests.toLocaleString()}</p>
                <p className="text-xs text-surface-600">{t('tokens.apiRequestsHint')}</p>
              </Card>

              <Card hover className="group">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm text-primary-600 font-medium">{t('tokens.averageTokens')}</span>
                  <div className="p-2 bg-primary-100 rounded-lg group-hover:bg-primary-200 transition-colors">
                    <svg className="w-5 h-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                  </div>
                </div>
                <p className="text-3xl font-bold text-surface-900 mb-1">{averageTokensPerRequest.toLocaleString()}</p>
                <p className="text-xs text-surface-600">{t('tokens.averageTokensHint')}</p>
              </Card>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <Card>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm text-primary-600 font-medium">{t('tokens.activeDays')}</div>
                    <div className="mt-1 text-2xl font-semibold text-surface-900">{activeDays}</div>
                    <div className="mt-1 text-xs text-surface-500">{t('tokens.activeDaysHint')}</div>
                  </div>
                  <div className="rounded-2xl bg-surface-50 border border-surface-200 px-3 py-2 text-right">
                    <div className="text-xs text-surface-500">{t('tokens.trendSample')}</div>
                    <div className="text-sm font-semibold text-surface-800">{t('tokens.trendSampleDays', { count: stats.by_day.length })}</div>
                  </div>
                </div>
              </Card>
              <Card>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm text-primary-600 font-medium">{t('tokens.outputShare')}</div>
                    <div className="mt-1 text-2xl font-semibold text-surface-900">{outputShare}%</div>
                    <div className="mt-1 text-xs text-surface-500">{t('tokens.outputShareHint')}</div>
                  </div>
                  <div className="w-24 h-24 rounded-full border-8 border-surface-100 flex items-center justify-center text-sm font-semibold text-primary-700">
                    {outputShare}%
                  </div>
                </div>
              </Card>
            </div>

            <div className="flex gap-2 mb-6">
              <Button
                onClick={() => setActiveTab('overview')}
                variant={activeTab === 'overview' ? 'primary' : 'secondary'}
                size="md"
              >
                {t('tokens.tabOverview')}
              </Button>
              <Button
                onClick={() => setActiveTab('details')}
                variant={activeTab === 'details' ? 'primary' : 'secondary'}
                size="md"
              >
                {t('tokens.tabDetails')}
              </Button>
            </div>

            {activeTab === 'overview' ? (
              <>
                {stats.by_day.length > 0 && (
                  <Card className="mb-6">
                    <CardHeader 
                      title={t('tokens.dailyTrend')}
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
                                    <div className="text-primary-600 font-medium">{t('tokens.tooltipTotalTokens', { count: formatNumber(dayData.total) })}</div>
                                    <div className="text-surface-600">{t('tokens.tooltipInputTokens', { count: formatNumber(dayData.input) })}</div>
                                    <div className="text-surface-600">{t('tokens.tooltipOutputTokens', { count: formatNumber(dayData.output) })}</div>
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
                    <CardHeader title={t('tokens.byProvider')} />
                    <CardContent>
                      {Object.keys(stats.by_provider).length === 0 ? (
                        <div className="text-center py-8 text-surface-500">
                          <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                          </svg>
                          {t('tokens.noData')}
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
                                    <span>{t('tokens.inputCount', { count: formatNumber(data.input) })}</span>
                                    <span>{t('tokens.outputCount', { count: formatNumber(data.output) })}</span>
                                  </div>
                                </div>
                              );
                            })}
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader title={t('tokens.byModel')} />
                    <CardContent>
                      {Object.keys(stats.by_model).length === 0 ? (
                        <div className="text-center py-8 text-surface-500">
                          <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                          </svg>
                          {t('tokens.noData')}
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
                                    <span>{t('tokens.inputCount', { count: formatNumber(data.input) })}</span>
                                    <span>{t('tokens.outputCount', { count: formatNumber(data.output) })}</span>
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
                        <th className="px-4 py-3 text-left text-xs font-semibold text-primary-600 uppercase tracking-wider">{t('tokens.tableDate')}</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-primary-600 uppercase tracking-wider">{t('tokens.tableProvider')}</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-primary-600 uppercase tracking-wider">{t('tokens.tableModel')}</th>
                        <th className="px-4 py-3 text-right text-xs font-semibold text-primary-600 uppercase tracking-wider">{t('tokens.tableInputTokens')}</th>
                        <th className="px-4 py-3 text-right text-xs font-semibold text-primary-600 uppercase tracking-wider">{t('tokens.tableOutputTokens')}</th>
                        <th className="px-4 py-3 text-right text-xs font-semibold text-primary-600 uppercase tracking-wider">{t('tokens.tableTotalTokens')}</th>
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
                    {t('tokens.showingFirstRecords', { count: 20 })}
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
            <h3 className="text-lg font-medium text-surface-700 mb-2">{t('tokens.emptyTitle')}</h3>
            <p className="text-surface-500">{t('tokens.emptyBody')}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default TokenPage;
