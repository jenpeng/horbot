import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { getStorageItem, setStorageItem } from '../utils/storage';

export type Theme = 'light' | 'dark' | 'system';

interface AppState {
  sidebarCollapsed: boolean;
  theme: Theme;
}

interface AppContextType extends AppState {
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setTheme: (theme: Theme) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);
const SIDEBAR_COLLAPSED_STORAGE_KEY = 'horbot.sidebar-collapsed';

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};

interface AppProviderProps {
  children: ReactNode;
}

export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => (
    getStorageItem<boolean>(SIDEBAR_COLLAPSED_STORAGE_KEY, true)
  ));
  const [theme, setThemeState] = useState<Theme>('system');

  useEffect(() => {
    setStorageItem(SIDEBAR_COLLAPSED_STORAGE_KEY, sidebarCollapsed);
  }, [sidebarCollapsed]);

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => !prev);
  }, []);

  const setSidebarCollapsedCallback = useCallback((collapsed: boolean) => {
    setSidebarCollapsed(collapsed);
  }, []);

  const setTheme = useCallback((newTheme: Theme) => {
    setThemeState(newTheme);
  }, []);

  const value: AppContextType = {
    sidebarCollapsed,
    theme,
    toggleSidebar,
    setSidebarCollapsed: setSidebarCollapsedCallback,
    setTheme,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};
