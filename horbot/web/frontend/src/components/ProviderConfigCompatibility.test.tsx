import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactElement } from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { I18nProvider } from '../contexts/I18nContext';
import ProviderCard from './ProviderCard';
import ProviderManager from './ProviderManager';

const { updateProvider, addProvider } = vi.hoisted(() => ({
  updateProvider: vi.fn(),
  addProvider: vi.fn(),
}));

vi.mock('../services', () => ({
  configService: {
    updateProvider,
    addProvider,
  },
}));

const renderWithI18n = (ui: ReactElement) => render(<I18nProvider>{ui}</I18nProvider>);

describe('Provider compatibility profile controls', () => {
  beforeEach(() => {
    updateProvider.mockReset();
    addProvider.mockReset();
  });

  it('saves compatibility profile changes from provider cards', async () => {
    updateProvider.mockResolvedValue(undefined);

    renderWithI18n(
      <ProviderCard
        name="custom"
        settings={{
          apiKey: '',
          hasApiKey: true,
          apiKeyMasked: 'sk-***',
          apiBase: 'https://example.test/v1',
          compatibilityProfile: 'auto',
        }}
      />,
    );

    fireEvent.click(screen.getByTestId('provider-card-toggle'));
    fireEvent.change(screen.getByTestId('provider-card-compatibility-profile-select'), {
      target: { value: 'newapi' },
    });
    fireEvent.click(screen.getByTestId('provider-card-save'));

    await waitFor(() => {
      expect(updateProvider).toHaveBeenCalledWith(
        'custom',
        expect.objectContaining({
          compatibilityProfile: 'newapi',
        }),
      );
    });
  });

  it('includes compatibility profile when adding custom providers', async () => {
    addProvider.mockResolvedValue(undefined);
    const onProviderAdded = vi.fn();

    renderWithI18n(
      <ProviderManager
        providers={{}}
        onProviderAdded={onProviderAdded}
      />,
    );

    fireEvent.click(screen.getByTestId('provider-add-button'));
    fireEvent.change(screen.getByTestId('provider-name-input'), {
      target: { value: 'newapi-gateway' },
    });
    fireEvent.change(screen.getByTestId('provider-compatibility-profile-select'), {
      target: { value: 'newapi' },
    });
    fireEvent.click(screen.getByTestId('provider-add-confirm'));

    await waitFor(() => {
      expect(addProvider).toHaveBeenCalledWith(
        'newapi-gateway',
        expect.objectContaining({
          compatibilityProfile: 'newapi',
        }),
      );
    });
  });
});
