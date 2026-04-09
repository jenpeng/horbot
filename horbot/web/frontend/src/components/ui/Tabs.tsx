import React from 'react';

interface Tab {
  id: string;
  label: string;
  icon?: React.ReactNode;
  disabled?: boolean;
}

interface TabsProps {
  tabs: Tab[];
  activeTab?: string;
  onChange?: (tabId: string) => void;
  variant?: 'default' | 'pills' | 'underline';
  className?: string;
}

const Tabs: React.FC<TabsProps> = ({
  tabs,
  activeTab,
  onChange,
  variant = 'default',
  className = '',
}) => {
  const variantStyles = {
    default: {
      container: 'flex gap-1 p-1 bg-surface-100 rounded-lg',
      tab: 'px-4 py-2 rounded-md text-sm font-medium transition-all duration-200',
      active: 'bg-primary-500 text-white shadow-md',
      inactive: 'text-surface-600 hover:text-surface-900 hover:bg-surface-200',
    },
    pills: {
      container: 'flex gap-2',
      tab: 'px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 border',
      active: 'bg-primary-500/10 text-primary-600 border-primary-500/50',
      inactive: 'text-surface-600 border-surface-200 hover:text-surface-900 hover:border-surface-300',
    },
    underline: {
      container: 'flex gap-6 border-b border-surface-200',
      tab: 'pb-3 text-sm font-medium transition-all duration-200 border-b-2 -mb-px',
      active: 'text-primary-600 border-primary-500',
      inactive: 'text-surface-600 border-transparent hover:text-surface-900',
    },
  };

  const styles = variantStyles[variant];

  return (
    <div className={`${styles.container} ${className}`}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => !tab.disabled && onChange?.(tab.id)}
          disabled={tab.disabled}
          className={`
            ${styles.tab}
            ${activeTab === tab.id ? styles.active : styles.inactive}
            ${tab.disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
            flex items-center gap-2
          `}
        >
          {tab.icon}
          {tab.label}
        </button>
      ))}
    </div>
  );
};

export default Tabs;
