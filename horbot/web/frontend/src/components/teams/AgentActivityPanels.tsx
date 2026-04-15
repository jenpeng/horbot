import type { TeamsPageAuditUrlState } from '../../pages/teams/selection';
import type { AgentInfo, AgentMemoryStats, AgentSkillInfo, AgentToolAuditBundle, ToolAuditRiskFilter } from '../../pages/teams/types';
import { useI18n } from '../../contexts/I18nContext';

interface AgentActivityPanelsProps {
  selectedAgent: AgentInfo;
  agentMemoryStats: AgentMemoryStats | null;
  agentSkills: AgentSkillInfo[];
  agentToolAudits: AgentToolAuditBundle | null;
  toolAuditState: TeamsPageAuditUrlState;
  toolAuditLoading: boolean;
  assetReady: boolean;
  assetLoading: boolean;
  reasoningStyleLabel: string | null;
  onToolAuditSessionKeyChange: (value: string) => void;
  onToolAuditRiskFilterChange: (value: ToolAuditRiskFilter) => void;
  onToolAuditWindowHoursChange: (value: number) => void;
  onLoadMoreToolAudits: () => void;
  onToolAuditFocus: () => void;
}

const AgentActivityPanels = ({
  selectedAgent,
  agentMemoryStats,
  agentSkills,
  agentToolAudits,
  toolAuditState,
  toolAuditLoading,
  assetReady,
  assetLoading,
  reasoningStyleLabel,
  onToolAuditSessionKeyChange,
  onToolAuditRiskFilterChange,
  onToolAuditWindowHoursChange,
  onLoadMoreToolAudits,
  onToolAuditFocus,
}: AgentActivityPanelsProps) => {
  const { t } = useI18n();
  const { sessionKey: toolAuditSessionKey, riskKind: toolAuditRiskFilter, windowHours: toolAuditWindowHours } = toolAuditState;
  const loadingLabels = [
    t('teams.agentActivity.memoryEntries'),
    t('teams.agentActivity.memorySize'),
    t('teams.agentActivity.skillCount'),
  ];
  const auditItems = agentToolAudits?.items || [];
  const auditSummary = agentToolAudits?.summary;
  const auditHasMore = (agentToolAudits?.total_matches || 0) > auditItems.length;
  const trimmedToolAuditSessionKey = toolAuditSessionKey.trim();
  const recentSessionKeys = Array.from(new Set([
    trimmedToolAuditSessionKey,
    agentToolAudits?.session_key?.trim() || '',
    ...auditItems.map((item) => item.audit_event?.session_key?.trim() || ''),
  ].filter(Boolean))).slice(0, 6);
  const windowButtons = [
    { hours: 24, label: t('teams.agentActivity.auditWindow24h') },
    { hours: 72, label: t('teams.agentActivity.auditWindow72h') },
    { hours: 168, label: t('teams.agentActivity.auditWindow7d') },
  ];
  const riskButtons: Array<{ key: ToolAuditRiskFilter; label: string; activeClass: string; idleClass: string }> = [
    {
      key: 'blocked',
      label: t('teams.agentActivity.auditSummaryBlocked', { count: auditSummary?.blocked_count || 0 }),
      activeClass: 'bg-amber-200 text-amber-900 ring-2 ring-amber-300',
      idleClass: 'bg-amber-100 text-amber-800 hover:bg-amber-200',
    },
    {
      key: 'exec',
      label: t('teams.agentActivity.auditSummaryExec', { count: auditSummary?.exec_count || 0 }),
      activeClass: 'bg-rose-200 text-rose-900 ring-2 ring-rose-300',
      idleClass: 'bg-rose-100 text-rose-700 hover:bg-rose-200',
    },
    {
      key: 'outbound',
      label: t('teams.agentActivity.auditSummaryOutbound', { count: auditSummary?.outbound_count || 0 }),
      activeClass: 'bg-sky-200 text-sky-900 ring-2 ring-sky-300',
      idleClass: 'bg-sky-100 text-sky-700 hover:bg-sky-200',
    },
    {
      key: 'error',
      label: t('teams.agentActivity.auditSummaryErrors', { count: auditSummary?.error_count || 0 }),
      activeClass: 'bg-slate-300 text-slate-900 ring-2 ring-slate-300',
      idleClass: 'bg-slate-100 text-slate-700 hover:bg-slate-200',
    },
  ];
  const formatTimestamp = (value?: string) => {
    if (!value) {
      return t('teams.agentActivity.auditNotAvailable');
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return value;
    }
    return parsed.toLocaleString();
  };
  return (
  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
    <div className="lg:col-span-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-surface-900">{t('teams.agentActivity.title')}</h3>
          <p className="mt-1 text-sm text-surface-500">{t('teams.agentActivity.subtitle')}</p>
        </div>
      </div>
    </div>
    <div className="bg-white rounded-2xl border border-surface-200 p-6 transition-shadow" data-focus-anchor="agent-runtime">
      <h3 className="text-lg font-semibold text-surface-900">{t('teams.agentActivity.runtimeTitle')}</h3>
      {assetReady ? (
        <div className="mt-4 space-y-3">
          <div className="rounded-xl bg-surface-50 p-4">
            <p className="text-xs uppercase tracking-wide text-surface-500">{t('teams.agentActivity.memoryEntries')}</p>
            <p className="mt-1 text-2xl font-bold text-surface-900">{agentMemoryStats?.total_entries ?? t('teams.agentActivity.notLoaded')}</p>
          </div>
          <div className="rounded-xl bg-surface-50 p-4">
            <p className="text-xs uppercase tracking-wide text-surface-500">{t('teams.agentActivity.memorySize')}</p>
            <p className="mt-1 text-2xl font-bold text-surface-900">
              {agentMemoryStats ? `${agentMemoryStats.total_size_kb} KB` : t('teams.agentActivity.notLoaded')}
            </p>
          </div>
          <div className="rounded-xl bg-surface-50 p-4">
            <p className="text-xs uppercase tracking-wide text-surface-500">{t('teams.agentActivity.skillCount')}</p>
            <p className="mt-1 text-2xl font-bold text-surface-900">{agentSkills.length}</p>
          </div>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          {loadingLabels.map((label) => (
            <div key={label} className="rounded-xl bg-surface-50 p-4">
              <div className="animate-pulse">
                <div className="h-3 w-20 rounded bg-surface-200" />
                <div className="mt-3 h-8 w-24 rounded bg-surface-200" />
              </div>
              <p className="mt-2 text-xs text-surface-500">
                {assetLoading ? t('teams.agentActivity.loadingMetric', { label }) : t('teams.agentActivity.waitingRuntime')}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>

    <div className="bg-white rounded-2xl border border-surface-200 p-6">
      <h3 className="text-lg font-semibold text-surface-900">{t('teams.agentActivity.skillsTitle')}</h3>
      {assetReady ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {agentSkills.length > 0 ? agentSkills.map((skill) => (
            <span
              key={`${skill.source}-${skill.name}`}
              className={`px-3 py-1.5 rounded-full text-xs font-medium ${
                skill.enabled ? 'bg-primary-100 text-primary-700' : 'bg-surface-100 text-surface-500'
              }`}
            >
              {skill.name}
              {skill.always ? ` · ${t('teams.agentActivity.always')}` : ''}
            </span>
          )) : (
            <p className="text-sm text-surface-500">{t('teams.agentActivity.noSkills')}</p>
          )}
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          <div className="flex flex-wrap gap-2 animate-pulse">
            {Array.from({ length: 4 }).map((_, index) => (
              <span key={index} className="h-8 w-24 rounded-full bg-surface-200" />
            ))}
          </div>
          <p className="text-xs text-surface-500">
            {assetLoading ? t('teams.agentActivity.loadingSkills') : t('teams.agentActivity.waitingSkills')}
          </p>
        </div>
      )}
    </div>

    <div className="bg-white rounded-2xl border border-surface-200 p-6 lg:col-span-3 transition-shadow" data-focus-anchor="agent-tool-audits">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-surface-900">{t('teams.agentActivity.auditTitle')}</h3>
          <p className="mt-1 text-sm text-surface-500">{t('teams.agentActivity.auditSubtitle')}</p>
        </div>
        {assetReady && agentToolAudits && (
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded-full bg-surface-100 px-3 py-1 text-surface-600">
              {t('teams.agentActivity.auditCount', { count: agentToolAudits.total_returned })}
            </span>
            <span className="rounded-full bg-amber-100 px-3 py-1 text-amber-700">
              {t('teams.agentActivity.auditBlockedCount', { count: agentToolAudits.blocked_count })}
            </span>
            <span className="rounded-full bg-rose-100 px-3 py-1 text-rose-700">
              {t('teams.agentActivity.auditErrorCount', { count: agentToolAudits.error_count })}
            </span>
          </div>
        )}
      </div>
      {assetReady && auditSummary && (
        <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50/70 px-4 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-700">
                {t('teams.agentActivity.auditSummaryTitle', { hours: auditSummary.window_hours })}
              </p>
              <p className="mt-1 text-sm text-amber-900">
                {t('teams.agentActivity.auditSummarySentence', {
                  hours: auditSummary.window_hours,
                  blocked: auditSummary.blocked_count,
                  exec: auditSummary.exec_count,
                  outbound: auditSummary.outbound_count,
                  errors: auditSummary.error_count,
                })}
              </p>
            </div>
            <div className="flex flex-wrap gap-2 text-xs font-medium">
              {riskButtons.map((button) => {
                const active = toolAuditRiskFilter === button.key;
                return (
                  <button
                    key={button.key}
                    type="button"
                    onClick={() => {
                      onToolAuditRiskFilterChange(active ? 'all' : button.key);
                      onToolAuditFocus();
                    }}
                    className={`rounded-full px-3 py-1 transition-colors ${active ? button.activeClass : button.idleClass}`}
                    aria-pressed={active}
                  >
                    {button.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap gap-2">
          {windowButtons.map((button) => {
            const active = toolAuditWindowHours === button.hours;
            return (
              <button
                key={button.hours}
                type="button"
                onClick={() => onToolAuditWindowHoursChange(button.hours)}
                className={`rounded-full px-3 py-1 text-xs transition-colors ${
                  active
                    ? 'bg-surface-900 text-white'
                    : 'bg-surface-100 text-surface-600 hover:bg-surface-200'
                }`}
                aria-pressed={active}
              >
                {button.label}
              </button>
            );
          })}
        </div>
        <input
          value={toolAuditSessionKey}
          onChange={(event) => onToolAuditSessionKeyChange(event.target.value)}
          placeholder={t('teams.agentActivity.auditSessionPlaceholder')}
          className="w-full max-w-md rounded-xl border border-surface-300 bg-white px-3 py-2 text-sm text-surface-800 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
        />
        {trimmedToolAuditSessionKey && (
          <button
            type="button"
            onClick={() => onToolAuditSessionKeyChange('')}
            className="rounded-xl border border-surface-300 px-3 py-2 text-sm text-surface-600 hover:bg-surface-50"
          >
            {t('teams.agentActivity.auditClearFilter')}
          </button>
        )}
        {toolAuditRiskFilter !== 'all' && (
          <button
            type="button"
            onClick={() => onToolAuditRiskFilterChange('all')}
            className="rounded-xl border border-surface-300 px-3 py-2 text-sm text-surface-600 hover:bg-surface-50"
          >
            {t('teams.agentActivity.auditClearRiskFilter')}
          </button>
        )}
      </div>
      {assetReady && recentSessionKeys.length > 0 && (
        <details className="mt-3 rounded-2xl border border-surface-200 bg-surface-50/80 px-4 py-3">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm text-surface-700">
            <div className="flex min-w-0 items-center gap-2">
              <span className="font-medium">{t('teams.agentActivity.auditRecentSessions')}</span>
              <span className="rounded-full bg-white px-2 py-0.5 text-xs text-surface-500 ring-1 ring-surface-200">
                {recentSessionKeys.length}
              </span>
              {trimmedToolAuditSessionKey && (
                <span className="truncate rounded-full bg-primary-50 px-2.5 py-1 text-xs text-primary-700 ring-1 ring-primary-200">
                  {trimmedToolAuditSessionKey}
                </span>
              )}
            </div>
            <span className="text-xs text-surface-500">{t('teams.agentActivity.auditSessionMenuHint')}</span>
          </summary>
          <div className="mt-3 grid gap-2 md:grid-cols-2">
            <button
              type="button"
              onClick={() => onToolAuditSessionKeyChange('')}
              className={`rounded-xl border px-3 py-2 text-left text-sm transition-colors ${
                trimmedToolAuditSessionKey
                  ? 'border-surface-200 bg-white text-surface-700 hover:bg-surface-50'
                  : 'border-surface-900 bg-surface-900 text-white'
              }`}
              aria-pressed={!trimmedToolAuditSessionKey}
            >
              {t('teams.agentActivity.auditAllSessions')}
            </button>
            {recentSessionKeys.map((sessionKey) => {
              const active = trimmedToolAuditSessionKey === sessionKey;
              return (
                <button
                  key={sessionKey}
                  type="button"
                  onClick={() => onToolAuditSessionKeyChange(active ? '' : sessionKey)}
                  className={`rounded-xl border px-3 py-2 text-left text-sm transition-colors ${
                    active
                      ? 'border-primary-500 bg-primary-600 text-white'
                      : 'border-primary-200 bg-white text-primary-700 hover:bg-primary-50'
                  }`}
                  aria-pressed={active}
                >
                  <span className="block truncate">{sessionKey}</span>
                </button>
              );
            })}
          </div>
        </details>
      )}
      {assetReady && toolAuditRiskFilter !== 'all' && (
        <div className="mt-3">
          <span className="rounded-full bg-surface-100 px-3 py-1 text-xs text-surface-600">
            {t('teams.agentActivity.auditFilteredBy', {
              label: t(`teams.agentActivity.auditFilterLabel.${toolAuditRiskFilter}`),
            })}
          </span>
        </div>
      )}
      {assetReady ? (
        auditItems.length > 0 ? (
          <div className="mt-4 space-y-3">
            {auditItems.map((item, index) => {
              const itemSessionKey = item.audit_event?.session_key?.trim() || '';
              const toneClass = item.guard_blocked
                ? 'border-amber-200 bg-amber-50'
                : item.error
                  ? 'border-rose-200 bg-rose-50'
                  : 'border-surface-200 bg-surface-50';
              const statusLabel = item.guard_blocked
                ? t('teams.agentActivity.auditStatusBlocked')
                : item.error
                  ? t('teams.agentActivity.auditStatusError')
                  : t('teams.agentActivity.auditStatusOk');
              return (
                <div
                  key={`${item.tool_name}-${item.timestamp}-${index}`}
                  className={`rounded-2xl border p-4 ${toneClass}`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-surface-700 ring-1 ring-surface-200">
                          {item.tool_name}
                        </span>
                        {itemSessionKey && (
                          <button
                            type="button"
                            onClick={() => onToolAuditSessionKeyChange(itemSessionKey)}
                            className="rounded-full bg-white px-3 py-1 text-xs font-medium text-primary-700 ring-1 ring-primary-200 hover:bg-primary-50"
                          >
                            {t('teams.agentActivity.auditSessionChip', { value: itemSessionKey })}
                          </button>
                        )}
                        <span className="text-xs text-surface-500">{statusLabel}</span>
                        {item.permission_level && (
                          <span className="text-xs text-surface-400">
                            {t('teams.agentActivity.auditPermission', { value: item.permission_level })}
                          </span>
                        )}
                      </div>
                      <p className="mt-2 text-sm text-surface-700">
                        {item.task || t('teams.agentActivity.auditNoTask')}
                      </p>
                    </div>
                    <div className="text-right text-xs text-surface-500">
                      <div>{formatTimestamp(item.timestamp)}</div>
                      <div>
                        {item.duration_ms != null
                          ? t('teams.agentActivity.auditDuration', { count: item.duration_ms })
                          : t('teams.agentActivity.auditNotAvailable')}
                      </div>
                    </div>
                  </div>
                  {item.guard_reasons && item.guard_reasons.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {item.guard_reasons.map((reason) => (
                        <span key={reason} className="rounded-full bg-white px-2.5 py-1 text-[11px] text-amber-700 ring-1 ring-amber-200">
                          {reason}
                        </span>
                      ))}
                    </div>
                  )}
                  {(item.error || item.result) && (
                    <div className="mt-3 rounded-xl bg-white/80 px-3 py-3 text-xs leading-6 text-surface-600 ring-1 ring-surface-200">
                      {item.error || item.result}
                    </div>
                  )}
                  <details className="mt-3 rounded-xl bg-white/70 px-3 py-2 ring-1 ring-surface-200">
                    <summary className="cursor-pointer text-xs font-medium text-surface-600">
                      {t('teams.agentActivity.auditRawJson')}
                    </summary>
                    <pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-all text-[11px] leading-5 text-surface-600">
                      {JSON.stringify(item.audit_event || item, null, 2)}
                    </pre>
                  </details>
                </div>
              );
            })}
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-dashed border-surface-200 bg-surface-50 px-4 py-3">
              <span className="text-xs text-surface-500">
                {t('teams.agentActivity.auditShowingCount', {
                  shown: auditItems.length,
                  total: agentToolAudits?.total_matches || auditItems.length,
                })}
              </span>
              {auditHasMore && (
                <button
                  type="button"
                  onClick={onLoadMoreToolAudits}
                  disabled={toolAuditLoading}
                  className="rounded-xl border border-surface-300 px-3 py-2 text-sm text-surface-700 hover:bg-white disabled:opacity-60"
                >
                  {toolAuditLoading ? t('teams.agentActivity.loadingAudits') : t('teams.agentActivity.auditLoadMore')}
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className="mt-4 rounded-2xl border border-dashed border-surface-200 bg-surface-50 px-4 py-8 text-center text-sm text-surface-500">
            {toolAuditRiskFilter === 'all'
              ? t('teams.agentActivity.auditEmpty')
              : t('teams.agentActivity.auditEmptyFiltered', {
                  label: t(`teams.agentActivity.auditFilterLabel.${toolAuditRiskFilter}`),
                })}
          </div>
        )
      ) : (
        <div className="mt-4 rounded-2xl border border-surface-200 bg-surface-50 p-4">
          <div className="animate-pulse">
            <div className="h-4 w-40 rounded bg-surface-200" />
            <div className="mt-3 h-16 rounded-xl bg-white/80 border border-surface-200" />
            <div className="mt-3 h-16 rounded-xl bg-white/80 border border-surface-200" />
          </div>
          <p className="mt-3 text-xs text-surface-500">
            {toolAuditLoading || assetLoading ? t('teams.agentActivity.loadingAudits') : t('teams.agentActivity.waitingAudits')}
          </p>
        </div>
      )}
    </div>

    <div className="bg-white rounded-2xl border border-surface-200 p-6 lg:col-span-3 transition-shadow">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-surface-900">{t('teams.agentActivity.memoryProfileTitle')}</h3>
          <p className="mt-1 text-sm text-surface-500">{t('teams.agentActivity.memoryProfileSubtitle')}</p>
        </div>
        {reasoningStyleLabel && (
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
            {reasoningStyleLabel}
          </span>
        )}
      </div>
      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4">
          <div className="text-xs font-medium uppercase tracking-wide text-surface-500">Mission</div>
          <div className="mt-2 text-sm text-surface-800">
            {selectedAgent.memory_bank_profile?.mission || t('teams.agentActivity.memoryMissionFallback')}
          </div>
        </div>
        <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4 md:col-span-2">
          <div className="flex items-center justify-between gap-3">
            <div className="text-xs font-medium uppercase tracking-wide text-surface-500">Directives</div>
            <span className="text-xs text-surface-500">{t('teams.agentActivity.directiveCount', { count: selectedAgent.memory_bank_profile?.directives?.length || 0 })}</span>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {(selectedAgent.memory_bank_profile?.directives || []).length > 0 ? (
              (selectedAgent.memory_bank_profile?.directives || []).map((directive) => (
                <span key={directive} className="rounded-full bg-white px-3 py-1.5 text-xs text-surface-700 ring-1 ring-surface-200">
                  {directive}
                </span>
              ))
            ) : (
              <p className="text-sm text-surface-500">{t('teams.agentActivity.directivesFallback')}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  </div>
  );
};

export default AgentActivityPanels;
