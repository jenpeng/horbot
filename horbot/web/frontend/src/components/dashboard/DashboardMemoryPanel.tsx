import type { MemoryData } from '../../services/diagnostics';
import { useI18n } from '../../contexts/I18nContext';

interface DashboardMemoryPanelProps {
  memoryData: MemoryData;
}

const DashboardMemoryPanel = ({ memoryData }: DashboardMemoryPanelProps) => {
  const { intlLocale, t } = useI18n();

  return (
    <div className="space-y-4">
    <div className="grid grid-cols-2 gap-4">
      <div className="bg-surface-50 rounded-xl p-4 border border-surface-200">
        <p className="text-sm text-surface-600">{t('dashboard.memory.totalEntries')}</p>
        <p className="text-2xl font-bold text-surface-900">{memoryData.total_entries}</p>
      </div>
      <div className="bg-surface-50 rounded-xl p-4 border border-surface-200">
        <p className="text-sm text-surface-600">{t('dashboard.memory.totalSize')}</p>
        <p className="text-2xl font-bold text-surface-900">{memoryData.total_size_kb.toFixed(2)} KB</p>
      </div>
    </div>
    {memoryData.oldest_entry && memoryData.newest_entry && (
      <div className="bg-surface-50 rounded-xl p-4 border border-surface-200">
        <h4 className="text-sm font-semibold text-surface-700 mb-3">{t('dashboard.memory.timeRange')}</h4>
        <div className="flex justify-between text-sm">
          <span className="text-surface-600">{t('dashboard.memory.oldest')}:</span>
          <span className="text-surface-800">{new Date(memoryData.oldest_entry).toLocaleString(intlLocale)}</span>
        </div>
        <div className="flex justify-between text-sm mt-2">
          <span className="text-surface-600">{t('dashboard.memory.newest')}:</span>
          <span className="text-surface-800">{new Date(memoryData.newest_entry).toLocaleString(intlLocale)}</span>
        </div>
      </div>
    )}
    {memoryData.details && (
      <div className="bg-surface-50 rounded-xl p-4 border border-surface-200">
        <h4 className="text-sm font-semibold text-surface-700 mb-3">{t('dashboard.memory.details')}</h4>
        <pre className="text-xs text-surface-600 overflow-auto max-h-40">
          {JSON.stringify(memoryData.details, null, 2)}
        </pre>
      </div>
    )}
  </div>
  );
};

export default DashboardMemoryPanel;
