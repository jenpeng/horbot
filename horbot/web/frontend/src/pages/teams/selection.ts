import type { TeamsPageFocusTarget, TeamsPageSelection, ToolAuditRiskFilter } from './types';

const TOOL_AUDIT_RISK_FILTERS: ToolAuditRiskFilter[] = ['all', 'blocked', 'exec', 'outbound', 'error'];
export const TOOL_AUDIT_WINDOW_OPTIONS = [24, 72, 168] as const;
export const TOOL_AUDIT_DEFAULT_WINDOW_HOURS = 24;
export const TOOL_AUDIT_DEFAULT_LIMIT = 12;
export const TOOL_AUDIT_LIMIT_STEP = 12;
export const TOOL_AUDIT_LIMIT_MAX = 96;
const FOCUS_TARGETS: TeamsPageFocusTarget[] = [
  'agent-overview',
  'agent-runtime',
  'agent-tool-audits',
  'agent-summary',
  'agent-files',
  'agent-file-agents',
  'agent-file-soul',
  'agent-file-user',
  'team-overview',
  'team-members',
  'team-workspace',
  'team-collaboration',
];

export interface TeamsPageAuditUrlState {
  sessionKey: string;
  riskKind: ToolAuditRiskFilter;
  windowHours: number;
  limit: number;
}

interface TeamsPageAuditStateInput {
  sessionKey?: string | null;
  riskKind?: ToolAuditRiskFilter | string | null;
  windowHours?: number | string | null;
  limit?: number | string | null;
}

export const createDefaultToolAuditState = (): TeamsPageAuditUrlState => ({
  sessionKey: '',
  riskKind: 'all',
  windowHours: TOOL_AUDIT_DEFAULT_WINDOW_HOURS,
  limit: TOOL_AUDIT_DEFAULT_LIMIT,
});

const isFocusCompatibleWithSelection = (
  selection: TeamsPageSelection | null,
  focusTarget: TeamsPageFocusTarget | null | undefined,
) => {
  if (!selection?.id || !focusTarget) {
    return false;
  }
  if (selection.kind === 'agent') {
    return focusTarget.startsWith('agent-');
  }
  if (selection.kind === 'team') {
    return focusTarget.startsWith('team-');
  }
  return false;
};

export const normalizeToolAuditRiskKind = (value: string | null | undefined): ToolAuditRiskFilter => {
  const normalized = String(value || '').trim().toLowerCase();
  return TOOL_AUDIT_RISK_FILTERS.includes(normalized as ToolAuditRiskFilter)
    ? normalized as ToolAuditRiskFilter
    : 'all';
};

export const normalizeToolAuditWindowHours = (value: string | number | null | undefined): number => {
  const parsed = Number.parseInt(String(value || '').trim(), 10);
  return TOOL_AUDIT_WINDOW_OPTIONS.includes(parsed as typeof TOOL_AUDIT_WINDOW_OPTIONS[number])
    ? parsed
    : TOOL_AUDIT_DEFAULT_WINDOW_HOURS;
};

export const normalizeToolAuditLimit = (value: string | number | null | undefined): number => {
  const parsed = Number.parseInt(String(value || '').trim(), 10);
  if (!Number.isFinite(parsed) || parsed < TOOL_AUDIT_DEFAULT_LIMIT) {
    return TOOL_AUDIT_DEFAULT_LIMIT;
  }
  const normalized = Math.min(parsed, TOOL_AUDIT_LIMIT_MAX);
  return normalized - (normalized % TOOL_AUDIT_LIMIT_STEP) || TOOL_AUDIT_DEFAULT_LIMIT;
};

export const normalizeToolAuditState = (
  state?: TeamsPageAuditStateInput | null,
): TeamsPageAuditUrlState => ({
  sessionKey: String(state?.sessionKey || '').trim(),
  riskKind: normalizeToolAuditRiskKind(state?.riskKind),
  windowHours: normalizeToolAuditWindowHours(state?.windowHours),
  limit: normalizeToolAuditLimit(state?.limit),
});

