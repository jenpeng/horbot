import type { AgentInfo, TeamInfo } from '../../pages/teams/types';

interface AgentStatusMeta {
  tone: string;
  shortLabel: string;
}

interface TeamsSidebarProps {
  teams: TeamInfo[];
  agents: AgentInfo[];
  selectedTeamId: string | null;
  selectedAgentId: string | null;
  onCreateTeam: () => void;
  onCreateAgent: () => void;
  onSelectTeam: (team: TeamInfo) => void;
  onEditTeam: (team: TeamInfo) => void;
  onDeleteTeam: (teamId: string) => void;
  onSelectAgent: (agentId: string) => void;
  onEditAgent: (agent: AgentInfo) => void;
  onDeleteAgent: (agentId: string) => void;
  getBadgeClassName: (tone: string, size?: 'sm' | 'md') => string;
  getAgentProfileLabel: (profileId?: string) => string | null;
  getAgentPermissionLabel: (permissionId?: string) => string | null;
  getAgentStatusMeta: (agent: AgentInfo) => AgentStatusMeta;
}

const TeamsSidebar = ({
  teams,
  agents,
  selectedTeamId,
  selectedAgentId,
  onCreateTeam,
  onCreateAgent,
  onSelectTeam,
  onEditTeam,
  onDeleteTeam,
  onSelectAgent,
  onEditAgent,
  onDeleteAgent,
  getBadgeClassName,
  getAgentProfileLabel,
  getAgentPermissionLabel,
  getAgentStatusMeta,
}: TeamsSidebarProps) => (
  <div className="w-64 border-r border-surface-200 bg-white overflow-y-auto">
    <div className="p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-medium text-surface-500 uppercase tracking-wider">
          团队列表
        </h2>
        <button
          onClick={onCreateTeam}
          className="p-1 hover:bg-surface-100 rounded"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>
      {teams.length === 0 ? (
        <div className="text-sm text-surface-500 text-center py-8">
          暂无团队配置
        </div>
      ) : (
        <div className="space-y-2">
          {teams.map((team) => (
            <div
              key={team.id}
              className={`group relative p-3 rounded-xl transition-all ${
                selectedTeamId === team.id
                  ? 'bg-primary-50 border border-primary-200'
                  : 'hover:bg-surface-50 border border-transparent'
              }`}
            >
              <button
                onClick={() => onSelectTeam(team)}
                data-testid="team-list-select"
                data-team-id={team.id}
                className="w-full text-left flex items-center gap-3"
              >
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                  selectedTeamId === team.id
                    ? 'bg-primary-500 text-white'
                    : 'bg-surface-100 text-surface-600'
                }`}>
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-surface-900 truncate">{team.name}</p>
                  <p className="text-xs text-surface-500">{team.members.length} 成员</p>
                </div>
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onEditTeam(team); }}
                className="absolute right-8 top-1/2 -translate-y-1/2 p-1 opacity-0 group-hover:opacity-100 hover:bg-surface-100 rounded transition-all"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-surface-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onDeleteTeam(team.id); }}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 opacity-0 group-hover:opacity-100 hover:bg-red-100 rounded transition-all"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>

    <div className="p-4 border-t border-surface-100">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-medium text-surface-500 uppercase tracking-wider">
          所有 Agent
        </h2>
        <button
          onClick={onCreateAgent}
          className="p-1 hover:bg-surface-100 rounded"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>
      <div className="space-y-2">
        {agents.map((agent) => {
          const statusMeta = getAgentStatusMeta(agent);
          const profileLabel = getAgentProfileLabel(agent.profile);
          const permissionLabel = getAgentPermissionLabel(agent.permission_profile || agent.tool_permission_profile);
          return (
            <div
              key={agent.id}
              data-testid="agent-list-item"
              data-agent-id={agent.id}
              className={`group relative flex items-center gap-3 p-2 rounded-lg transition-colors ${
                selectedAgentId === agent.id ? 'bg-primary-50 ring-1 ring-primary-200' : 'hover:bg-surface-50'
              }`}
            >
              <button
                onClick={() => onSelectAgent(agent.id)}
                data-testid="agent-list-select"
                data-agent-id={agent.id}
                className="min-w-0 flex flex-1 items-center gap-3 text-left"
              >
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                  agent.setup_required ? 'bg-accent-orange/15 text-accent-orange' : 'bg-surface-100 text-surface-600'
                }`}>
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-surface-900 truncate">{agent.name}</p>
                  <div className="flex items-center gap-2">
                    <p className="text-xs text-surface-500 truncate">{agent.description || agent.model || '等待首次配置'}</p>
                    {profileLabel && (
                      <span className={`shrink-0 ${getBadgeClassName('neutral', 'sm')}`}>
                        {profileLabel}
                      </span>
                    )}
                    {permissionLabel && (
                      <span className={`shrink-0 ${getBadgeClassName('slate', 'sm')}`}>
                        {permissionLabel}
                      </span>
                    )}
                  </div>
                </div>
                <span className={getBadgeClassName(statusMeta.tone, 'sm')}>{statusMeta.shortLabel}</span>
              </button>
              <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-all">
                <button
                  onClick={() => onEditAgent(agent)}
                  className="p-1 hover:bg-surface-200 rounded transition-all"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 text-surface-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                  </svg>
                </button>
                <button
                  onClick={() => onDeleteAgent(agent.id)}
                  className="p-1 hover:bg-red-100 rounded transition-all"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  </div>
);

export default TeamsSidebar;
