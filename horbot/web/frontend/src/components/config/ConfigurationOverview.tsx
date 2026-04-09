import React from 'react';
import { Link } from 'react-router-dom';
import { Card } from '../ui/Card';
import type {
  ConfigurationSectionKey,
  ConfigurationValidationSummary,
  MainAgentSummary,
} from '../../hooks/useConfigurationState';

interface ConfigurationOverviewProps {
  configuredProviders: number;
  totalProviders: number;
  missingProviderCount: number;
  mainModel: string;
  mainProvider: string;
  mainProviderConfigured: boolean;
  mainAgent: MainAgentSummary | null;
  workspacePath: string;
  validationSummary: ConfigurationValidationSummary | null;
  hasPendingChanges: boolean;
  dirtySections: ConfigurationSectionKey[];
  webSearchProvider: string;
  webSearchProviderName: string;
  webSearchRequiresApiKey: boolean;
  webSearchHasApiKey: boolean;
  webSearchMaxResults: number;
}

const SECTION_META: Record<ConfigurationSectionKey, { label: string; href: string }> = {
  agent: { label: '运行参数', href: '#config-agent' },
  workspace: { label: '工作区默认值', href: '#config-workspace' },
  'web-search': { label: 'Web Search', href: '#config-web-search' },
};

const toneBadgeClass: Record<NonNullable<ConfigurationValidationSummary>['tone'], string> = {
  ok: 'bg-accent-emerald/15 text-accent-emerald',
  warning: 'bg-accent-orange/15 text-accent-orange',
  error: 'bg-accent-red/15 text-accent-red',
};

