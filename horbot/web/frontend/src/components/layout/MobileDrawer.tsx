import React, { useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { X, Search } from 'lucide-react';
import { navItems } from './NavConfig';

interface MobileDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

const MobileDrawer: React.FC<MobileDrawerProps> = React.memo(({ isOpen, onClose }) => {
  const location = useLocation();

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  useEffect(() => {
    onClose();
  }, [location.pathname, onClose]);

  return (
    <>
      <div 
        className={`
          lg:hidden fixed inset-0 bg-black/40 backdrop-blur-sm z-[1040]
          transition-opacity duration-300 var(--duration-slow) var(--ease-smooth)
          ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}
        `}
        onClick={onClose}
      />

      <div 
        className={`
          lg:hidden fixed top-0 left-0 h-full w-[280px] bg-surface-50 z-[1050]
          transform transition-transform duration-300 ease-out var(--duration-slow) var(--ease-smooth)
          shadow-2xl shadow-black/20
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <div className="flex items-center justify-between px-4 h-16 border-b border-black/[0.06]">
          <div className="flex items-center gap-3">
            <div className="relative cursor-pointer hover:scale-105 transition-all duration-200">
              <img 
                src="/logo.png" 
                alt="Logo" 
                className="w-9 h-9 rounded-xl shadow-md object-cover"
              />
              <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-semantic-success rounded-full border-2 border-white" />
            </div>
            <h2 className="text-lg font-semibold text-surface-900">Horbot</h2>
          </div>
          <button 
            onClick={onClose}
            className="w-9 h-9 rounded-xl hover:bg-surface-100 flex items-center justify-center text-surface-500 hover:text-surface-700 transition-colors"
            aria-label="关闭菜单"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-4 py-4">
          <div className="flex items-center gap-3 px-3.5 py-3 bg-surface-100 rounded-xl border border-surface-300 hover:border-primary-500/30 transition-all var(--duration-normal) var(--ease-smooth) focus-within:border-primary-500 focus-within:ring-2 focus-within:ring-primary-500/10">
            <Search className="w-4 h-4 text-surface-500" />
            <input 
              type="text" 
              placeholder="搜索..." 
              className="flex-1 bg-transparent text-sm text-surface-900 placeholder-surface-500 outline-none"
            />
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 scrollbar-thin">
          <div className="mb-3 px-3">
            <p className="text-xs font-semibold text-surface-500 uppercase tracking-wider">导航菜单</p>
          </div>
          <div className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  onClick={onClose}
                  className={`
                    flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-medium
                    transition-all duration-150 ease-out relative group
                    ${isActive 
                      ? 'bg-gradient-to-r from-primary-500/10 to-accent-indigo/5 text-primary-600 shadow-sm shadow-primary-500/10'
                      : 'text-surface-600 hover:text-surface-900 hover:bg-surface-100'
                    }
                  `}
                >
                  <span className={`
                    flex items-center justify-center w-8 h-8 rounded-lg
                    transition-all duration-150 ease-out
                    ${isActive
                      ? 'bg-primary-500/10 text-primary-600 scale-110'
                      : 'bg-surface-100 text-surface-500 hover:bg-primary-500/10 hover:text-primary-500 group-hover:scale-105'
                    }
                  `}>
                    <Icon className="w-5 h-5" />
                  </span>
                  <span>{item.label}</span>
                  {isActive && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-gradient-to-b from-primary-500 to-accent-indigo rounded-r-full" />
                  )}
                </NavLink>
              );
            })}
          </div>
        </nav>

        <div className="p-3 border-t border-black/[0.06]">
          <div className="flex items-center gap-3 px-3.5 py-3 rounded-xl hover:bg-surface-100 cursor-pointer transition-all var(--duration-normal) var(--ease-smooth) group">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent-emerald to-accent-cyan flex items-center justify-center text-sm font-bold text-white shadow-md shadow-emerald-500/20 group-hover:scale-105 transition-transform duration-200 relative">
              U
              <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-semantic-success rounded-full border-2 border-white" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-surface-900 truncate">用户</p>
              <p className="text-xs text-surface-500">免费版</p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
});

export default MobileDrawer;
