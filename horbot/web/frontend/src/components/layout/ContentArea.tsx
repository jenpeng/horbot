import React from 'react';
import { Outlet } from 'react-router-dom';
import { Menu } from 'lucide-react';

interface ContentAreaProps {
  onMobileMenuToggle?: () => void;
}

const ContentArea: React.FC<ContentAreaProps> = ({ 
  onMobileMenuToggle
}) => {
  return (
    <main className="flex-1 flex flex-col overflow-hidden bg-[#f8fafc]">
      <header className="lg:hidden flex items-center justify-between px-5 h-16 bg-white/95 backdrop-blur-xl border-b border-black/[0.06] shrink-0">
        <div className="flex items-center gap-3">
          <img 
            src="/logo.png" 
            alt="Logo" 
            className="w-10 h-10 rounded-xl shadow-md object-cover"
          />
          <h1 className="text-lg font-semibold text-[#1e293b]">Horbot</h1>
        </div>
        <button
          onClick={onMobileMenuToggle}
          className="w-10 h-10 rounded-xl hover:bg-[#f1f5f9] flex items-center justify-center text-[#64748b] hover:text-[#1e293b] transition-colors"
          aria-label="切换菜单"
        >
          <Menu className="w-6 h-6" />
        </button>
      </header>

      <div className="flex-1 overflow-y-auto">
        <Outlet />
      </div>
    </main>
  );
};

export default ContentArea;
