import { useCallback, useEffect, useRef, useState } from 'react';
import { getStorageItem } from '../utils/storage';
import { readSelectionFromUrl } from '../pages/teams/selection';
import type {
  AgentInfo,
  ProviderInfo,
  TeamInfo,
  TeamsPageSelection,
} from '../pages/teams/types';

interface UseTeamsDirectoryDataOptions {
  currentSelectedAgentId: string | null;
  currentSelectedTeamId: string | null;
  selectionStorageKey: string;
  onSelectionResolved: (selection: {
    selectedAgentId: string | null;
    selectedTeam: TeamInfo | null;
  }) => void;
}

export const useTeamsDirectoryData = ({
  currentSelectedAgentId,
  currentSelectedTeamId,
  selectionStorageKey,
  onSelectionResolved,
}: UseTeamsDirectoryDataOptions) => {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [teams, setTeams] = useState<TeamInfo[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const currentSelectedAgentIdRef = useRef(currentSelectedAgentId);
  const currentSelectedTeamIdRef = useRef(currentSelectedTeamId);

  useEffect(() => {
    currentSelectedAgentIdRef.current = currentSelectedAgentId;
  }, [currentSelectedAgentId]);

  useEffect(() => {
    currentSelectedTeamIdRef.current = currentSelectedTeamId;
  }, [currentSelectedTeamId]);

  const refreshDirectory = useCallback(async () => {
    try {
      const [agentsRes, teamsRes, providersRes] = await Promise.all([
        fetch('/api/agents'),
        fetch('/api/teams'),
        fetch('/api/providers'),
      ]);

      const agentsData = await agentsRes.json();
      const teamsData = await teamsRes.json();
      const providersData = await providersRes.json();

      const nextAgents = agentsData.agents || [];
      const nextTeams = teamsData.teams || [];
      const urlSelection = readSelectionFromUrl();
      const persistedSelection = getStorageItem<TeamsPageSelection | null>(selectionStorageKey, null);
      const preferredAgentId =
        (urlSelection?.kind === 'agent' ? urlSelection.id : null)
        || currentSelectedAgentIdRef.current
        || (persistedSelection?.kind === 'agent' ? persistedSelection.id : null);
      const resolvedAgentId = preferredAgentId && nextAgents.some((agent: AgentInfo) => agent.id === preferredAgentId)
        ? preferredAgentId
        : null;
      const preferredTeamId =
        (urlSelection?.kind === 'team' ? urlSelection.id : null)
        || currentSelectedTeamIdRef.current
        || (persistedSelection?.kind === 'team' ? persistedSelection.id : null);
      const resolvedTeam = !resolvedAgentId
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
      setProviders(providersData.providers || []);
      onSelectionResolved({
        selectedAgentId: resolvedAgentId,
        selectedTeam: resolvedTeam,
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
    providers,
    loading,
    refreshDirectory,
  };
};
