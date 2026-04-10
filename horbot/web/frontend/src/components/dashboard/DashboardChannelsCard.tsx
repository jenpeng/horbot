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
  <Card data-testid="dashboard-channel-card" className="border border-surface-200/60 shadow-sm hover:shadow-lg transition-all duration-500 ease-out overflow-hidden">
    <CardHeader
      title={(
        <div>
          <div className="flex items-center gap-2">
            <span className="text-lg font-semibold text-surface-900 tracking-tight">Channel Status</span>
            <span className="px-2.5 py-0.5 text-xs font-medium bg-emerald-100 text-emerald-700 rounded-full shadow-sm flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              {counts.online} Online
            </span>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full bg-surface-100 px-2.5 py-1 font-medium text-surface-600">
              {counts.total} Total
            </span>
            <span className="rounded-full bg-primary-50 px-2.5 py-1 font-medium text-primary-700">
              {counts.enabled} Enabled
            </span>
            {counts.misconfigured > 0 && (
              <span className="rounded-full bg-amber-50 px-2.5 py-1 font-medium text-amber-700">
                {counts.misconfigured} Missing Config
              </span>
            )}
            {counts.disabled > 0 && (
              <span className="rounded-full bg-surface-100 px-2.5 py-1 font-medium text-surface-500">
                {counts.disabled} Disabled
              </span>
            )}
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
    <CardContent padding="none">
      {channels.length > 0 ? (
        <div className="divide-y divide-surface-100/80">
          {channels.map((channel) => {
            const channelKey = channel.name.toLowerCase();
            const channelIcon = CHANNEL_ICONS[channelKey] || CHANNEL_ICONS.default;

            return (
              <div key={channel.name} data-testid={`dashboard-channel-${channel.name}`} className="flex items-center justify-between px-5 py-3.5 hover:bg-gradient-to-r hover:from-surface-50/80 hover:to-transparent transition-all duration-300 group">
                <div className="flex items-center gap-3.5">
                  <div className={`relative w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-300 group-hover:scale-105 ${
                    channel.status === 'online'
                      ? 'bg-gradient-to-br from-emerald-100 to-emerald-50 text-emerald-600 shadow-md shadow-emerald-500/10'
                      : channel.status === 'error'
                        ? 'bg-gradient-to-br from-amber-100 to-amber-50 text-amber-600 shadow-sm'
                        : 'bg-surface-100 text-surface-400 shadow-sm'
                  }`}>
                    {channelIcon}
                    {channel.status === 'online' && (
                      <div className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-white rounded-full flex items-center justify-center shadow-sm">
                        <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-lg shadow-emerald-500/50 animate-pulse" />
                      </div>
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2.5">
                      <span className="font-medium text-surface-900 tracking-wide">{channel.display_name}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        channel.status === 'online'
                          ? 'bg-emerald-50 text-emerald-600'
                          : channel.status === 'error'
                            ? 'bg-amber-50 text-amber-700'
                            : 'bg-surface-100 text-surface-500'
                      }`}>
                        {channel.status_label}
                      </span>
                    </div>
                    {channel.reason && (
                      <p className="mt-1 text-xs text-surface-500">{channel.reason}</p>
                    )}
                    {!channel.reason && channel.missing_fields.length > 0 && (
                      <p className="mt-1 text-xs text-amber-600">
                        缺少配置: {channel.missing_fields.join(', ')}
                      </p>
                    )}
                  </div>
                </div>
                <Link
                  to="/channels"
                  className="inline-flex items-center gap-1.5 rounded-full border border-surface-200 bg-surface-50 px-3 py-1.5 text-xs font-medium text-surface-600 transition-colors hover:border-primary-200 hover:bg-primary-50 hover:text-primary-700"
                >
                  View
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                  </svg>
                </Link>
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
