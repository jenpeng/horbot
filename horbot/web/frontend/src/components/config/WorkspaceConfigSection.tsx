import React from 'react';
import { Link } from 'react-router-dom';
import type { MainAgentSummary } from '../../hooks/useConfigurationState';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import ConfigInput from '../ConfigInput';
import ConfigSectionStatus from './ConfigSectionStatus';

interface WorkspaceConfigSectionProps {
  workspacePath: string;
  hasWorkspaceChanges: boolean;
  isSavingWorkspace: boolean;
  mainAgent: MainAgentSummary | null;
  onWorkspacePathChange: (value: string) => void;
  onSaveWorkspace: () => void | Promise<void>;
}

const WorkspaceConfigSection: React.FC<WorkspaceConfigSectionProps> = ({
  workspacePath,
  hasWorkspaceChanges,
  isSavingWorkspace,
  mainAgent,
  onWorkspacePathChange,
  onSaveWorkspace,
}) => {
  return (
    <Card padding="none" variant="default" className="shadow-sm hover:shadow-md transition-shadow duration-300">
      <div className="px-6 py-4 border-b border-surface-200 bg-gradient-to-r from-accent-emerald/10 to-transparent">
        <h2 className="text-xl font-bold text-surface-900 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-accent-emerald/20 flex items-center justify-center">
            <svg className="w-5 h-5 text-accent-emerald" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
          </div>
          默认工作区
        </h2>
        <p className="text-base text-surface-600 mt-2 ml-12">定义新 Agent 默认使用的工作目录基线</p>
      </div>
      <div className="p-6 space-y-4">
        <ConfigSectionStatus
          status={hasWorkspaceChanges ? 'dirty' : 'synced'}
          title={hasWorkspaceChanges ? '工作区路径尚未保存' : '工作区路径已同步'}
          description={
            hasWorkspaceChanges
              ? '当前输入框中的路径还只是本地修改，保存后才会影响新的默认工作区基线。'
              : '当前显示的是已生效的默认工作目录，新建 Agent 若未单独覆盖工作区会按此路径解析。'
          }
        />
        <div className="rounded-2xl border border-accent-emerald/20 bg-accent-emerald/5 px-4 py-3 text-sm text-surface-700">
          <div className="font-semibold text-surface-900">这里修改的是全局默认工作区，不是每个 Agent 的独立工作区。</div>
          <div className="mt-1">
            {mainAgent
              ? mainAgent.usesWorkspaceOverride
                ? `当前选中的 Agent ${mainAgent.name} (${mainAgent.id}) 已单独覆盖工作区，实际路径为 ${mainAgent.effectiveWorkspace}。`
                : `当前选中的 Agent ${mainAgent.name} (${mainAgent.id}) 未覆盖工作区时会回退到这里。`
              : '当前还没有可用 Agent；请在多 Agent 管理页先创建。'}
          </div>
          <Link to="/teams" className="mt-3 inline-flex rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-accent-emerald shadow-sm transition hover:bg-accent-emerald/10">
            去多 Agent 管理页调整实例工作区
          </Link>
        </div>
        <div>
          <ConfigInput
            label="Default Workspace"
            value={workspacePath}
            onChange={onWorkspacePathChange}
            placeholder=".horbot/agents/default/workspace (default: project directory)"
          />
          <p className="text-sm text-surface-500 mt-3">
            默认使用项目目录下的 <code className="bg-surface-100 px-2 py-1 rounded-lg text-surface-700 font-mono text-sm">.horbot/agents/default/workspace</code>。
            留空将回退到默认路径。
          </p>
          <p className="text-sm text-surface-500 mt-2">
            建议填写项目内的相对路径，便于权限控制、文件回收和跨环境迁移。独立 Agent 若配置了自己的 workspace，不会被这里覆盖。
          </p>
        </div>
        <div className="flex justify-end pt-5 border-t border-surface-200">
          <Button
            variant="primary"
            size="lg"
            onClick={() => void onSaveWorkspace()}
            disabled={!hasWorkspaceChanges || isSavingWorkspace}
            isLoading={isSavingWorkspace}
            className="px-8"
            leftIcon={
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            }
          >
            保存工作区默认值
          </Button>
        </div>
      </div>
    </Card>
  );
};

export default WorkspaceConfigSection;
