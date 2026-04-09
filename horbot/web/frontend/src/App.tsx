
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import { ToastProvider } from './contexts/ToastContext';
import Toast from './components/Toast';

const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const ChatPage = lazy(() => import('./pages/ChatPage'));
const ConfigPage = lazy(() => import('./pages/ConfigPage'));
const ChannelsPage = lazy(() => import('./pages/ChannelsPage'));
const TasksPage = lazy(() => import('./pages/TasksPage'));
const StatusPage = lazy(() => import('./pages/StatusPage'));
const SkillsPage = lazy(() => import('./pages/SkillsPage'));
const TokenPage = lazy(() => import('./pages/TokenPage'));
const TeamsPage = lazy(() => import('./pages/TeamsPage'));
const WebMCPBootstrap = lazy(() => import('./components/WebMCPBootstrap'));

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
