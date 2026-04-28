import { useCallback } from 'react';
import type { AgentFormState, ExternalAgentFormState, TeamFormState } from '../pages/teams/types';

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

  const serializeExternalAgentForm = useCallback((form: ExternalAgentFormState) => ({
    id: form.id,
    name: form.name,
    description: form.description,
    avatar: form.avatar,
    adapter: form.adapter,
    transport: form.transport,
    endpoint: form.endpoint,
    auth_type: form.auth_type,
    auth_header: form.auth_header,
    auth_secret: form.auth_secret,
    capabilities: form.capabilities,
    dm_enabled: form.dm_enabled,
    team_enabled: form.team_enabled,
    mention_required: form.mention_required,
    timeout_s: form.timeout_s,
    max_turn_chars: form.max_turn_chars,
    context_scope: form.context_scope,
    memory_access: form.memory_access,
    file_access: form.file_access,
    adapter_config: form.adapter_config,
    metadata: form.metadata,
  }), []);

  const createExternalAgent = useCallback(async (form: ExternalAgentFormState) => {
    await runMutation(
      () => fetch('/api/external-agents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(serializeExternalAgentForm(form)),
      }),
      'Failed to create external agent',
    );
  }, [runMutation, serializeExternalAgentForm]);

  const updateExternalAgent = useCallback(async (form: ExternalAgentFormState) => {
    await runMutation(
      () => fetch(`/api/external-agents/${form.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(serializeExternalAgentForm(form)),
      }),
      'Failed to update external agent',
    );
  }, [runMutation, serializeExternalAgentForm]);

  const deleteExternalAgent = useCallback(async (externalAgentId: string) => {
    await runMutation(
      () => fetch(`/api/external-agents/${externalAgentId}`, { method: 'DELETE' }),
      'Failed to delete external agent',
    );
  }, [runMutation]);

  const testExternalAgent = useCallback(async (externalAgentId: string) => {
    const response = await fetch(`/api/external-agents/${externalAgentId}/test`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw await parseMutationError(response, 'Failed to test external agent');
    }
    return response.json();
  }, []);

  return {
    createAgent,
    updateAgent,
    deleteAgent,
    createTeam,
    updateTeam,
    deleteTeam,
    createExternalAgent,
    updateExternalAgent,
    deleteExternalAgent,
    testExternalAgent,
  };
};
