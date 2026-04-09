import React, { useState } from 'react';
import { useConfigurationState } from '../hooks/useConfigurationState';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import ConfigCheckResult from '../components/ConfigCheckResult';
import ConfigurationHeader from '../components/config/ConfigurationHeader';
import ConfigurationOverview from '../components/config/ConfigurationOverview';
import AgentConfigSection from '../components/config/AgentConfigSection';
import WorkspaceConfigSection from '../components/config/WorkspaceConfigSection';
import WebSearchConfigSection from '../components/config/WebSearchConfigSection';
import ProviderConfigSection from '../components/config/ProviderConfigSection';

const ConfigPage: React.FC = () => {
  const state = useConfigurationState();
  const [reloadConfirmOpen, setReloadConfirmOpen] = useState(false);

  const handleReload = () => {
    if (!state.hasPendingChanges) {
      void state.refreshConfigFromServer('配置已重新从磁盘加载');
      return;
    }
    setReloadConfirmOpen(true);
  };

  if (state.isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex space-x-2">
          <div className="w-2 h-2 bg-brand-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
          <div className="w-2 h-2 bg-brand-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
          <div className="w-2 h-2 bg-brand-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto w-full px-4 py-6 space-y-6">
        <ConfigurationHeader
          fileInputRef={state.fileInputRef}
          isValidating={state.isValidating}
          isRefreshing={state.isRefreshing}
          onValidate={state.handleValidateClick}
          onReload={handleReload}
          onExport={state.handleExport}
          onImport={state.handleImport}
        />

        <ConfigurationOverview
          configuredProviders={state.configuredProviders}
          totalProviders={state.totalProviders}
          missingProviderCount={state.missingProviderCount}
          mainModel={state.modelsConfig.main.model}
          mainProvider={state.modelsConfig.main.provider}
          mainProviderConfigured={state.mainProviderConfigured}
          mainAgent={state.mainAgent}
          workspacePath={state.workspacePath}
          validationSummary={state.validationSummary}
          hasPendingChanges={state.hasPendingChanges}
          dirtySections={state.dirtySections}
          webSearchProvider={state.currentWebSearchConfig.provider}
          webSearchProviderName={state.selectedWebSearchProvider?.name || state.currentWebSearchConfig.provider}
          webSearchRequiresApiKey={Boolean(state.selectedWebSearchProvider?.requires_api_key)}
          webSearchHasApiKey={state.currentWebSearchConfig.hasApiKey}
          webSearchMaxResults={state.currentWebSearchConfig.maxResults}
        />

        {state.validationData && <ConfigCheckResult data={state.validationData} title="配置体检" />}

        {state.error && (
          <div className="fixed top-4 right-4 z-50 px-4 py-3 bg-accent-red/5 border border-accent-red/20 rounded-xl shadow-lg flex items-center gap-3 animate-slide-in-right">
            <div className="w-8 h-8 rounded-lg bg-accent-red/10 flex items-center justify-center flex-shrink-0">
              <svg className="h-5 w-5 text-accent-red" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <span className="text-sm font-medium text-surface-900">{state.error}</span>
            <button onClick={() => state.setError(null)} className="ml-2 p-1 hover:bg-surface-100 rounded-lg transition-colors">
              <svg className="h-4 w-4 text-surface-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {state.success && (
          <div className="fixed top-4 right-4 z-50 p-4 bg-white border-2 border-accent-emerald rounded-xl shadow-lg flex items-center gap-3 animate-slide-in-right">
            <div className="w-8 h-8 rounded-lg bg-accent-emerald/10 flex items-center justify-center flex-shrink-0">
              <svg className="h-5 w-5 text-accent-emerald" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <span className="text-sm font-medium text-surface-900">{state.success}</span>
            <button onClick={() => state.setSuccess(null)} className="ml-2 p-1 hover:bg-surface-100 rounded-lg transition-colors">
              <svg className="h-4 w-4 text-surface-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        <div id="config-agent" className="scroll-mt-24">
          <AgentConfigSection
            modelsConfig={state.modelsConfig}
            providerOptions={state.providerOptions}
            modelChanges={state.modelChanges}
            modelSaving={state.modelSaving}
            agentSettings={state.agentSettings}
          agentErrors={state.agentErrors}
          hasAgentChanges={state.hasAgentChanges}
          hasModelsChanges={state.hasModelsChanges}
          isSavingAgent={state.isSavingAgent}
          isSavingModels={state.isSavingModels}
          mainAgent={state.mainAgent}
          onUpdateModelConfig={state.updateModelConfig}
          onSaveModel={state.handleSaveModel}
          onSaveAgentSettings={state.handleSaveAgentSettings}
          onSaveModelsConfig={state.handleSaveModelsConfig}
            onAgentSettingsChange={(field, value) => {
              state.setAgentSettings((prev) => ({ ...prev, [field]: value }));
            }}
            clearFieldError={state.clearFieldError}
          />
        </div>

        <div id="config-workspace" className="scroll-mt-24">
          <WorkspaceConfigSection
          workspacePath={state.workspacePath}
          hasWorkspaceChanges={state.hasWorkspaceChanges}
          isSavingWorkspace={state.isSavingWorkspace}
          mainAgent={state.mainAgent}
          onWorkspacePathChange={state.setWorkspacePath}
          onSaveWorkspace={state.handleSaveWorkspace}
        />
        </div>

        <div id="config-web-search" className="scroll-mt-24">
          <WebSearchConfigSection
            currentWebSearchConfig={state.currentWebSearchConfig}
            selectedWebSearchProvider={state.selectedWebSearchProvider}
            webSearchProviders={state.webSearchProviders}
            isLoadingProviders={state.isLoadingProviders}
            hasWebSearchChanges={state.hasWebSearchChanges}
            canSaveWebSearch={state.canSaveWebSearch}
            isSavingWebSearch={state.isSavingWebSearch}
            onWebSearchChange={state.updateWebSearchConfig}
            onSaveWebSearch={state.handleSaveWebSearch}
          />
        </div>

        <div id="config-providers" className="scroll-mt-24">
          <ProviderConfigSection
            providers={state.config?.providers}
            onProviderAdded={state.handleProviderAdded}
            onProviderUpdated={() => state.refreshConfigFromServer()}
            onProviderDeleted={state.handleProviderDeleted}
            onError={(message) => state.setError(message)}
          />
        </div>
      </div>

      <ConfirmDialog
        isOpen={reloadConfirmOpen}
        title="放弃未保存修改？"
        message="当前页面还有未保存的配置更改。重新加载会丢弃这些本地修改。"
        confirmText="重新加载"
        cancelText="继续编辑"
        onConfirm={() => {
          setReloadConfirmOpen(false);
          void state.refreshConfigFromServer('配置已重新从磁盘加载');
        }}
        onCancel={() => setReloadConfirmOpen(false)}
        variant="warning"
      />
    </div>
  );
};

export default ConfigPage;
