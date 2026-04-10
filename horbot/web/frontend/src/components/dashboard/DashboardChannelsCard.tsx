import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader } from '../ui';
import { PanelEmptyState } from '../state';
import type { DashboardChannelSummary } from '../../types';
import { CHANNEL_ICONS } from './constants';

interface DashboardChannelsCardProps {
  channels: DashboardChannelSummary[];
  counts: {
    total: number;
    enabled: number;
    online: number;
    disabled: number;
    misconfigured: number;
  };
}

const DashboardChannelsCard = ({
  channels,
  counts,
}: DashboardChannelsCardProps) => (
  <Card data-testid="dashboard-channel-card" className="self-start overflow-hidden border border-surface-200/60 shadow-sm transition-all duration-500 ease-out hover:shadow-lg">
    <CardHeader
      className="px-5 pt-5 pb-0"
      title={(
        <div>
          <div className="flex items-center gap-2">
            <span className="text-lg font-semibold text-surface-900 tracking-tight">Channel Status</span>
            <span className="flex items-center gap-1.5 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-700 shadow-sm">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
              {counts.online} Online
            </span>
          </div>
        </div>
      )}
      action={(
        <Link to="/channels" className="text-sm font-medium text-primary-600 hover:text-primary-700 transition-colors flex items-center gap-1.5 group">
          Manage
          <svg className="w-4 h-4 transform group-hover:translate-x-1 transition-transform duration-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
          </svg>
        </Link>
      )}
    />
    <CardContent className="space-y-4 px-5 pb-5 pt-4">
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <div className="rounded-2xl border border-surface-200 bg-surface-50 px-3 py-3">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-surface-400">Total</p>
          <p className="mt-2 text-base font-semibold text-surface-900">{counts.total}</p>
        </div>
        <div className="rounded-2xl border border-primary-100 bg-primary-50 px-3 py-3">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-primary-500">Enabled</p>
          <p className="mt-2 text-base font-semibold text-primary-700">{counts.enabled}</p>
        </div>
        <div className="rounded-2xl border border-emerald-100 bg-emerald-50 px-3 py-3">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-emerald-500">Online</p>
          <p className="mt-2 text-base font-semibold text-emerald-700">{counts.online}</p>
        </div>
        <div className="rounded-2xl border border-amber-100 bg-amber-50 px-3 py-3">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-amber-500">Missing Config</p>
          <p className="mt-2 text-base font-semibold text-amber-700">{counts.misconfigured}</p>
        </div>
      </div>

      {channels.length > 0 ? (
        <div className="grid gap-3 md:grid-cols-2">
          {channels.map((channel) => {
            const channelKey = channel.name.toLowerCase();
            const channelIcon = CHANNEL_ICONS[channelKey] || CHANNEL_ICONS.default;

            return (
              <div
                key={channel.name}
                data-testid={`dashboard-channel-${channel.name}`}
                className="group rounded-2xl border border-surface-200/70 bg-white px-4 py-4 transition-all duration-300 hover:-translate-y-0.5 hover:border-surface-300 hover:shadow-sm"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className={`relative flex h-10 w-10 items-center justify-center rounded-xl transition-all duration-300 group-hover:scale-105 ${
                      channel.status === 'online'
                        ? 'bg-gradient-to-br from-emerald-100 to-emerald-50 text-emerald-600 shadow-md shadow-emerald-500/10'
                        : channel.status === 'error'
                          ? 'bg-gradient-to-br from-amber-100 to-amber-50 text-amber-600 shadow-sm'
                          : 'bg-surface-100 text-surface-400 shadow-sm'
                    }`}>
                      {channelIcon}
                      {channel.status === 'online' && (
                        <div className="absolute -right-1 -top-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-white shadow-sm">
                          <div className="h-2 w-2 rounded-full bg-emerald-500 shadow-lg shadow-emerald-500/50 animate-pulse" />
                        </div>
                      )}
                    </div>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="truncate font-medium tracking-wide text-surface-900">{channel.display_name}</span>
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          channel.status === 'online'
                            ? 'bg-emerald-50 text-emerald-600'
                            : channel.status === 'error'
                              ? 'bg-amber-50 text-amber-700'
                              : 'bg-surface-100 text-surface-500'
                        }`}>
                          {channel.status_label}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-surface-500">{channel.name}</p>
                    </div>
                  </div>
                  <Link
                    to="/channels"
                    className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-surface-200 bg-surface-50 px-3 py-1.5 text-xs font-medium text-surface-600 transition-colors hover:border-primary-200 hover:bg-primary-50 hover:text-primary-700"
                  >
                    View
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                    </svg>
                  </Link>
                </div>

                <div className="mt-3 space-y-2">
                  {channel.reason && (
                    <p className="text-sm text-surface-600">{channel.reason}</p>
                  )}
                  {!channel.reason && channel.missing_fields.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5">
                      {channel.missing_fields.slice(0, 3).map((field) => (
                        <span
                          key={field}
                          className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700"
                        >
                          {field}
                        </span>
                      ))}
                      {channel.missing_fields.length > 3 && (
                        <span className="text-[11px] text-amber-700">+{channel.missing_fields.length - 3}</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <PanelEmptyState
          title="No channels configured"
          description="Add channels in the Channels page, then enable the ones you want to run"
        />
      )}
    </CardContent>
  </Card>
);

export default DashboardChannelsCard;
