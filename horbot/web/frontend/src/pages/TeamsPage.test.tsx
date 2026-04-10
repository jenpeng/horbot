import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TeamsPage from './TeamsPage';
import { useTeamAgentAssets, useTeamsDirectoryData, useTeamsMutations } from '../hooks';
import type { AgentInfo, ProviderInfo, TeamInfo } from './teams/types';

vi.mock('../components/CollaborationFlow', () => ({
  default: ({ teamId }: { teamId: string }) => <div data-testid="mock-collaboration-flow">{teamId}</div>,
}));

vi.mock('../hooks', async () => {
  const actual = await vi.importActual<typeof import('../hooks')>('../hooks');
  return {
    ...actual,
    useTeamAgentAssets: vi.fn(),
    useTeamsDirectoryData: vi.fn(),
    useTeamsMutations: vi.fn(),
  };
});

const agentFixture: AgentInfo = {
  id: 'agent-a',
  name: 'Agent A',
  description: 'Alpha agent',
  model: 'gpt-test',
  provider: 'openai',
  capabilities: ['planning'],
  tools: [],
  skills: [],
  teams: ['team-a'],
  workspace: '/tmp/agent-a',
  effective_workspace: '/tmp/agent-a',
};

const teamFixture: TeamInfo = {
  id: 'team-a',
  name: 'Team A',
  description: 'Delivery team',
  members: ['agent-a'],
  member_profiles: {
    'agent-a': {
      role: 'coordinator',
      priority: 10,
      isLead: true,
      responsibility: '负责拆解任务',
    },
  },
  workspace: '/tmp/team-a',
  effective_workspace: '/tmp/team-a',
};

const providerFixture: ProviderInfo = {
  id: 'openai',
  name: 'OpenAI',
  configured: true,
  models: [],
};

describe('TeamsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();

    vi.mocked(useTeamAgentAssets).mockReturnValue({
      agentAssets: null,
      agentMemoryStats: null,
      agentSkills: [],
      assetDrafts: { soul: '', user: '' },
      assetLoading: false,
      assetLoadedAgentId: null,
      assetSaving: null,
      assetError: '',
      assetSuccess: '',
      summaryDrafts: {
        identity: '',
        role_focus: '',
        communication_style: '',
        boundaries: '',
        user_preferences: '',
      },
      summarySaving: false,
      handleAssetDraftChange: vi.fn(),
      handleSummaryDraftChange: vi.fn(),
      handleSaveAssetFile: vi.fn(),
      handleSaveSummary: vi.fn(),
      setAssetError: vi.fn(),
      setAssetSuccess: vi.fn(),
    });

    vi.mocked(useTeamsDirectoryData).mockImplementation(({ onSelectionResolved }) => {
      React.useEffect(() => {
        const search = new URLSearchParams(window.location.search);
        const teamId = search.get('team');
        if (teamId === teamFixture.id) {
          onSelectionResolved({
            selectedAgentId: null,
            selectedTeam: teamFixture,
          });
        }
      }, [onSelectionResolved]);

      return {
        agents: [agentFixture],
        teams: [teamFixture],
        providers: [providerFixture],
        loading: false,
        refreshDirectory: vi.fn(),
      };
    });
    vi.mocked(useTeamsMutations).mockReturnValue({
      createAgent: vi.fn(),
      updateAgent: vi.fn(),
      deleteAgent: vi.fn(),
      createTeam: vi.fn(),
      updateTeam: vi.fn(),
      deleteTeam: vi.fn(),
    });
  });

  it('opens the extracted create agent modal from the page shell', () => {
    window.history.replaceState({}, '', '/teams?agent=agent-a');

    render(<TeamsPage />);

    expect(screen.getByTestId('agent-detail-view')).toHaveAttribute('data-agent-id', 'agent-a');

    fireEvent.click(screen.getByRole('button', { name: '创建 Agent' }));

    expect(screen.getByRole('heading', { name: '创建新 Agent' })).toBeInTheDocument();
  });

  it('opens the extracted edit team modal from the team detail panel', () => {
    window.history.replaceState({}, '', '/teams?team=team-a');

    render(<TeamsPage />);

    expect(screen.getByTestId('team-detail-view')).toHaveAttribute('data-team-id', 'team-a');

    fireEvent.click(screen.getByRole('button', { name: '编辑团队' }));

    expect(screen.getByRole('heading', { name: '编辑团队' })).toBeInTheDocument();
  });
});