export const buildToolAuditQueryParams = (
  agentId: string,
  state?: TeamsPageAuditStateInput | null,
): URLSearchParams => {
  const normalized = normalizeToolAuditState(state);
  const params = new URLSearchParams({
    agent_id: agentId,
    limit: String(normalized.limit),
    window_hours: String(normalized.windowHours),
  });
  if (normalized.sessionKey) {
    params.set('session_key', normalized.sessionKey);
  }
  if (normalized.riskKind !== 'all') {
    params.set('risk_kind', normalized.riskKind);
  }
  return params;
};

export const readSelectionFromUrl = (): TeamsPageSelection | null => {
  if (typeof window === 'undefined') {
    return null;
  }

  const params = new URLSearchParams(window.location.search);
  const agentId = params.get('agent')?.trim();
  if (agentId) {
    return { kind: 'agent', id: agentId };
  }

  const teamId = params.get('team')?.trim();
  if (teamId) {
    return { kind: 'team', id: teamId };
  }

  const externalAgentId = params.get('externalAgent')?.trim();
  if (externalAgentId) {
    return { kind: 'external-agent', id: externalAgentId };
  }

  return null;
};

export const readToolAuditStateFromUrl = (): TeamsPageAuditUrlState => {
  if (typeof window === 'undefined') {
    return createDefaultToolAuditState();
  }

  const params = new URLSearchParams(window.location.search);
  return normalizeToolAuditState({
    sessionKey: params.get('auditSession')?.trim() || '',
    riskKind: params.get('auditRisk'),
    windowHours: params.get('auditWindow'),
    limit: params.get('auditLimit'),
  });
};

export const readFocusFromUrl = (): TeamsPageFocusTarget | null => {
  if (typeof window === 'undefined') {
    return null;
  }

  const focus = new URLSearchParams(window.location.search).get('focus')?.trim();
  if (!focus) {
    return null;
  }

  return FOCUS_TARGETS.includes(focus as TeamsPageFocusTarget)
    ? (focus as TeamsPageFocusTarget)
    : null;
};

export const writeSelectionToUrl = (
  selection: TeamsPageSelection | null,
  auditState?: TeamsPageAuditUrlState | null,
  focusTarget?: TeamsPageFocusTarget | null,
): void => {
  if (typeof window === 'undefined') {
    return;
  }

  const url = new URL(window.location.href);
  url.searchParams.delete('agent');
  url.searchParams.delete('team');
  url.searchParams.delete('externalAgent');
  url.searchParams.delete('focus');
  url.searchParams.delete('auditSession');
  url.searchParams.delete('auditRisk');
  url.searchParams.delete('auditWindow');
  url.searchParams.delete('auditLimit');

  if (selection?.kind === 'agent' && selection.id) {
    const normalizedAuditState = normalizeToolAuditState(auditState);
    url.searchParams.set('agent', selection.id);
    if (normalizedAuditState.sessionKey) {
      url.searchParams.set('auditSession', normalizedAuditState.sessionKey);
    }
    if (normalizedAuditState.riskKind !== 'all') {
      url.searchParams.set('auditRisk', normalizedAuditState.riskKind);
    }
    if (normalizedAuditState.windowHours !== TOOL_AUDIT_DEFAULT_WINDOW_HOURS) {
      url.searchParams.set('auditWindow', String(normalizedAuditState.windowHours));
    }
    if (normalizedAuditState.limit !== TOOL_AUDIT_DEFAULT_LIMIT) {
      url.searchParams.set('auditLimit', String(normalizedAuditState.limit));
    }
  } else if (selection?.kind === 'team' && selection.id) {
    url.searchParams.set('team', selection.id);
  } else if (selection?.kind === 'external-agent' && selection.id) {
    url.searchParams.set('externalAgent', selection.id);
  }

  if (isFocusCompatibleWithSelection(selection, focusTarget)) {
    url.searchParams.set('focus', focusTarget!);
  }

  const nextUrl = `${url.pathname}${url.search}${url.hash}`;
  window.history.replaceState(null, '', nextUrl);
};
