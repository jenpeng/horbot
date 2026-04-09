
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Suspense } from 'react';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import { ToastProvider } from './contexts/ToastContext';
import Toast from './components/Toast';
import { lazyWithReload } from './utils/lazyWithReload';

const DashboardPage = lazyWithReload('DashboardPage', () => import('./pages/DashboardPage'));
const ChatPage = lazyWithReload('ChatPage', () => import('./pages/ChatPage'));
const ConfigPage = lazyWithReload('ConfigPage', () => import('./pages/ConfigPage'));
const ChannelsPage = lazyWithReload('ChannelsPage', () => import('./pages/ChannelsPage'));
const TasksPage = lazyWithReload('TasksPage', () => import('./pages/TasksPage'));
const StatusPage = lazyWithReload('StatusPage', () => import('./pages/StatusPage'));
const SkillsPage = lazyWithReload('SkillsPage', () => import('./pages/SkillsPage'));
const TokenPage = lazyWithReload('TokenPage', () => import('./pages/TokenPage'));
const TeamsPage = lazyWithReload('TeamsPage', () => import('./pages/TeamsPage'));
const WebMCPBootstrap = lazyWithReload('WebMCPBootstrap', () => import('./components/WebMCPBootstrap'));

function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <Suspense fallback={null}>
          <WebMCPBootstrap />
        </Suspense>
        <Router>
          <Suspense fallback={<div className="flex items-center justify-center h-full">加载中...</div>}>
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
