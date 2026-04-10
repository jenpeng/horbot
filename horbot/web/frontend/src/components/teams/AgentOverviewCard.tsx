import type { AgentInfo } from '../../pages/teams/types';

interface AgentOverviewCardProps {
  selectedAgent: AgentInfo;
  selectedAgentStatusMeta: {
    tone: string;
    detailLabel: string;
  };
  selectedAgentProfileLabel: string | null;
  selectedAgentProfileSummary: string | null;
  selectedAgentPermissionLabel: string | null;
  selectedAgentPermissionSummary: string | null;
  memoryReasoningStyleLabel: string | null;
  workspacePath: string;
  getBadgeClassName: (tone: string, size?: 'sm' | 'md') => string;
  getNoticeClassName: (tone: 'warning' | 'pending' | 'success') => string;
  onEditAgent: () => void;
  onOpenChat: () => void;
}

const AgentOverviewCard = ({
  selectedAgent,
  selectedAgentStatusMeta,
  selectedAgentProfileLabel,
  selectedAgentProfileSummary,
  selectedAgentPermissionLabel,
  selectedAgentPermissionSummary,
  memoryReasoningStyleLabel,
  workspacePath,
  getBadgeClassName,
  getNoticeClassName,
  onEditAgent,
  onOpenChat,
}: AgentOverviewCardProps) => (
  <div className="bg-white rounded-2xl border border-surface-200 p-6 transition-shadow" data-focus-anchor="agent-overview">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <div className="flex items-center gap-2">
          <h2 className="text-2xl font-bold text-surface-900">{selectedAgent.name}</h2>
          <span className={getBadgeClassName(selectedAgentStatusMeta.tone)}>
            {selectedAgentStatusMeta.detailLabel}
          </span>
        </div>
        <p className="text-surface-600 mt-1">{selectedAgent.description || '暂无描述'}</p>
        <div className="mt-3 flex flex-wrap gap-2 text-xs text-surface-500">
          {selectedAgent.profile && (
            <span className={getBadgeClassName('neutral')}>
              {selectedAgentProfileLabel || selectedAgent.profile}
            </span>
          )}
          {(selectedAgent.permission_profile || selectedAgent.tool_permission_profile) && (
            <span className={getBadgeClassName('slate')}>
              {selectedAgentPermissionLabel || selectedAgent.permission_profile || selectedAgent.tool_permission_profile}
            </span>
          )}
          <span className={getBadgeClassName('neutral')}>{selectedAgent.provider || '未选择 provider'}</span>
          <span className={getBadgeClassName('neutral')}>{selectedAgent.model || '未选择模型'}</span>
          <span className={getBadgeClassName('neutral')}>{selectedAgent.teams.length} 个团队</span>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onEditAgent}
          className="px-3 py-2 bg-white border border-surface-200 text-surface-700 rounded-xl hover:bg-surface-50 transition-colors"
        >
          编辑 Agent
        </button>
        <button
          onClick={onOpenChat}
          className="px-3 py-2 bg-primary-500 text-white rounded-xl hover:bg-primary-600 transition-colors"
        >
          打开单聊
        </button>
      </div>
    </div>

    {selectedAgent.setup_required && (
      <div className={`mt-4 ${getNoticeClassName('warning')}`}>
        <div className="font-semibold text-surface-900">这个 Agent 还没有完成首次配置。</div>
        <div className="mt-1">
          先在这里为它选择 provider 和 model，然后进入私聊，用第一轮对话引导它完善职责、风格和协作边界。
        </div>
      </div>
    )}
    {!selectedAgent.setup_required && selectedAgent.bootstrap_setup_pending && (
      <div className={`mt-4 ${getNoticeClassName('pending')}`}>
        <div className="font-semibold">这个 Agent 已具备模型能力，但首次私聊引导还没完全落盘。</div>
        <div className="mt-1">
          建议继续单聊，直到它把 `SOUL.md` 与 `USER.md` 写成正式版本并移除待配置标记。
        </div>
      </div>
    )}
    {!selectedAgent.setup_required && !selectedAgent.bootstrap_setup_pending && (
      <div className={`mt-4 ${getNoticeClassName('success')}`}>
        <div className="font-semibold">这个 Agent 已完成个性化配置。</div>
        <div className="mt-1">
          后续可以继续通过私聊或直接编辑 `SOUL.md` / `USER.md` 逐步微调，不再强制进入首次引导流程。
        </div>
      </div>
    )}

    <div className="mt-4 rounded-2xl bg-surface-50 px-4 py-3 text-sm text-surface-600">
      {selectedAgent.profile && (
        <div className="mb-2">
          <span className="font-semibold text-surface-900">协作画像：</span>
          <span>{selectedAgentProfileSummary || selectedAgent.profile}</span>
        </div>
      )}
      {(selectedAgent.permission_profile || selectedAgent.tool_permission_profile) && (
        <div className="mb-2">
          <span className="font-semibold text-surface-900">权限档位：</span>
          <span>
            {selectedAgentPermissionSummary || selectedAgent.permission_profile || selectedAgent.tool_permission_profile}
            {selectedAgent.permission_profile ? '' : '（继承全局）'}
          </span>
        </div>
      )}
      <div className="mb-2">
        <span className="font-semibold text-surface-900">配置状态：</span>
        <span>
          {selectedAgent.setup_required
            ? '缺少 provider / model'
            : selectedAgent.bootstrap_setup_pending
              ? '模型已就绪，等待首次私聊引导落盘'
              : '已完成个性化配置'}
        </span>
      </div>
      {(selectedAgent.memory_bank_profile?.mission
        || selectedAgent.memory_bank_profile?.directives?.length
        || selectedAgent.memory_bank_profile?.reasoning_style) && (
        <div className="mb-2">
          <span className="font-semibold text-surface-900">记忆银行画像：</span>
          <span>
            {selectedAgent.memory_bank_profile?.mission || '未设置使命'}
            {memoryReasoningStyleLabel ? ` · ${memoryReasoningStyleLabel}` : ''}
          </span>
        </div>
      )}
      <div>
        <span className="font-semibold text-surface-900">实际工作区：</span>
        <span className="break-all">{workspacePath}</span>
      </div>
      <div className="mt-2">
        <span className="font-semibold text-surface-900">系统提示：</span>
        <span>{selectedAgent.system_prompt ? '已配置实例级系统提示词' : '未配置实例级系统提示词'}</span>
      </div>
    </div>
  </div>
);

export default AgentOverviewCard;
