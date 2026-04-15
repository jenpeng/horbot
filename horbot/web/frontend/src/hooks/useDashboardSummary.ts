import { useEffect, useState } from 'react';
import { statusService } from '../services';
import type { DashboardChannelSummary, DashboardSummary } from '../types';
import { createAsyncResourceCache } from '../utils/asyncResourceCache';

const dashboardSummaryCache = createAsyncResourceCache(
  () => statusService.getDashboardSummary(),
  {
    ttlMs: 15_000,
    keyFn: () => 'dashboard-summary',
  },
);

const computeChannelCounts = (items: DashboardChannelSummary[]) => ({
  total: items.length,
  enabled: items.filter((item) => item.enabled).length,
  online: items.filter((item) => item.status === 'online').length,
  disabled: items.filter((item) => item.status === 'disabled').length,
  misconfigured: items.filter((item) => item.status === 'error').length,
});

export const useDashboardSummary = () => {
  const cachedSummary = dashboardSummaryCache.peek();
  const [dashboardSummary, setDashboardSummary] = useState<DashboardSummary | null>(cachedSummary ?? null);
  const [isLoading, setIsLoading] = useState(!cachedSummary);
  const [error, setError] = useState<string | null>(null);
  const [refreshVersion, setRefreshVersion] = useState(0);

  useEffect(() => {
    let disposed = false;
    let hasLoadedInitial = false;

    const fetchData = async (silent: boolean = false, force: boolean = false) => {
      if (!silent) {
        setIsLoading(true);
      }
      setError(null);

      try {
        const summaryData = force
          ? await dashboardSummaryCache.refresh()
          : await dashboardSummaryCache.get();
        if (disposed) {
          return;
        }
        setDashboardSummary(summaryData);
        hasLoadedInitial = true;
      } catch (err) {
        if (!disposed && !hasLoadedInitial) {
          setError('Failed to load data');
        }
        console.error('Error fetching dashboard data:', err);
      } finally {
        if (!disposed && !silent) {
          setIsLoading(false);
        }
      }
    };

    void fetchData(Boolean(cachedSummary));
    const intervalId = window.setInterval(() => {
      void fetchData(true);
    }, 30000);

    return () => {
      disposed = true;
      window.clearInterval(intervalId);
    };
  }, [refreshVersion]);

  return {
    dashboardSummary,
    isLoading,
    error,
    refreshSummary: () => {
      dashboardSummaryCache.clear();
      setRefreshVersion((current) => current + 1);
    },
    systemStatus: dashboardSummary?.system_status ?? null,
    channelStatusList: dashboardSummary?.channels.items ?? [],
    channelCounts: dashboardSummary?.channels.counts ?? computeChannelCounts([]),
    recentActivities: dashboardSummary?.recent_activities ?? [],
    dashboardAlerts: dashboardSummary?.alerts ?? [],
  };
};
