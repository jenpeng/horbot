import { useI18n } from '../../../contexts/I18nContext';
import type { ExternalAgentInfo } from '../../../pages/teams/types';

interface ExternalAgentDetailViewProps {
  externalAgent: ExternalAgentInfo;
  onEdit: () => void;
  onDelete: () => void;
  onTest: () => void;
  getBadgeClassName: (tone: string, size?: 'sm' | 'md') => string;
  testFeedback: {
    tone: 'success' | 'warning';
    summary: string;
    detail: string;
  } | null;
}

const ExternalAgentDetailView = ({
  externalAgent,
  onEdit,
  onDelete,
  onTest,
  getBadgeClassName,
  testFeedback,
}: ExternalAgentDetailViewProps) => {
  const { t } = useI18n();
  const inbound = externalAgent.inbound || null;
  const inboundBotAdapter = ['inbound-bot', 'channel-backed-agent', 'web-ui-bridge'].includes(externalAgent.adapter || '');
  const inboundUrl = inbound?.url_path && typeof window !== 'undefined'
    ? `${window.location.origin.replace(/:3000$/, ':8000')}${inbound.url_path}`
    : inbound?.url_path || '';

  return (
    <div className="space-y-6" data-testid="external-agent-detail-view" data-external-agent-id={externalAgent.id}>
      <div className="rounded-3xl border border-surface-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-2xl font-semibold text-surface-900">{externalAgent.name}</h2>
              <span className={getBadgeClassName('neutral', 'sm')}>{externalAgent.adapter || 'generic-agent-api'}</span>
              {!inboundBotAdapter && <span className={getBadgeClassName('primary', 'sm')}>{externalAgent.transport}</span>}
              {externalAgent.dm_enabled && <span className={getBadgeClassName('success', 'sm')}>{t('teams.external.badge.dm')}</span>}
              {externalAgent.team_enabled && <span className={getBadgeClassName('neutral', 'sm')}>{t('teams.external.badge.team')}</span>}
            </div>
            <p className="mt-2 text-sm text-surface-600">{externalAgent.description || t('teams.external.emptyDescription')}</p>
            <p className="mt-3 break-all text-sm text-surface-500">{inboundBotAdapter ? inboundUrl : (externalAgent.endpoint || t('common.notAvailable'))}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={onTest}
              className="rounded-lg border border-primary-200 bg-primary-50 px-4 py-2 text-sm font-medium text-primary-700 hover:bg-primary-100"
            >
              {t('teams.external.actions.test')}
            </button>
            <button
              onClick={onEdit}
              className="rounded-lg border border-surface-300 px-4 py-2 text-sm font-medium text-surface-700 hover:bg-surface-50"
            >
              {t('common.edit')}
            </button>
            <button
              onClick={onDelete}
              className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100"
            >
              {t('common.delete')}
            </button>
          </div>
        </div>
        {testFeedback && (
          <div className={`mt-4 rounded-2xl border px-4 py-3 text-sm ${
            testFeedback.tone === 'success'
              ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
              : 'border-amber-200 bg-amber-50 text-amber-900'
          }`}>
            <div className="font-medium">{testFeedback.summary}</div>
            <div className="mt-1">{testFeedback.detail}</div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="rounded-2xl border border-surface-200 bg-white p-5 shadow-sm xl:col-span-2">
          <h3 className="text-base font-semibold text-surface-900">{t('teams.external.sections.connection')}</h3>
          <dl className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-surface-500">{t('teams.external.fields.adapter')}</dt>
              <dd className="mt-1 text-sm text-surface-900">{externalAgent.adapter || 'generic-agent-api'}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-surface-500">{t('teams.external.fields.transport')}</dt>
              <dd className="mt-1 text-sm text-surface-900">
                {inboundBotAdapter ? t('teams.external.adapter.inboundBot') : externalAgent.transport}
              </dd>
            </div>
            {!inboundBotAdapter && (
            <>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-surface-500">{t('teams.external.fields.authType')}</dt>
              <dd className="mt-1 text-sm text-surface-900">{externalAgent.auth_type}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-surface-500">{t('teams.external.fields.authHeader')}</dt>
              <dd className="mt-1 text-sm text-surface-900">{externalAgent.auth_header || t('common.notAvailable')}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-surface-500">{t('teams.external.fields.authSecret')}</dt>
              <dd className="mt-1 text-sm text-surface-900">
                {externalAgent.auth_secret_configured ? t('teams.external.status.secretConfigured') : t('teams.external.status.secretNotConfigured')}
              </dd>
            </div>
            </>
            )}
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-surface-500">{t('teams.external.fields.timeout')}</dt>
              <dd className="mt-1 text-sm text-surface-900">{t('teams.external.value.seconds', { count: externalAgent.timeout_s })}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-surface-500">{t('teams.external.fields.maxTurnChars')}</dt>
              <dd className="mt-1 text-sm text-surface-900">{externalAgent.max_turn_chars}</dd>
            </div>
          </dl>
          {inbound && (
            <div className="mt-5 rounded-2xl border border-emerald-200 bg-emerald-50/80 p-4">
              <div className="text-sm font-semibold text-emerald-900">{t('teams.external.form.inboundBotTitle')}</div>
              <p className="mt-1 text-xs text-emerald-800">{t('teams.external.form.inboundBotHint')}</p>
              <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-3">
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700">App ID</div>
                  <div className="mt-1 break-all rounded-lg bg-white px-3 py-2 font-mono text-xs text-surface-800 ring-1 ring-emerald-100">{inbound.app_id}</div>
                </div>
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700">Token</div>
                  <div className="mt-1 break-all rounded-lg bg-white px-3 py-2 font-mono text-xs text-surface-800 ring-1 ring-emerald-100">{inbound.token}</div>
                </div>
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700">Inbound URL</div>
                  <div className="mt-1 break-all rounded-lg bg-white px-3 py-2 font-mono text-xs text-surface-800 ring-1 ring-emerald-100">{inboundUrl}</div>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-surface-200 bg-white p-5 shadow-sm">
          <h3 className="text-base font-semibold text-surface-900">{t('teams.external.sections.accessPolicy')}</h3>
          <div className="mt-4 space-y-3 text-sm text-surface-700">
            <div className="flex items-center justify-between gap-3">
              <span>{t('teams.external.fields.dmEnabled')}</span>
              <span className={getBadgeClassName(externalAgent.dm_enabled ? 'success' : 'warning', 'sm')}>
                {externalAgent.dm_enabled ? t('common.online') : t('common.notAvailable')}
              </span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span>{t('teams.external.fields.teamEnabled')}</span>
              <span className={getBadgeClassName(externalAgent.team_enabled ? 'success' : 'warning', 'sm')}>
                {externalAgent.team_enabled ? t('common.online') : t('common.notAvailable')}
              </span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span>{t('teams.external.fields.mentionRequired')}</span>
              <span className={getBadgeClassName(externalAgent.mention_required ? 'primary' : 'neutral', 'sm')}>
                {externalAgent.mention_required ? t('teams.external.status.required') : t('teams.external.status.optional')}
              </span>
            </div>
            <div className="border-t border-surface-100 pt-3">
              <div className="text-xs uppercase tracking-wide text-surface-500">{t('teams.external.fields.contextScope')}</div>
              <div className="mt-1 text-sm text-surface-900">{externalAgent.context_scope}</div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wide text-surface-500">{t('teams.external.fields.memoryAccess')}</div>
              <div className="mt-1 text-sm text-surface-900">{externalAgent.memory_access}</div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wide text-surface-500">{t('teams.external.fields.fileAccess')}</div>
              <div className="mt-1 text-sm text-surface-900">{externalAgent.file_access}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-surface-200 bg-white p-5 shadow-sm">
        <h3 className="text-base font-semibold text-surface-900">{t('teams.external.sections.capabilities')}</h3>
        <div className="mt-4 flex flex-wrap gap-2">
          {externalAgent.capabilities.length > 0 ? externalAgent.capabilities.map((capability) => (
            <span key={capability} className="rounded-full bg-surface-100 px-2.5 py-1 text-xs font-medium text-surface-700 ring-1 ring-surface-200">
              {capability}
            </span>
          )) : (
            <span className="text-sm text-surface-500">{t('teams.external.noCapabilities')}</span>
          )}
        </div>
        <div className="mt-4 rounded-2xl border border-dashed border-surface-200 bg-surface-50 px-4 py-3 text-sm text-surface-600">
          {t('teams.external.phaseNotice')}
        </div>
      </div>
    </div>
  );
};

export default ExternalAgentDetailView;
