import CollaborationFlow from '../CollaborationFlow';
import type { AgentInfo, TeamInfo, TeamMemberProfile } from '../../pages/teams/types';

interface TeamDetailViewProps {
  selectedTeam: TeamInfo;
  selectedTeamAgents: AgentInfo[];
  selectedTeamLead?: AgentInfo;
  selectedTeamCapabilitiesCount: number;
  getBadgeClassName: (tone: string, size?: 'sm' | 'md') => string;
  getTeamMemberProfile: (team: TeamInfo | null, agentId: string) => TeamMemberProfile;
  getTeamRoleLabel: (role?: string) => string;
  getTeamPriorityLabel: (priority?: number) => string;
  onEditTeam: () => void;
  onSelectAgent: (agentId: string) => void;
  onEditAgent: (agent: AgentInfo) => void;
}

const TeamDetailView = ({
  selectedTeam,
  selectedTeamAgents,
  selectedTeamLead,
  selectedTeamCapabilitiesCount,
  getBadgeClassName,
  getTeamMemberProfile,
  getTeamRoleLabel,
  getTeamPriorityLabel,
  onEditTeam,
  onSelectAgent,
  onEditAgent,
}: TeamDetailViewProps) => (
  <div data-testid="team-detail-view" data-team-id={selectedTeam.id}>
    <div className="mb-6 transition-shadow" data-focus-anchor="team-overview">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-surface-900">{selectedTeam.name}</h2>
          {selectedTeam.description && (
            <p className="text-surface-600 mt-1">{selectedTeam.description}</p>
          )}
          <p className="mt-2 text-xs text-surface-500">
            工作空间：{selectedTeam.effective_workspace || selectedTeam.workspace || '默认团队目录'}
          </p>
        </div>
        <button
          onClick={onEditTeam}
          className="px-3 py-2 bg-white border border-surface-200 text-surface-700 rounded-xl hover:bg-surface-50 transition-colors flex items-center gap-2"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
          </svg>
          编辑团队
        </button>
      </div>
      <div className="mt-4 flex flex-wrap gap-2 text-xs text-surface-500">
        <span className={getBadgeClassName('neutral')}>{selectedTeamAgents.length} 个成员</span>
        <span className={getBadgeClassName(selectedTeamLead ? 'primary' : 'neutral')}>
          {selectedTeamLead ? `负责人 ${selectedTeamLead.name}` : '未指定负责人'}
        </span>
        <span className={getBadgeClassName('neutral')}>{selectedTeamCapabilitiesCount} 类能力</span>
        <span className={getBadgeClassName('neutral')}>{selectedTeam.workspace || selectedTeam.effective_workspace ? '自定义工作区' : '默认工作区'}</span>
      </div>
    </div>

    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="lg:col-span-2">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-surface-900">日常协作</h3>
            <p className="mt-1 text-sm text-surface-500">优先查看成员组成和当前团队接力流程。</p>
          </div>
        </div>
      </div>
      <div className="bg-white rounded-2xl border border-surface-200 p-6 transition-shadow" data-focus-anchor="team-members">
        <h3 className="text-lg font-semibold text-surface-900 mb-4">团队成员</h3>
        <div className="space-y-3">
          {selectedTeamAgents.map((agent) => {
            const profile = getTeamMemberProfile(selectedTeam, agent.id);
            const roleLabel = getTeamRoleLabel(profile.role);
            const priorityLabel = getTeamPriorityLabel(profile.priority);
            return (
              <div
                key={agent.id}
                className="group flex items-center gap-3 p-3 rounded-xl bg-surface-50 hover:bg-surface-100 transition-colors"
              >
                <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-surface-200 text-surface-600">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-surface-900">{agent.name}</p>
                    {profile.isLead && (
                      <span className={getBadgeClassName('primary', 'sm')}>负责人</span>
                    )}
                    {profile.role && profile.role !== 'member' && (
                      <span className={getBadgeClassName('neutral', 'sm')}>{roleLabel}</span>
                    )}
                  </div>
                  <p className="text-sm text-surface-500">{agent.description || '暂无描述'}</p>
                  {profile.responsibility && (
                    <p className="mt-1 text-xs text-surface-500">负责内容：{profile.responsibility}</p>
                  )}
                  <p className="mt-1 text-[11px] text-surface-400">接力顺序：{priorityLabel}</p>
                </div>
                <div className="flex items-center gap-2">
                  <div className="text-right">
                    <p className="text-xs text-surface-400">{agent.provider}</p>
                    <p className="text-xs text-surface-500">{agent.model}</p>
                    <p className="text-[11px] text-surface-400 truncate max-w-[180px]" title={agent.effective_workspace}>
                      {agent.effective_workspace || agent.workspace || '默认工作区'}
                    </p>
                  </div>
                  <button
                    onClick={() => onSelectAgent(agent.id)}
                    data-testid="team-member-open-agent"
                    data-agent-id={agent.id}
                    className="p-1.5 opacity-0 group-hover:opacity-100 hover:bg-white rounded transition-all"
                    title="查看 Agent 资产"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12H9m12 0c0 1.657-4.03 6-9 6s-9-4.343-9-6 4.03-6 9-6 9 4.343 9 6z" />
                    </svg>
                  </button>
                  <button
                    onClick={() => onEditAgent(agent)}
                    className="p-1.5 opacity-0 group-hover:opacity-100 hover:bg-white rounded transition-all"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-surface-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                    </svg>
                  </button>
                </div>
              </div>
            );
          })}
          {selectedTeamAgents.length === 0 && (
            <div className="text-center py-8 text-surface-500">
              该团队暂无成员
            </div>
          )}
        </div>
      </div>

      <div className="lg:col-span-2 bg-white rounded-2xl border border-surface-200 p-6 transition-shadow" data-focus-anchor="team-collaboration">
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-surface-900">团队协作流</h3>
          <p className="mt-1 text-sm text-surface-500">这里查看群聊接力、分工协作和当前执行流。</p>
        </div>
        <CollaborationFlow teamId={selectedTeam.id} />
      </div>

      <div className="lg:col-span-2 pt-2">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-surface-900">资产与拓扑</h3>
            <p className="mt-1 text-sm text-surface-500">能力分布和团队工作区属于次级信息，放在协作视图之后。</p>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-surface-200 p-6">
        <h3 className="text-lg font-semibold text-surface-900 mb-4">能力分布</h3>
        <div className="space-y-3">
          {Array.from(new Set(selectedTeamAgents.flatMap((agent) => agent.capabilities))).map((capability) => {
            const agentsWithCapability = selectedTeamAgents.filter((agent) => agent.capabilities.includes(capability));
            return (
              <div key={capability} className="p-3 rounded-xl bg-surface-50">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-surface-900">{capability}</span>
                  <span className="text-xs text-surface-500">{agentsWithCapability.length} 个 Agent</span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {agentsWithCapability.map((agent) => (
                    <span
                      key={agent.id}
                      className="text-xs bg-white px-2 py-1 rounded-lg border border-surface-200 text-surface-600"
                    >
                      {agent.name}
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
          {selectedTeamAgents.flatMap((agent) => agent.capabilities).length === 0 && (
            <div className="text-center py-8 text-surface-500">
              暂无能力信息
            </div>
          )}
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-surface-200 p-6 lg:col-span-2 transition-shadow" data-focus-anchor="team-workspace">
        <h3 className="text-lg font-semibold text-surface-900 mb-4">团队工作空间</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-surface-50 text-center">
            <div className="w-10 h-10 mx-auto mb-2 rounded-xl bg-primary-100 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
              </svg>
            </div>
            <p className="text-sm font-medium text-surface-900">共享工作空间</p>
            <p className="text-xs text-surface-500 mt-1">团队共享文件</p>
          </div>
          <div className="p-4 rounded-xl bg-surface-50 text-center">
            <div className="w-10 h-10 mx-auto mb-2 rounded-xl bg-accent-purple/10 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-accent-purple" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <p className="text-sm font-medium text-surface-900">共享记忆</p>
            <p className="text-xs text-surface-500 mt-1">团队上下文</p>
          </div>
          <div className="p-4 rounded-xl bg-surface-50 text-center">
            <div className="w-10 h-10 mx-auto mb-2 rounded-xl bg-accent-emerald/10 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-accent-emerald" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <p className="text-sm font-medium text-surface-900">消息总线</p>
            <p className="text-xs text-surface-500 mt-1">Agent 通信</p>
          </div>
          <div className="p-4 rounded-xl bg-surface-50 text-center">
            <div className="w-10 h-10 mx-auto mb-2 rounded-xl bg-accent-orange/10 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-accent-orange" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
              </svg>
            </div>
            <p className="text-sm font-medium text-surface-900">任务委派</p>
            <p className="text-xs text-surface-500 mt-1">工作分配</p>
          </div>
        </div>
      </div>
    </div>
  </div>
);

export default TeamDetailView;
