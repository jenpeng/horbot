import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  MessageSquare,
  MessagesSquare,
  Bot,
  ListTodo,
  Radio,
  Activity,
  FileText,
  Settings,
  Coins,
  ChevronRight,
  Search,
  Plus,
  Zap,
} from 'lucide-react';

export interface NavItem {
  path: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string | number;
  badgeVariant?: 'default' | 'success' | 'warning' | 'error' | 'info';
}

export interface NavGroup {
  id: string;
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
  items: NavItem[];
  collapsible?: boolean;
  defaultCollapsed?: boolean;
}

interface SidebarProps {
  groups?: NavGroup[];
  isMobile?: boolean;
  onItemClick?: () => void;
  className?: string;
}

const DEFAULT_NAV_GROUPS: NavGroup[] = [
  {
    id: 'conversation',
    label: 'Conversation',
    icon: MessageSquare,
    collapsible: true,
    defaultCollapsed: false,
    items: [
      { path: '/chat', label: 'Chat', icon: MessageSquare, badge: '3', badgeVariant: 'info' },
      { path: '/sessions', label: 'Sessions', icon: MessagesSquare },
    ],
  },
  {
    id: 'management',
    label: 'Management',
    icon: Bot,
    collapsible: true,
    defaultCollapsed: false,
    items: [
      { path: '/skills', label: 'Skills', icon: Bot, badge: 'New', badgeVariant: 'success' },
      { path: '/tasks', label: 'Tasks', icon: ListTodo },
      { path: '/channels', label: 'Channels', icon: Radio },
    ],
  },
  {
    id: 'monitor',
    label: 'Monitor',
    icon: Activity,
    collapsible: true,
    defaultCollapsed: false,
    items: [
      { path: '/status', label: 'Status', icon: Activity },
      { path: '/logs', label: 'Logs', icon: FileText },
    ],
  },
  {
    id: 'settings',
    label: 'Settings',
    icon: Settings,
    collapsible: true,
    defaultCollapsed: false,
    items: [
      { path: '/config', label: 'Config', icon: Settings },
      { path: '/tokens', label: 'Token Stats', icon: Coins },
    ],
  },
];

const getBadgeStyles = (variant: string = 'default'): string => {
  const styles: Record<string, string> = {
    default: 'bg-surface-200 text-surface-700',
    success: 'bg-semantic-success-light text-semantic-success',
    warning: 'bg-semantic-warning-light text-semantic-warning',
    error: 'bg-semantic-error-light text-semantic-error',
    info: 'bg-semantic-info-light text-semantic-info',
  };
  return styles[variant] || styles.default;
};

interface SidebarHeaderProps {
  title?: string;
  subtitle?: string;
}

const SidebarHeader: React.FC<SidebarHeaderProps> = ({
  title,
  subtitle = 'AI Assistant',
}) => (
  <div className="p-5 border-b border-black/[0.06]">
    <div className="flex items-center gap-3">
      <div className="relative">
        <img 
          src="/logo.png" 
          alt="Logo" 
          className="w-11 h-11 rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105 cursor-pointer object-cover"
        />
        <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-semantic-success rounded-full border-2 border-white animate-pulse" />
      </div>
      <div>
        <h1 className="text-base font-semibold text-surface-900">{title}</h1>
        <p className="text-xs text-surface-500">{subtitle}</p>
      </div>
    </div>
  </div>
);

interface SidebarQuickActionsProps {
  onNewChat?: () => void;
}

const SidebarQuickActions: React.FC<SidebarQuickActionsProps> = ({ onNewChat }) => (
  <div className="px-4 py-3 border-b border-black/[0.06]">
    <button
      onClick={onNewChat}
      className="w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-gradient-to-br from-primary-500 to-accent-indigo text-white font-medium text-sm hover:from-primary-600 hover:to-primary-700 transition-all duration-200 shadow-md shadow-primary-500/20 hover:shadow-lg hover:shadow-primary-500/30 hover:scale-[1.02] active:scale-[0.98]"
    >
      <Plus className="w-5 h-5" />
      <span>New Chat</span>
    </button>
  </div>
);

interface SidebarSearchProps {
  placeholder?: string;
}

const SidebarSearch: React.FC<SidebarSearchProps> = ({ placeholder = 'Search...' }) => {
  const [isFocused, setIsFocused] = useState(false);
  
  return (
    <div className="px-4 py-3">
      <div className={`
        flex items-center gap-3 px-4 py-3 rounded-xl border transition-all duration-200
        ${isFocused 
          ? 'bg-white border-primary-500 ring-2 ring-primary-500/10' 
          : 'bg-surface-50 border-black/[0.06] hover:border-primary-500/30'
        }
      `}>
        <Search className={`w-5 h-5 transition-colors ${isFocused ? 'text-primary-500' : 'text-surface-400'}`} />
        <input
          type="text"
          placeholder={placeholder}
          className="flex-1 bg-transparent text-sm text-surface-900 placeholder-surface-400 outline-none"
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
        />
      </div>
    </div>
  );
};

interface SidebarStatusProps {
  status?: 'online' | 'offline' | 'degraded';
  statusLabel?: string;
  statusDescription?: string;
  services?: { name: string; status: 'online' | 'offline' | 'active' }[];
}

