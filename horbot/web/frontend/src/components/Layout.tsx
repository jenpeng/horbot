import React, { useState } from 'react';
import NavigationPanel from './layout/NavigationPanel';
import ContentArea from './layout/ContentArea';
import MobileDrawer from './layout/MobileDrawer';
import { useApp } from '../stores';

const Layout: React.FC = () => {
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);
  const { sidebarCollapsed, toggleSidebar } = useApp();

  const handleMobileMenuToggle = () => {
    setIsMobileDrawerOpen(!isMobileDrawerOpen);
  };

  return (
    <div className="flex h-screen bg-surface-100 text-surface-900 font-sans overflow-hidden">
      <NavigationPanel 
        isCollapsed={sidebarCollapsed}
        onToggleCollapse={toggleSidebar}
      />
      
      <ContentArea 
        onMobileMenuToggle={handleMobileMenuToggle}
      />
      
      <MobileDrawer 
        isOpen={isMobileDrawerOpen}
        onClose={() => setIsMobileDrawerOpen(false)}
      />
    </div>
  );
};

export default Layout;
