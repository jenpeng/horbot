import type { AgentInfo, AgentAssetBundle, SummarySectionKey } from '../../pages/teams/types';

interface SummarySectionDef {
  key: SummarySectionKey;
  label: string;
  placeholder: string;
}

interface AgentConfigurationPanelsProps {
  selectedAgent: AgentInfo;
  agentAssets: AgentAssetBundle | null;
  assetReady: boolean;
  assetLoading: boolean;
  assetError: string;
  assetSuccess: string;
  assetSaving: 'soul' | 'user' | null;
  assetDrafts: {
    soul: string;
    user: string;
  };
  summaryDrafts: Record<SummarySectionKey, string>;
  summarySaving: boolean;
  summarySectionDefs: SummarySectionDef[];
  noticeToneClasses: {
    pending: string;
    success: string;
  };
  onSaveSummary: () => void;
  onSummaryDraftChange: (key: SummarySectionKey, value: string) => void;
  onSaveAssetFile: (fileKind: 'soul' | 'user') => void;
  onAssetDraftChange: (fileKind: 'soul' | 'user', value: string) => void;
}

const AgentConfigurationPanels = ({
  selectedAgent,
  agentAssets,
  assetReady,
  assetLoading,
  assetError,
  assetSuccess,
  assetSaving,
  assetDrafts,
  summaryDrafts,
  summarySaving,
  summarySectionDefs,
  noticeToneClasses,
  onSaveSummary,
  onSummaryDraftChange,
  onSaveAssetFile,
  onAssetDraftChange,
}: AgentConfigurationPanelsProps) => (
  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
    <div className="lg:col-span-3 pt-2">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-surface-900">档案与配置</h3>
          <p className="mt-1 text-sm text-surface-500">结构化摘要和人格档案属于低频配置，集中放在后面统一管理。</p>
        </div>
      </div>
    </div>

    <div className="bg-white rounded-2xl border border-surface-200 p-6 lg:col-span-2 transition-shadow" data-focus-anchor="agent-summary">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-surface-900">配置摘要</h3>
          <p className="mt-1 text-sm text-surface-500">这里按分类直接编辑结构化要点。每行一条，保存后会自动写回 `SOUL.md` 和 `USER.md` 对应章节。</p>
        </div>
        {assetReady && (
          <button
            onClick={onSaveSummary}
            disabled={summarySaving}
            data-testid="agent-save-summary"
            className="px-3 py-2 rounded-xl bg-primary-500 text-white hover:bg-primary-600 disabled:opacity-60 transition-colors"
          >
            {summarySaving ? '保存中...' : '保存摘要'}
          </button>
        )}
      </div>
      {assetReady ? (
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          {summarySectionDefs.map((section) => (
            <div key={section.key} className="rounded-2xl border border-surface-200 bg-surface-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-semibold text-surface-900">{section.label}</div>
                <span className="text-xs text-surface-500">
                  {(summaryDrafts[section.key] || '')
                    .split('\n')
                    .map((item) => item.trim())
                    .filter(Boolean).length} 条
                </span>
              </div>
              <textarea
                value={summaryDrafts[section.key]}
                onChange={(e) => onSummaryDraftChange(section.key, e.target.value)}
                data-testid={`agent-summary-${section.key}`}
                className="mt-3 h-32 w-full rounded-xl border border-surface-300 bg-white px-3 py-3 text-sm text-surface-800 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                placeholder={section.placeholder}
              />
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="rounded-2xl border border-surface-200 bg-surface-50 p-4">
              <div className="animate-pulse">
                <div className="h-4 w-24 rounded bg-surface-200" />
                <div className="mt-3 flex flex-wrap gap-2">
                  <div className="h-6 w-20 rounded-full bg-surface-200" />
                  <div className="h-6 w-28 rounded-full bg-surface-200" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>

    <div className="bg-white rounded-2xl border border-surface-200 p-6 lg:col-span-2 transition-shadow" data-focus-anchor="agent-files">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-surface-900">Bootstrap 文件</h3>
          <p className="text-sm text-surface-500 mt-1">这里直接管理当前 Agent 的独立人格与用户档案文件。若文件仍处于初始状态，系统会按画像和权限档位自动生成待确认模板。</p>
        </div>
        {assetLoading && <span className="text-sm text-surface-500">加载中...</span>}
      </div>
      {assetError && (
        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
          {assetError}
        </div>
      )}
      {assetSuccess && (
        <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {assetSuccess}
        </div>
      )}
      {assetReady ? (
        <div className="mt-4">
          <div className={`rounded-2xl border px-4 py-3 text-sm ${
            selectedAgent.bootstrap_setup_pending
              ? noticeToneClasses.pending
              : noticeToneClasses.success
          }`}>
            {selectedAgent.bootstrap_setup_pending
              ? '当前仍处于首次引导阶段：建议继续通过私聊完善信息，或在这里手动补全并移除待配置标记。'
              : '当前档案已完成初始化，不会再自动进入首次引导。'}
          </div>
          <div className="mt-4 grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4 transition-shadow" data-focus-anchor="agent-file-soul">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h4 className="font-semibold text-surface-900">SOUL.md</h4>
                  <p className="text-xs text-surface-500 break-all">{agentAssets?.files?.soul?.path || '未加载'}</p>
                </div>
                <button
                  onClick={() => onSaveAssetFile('soul')}
                  data-testid="agent-save-soul"
                  disabled={assetSaving === 'soul'}
                  className="px-3 py-2 bg-primary-500 text-white rounded-xl hover:bg-primary-600 disabled:opacity-60 transition-colors"
                >
                  {assetSaving === 'soul' ? '保存中...' : '保存 SOUL'}
                </button>
              </div>
              <textarea
                data-testid="agent-soul-editor"
                value={assetDrafts.soul}
                onChange={(e) => onAssetDraftChange('soul', e.target.value)}
                className="mt-4 h-72 w-full rounded-xl border border-surface-300 bg-white px-3 py-3 text-sm text-surface-800 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                placeholder="为这个 Agent 编写独立的 SOUL.md..."
              />
            </div>

            <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4 transition-shadow" data-focus-anchor="agent-file-user">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h4 className="font-semibold text-surface-900">USER.md</h4>
                  <p className="text-xs text-surface-500 break-all">{agentAssets?.files?.user?.path || '未加载'}</p>
                </div>
                <button
                  onClick={() => onSaveAssetFile('user')}
                  data-testid="agent-save-user"
                  disabled={assetSaving === 'user'}
                  className="px-3 py-2 bg-surface-900 text-white rounded-xl hover:bg-surface-800 disabled:opacity-60 transition-colors"
                >
                  {assetSaving === 'user' ? '保存中...' : '保存 USER'}
                </button>
              </div>
              <textarea
                data-testid="agent-user-editor"
                value={assetDrafts.user}
                onChange={(e) => onAssetDraftChange('user', e.target.value)}
                className="mt-4 h-72 w-full rounded-xl border border-surface-300 bg-white px-3 py-3 text-sm text-surface-800 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                placeholder="为这个 Agent 编写独立的 USER.md..."
              />
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-4 grid grid-cols-1 xl:grid-cols-2 gap-4">
          {['SOUL.md', 'USER.md'].map((label) => (
            <div key={label} className="rounded-2xl border border-surface-200 bg-surface-50 p-4">
              <div className="animate-pulse">
                <div className="flex items-center justify-between gap-3">
                  <div className="space-y-2">
                    <div className="h-4 w-24 rounded bg-surface-200" />
                    <div className="h-3 w-48 rounded bg-surface-200" />
                  </div>
                  <div className="h-9 w-24 rounded-xl bg-surface-200" />
                </div>
                <div className="mt-4 h-72 rounded-xl bg-white/80 border border-surface-200" />
              </div>
              <p className="mt-3 text-xs text-surface-500">
                {assetLoading ? `正在加载 ${label}...` : '等待当前 Agent 资产就绪...'}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  </div>
);

export default AgentConfigurationPanels;
