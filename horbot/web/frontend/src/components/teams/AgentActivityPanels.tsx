import type { AgentInfo, AgentMemoryStats, AgentSkillInfo } from '../../pages/teams/types';

interface AgentActivityPanelsProps {
  selectedAgent: AgentInfo;
  agentMemoryStats: AgentMemoryStats | null;
  agentSkills: AgentSkillInfo[];
  assetReady: boolean;
  assetLoading: boolean;
  reasoningStyleLabel: string | null;
}

const AgentActivityPanels = ({
  selectedAgent,
  agentMemoryStats,
  agentSkills,
  assetReady,
  assetLoading,
  reasoningStyleLabel,
}: AgentActivityPanelsProps) => (
  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
    <div className="lg:col-span-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-surface-900">日常协作</h3>
          <p className="mt-1 text-sm text-surface-500">先看当前可直接影响聊天与协作表现的运行、技能和记忆状态。</p>
        </div>
      </div>
    </div>
    <div className="bg-white rounded-2xl border border-surface-200 p-6 transition-shadow" data-focus-anchor="agent-runtime">
      <h3 className="text-lg font-semibold text-surface-900">运行摘要</h3>
      {assetReady ? (
        <div className="mt-4 space-y-3">
          <div className="rounded-xl bg-surface-50 p-4">
            <p className="text-xs uppercase tracking-wide text-surface-500">记忆条目</p>
            <p className="mt-1 text-2xl font-bold text-surface-900">{agentMemoryStats?.total_entries ?? '未加载'}</p>
          </div>
          <div className="rounded-xl bg-surface-50 p-4">
            <p className="text-xs uppercase tracking-wide text-surface-500">记忆体积</p>
            <p className="mt-1 text-2xl font-bold text-surface-900">
              {agentMemoryStats ? `${agentMemoryStats.total_size_kb} KB` : '未加载'}
            </p>
          </div>
          <div className="rounded-xl bg-surface-50 p-4">
            <p className="text-xs uppercase tracking-wide text-surface-500">技能数量</p>
            <p className="mt-1 text-2xl font-bold text-surface-900">{agentSkills.length}</p>
          </div>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          {['记忆条目', '记忆体积', '技能数量'].map((label) => (
            <div key={label} className="rounded-xl bg-surface-50 p-4">
              <div className="animate-pulse">
                <div className="h-3 w-20 rounded bg-surface-200" />
                <div className="mt-3 h-8 w-24 rounded bg-surface-200" />
              </div>
              <p className="mt-2 text-xs text-surface-500">
                {assetLoading ? `正在加载 ${label}...` : '等待当前 Agent 运行摘要就绪...'}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>

    <div className="bg-white rounded-2xl border border-surface-200 p-6">
      <h3 className="text-lg font-semibold text-surface-900">技能概览</h3>
      {assetReady ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {agentSkills.length > 0 ? agentSkills.map((skill) => (
            <span
              key={`${skill.source}-${skill.name}`}
              className={`px-3 py-1.5 rounded-full text-xs font-medium ${
                skill.enabled ? 'bg-primary-100 text-primary-700' : 'bg-surface-100 text-surface-500'
              }`}
            >
              {skill.name}
              {skill.always ? ' · always' : ''}
            </span>
          )) : (
            <p className="text-sm text-surface-500">当前 Agent 没有加载到独立技能。</p>
          )}
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          <div className="flex flex-wrap gap-2 animate-pulse">
            {Array.from({ length: 4 }).map((_, index) => (
              <span key={index} className="h-8 w-24 rounded-full bg-surface-200" />
            ))}
          </div>
          <p className="text-xs text-surface-500">
            {assetLoading ? '正在加载当前 Agent 技能...' : '等待当前 Agent 技能概览就绪...'}
          </p>
        </div>
      )}
    </div>

    <div className="bg-white rounded-2xl border border-surface-200 p-6 lg:col-span-2 transition-shadow">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-surface-900">记忆银行画像</h3>
          <p className="mt-1 text-sm text-surface-500">这组设置只影响记忆召回、解释与反思，不直接替代人格文件。</p>
        </div>
        {reasoningStyleLabel && (
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
            {reasoningStyleLabel}
          </span>
        )}
      </div>
      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4">
          <div className="text-xs font-medium uppercase tracking-wide text-surface-500">Mission</div>
          <div className="mt-2 text-sm text-surface-800">
            {selectedAgent.memory_bank_profile?.mission || '未设置。建议说明这个 Agent 在长期记忆里应优先服务什么目标。'}
          </div>
        </div>
        <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4 md:col-span-2">
          <div className="flex items-center justify-between gap-3">
            <div className="text-xs font-medium uppercase tracking-wide text-surface-500">Directives</div>
            <span className="text-xs text-surface-500">{selectedAgent.memory_bank_profile?.directives?.length || 0} 条</span>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {(selectedAgent.memory_bank_profile?.directives || []).length > 0 ? (
              (selectedAgent.memory_bank_profile?.directives || []).map((directive) => (
                <span key={directive} className="rounded-full bg-white px-3 py-1.5 text-xs text-surface-700 ring-1 ring-surface-200">
                  {directive}
                </span>
              ))
            ) : (
              <p className="text-sm text-surface-500">未设置。可补充“优先记住什么”“如何解释历史约束”“何时保守处理”等规则。</p>
            )}
          </div>
        </div>
      </div>
    </div>
  </div>
);

export default AgentActivityPanels;
