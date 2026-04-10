import { useState } from 'react';
import type { ConfigCheckResultData } from '../components/ConfigCheckResult';
import type { GatewayDiagnosticsData } from '../components/GatewayDiagnosticsResult';
import type { EnvironmentDetectionData } from '../components/EnvironmentDetectionResult';
import { diagnosticsService } from '../services';
import type { MemoryData } from '../services/diagnostics';

export type DashboardModal =
  | 'config-check'
  | 'gateway-diagnosis'
  | 'env-detection'
  | 'memory-manager'
  | null;

export const useDashboardDiagnostics = () => {
  const [activeModal, setActiveModal] = useState<DashboardModal>(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [configCheckData, setConfigCheckData] = useState<ConfigCheckResultData | null>(null);
  const [gatewayDiagnosticsData, setGatewayDiagnosticsData] = useState<GatewayDiagnosticsData | null>(null);
  const [environmentData, setEnvironmentData] = useState<EnvironmentDetectionData | null>(null);
  const [memoryData, setMemoryData] = useState<MemoryData | null>(null);

  const loadDiagnosticModal = async <T,>(
    modalId: Exclude<DashboardModal, null>,
    reset: () => void,
    loader: () => Promise<T>,
    applyData: (data: T) => void,
    fallbackMessage: string,
  ) => {
    setActiveModal(modalId);
    setModalLoading(true);
    setModalError(null);
    reset();

    try {
      const data = await loader();
      applyData(data);
    } catch (err) {
      setModalError(err instanceof Error ? err.message : fallbackMessage);
    } finally {
      setModalLoading(false);
    }
  };

  const openSkillDiagnostic = async (skillId: string): Promise<boolean> => {
    switch (skillId) {
      case 'config-check':
        await loadDiagnosticModal(
          'config-check',
          () => setConfigCheckData(null),
          diagnosticsService.validateConfig,
          setConfigCheckData,
          '配置检查失败',
        );
        return true;
      case 'gateway-diagnosis':
        await loadDiagnosticModal(
          'gateway-diagnosis',
          () => setGatewayDiagnosticsData(null),
          diagnosticsService.getGatewayDiagnostics,
          setGatewayDiagnosticsData,
          '网关诊断失败',
        );
        return true;
      case 'env-detection':
        await loadDiagnosticModal(
          'env-detection',
          () => setEnvironmentData(null),
          diagnosticsService.getEnvironment,
          setEnvironmentData,
          '环境检测失败',
        );
        return true;
      case 'memory-manager':
        await loadDiagnosticModal(
          'memory-manager',
          () => setMemoryData(null),
          diagnosticsService.getMemory,
          setMemoryData,
          '获取内存信息失败',
        );
        return true;
      default:
        return false;
    }
  };

  const closeModal = () => {
    setActiveModal(null);
    setModalError(null);
  };

  return {
    activeModal,
    modalLoading,
    modalError,
    configCheckData,
    gatewayDiagnosticsData,
    environmentData,
    memoryData,
    openSkillDiagnostic,
    closeModal,
  };
};
