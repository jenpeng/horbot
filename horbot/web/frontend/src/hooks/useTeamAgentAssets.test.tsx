import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useTeamAgentAssets } from './useTeamAgentAssets';

const createJsonResponse = (data: unknown, ok = true, url = '/api/test'): Response => ({
  ok,
  url,
  headers: new Headers({ 'content-type': 'application/json' }),
  json: vi.fn().mockResolvedValue(data),
  text: vi.fn().mockResolvedValue(JSON.stringify(data)),
} as unknown as Response);

const createHtmlResponse = (html: string, ok = true, url = '/api/test'): Response => ({
  ok,
  url,
  headers: new Headers({ 'content-type': 'text/html' }),
  json: vi.fn().mockRejectedValue(new Error('Unexpected token <')),
  text: vi.fn().mockResolvedValue(html),
} as unknown as Response);

describe('useTeamAgentAssets', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.history.replaceState({}, '', '/teams');
  });

  it('loads selected agent assets, memory stats, and skills', async () => {
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/agents/agent-1/bootstrap-files') {
        return Promise.resolve(createJsonResponse({
          workspace_path: '/tmp/workspace',
          summary: {
            identity: ['Lead engineer'],
          },
          files: {
            agents: { path: 'AGENTS.md', exists: true, content: 'Agents content' },
            soul: { path: 'SOUL.md', exists: true, content: 'Soul content' },
            user: { path: 'USER.md', exists: true, content: 'User content' },
          },
        }));
      }
      if (url === '/api/memory?agent_id=agent-1') {
        return Promise.resolve(createJsonResponse({
          total_entries: 12,
          total_size_kb: 48,
        }));
      }
      if (url === '/api/skills?agent_id=agent-1') {
        return Promise.resolve(createJsonResponse({
          skills: [{ name: 'debugger', source: 'user', enabled: true }],
        }));
      }
      if (url === '/api/memory/tool-audits?agent_id=agent-1&limit=12&window_hours=24') {
        return Promise.resolve(createJsonResponse({
          agent_id: 'agent-1',
          session_key: null,
          risk_kind: 'all',
          window_hours: 24,
          limit: 12,
          total_returned: 1,
          total_matches: 1,
          blocked_count: 0,
          error_count: 0,
          summary: {
            window_hours: 24,
            total_count: 1,
            blocked_count: 0,
            error_count: 0,
            exec_count: 0,
            outbound_count: 0,
          },
          items: [
            {
              type: 'tool_audit',
              tool_name: 'read_file',
              task: 'tool:read_file',
              timestamp: '2026-04-14T10:00:00',
              guard_blocked: false,
            },
          ],
        }));
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    const { result } = renderHook(() => useTeamAgentAssets({ selectedAgentId: 'agent-1' }));

    await waitFor(() => {
      expect(result.current.assetLoading).toBe(false);
    });

    expect(result.current.agentAssets?.workspace_path).toBe('/tmp/workspace');
    expect(result.current.assetDrafts.agents).toBe('Agents content');
    expect(result.current.assetDrafts.soul).toBe('Soul content');
    expect(result.current.summaryDrafts.identity).toBe('Lead engineer');
    expect(result.current.agentMemoryStats).toEqual({
      total_entries: 12,
      total_size_kb: 48,
    });
    expect(result.current.agentSkills).toEqual([
      { name: 'debugger', source: 'user', enabled: true },
    ]);
    expect(result.current.agentToolAudits?.total_returned).toBe(1);
    expect(result.current.toolAuditState.sessionKey).toBe('');
    expect(result.current.assetLoadedAgentId).toBe('agent-1');
  });

  it('saves an asset file and refreshes the bootstrap content', async () => {
    const onSaved = vi.fn();
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method || 'GET';

      if (url === '/api/agents/agent-1/bootstrap-files' && method === 'GET') {
        return Promise.resolve(createJsonResponse({
          workspace_path: '/tmp/workspace',
          summary: {},
          files: {
            agents: { path: 'AGENTS.md', exists: true, content: 'Updated agents' },
            soul: { path: 'SOUL.md', exists: true, content: 'Updated soul' },
            user: { path: 'USER.md', exists: true, content: 'User content' },
          },
        }));
      }
      if (url === '/api/memory?agent_id=agent-1') {
        return Promise.resolve(createJsonResponse({
          total_entries: 1,
          total_size_kb: 2,
        }));
      }
      if (url === '/api/skills?agent_id=agent-1') {
        return Promise.resolve(createJsonResponse({
          skills: [],
        }));
      }
      if (url === '/api/memory/tool-audits?agent_id=agent-1&limit=12&window_hours=24') {
        return Promise.resolve(createJsonResponse({
          agent_id: 'agent-1',
          session_key: null,
          risk_kind: 'all',
          window_hours: 24,
          limit: 12,
          total_returned: 0,
          total_matches: 0,
          blocked_count: 0,
          error_count: 0,
          summary: {
            window_hours: 24,
            total_count: 0,
            blocked_count: 0,
            error_count: 0,
            exec_count: 0,
            outbound_count: 0,
          },
          items: [],
        }));
      }
      if (url === '/api/agents/agent-1/bootstrap-files/soul' && method === 'PUT') {
        return Promise.resolve(createJsonResponse({ ok: true }));
      }
      throw new Error(`Unhandled fetch: ${method} ${url}`);
    });

    const { result } = renderHook(() => useTeamAgentAssets({
      selectedAgentId: 'agent-1',
      onSaved,
    }));

    await waitFor(() => {
      expect(result.current.assetLoading).toBe(false);
    });

    await act(async () => {
      result.current.handleAssetDraftChange('soul', 'Fresh soul content');
    });

    await act(async () => {
      await result.current.handleSaveAssetFile('soul');
    });

    expect(fetch).toHaveBeenCalledWith('/api/agents/agent-1/bootstrap-files/soul', expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify({ content: 'Fresh soul content' }),
    }));
    expect(onSaved).toHaveBeenCalledTimes(1);
    expect(result.current.assetDrafts.soul).toBe('Updated soul');
    expect(result.current.assetSuccess).toBe('SOUL.md 已保存');
  });

  it('reloads tool audits when session key filter changes', async () => {
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/agents/agent-1/bootstrap-files') {
        return Promise.resolve(createJsonResponse({
          workspace_path: '/tmp/workspace',
          summary: {},
          files: {
            agents: { path: 'AGENTS.md', exists: true, content: '' },
            soul: { path: 'SOUL.md', exists: true, content: 'Soul content' },
            user: { path: 'USER.md', exists: true, content: 'User content' },
          },
        }));
      }
      if (url === '/api/memory?agent_id=agent-1') {
        return Promise.resolve(createJsonResponse({
          total_entries: 2,
          total_size_kb: 4,
        }));
      }
      if (url === '/api/skills?agent_id=agent-1') {
        return Promise.resolve(createJsonResponse({ skills: [] }));
      }
      if (url === '/api/memory/tool-audits?agent_id=agent-1&limit=12&window_hours=24') {
        return Promise.resolve(createJsonResponse({
          agent_id: 'agent-1',
          session_key: null,
          risk_kind: 'all',
          window_hours: 24,
          limit: 12,
          total_returned: 2,
          total_matches: 2,
          blocked_count: 0,
          error_count: 0,
          summary: {
            window_hours: 24,
            total_count: 2,
            blocked_count: 0,
            error_count: 0,
            exec_count: 0,
            outbound_count: 0,
          },
          items: [],
        }));
      }
      if (url === '/api/memory/tool-audits?agent_id=agent-1&limit=12&window_hours=24&session_key=web%3Ademo') {
        return Promise.resolve(createJsonResponse({
          agent_id: 'agent-1',
          session_key: 'web:demo',
          risk_kind: 'all',
          window_hours: 24,
          limit: 12,
          total_returned: 1,
          total_matches: 1,
          blocked_count: 0,
          error_count: 0,
          summary: {
            window_hours: 24,
            total_count: 1,
            blocked_count: 0,
            error_count: 0,
            exec_count: 0,
            outbound_count: 0,
          },
          items: [],
        }));
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    const { result } = renderHook(() => useTeamAgentAssets({ selectedAgentId: 'agent-1' }));

    await waitFor(() => {
      expect(result.current.assetLoading).toBe(false);
    });

    await act(async () => {
      result.current.setToolAuditSessionKey('web:demo');
    });

    await waitFor(() => {
      expect(result.current.agentToolAudits?.session_key).toBe('web:demo');
    });

    expect(fetch).toHaveBeenCalledWith('/api/memory/tool-audits?agent_id=agent-1&limit=12&window_hours=24&session_key=web%3Ademo');
  });

  it('reloads tool audits when risk filter changes', async () => {
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/agents/agent-1/bootstrap-files') {
        return Promise.resolve(createJsonResponse({
          workspace_path: '/tmp/workspace',
          summary: {},
          files: {
            agents: { path: 'AGENTS.md', exists: true, content: '' },
            soul: { path: 'SOUL.md', exists: true, content: '' },
            user: { path: 'USER.md', exists: true, content: '' },
          },
        }));
      }
      if (url === '/api/memory?agent_id=agent-1') {
        return Promise.resolve(createJsonResponse({
          total_entries: 1,
          total_size_kb: 2,
        }));
      }
      if (url === '/api/skills?agent_id=agent-1') {
        return Promise.resolve(createJsonResponse({ skills: [] }));
      }
      if (url === '/api/memory/tool-audits?agent_id=agent-1&limit=12&window_hours=24') {
        return Promise.resolve(createJsonResponse({
          agent_id: 'agent-1',
          session_key: null,
          risk_kind: 'all',
          window_hours: 24,
          limit: 12,
          total_returned: 2,
          total_matches: 2,
          blocked_count: 0,
          error_count: 0,
          summary: {
            window_hours: 24,
            total_count: 2,
            blocked_count: 1,
            error_count: 0,
            exec_count: 1,
            outbound_count: 0,
          },
          items: [],
        }));
      }
      if (url === '/api/memory/tool-audits?agent_id=agent-1&limit=12&window_hours=24&risk_kind=exec') {
        return Promise.resolve(createJsonResponse({
          agent_id: 'agent-1',
          session_key: null,
          risk_kind: 'exec',
          window_hours: 24,
          limit: 12,
          total_returned: 1,
          total_matches: 1,
          blocked_count: 0,
          error_count: 0,
          summary: {
            window_hours: 24,
            total_count: 2,
            blocked_count: 1,
            error_count: 0,
            exec_count: 1,
            outbound_count: 0,
          },
          items: [
            {
              type: 'tool_audit',
              tool_name: 'exec',
              task: 'tool:exec',
              timestamp: '2026-04-14T11:00:00',
            },
          ],
        }));
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    const { result } = renderHook(() => useTeamAgentAssets({ selectedAgentId: 'agent-1' }));

    await waitFor(() => {
      expect(result.current.assetLoading).toBe(false);
    });

    await act(async () => {
      result.current.setToolAuditRiskFilter('exec');
    });

    await waitFor(() => {
      expect(result.current.agentToolAudits?.risk_kind).toBe('exec');
    });

    expect(fetch).toHaveBeenCalledWith('/api/memory/tool-audits?agent_id=agent-1&limit=12&window_hours=24&risk_kind=exec');
  });

  it('hydrates tool audit filters from the URL on first load', async () => {
    window.history.replaceState({}, '', '/teams?agent=agent-1&auditSession=web%3Ademo&auditRisk=exec&auditWindow=72&auditLimit=24');

    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/agents/agent-1/bootstrap-files') {
        return Promise.resolve(createJsonResponse({
          workspace_path: '/tmp/workspace',
          summary: {},
          files: {
            agents: { path: 'AGENTS.md', exists: true, content: '' },
            soul: { path: 'SOUL.md', exists: true, content: '' },
            user: { path: 'USER.md', exists: true, content: '' },
          },
        }, true, url));
      }
      if (url === '/api/memory?agent_id=agent-1') {
        return Promise.resolve(createJsonResponse({
          total_entries: 2,
          total_size_kb: 4,
        }, true, url));
      }
      if (url === '/api/skills?agent_id=agent-1') {
        return Promise.resolve(createJsonResponse({ skills: [] }, true, url));
      }
      if (url === '/api/memory/tool-audits?agent_id=agent-1&limit=24&window_hours=72&session_key=web%3Ademo&risk_kind=exec') {
        return Promise.resolve(createJsonResponse({
          agent_id: 'agent-1',
          session_key: 'web:demo',
          risk_kind: 'exec',
          window_hours: 72,
          limit: 24,
          total_returned: 1,
          total_matches: 1,
          blocked_count: 0,
          error_count: 0,
          summary: {
            window_hours: 24,
            total_count: 1,
            blocked_count: 0,
            error_count: 0,
            exec_count: 1,
            outbound_count: 0,
          },
          items: [
            {
              type: 'tool_audit',
              tool_name: 'exec',
              task: 'tool:exec',
              timestamp: '2026-04-14T10:00:00',
            },
          ],
        }, true, url));
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    const { result } = renderHook(() => useTeamAgentAssets({ selectedAgentId: 'agent-1' }));

    await waitFor(() => {
      expect(result.current.assetLoading).toBe(false);
    });

    expect(result.current.toolAuditState).toEqual({
      sessionKey: 'web:demo',
      riskKind: 'exec',
      windowHours: 72,
      limit: 24,
    });
    expect(result.current.agentToolAudits?.risk_kind).toBe('exec');
    expect(fetch).toHaveBeenCalledWith('/api/memory/tool-audits?agent_id=agent-1&limit=24&window_hours=72&session_key=web%3Ademo&risk_kind=exec');
  });

  it('keeps bootstrap data loaded when tool audit endpoint returns html', async () => {
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/agents/agent-1/bootstrap-files') {
        return Promise.resolve(createJsonResponse({
          workspace_path: '/tmp/workspace',
          summary: {},
          files: {
            agents: { path: 'AGENTS.md', exists: true, content: 'Agents content' },
            soul: { path: 'SOUL.md', exists: true, content: 'Soul content' },
            user: { path: 'USER.md', exists: true, content: 'User content' },
          },
        }, true, url));
      }
      if (url === '/api/memory?agent_id=agent-1') {
        return Promise.resolve(createJsonResponse({
          total_entries: 2,
          total_size_kb: 4,
        }, true, url));
      }
      if (url === '/api/skills?agent_id=agent-1') {
        return Promise.resolve(createJsonResponse({ skills: [] }, true, url));
      }
      if (url === '/api/memory/tool-audits?agent_id=agent-1&limit=12&window_hours=24') {
        return Promise.resolve(createHtmlResponse('<!doctype html><html></html>', true, url));
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    const { result } = renderHook(() => useTeamAgentAssets({ selectedAgentId: 'agent-1' }));

    await waitFor(() => {
      expect(result.current.assetLoading).toBe(false);
    });

    expect(result.current.agentAssets?.workspace_path).toBe('/tmp/workspace');
    expect(result.current.agentToolAudits).toBeNull();
    expect(result.current.assetError).toBe('');
  });

  it('loads more tool audits when requested', async () => {
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/agents/agent-1/bootstrap-files') {
        return Promise.resolve(createJsonResponse({
          workspace_path: '/tmp/workspace',
          summary: {},
          files: {
            agents: { path: 'AGENTS.md', exists: true, content: '' },
            soul: { path: 'SOUL.md', exists: true, content: '' },
            user: { path: 'USER.md', exists: true, content: '' },
          },
        }));
      }
      if (url === '/api/memory?agent_id=agent-1') {
        return Promise.resolve(createJsonResponse({
          total_entries: 2,
          total_size_kb: 4,
        }));
      }
      if (url === '/api/skills?agent_id=agent-1') {
        return Promise.resolve(createJsonResponse({ skills: [] }));
      }
      if (url === '/api/memory/tool-audits?agent_id=agent-1&limit=12&window_hours=24') {
        return Promise.resolve(createJsonResponse({
          agent_id: 'agent-1',
          session_key: null,
          risk_kind: 'all',
          window_hours: 24,
          limit: 12,
          total_returned: 12,
          total_matches: 20,
          blocked_count: 0,
          error_count: 0,
          summary: {
            window_hours: 24,
            total_count: 20,
            blocked_count: 0,
            error_count: 0,
            exec_count: 0,
            outbound_count: 0,
          },
          items: Array.from({ length: 12 }).map((_, index) => ({
            type: 'tool_audit',
            tool_name: `read_file_${index}`,
            task: 'tool:read_file',
            timestamp: '2026-04-14T10:00:00',
          })),
        }));
      }
      if (url === '/api/memory/tool-audits?agent_id=agent-1&limit=24&window_hours=24') {
        return Promise.resolve(createJsonResponse({
          agent_id: 'agent-1',
          session_key: null,
          risk_kind: 'all',
          window_hours: 24,
          limit: 24,
          total_returned: 20,
          total_matches: 20,
          blocked_count: 0,
          error_count: 0,
          summary: {
            window_hours: 24,
            total_count: 20,
            blocked_count: 0,
            error_count: 0,
            exec_count: 0,
            outbound_count: 0,
          },
          items: Array.from({ length: 20 }).map((_, index) => ({
            type: 'tool_audit',
            tool_name: `read_file_${index}`,
            task: 'tool:read_file',
            timestamp: '2026-04-14T10:00:00',
          })),
        }));
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    const { result } = renderHook(() => useTeamAgentAssets({ selectedAgentId: 'agent-1' }));

    await waitFor(() => {
      expect(result.current.assetLoading).toBe(false);
    });

    await act(async () => {
      result.current.loadMoreToolAudits();
    });

    await waitFor(() => {
      expect(result.current.agentToolAudits?.total_returned).toBe(20);
    });

    expect(fetch).toHaveBeenCalledWith('/api/memory/tool-audits?agent_id=agent-1&limit=24&window_hours=24');
  });
});
