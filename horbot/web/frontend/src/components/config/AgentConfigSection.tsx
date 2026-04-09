import React from 'react';
import { Link } from 'react-router-dom';
import type { ModelConfig, ModelsConfig } from '../../types';
import type { MainAgentSummary } from '../../hooks/useConfigurationState';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import ConfigInput from '../ConfigInput';
import ConfigSectionStatus from './ConfigSectionStatus';
import { type ModelScenarioKey } from './constants';

interface AgentConfigSectionProps {
  modelsConfig: ModelsConfig;
  providerOptions: string[];
  modelChanges: Record<ModelScenarioKey, boolean>;
  modelSaving: Record<ModelScenarioKey, boolean>;
  agentSettings: {
    max_tokens: number;
    temperature: number;
  };
  agentErrors: Record<string, string>;
  hasAgentChanges: boolean;
  hasModelsChanges: boolean;
  isSavingAgent: boolean;
  isSavingModels: boolean;
  mainAgent: MainAgentSummary | null;
  onUpdateModelConfig: (scenario: ModelScenarioKey, field: keyof ModelConfig, value: string) => void;
  onSaveModel: (scenario: ModelScenarioKey) => void | Promise<void>;
  onSaveAgentSettings: () => void | Promise<void>;
  onSaveModelsConfig: () => void | Promise<void>;
  onAgentSettingsChange: (field: 'max_tokens' | 'temperature', value: number) => void;
  clearFieldError: (fieldName: string) => void;
}

const AgentConfigSection: React.FC<AgentConfigSectionProps> = ({
  agentSettings,
  agentErrors,
  hasAgentChanges,
  isSavingAgent,
  mainAgent,
  onSaveAgentSettings,
  onAgentSettingsChange,
  clearFieldError,
}) => {
  const agentStatusTitle = hasAgentChanges ? '存在未保存修改' : '当前配置已同步';
  const agentStatusDescription = hasAgentChanges
    ? [
        hasAgentChanges ? '高级参数有本地改动' : '',
      ].filter(Boolean).join('，') + '。请按需保存对应区块。'
    : '当前页仅保留全局运行参数。Agent 的 provider 与 model 已移到多 Agent 管理页。';

  return (
    <Card padding="none" variant="default" className="shadow-sm hover:shadow-md transition-shadow duration-300">
      <div className="px-6 py-4 border-b border-surface-200 bg-gradient-to-r from-primary-50/50 to-transparent">
        <h2 className="text-xl font-bold text-surface-900 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center">
            <svg className="w-5 h-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
            </svg>
          </div>
          全局运行参数
        </h2>
        <p className="text-base text-surface-600 mt-2 ml-12">这里只保留运行参数；Agent 模型配置请前往多 Agent 管理</p>
      </div>
      <div className="p-6 space-y-4">
        <ConfigSectionStatus
          status={hasAgentChanges ? 'dirty' : 'synced'}
          title={agentStatusTitle}
          description={agentStatusDescription}
        />
        <div className="rounded-2xl border border-primary-200 bg-primary-50/60 px-4 py-3 text-sm text-surface-700">
          <div className="font-semibold text-surface-900">Agent 的 provider、model、人格和职责不再在这里配置。</div>
          <div className="mt-1">
            {mainAgent
              ? `当前默认打开的 Agent 为 ${mainAgent.name} (${mainAgent.id})。如需调整模型或实例工作区，请直接去多 Agent 管理页。`
              : '当前未选择默认 Agent，请在多 Agent 管理页创建并管理。'}
          </div>
          <Link to="/teams" className="mt-3 inline-flex rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-primary-700 shadow-sm transition hover:bg-primary-100">
            打开多 Agent 管理
          </Link>
        </div>
        <div className="bg-surface-50 rounded-xl p-5 border border-surface-200">
          <h3 className="text-base font-bold text-surface-900 mb-4 flex items-center gap-2">
            <svg className="w-5 h-5 text-accent-orange" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
            </svg>
            高级参数
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div>
              <ConfigInput
                label="Max Tokens"
                type="number"
                value={String(agentSettings.max_tokens)}
                onChange={(value) => {
                  onAgentSettingsChange('max_tokens', parseInt(value, 10) || 8192);
                  clearFieldError('max_tokens');
                }}
                placeholder="8192"
                min={1}
                max={1000000}
              />
              <p className="mt-2 text-sm text-surface-500">限制单次回复可生成的最大 token 数；过大可能增加成本和响应时间。</p>
              {agentErrors.max_tokens && <p className="text-accent-red text-sm mt-2">{agentErrors.max_tokens}</p>}
            </div>
            <div>
              <ConfigInput
                label="Temperature"
                type="number"
                value={String(agentSettings.temperature)}
                onChange={(value) => {
                  onAgentSettingsChange('temperature', parseFloat(value) || 0.7);
                  clearFieldError('temperature');
                }}
                placeholder="0.7"
                min={0}
                max={2}
                step={0.1}
              />
              <p className="mt-2 text-sm text-surface-500">控制回答随机性；越低越稳定，越高越发散，建议常规场景保持在 0.2 到 0.8。</p>
              {agentErrors.temperature && <p className="text-accent-red text-sm mt-2">{agentErrors.temperature}</p>}
            </div>
          </div>
        </div>
      </div>
      <div className="flex justify-end pt-5 border-t border-surface-200 px-6 pb-6 gap-3">
        <Button
          variant="secondary"
            onClick={() => void onSaveAgentSettings()}
            disabled={!hasAgentChanges || isSavingAgent || Object.keys(agentErrors).length > 0}
          isLoading={isSavingAgent}
          leftIcon={
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          }
        >
          保存全局默认参数
        </Button>
      </div>
    </Card>
  );
};

export default AgentConfigSection;
