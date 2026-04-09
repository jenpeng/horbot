import React, { useState } from 'react';
import { planService } from '../services';
import ExecutionLogTree, { type StepExecutionLog } from './ExecutionLogTree';

export interface SubTask {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  tools: string[];
  result: string;
  required_skills?: string[];
  required_mcp_tools?: string[];
}

export interface PlanSpec {
  why: string;
  what_changes: string[];
  impact: {
    affected_specs?: string[];
    affected_code?: string[];
  };
}

export interface PlanChecklistItem {
  id: string;
  description: string;
  category: string;
  checked: boolean;
}

export interface PlanChecklist {
  items: PlanChecklistItem[];
}

export interface Plan {
  id: string;
  title: string;
  description: string;
  subtasks: SubTask[];
  status: 'pending' | 'confirmed' | 'cancelled' | 'running' | 'completed' | 'stopped';
  created_at: string;
  updated_at: string;
  session_key: string;
  message_id: string;
  spec?: PlanSpec;
  checklist?: PlanChecklist;
  spec_content?: string;
  tasks_content?: string;
  checklist_content?: string;
  folder?: string;
  plan_type?: 'informational' | 'actionable';
  content?: string;
}

interface ExecutionPlanProps {
  plan: Plan;
  onConfirmed?: (plan: Plan) => void;
  onCancelled?: (plan: Plan) => void;
}

type TabType = 'spec' | 'tasks' | 'checklist';

