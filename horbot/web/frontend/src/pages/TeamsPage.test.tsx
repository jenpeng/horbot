import React, { type ReactElement } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import TeamsPage from './TeamsPage';
import { useTeamAgentAssets, useTeamsDirectoryData, useTeamsMutations } from '../hooks';
import { I18nProvider } from '../contexts/I18nContext';
import { preloadLocaleMessages } from '../i18n/messages';
import type { AgentInfo, ExternalAgentInfo, ProviderInfo, TeamInfo } from './teams/types';

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
  memory_bank_profile: {
    mission: 'Keep engineering context stable',
    directives: ['Prefer recent regression outcomes'],
    reasoning_style: 'precise',
  },
};

const teamFixture: TeamInfo = {
  id: 'team-a',
  name: 'Team A',
  description: 'Delivery team',
  members: ['agent-a', 'partner-agent'],
  member_profiles: {
    'agent-a': {
      role: 'coordinator',
      priority: 10,
      isLead: true,
      responsibility: '负责拆解任务',
    },
    'partner-agent': {
      role: 'researcher',
      priority: 50,
      isLead: false,
      responsibility: '负责外部调研',
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

const renderWithI18n = (ui: ReactElement) => render(<I18nProvider>{ui}</I18nProvider>);

const externalAgentFixture: ExternalAgentInfo = {
  id: 'partner-agent',
  name: 'Partner Agent',
  description: 'External partner',
  transport: 'http_sse',
  endpoint: 'https://example.com/agent',
  auth_type: 'none',
  auth_header: 'Authorization',
  auth_secret_configured: false,
  capabilities: ['research'],
  dm_enabled: true,
  team_enabled: false,
  mention_required: true,
  timeout_s: 90,
  max_turn_chars: 12000,
  context_scope: 'recent_turns',
  memory_access: 'none',
  file_access: 'none',
};

describe('TeamsPage', () => {
  const setToolAuditState = vi.fn();
  const setToolAuditSessionKey = vi.fn();
  const setToolAuditRiskFilter = vi.fn();
  const setToolAuditWindowHours = vi.fn();
  const loadMoreToolAudits = vi.fn();

  beforeAll(async () => {
    await preloadLocaleMessages('en');
  });

  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();

    vi.mocked(useTeamAgentAssets).mockReturnValue({
      agentAssets: null,
      agentMemoryStats: null,
      agentSkills: [],
      agentToolAudits: null,
      toolAuditState: {
        sessionKey: '',
        riskKind: 'all',
        windowHours: 24,
        limit: 12,
      },
      toolAuditLoading: false,
      assetDrafts: { agents: '', soul: '', user: '' },
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
      setToolAuditState,
      setToolAuditSessionKey,
      setToolAuditRiskFilter,
      setToolAuditWindowHours,
      loadMoreToolAudits,
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
            selectedExternalAgentId: null,
          });
        }
      }, [onSelectionResolved]);

      return {
        agents: [agentFixture],
        teams: [teamFixture],
        externalAgents: [externalAgentFixture],
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
      createExternalAgent: vi.fn(),
      updateExternalAgent: vi.fn(),
      deleteExternalAgent: vi.fn(),
      testExternalAgent: vi.fn(),
    });
  });

  it('opens the extracted create agent modal from the page shell', () => {
    window.history.replaceState({}, '', '/teams?agent=agent-a');

    renderWithI18n(<TeamsPage />);

    expect(screen.getByTestId('agent-detail-view')).toHaveAttribute('data-agent-id', 'agent-a');

    fireEvent.click(screen.getByRole('button', { name: 'Create Agent' }));

    expect(screen.getByRole('heading', { name: 'Create Agent' })).toBeInTheDocument();
    expect(screen.getByText('Provider')).toBeInTheDocument();
    expect(screen.getByText('Model')).toBeInTheDocument();
  });

  it('requires provider and model before enabling agent creation', () => {
    window.history.replaceState({}, '', '/teams?agent=agent-a');

    renderWithI18n(<TeamsPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Create Agent' }));

    const createButton = screen.getByRole('button', { name: 'Create' });
    expect(createButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText('ID'), { target: { value: 'agent-b' } });
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Agent B' } });
    expect(createButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText('Provider'), { target: { value: 'openai' } });
    fireEvent.change(screen.getByLabelText('Model'), { target: { value: 'gpt-5.4' } });
    expect(createButton).not.toBeDisabled();
  });

  it('opens the extracted edit team modal from the team detail panel', () => {
    window.history.replaceState({}, '', '/teams?team=team-a');

    renderWithI18n(<TeamsPage />);

    expect(screen.getByTestId('team-detail-view')).toHaveAttribute('data-team-id', 'team-a');

    fireEvent.click(screen.getByRole('button', { name: 'Edit Team' }));

    expect(screen.getByRole('heading', { name: 'Edit Team' })).toBeInTheDocument();
  });

  it('renders external agents that are explicit team members in the team detail view', () => {
    window.history.replaceState({}, '', '/teams?team=team-a');

    renderWithI18n(<TeamsPage />);

    expect(screen.getByTestId('team-detail-view')).toHaveAttribute('data-team-id', 'team-a');
    expect(screen.getByText('Partner Agent')).toBeInTheDocument();
    expect(screen.getAllByText(/External|外部/).length).toBeGreaterThan(0);
  });

  it('renders the tool audit activity panel for an agent selection', () => {
    vi.mocked(useTeamAgentAssets).mockReturnValue({
      agentAssets: {
        workspace_path: '/tmp/agent-a',
        summary: {},
        files: {
          agents: { path: 'AGENTS.md', exists: true, content: '' },
          soul: { path: 'SOUL.md', exists: true, content: '' },
          user: { path: 'USER.md', exists: true, content: '' },
        },
      },
      agentMemoryStats: { total_entries: 4, total_size_kb: 8 },
      agentSkills: [{ name: 'debugger', source: 'user', enabled: true }],
      agentToolAudits: {
        agent_id: 'agent-a',
        session_key: null,
        risk_kind: 'all',
        window_hours: 24,
        limit: 12,
        total_returned: 1,
        total_matches: 15,
        blocked_count: 1,
        error_count: 0,
        summary: {
          window_hours: 24,
          total_count: 8,
          blocked_count: 3,
          error_count: 1,
          exec_count: 2,
          outbound_count: 5,
        },
        items: [
          {
            type: 'tool_audit',
            tool_name: 'web_fetch',
            task: 'tool:web_fetch',
            timestamp: '2026-04-14T12:00:00',
            guard_blocked: true,
            guard_reasons: ['instruction override content'],
            result: '[Security notice] Tool output from web_fetch was withheld.',
            permission_level: 'allow',
            duration_ms: 37,
            audit_event: {
              session_key: 'web:dm_agent-a',
            },
          },
        ],
      },
      toolAuditState: {
        sessionKey: '',
        riskKind: 'all',
        windowHours: 24,
        limit: 12,
      },
      toolAuditLoading: false,
      assetDrafts: { agents: '', soul: '', user: '' },
      assetLoading: false,
      assetLoadedAgentId: 'agent-a',
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
      setToolAuditState,
      setToolAuditSessionKey,
      setToolAuditRiskFilter,
      setToolAuditWindowHours,
      loadMoreToolAudits,
      setAssetError: vi.fn(),
      setAssetSuccess: vi.fn(),
    });

    window.history.replaceState({}, '', '/teams?agent=agent-a');

    renderWithI18n(<TeamsPage />);

    expect(screen.getByText(/Tool Audit|工具审计/)).toBeInTheDocument();
    expect(screen.getByText(/Last 24h: blocked 3 \/ exec 2 \/ outbound 5 \/ errors 1|最近 24h 拦截 3 次 \/ exec 2 次 \/ 外联 5 次 \/ 错误 1 次/)).toBeInTheDocument();
    expect(screen.getByText('web_fetch')).toBeInTheDocument();
    expect(screen.getByText('instruction override content')).toBeInTheDocument();
    expect(screen.getByText(/Raw JSON|原始 JSON/)).toBeInTheDocument();
    expect(screen.getByText(/Recent sessions|最近会话/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^web:dm_agent-a$/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /exec 2/i }));
    expect(setToolAuditRiskFilter).toHaveBeenCalledWith('exec');
    expect(window.location.search).toContain('focus=agent-tool-audits');
    fireEvent.click(screen.getByRole('button', { name: /Session web:dm_agent-a|会话 web:dm_agent-a/ }));
    expect(setToolAuditSessionKey).toHaveBeenCalledWith('web:dm_agent-a');
    fireEvent.click(screen.getByRole('button', { name: /72h/i }));
    expect(setToolAuditWindowHours).toHaveBeenCalledWith(72);
    fireEvent.click(screen.getByRole('button', { name: /Load More|查看更多/i }));
    expect(loadMoreToolAudits).toHaveBeenCalled();
  });

  it('syncs tool audit filters into the URL for agent selections', async () => {
    vi.mocked(useTeamAgentAssets).mockReturnValue({
      agentAssets: {
        workspace_path: '/tmp/agent-a',
        summary: {},
        files: {
          agents: { path: 'AGENTS.md', exists: true, content: '' },
          soul: { path: 'SOUL.md', exists: true, content: '' },
          user: { path: 'USER.md', exists: true, content: '' },
        },
      },
      agentMemoryStats: { total_entries: 4, total_size_kb: 8 },
      agentSkills: [],
      agentToolAudits: null,
      toolAuditState: {
        sessionKey: 'web:demo',
        riskKind: 'exec',
        windowHours: 72,
        limit: 24,
      },
      toolAuditLoading: false,
      assetDrafts: { agents: '', soul: '', user: '' },
      assetLoading: false,
      assetLoadedAgentId: 'agent-a',
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
      setToolAuditState,
      setToolAuditSessionKey,
      setToolAuditRiskFilter,
      setToolAuditWindowHours,
      loadMoreToolAudits,
      setAssetError: vi.fn(),
      setAssetSuccess: vi.fn(),
    });

    window.history.replaceState({}, '', '/teams?agent=agent-a');

    renderWithI18n(<TeamsPage />);

    await waitFor(() => {
      expect(window.location.search).toContain('agent=agent-a');
      expect(window.location.search).toContain('auditSession=web%3Ademo');
      expect(window.location.search).toContain('auditRisk=exec');
      expect(window.location.search).toContain('auditWindow=72');
      expect(window.location.search).toContain('auditLimit=24');
    });
  });

  it('restores selection and audit filters from the URL on popstate', async () => {
    window.history.replaceState({}, '', '/teams?team=team-a');

    renderWithI18n(<TeamsPage />);

    expect(screen.getByTestId('team-detail-view')).toHaveAttribute('data-team-id', 'team-a');

    window.history.pushState({}, '', '/teams?agent=agent-a&auditSession=web%3Ademo&auditRisk=exec&auditWindow=72&auditLimit=24');
    window.dispatchEvent(new PopStateEvent('popstate'));

    await waitFor(() => {
      expect(screen.getByTestId('agent-detail-view')).toHaveAttribute('data-agent-id', 'agent-a');
    });

    expect(setToolAuditState).toHaveBeenCalledWith({
      sessionKey: 'web:demo',
      riskKind: 'exec',
      windowHours: 72,
      limit: 24,
    });
  });
});
