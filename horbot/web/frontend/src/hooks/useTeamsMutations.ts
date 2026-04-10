import { useCallback } from 'react';
import type { AgentFormState, TeamFormState } from '../pages/teams/types';

interface UseTeamsMutationsOptions {
  onRefresh?: () => void | Promise<void>;
}

const parseMutationError = async (response: Response, fallback: string): Promise<Error> => {
  try {
    const payload = await response.json();
    return new Error(payload?.detail || fallback);
  } catch {
    return new Error(fallback);
  }
};

export const useTeamsMutations = ({ onRefresh }: UseTeamsMutationsOptions = {}) => {
  const runMutation = useCallback(async (request: () => Promise<Response>, fallback: string) => {
    const response = await request();
    if (!response.ok) {
      throw await parseMutationError(response, fallback);
    }
    await onRefresh?.();
  }, [onRefresh]);

  const createAgent = useCallback(async (form: AgentFormState) => {
    await runMutation(
      () => fetch('/api/agents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      }),
      'Failed to create agent',
    );
  }, [runMutation]);

  const updateAgent = useCallback(async (form: AgentFormState) => {
    await runMutation(
      () => fetch(`/api/agents/${form.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      }),
      'Failed to update agent',
    );
  }, [runMutation]);

  const deleteAgent = useCallback(async (agentId: string) => {
    await runMutation(
      () => fetch(`/api/agents/${agentId}`, { method: 'DELETE' }),
      'Failed to delete agent',
    );
  }, [runMutation]);

  const createTeam = useCallback(async (form: TeamFormState) => {
    await runMutation(
      () => fetch('/api/teams', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      }),
      'Failed to create team',
    );
  }, [runMutation]);

  const updateTeam = useCallback(async (form: TeamFormState) => {
    await runMutation(
      () => fetch(`/api/teams/${form.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      }),
      'Failed to update team',
    );
  }, [runMutation]);

  const deleteTeam = useCallback(async (teamId: string) => {
    await runMutation(
      () => fetch(`/api/teams/${teamId}`, { method: 'DELETE' }),
      'Failed to delete team',
    );
  }, [runMutation]);

  return {
    createAgent,
    updateAgent,
    deleteAgent,
    createTeam,
    updateTeam,
    deleteTeam,
  };
};
