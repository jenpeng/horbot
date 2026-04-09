import React, { useState, useEffect } from 'react';
import { planService } from '../services';
import type { SimplePlan } from '../services/plan';

interface PlanStep {
  id: string;
  description: string;
  tool_name: string | null;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  result?: string;
  error?: string;
}

interface Plan {
  id: string;
  title: string;
  steps: PlanStep[];
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  progress: number;
}

interface PlanViewProps {
  planId?: string;
  onPlanComplete?: (plan: Plan) => void;
  onPlanError?: (plan: Plan, error: string) => void;
}

const PlanView: React.FC<PlanViewProps> = ({ planId, onPlanComplete: _onPlanComplete, onPlanError: _onPlanError }) => {
  const [plan, setPlan] = useState<SimplePlan | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (planId) {
      loadPlan(planId);
    }
  }, [planId]);

  const loadPlan = async (id: string) => {
    setLoading(true);
    try {
      const data = await planService.getPlan(id);
      setPlan(data);
    } catch (error) {
      console.error('Error loading plan:', error);
    } finally {
      setLoading(false);
    }
  };

  const handlePause = async () => {
    if (!plan) return;
    try {
      await planService.pausePlan(plan.id);
      loadPlan(plan.id);
    } catch (error) {
      console.error('Error pausing plan:', error);
    }
  };

  const handleResume = async () => {
    if (!plan) return;
    try {
      await planService.resumePlan(plan.id);
      loadPlan(plan.id);
    } catch (error) {
      console.error('Error resuming plan:', error);
    }
  };

  const handleCancel = async () => {
    if (!plan) return;
    if (!window.confirm('确定要取消这个计划吗？')) return;
    try {
      await planService.pausePlan(plan.id);
      loadPlan(plan.id);
    } catch (error) {
      console.error('Error cancelling plan:', error);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending': return '⏳';
      case 'running': return '🔄';
      case 'completed': return '✅';
      case 'failed': return '❌';
      case 'skipped': return '⏭️';
      default: return '❓';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending': return 'text-gray-500';
      case 'running': return 'text-blue-500';
      case 'completed': return 'text-green-500';
      case 'failed': return 'text-red-500';
      case 'skipped': return 'text-yellow-500';
      default: return 'text-gray-500';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-4">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
        <span className="ml-2 text-gray-500">加载中...</span>
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="text-gray-500 text-center p-4">
        暂无执行计划
      </div>
    );
  }

  return (
    <div className="plan-view">
      <div className="plan-header mb-4">
        <h3 className="text-lg font-semibold">{plan.title}</h3>
        <div className="flex items-center gap-2 mt-1">
          <span className={`text-sm ${getStatusColor(plan.status)}`}>
            {plan.status}
          </span>
          <span className="text-sm text-gray-500">
            进度: {plan.progress.toFixed(0)}%
          </span>
        </div>
      </div>

      <div className="plan-steps space-y-2">
        {plan.steps.map((step, _index) => (
          <div 
            key={step.id}
            className={`step-item p-3 rounded border ${
              step.status === 'running' ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
            }`}
          >
            <div className="flex items-start gap-2">
              <span className="text-lg">{getStatusIcon(step.status)}</span>
              <div className="flex-1">
                <div className="font-medium">{step.description}</div>
                {step.tool_name && (
                  <div className="text-xs text-gray-500 mt-1">
                    工具: {step.tool_name}
                  </div>
                )}
                {step.error && (
                  <div className="text-xs text-red-500 mt-1">
                    错误: {step.error}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="plan-actions mt-4 flex gap-2">
        {plan.status === 'running' && (
          <button
            onClick={handlePause}
            className="px-3 py-1 bg-yellow-500 text-white rounded text-sm hover:bg-yellow-600"
          >
            暂停
          </button>
        )}
        {plan.status === 'paused' && (
          <button
            onClick={handleResume}
            className="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600"
          >
            继续
          </button>
        )}
        {['running', 'paused'].includes(plan.status) && (
          <button
            onClick={handleCancel}
            className="px-3 py-1 bg-red-500 text-white rounded text-sm hover:bg-red-600"
          >
            取消
          </button>
        )}
      </div>

      <div className="progress-bar mt-4">
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div 
            className="h-full bg-blue-500 transition-all duration-300"
            style={{ width: `${plan.progress}%` }}
          />
        </div>
      </div>
    </div>
  );
};

export default PlanView;
