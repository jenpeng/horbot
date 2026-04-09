import React, { memo } from 'react';

interface AgentInfo {
  id: string;
  name: string;
  description: string;
  model: string;
  provider: string;
  capabilities: string[];
  teams: string[];
  is_main: boolean;
}

interface TeamInfo {
  id: string;
  name: string;
  members: string[];
  description?: string;
}

interface AgentSidebarProps {
  agents: AgentInfo[];
  teams?: TeamInfo[];
  currentChatTarget: { type: 'agent'; id: string } | { type: 'team'; id: string } | null;
  onSelectAgent: (agentId: string) => void;
  onSelectTeam: (teamId: string) => void;
  isOpen: boolean;
  onClose: () => void;
}

// Agent 头像颜色映射
const getAgentColor = (agentId: string): { bg: string; border: string; text: string } => {
  // 根据 agent ID 生成一致的颜色
  const colors = [
    { bg: 'bg-gradient-to-br from-purple-400 to-purple-600', border: 'border-purple-300', text: 'text-white' },
    { bg: 'bg-gradient-to-br from-emerald-400 to-emerald-600', border: 'border-emerald-300', text: 'text-white' },
    { bg: 'bg-gradient-to-br from-orange-400 to-orange-600', border: 'border-orange-300', text: 'text-white' },
    { bg: 'bg-gradient-to-br from-cyan-400 to-cyan-600', border: 'border-cyan-300', text: 'text-white' },
    { bg: 'bg-gradient-to-br from-pink-400 to-pink-600', border: 'border-pink-300', text: 'text-white' },
    { bg: 'bg-gradient-to-br from-indigo-400 to-indigo-600', border: 'border-indigo-300', text: 'text-white' },
  ];
  
  const index = Math.abs(agentId.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)) % colors.length;
  return colors[index];
};

const AgentSidebar: React.FC<AgentSidebarProps> = ({
  agents,
  teams = [],
  currentChatTarget,
  onSelectAgent,
  onSelectTeam,
  isOpen,
  onClose,
}) => {
  return (
    <>
      {/* 移动端遮罩 */}
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-surface-900/20 backdrop-blur-sm md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      
      {/* Agent 侧边栏 */}
      <div
        className={`
          fixed md:relative inset-y-0 left-0 z-40
          w-[200px] bg-white border-r border-surface-200
          transform transition-transform duration-300 ease-out
          md:translate-x-0 flex flex-col
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        {/* 头部 */}
        <div className="p-4 border-b border-surface-200">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-surface-900 text-sm">Agents</h3>
            <button
              onClick={onClose}
              className="md:hidden p-1.5 text-surface-500 hover:text-surface-700 rounded-lg hover:bg-surface-100 transition-colors"
              aria-label="关闭"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
        
        {/* Agent 列表 */}
        <div className="flex-1 overflow-y-auto p-2">
          {agents.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <div className="w-12 h-12 rounded-xl bg-surface-100 flex items-center justify-center mb-3">
                <svg className="w-6 h-6 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
              <p className="text-xs text-surface-500">暂无 Agent</p>
            </div>
          ) : (
            <div className="space-y-1">
              {agents.map((agent) => {
                const color = getAgentColor(agent.id);
                const isSelected = currentChatTarget?.type === 'agent' && currentChatTarget.id === agent.id;
                
                return (
                  <button
                    key={agent.id}
                    onClick={() => onSelectAgent(agent.id)}
                    className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-all text-left group ${
                      isSelected
                        ? 'bg-primary-50 border border-primary-200'
                        : 'hover:bg-surface-50 border border-transparent'
                    }`}
                  >
                    {/* 头像 */}
                    <div className="relative flex-shrink-0">
                      <div className={`w-8 h-8 rounded-lg ${color.bg} flex items-center justify-center ${color.text} font-semibold text-xs shadow-sm`}>
                        {agent.name.charAt(0).toUpperCase()}
                      </div>
                      {/* 在线状态指示器 */}
                      <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-semantic-success rounded-full border-2 border-white" />
                    </div>
                    
                    {/* 信息 */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1">
                        <p className={`text-sm font-medium truncate ${isSelected ? 'text-primary-700' : 'text-surface-900'}`}>
                          {agent.name}
                        </p>
                      </div>
                      <p className="text-xs text-surface-500 truncate">{agent.description || agent.model}</p>
                    </div>
                    
                    {/* 选中指示器 */}
                    {isSelected && (
                      <div className="w-1 h-6 bg-primary-500 rounded-full" />
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>
        
        {/* 团队列表 */}
        {teams.length > 0 && (
          <div className="p-2 border-t border-surface-200">
            <div className="px-2 py-1 text-xs font-medium text-surface-500 uppercase tracking-wider">
              团队
            </div>
            <div className="space-y-1">
              {teams.map((team) => {
                const isSelected = currentChatTarget?.type === 'team' && currentChatTarget.id === team.id;
                return (
                  <button
                    key={team.id}
                    onClick={() => onSelectTeam(team.id)}
                    className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-all text-left ${
                      isSelected
                        ? 'bg-primary-50 border border-primary-200'
                        : 'hover:bg-surface-50 border border-transparent'
                    }`}
                  >
                    <div className="relative flex-shrink-0">
                      <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-400 to-violet-600 flex items-center justify-center text-white font-semibold text-xs">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                        </svg>
                      </div>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1">
                        <p className={`text-sm font-medium truncate ${isSelected ? 'text-primary-700' : 'text-surface-900'}`}>
                          {team.name}
                        </p>
                      </div>
                      <p className="text-xs text-surface-500 truncate">{team.members.length} 个成员</p>
                    </div>
                    {isSelected && (
                      <div className="w-1 h-6 bg-primary-500 rounded-full" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}
        
        {/* 底部信息 */}
        <div className="p-3 border-t border-surface-200 bg-surface-50">
          <div className="flex items-center justify-between text-xs text-surface-500">
            <span>{agents.length} 个 Agent</span>
            <div className="flex items-center gap-1">
              <div className="w-1.5 h-1.5 bg-semantic-success rounded-full" />
              <span>在线</span>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default memo(AgentSidebar);
