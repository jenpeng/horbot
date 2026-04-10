import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useTeamsDirectoryData } from './useTeamsDirectoryData';

const createJsonResponse = (data: unknown): Response => ({
  ok: true,
  json: vi.fn().mockResolvedValue(data),
} as unknown as Response);

describe('useTeamsDirectoryData', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('fetch', vi.fn());
    window.history.replaceState({}, '', '/teams?team=team-b');
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.history.replaceState({}, '', '/teams');
    window.localStorage.clear();
  });

  it('loads directory data and resolves selection from the URL', async () => {
    const onSelectionResolved = vi.fn();

    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/agents') {
        return Promise.resolve(createJsonResponse({
          agents: [
            {
              id: 'agent-a',
              name: 'Agent A',
              description: 'Alpha',
              model: 'gpt-test',
              provider: 'openai',
              capabilities: [],
              tools: [],
              skills: [],
              teams: [],
            },
          ],
        }));
      }
      if (url === '/api/teams') {
        return Promise.resolve(createJsonResponse({
          teams: [
            { id: 'team-a', name: 'Team A', description: '', members: [] },
            { id: 'team-b', name: 'Team B', description: '', members: ['agent-a'] },
          ],
        }));
      }
      if (url === '/api/providers') {
        return Promise.resolve(createJsonResponse({
          providers: [
            { id: 'openai', name: 'OpenAI', configured: true, models: [] },
          ],
        }));
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    const { result } = renderHook(() => useTeamsDirectoryData({
      currentSelectedAgentId: null,
      currentSelectedTeamId: null,
      selectionStorageKey: 'horbot.teams.selection',
      onSelectionResolved,
    }));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.agents).toHaveLength(1);
    expect(result.current.teams).toHaveLength(2);
    expect(result.current.providers).toHaveLength(1);
    expect(onSelectionResolved).toHaveBeenCalledWith({
      selectedAgentId: null,
      selectedTeam: expect.objectContaining({ id: 'team-b' }),
    });
  });
});
