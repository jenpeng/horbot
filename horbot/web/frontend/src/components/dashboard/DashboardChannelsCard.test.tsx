import { MemoryRouter } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import DashboardChannelsCard from './DashboardChannelsCard';

describe('DashboardChannelsCard', () => {
  it('renders channel summary counts and missing field hints', () => {
    render(
      <MemoryRouter>
        <DashboardChannelsCard
          counts={{ total: 3, enabled: 2, online: 1, disabled: 1, misconfigured: 1 }}
          channels={[
            {
              name: 'wechat',
              display_name: 'WeChat',
              enabled: true,
              configured: true,
              status: 'online',
              status_label: '就绪',
              reason: null,
              missing_fields: [],
            },
            {
              name: 'slack',
              display_name: 'Slack',
              enabled: true,
              configured: false,
              status: 'error',
              status_label: '配置缺失',
              reason: null,
              missing_fields: ['token', 'signing_secret'],
            },
          ]}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText('3 Total')).toBeInTheDocument();
    expect(screen.getByText('1 Missing Config')).toBeInTheDocument();
    expect(screen.getByText('缺少配置: token, signing_secret')).toBeInTheDocument();
    expect(screen.getAllByText('View')).toHaveLength(2);
  });
});