const ExecutionPlan: React.FC<ExecutionPlanProps> = ({ plan, onConfirmed, onCancelled }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('spec');
  const [currentPlan, setCurrentPlan] = useState<Plan>(plan);
  const [executionLogs, setExecutionLogs] = useState<Array<{type: 'start' | 'complete' | 'error', message: string, timestamp: Date}>>([]);
  const [detailedExecutionLogs, setDetailedExecutionLogs] = useState<StepExecutionLog[]>([]);
  const [completedStepsCount, setCompletedStepsCount] = useState(0);

  // Sync currentPlan with plan prop when it changes
  React.useEffect(() => {
    setCurrentPlan(plan);
  }, [plan]);

  // Load execution logs from API when component mounts or plan changes
  React.useEffect(() => {
    const loadExecutionLogs = async () => {
      if (!currentPlan?.id || currentPlan.status === 'pending') return;
      
      try {
        const data = await planService.getPlanLogs(currentPlan.id);
        if (data?.logs) {
          const logs = data.logs;
          const allLogs: StepExecutionLog[] = [];
          
          // Convert logs from API format to component format
          Object.entries(logs).forEach(([stepId, stepData]: [string, any]) => {
            if (stepData?.logs) {
              const subtask = currentPlan.subtasks.find(st => st.id === stepId);
              const stepLog: StepExecutionLog = {
                stepId: stepId,
                stepTitle: subtask?.title || stepId,
                status: stepData.logs.some((l: any) => l.type === 'error') ? 'failed' : 'completed',
                executionTime: 0,
                logs: stepData.logs.map((log: any) => ({
                  type: log.type || 'thinking',
                  content: log.message || log.content || '',
                  timestamp: log.timestamp ? (typeof log.timestamp === 'number' ? log.timestamp : new Date(log.timestamp).getTime()) : Date.now(),
                  metadata: log.data ? { result: JSON.stringify(log.data) } : undefined
                }))
              };
              allLogs.push(stepLog);
            }
          });
          
          setDetailedExecutionLogs(allLogs);
          
          // Update completed steps count
          setCompletedStepsCount(allLogs.length);
          
          // Also update execution logs summary
          const summaryLogs: Array<{type: 'start' | 'complete' | 'error', message: string, timestamp: Date}> = [];
          allLogs.forEach(log => {
            summaryLogs.push({
              type: log.status === 'failed' ? 'error' : 'complete',
              message: `${log.stepTitle}: ${log.status === 'completed' ? '完成' : '失败'}`,
              timestamp: new Date()
            });
          });
          setExecutionLogs(summaryLogs);
        }
      } catch (err) {
        console.error('Failed to load execution logs:', err);
      }
    };
    
    loadExecutionLogs();
  }, [currentPlan?.id, currentPlan?.status]);

  // Generate execution logs from plan status and subtasks
  React.useEffect(() => {
    if (currentPlan) {
      const logs: Array<{type: 'start' | 'complete' | 'error', message: string, timestamp: Date}> = [];
      
      // Add plan start log if status is not pending
      if (currentPlan.status !== 'pending') {
        logs.push({
          type: 'start',
          message: '开始执行计划...',
          timestamp: new Date(currentPlan.created_at || Date.now())
        });
      }
      
      // Add subtask logs based on their status
      currentPlan.subtasks.forEach((subtask) => {
        if (subtask.status !== 'pending') {
          if (subtask.status === 'running') {
            logs.push({
              type: 'start',
              message: `开始执行: ${subtask.title}`,
              timestamp: new Date()
            });
          } else if (subtask.status === 'completed') {
            logs.push({
              type: 'complete',
              message: `步骤完成: ${subtask.title}`,
              timestamp: new Date()
            });
          } else if (subtask.status === 'failed') {
            logs.push({
              type: 'error',
              message: `步骤失败: ${subtask.title}`,
              timestamp: new Date()
            });
          }
        }
      });
      
      // Add plan complete log if status is completed
      if (currentPlan.status === 'completed') {
        logs.push({
          type: 'complete',
          message: '计划执行完成',
          timestamp: new Date()
        });
      }
      
      setExecutionLogs(logs);
    }
  }, [currentPlan]);

  const addExecutionLog = (type: 'start' | 'complete' | 'error', message: string) => {
    setExecutionLogs(prev => [...prev, { type, message, timestamp: new Date() }]);
  };

  const handleConfirm = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/plan/${currentPlan.id}/confirm`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          plan_id: currentPlan.id,
          session_key: currentPlan.session_key || 'default'
        }),
      });

      if (!response.ok) {
        throw new Error('确认失败');
      }

      // Mark plan as confirmed
      const confirmedPlan = { ...currentPlan, status: 'confirmed' as const };
      setCurrentPlan(confirmedPlan);
      // Use setTimeout to avoid updating parent component during render
      setTimeout(() => {
        onConfirmed?.(confirmedPlan);
      }, 0);
      addExecutionLog('start', '开始执行计划...');

      // Process SSE stream
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      
      if (reader) {
        let finished = false;
        while (!finished) {
          const { done, value } = await reader.read();
          if (done) {
            console.log('SSE stream done');
            break;
          }

          const chunk = decoder.decode(value, { stream: true });
          buffer += chunk;
          const lines = buffer.split('\n');
          
          // Keep the last incomplete line in the buffer
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const jsonStr = line.slice(6);
                const data = JSON.parse(jsonStr);
                
                if (data.event === 'subtask_start') {
                  // Update subtask status to running
                  addExecutionLog('start', `开始执行: ${data.title}`);
                  setCurrentPlan(prev => {
                    const updated = {
                      ...prev,
                      status: 'running' as const,
                      subtasks: prev.subtasks.map(st =>
                        st.id === data.subtask_id
                          ? { ...st, status: 'running' as const }
                          : st
                      )
                    };
                    // Use setTimeout to avoid updating parent component during render
                    setTimeout(() => {
                      onConfirmed?.(updated);
                    }, 0);
                    return updated;
                  });
                } else if (data.event === 'subtask_complete') {
                  // Update subtask status
                  const statusText = data.status === 'completed' ? '完成' : data.status === 'failed' ? '失败' : data.status;
                  addExecutionLog(data.status === 'failed' ? 'error' : 'complete', `步骤${statusText}: ${data.result?.substring(0, 100) || '无结果'}`);
                  
                  // Update detailed execution logs
                  if (data.logs && data.logs.length > 0) {
                    const subtask = currentPlan.subtasks.find(st => st.id === data.subtask_id);
                    if (subtask) {
                      const stepLog: StepExecutionLog = {
                        stepId: data.subtask_id,
                        stepTitle: subtask.title,
                        status: data.status,
                        executionTime: data.execution_time || 0,
                        logs: data.logs.map((log: any) => ({
                          timestamp: log.timestamp,
                          type: log.type,
                          content: log.content,
                          metadata: log.metadata
                        }))
                      };
                      setDetailedExecutionLogs(prev => {
                        const existingIndex = prev.findIndex(l => l.stepId === data.subtask_id);
                        if (existingIndex >= 0) {
                          const updated = [...prev];
                          updated[existingIndex] = stepLog;
                          return updated;
                        }
                        return [...prev, stepLog];
                      });
                    }
                  }
                  
                  if (data.status === 'completed') {
                    setCompletedStepsCount(prev => prev + 1);
                  }
                  
                  setCurrentPlan(prev => {
                    const updated = {
                      ...prev,
                      subtasks: prev.subtasks.map(st =>
                        st.id === data.subtask_id
                          ? { ...st, status: data.status as any, result: data.result }
                          : st
                      )
                    };
                    // Use setTimeout to avoid updating parent component during render
                    setTimeout(() => {
                      onConfirmed?.(updated);
                    }, 0);
                    return updated;
                  });
                } else if (data.event === 'plan_complete') {
                  // Plan execution completed
                  addExecutionLog('complete', '计划执行完成');
                  setCurrentPlan(prev => {
                    const updated = {
                      ...prev,
                      status: 'completed' as const,
                      subtasks: prev.subtasks.map(st => ({
                        ...st,
                        status: st.status === 'running' ? 'completed' as const : st.status
                      }))
                    };
                    // Use setTimeout to avoid updating parent component during render
                    setTimeout(() => {
                      onConfirmed?.(updated);
                    }, 0);
                    return updated;
                  });
                } else if (data.event === 'error') {
                  addExecutionLog('error', `错误: ${data.content}`);
                  setError(data.content);
                } else if (data.event === 'done') {
                  console.log('Received done event');
                  finished = true;
                  // Force a final state update to ensure UI reflects completion
                  setCurrentPlan(prev => {
                    const updated = { ...prev };
                    // If status is still running/confirmed, mark as completed
                    if (updated.status === 'running' || updated.status === 'confirmed') {
                      updated.status = 'completed';
                    }
                    return updated;
                  });
                  break;
                }
              } catch (e) {
                console.error('Error parsing SSE data:', e);
              }
            }
          }
        }
        console.log('SSE stream finished');
      }
    } catch (err: any) {
      console.error('handleConfirm error:', err);
      setError(err.message || '确认失败');
    } finally {
      console.log('Setting isLoading to false');
      setIsLoading(false);
    }
  };

  const handleCancel = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await planService.cancelPlan(currentPlan.id, currentPlan.session_key || 'default');
      if (response.status === 'cancelled') {
        const cancelledPlan = { ...currentPlan, status: 'cancelled' as const };
        setCurrentPlan(cancelledPlan);
        onCancelled?.(cancelledPlan);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '取消失败');
    } finally {
      setIsLoading(false);
    }
  };

  const handleStop = async () => {
    setIsLoading(true);
    setError(null);
    try {
      console.log('Stop button clicked:', {
        plan_id: currentPlan.id,
        session_key: currentPlan.session_key || 'default'
      });
      const response = await planService.stopPlan(currentPlan.id, currentPlan.session_key || 'default');
      console.log('Stop response:', response);
      if (response.status === 'stopped') {
        const stoppedPlan = { ...currentPlan, status: 'stopped' as const };
        setCurrentPlan(stoppedPlan);
        addExecutionLog('error', '计划执行已停止');
      }
    } catch (err: any) {
      console.error('Stop error:', err);
      setError(err.response?.data?.detail || '停止失败');
    } finally {
      setIsLoading(false);
    }
  };

  const statusIcons: Record<string, React.ReactNode> = {
    pending: (
      <div className="w-5 h-5 rounded-full border-2 border-surface-400 bg-surface-100 flex items-center justify-center">
        <div className="w-2 h-2 rounded-full bg-surface-400" />
      </div>
    ),
    running: (
      <div className="w-5 h-5 rounded-full bg-primary-500 flex items-center justify-center shadow-lg shadow-primary-500/30">
        <svg className="w-3 h-3 text-white animate-spin" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
      </div>
    ),
    completed: (
      <div className="w-5 h-5 rounded-full bg-semantic-success flex items-center justify-center shadow-md shadow-semantic-success/20">
        <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
        </svg>
      </div>
    ),
    failed: (
      <div className="w-5 h-5 rounded-full bg-semantic-error flex items-center justify-center shadow-md shadow-semantic-error/20">
        <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </div>
    ),
  };

  const completedCount = currentPlan.subtasks.filter(s => s.status === 'completed').length;
  const isPending = currentPlan.status === 'pending';
  const isCancelled = currentPlan.status === 'cancelled';
  const isCompleted = currentPlan.status === 'completed';
  const isStopped = currentPlan.status === 'stopped';
  const isInformational = currentPlan.plan_type === 'informational';
  const showActionButtons = isPending; // Only show buttons for pending plans

  // Debug: log status to verify logic
  console.log('[ExecutionPlan] Plan ID:', currentPlan.id, 'Status:', currentPlan.status, 'showActionButtons:', showActionButtons, 'plan_type:', currentPlan.plan_type);

  const renderMarkdownContent = (content: string) => {
    const lines = content.split('\n');
    return lines.map((line, index) => {
      if (line.startsWith('# ')) {
        return <h1 key={index} className="text-xl font-bold text-surface-900 mt-5 mb-3">{line.slice(2)}</h1>;
      } else if (line.startsWith('## ')) {
        return <h2 key={index} className="text-lg font-semibold text-surface-800 mt-4 mb-2">{line.slice(3)}</h2>;
      } else if (line.startsWith('### ')) {
        return <h3 key={index} className="text-base font-medium text-surface-700 mt-3 mb-2">{line.slice(4)}</h3>;
      } else if (line.startsWith('- [x]')) {
        return <div key={index} className="text-sm text-surface-600 line-through flex items-center gap-2 py-0.5"><span className="text-semantic-success font-bold">✓</span>{line.slice(6)}</div>;
      } else if (line.startsWith('- [ ]')) {
        return <div key={index} className="text-sm text-surface-700 flex items-center gap-2 py-0.5"><span className="text-surface-400">☐</span>{line.slice(6)}</div>;
      } else if (line.startsWith('- ')) {
        return <div key={index} className="text-sm text-surface-700 ml-4 py-0.5">• {line.slice(2)}</div>;
      } else if (line.startsWith('**') && line.endsWith('**')) {
        return <div key={index} className="text-sm font-semibold text-surface-800 py-0.5">{line.slice(2, -2)}</div>;
      } else if (line.trim() === '---') {
        return <hr key={index} className="border-surface-200 my-4" />;
      } else if (line.trim()) {
        return <div key={index} className="text-sm text-surface-700 py-0.5 leading-relaxed">{line}</div>;
      }
      return <div key={index} className="h-2" />;
    });
  };

  const tabs: { id: TabType; label: string; icon: React.ReactNode }[] = [
    { id: 'spec', label: '规范大纲', icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ) },
    { id: 'tasks', label: '任务列表', icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
      </svg>
    ) },
    { id: 'checklist', label: '验收清单', icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ) },
  ];

  return (
    <div className="rounded-2xl bg-white border border-surface-200 shadow-md overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-surface-200 bg-gradient-to-r from-surface-50 to-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center shadow-lg shadow-primary-500/20">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-surface-900">执行计划</span>
                {currentPlan.status !== 'pending' && (
                  <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                    currentPlan.status === 'confirmed' ? 'bg-primary-100 text-primary-700' :
                    currentPlan.status === 'cancelled' ? 'bg-semantic-error-light text-semantic-error' :
                    currentPlan.status === 'running' ? 'bg-semantic-warning-light text-semantic-warning' :
                    currentPlan.status === 'completed' ? 'bg-semantic-success-light text-semantic-success' :
                    'bg-surface-100 text-surface-600'
                  }`}>
                    {currentPlan.status === 'confirmed' ? '已确认' :
                     currentPlan.status === 'cancelled' ? '已取消' :
                     currentPlan.status === 'running' ? '执行中' :
                     currentPlan.status === 'completed' ? '已完成' : '待确认'}
                  </span>
                )}
              </div>
              <div className="text-sm text-surface-600 mt-0.5">{currentPlan.title}</div>
            </div>
          </div>
          {currentPlan.status !== 'pending' && (
            <div className="text-right">
              <div className="text-2xl font-bold text-surface-900">{Math.round((completedCount / currentPlan.subtasks.length) * 100)}%</div>
              <div className="text-xs text-surface-500">{completedCount}/{currentPlan.subtasks.length} 完成</div>
            </div>
          )}
        </div>
        {currentPlan.status !== 'pending' && (
          <div className="mt-3 h-2 bg-surface-100 rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-primary-500 to-primary-600 rounded-full transition-all duration-500"
              style={{ width: `${(completedCount / currentPlan.subtasks.length) * 100}%` }}
            />
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-surface-200 bg-surface-50">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 px-4 py-3 text-sm flex items-center justify-center gap-2 transition-all ${
              activeTab === tab.id
                ? 'bg-white text-primary-600 border-b-2 border-primary-500 font-medium'
                : 'text-surface-600 hover:text-surface-900 hover:bg-surface-100'
            }`}
          >
            {tab.icon}
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="px-5 py-4 max-h-[500px] overflow-y-auto bg-white">
        {activeTab === 'spec' && (
          <div className="spec-content">
            {/* For informational plans, show the content if available */}
            {isInformational && currentPlan.content ? (
              renderMarkdownContent(currentPlan.content)
            ) : currentPlan.spec_content ? (
              renderMarkdownContent(currentPlan.spec_content)
            ) : (
              <div className="text-surface-700 text-sm space-y-4">
                {currentPlan.spec?.why && (
                  <div className="p-4 rounded-xl bg-surface-50 border border-surface-200">
                    <div className="text-xs text-surface-500 mb-2 font-semibold uppercase tracking-wide">为什么需要这个计划</div>
                    <div className="text-surface-800 leading-relaxed">{currentPlan.spec.why}</div>
                  </div>
                )}
                {currentPlan.spec?.what_changes && currentPlan.spec.what_changes.length > 0 && (
                  <div className="p-4 rounded-xl bg-surface-50 border border-surface-200">
                    <div className="text-xs text-surface-500 mb-3 font-semibold uppercase tracking-wide">计划变更</div>
                    <ul className="list-disc list-inside text-surface-800 space-y-2">
                      {currentPlan.spec.what_changes.map((change, i) => (
                        <li key={i} className="leading-relaxed">{change}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {currentPlan.spec?.impact && (currentPlan.spec.impact.affected_specs?.length || currentPlan.spec.impact.affected_code?.length) && (
                  <div className="p-4 rounded-xl bg-surface-50 border border-surface-200">
                    <div className="text-xs text-surface-500 mb-3 font-semibold uppercase tracking-wide">影响范围</div>
                    <div className="text-surface-800 space-y-2">
                      {currentPlan.spec.impact.affected_specs && currentPlan.spec.impact.affected_specs.length > 0 && (
                        <div className="flex items-start gap-2">
                          <span className="text-surface-500 font-medium min-w-[60px]">Specs:</span>
                          <span className="text-surface-700">{currentPlan.spec.impact.affected_specs.join(', ')}</span>
                        </div>
                      )}
                      {currentPlan.spec.impact.affected_code && currentPlan.spec.impact.affected_code.length > 0 && (
                        <div className="flex items-start gap-2">
                          <span className="text-surface-500 font-medium min-w-[60px]">代码:</span>
                          <span className="text-surface-700">{currentPlan.spec.impact.affected_code.join(', ')}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
                {!currentPlan.spec?.why && !currentPlan.spec?.what_changes?.length && (
                  <div className="text-center py-12 text-surface-400">
                    <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    暂无规范大纲内容
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === 'tasks' && (
          <div className="tasks-content">
            {isInformational ? (
              <div className="text-center py-12 text-surface-400">
                <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p>这是一个信息提供型规划</p>
                <p className="text-sm mt-2">请在"规范大纲"标签页查看建议内容</p>
              </div>
            ) : currentPlan.tasks_content ? (
              renderMarkdownContent(currentPlan.tasks_content)
            ) : (
              <div className="space-y-2">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-medium text-surface-700">子任务</span>
                  <span className="text-xs text-surface-500">{completedCount}/{currentPlan.subtasks.length}</span>
                </div>
                {currentPlan.subtasks.map((subtask, index) => (
                  <div
                    key={subtask.id}
                    className={`flex items-start gap-3 p-3 rounded-lg border transition-all ${
                      subtask.status === 'running'
                        ? 'bg-primary-50 border-primary-200'
                        : 'bg-surface-50 border-surface-200 hover:border-surface-300'
                    }`}
                  >
                    <div className="flex-shrink-0 mt-0.5">
                      {statusIcons[subtask.status]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm font-medium ${
                          subtask.status === 'completed' ? 'text-surface-500 line-through' :
                          subtask.status === 'running' ? 'text-primary-700' :
                          subtask.status === 'failed' ? 'text-semantic-error' :
                          'text-surface-700'
                        }`}>
                          {index + 1}. {subtask.title}
                        </span>
                        {subtask.status === 'running' && (
                          <span className="px-2 py-0.5 text-xs rounded-full bg-primary-100 text-primary-700 font-medium">
                            执行中
                          </span>
                        )}
                      </div>
                      {subtask.tools && subtask.tools.length > 0 && (
                        <div className="flex items-center gap-1 mt-1">
                          <span className="text-xs text-surface-500">工具:</span>
                          {subtask.tools.map((tool, i) => (
                            <span key={i} className="text-xs px-2 py-0.5 rounded bg-surface-200 text-surface-600 font-mono">
                              {tool}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'checklist' && (
          <div className="checklist-content">
            {isInformational ? (
              <div className="text-center py-12 text-surface-400">
                <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p>信息提供型规划无需验收清单</p>
                <p className="text-sm mt-2">请在"规范大纲"标签页查看建议内容</p>
              </div>
            ) : currentPlan.checklist_content ? (
              renderMarkdownContent(currentPlan.checklist_content)
            ) : (
              <div className="space-y-2">
                {currentPlan.checklist?.items && currentPlan.checklist.items.length > 0 ? (
                  currentPlan.checklist.items.map((item) => (
                    <div
                      key={item.id}
                      className={`flex items-start gap-3 p-3 rounded-lg border transition-all ${
                        item.checked
                          ? 'bg-semantic-success-light border-semantic-success/30'
                          : 'bg-surface-50 border-surface-200'
                      }`}
                    >
                      <div className="flex-shrink-0 mt-0.5">
                        {item.checked ? (
                          <div className="w-5 h-5 rounded-full bg-semantic-success flex items-center justify-center">
                            <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                            </svg>
                          </div>
                        ) : (
                          <div className="w-5 h-5 rounded-full border-2 border-surface-400 bg-white" />
                        )}
                      </div>
                      <div className="flex-1">
                        <span className={`text-sm ${item.checked ? 'text-surface-600 line-through' : 'text-surface-700'}`}>
                          {item.description}
                        </span>
                        <span className="ml-2 text-xs px-2 py-0.5 rounded bg-surface-200 text-surface-600">
                          {item.category}
                        </span>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-surface-500">暂无验收清单内容</div>
                )}
              </div>
            )}
          </div>
        )}

      </div>

      {/* Execution Logs - Main Content Area */}
      {currentPlan.status !== 'pending' && (
        <div className="border-t border-surface-200">
          {/* Execution Logs Header */}
          <div className="px-5 py-3 bg-surface-50 border-b border-surface-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-surface-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              <span className="text-sm font-medium text-surface-700">执行日志</span>
              <span className="text-xs text-surface-500">
                ({completedStepsCount}/{currentPlan.subtasks.length} 步骤)
              </span>
            </div>
            {currentPlan.status === 'running' && (
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-primary-500 animate-pulse"></div>
                <span className="text-xs text-primary-600 font-medium">执行中...</span>
              </div>
            )}
          </div>

          {/* Execution Logs Content */}
          <div className="execution-logs-container max-h-[600px] overflow-y-auto bg-surface-50">
            {detailedExecutionLogs.length > 0 ? (
              <div className="p-4">
                <ExecutionLogTree
                  logs={detailedExecutionLogs}
                  totalSteps={currentPlan.subtasks.length}
                  completedSteps={completedStepsCount}
                />
              </div>
            ) : (
              <div className="px-4 py-8 text-center text-surface-500 text-sm">
                {currentPlan.status === 'running' ? (
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
                      <svg className="w-5 h-5 text-primary-600 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                    </div>
                    <span>等待执行日志...</span>
                  </div>
                ) : (
                  <span>暂无详细执行日志</span>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Execution History Logs */}
      {executionLogs.length > 0 && (
        <div className="border-t border-surface-200">
          <div className="px-5 py-3 bg-surface-50 text-sm font-medium text-surface-700 flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            执行历史
          </div>
          <div className="max-h-40 overflow-y-auto bg-surface-50">
            {executionLogs.map((log, index) => (
              <div 
                key={index}
                className={`px-5 py-2.5 text-xs border-b border-surface-200 flex items-center gap-2 ${
                  log.type === 'error' ? 'text-semantic-error bg-semantic-error-light/30' : 
                  log.type === 'complete' ? 'text-semantic-success bg-semantic-success-light/30' : 
                  'text-surface-600'
                }`}
              >
                <span className="text-surface-500 font-mono">
                  {log.timestamp.toLocaleTimeString()}
                </span>
                <span className="flex-1">{log.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Plan file path */}
      <div className="px-5 py-3 border-t border-surface-200 text-xs text-surface-500 flex items-center gap-2 bg-surface-50">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
        </svg>
        <span className="font-mono">.horbot/plans/{currentPlan.folder || currentPlan.id}/</span>
      </div>

      {/* Error message */}
      {error && (
        <div className="px-5 py-3 bg-semantic-error-light text-semantic-error text-sm flex items-center gap-2 border-t border-semantic-error/30">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {error}
        </div>
      )}

      {/* Running status with stop button */}
      {(currentPlan.status === 'running' || currentPlan.status === 'confirmed') && (
        <div className="px-5 py-4 border-t border-surface-200 flex items-center justify-between bg-semantic-warning-light/30">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-semantic-warning flex items-center justify-center">
              <svg className="w-4 h-4 text-white animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            </div>
            <span className="text-sm font-medium text-surface-900">
              {currentPlan.status === 'confirmed' ? '等待执行...' : '正在执行...'}
            </span>
          </div>
          <button
            onClick={handleStop}
            className="px-5 py-2.5 rounded-xl bg-semantic-error hover:bg-red-600 text-white text-sm font-medium transition-all shadow-md hover:shadow-lg flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
            </svg>
            停止执行
          </button>
        </div>
      )}

      {/* Action buttons - Only show for pending plans */}
      {(() => { console.log('[ExecutionPlan] Rendering buttons section, showActionButtons:', showActionButtons); return showActionButtons; })() && (
        <div className="px-5 py-4 border-t border-surface-200 flex gap-3 bg-surface-50">
          <button
            onClick={handleConfirm}
            disabled={isLoading}
            className="flex-1 px-5 py-3 rounded-xl bg-gradient-to-r from-primary-500 to-primary-600 hover:from-primary-600 hover:to-primary-700 text-white text-sm font-medium transition-all shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {isLoading ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                处理中...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                {isInformational ? '采纳建议' : '确认执行'}
              </>
            )}
          </button>
          <button
            onClick={handleCancel}
            disabled={isLoading}
            className="flex-1 px-5 py-3 rounded-xl bg-white hover:bg-surface-50 text-semantic-error text-sm font-medium transition-all border-2 border-semantic-error/30 hover:border-semantic-error disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
            {isInformational ? '重新规划' : '取消计划'}
          </button>
        </div>
      )}

      {/* Status messages for non-pending plans */}
      {!showActionButtons && (
        <div className={`px-5 py-4 border-t border-surface-200 text-center text-sm flex items-center justify-center gap-2 ${
          isCompleted ? 'bg-semantic-success-light/30 text-semantic-success' :
          isCancelled ? 'bg-semantic-error-light/30 text-semantic-error' :
          isStopped ? 'bg-semantic-warning-light/30 text-semantic-warning' :
          'bg-surface-50 text-surface-600'
        }`}>
          {isCompleted && (
            <>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              计划已完成
            </>
          )}
          {isCancelled && (
            <>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              计划已取消
            </>
          )}
          {isStopped && (
            <>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
              </svg>
              计划已停止
            </>
          )}
          {!isCompleted && !isCancelled && !isStopped && (
            <>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              计划状态: {currentPlan.status}
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default ExecutionPlan;
