import { MemoryRouter } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import DashboardChannelsCard from './DashboardChannelsCard';

describe('DashboardChannelsCard', () => {
  it('renders channel summary counts and manage guidance', () => {
    render(
      <MemoryRouter>
        <DashboardChannelsCard
          counts={{ total: 3, enabled: 2, online: 1, disabled: 1, misconfigured: 1 }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText('Total')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('Missing Config')).toBeInTheDocument();
    expect(screen.getByText(/Channel details now live in the Channels page/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Manage/i })).toBeInTheDocument();
  });
});
