import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SkillsPage from './SkillsPage';
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

    render(<SkillsPage />);

    expect(screen.getByRole('status', { name: '页面加载中' })).toBeInTheDocument();
  });

  it('renders a page error state and retries the initial load', async () => {
    vi.mocked(skillsService.getSkills)
      .mockRejectedValueOnce(new Error('fetch failed'))
      .mockResolvedValueOnce([skillFixture]);
    vi.mocked(skillsService.getMcpServers)
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({});

    render(<SkillsPage />);

    expect(await screen.findByText('技能加载失败')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '重试' }));

    await waitFor(() => {
      expect(screen.getByText('Skills & MCP')).toBeInTheDocument();
    });

    expect(skillsService.getSkills).toHaveBeenCalledTimes(2);
    expect(skillsService.getMcpServers).toHaveBeenCalledTimes(2);
  });
});
