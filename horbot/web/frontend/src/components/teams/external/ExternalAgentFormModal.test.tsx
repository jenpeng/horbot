import { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { I18nProvider } from '../../../contexts/I18nContext';
import type { AgentCapabilityOption } from '../../../pages/teams/formOptions';
import type { ExternalAgentFormState } from '../../../pages/teams/types';
import ExternalAgentFormModal from './ExternalAgentFormModal';

const capabilityOptions: AgentCapabilityOption[] = [
  { id: 'research', label: 'Research', description: 'Find and synthesize external information' },
  { id: 'planning', label: 'Planning', description: 'Break work into actionable steps' },
];

const baseFormState: ExternalAgentFormState = {
  id: '',
  name: '',
  description: '',
  avatar: '',
  transport: 'http_sse',
  endpoint: '',
  auth_type: 'none',
  auth_header: 'Authorization',
  auth_secret: '',
  auth_secret_configured: false,
  capabilities: [],
  dm_enabled: true,
  team_enabled: false,
  mention_required: true,
  timeout_s: 90,
  max_turn_chars: 12000,
  context_scope: 'recent_turns',
  memory_access: 'none',
  file_access: 'none',
  metadata: {},
};

const renderModal = (initialForm: Partial<ExternalAgentFormState> = {}) => {
  const Wrapper = () => {
    const [form, setForm] = useState<ExternalAgentFormState>({
      ...baseFormState,
      ...initialForm,
    });

    return (
      <I18nProvider>
        <ExternalAgentFormModal
          mode="create"
          form={form}
          setForm={setForm}
          capabilityOptions={capabilityOptions}
          onClose={() => {}}
          onSubmit={() => {}}
        />
      </I18nProvider>
    );
  };

  return render(<Wrapper />);
};

const renderBehaviorStepModal = (initialForm: Partial<ExternalAgentFormState> = {}) => {
  renderModal({
    id: 'partner-agent',
    name: 'Partner Agent',
    endpoint: 'https://example.com/agent',
    ...initialForm,
  });
  fireEvent.click(screen.getByTestId('external-form-next'));
};

describe('ExternalAgentFormModal', () => {
  it('splits the form into connection and capability steps', () => {
    renderModal({
      id: 'partner-agent',
      name: 'Partner Agent',
      endpoint: 'https://example.com/agent',
    });

    expect(screen.getByTestId('external-form-step-connection')).toBeInTheDocument();
    expect(screen.queryByTestId('external-form-step-behavior')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('external-form-next'));

    expect(screen.getByTestId('external-form-step-behavior')).toBeInTheDocument();
    expect(screen.queryByTestId('external-form-step-connection')).not.toBeInTheDocument();
  });

  it('suggests connection setup from endpoint and description and applies it on demand', () => {
    renderModal({
      id: 'partner-agent',
      name: 'Partner Agent',
      endpoint: 'wss://example.com/agent',
      description: 'Uses bearer token and supports team relay via @mention.',
    });

    expect(screen.getByTestId('external-connection-recommendation')).toBeInTheDocument();
    expect(screen.getByTestId('external-connection-recommendation')).toHaveTextContent('WebSocket');
    expect(screen.getByTestId('external-connection-recommendation')).toHaveTextContent('Bearer');

    fireEvent.click(screen.getByTestId('apply-connection-recommendation'));

    expect(screen.getByLabelText('Transport')).toHaveValue('websocket');
    expect(screen.getByLabelText('Auth Type')).toHaveValue('bearer');
    fireEvent.click(screen.getByTestId('external-form-next'));
    expect(screen.getByRole('checkbox', { name: /Allow team participation/i })).toBeChecked();
  });

  it('recommends a preset from description and lets users apply it directly', () => {
    renderBehaviorStepModal({
      name: 'Repo QA Bot',
      description: 'Helps review pull requests, test changes, and inspect code quality.',
      endpoint: 'https://example.com/repo-agent',
    });

    expect(screen.getByTestId('external-capability-recommendation')).toHaveTextContent('Engineering Support');

    fireEvent.click(screen.getByRole('button', { name: /Use Recommendation/i }));

    expect(screen.getByTestId('selected-capability-code')).toBeInTheDocument();
    expect(screen.getByTestId('selected-capability-testing')).toBeInTheDocument();
    expect(screen.getByTestId('selected-capability-review')).toBeInTheDocument();
  });

  it('lets users apply a capability preset to fill common tags quickly', () => {
    renderBehaviorStepModal();

    fireEvent.click(screen.getByTestId('external-capability-preset-research'));

    expect(screen.getByTestId('selected-capability-research')).toBeInTheDocument();
    expect(screen.getByTestId('selected-capability-planning')).toBeInTheDocument();
    expect(screen.getByTestId('selected-capability-writing')).toBeInTheDocument();
  });

  it('lets users toggle suggested capability tags without manual typing', () => {
    renderBehaviorStepModal();

    expect(screen.getByText('No capability tags selected yet')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('toggle-manual-capabilities'));
    fireEvent.click(screen.getByRole('button', { name: /Research/i, pressed: false }));

    expect(screen.getByText('Selected Tags')).toBeInTheDocument();
    expect(screen.getByTestId('selected-capability-research')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Research/i, pressed: true }));

    expect(screen.getByText('No capability tags selected yet')).toBeInTheDocument();
    expect(screen.queryByTestId('selected-capability-research')).not.toBeInTheDocument();
  });

  it('lets users add custom capability tags as a supplement', () => {
    renderBehaviorStepModal();

    fireEvent.click(screen.getByTestId('toggle-manual-capabilities'));
    fireEvent.change(screen.getByLabelText('Custom Tags'), {
      target: { value: 'finance, api' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));

    expect(screen.getByRole('button', { name: /finance/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /api/i })).toBeInTheDocument();
  });

  it('keeps runtime settings collapsed by default until users expand them', () => {
    renderBehaviorStepModal();

    expect(screen.queryByLabelText('Timeout (seconds)')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('toggle-runtime-settings'));

    expect(screen.getByLabelText('Timeout (seconds)')).toBeInTheDocument();
    expect(screen.getByLabelText('Context Scope')).toBeInTheDocument();
  });
});
