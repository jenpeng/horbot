import React, { useState } from 'react';
import { useLocation } from 'react-router-dom';

export interface BreadcrumbItem {
  label: string;
  path?: string;
}

interface HeaderProps {
  title?: string;
  breadcrumbs?: BreadcrumbItem[];
  showMenuButton?: boolean;
  onMenuClick?: () => void;
  showToolsButton?: boolean;
  toolsActive?: boolean;
  onToolsClick?: () => void;
  showSearch?: boolean;
  onSearch?: (query: string) => void;
  showNotifications?: boolean;
  notificationCount?: number;
  user?: {
    name: string;
    avatar?: string;
  };
  onUserClick?: () => void;
  className?: string;
}

const getPageTitle = (pathname: string): string => {
  const routes: Record<string, string> = {
    '/': 'Dashboard',
    '/chat': 'Chat',
    '/skills': 'Skills & MCP',
    '/tasks': 'Tasks',
    '/channels': 'Channels',
    '/status': 'Status',
    '/tokens': 'Token统计',
    '/config': 'Configuration',
  };
  return routes[pathname] || 'Horbot';
};

const MenuIcon: React.FC = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
  </svg>
);

const SearchIcon: React.FC = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
  </svg>
);

const BellIcon: React.FC = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
  </svg>
);

const ToolsIcon: React.FC = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17L17.25 21A2.652 2.652 0 0021 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 11-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 004.486-6.336l-3.276 3.277a3.004 3.004 0 01-2.25-2.25l3.276-3.276a4.5 4.5 0 00-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26m-1.745 1.437l1.745-1.437m6.615 8.206L15.75 15.75M4.867 19.125h.008v.008h-.008v-.008z" />
  </svg>
);

const ChevronDownIcon: React.FC = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
  </svg>
);

interface UserMenuProps {
  user?: {
    name: string;
    avatar?: string;
  };
  onClick?: () => void;
}

const UserMenu: React.FC<UserMenuProps> = ({ user, onClick }) => (
  <button
    onClick={onClick}
    className="flex items-center gap-2 p-1.5 pr-3 rounded-lg hover:bg-surface-800/50 transition-colors"
  >
    <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-brand-500 to-accent-purple flex items-center justify-center">
      {user?.avatar ? (
        <img src={user.avatar} alt={user.name} className="w-full h-full rounded-lg object-cover" />
      ) : (
        <span className="text-xs font-bold text-white">{user?.name?.charAt(0).toUpperCase() || 'U'}</span>
      )}
    </div>
    <span className="hidden sm:block text-sm font-medium text-surface-300">{user?.name || '用户'}</span>
    <ChevronDownIcon />
  </button>
);

interface PageTitleProps {
  title: string;
  showIcon?: boolean;
}

const PageTitle: React.FC<PageTitleProps> = ({ title, showIcon = true }) => (
  <div className="hidden lg:flex items-center gap-2">
    {showIcon && (
      <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-brand-500 to-accent-purple flex items-center justify-center">
        <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      </div>
    )}
    <span className="text-sm font-medium text-surface-300">{title}</span>
  </div>
);

interface MobileTitleProps {
  title: string;
}

const MobileTitle: React.FC<MobileTitleProps> = ({ title }) => (
  <div className="lg:hidden flex items-center gap-2">
    <img 
      src="/logo.png" 
      alt="Logo" 
      className="w-8 h-8 rounded-lg object-cover"
    />
    <span className="text-sm font-semibold text-surface-200">{title}</span>
  </div>
);

export const Header: React.FC<HeaderProps> = ({
  title,
  breadcrumbs,
  showMenuButton = true,
  onMenuClick,
  showToolsButton = true,
  toolsActive = false,
  onToolsClick,
  showSearch = true,
  onSearch,
  showNotifications = true,
  notificationCount = 0,
  user,
  onUserClick,
  className = '',
}) => {
  const location = useLocation();
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const pageTitle = title || getPageTitle(location.pathname);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch?.(searchQuery);
  };

  return (
    <header
      className={`
        bg-surface-900/80 backdrop-blur-xl border-b border-surface-800/50 sticky top-0 z-30
        ${className}
      `}
    >
      <div className="flex items-center justify-between h-14 px-4">
        <div className="flex items-center gap-3">
          {showMenuButton && (
            <button
              onClick={onMenuClick}
              className="lg:hidden p-2 -ml-2 rounded-lg text-surface-400 hover:text-surface-200 hover:bg-surface-800/50 transition-colors"
              aria-label="Open menu"
            >
              <MenuIcon />
            </button>
          )}

          <PageTitle title={pageTitle} />
          <MobileTitle title="Horbot" />

          {breadcrumbs && breadcrumbs.length > 0 && (
            <nav className="hidden md:flex items-center gap-2 text-sm">
              {breadcrumbs.map((item, index) => (
                <React.Fragment key={index}>
                  {index > 0 && <span className="text-surface-600">/</span>}
                  {item.path ? (
                    <a href={item.path} className="text-surface-400 hover:text-surface-200 transition-colors">
                      {item.label}
                    </a>
                  ) : (
                    <span className="text-surface-300">{item.label}</span>
                  )}
                </React.Fragment>
              ))}
            </nav>
          )}
        </div>

        <div className="flex items-center gap-2">
          {showToolsButton && (
            <button
              onClick={onToolsClick}
              className={`
                hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all duration-200
                ${toolsActive
                  ? 'bg-brand-500/10 text-brand-400'
                  : 'text-surface-400 hover:text-surface-200 hover:bg-surface-800/50'
                }
              `}
              title={toolsActive ? 'Collapse Tools Panel' : 'Expand Tools Panel'}
            >
              <ToolsIcon />
              <span className="text-sm font-medium">Tools</span>
            </button>
          )}

          {showSearch && (
            <>
              {searchOpen ? (
                <form onSubmit={handleSearch} className="relative">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search..."
                    autoFocus
                    className="w-48 sm:w-64 px-3 py-1.5 pl-9 text-sm bg-surface-800 border border-surface-700 rounded-lg text-surface-100 placeholder-surface-500 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500"
                  />
                  <SearchIcon />
                  <button
                    type="button"
                    onClick={() => {
                      setSearchOpen(false);
                      setSearchQuery('');
                    }}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 text-surface-500 hover:text-surface-300"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </form>
              ) : (
                <button
                  onClick={() => setSearchOpen(true)}
                  className="p-2 rounded-lg text-surface-400 hover:text-surface-200 hover:bg-surface-800/50 transition-colors"
                  aria-label="Search"
                >
                  <SearchIcon />
                </button>
              )}
            </>
          )}

          {showNotifications && (
            <button
              className="p-2 rounded-lg text-surface-400 hover:text-surface-200 hover:bg-surface-800/50 transition-colors relative"
              aria-label="Notifications"
            >
              <BellIcon />
              {notificationCount > 0 && (
                <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-accent-pink rounded-full" />
              )}
            </button>
          )}

          <div className="h-6 w-px bg-surface-800 mx-1" />

          <UserMenu user={user} onClick={onUserClick} />
        </div>
      </div>
    </header>
  );
};

export default Header;
