import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  DashboardActivityCard,
  DashboardAlerts,
  DashboardChannelsCard,
  DashboardDiagnosticsModals,
  DashboardErrorState,
  DashboardHero,
  DashboardLoadingState,
  DashboardSkillGrid,
  DashboardSystemInfoCard,
  DashboardSystemStatusCard,
} from '../components/dashboard';
import { useDashboardDiagnostics, useDashboardSummary } from '../hooks';

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const {
    isLoading,
    error,
    refreshSummary,
    systemStatus,
    channelCounts,
    recentActivities,
    dashboardAlerts,
  } = useDashboardSummary();
  const {
    activeModal,
    modalLoading,
    modalError,
    configCheckData,
    gatewayDiagnosticsData,
    environmentData,
    memoryData,
    openSkillDiagnostic,
    closeModal,
  } = useDashboardDiagnostics();

  const [copiedVersion, setCopiedVersion] = useState(false);

  const handleSkillClick = async (skillId: string) => {
    const handledByDiagnostics = await openSkillDiagnostic(skillId);
    if (handledByDiagnostics) {
      return;
    }

    switch (skillId) {
      case 'system-info':
        navigate('/status');
        return;
      case 'log-viewer':
        navigate('/status', { state: { activeTab: 'logs' } });
        return;
      case 'quick-settings':
        navigate('/config');
        return;
      default:
        console.log('Unknown skill:', skillId);
    }
  };

  const handleCopyVersion = async () => {
    if (!systemStatus?.version) {
      return;
    }

    try {
      await navigator.clipboard.writeText(systemStatus.version);
      setCopiedVersion(true);
      window.setTimeout(() => setCopiedVersion(false), 2000);
    } catch (err) {
      console.error('Failed to copy version:', err);
    }
  };

  if (isLoading) {
    return <DashboardLoadingState />;
  }

  if (error) {
    return <DashboardErrorState error={error} onRetry={refreshSummary} />;
  }

  return (
    <div className="h-full overflow-y-auto bg-gradient-to-br from-surface-50 via-surface-100 to-surface-50">
      <div className="max-w-7xl mx-auto p-8 space-y-6">
        <DashboardHero systemStatus={systemStatus} />
        <DashboardAlerts alerts={dashboardAlerts} />
        <DashboardSkillGrid onSkillClick={(skillId) => { void handleSkillClick(skillId); }} />

        <div className="grid grid-cols-1 items-start gap-6 mt-2 xl:grid-cols-3">
          <DashboardSystemStatusCard systemStatus={systemStatus} />
          <DashboardActivityCard activities={recentActivities} />
        </div>

        <div className="grid grid-cols-1 items-start gap-6 mt-6 lg:grid-cols-2 xl:grid-cols-2">
          <DashboardChannelsCard counts={channelCounts} />
          <DashboardSystemInfoCard
            copiedVersion={copiedVersion}
            onCopyVersion={() => { void handleCopyVersion(); }}
            systemStatus={systemStatus}
          />
        </div>
      </div>

      <DashboardDiagnosticsModals
        activeModal={activeModal}
        modalLoading={modalLoading}
        modalError={modalError}
        configCheckData={configCheckData}
        gatewayDiagnosticsData={gatewayDiagnosticsData}
        environmentData={environmentData}
        memoryData={memoryData}
        onClose={closeModal}
      />
    </div>
  );
};

export default DashboardPage;