const SidebarStatus: React.FC<SidebarStatusProps> = ({
  status = 'online',
  statusLabel = 'System Online',
  statusDescription = 'All services running normally',
  services = [
    { name: 'API', status: 'online' },
    { name: 'AI Model', status: 'active' },
    { name: 'Database', status: 'online' },
  ],
}) => {
  const statusColors: Record<string, string> = {
    online: 'bg-semantic-success',
    offline: 'bg-semantic-error',
    degraded: 'bg-semantic-warning',
    active: 'bg-primary-500',
  };

  const statusIconColors: Record<string, string> = {
    online: 'text-semantic-success',
    offline: 'text-semantic-error',
    degraded: 'text-semantic-warning',
    active: 'text-primary-500',
  };

  return (
    <div className="p-4 border-t border-black/[0.06]">
      <div className="p-4 rounded-xl bg-gradient-to-br from-surface-50 to-surface-100 border border-black/[0.06]">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-semantic-success/20 to-semantic-success/5 flex items-center justify-center">
            <Zap className={`w-5 h-5 ${statusIconColors[status]}`} />
          </div>
          <div>
            <div className="text-sm font-medium text-surface-900">{statusLabel}</div>
            <div className="text-xs text-surface-500">{statusDescription}</div>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2 text-xs">
          {services.map((service) => (
            <div key={service.name} className="flex items-center gap-1.5 text-surface-600">
              <span className={`w-1.5 h-1.5 rounded-full ${statusColors[service.status]} ${service.status === 'online' ? 'animate-pulse' : ''}`} />
              <span className="truncate">{service.name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export const Sidebar: React.FC<SidebarProps> = ({
  groups = DEFAULT_NAV_GROUPS,
  isMobile = false,
  onItemClick,
  className = '',
}) => {
  const location = useLocation();
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(
    new Set(
      groups.filter(g => g.defaultCollapsed).map(g => g.id)
    )
  );

  const toggleGroup = (groupId: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(groupId)) {
        next.delete(groupId);
      } else {
        next.add(groupId);
      }
      return next;
    });
  };

  const isActive = (path: string) => location.pathname === path;

  const renderNavItem = (item: NavItem) => {
    const active = isActive(item.path);
    const Icon = item.icon;
    
    return (
      <Link
        key={item.path}
        to={item.path}
        onClick={onItemClick}
        className={`
          flex items-center gap-3 px-4 py-3 rounded-xl
          transition-all duration-200 group relative
          ${active
            ? 'bg-gradient-to-r from-primary-500/10 to-accent-indigo/5 text-primary-600 shadow-sm shadow-primary-500/10'
            : 'text-surface-600 hover:text-surface-900 hover:bg-surface-50'
          }
        `}
      >
        <span className={`
          flex items-center justify-center w-8 h-8 rounded-lg
          transition-all duration-200
          ${active
            ? 'bg-primary-500/10 text-primary-600'
            : 'bg-surface-100 text-surface-500 group-hover:bg-primary-500/10 group-hover:text-primary-500'
          }
        `}>
          <Icon className="w-5 h-5" />
        </span>
        <span className="flex-1 font-medium text-sm">{item.label}</span>
        {item.badge && (
          <span className={`
            px-2 py-0.5 rounded-full text-xs font-semibold
            ${getBadgeStyles(item.badgeVariant)}
          `}>
            {item.badge}
          </span>
        )}
        {active && (
          <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-gradient-to-b from-primary-500 to-accent-indigo rounded-r-full" />
        )}
      </Link>
    );
  };

  const renderNavGroup = (group: NavGroup) => {
    const GroupIcon = group.icon;
    const isCollapsed = collapsedGroups.has(group.id);
    
    return (
      <div key={group.id} className="mb-2">
        <button
          onClick={() => group.collapsible && toggleGroup(group.id)}
          className={`
            flex items-center gap-2 w-full px-4 py-2.5 text-xs font-semibold text-surface-500 uppercase tracking-wider
            ${group.collapsible && !isMobile ? 'hover:text-surface-700 cursor-pointer' : 'cursor-default'}
            transition-colors duration-200
          `}
        >
          {GroupIcon && <GroupIcon className="w-4 h-4" />}
          <span className="flex-1 text-left">{group.label}</span>
          {group.collapsible && !isMobile && (
            <ChevronRight className={`
              w-4 h-4 transition-transform duration-200
              ${isCollapsed ? '' : 'rotate-90'}
            `} />
          )}
        </button>
        <div className={`
          space-y-1 overflow-hidden transition-all duration-200
          ${isCollapsed && !isMobile ? 'max-h-0 opacity-0' : 'max-h-[500px] opacity-100'}
        `}>
          {group.items.map(renderNavItem)}
        </div>
      </div>
    );
  };

  return (
    <div className={`flex flex-col h-full bg-white border-r border-black/[0.06] ${className}`}>
      <SidebarHeader title="Horbot" />
      
      {!isMobile && <SidebarQuickActions />}
      
      {!isMobile && <SidebarSearch />}

      <nav className="flex-1 overflow-y-auto py-2 px-2">
        {groups.map(renderNavGroup)}
      </nav>

      {!isMobile && <SidebarStatus />}
    </div>
  );
};

export default Sidebar;
