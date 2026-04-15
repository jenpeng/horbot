import { useCallback, useEffect, useRef, useState } from 'react';
import { getStorageItem } from '../utils/storage';
import { readSelectionFromUrl } from '../pages/teams/selection';
import { createAsyncResourceCache } from '../utils/asyncResourceCache';
import type {
  AgentInfo,
  ExternalAgentInfo,
  ProviderInfo,
  TeamInfo,
  TeamsPageSelection,
} from '../pages/teams/types';

interface UseTeamsDirectoryDataOptions {
  currentSelectedAgentId: string | null;
  currentSelectedTeamId: string | null;
  currentSelectedExternalAgentId: string | null;
  selectionStorageKey: string;
  onSelectionResolved: (selection: {
    selectedAgentId: string | null;
    selectedTeam: TeamInfo | null;
    selectedExternalAgentId: string | null;
  }) => void;
}

interface TeamsDirectoryBundle {
  agents: AgentInfo[];
  teams: TeamInfo[];
  externalAgents: ExternalAgentInfo[];
  providers: ProviderInfo[];
}

const teamsDirectoryCache = createAsyncResourceCache(
  async (): Promise<TeamsDirectoryBundle> => {
    const [agentsRes, teamsRes, externalAgentsRes, providersRes] = await Promise.all([
      fetch('/api/agents'),
      fetch('/api/teams'),
      fetch('/api/external-agents'),
      fetch('/api/providers'),
    ]);

    const agentsData = await agentsRes.json();
    const teamsData = await teamsRes.json();
    const externalAgentsData = await externalAgentsRes.json();
    const providersData = await providersRes.json();

    return {
      agents: agentsData.agents || [],
      teams: teamsData.teams || [],
      externalAgents: externalAgentsData.external_agents || [],
      providers: providersData.providers || [],
    };
  },
  {
    ttlMs: 20_000,
    keyFn: () => 'teams-directory',
  },
);

export const useTeamsDirectoryData = ({
  currentSelectedAgentId,
  currentSelectedTeamId,
  currentSelectedExternalAgentId,
  selectionStorageKey,
  onSelectionResolved,
}: UseTeamsDirectoryDataOptions) => {
  const cachedDirectory = teamsDirectoryCache.peek();
  const [agents, setAgents] = useState<AgentInfo[]>(cachedDirectory?.agents || []);
  const [teams, setTeams] = useState<TeamInfo[]>(cachedDirectory?.teams || []);
  const [externalAgents, setExternalAgents] = useState<ExternalAgentInfo[]>(cachedDirectory?.externalAgents || []);
  const [providers, setProviders] = useState<ProviderInfo[]>(cachedDirectory?.providers || []);
  const [loading, setLoading] = useState(!cachedDirectory);
  const currentSelectedAgentIdRef = useRef(currentSelectedAgentId);
  const currentSelectedTeamIdRef = useRef(currentSelectedTeamId);
  const currentSelectedExternalAgentIdRef = useRef(currentSelectedExternalAgentId);

  useEffect(() => {
    currentSelectedAgentIdRef.current = currentSelectedAgentId;
  }, [currentSelectedAgentId]);

  useEffect(() => {
    currentSelectedTeamIdRef.current = currentSelectedTeamId;
  }, [currentSelectedTeamId]);

  useEffect(() => {
    currentSelectedExternalAgentIdRef.current = currentSelectedExternalAgentId;
  }, [currentSelectedExternalAgentId]);

  const refreshDirectory = useCallback(async (options: { force?: boolean } = {}) => {
    const hasCachedDirectory = Boolean(teamsDirectoryCache.peek());
    if (options.force || !hasCachedDirectory) {
      setLoading(true);
    }

    try {
      const directory = options.force
        ? await teamsDirectoryCache.refresh()
        : await teamsDirectoryCache.get();
      const nextAgents = directory.agents;
      const nextTeams = directory.teams;
      const nextExternalAgents = directory.externalAgents;
      const urlSelection = readSelectionFromUrl();
      const persistedSelection = getStorageItem<TeamsPageSelection | null>(selectionStorageKey, null);
      const preferredAgentId =
        (urlSelection?.kind === 'agent' ? urlSelection.id : null)
        || currentSelectedAgentIdRef.current
        || (persistedSelection?.kind === 'agent' ? persistedSelection.id : null);
      const resolvedAgentId = preferredAgentId && nextAgents.some((agent: AgentInfo) => agent.id === preferredAgentId)
        ? preferredAgentId
        : null;
      const preferredExternalAgentId =
        (urlSelection?.kind === 'external-agent' ? urlSelection.id : null)
        || currentSelectedExternalAgentIdRef.current
        || (persistedSelection?.kind === 'external-agent' ? persistedSelection.id : null);
      const resolvedExternalAgentId = !resolvedAgentId
        ? (
            preferredExternalAgentId
            && nextExternalAgents.some((agent: ExternalAgentInfo) => agent.id === preferredExternalAgentId)
              ? preferredExternalAgentId
              : null
          )
        : null;
      const preferredTeamId =
        (urlSelection?.kind === 'team' ? urlSelection.id : null)
        || currentSelectedTeamIdRef.current
        || (persistedSelection?.kind === 'team' ? persistedSelection.id : null);
      const resolvedTeam = !resolvedAgentId && !resolvedExternalAgentId
        ? (
            (preferredTeamId
              ? nextTeams.find((team: TeamInfo) => team.id === preferredTeamId)
              : undefined)
            || nextTeams[0]
            || null
          )
        : null;

      setAgents(nextAgents);
      setTeams(nextTeams);
      setExternalAgents(nextExternalAgents);
      setProviders(directory.providers);
      onSelectionResolved({
        selectedAgentId: resolvedAgentId,
        selectedTeam: resolvedTeam,
        selectedExternalAgentId: resolvedExternalAgentId,
      });
    } catch (error) {
      console.error('Failed to fetch data:', error);
    } finally {
      setLoading(false);
    }
  }, [onSelectionResolved, selectionStorageKey]);

  useEffect(() => {
    void refreshDirectory();
  }, [refreshDirectory]);

  return {
    agents,
    teams,
    externalAgents,
    providers,
    loading,
    refreshDirectory,
  };
};
