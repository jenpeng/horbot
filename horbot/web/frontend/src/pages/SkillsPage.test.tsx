import type { ReactElement } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SkillsPage from './SkillsPage';
import { I18nProvider } from '../contexts/I18nContext';
import skillsService from '../services/skills';
import type { Skill } from '../types';

vi.mock('../services/skills', () => ({
  default: {
    getSkills: vi.fn(),
    getSkill: vi.fn(),
    createSkill: vi.fn(),
    updateSkill: vi.fn(),
    deleteSkill: vi.fn(),
    toggleSkill: vi.fn(),
    importSkill: vi.fn(),
    getMcpServers: vi.fn(),
    addMcpServer: vi.fn(),
    updateMcpServer: vi.fn(),
    deleteMcpServer: vi.fn(),
  },
}));

const skillFixture: Skill = {
  name: 'research-helper',
  source: 'user',
  path: '/tmp/research-helper',
  description: 'Helps with research.',
  available: true,
  enabled: true,
  always: false,
  requires: {},
  schema: 'skill',
  schema_version: 1,
  source_schema: 'skill',
  source_schema_version: 1,
  normalized_from_legacy: false,
  compatibility: {
    status: 'compatible',
    issues: [],
    warnings: [],
  },
};

const missingSkillFixture: Skill = {
  ...skillFixture,
  name: 'github',
  description: 'GitHub helper.',
  available: false,
  enabled: true,
  missing_requirements: ['CLI: gh'],
  install: [
    {
      kind: 'brew',
      formula: 'gh',
      label: 'Install GitHub CLI (brew)',
    },
  ],
  compatibility: {
    status: 'incompatible',
    issues: ['Missing CLI dependency: gh'],
    warnings: [],
  },
};

const renderWithI18n = (ui: ReactElement) => render(<I18nProvider>{ui}</I18nProvider>);

describe('SkillsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(skillsService.getSkills).mockResolvedValue([skillFixture]);
    vi.mocked(skillsService.getMcpServers).mockResolvedValue({});
  });

  it('renders the shared page loading state while skills are loading', () => {
    vi.mocked(skillsService.getSkills).mockImplementation(
      () => new Promise(() => {}),
    );
    vi.mocked(skillsService.getMcpServers).mockImplementation(
      () => new Promise(() => {}),
    );

    renderWithI18n(<SkillsPage />);

    expect(screen.getByRole('status', { name: 'Page loading' })).toBeInTheDocument();
  });

  it('renders a page error state and retries the initial load', async () => {
    vi.mocked(skillsService.getSkills)
      .mockRejectedValueOnce(new Error('fetch failed'))
      .mockResolvedValueOnce([skillFixture]);
    vi.mocked(skillsService.getMcpServers)
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({});

    renderWithI18n(<SkillsPage />);

    expect(await screen.findByText('Failed to load skills')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    await waitFor(() => {
      expect(screen.getByText('Skills & MCP')).toBeInTheDocument();
    });

    expect(skillsService.getSkills).toHaveBeenCalledTimes(2);
    expect(skillsService.getMcpServers).toHaveBeenCalledTimes(2);
  });

  it('shows missing requirement details on hover and toggles them on click', async () => {
    vi.mocked(skillsService.getSkills).mockResolvedValue([missingSkillFixture]);

    renderWithI18n(<SkillsPage />);

    expect(await screen.findByTestId('skill-missing-toggle-github')).toBeInTheDocument();
    expect(screen.queryByText('Install GitHub CLI (brew)')).not.toBeInTheDocument();

    const missingToggle = screen.getByTestId('skill-missing-toggle-github');

    fireEvent.mouseEnter(missingToggle);
    expect(await screen.findByText('Install GitHub CLI (brew)')).toBeInTheDocument();

    fireEvent.mouseLeave(missingToggle);
    await waitFor(() => {
      expect(screen.queryByText('Install GitHub CLI (brew)')).not.toBeInTheDocument();
    });

    fireEvent.click(missingToggle);
    expect(await screen.findByText('Install GitHub CLI (brew)')).toBeInTheDocument();

    fireEvent.click(missingToggle);
    await waitFor(() => {
      expect(screen.queryByText('Install GitHub CLI (brew)')).not.toBeInTheDocument();
    });
  });
});