const ConfigurationOverview: React.FC<ConfigurationOverviewProps> = ({
  configuredProviders,
  totalProviders,
  missingProviderCount,
  mainProviderConfigured,
  mainAgent,
  workspacePath,
  validationSummary,
  hasPendingChanges,
  dirtySections,
  webSearchProvider,
  webSearchProviderName,
  webSearchRequiresApiKey,
  webSearchHasApiKey,
  webSearchMaxResults,
}) => {
  const webSearchStatus = webSearchRequiresApiKey
    ? webSearchHasApiKey
      ? '已配置搜索密钥'
      : '缺少搜索密钥'
    : '无需 API Key';

  return (
    <Card padding="md" variant="gradient" gradient="primary" className="shadow-md">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="text-xl font-bold text-surface-900">配置总览</h2>
            {validationSummary && (
              <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${toneBadgeClass[validationSummary.tone]}`}>
                {validationSummary.label}
              </span>
            )}
            <span
              className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${
                hasPendingChanges
                  ? 'bg-accent-orange/15 text-accent-orange'
                  : 'bg-accent-emerald/15 text-accent-emerald'
              }`}
            >
              {hasPendingChanges ? '存在未保存修改' : '所有配置已同步'}
            </span>
          </div>
          <p className="mt-2 text-sm text-surface-600">
            这里配置的是 horbot 的全局级参数与 Provider 资产。Agent 的 provider、model 与职责配置请在多 Agent 管理页维护。
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap justify-end">
          <a href="#config-agent" className="rounded-full bg-white/80 px-3 py-1.5 text-xs font-semibold text-surface-700 shadow-sm transition hover:bg-white">
            跳到运行参数
          </a>
          <a href="#config-workspace" className="rounded-full bg-white/80 px-3 py-1.5 text-xs font-semibold text-surface-700 shadow-sm transition hover:bg-white">
            跳到默认工作区
          </a>
          <a href="#config-web-search" className="rounded-full bg-white/80 px-3 py-1.5 text-xs font-semibold text-surface-700 shadow-sm transition hover:bg-white">
            跳到 Web Search
          </a>
          <a href="#config-providers" className="rounded-full bg-white/80 px-3 py-1.5 text-xs font-semibold text-surface-700 shadow-sm transition hover:bg-white">
            跳到 Providers
          </a>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-white/70 bg-white/80 p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-surface-500">未保存区块</p>
          <p className="mt-2 text-2xl font-bold text-surface-900">{dirtySections.length}</p>
          <p className="mt-1 text-sm text-surface-600">
            {dirtySections.length > 0 ? '建议优先处理这些本地修改。' : '当前没有待保存的本地变更。'}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {dirtySections.length > 0 ? (
              dirtySections.map((section) => (
                <a
                  key={section}
                  href={SECTION_META[section].href}
                  className="rounded-full bg-accent-orange/12 px-2.5 py-1 text-xs font-semibold text-accent-orange transition hover:bg-accent-orange/20"
                >
                  {SECTION_META[section].label}
                </a>
              ))
            ) : (
              <span className="rounded-full bg-accent-emerald/12 px-2.5 py-1 text-xs font-semibold text-accent-emerald">
                已同步
              </span>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-white/70 bg-white/80 p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-surface-500">Agent 配置入口</p>
          <p className="mt-2 text-sm font-semibold text-surface-900 break-words">provider / model 已迁移到多 Agent 管理</p>
          <p className="mt-2 text-sm text-surface-600">
            当前默认打开的 Agent: <span className="font-semibold text-surface-900">{mainAgent ? `${mainAgent.name} (${mainAgent.id})` : '未选择'}</span>
          </p>
          <span
            className={`mt-3 inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${
              mainProviderConfigured
                ? 'bg-accent-emerald/12 text-accent-emerald'
                : 'bg-accent-orange/12 text-accent-orange'
            }`}
          >
            {mainProviderConfigured ? 'Provider 资产已就绪' : '请检查 Provider 资产是否齐全'}
          </span>
        </div>

        <div className="rounded-2xl border border-white/70 bg-white/80 p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-surface-500">Web Search</p>
          <p className="mt-2 text-sm font-semibold text-surface-900">{webSearchProviderName || webSearchProvider || '未设置搜索 Provider'}</p>
          <p className="mt-2 text-sm text-surface-600">
            返回条数: <span className="font-semibold text-surface-900">{webSearchMaxResults}</span>
          </p>
          <span
            className={`mt-3 inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${
              webSearchRequiresApiKey && !webSearchHasApiKey
                ? 'bg-accent-red/12 text-accent-red'
                : 'bg-accent-emerald/12 text-accent-emerald'
            }`}
          >
            {webSearchStatus}
          </span>
        </div>

        <div className="rounded-2xl border border-white/70 bg-white/80 p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-surface-500">Provider 覆盖率</p>
          <p className="mt-2 text-2xl font-bold text-surface-900">
            {configuredProviders} <span className="text-base font-semibold text-surface-500">/ {totalProviders}</span>
          </p>
          <p className="mt-1 text-sm text-surface-600">
            {missingProviderCount > 0
              ? `还有 ${missingProviderCount} 个 Provider 未配置密钥。`
              : '当前所有已登记 Provider 都已配置密钥。'}
          </p>
          <a
            href="#config-providers"
            className="mt-3 inline-flex rounded-full bg-primary-50 px-2.5 py-1 text-xs font-semibold text-primary-700 transition hover:bg-primary-100"
          >
            前往检查 Provider
          </a>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_auto]">
        <div className="rounded-2xl border border-white/60 bg-white/70 px-4 py-3 text-sm text-surface-600">
          <div>
            <span className="font-semibold text-surface-900">全局默认工作区：</span>
            <span className="break-all"> {workspacePath || '.horbot/agents/default/workspace'}</span>
          </div>
          {mainAgent && (
            <div className="mt-2">
              <span className="font-semibold text-surface-900">当前 Agent 实际工作区：</span>
              <span className="break-all"> {mainAgent.effectiveWorkspace || workspacePath || '.horbot/agents/default/workspace'}</span>
            </div>
          )}
        </div>
        <div className="flex items-stretch">
          <Link
            to="/teams"
            className="inline-flex items-center justify-center rounded-2xl bg-surface-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-surface-800"
          >
            前往多 Agent 管理
          </Link>
        </div>
      </div>
    </Card>
  );
};

export default ConfigurationOverview;
