import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { PanelLeftClose } from 'lucide-react';
import { navItems } from './NavConfig';

interface NavigationPanelProps {
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

const NavigationPanel: React.FC<NavigationPanelProps> = React.memo(({
  isCollapsed = true,
  onToggleCollapse
}) => {
  const location = useLocation();

  return (
    <>
      <aside
        className={`
          hidden lg:flex flex-col bg-surface-50 border-r border-black/[0.06]
          transition-[width] duration-300 ease-[cubic-bezier(0.4,0,0.2,1)] shrink-0 h-screen overflow-hidden
          ${isCollapsed ? 'w-[68px]' : 'w-[260px]'}
        `}
      >
        {/* Header */}
        <div className={`flex items-center h-14 border-b border-black/[0.04] shrink-0 ${isCollapsed ? 'justify-center px-2' : 'justify-between px-4'}`}>
          {/* Logo和标题 */}
          <div className={`flex items-center gap-3 transition-all duration-300 ${isCollapsed ? 'opacity-0 w-0 overflow-hidden' : 'opacity-100'}`}>
            <img 
              src="/logo.png" 
              alt="Logo" 
              className="w-8 h-8 rounded-lg shadow-sm shrink-0 object-cover"
            />
            <span className="text-base font-semibold text-surface-900 whitespace-nowrap">Horbot</span>
          </div>
          
          {/* 展开/折叠按钮 */}
          <button
            onClick={onToggleCollapse}
            className={`flex items-center justify-center w-10 h-10 rounded-lg hover:bg-surface-100 transition-colors shrink-0 ${isCollapsed ? '' : 'ml-auto'}`}
            aria-label={isCollapsed ? "展开导航栏" : "折叠导航栏"}
          >
            <PanelLeftClose className={`text-surface-400 transition-transform duration-300 ${isCollapsed ? 'rotate-180' : ''}`} />
          </button>
        </div>

        {/* Navigation - 展开状态 */}
        <nav className={`flex-1 overflow-y-auto scrollbar-hide transition-opacity duration-300 ${isCollapsed ? 'opacity-0 pointer-events-none' : 'opacity-100'}`}>
          <div className="px-3 py-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;

              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={`group flex items-center rounded-lg transition-all duration-200 relative w-full gap-3 px-3 h-10 mb-1`}
                >
                  {isActive && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-primary-500 rounded-r-full" />
                  )}
                  
                  <span className={`
                    flex items-center justify-center shrink-0 rounded-lg w-8 h-8
                    transition-all duration-200
                    ${isActive
                      ? 'bg-primary-500/10 text-primary-600'
                      : 'text-surface-500 group-hover:bg-surface-100 group-hover:text-surface-700'
                    }
                  `}>
                    <Icon className="w-4 h-4" />
                  </span>
                  
                  <span className={`flex-1 text-sm whitespace-nowrap leading-10 ${isActive ? 'font-medium text-surface-900' : 'text-surface-600 group-hover:text-surface-900'}`}>
                    {item.label}
                  </span>
                </NavLink>
              );
            })}
          </div>
        </nav>

        {/* Navigation - 折叠状态 */}
        <nav className={`flex-1 overflow-y-auto scrollbar-hide absolute left-0 top-14 bottom-0 w-[68px] transition-opacity duration-300 ${isCollapsed ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
          <div className="flex flex-col items-center py-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;

              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  title={item.label}
                  className={`
                    w-10 h-10 rounded-lg flex items-center justify-center mb-1
                    transition-all duration-200
                    ${isActive 
                      ? 'bg-primary-500/10 text-primary-600'
                      : 'text-surface-500 hover:bg-surface-100 hover:text-surface-700'
                    }
                  `}
                >
                  <Icon className="w-4 h-4" />
                </NavLink>
              );
            })}
          </div>
        </nav>

        {/* 底部 - 用户信息 */}
        <div className="border-t border-black/[0.04] shrink-0">
          {/* 展开状态 */}
          <div className={`transition-all duration-300 ${isCollapsed ? 'opacity-0 h-0 overflow-hidden' : 'opacity-100 px-3 py-3'}`}>
            <button className="group flex items-center rounded-lg hover:bg-surface-100 transition-colors w-full gap-3 px-3 h-11">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-accent-emerald to-accent-cyan flex items-center justify-center text-xs font-semibold text-white shrink-0">
                U
              </div>
              <div className="flex-1 min-w-0 text-left">
                <p className="text-sm font-medium text-surface-900 truncate">用户</p>
                <p className="text-xs text-surface-500">免费版</p>
              </div>
            </button>
          </div>
          {/* 折叠状态 */}
          <div className={`flex items-center justify-center transition-all duration-300 ${isCollapsed ? 'opacity-100 py-3' : 'opacity-0 h-0 overflow-hidden'}`}>
            <button className="group">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-accent-emerald to-accent-cyan flex items-center justify-center text-xs font-semibold text-white">
                U
              </div>
            </button>
          </div>
        </div>
      </aside>
    </>
  );
});

export default NavigationPanel;
