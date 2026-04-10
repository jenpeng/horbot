import type { DashboardAlertSummary } from '../../types';

interface DashboardAlertsProps {
  alerts: DashboardAlertSummary[];
}

const DashboardAlerts = ({ alerts }: DashboardAlertsProps) => {
  if (alerts.length === 0) {
    return null;
  }

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {alerts.slice(0, 4).map((alert) => (
        <div
          key={alert.id}
          data-testid={`dashboard-alert-${alert.id}`}
          className={`rounded-2xl border px-4 py-3 shadow-sm ${
            alert.level === 'error'
              ? 'border-red-200 bg-red-50'
              : alert.level === 'warning'
                ? 'border-amber-200 bg-amber-50'
                : 'border-sky-200 bg-sky-50'
          }`}
        >
          <div className="flex items-start gap-3">
            <div className={`mt-0.5 h-2.5 w-2.5 rounded-full ${
              alert.level === 'error'
                ? 'bg-red-500'
                : alert.level === 'warning'
                  ? 'bg-amber-500'
                  : 'bg-sky-500'
            }`} />
            <div className="min-w-0">
              <p className="text-sm font-semibold text-surface-900">{alert.title}</p>
              <p className="mt-1 text-sm text-surface-600">{alert.message}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default DashboardAlerts;
