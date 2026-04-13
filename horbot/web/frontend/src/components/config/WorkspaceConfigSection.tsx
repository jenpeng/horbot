import React from 'react';
import { Link } from 'react-router-dom';
import { useI18n } from '../../contexts/I18nContext';
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
  const { t } = useI18n();
  return (
    <Card padding="none" variant="default" className="shadow-sm hover:shadow-md transition-shadow duration-300">
      <div className="px-6 py-4 border-b border-surface-200 bg-gradient-to-r from-accent-emerald/10 to-transparent">
        <h2 className="text-xl font-bold text-surface-900 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-accent-emerald/20 flex items-center justify-center">
            <svg className="w-5 h-5 text-accent-emerald" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
          </div>
          {t('config.section.workspace')}
        </h2>
        <p className="text-base text-surface-600 mt-2 ml-12">{t('config.workspace.subtitle')}</p>
      </div>
      <div className="p-6 space-y-4">
        <ConfigSectionStatus
          status={hasWorkspaceChanges ? 'dirty' : 'synced'}
          title={hasWorkspaceChanges ? t('config.workspace.unsaved') : t('config.workspace.synced')}
          description={
            hasWorkspaceChanges
              ? t('config.workspace.unsavedDescription')
              : t('config.workspace.syncedDescription')
          }
        />
        <div className="rounded-2xl border border-accent-emerald/20 bg-accent-emerald/5 px-4 py-3 text-sm text-surface-700">
          <div className="font-semibold text-surface-900">{t('config.workspace.cardTitle')}</div>
          <div className="mt-1">
            {mainAgent
              ? mainAgent.usesWorkspaceOverride
                ? t('config.workspace.overrideBody', { name: mainAgent.name, id: mainAgent.id, workspace: mainAgent.effectiveWorkspace })
                : t('config.workspace.fallbackBody', { name: mainAgent.name, id: mainAgent.id })
              : t('config.workspace.noAgent')}
          </div>
          <Link to="/teams" className="mt-3 inline-flex rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-accent-emerald shadow-sm transition hover:bg-accent-emerald/10">
            {t('config.workspace.adjustAgentWorkspace')}
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
            {t('config.workspace.defaultHintPrefix')} <code className="bg-surface-100 px-2 py-1 rounded-lg text-surface-700 font-mono text-sm">.horbot/agents/default/workspace</code>. {t('config.workspace.defaultHintSuffix')}
          </p>
          <p className="text-sm text-surface-500 mt-2">
            {t('config.workspace.pathAdvice')}
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
            {t('config.workspace.save')}
          </Button>
        </div>
      </div>
    </Card>
  );
};

export default WorkspaceConfigSection;
