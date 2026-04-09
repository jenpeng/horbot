import React, { useState, useEffect } from 'react';

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

interface DelegatedTask {
  id: string;
  description: string;
  target_agent_id: string;
  source_agent_id: string;
  status: string;
  result: any;
  error: string | null;
  created_at: string;
  completed_at: string | null;
  priority: string;
}

interface CollaborationFlowProps {
  teamId?: string;
}

const CollaborationFlow: React.FC<CollaborationFlowProps> = ({ teamId }) => {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [tasks, setTasks] = useState<DelegatedTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTask, setSelectedTask] = useState<DelegatedTask | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [agentsRes, tasksRes] = await Promise.all([
          fetch('/api/agents'),
          fetch('/api/delegated-tasks')
        ]);
        
        const agentsData = await agentsRes.json();
        const tasksData = await tasksRes.json();
        
        setAgents(agentsData.agents || []);
        setTasks(tasksData.tasks || []);
      } catch (error) {
        console.error('Failed to fetch data:', error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [teamId]);

  const getAgentById = (agentId: string): AgentInfo | undefined => {
    return agents.find(a => a.id === agentId);
  };

  const getAgentColor = (agentId: string): string => {
    const colors = [
      'bg-primary-500',
      'bg-accent-purple',
      'bg-accent-emerald',
      'bg-accent-orange',
      'bg-accent-cyan',
      'bg-accent-pink',
    ];
    const index = agents.findIndex(a => a.id === agentId);
    return colors[index % colors.length];
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'completed': return 'bg-semantic-success';
      case 'failed': return 'bg-semantic-error';
      case 'pending': return 'bg-semantic-warning';
      default: return 'bg-surface-400';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return (
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        );
      case 'failed':
        return (
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        );
      case 'pending':
        return (
          <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        );
      default:
        return null;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex gap-2">
          {[0, 1, 2].map((i) => (
            <div 
              key={i} 
              className="w-2.5 h-2.5 bg-primary-500 rounded-full animate-bounce" 
              style={{ animationDelay: `${i * 150}ms` }}
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-surface-200 p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-surface-900">协作流程</h3>
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-semantic-success" />
            <span className="text-surface-600">已完成</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-semantic-warning" />
            <span className="text-surface-600">进行中</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-semantic-error" />
            <span className="text-surface-600">失败</span>
          </div>
        </div>
      </div>

      {agents.length === 0 ? (
        <div className="text-center py-12 text-surface-500">
          暂无 Agent 数据
        </div>
      ) : (
        <div className="space-y-6">
          <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h4 className="text-sm font-semibold text-surface-900">当前接入 Agent</h4>
                <p className="mt-1 text-xs text-surface-500">所有 Agent 在全局层面平级展示；团队中的主次与职责请在团队配置里定义。</p>
              </div>
              <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-surface-600 shadow-sm">
                共 {agents.length} 个
              </span>
            </div>
            <div className="mt-4 flex flex-wrap justify-center gap-4">
              {agents.map((agent) => (
                <div key={agent.id} className="flex min-w-[112px] flex-col items-center">
                  <div className={`w-12 h-12 rounded-xl ${getAgentColor(agent.id)} flex items-center justify-center text-white shadow-md`}>
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                  </div>
                  <p className="mt-1.5 text-sm font-medium text-surface-900">{agent.name}</p>
                  <p className="text-xs text-surface-500 text-center">{agent.capabilities[0] || '通用协作'}</p>
                </div>
              ))}
            </div>
          </div>

          {tasks.length > 0 && (
            <div className="mt-8">
              <h4 className="text-sm font-medium text-surface-700 mb-3">任务流程</h4>
              <div className="space-y-3">
                {tasks.slice(0, 10).map((task) => {
                  const sourceAgent = getAgentById(task.source_agent_id);
                  const targetAgent = getAgentById(task.target_agent_id);
                  
                  return (
                    <div
                      key={task.id}
                      onClick={() => setSelectedTask(selectedTask?.id === task.id ? null : task)}
                      className={`p-4 rounded-xl border transition-all cursor-pointer ${
                        selectedTask?.id === task.id
                          ? 'border-primary-300 bg-primary-50'
                          : 'border-surface-200 hover:border-surface-300 bg-surface-50'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-8 h-8 rounded-lg ${getStatusColor(task.status)} flex items-center justify-center text-white`}>
                          {getStatusIcon(task.status)}
                        </div>
                        
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-surface-900 truncate">{task.description}</p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-xs text-surface-500">
                              {sourceAgent?.name || task.source_agent_id}
                            </span>
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
                            </svg>
                            <span className="text-xs text-surface-500">
                              {targetAgent?.name || task.target_agent_id}
                            </span>
                          </div>
                        </div>
                        
                        <div className="text-right">
                          <span className={`text-xs px-2 py-1 rounded-full ${
                            task.status === 'completed' ? 'bg-semantic-success-light text-semantic-success' :
                            task.status === 'failed' ? 'bg-semantic-error-light text-semantic-error' :
                            'bg-semantic-warning-light text-semantic-warning'
                          }`}>
                            {task.status === 'completed' ? '已完成' : task.status === 'failed' ? '失败' : '进行中'}
                          </span>
                        </div>
                      </div>
                      
                      {selectedTask?.id === task.id && (
                        <div className="mt-4 pt-4 border-t border-surface-200">
                          <div className="grid grid-cols-2 gap-4 text-sm">
                            <div>
                              <p className="text-surface-500">任务 ID</p>
                              <p className="font-mono text-surface-900">{task.id}</p>
                            </div>
                            <div>
                              <p className="text-surface-500">优先级</p>
                              <p className="text-surface-900">{task.priority}</p>
                            </div>
                            <div>
                              <p className="text-surface-500">创建时间</p>
                              <p className="text-surface-900">{new Date(task.created_at).toLocaleString()}</p>
                            </div>
                            <div>
                              <p className="text-surface-500">完成时间</p>
                              <p className="text-surface-900">{task.completed_at ? new Date(task.completed_at).toLocaleString() : '-'}</p>
                            </div>
                          </div>
                          {task.result && (
                            <div className="mt-3">
                              <p className="text-surface-500 text-sm">结果</p>
                              <pre className="mt-1 p-3 bg-surface-100 rounded-lg text-xs overflow-auto max-h-32">
                                {typeof task.result === 'string' ? task.result : JSON.stringify(task.result, null, 2)}
                              </pre>
                            </div>
                          )}
                          {task.error && (
                            <div className="mt-3">
                              <p className="text-semantic-error text-sm">错误</p>
                              <p className="mt-1 text-sm text-surface-700">{task.error}</p>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {tasks.length === 0 && (
            <div className="text-center py-8 text-surface-500">
              暂无协作任务
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default CollaborationFlow;
