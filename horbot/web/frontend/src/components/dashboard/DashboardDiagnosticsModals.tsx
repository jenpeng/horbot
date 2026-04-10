import { Suspense } from 'react';
import DiagnosticModal from '../DiagnosticModal';
import ConfirmDialog from '../ConfirmDialog';
import type { ConfigCheckResultData } from '../ConfigCheckResult';
import type { GatewayDiagnosticsData } from '../GatewayDiagnosticsResult';
import type { EnvironmentDetectionData } from '../EnvironmentDetectionResult';
import { lazyWithReload } from '../../utils/lazyWithReload';
import type { DashboardModal } from '../../hooks/useDashboardDiagnostics';
import type { FixResult, MemoryData } from '../../services/diagnostics';
import DashboardFixResult from './DashboardFixResult';
import DashboardMemoryPanel from './DashboardMemoryPanel';

const ConfigCheckResult = lazyWithReload('DashboardConfigCheckResult', () => import('../ConfigCheckResult'));
const GatewayDiagnosticsResult = lazyWithReload('DashboardGatewayDiagnosticsResult', () => import('../GatewayDiagnosticsResult'));
const EnvironmentDetectionResult = lazyWithReload('DashboardEnvironmentDetectionResult', () => import('../EnvironmentDetectionResult'));

const modalBodyFallback = (
  <div className="p-6 text-sm text-surface-500">加载诊断详情中...</div>
);

interface DashboardDiagnosticsModalsProps {
  activeModal: DashboardModal;
  modalLoading: boolean;
  modalError: string | null;
  configCheckData: ConfigCheckResultData | null;
  gatewayDiagnosticsData: GatewayDiagnosticsData | null;
  environmentData: EnvironmentDetectionData | null;
  memoryData: MemoryData | null;
  showFixConfirm: boolean;
  fixLoading: boolean;
  fixResult: FixResult | null;
  onClose: () => void;
  onConfirmFix: () => void;
  onCancelFix: () => void;
}

const DashboardDiagnosticsModals = ({
  activeModal,
  modalLoading,
  modalError,
  configCheckData,
  gatewayDiagnosticsData,
  environmentData,
  memoryData,
  showFixConfirm,
  fixLoading,
  fixResult,
  onClose,
  onConfirmFix,
  onCancelFix,
}: DashboardDiagnosticsModalsProps) => (
  <>
    <DiagnosticModal
      title="配置检查"
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
      title="网关诊断"
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
      title="环境检测"
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
      title="内存管理"
      isOpen={activeModal === 'memory-manager'}
      onClose={onClose}
      isLoading={modalLoading}
      error={modalError}
      size="lg"
    >
      {memoryData && <DashboardMemoryPanel memoryData={memoryData} />}
    </DiagnosticModal>

    <ConfirmDialog
      isOpen={showFixConfirm}
      title="一键修复"
      message="确定要执行一键修复吗？此操作将自动修复检测到的常见问题。"
      confirmText="执行修复"
      cancelText="取消"
      onConfirm={onConfirmFix}
      onCancel={onCancelFix}
      variant="warning"
      isLoading={fixLoading}
    />

    <DiagnosticModal
      title="修复结果"
      isOpen={activeModal === 'fix-result'}
      onClose={onClose}
      size="lg"
    >
      {fixResult && <DashboardFixResult fixResult={fixResult} />}
    </DiagnosticModal>
  </>
);

export default DashboardDiagnosticsModals;
