import { Suspense } from 'react';
import DiagnosticModal from '../DiagnosticModal';
import type { ConfigCheckResultData } from '../ConfigCheckResult';
import type { GatewayDiagnosticsData } from '../GatewayDiagnosticsResult';
import type { EnvironmentDetectionData } from '../EnvironmentDetectionResult';
import { lazyWithReload } from '../../utils/lazyWithReload';
import type { DashboardModal } from '../../hooks/useDashboardDiagnostics';
import type { MemoryData } from '../../services/diagnostics';
import { useI18n } from '../../contexts/I18nContext';
import DashboardMemoryPanel from './DashboardMemoryPanel';

const ConfigCheckResult = lazyWithReload('DashboardConfigCheckResult', () => import('../ConfigCheckResult'));
const GatewayDiagnosticsResult = lazyWithReload('DashboardGatewayDiagnosticsResult', () => import('../GatewayDiagnosticsResult'));
const EnvironmentDetectionResult = lazyWithReload('DashboardEnvironmentDetectionResult', () => import('../EnvironmentDetectionResult'));

interface DashboardDiagnosticsModalsProps {
  activeModal: DashboardModal;
  modalLoading: boolean;
  modalError: string | null;
  configCheckData: ConfigCheckResultData | null;
  gatewayDiagnosticsData: GatewayDiagnosticsData | null;
  environmentData: EnvironmentDetectionData | null;
  memoryData: MemoryData | null;
  onClose: () => void;
}

const DashboardDiagnosticsModals = ({
  activeModal,
  modalLoading,
  modalError,
  configCheckData,
  gatewayDiagnosticsData,
  environmentData,
  memoryData,
  onClose,
}: DashboardDiagnosticsModalsProps) => {
  const { t } = useI18n();
  const modalBodyFallback = (
    <div className="p-6 text-sm text-surface-500">{t('dashboard.diagnostics.loading')}</div>
  );

  return (
    <>
    <DiagnosticModal
      title={t('dashboard.diagnostics.configCheck')}
      isOpen={activeModal === 'config-check'}
      onClose={onClose}
      isLoading={modalLoading}
      error={modalError}
      size="xl"
    >
      {configCheckData && (
        <Suspense fallback={modalBodyFallback}>
          <ConfigCheckResult data={configCheckData} />
        </Suspense>
      )}
    </DiagnosticModal>

    <DiagnosticModal
      title={t('dashboard.diagnostics.gateway')}
      isOpen={activeModal === 'gateway-diagnosis'}
      onClose={onClose}
      isLoading={modalLoading}
      error={modalError}
      size="xl"
    >
      {gatewayDiagnosticsData && (
        <Suspense fallback={modalBodyFallback}>
          <GatewayDiagnosticsResult data={gatewayDiagnosticsData} />
        </Suspense>
      )}
    </DiagnosticModal>

    <DiagnosticModal
      title={t('dashboard.diagnostics.environment')}
      isOpen={activeModal === 'env-detection'}
      onClose={onClose}
      isLoading={modalLoading}
      error={modalError}
      size="full"
    >
      {environmentData && (
        <Suspense fallback={modalBodyFallback}>
          <EnvironmentDetectionResult data={environmentData} />
        </Suspense>
      )}
    </DiagnosticModal>

    <DiagnosticModal
      title={t('dashboard.diagnostics.memory')}
      isOpen={activeModal === 'memory-manager'}
      onClose={onClose}
      isLoading={modalLoading}
      error={modalError}
      size="lg"
    >
      {memoryData && <DashboardMemoryPanel memoryData={memoryData} />}
    </DiagnosticModal>
  </>
  );
};

export default DashboardDiagnosticsModals;
