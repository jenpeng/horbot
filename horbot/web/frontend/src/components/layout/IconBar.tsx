import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { MessageSquarePlus, History, Settings } from 'lucide-react';
import { navItems } from './NavConfig';

const IconBar: React.FC = React.memo(() => {
  const location = useLocation();

  return (
    <aside className="hidden md:flex lg:hidden flex-col w-[68px] bg-surface-50 border-r border-black/[0.06] shrink-0 h-screen">
      {/* Header */}
      <div className="flex items-center justify-center h-12 border-b border-black/[0.04] shrink-0">
        <img 
          src="/logo.png" 
          alt="Logo" 
          className="w-7 h-7 rounded-lg shadow-sm object-cover"
        />
      </div>

      {/* 新对话按钮 */}
      <div className="flex justify-center py-2 shrink-0">
        <button className="w-10 h-10 rounded-lg bg-primary-500 hover:bg-primary-600 flex items-center justify-center transition-colors">
          <MessageSquarePlus className="w-4 h-4 text-white" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto scrollbar-hide">
        <div className="flex flex-col items-center px-2 py-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={`
                  w-10 h-10 rounded-lg flex items-center justify-center my-1
                  transition-all duration-200 group relative
                  ${isActive 
                    ? 'bg-primary-500/10 text-primary-500'
                    : 'text-surface-500 hover:bg-surface-100 hover:text-surface-700'
                  }
                `}
                title={item.label}
              >
                <Icon className="w-4 h-4" />
                <div className="absolute left-full ml-2 px-2 py-1 bg-surface-900 text-white text-xs font-medium rounded-md whitespace-nowrap opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-150 z-[100] pointer-events-none shadow-lg">
                  {item.label}
                  <div className="absolute top-1/2 -left-0.5 -translate-y-1/2 w-1 h-1 bg-surface-900 rotate-45" />
                </div>
              </NavLink>
            );
          })}
        </div>
      </nav>

      {/* 底部快捷入口 */}
      <div className="border-t border-black/[0.04] shrink-0">
        <div className="flex flex-col items-center px-2 py-2">
          <button className="w-10 h-10 rounded-lg flex items-center justify-center text-surface-500 hover:bg-surface-100 hover:text-surface-700 transition-colors">
            <History className="w-4 h-4" />
          </button>
          <button className="w-10 h-10 rounded-lg flex items-center justify-center text-surface-500 hover:bg-surface-100 hover:text-surface-700 transition-colors">
            <Settings className="w-4 h-4" />
          </button>
        </div>
        
        <div className="border-t border-black/[0.04] px-2 py-2">
          <button className="w-10 h-10 rounded-lg flex items-center justify-center hover:bg-surface-100 transition-colors mx-auto">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-accent-emerald to-accent-cyan flex items-center justify-center text-xs font-semibold text-white">
              U
            </div>
          </button>
        </div>
      </div>
    </aside>
  );
});

export default IconBar;
