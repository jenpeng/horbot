import React, { memo } from 'react';
import { useConversationStore } from '../stores/conversationStore';

interface AgentInfo {
  id: string;
  name: string;
  description?: string;
  is_main?: boolean;
}

interface TeamInfo {
  id: string;
  name: string;
  members: string[];
  description?: string;
}

interface ConversationSidebarProps {
  agents: AgentInfo[];
  teams: TeamInfo[];
  onSelectAgent: (agentId: string) => void;
  onSelectTeam: (teamId: string) => void;
  isOpen: boolean;
  onClose: () => void;
}

const getAgentColor = (agentId: string): { bg: string; text: string } => {
  const colors = [
    { bg: 'bg-gradient-to-br from-purple-400 to-purple-600', text: 'text-white' },
    { bg: 'bg-gradient-to-br from-emerald-400 to-emerald-600', text: 'text-white' },
    { bg: 'bg-gradient-to-br from-orange-400 to-orange-600', text: 'text-white' },
    { bg: 'bg-gradient-to-br from-cyan-400 to-cyan-600', text: 'text-white' },
    { bg: 'bg-gradient-to-br from-pink-400 to-pink-600', text: 'text-white' },
  ];
  
  const index = Math.abs(
    agentId.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
  ) % colors.length;
  
  return colors[index];
};

const ConversationSidebar: React.FC<ConversationSidebarProps> = ({
  agents,
  teams,
  onSelectAgent,
  onSelectTeam,
  isOpen,
  onClose,
}) => {
  const currentConversationId = useConversationStore(state => state.currentConversationId);
  const setCurrentConversation = useConversationStore(state => state.setCurrentConversation);
  const getOrCreateDMConversation = useConversationStore(state => state.getOrCreateDMConversation);
  const getOrCreateTeamConversation = useConversationStore(state => state.getOrCreateTeamConversation);
  
  const handleSelectAgent = (agent: AgentInfo) => {
    const conv = getOrCreateDMConversation(agent.id, agent.name);
    setCurrentConversation(conv.id);
    onSelectAgent(agent.id);
  };
  
  const handleSelectTeam = (team: TeamInfo) => {
    const conv = getOrCreateTeamConversation(team.id, team.name, team.members, team.description);
    setCurrentConversation(conv.id);
    onSelectTeam(team.id);
  };
  
  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-surface-900/20 backdrop-blur-sm md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      
      <div
        className={`
          fixed md:relative inset-y-0 left-0 z-40
          w-[220px] bg-surface-900 border-r border-surface-700
          transform transition-transform duration-300 ease-out
          md:translate-x-0 flex flex-col
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <div className="p-3 border-b border-surface-700">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-surface-100 text-sm">对话</h3>
            <button
              onClick={onClose}
              className="md:hidden p-1.5 text-surface-400 hover:text-surface-200 rounded-lg hover:bg-surface-800 transition-colors"
              aria-label="关闭"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
        
        <div className="flex-1 overflow-y-auto">
          <div className="p-2">
            <div className="px-2 py-1.5 text-xs font-semibold text-surface-500 uppercase tracking-wider">
              私信
            </div>
            <div className="space-y-0.5 mt-1">
              {agents.map((agent) => {
                const convId = `dm_${agent.id}`;
                const isSelected = currentConversationId === convId;
                const color = getAgentColor(agent.id);
                
                return (
                  <button
                    key={agent.id}
                    onClick={() => handleSelectAgent(agent)}
                    className={`
                      w-full flex items-center gap-2.5 px-2 py-1.5 rounded-md transition-all text-left group
                      ${isSelected
                        ? 'bg-surface-700 text-white'
                        : 'text-surface-300 hover:bg-surface-800 hover:text-surface-100'
                      }
                    `}
                  >
                    <div className="relative flex-shrink-0">
                      <div className={`w-8 h-8 rounded-full ${color.bg} flex items-center justify-center ${color.text} font-semibold text-xs`}>
                        {agent.name.charAt(0).toUpperCase()}
                      </div>
                      <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-green-500 rounded-full border-2 border-surface-900" />
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{agent.name}</p>
                      {agent.description && (
                        <p className="text-xs text-surface-500 truncate">{agent.description}</p>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
          
          {teams.length > 0 && (
            <div className="p-2 border-t border-surface-700 mt-2">
              <div className="px-2 py-1.5 text-xs font-semibold text-surface-500 uppercase tracking-wider">
                团队
              </div>
              <div className="space-y-0.5 mt-1">
                {teams.map((team) => {
                  const convId = `team_${team.id}`;
                  const isSelected = currentConversationId === convId;
                  
                  return (
                    <button
                      key={team.id}
                      onClick={() => handleSelectTeam(team)}
                      className={`
                        w-full flex items-center gap-2.5 px-2 py-1.5 rounded-md transition-all text-left
                        ${isSelected
                          ? 'bg-surface-700 text-white'
                          : 'text-surface-300 hover:bg-surface-800 hover:text-surface-100'
                        }
                      `}
                    >
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-violet-700 flex items-center justify-center text-white">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                        </svg>
                      </div>
                      
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{team.name}</p>
                        <p className="text-xs text-surface-500">{team.members.length} 个成员</p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
        
        <div className="p-3 border-t border-surface-700 bg-surface-800">
          <div className="flex items-center justify-between text-xs text-surface-500">
            <span>{agents.length} 个 Agent</span>
            <div className="flex items-center gap-1">
              <div className="w-1.5 h-1.5 bg-green-500 rounded-full" />
              <span>在线</span>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default memo(ConversationSidebar);
