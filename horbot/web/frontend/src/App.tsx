
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Suspense } from 'react';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import { useI18n } from './contexts/I18nContext';
import { ToastProvider } from './contexts/ToastContext';
import Toast from './components/Toast';
import { lazyWithReload } from './utils/lazyWithReload';
import { registerRoutePreload } from './utils/routePreload';

const dashboardPageLoader = () => import('./pages/DashboardPage');
const chatPageLoader = () => import('./pages/ChatPage');
const configPageLoader = () => import('./pages/ConfigPage');
const channelsPageLoader = () => import('./pages/ChannelsPage');
const tasksPageLoader = () => import('./pages/TasksPage');
const statusPageLoader = () => import('./pages/StatusPage');
const skillsPageLoader = () => import('./pages/SkillsPage');
const tokenPageLoader = () => import('./pages/TokenPage');
const teamsPageLoader = () => import('./pages/TeamsPage');
const webMcpBootstrapLoader = () => import('./components/WebMCPBootstrap');

const DashboardPage = lazyWithReload('DashboardPage', dashboardPageLoader);
const ChatPage = lazyWithReload('ChatPage', chatPageLoader);
const ConfigPage = lazyWithReload('ConfigPage', configPageLoader);
const ChannelsPage = lazyWithReload('ChannelsPage', channelsPageLoader);
const TasksPage = lazyWithReload('TasksPage', tasksPageLoader);
const StatusPage = lazyWithReload('StatusPage', statusPageLoader);
const SkillsPage = lazyWithReload('SkillsPage', skillsPageLoader);
const TokenPage = lazyWithReload('TokenPage', tokenPageLoader);
const TeamsPage = lazyWithReload('TeamsPage', teamsPageLoader);
const WebMCPBootstrap = lazyWithReload('WebMCPBootstrap', webMcpBootstrapLoader);

registerRoutePreload('/', dashboardPageLoader);
registerRoutePreload('/chat', chatPageLoader);
registerRoutePreload('/config', configPageLoader);
registerRoutePreload('/channels', channelsPageLoader);
registerRoutePreload('/tasks', tasksPageLoader);
registerRoutePreload('/status', statusPageLoader);
registerRoutePreload('/skills', skillsPageLoader);
registerRoutePreload('/tokens', tokenPageLoader);
registerRoutePreload('/teams', teamsPageLoader);

function App() {
  const { t } = useI18n();

  return (
    <ErrorBoundary>
      <ToastProvider>
        <Suspense fallback={null}>
          <WebMCPBootstrap />
        </Suspense>
        <Router>
          <Suspense fallback={<div className="flex items-center justify-center h-full">{t('app.loading')}</div>}>
            <Routes>
              <Route path="/" element={<Layout />}>
                <Route index element={<DashboardPage />} />
                <Route path="chat" element={<ChatPage />} />
                <Route path="config" element={<ConfigPage />} />
                <Route path="channels" element={<ChannelsPage />} />
                <Route path="tasks" element={<TasksPage />} />
                <Route path="status" element={<StatusPage />} />
                <Route path="skills" element={<SkillsPage />} />
                <Route path="tokens" element={<TokenPage />} />
                <Route path="teams" element={<TeamsPage />} />
              </Route>
            </Routes>
          </Suspense>
        </Router>
        <Toast />
      </ToastProvider>
    </ErrorBoundary>
  );
}

export default App;
