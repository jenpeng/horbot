import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useTeamsMutations } from './useTeamsMutations';

const createJsonResponse = (data: unknown, ok = true): Response => ({
  ok,
  json: vi.fn().mockResolvedValue(data),
} as unknown as Response);

describe('useTeamsMutations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('creates an agent and refreshes the directory data', async () => {
    const onRefresh = vi.fn();
    vi.mocked(fetch).mockResolvedValue(createJsonResponse({ ok: true }));

    const { result } = renderHook(() => useTeamsMutations({ onRefresh }));

    await act(async () => {
      await result.current.createAgent({
        id: 'agent-a',
        name: 'Agent A',
        description: 'Alpha',
        profile: '',
        permission_profile: '',
        model: '',
        provider: 'auto',
        system_prompt: '',
        capabilities: [],
        tools: [],
        skills: [],
        workspace: '',
        teams: [],
        personality: '',
        avatar: '',
        evolution_enabled: true,
        learning_enabled: true,
        memory_bank_profile: {
          mission: '',
          directives: [],
          reasoning_style: '',
        },
      });
    });

    expect(fetch).toHaveBeenCalledWith('/api/agents', expect.objectContaining({
      method: 'POST',
    }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it('surfaces API errors when a team update fails', async () => {
    vi.mocked(fetch).mockResolvedValue(createJsonResponse({ detail: 'team update failed' }, false));

    const { result } = renderHook(() => useTeamsMutations());

    await expect(result.current.updateTeam({
      id: 'team-a',
      name: 'Team A',
      description: 'Alpha',
      members: [],
      member_profiles: {},
      workspace: '',
    })).rejects.toThrow('team update failed');
  });
});
