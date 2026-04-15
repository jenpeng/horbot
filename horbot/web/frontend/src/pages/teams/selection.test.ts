import { afterEach, describe, expect, it } from 'vitest';
import {
  buildToolAuditQueryParams,
  normalizeToolAuditState,
  readToolAuditStateFromUrl,
  writeSelectionToUrl,
} from './selection';

describe('teams selection helpers', () => {
  afterEach(() => {
    window.history.replaceState({}, '', '/teams');
  });

  it('normalizes tool audit state and builds backend query params', () => {
    const auditState = normalizeToolAuditState({
      sessionKey: '  web:demo  ',
      riskKind: 'EXEC' as any,
      windowHours: '25' as any,
      limit: '110' as any,
    });

    expect(auditState).toEqual({
      sessionKey: 'web:demo',
      riskKind: 'exec',
      windowHours: 24,
      limit: 96,
    });
    expect(buildToolAuditQueryParams('agent-1', auditState).toString()).toBe(
      'agent_id=agent-1&limit=96&window_hours=24&session_key=web%3Ademo&risk_kind=exec',
    );
  });

  it('hydrates normalized tool audit state from the url', () => {
    window.history.replaceState({}, '', '/teams?agent=agent-a&auditSession=%20web%3Ademo%20&auditRisk=EXEC&auditWindow=72&auditLimit=25');

    expect(readToolAuditStateFromUrl()).toEqual({
      sessionKey: 'web:demo',
      riskKind: 'exec',
      windowHours: 72,
      limit: 24,
    });
  });

  it('writes normalized audit state into the url and omits defaults', () => {
    window.history.replaceState({}, '', '/teams');

    writeSelectionToUrl(
      { kind: 'agent', id: 'agent-a' },
      {
        sessionKey: '  web:demo ',
        riskKind: 'all',
        windowHours: 72,
        limit: 25,
      },
      'agent-tool-audits',
    );

    expect(window.location.search).toBe(
      '?agent=agent-a&auditSession=web%3Ademo&auditWindow=72&auditLimit=24&focus=agent-tool-audits',
    );
  });
});
