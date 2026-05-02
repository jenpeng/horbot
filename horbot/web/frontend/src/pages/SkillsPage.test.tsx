import type { ReactElement } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import SkillsPage from './SkillsPage';
import { I18nProvider } from '../contexts/I18nContext';
import { preloadLocaleMessages } from '../i18n/messages';
import skillsService from '../services/skills';
import type { Skill, SkillDetail } from '../types';

vi.mock('../services/skills', () => ({
  default: {
    getSkills: vi.fn(),
    getSkill: vi.fn(),
    createSkill: vi.fn(),
    updateSkill: vi.fn(),
    deleteSkill: vi.fn(),
    toggleSkill: vi.fn(),
    importSkill: vi.fn(),
    exportSkill: vi.fn(),
    promoteSkill: vi.fn(),
    consolidateGeneratedSkills: vi.fn(),
    getMcpServers: vi.fn(),
    addMcpServer: vi.fn(),
    updateMcpServer: vi.fn(),
    deleteMcpServer: vi.fn(),
  },
}));

const skillFixture: Skill = {
  name: 'research-helper',
  source: 'user',
  source_group: 'custom',
  source_origin_kind: 'manual',
  source_origin_agent_id: null,
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

const builtinSkillFixture: Skill = {
  name: 'excel-xlsx',
  source: 'builtin',
  source_group: 'system',
  source_origin_kind: 'builtin',
  source_origin_agent_id: null,
  path: '/builtin/excel-xlsx/SKILL.md',
  description: 'Spreadsheet helper.',
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

const skillDetailFixture: SkillDetail = {
  ...skillFixture,
  content: '# Research Helper',
  metadata: {},
};

const renderWithI18n = (ui: ReactElement) => render(<I18nProvider>{ui}</I18nProvider>);

describe('SkillsPage', () => {
  beforeAll(async () => {
    await preloadLocaleMessages('en');
  });

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(skillsService.getSkills).mockResolvedValue([skillFixture, builtinSkillFixture]);
    vi.mocked(skillsService.getSkill).mockResolvedValue(skillDetailFixture);
    vi.mocked(skillsService.getMcpServers).mockResolvedValue({});
    vi.mocked(skillsService.exportSkill).mockResolvedValue(new Blob(['demo'], { type: 'application/zip' }));
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

  it('switches between custom and system skill tabs', async () => {
    renderWithI18n(<SkillsPage />);

    expect(await screen.findByRole('button', { name: 'Custom (1)' })).toBeInTheDocument();
    expect(screen.getByText('research-helper')).toBeInTheDocument();
    expect(screen.getByText('Manual')).toBeInTheDocument();
    expect(screen.queryByText('excel-xlsx')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'System (1)' }));

    expect(await screen.findByText('excel-xlsx')).toBeInTheDocument();
    expect(screen.getByText('System')).toBeInTheDocument();
  });

  it('searches only within the active skill tab and can clear the query', async () => {
    renderWithI18n(<SkillsPage />);

    const searchInput = await screen.findByPlaceholderText('Search custom skills...');
    fireEvent.change(searchInput, { target: { value: 'excel' } });

    expect(screen.queryByText('research-helper')).not.toBeInTheDocument();
    expect(screen.queryByText('excel-xlsx')).not.toBeInTheDocument();
    expect(screen.getByText('No skills found')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'System (1)' }));
    expect(await screen.findByPlaceholderText('Search system skills...')).toBeInTheDocument();
    expect(await screen.findByText('excel-xlsx')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
    expect(await screen.findByText('excel-xlsx')).toBeInTheDocument();
  });

  it('manually consolidates generated skills and refreshes the list', async () => {
    vi.mocked(skillsService.consolidateGeneratedSkills).mockResolvedValue({
      family_count_before: 3,
      family_count_after: 2,
      merged_skill_count: 1,
      updated_families: [
        {
          skill_name: 'auto-shell-retry-checklist',
          merged_skills: ['auto-shell-timeout-diagnosis'],
        },
      ],
      message: 'Consolidated 1 generated skills across 1 skill families.',
    });

    renderWithI18n(<SkillsPage />);

    expect(await screen.findByText('Skills & MCP')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Consolidate Generated' }));

    await waitFor(() => {
      expect(skillsService.consolidateGeneratedSkills).toHaveBeenCalledTimes(1);
    });

    await waitFor(() => {
      expect(skillsService.getSkills).toHaveBeenCalledTimes(2);
      expect(skillsService.getMcpServers).toHaveBeenCalledTimes(2);
    });

    expect(
      await screen.findByText('Consolidated 1 generated skills into 1 skill families'),
    ).toBeInTheDocument();
  });

  it('promotes a custom skill to builtin and refreshes the list', async () => {
    vi.mocked(skillsService.promoteSkill).mockResolvedValue({
      name: 'research-helper',
      path: '/builtin/research-helper/SKILL.md',
      source: 'builtin',
      message: 'Skill promoted',
    });

    renderWithI18n(<SkillsPage />);

    expect(await screen.findByText('research-helper')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Promote to Builtin' }));

    await waitFor(() => {
      expect(skillsService.promoteSkill).toHaveBeenCalledWith('research-helper');
    });

    await waitFor(() => {
      expect(skillsService.getSkills).toHaveBeenCalledTimes(2);
      expect(skillsService.getMcpServers).toHaveBeenCalledTimes(2);
    });

    expect(await screen.findByText('Skill "research-helper" promoted to builtin')).toBeInTheDocument();
  });

  it('exports a skill package from the card action', async () => {
    const createObjectURL = vi.fn(() => 'blob:skill-export');
    const revokeObjectURL = vi.fn();
    const click = vi.fn();
    Object.defineProperty(window.URL, 'createObjectURL', {
      configurable: true,
      value: createObjectURL,
    });
    Object.defineProperty(window.URL, 'revokeObjectURL', {
      configurable: true,
      value: revokeObjectURL,
    });

    renderWithI18n(<SkillsPage />);

    expect(await screen.findByText('research-helper')).toBeInTheDocument();

    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(click);

    fireEvent.click(screen.getByRole('button', { name: 'Export' }));

    await waitFor(() => {
      expect(skillsService.exportSkill).toHaveBeenCalledWith('research-helper');
    });
    const downloadAnchor = clickSpy.mock.instances[0] as HTMLAnchorElement;
    expect(downloadAnchor.download).toBe('research-helper.skill');
    expect(click).toHaveBeenCalledTimes(1);
    expect(await screen.findByText('Skill "research-helper" exported')).toBeInTheDocument();

    clickSpy.mockRestore();
  });

  it('shows the skill storage path and source hint in the detail modal', async () => {
    renderWithI18n(<SkillsPage />);

    expect(await screen.findByText('research-helper')).toBeInTheDocument();

    fireEvent.click(screen.getByText('research-helper'));

    expect(await screen.findByText('Storage Path')).toBeInTheDocument();
    expect(screen.getByText('/tmp/research-helper')).toBeInTheDocument();
    expect(
      screen.getByText('Custom skills are stored per agent under workspace/.horbot-agent/skills.'),
    ).toBeInTheDocument();
  });
});
