import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useTeamAgentAssets } from './useTeamAgentAssets';

const createJsonResponse = (data: unknown, ok = true): Response => ({
  ok,
  json: vi.fn().mockResolvedValue(data),
} as unknown as Response);

describe('useTeamAgentAssets', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
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
      throw new Error(`Unhandled fetch: ${url}`);
    });

    const { result } = renderHook(() => useTeamAgentAssets({ selectedAgentId: 'agent-1' }));

    await waitFor(() => {
      expect(result.current.assetLoading).toBe(false);
    });

    expect(result.current.agentAssets?.workspace_path).toBe('/tmp/workspace');
    expect(result.current.assetDrafts.soul).toBe('Soul content');
    expect(result.current.summaryDrafts.identity).toBe('Lead engineer');
    expect(result.current.agentMemoryStats).toEqual({
      total_entries: 12,
      total_size_kb: 48,
    });
    expect(result.current.agentSkills).toEqual([
      { name: 'debugger', source: 'user', enabled: true },
    ]);
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
});
