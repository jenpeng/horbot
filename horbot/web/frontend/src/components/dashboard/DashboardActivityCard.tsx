import { Link } from 'react-router-dom';
import { Badge, Card, CardContent, CardHeader } from '../ui';
import type { DashboardActivitySummary } from '../../types';
import { ACTIVITY_ICONS } from './constants';

interface DashboardActivityCardProps {
  activities: DashboardActivitySummary[];
}

const DashboardActivityCard = ({ activities }: DashboardActivityCardProps) => (
  <Card data-testid="dashboard-activity-card" className="xl:col-span-2 border border-surface-200/60 shadow-sm hover:shadow-lg transition-shadow duration-500 ease-out overflow-hidden">
    <CardHeader
      className="mb-4 px-5 pt-5"
      title={(
        <div className="flex items-center gap-2">
          <span className="text-lg font-semibold text-surface-900 tracking-tight">Recent Activity</span>
          <span className="px-2 py-0.5 text-xs font-medium bg-primary-100 text-primary-700 rounded-full shadow-sm">
            {activities.length}
          </span>
        </div>
      )}
      action={(
        <Link to="/status" className="text-sm font-medium text-primary-600 hover:text-primary-700 transition-colors flex items-center gap-1.5 group">
          View More
          <svg className="w-4 h-4 transform group-hover:translate-x-1 transition-transform duration-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
          </svg>
        </Link>
      )}
    />
    <CardContent padding="none">
      {activities.length > 0 ? (
        <div className="divide-y divide-surface-100/80">
          {activities.map((activity, index) => (
            <div
              key={activity.id}
              data-testid={`dashboard-activity-${activity.id}`}
              className="flex items-start gap-4 px-5 py-4 hover:bg-gradient-to-r hover:from-surface-50/80 hover:to-transparent transition-all duration-300 ease-out group"
              style={{ animationDelay: `${index * 80}ms` }}
            >
              <div className={`relative w-10 h-10 rounded-[10px] flex items-center justify-center flex-shrink-0 transition-all duration-300 group-hover:scale-110 ${
                activity.status === 'success' ? 'bg-gradient-to-br from-emerald-100 to-emerald-50 text-emerald-600 shadow-sm' :
                activity.status === 'warning' ? 'bg-gradient-to-br from-amber-100 to-amber-50 text-amber-600 shadow-sm' :
                activity.status === 'error' ? 'bg-gradient-to-br from-red-100 to-red-50 text-red-600 shadow-sm' :
                'bg-gradient-to-br from-primary-100 to-primary-50 text-primary-600 shadow-sm'
              }`}>
                {ACTIVITY_ICONS[activity.type]}
                <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-white flex items-center justify-center ${
                  activity.status === 'success' ? 'bg-emerald-500' :
                  activity.status === 'warning' ? 'bg-amber-500' :
                  activity.status === 'error' ? 'bg-red-500' : 'bg-primary-500'
                }`}>
                  <div className="w-1 h-1 rounded-full bg-white animate-pulse" />
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[14px] font-medium text-surface-900 tracking-wide">{activity.message}</p>
                <div className="flex items-center gap-3 mt-1.5">
                  <p className="text-[12px] text-surface-400 flex items-center gap-1.5 group-hover:text-surface-500 transition-colors duration-300">
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    {activity.time}
                  </p>
                  <Badge
                    variant={
                      activity.status === 'success'
                        ? 'success'
                        : activity.status === 'error'
                          ? 'error'
                          : 'info'
                    }
                    size="sm"
                    className="text-[10px] px-2 py-0.5 font-medium"
                  >
                    {activity.status === 'success' ? (
                      <><svg className="w-2.5 h-2.5 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>Success</>
                    ) : activity.status === 'warning' ? (
                      <><svg className="w-2.5 h-2.5 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l6.518 11.595c.75 1.334-.213 2.996-1.742 2.996H3.48c-1.53 0-2.492-1.662-1.742-2.996L8.257 3.1zM11 8a1 1 0 10-2 0v3a1 1 0 102 0V8zm-1 7a1.25 1.25 0 100-2.5A1.25 1.25 0 0010 15z" clipRule="evenodd" /></svg>Warning</>
                    ) : activity.status === 'error' ? (
                      <><svg className="w-2.5 h-2.5 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" /></svg>Failed</>
                    ) : (
                      <><svg className="w-2.5 h-2.5 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" /></svg>Info</>
                    )}
                  </Badge>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-14 px-6">
          <div className="relative mb-4">
            <div className="w-24 h-24 rounded-full bg-surface-100 flex items-center justify-center">
              <svg className="w-12 h-12 text-surface-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
              </svg>
            </div>
            <div className="absolute inset-0 w-24 h-24 rounded-full bg-primary-100/50 animate-pulse opacity-0" />
          </div>
          <p className="text-surface-600 font-medium text-center">No recent activity</p>
          <p className="text-surface-400 text-sm text-center mt-1">Activity records will appear after system starts</p>
        </div>
      )}
    </CardContent>
  </Card>
);

export default DashboardActivityCard;
