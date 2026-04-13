import React from 'react';
import { Outlet } from 'react-router-dom';
import { Menu } from 'lucide-react';
import { useI18n } from '../../contexts/I18nContext';
import LanguageSwitcher from './LanguageSwitcher';

interface ContentAreaProps {
  onMobileMenuToggle?: () => void;
}

const ContentArea: React.FC<ContentAreaProps> = ({ 
  onMobileMenuToggle
}) => {
  const { t } = useI18n();

  return (
    <main className="flex-1 flex flex-col overflow-hidden bg-[#f8fafc]">
      <header className="lg:hidden flex items-center justify-between px-5 h-16 bg-white/95 backdrop-blur-xl border-b border-black/[0.06] shrink-0">
        <div className="flex items-center gap-3">
          <img 
            src="/logo.png" 
            alt="Logo" 
            className="w-10 h-10 rounded-xl shadow-md object-cover"
          />
          <h1 className="text-lg font-semibold text-[#1e293b]">{t('brand.name')}</h1>
        </div>
        <div className="flex items-center gap-2">
          <LanguageSwitcher compact />
          <button
            onClick={onMobileMenuToggle}
            className="w-10 h-10 rounded-xl hover:bg-[#f1f5f9] flex items-center justify-center text-[#64748b] hover:text-[#1e293b] transition-colors"
            aria-label={t('content.toggleMenu')}
          >
            <Menu className="w-6 h-6" />
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto">
        <Outlet />
      </div>
    </main>
  );
};

export default ContentArea;
